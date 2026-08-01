# -*- coding: utf-8 -*-
"""
眼底照片 → DICOM Ophthalmic Photography 转换测试

对应方案决策三「全量 DICOM 化」与报告 P0/P1：
    患者-检查-序列-实例层级、图像级眼别一致、不用入库时间冒充检查时间。
"""

import warnings
from datetime import datetime
from pathlib import Path

import numpy as np
import pytest
from PIL import Image

from app.common.dicom_convert import (
    LateralityConflictError,
    OP_SOP_CLASS_UID,
    build_op_dataset,
    convert_image_to_dicom,
    deterministic_uid,
    describe,
)

pydicom = pytest.importorskip("pydicom")


@pytest.fixture
def fundus_image(tmp_path: Path) -> Path:
    """
    造一张小尺寸假眼底图，避免测试依赖真实数据集。

    固定随机种子：像素内容影响 JPEG 编码结果，不固定会让涉及
    色彩转换舍入的断言时通过时失败。
    """
    path = tmp_path / "IDRiD_01.jpg"
    rng = np.random.default_rng(20260801)
    arr = rng.integers(0, 255, (32, 48, 3), dtype=np.uint8)
    Image.fromarray(arr).save(path)
    return path


def _build(image_path: Path, **kw):
    params = dict(
        patient_id="P0001", patient_name="测试患者",
        case_no="T2026001", eye="OD", file_name=image_path.name,
    )
    params.update(kw)
    return build_op_dataset(image_path=image_path, **params)


# --------------------------------------------------------------------------
# SOP / 模态
# --------------------------------------------------------------------------

def test_sop_class_is_vl_photographic(fundus_image):
    """
    使用 VL Photographic Image Storage（单帧 IOD）。

    不用 Ophthalmic Photography 8 Bit 的原因：该 IOD 允许多帧，
    按标准需要多帧功能组，其中 PixelMeasuresSequence 要求 PixelSpacing——
    眼底照未做尺度标定，没有真实值可填。
    Modality 仍为 OP：这些确实是眼科摄影，临床语义不因 SOP 类而改变。
    """
    ds = _build(fundus_image)
    assert ds.SOPClassUID == "1.2.840.10008.5.1.4.1.1.77.1.4"
    assert ds.Modality == "OP"


def test_pixel_data_round_trip(fundus_image, tmp_path):
    """写出后能被标准 DICOM 阅读器解回正确尺寸的三通道图像"""
    out = tmp_path / "out.dcm"
    convert_image_to_dicom(
        image_path=fundus_image, output_path=out,
        patient_id="P1", case_no="T1", eye="OD", file_name=fundus_image.name,
    )
    re = pydicom.dcmread(str(out))
    assert re.pixel_array.shape == (32, 48, 3)
    assert re.BitsAllocated == 8
    assert re.SamplesPerPixel == 3
    # 默认对 baseline JPEG 走内嵌，色彩空间为 YCbCr；
    # 未压缩回退路径的 RGB 断言见 test_embed_can_be_disabled
    assert re.PhotometricInterpretation == "YBR_FULL_422"


# --------------------------------------------------------------------------
# 患者-检查-序列-实例层级
# --------------------------------------------------------------------------

def test_hierarchy_uids_present(fundus_image):
    ds = _build(fundus_image)
    assert ds.PatientID
    assert ds.StudyInstanceUID
    assert ds.SeriesInstanceUID
    assert ds.SOPInstanceUID
    # 三级 UID 必须互不相同，否则层级就塌成一层了
    assert len({ds.StudyInstanceUID, ds.SeriesInstanceUID, ds.SOPInstanceUID}) == 3


