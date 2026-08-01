# -*- coding: utf-8 -*-
"""
业务影像记录 ↔ PACS 中 DICOM 实例的对应关系

阅片端换成 Cornerstone3D 之后要能直接读 PACS 里的 DICOM，
就得知道「界面上这张图，对应 PACS 里哪个实例」。

不按顺序猜配。转换时用的是确定性 UID，可由同样的输入精确重算；
算出来的 UID 再拿去和 PACS 实际存在的实例核对：
    对得上   → 用 DICOM
    对不上   → 退回原来的 JPG
这样即便当初是在另一台机器上转换的（UID 里含本地文件路径），
表现也只是「这个病例暂时不走 DICOM」，而不是把 A 的图配到 B 的标注上。
"""

from pathlib import Path
from typing import Dict, Iterable, Optional

from app.common.dicom_convert import deterministic_uid
from app.core.config import settings


def resolve_local_file(file_url: str) -> Path:
    """把 /static/... URL 还原为磁盘路径。必须与转换脚本完全一致"""
    raw = (file_url or "").split("?", 1)[0]
    prefix = settings.STATIC_URL.rstrip("/") + "/"
    rel = raw[len(prefix):] if raw.startswith(prefix) else raw.lstrip("/")
    base = Path(__file__).resolve().parent.parent.parent / settings.UPLOAD_DIR
    return (base / rel).resolve()


def expected_uids(case_no: str, file_url: str, eye: Optional[str]) -> Dict[str, str]:
    """
    重算某张影像在转换时得到的三个 UID。

    输入必须与 convert_cases_to_dicom.py 调用 convert_image_to_dicom 时一致：
    patient_id 传的就是 case_no，sop 的第三段是解析后的本地文件绝对路径。
    """
    local = resolve_local_file(file_url)
    return {
        "studyInstanceUid": deterministic_uid("study", case_no, case_no),
        "seriesInstanceUid": deterministic_uid("series", case_no, case_no, eye or "NA"),
        "sopInstanceUid": deterministic_uid("sop", case_no, case_no, str(local)),
    }


def uids_of(record, case_no: str) -> Dict[str, str]:
    """
    取一条影像记录对应的 UID。

    优先用落库值：它记录的是转换当时的事实。
    没有落库才回退到重算 —— 重算依赖本地文件路径，
    目录搬迁或换机器后就对不上了（见遗留清单 D-007）。
    """
    sop = getattr(record, "sop_instance_uid", None)
    if sop:
        return {
            "studyInstanceUid": getattr(record, "study_instance_uid", "") or "",
            "seriesInstanceUid": getattr(record, "series_instance_uid", "") or "",
            "sopInstanceUid": sop,
        }
    return expected_uids(case_no, getattr(record, "file_url", "") or "",
                         getattr(record, "eye", None))


def match_instances(
    case_no: str,
    records: Iterable,
    pacs_sop_uids: Iterable[str],
) -> Dict[str, Dict[str, str]]:
    """
    :param records: CaseImage 记录（只应传原图）
    :param pacs_sop_uids: PACS 中该病例实际存在的 SOP Instance UID
    :return: {影像 URL: {studyInstanceUid, seriesInstanceUid, sopInstanceUid}}
             只包含在 PACS 中确实找得到的那些
    """
    present = set(pacs_sop_uids or ())
    out: Dict[str, Dict[str, str]] = {}
    for r in records:
        url = getattr(r, "file_url", "") or ""
        if not url:
            continue
        uids = uids_of(r, case_no)
        # 落库了也要核对：PACS 里被删过、或从未推送成功的，
        # 光有 UID 不代表取得到像素
        if uids["sopInstanceUid"] and uids["sopInstanceUid"] in present:
            out[url] = uids
    return out
