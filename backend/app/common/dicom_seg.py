# -*- coding: utf-8 -*-
"""
病灶掩码 → DICOM Segmentation (SEG)

对应《医学培训端评估与工作流重构报告》P1：
    「影像与图层混算：病例列表的『8 张/9 张影像』实际混合原图、mask、
      病灶层和金标准，医生无法确认是否完整阅完原始检查。」

做法
    把每张原图的全部病灶掩码合并成 **一个多分段 SEG 实例**，
    并通过 Referenced Series 指回原图。于是：
        原图     = 1 个 OP 实例（属于「影像」）
        病灶标注 = 1 个 SEG 实例（属于「派生对象」）
    两者在 DICOM 层面天然分离，不会再被混算成「N 张影像」。

    overlay / color_mask / class_mask 属于渲染出来的可视化图，
    不是分割数据，不做 SEG——它们可由原图 + SEG 随时重新渲染。

关于分段类型与体积
    使用 BINARY（每像素每分段 1 比特，无损、允许分段重叠）。
    掩码极稀疏（非零像素约 4%），单个 SEG 约 5.8 MB，81 例合计约 470 MB，
    比原图（36 MB）大一个量级。曾评估两种压缩方案，均不采用：

      · RLE 无损：DICOM 规定不能用于 BINARY 分段（比特打包与 RLE 不兼容）；
      · LABELMAP + RLE：可大幅压缩，但每个像素只能属于一个分段。
        实测 81 例中有 31 例存在分段重叠（如视盘与病灶交叠，
        重叠面积占标注区 0.00%~0.10%），改用 LABELMAP 会静默丢弃
        重叠处的一个分段——为省空间而丢金标准数据，不可接受。

    因此保留 BINARY。若后续磁盘吃紧，正确方向是把 SEG 与原图分卷存放，
    而不是改变分段语义。

关于编码
    DICOM 要求每个分段声明「属性类别」与「属性类型」编码。
    眼底病灶的标准 SNOMED CT 编码需要逐条核对，未经核实就填入
    等于在数据里写下无法追溯的断言。因此这里统一使用私有编码方案
    99HUIYAN（DICOM 约定私有方案以 99 开头），编码含义清晰可读；
    待临床确认标准编码后，只需替换本文件的映射表即可，
    不影响已生成实例的结构。
"""

from pathlib import Path
from typing import Dict, List, Optional, Tuple

import numpy as np
from PIL import Image

Image.MAX_IMAGE_PIXELS = None

# 私有编码方案：待临床核对 SNOMED CT 后替换
PRIVATE_SCHEME = "99HUIYAN"

# role → (编码值, 中文含义, 是否为解剖结构)
SEGMENT_DEFS: Dict[str, Tuple[str, str, bool]] = {
    "MA": ("MA", "微动脉瘤", False),
    "HE": ("HE", "视网膜出血", False),
    "EX": ("EX", "硬性渗出", False),
    "SE": ("SE", "软性渗出（棉绒斑）", False),
    "OD": ("OD", "视盘", True),
}

# 参与 SEG 的角色；其余派生对象是渲染图，不做分割
SEGMENTABLE_ROLES = tuple(SEGMENT_DEFS.keys())

# 渲染类派生对象：可由原图 + SEG 重新生成，不迁入 PACS
RENDERED_ROLES = ("overlay", "color_mask", "class_mask", "heatmap")


def load_mask(path: Path, shape: Optional[Tuple[int, int]] = None) -> Optional[np.ndarray]:
    """
    读入掩码并二值化。

    返回 uint8 的 0/1 数组；掩码为空（全 0）时返回 None——
    空分段没有意义，写进 SEG 只会制造噪声。
    """
    if not path.exists():
        return None
    with Image.open(path) as im:
        arr = np.asarray(im.convert("L"))
    binary = (arr > 0).astype(np.uint8)
    if binary.sum() == 0:
        return None
    if shape is not None and binary.shape != shape:
        # 尺寸不一致时不做缩放：掩码与原图必须严格对齐，
        # 缩放会让病灶位置偏移，宁可报错也不能悄悄改数据
        raise ValueError(
            f"掩码尺寸 {binary.shape} 与原图 {shape} 不一致：{path.name}"
        )
    return binary


def build_segment_descriptions(roles: List[str]):
    """按角色生成 highdicom 的分段描述"""
    from highdicom.content import AlgorithmIdentificationSequence
    from highdicom.seg.content import SegmentDescription
    from highdicom.seg.enum import SegmentAlgorithmTypeValues
    from pydicom.sr.coding import Code

    algo = AlgorithmIdentificationSequence(
        name="IDRiD reference annotation",
        version="1.0",
        family=Code("111100", "DCM", "Artificial Intelligence"),
    )

    descriptions = []
    for idx, role in enumerate(roles, start=1):
        code_value, meaning, is_anatomy = SEGMENT_DEFS[role]
        category = (
            Code("ANATOMY", PRIVATE_SCHEME, "解剖结构")
            if is_anatomy
            else Code("LESION", PRIVATE_SCHEME, "病变")
        )
        descriptions.append(
            SegmentDescription(
                segment_number=idx,
                segment_label=meaning,
                segmented_property_category=category,
                segmented_property_type=Code(code_value, PRIVATE_SCHEME, meaning),
                algorithm_type=SegmentAlgorithmTypeValues.MANUAL,
                algorithm_identification=algo,
            )
        )
    return descriptions


def build_seg(
    *,
    source_dataset,
    masks: Dict[str, np.ndarray],
    series_number: int = 100,
    instance_number: int = 1,
    series_description: str = "病灶分割（金标准）",
    device_serial: str = "HUIYAN-SEG-1",
):
    """
    由原图数据集与若干掩码构造一个多分段 SEG 实例。

    :param source_dataset: 原图的 pydicom Dataset（提供患者/检查/序列引用）
    :param masks: {role: 二值掩码}，顺序即分段编号顺序
    :return: highdicom Segmentation 实例
    """
    import highdicom as hd

    roles = [r for r in SEGMENTABLE_ROLES if r in masks]
    if not roles:
        return None

    # (frames, rows, cols) —— 单帧影像，每个分段一层
    pixel_array = np.stack([masks[r] for r in roles], axis=0)
    # highdicom 要求形状为 (frames, rows, cols) 且分段维度单独传
    # 单帧多分段时用 (1, rows, cols, segments)
    pixel_array = np.moveaxis(pixel_array, 0, -1)[np.newaxis, ...]

    from app.common.dicom_convert import UID_ROOT, deterministic_uid

    return hd.seg.Segmentation(
        source_images=[source_dataset],
        pixel_array=pixel_array,
        segmentation_type=hd.seg.SegmentationTypeValues.BINARY,
        segment_descriptions=build_segment_descriptions(roles),
        series_instance_uid=deterministic_uid(
            "seg-series", getattr(source_dataset, "PatientID", ""),
            getattr(source_dataset, "StudyID", ""),
        ),
        series_number=series_number,
        sop_instance_uid=deterministic_uid(
            "seg-sop", getattr(source_dataset, "SOPInstanceUID", ""),
            ",".join(roles),
        ),
        instance_number=instance_number,
        manufacturer="Huiyan",
        manufacturer_model_name="Huiyan DICOM Migration",
        software_versions="1.0",
        device_serial_number=device_serial,
        series_description=series_description,
        omit_empty_frames=False,
    )