def test_same_case_shares_study_uid(fundus_image, tmp_path):
    """同一病例的不同影像应归入同一个 Study"""
    other = tmp_path / "IDRiD_02.jpg"
    Image.fromarray(np.zeros((16, 16, 3), dtype=np.uint8)).save(other)

    a = _build(fundus_image, eye="OD")
    b = _build(other, eye="OS", file_name=other.name)
    assert a.StudyInstanceUID == b.StudyInstanceUID
    # 左右眼分属不同序列
    assert a.SeriesInstanceUID != b.SeriesInstanceUID
    assert a.SOPInstanceUID != b.SOPInstanceUID


def test_uid_is_deterministic(fundus_image):
    """
    幂等性：同一张影像重复转换必须得到相同 UID，
    否则每次重跑都会在 PACS 里堆出重复实例。
    """
    a = _build(fundus_image)
    b = _build(fundus_image)
    assert a.SOPInstanceUID == b.SOPInstanceUID
    assert a.StudyInstanceUID == b.StudyInstanceUID


def test_uid_within_dicom_length_limit():
    uid = deterministic_uid("study", "P" * 40, "T" * 40)
    assert len(uid) <= 64, "DICOM UID 上限 64 字符"
    assert all(part.isdigit() for part in uid.split("."))


def test_different_cases_get_different_uids(fundus_image):
    a = _build(fundus_image, case_no="T2026001")
    b = _build(fundus_image, case_no="T2026002")
    assert a.StudyInstanceUID != b.StudyInstanceUID


# --------------------------------------------------------------------------
# 眼别（报告 8.3 首条 P0）
# --------------------------------------------------------------------------

@pytest.mark.parametrize("eye,expected", [("OD", "R"), ("OS", "L")])
def test_laterality_mapping(fundus_image, eye, expected):
    ds = _build(fundus_image, eye=eye)
    assert ds.ImageLaterality == expected
    assert ds.Laterality == expected


@pytest.mark.parametrize("eye", ["OU", "", None, "XX"])
def test_ou_and_unknown_do_not_get_a_side(fundus_image, eye):
    """
    DICOM 的 Image Laterality 只有 R/L，没有「双眼」。
    OU 或未知时必须不写该字段——编造一侧会让下游把双眼图当成单眼图。
    """
    ds = _build(fundus_image, eye=eye)
    assert "ImageLaterality" not in ds


def test_laterality_conflict_blocks_conversion(fundus_image):
    """元数据 OD、文件名 OS → 拒绝转换，不静默取值"""
    with pytest.raises(LateralityConflictError) as exc:
        _build(fundus_image, eye="OD", file_name="patient_OS_001.jpg")
    assert "OD" in str(exc.value) and "OS" in str(exc.value)


def test_laterality_conflict_can_be_downgraded_explicitly(fundus_image):
    """
    迁移场景下允许显式放行，但必须由调用方主动关闭严格模式，
    不能是默认行为。
    """
    ds = _build(
        fundus_image, eye="OD", file_name="patient_OS_001.jpg",
        strict_laterality=False,
    )
    assert ds.ImageLaterality == "R"


# --------------------------------------------------------------------------
# 检查时间：不得用入库时间冒充
# --------------------------------------------------------------------------

def test_no_exam_datetime_means_empty_not_fabricated(fundus_image):
    """
    检查时间未知时不得填任何值（尤其不能拿入库时间冒充）。

    但 StudyDate / StudyTime 是 DICOM Type 2：必须存在、允许零长度。
    正确表达「未知」是写空值而不是省略标签——省略既不符合规范，
    也会让下游工具取不到属性而报错。
    """
    ds = _build(fundus_image, exam_datetime=None)
    # Type 3，可选，未知时不写
    assert "AcquisitionDateTime" not in ds
    # Type 2，必须存在但为空
    assert "StudyDate" in ds
    assert ds.StudyDate == ""
    assert "StudyTime" in ds
    assert ds.StudyTime == ""


def test_empty_study_date_is_not_a_real_date(fundus_image):
    """空值不能被误读成某个具体日期"""
    ds = _build(fundus_image, exam_datetime=None)
    assert not str(ds.StudyDate).strip()


