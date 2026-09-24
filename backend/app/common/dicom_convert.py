# -*- coding: utf-8 -*-
"""
眼底照片 → DICOM Ophthalmic Photography 转换

对应《慧眼医学培训端-重构技术方案》决策三「全量 DICOM 化」与报告 P0/P1：
    「数据层级：单层病例宽表；影像/图层混算 → 患者-检查-序列-实例-派生结果」
    「安全标识：眼别/日期/模态不固定 → 安全条常驻，图像级眼别一致」

为什么要转 DICOM 而不是自建层级表：
    患者-检查-序列-实例是 DICOM 的原生数据模型，眼别（Image Laterality）、
    模态、采集时间都是标准字段。转过去之后 Orthanc / Cornerstone3D / OHIF
    可直接消费，不需要为每个组件写适配层。

关键设计
    1. UID 确定性派生：同一张影像重复转换得到相同 UID，转换过程幂等，
       重跑不会在 PACS 里产生重复实例；
    2. 眼别冲突不静默处理：元数据与文件名冲突时抛出，由调用方决定阻断或告警
       （报告 8.3 首条 P0 用例）；
    3. 未知信息留空而非编造：没有真实检查日期时不写 AcquisitionDateTime，
       绝不用入库时间冒充。
"""

import hashlib
from datetime import datetime
from pathlib import Path
from typing import Optional, Tuple

import numpy as np
from PIL import Image
from pydicom.dataset import Dataset, FileDataset, FileMetaDataset
from pydicom.encaps import encapsulate
from pydicom.uid import ExplicitVRLittleEndian, JPEGBaseline8Bit, generate_uid

from app.common.image_safety import EYE_TEXT, detect_laterality_conflict

# VL Photographic Image Storage
#
# 为什么不用 Ophthalmic Photography 8 Bit（1.2.840.10008.5.1.4.1.1.77.1.5.1）：
# 该 IOD 允许多帧，因此按标准需要多帧功能组，其中 PixelMeasuresSequence
# 要求 PixelSpacing。眼底照未做尺度标定，这个值我们没有真实来源，
# 填进去等于编造数据。VL Photographic 是单帧 IOD，也是眼底相机的常见输出，
# 语义同样成立且不需要伪造任何标定信息。
VL_PHOTO_SOP_CLASS_UID = "1.2.840.10008.5.1.4.1.1.77.1.4"

# 旧名保留，避免调用方与既有测试全部改名
OP_SOP_CLASS_UID = VL_PHOTO_SOP_CLASS_UID

# 平台自有 UID 根。正式对外交换数据前应向 IANA 申请组织专属 UID 根，
# 此处使用 2.25.<UUID 十进制> 形式的临时根，符合 DICOM 对 UID 的格式要求。
UID_ROOT = "2.25"

MODALITY_OP = "OP"  # Ophthalmic Photography


class LateralityConflictError(ValueError):
    """眼别冲突：元数据与文件名不一致，拒绝转换而不是静默取值"""


def deterministic_uid(*parts: str) -> str:
    """
    由稳定输入派生 UID，保证同一张影像每次转换得到相同 UID。

    这样转换过程是幂等的：重跑不会在 PACS 中产生重复实例，
    也便于把 DICOM 实例与业务库记录一一对应。
    """
    raw = "|".join(str(p) for p in parts)
    digest = hashlib.sha256(raw.encode("utf-8")).hexdigest()
    # 取前 32 位十六进制转十进制，控制长度在 UID 上限（64 字符）内
    suffix = str(int(digest[:32], 16))[:38]
    return f"{UID_ROOT}.{suffix}"


def _normalize_laterality(eye: Optional[str]) -> str:
    """
    归一化眼别为 DICOM Image Laterality 取值。

    DICOM 的 Image Laterality 只接受 R / L（单眼）；OU（双眼）不是合法的
    图像级取值——一张图不可能同时是左眼和右眼。因此 OU 与未知都返回空串，
    由调用方决定如何处理，绝不猜成某一侧。
    """
    code = (eye or "").strip().upper()
    return {"OD": "R", "OS": "L"}.get(code, "")


def _load_pixels(path: Path) -> Tuple[np.ndarray, int, int]:
    """读入图像并转为 RGB 三通道 uint8"""
    with Image.open(path) as im:
        if im.mode != "RGB":
            im = im.convert("RGB")
        arr = np.asarray(im, dtype=np.uint8)
    h, w = arr.shape[0], arr.shape[1]
    return arr, w, h


