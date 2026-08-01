# -*- coding: utf-8 -*-
"""
DICOMweb 影像 / 分割拆分测试

对应《医学培训端评估与工作流重构报告》P1：
    「病例列表的『8 张/9 张影像』实际混合原图、mask、病灶层和金标准，
      医生无法确认是否完整阅完原始检查。」

拆分后「影像张数」只统计原始影像，分割标注单独计数。
本文件不依赖运行中的 PACS，用构造的元数据验证拆分与解析逻辑。
"""

from unittest.mock import patch

import pytest

from app.services import dicomweb_client as dw


def _tagged(value):
    return {"Value": [value]}


def _image_item(sop, laterality="R", instance_number=1, rows=2848, cols=4288):
    return {
        dw.TAG_SOP_UID: _tagged(sop),
        dw.TAG_SERIES_UID: _tagged("series-" + sop),
        dw.TAG_MODALITY: _tagged("OP"),
        dw.TAG_IMAGE_LATERALITY: _tagged(laterality),
        dw.TAG_ROWS: _tagged(rows),
        dw.TAG_COLUMNS: _tagged(cols),
        dw.TAG_INSTANCE_NUMBER: _tagged(instance_number),
    }


def _seg_item(sop, labels, frames=None):
    return {
        dw.TAG_SOP_UID: _tagged(sop),
        dw.TAG_SERIES_UID: _tagged("series-" + sop),
        dw.TAG_MODALITY: _tagged("SEG"),
        dw.TAG_NUMBER_OF_FRAMES: _tagged(frames if frames is not None else len(labels)),
        dw.TAG_SEGMENT_SEQUENCE: {
            "Value": [
                {dw.TAG_SEGMENT_NUMBER: _tagged(i + 1),
                 dw.TAG_SEGMENT_LABEL: _tagged(lbl)}
                for i, lbl in enumerate(labels)
            ]
        },
    }


@pytest.fixture
def fake_study():
    """一张原图 + 一个含 4 分段的 SEG，与真实 IDRiD 病例结构一致"""
    return [
        _seg_item("seg-1", ["微动脉瘤", "视网膜出血", "硬性渗出", "视盘"]),
        _image_item("img-1", laterality="R"),
    ]


def _with(meta):
    """注入元数据；拆分逻辑只依赖 _study_and_metadata 这一个入口"""
    return patch.object(dw, "_study_and_metadata",
                        return_value=("study-uid-test", meta))


# --------------------------------------------------------------------------
# 拆分
# --------------------------------------------------------------------------

def test_images_and_segmentations_are_separated(fake_study):
    with _with(fake_study):
        out = dw.split_instances("T1")
    assert len(out["images"]) == 1
    assert len(out["segmentations"]) == 1


def test_image_count_excludes_segmentations(fake_study):
    """
    这是报告 P1 的核心：影像张数绝不能把派生对象算进去，
    否则医生无法判断原始检查是否阅完。
    """
    with _with(fake_study):
        s = dw.study_summary("T1")
    assert s["imageCount"] == 1
    assert s["segmentationCount"] == 1
    assert s["segmentTotal"] == 4


def test_many_segmentations_do_not_inflate_image_count():
    meta = [_image_item("img-1")] + [
        _seg_item(f"seg-{i}", ["MA", "HE"]) for i in range(8)
    ]
    with _with(meta):
        s = dw.study_summary("T1")
    assert s["imageCount"] == 1, "8 个分割不应让影像张数变成 9"
    assert s["segmentationCount"] == 8


def test_segment_labels_are_exposed(fake_study):
    with _with(fake_study):
        out = dw.split_instances("T1")
    labels = [x["label"] for x in out["segmentations"][0]["segments"]]
    assert labels == ["微动脉瘤", "视网膜出血", "硬性渗出", "视盘"]
    numbers = [x["number"] for x in out["segmentations"][0]["segments"]]
    assert numbers == [1, 2, 3, 4]