def test_exam_datetime_is_written_when_known(fundus_image):
    ds = _build(fundus_image, exam_datetime=datetime(2026, 5, 14, 9, 30, 0))
    assert ds.AcquisitionDateTime == "20260514093000"
    assert ds.StudyDate == "20260514"
    assert ds.StudyTime == "093000"


# --------------------------------------------------------------------------
# 字符集：中文姓名必须无损
# --------------------------------------------------------------------------

def test_chinese_patient_name_round_trip(fundus_image, tmp_path):
    """
    未声明 SpecificCharacterSet 时 pydicom 按 ISO-8859 编码，
    中文姓名会被替换字符顶掉而永久丢失。
    """
    out = tmp_path / "cn.dcm"
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        convert_image_to_dicom(
            image_path=fundus_image, output_path=out,
            patient_id="P1", patient_name="张三丰",
            case_no="T1", eye="OD", file_name=fundus_image.name,
        )
        encode_warnings = [w for w in caught if "encode" in str(w.message)]

    assert not encode_warnings, "出现编码告警说明字符集未正确声明"

    re = pydicom.dcmread(str(out))
    assert re.SpecificCharacterSet == "ISO_IR 192"
    # 单段名会被补上尾部脱字符以符合 DICOM PN 规范，比对时去掉
    assert str(re.PatientName).rstrip("^") == "张三丰"


# --------------------------------------------------------------------------
# describe 辅助
# --------------------------------------------------------------------------

def test_describe_exposes_key_tags(fundus_image):
    d = describe(_build(fundus_image, eye="OS"))
    assert d["modality"] == "OP"
    assert d["laterality"] == "L"
    assert d["lateralityText"] == "左眼"
    assert d["rows"] == 32 and d["columns"] == 48


def test_describe_unlabelled_laterality(fundus_image):
    d = describe(_build(fundus_image, eye="OU"))
    assert d["laterality"] == ""
    assert d["lateralityText"] == "未标注"


# --------------------------------------------------------------------------
# JPEG 内嵌：控制存储体积且不引入二次压缩
# --------------------------------------------------------------------------

def test_jpeg_source_is_embedded_not_decompressed(fundus_image, tmp_path):
    """
    眼底照解压成 RGB 后体积膨胀约 30 倍（实测 1.5 MB → 43 MB），
    全量转换会迅速吃满磁盘。baseline JPEG 应原样内嵌。
    """
    from pydicom.uid import JPEGBaseline8Bit

    out = tmp_path / "embed.dcm"
    convert_image_to_dicom(
        image_path=fundus_image, output_path=out,
        patient_id="P1", case_no="T1", eye="OD", file_name=fundus_image.name,
    )
    re = pydicom.dcmread(str(out))
    assert re.file_meta.TransferSyntaxUID == JPEGBaseline8Bit
    # JPEG 中的三通道是 YCbCr，声明成 RGB 会让阅读器解错颜色
    assert re.PhotometricInterpretation == "YBR_FULL_422"
    # 内嵌后文件不应比源文件大太多
    assert out.stat().st_size < fundus_image.stat().st_size * 3


def test_embedded_frame_is_byte_identical_to_source(fundus_image, tmp_path):
    """
    内嵌是字节透传：DICOM 里存的那一帧应与源 JPEG 文件逐字节相同，
    没有二次编码，因此不会引入任何额外的压缩损失。

    这是本方案真正的保证，比比较解码后的像素更严格也更确定。
    """
    from pydicom.encaps import generate_frames

    out = tmp_path / "embed.dcm"
    convert_image_to_dicom(
        image_path=fundus_image, output_path=out,
        patient_id="P1", case_no="T1", eye="OD", file_name=fundus_image.name,
    )
    ds = pydicom.dcmread(str(out))
    frames = list(generate_frames(ds.PixelData, number_of_frames=1))
    assert len(frames) == 1
    assert bytes(frames[0]) == fundus_image.read_bytes(), "内嵌帧应与源文件字节一致"