def can_embed_jpeg(path: Path) -> Tuple[bool, str, int, int]:
    """
    判断源文件能否以 JPEG Baseline 原样内嵌进 DICOM。

    可内嵌的条件：本身就是 JPEG、8 位、三通道、且非渐进式
    （DICOM 的 JPEG Baseline 传输语法不接受渐进式编码）。

    :return: (是否可内嵌, 不可内嵌的原因, 宽, 高)
    """
    try:
        with Image.open(path) as im:
            fmt = (im.format or "").upper()
            mode = im.mode
            progressive = bool(im.info.get("progression"))
            w, h = im.size
    except Exception as exc:
        return False, f"无法读取图像：{exc}", 0, 0

    if fmt != "JPEG":
        return False, f"源文件不是 JPEG（{fmt}）", w, h
    if progressive:
        return False, "渐进式 JPEG，DICOM JPEG Baseline 不支持", w, h
    if mode not in ("RGB", "L"):
        return False, f"不支持的色彩模式 {mode}", w, h
    return True, "", w, h


def build_op_dataset(
    *,
    image_path: Path,
    patient_id: str,
    patient_name: str = "",
    patient_birth_date: str = "",
    patient_sex: str = "",
    accession_number: str = "",
    case_no: str = "",
    eye: Optional[str] = None,
    file_name: str = "",
    role: str = "",
    exam_datetime: Optional[datetime] = None,
    series_description: str = "",
    instance_number: int = 1,
    strict_laterality: bool = True,
    embed_jpeg: bool = True,
) -> FileDataset:
    """
    构造一份 Ophthalmic Photography DICOM 实例。

    :param exam_datetime: 真实检查时间。为 None 时不写入采集时间字段——
                          宁可留空，也不用入库时间冒充检查时间。
    :param strict_laterality: 眼别与文件名冲突时是否抛错（默认抛）
    :param embed_jpeg: 源文件是 baseline JPEG 时，原样内嵌其压缩字节
                       （JPEG Baseline 传输语法）。

    关于 embed_jpeg：眼底照解压成 RGB 后体积会膨胀约 30 倍
    （实测 0.4~1.5 MB 的 JPG 变成 14~43 MB），全量转换会迅速吃满磁盘。
    内嵌原始 JPEG 字节既是眼科影像的通行做法，也不引入二次压缩损失——
    像素数据与原文件逐字节相同。
    """
    if not image_path.exists():
        raise FileNotFoundError(f"影像文件不存在：{image_path}")

    # ---- 眼别一致性校验（报告 8.3 首条 P0）----
    conflict = detect_laterality_conflict(
        eye=eye, file_name=file_name or image_path.name, role=role,
    )
    if conflict and strict_laterality:
        raise LateralityConflictError(conflict)

    # ---- 像素来源：优先原样内嵌 JPEG，避免解压后体积暴涨 ----
    embeddable, _reason, width, height = can_embed_jpeg(image_path)
    use_jpeg = bool(embed_jpeg and embeddable)

    if use_jpeg:
        jpeg_bytes = image_path.read_bytes()
        pixels = None
    else:
        pixels, width, height = _load_pixels(image_path)
        jpeg_bytes = None

    # ---- UID：由病例与影像稳定派生，保证幂等 ----
    study_uid = deterministic_uid("study", patient_id, case_no)
    series_uid = deterministic_uid("series", patient_id, case_no, eye or "NA")
    sop_uid = deterministic_uid("sop", patient_id, case_no, str(image_path))

    file_meta = FileMetaDataset()
    file_meta.MediaStorageSOPClassUID = OP_SOP_CLASS_UID
    file_meta.MediaStorageSOPInstanceUID = sop_uid
    file_meta.TransferSyntaxUID = JPEGBaseline8Bit if use_jpeg else ExplicitVRLittleEndian
    file_meta.ImplementationClassUID = generate_uid()

    ds = FileDataset(None, {}, file_meta=file_meta, preamble=b"\0" * 128)

    # ---- 字符集 ----
    # 必须显式声明，否则 pydicom 按默认的 ISO-8859 编码写入，
    # 中文姓名会被替换字符顶掉而永久丢失。ISO_IR 192 即 UTF-8。
    ds.SpecificCharacterSet = "ISO_IR 192"

    # ---- 患者层 ----
    ds.PatientID = patient_id
    # DICOM 的 PN 由「姓^名^中间名^前缀^后缀」组成。单段名（如病例编号）
    # 必须加尾部脱字符消歧，否则下游会把它当成不完整的姓名解析。
    _name = patient_name or patient_id
    ds.PatientName = _name if "^" in _name else f"{_name}^"
    ds.PatientBirthDate = patient_birth_date
    ds.PatientSex = patient_sex if patient_sex in ("M", "F", "O") else ""

    # ---- 检查层 ----
    ds.StudyInstanceUID = study_uid
    ds.StudyID = (case_no or "")[:16]
    ds.AccessionNumber = accession_number
    ds.StudyDescription = "眼底照相"

    # ---- 序列层 ----
    ds.SeriesInstanceUID = series_uid
    ds.SeriesNumber = 1
    ds.Modality = MODALITY_OP
    ds.SeriesDescription = series_description or "Color Fundus Photography"

    # ---- VL 图像模块（VL Photographic IOD 必需）----
    # ImageType 为 Type 1；AcquisitionContextSequence 为 Type 2，
    # 无采集上下文时留空序列即可，不需要编造内容。
    ds.ImageType = ["ORIGINAL", "PRIMARY"]
    ds.AcquisitionContextSequence = []

    # ---- 实例层 ----
    ds.SOPClassUID = OP_SOP_CLASS_UID
    ds.SOPInstanceUID = sop_uid
    ds.InstanceNumber = instance_number

    # ---- 眼别 ----
    laterality = _normalize_laterality(eye)
    if laterality:
        ds.ImageLaterality = laterality
        ds.Laterality = laterality
    # OU / 未知：不写该字段。DICOM 无「双眼」这一图像级取值，
    # 编造一个会让下游把双眼图当成某一只眼。

    # ---- 采集时间 ----
    # 报告要求「不得用入库时间冒充检查日期」，因此未知时不填任何值。
    #
    # 但 StudyDate / StudyTime 在 DICOM 中是 Type 2：必须存在，允许零长度。
    # 早先直接省略这两个标签是不符合规范的，也会让下游工具（如 highdicom
    # 生成 SEG 时）取不到属性而报错。正确表达「未知」的方式是写空值。
    if exam_datetime is not None:
        ds.AcquisitionDateTime = exam_datetime.strftime("%Y%m%d%H%M%S")
        ds.StudyDate = exam_datetime.strftime("%Y%m%d")
        ds.StudyTime = exam_datetime.strftime("%H%M%S")
        ds.ContentDate = ds.StudyDate
        ds.ContentTime = ds.StudyTime
    else:
        ds.StudyDate = ""
        ds.StudyTime = ""
        ds.ContentDate = ""
        ds.ContentTime = ""
        # AcquisitionDateTime 是 Type 3（可选），未知时不写

    # ---- 像素 ----
    ds.SamplesPerPixel = 3
    ds.PlanarConfiguration = 0
    ds.Rows = height
    ds.Columns = width
    # VL Photographic 是单帧 IOD，不写 NumberOfFrames
    # （该属性仅在多帧时为必需）
    ds.BitsAllocated = 8
    ds.BitsStored = 8
    ds.HighBit = 7
    ds.PixelRepresentation = 0

    if use_jpeg:
        # JPEG Baseline 中三通道数据的色彩空间是 YCbCr（4:2:2 子采样），
        # 声明成 RGB 会让阅读器把颜色解错。
        ds.PhotometricInterpretation = "YBR_FULL_422"
        ds.LossyImageCompression = "01"
        ds.LossyImageCompressionMethod = "ISO_10918_1"
        ds.PixelData = encapsulate([jpeg_bytes])
        ds["PixelData"].is_undefined_length = True
    else:
        ds.PhotometricInterpretation = "RGB"
        ds.PixelData = pixels.tobytes()

    # 字节序与 VR 由 file_meta.TransferSyntaxUID（Explicit VR Little Endian）
    # 决定；pydicom 3.x 起不再需要（也不建议）在数据集上单独设置这两个属性。
    return ds


def convert_image_to_dicom(
    *,
    image_path: Path,
    output_path: Path,
    **kwargs,
) -> FileDataset:
    """转换并落盘，返回构造好的数据集"""
    ds = build_op_dataset(image_path=image_path, **kwargs)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    ds.save_as(str(output_path), enforce_file_format=True)
    return ds


def describe(ds: Dataset) -> dict:
    """提取关键标签，便于转换后核对与测试断言"""
    lat = getattr(ds, "ImageLaterality", "")
    return {
        "patientId": getattr(ds, "PatientID", ""),
        "studyUid": getattr(ds, "StudyInstanceUID", ""),
        "seriesUid": getattr(ds, "SeriesInstanceUID", ""),
        "sopUid": getattr(ds, "SOPInstanceUID", ""),
        "modality": getattr(ds, "Modality", ""),
        "laterality": lat,
        "lateralityText": {"R": EYE_TEXT["OD"], "L": EYE_TEXT["OS"]}.get(lat, "未标注"),
        "rows": int(getattr(ds, "Rows", 0)),
        "columns": int(getattr(ds, "Columns", 0)),
        "acquisitionDateTime": getattr(ds, "AcquisitionDateTime", ""),
    }