def test_segmentation_frame_url_is_templated(fake_study):
    with _with(fake_study):
        out = dw.split_instances("T1")
    tmpl = out["segmentations"][0]["frameUrlTemplate"]
    assert "{frame}" in tmpl
    assert "seg-1" in tmpl


# --------------------------------------------------------------------------
# 眼别与汇总
# --------------------------------------------------------------------------

def test_laterality_mapped_to_platform_codes():
    with _with([_image_item("a", "R"), _image_item("b", "L", 2)]):
        out = dw.split_instances("T1")
    eyes = {i["eye"] for i in out["images"]}
    assert eyes == {"OD", "OS"}


def test_unknown_laterality_is_explicit():
    """未标注眼别时如实返回「眼别未知」，不猜成双眼"""
    item = _image_item("a")
    del item[dw.TAG_IMAGE_LATERALITY]
    with _with([item]):
        out = dw.split_instances("T1")
    assert out["images"][0]["eye"] == "UNKNOWN"
    assert out["images"][0]["eyeText"] == "眼别未知"


def test_summary_reports_unknown_exam_date():
    """检查时间未采集时必须显式标明，不能让界面以为有日期"""
    with _with([_image_item("a")]):
        s = dw.study_summary("T1")
    assert s["examDateKnown"] is False
    assert s["examDate"] is None


def test_empty_study_is_safe():
    with _with([]):
        s = dw.study_summary("T1")
    assert s["imageCount"] == 0
    assert s["segmentationCount"] == 0
    assert s["eyesText"] == "眼别未知"


def test_images_sorted_by_instance_number():
    with _with([_image_item("c", instance_number=3),
                _image_item("a", instance_number=1),
                _image_item("b", instance_number=2)]):
        out = dw.split_instances("T1")
    assert [i["instanceNumber"] for i in out["images"]] == [1, 2, 3]


def test_legacy_fields_kept_for_migration(fake_study):
    """
    前端尚未全量切换，保留旧字段名；
    但旧字段同样不得包含分割，否则等于没修。
    """
    with _with(fake_study):
        s = dw.study_summary("T1")
    assert s["instanceCount"] == s["imageCount"]
    assert all(i["modality"] != "SEG" for i in s["instances"])


# --------------------------------------------------------------------------
# WADO 透传的安全边界
# --------------------------------------------------------------------------

@pytest.mark.parametrize("bad", [
    "../../patients",
    "..%2f..%2fpatients",
    "studies/../../system",
    "/system",
    "patients",
    "system",
    "tools/reset",
])
def test_wado_passthrough_rejects_non_dicomweb_paths(bad):
    """
    后端用 ADMIN 权限的服务账号访问 PACS。若把用户路径原样拼进 URL，
    任何登录用户都能用 ../ 跳出 /dicom-web/ 抵达 Orthanc 管理接口
    （实测曾可读到 /patients 与 /system）。只放行 DICOMweb 资源路径。
    """
    from fastapi import HTTPException

    with pytest.raises(HTTPException) as exc:
        dw.proxy_wado(bad)
    assert exc.value.status_code == 400


@pytest.mark.parametrize("ok", [
    "studies",
    "studies/1.2.3/metadata",
    "studies/1.2.3/series/4.5.6/instances/7.8.9/frames/1",
])
def test_wado_passthrough_allows_dicomweb_paths(ok, monkeypatch):
    """正常 DICOMweb 路径不受影响"""
    captured = {}

    class FakeResp:
        status_code = 200
        content = b"x"
        headers = {"Content-Type": "application/dicom+json"}

    def fake_get(url, headers=None, timeout=None):
        captured["url"] = url
        return FakeResp()

    monkeypatch.setattr(dw.requests, "get", fake_get)
    monkeypatch.setattr(dw, "_headers", lambda a: {})
    body, ctype = dw.proxy_wado(ok)
    assert body == b"x"
    assert "/dicom-web/" + ok.split("?")[0] in captured["url"]