def test_decoded_pixels_match_source_within_rounding(fundus_image, tmp_path):
    """
    解码后的像素与直接读源图应当一致。

    容差 1：JPEG 的三通道是 YCbCr，解码链路在 YCbCr→RGB 转换上
    可能有 ±1 的舍入差（高频噪声图上偶发，真实眼底照实测为 0）。
    这属于色彩转换舍入，不是数据丢失——存储的字节由上一个测试保证无损。
    """
    out = tmp_path / "embed.dcm"
    convert_image_to_dicom(
        image_path=fundus_image, output_path=out,
        patient_id="P1", case_no="T1", eye="OD", file_name=fundus_image.name,
    )
    decoded = pydicom.dcmread(str(out)).pixel_array
    with Image.open(fundus_image) as im:
        reference = np.asarray(im.convert("RGB"))

    assert decoded.shape == reference.shape
    diff = np.abs(decoded.astype(int) - reference.astype(int))
    assert diff.max() <= 1, f"像素差异过大（{diff.max()}），可能是色彩空间声明有误"


def test_embed_can_be_disabled(fundus_image, tmp_path):
    """显式关闭内嵌时回退为未压缩，PhotometricInterpretation 应为 RGB"""
    from pydicom.uid import ExplicitVRLittleEndian

    out = tmp_path / "raw.dcm"
    ds = build_op_dataset(
        image_path=fundus_image, patient_id="P1", case_no="T1",
        eye="OD", file_name=fundus_image.name, embed_jpeg=False,
    )
    assert ds.file_meta.TransferSyntaxUID == ExplicitVRLittleEndian
    assert ds.PhotometricInterpretation == "RGB"


def test_png_source_falls_back_to_uncompressed(tmp_path):
    """非 JPEG 源（如 mask 用的 PNG）无法内嵌，应回退且不报错"""
    from pydicom.uid import ExplicitVRLittleEndian

    png = tmp_path / "mask.png"
    Image.fromarray(np.zeros((16, 16, 3), dtype=np.uint8)).save(png)
    ds = build_op_dataset(
        image_path=png, patient_id="P1", case_no="T1",
        eye="OD", file_name=png.name,
    )
    assert ds.file_meta.TransferSyntaxUID == ExplicitVRLittleEndian
    assert ds.PhotometricInterpretation == "RGB"


def test_can_embed_jpeg_reports_reason(tmp_path):
    from app.common.dicom_convert import can_embed_jpeg

    png = tmp_path / "a.png"
    Image.fromarray(np.zeros((8, 8, 3), dtype=np.uint8)).save(png)
    ok, reason, w, h = can_embed_jpeg(png)
    assert ok is False
    assert "JPEG" in reason
    assert (w, h) == (8, 8)


def test_single_component_patient_name_gets_caret(fundus_image):
    """
    DICOM 的 PN 是「姓^名^…」结构。单段名必须加尾部脱字符消歧，
    否则下游会当作不完整姓名解析（highdicom 会直接告警）。
    """
    ds = _build(fundus_image, patient_name="T2026001")
    assert str(ds.PatientName) == "T2026001^"


def test_multi_component_name_is_untouched(fundus_image):
    ds = _build(fundus_image, patient_name="Zhang^San")
    assert str(ds.PatientName) == "Zhang^San"


def test_single_frame_iod_omits_number_of_frames(fundus_image):
    """VL Photographic 为单帧 IOD，NumberOfFrames 仅多帧时必需，不应出现"""
    ds = _build(fundus_image)
    assert "NumberOfFrames" not in ds


def test_vl_required_attributes_present(fundus_image):
    """VL Photographic IOD 的必需属性"""
    ds = _build(fundus_image)
    assert list(ds.ImageType) == ["ORIGINAL", "PRIMARY"]
    # Type 2：必须存在，可为空序列
    assert "AcquisitionContextSequence" in ds
