# -*- coding: utf-8 -*-
"""
DICOMweb 客户端（Orthanc）

对应方案决策三「全量 DICOM 化」与报告 P0/P1：
    「影像与图层混算」「眼别/日期/模态不固定」
    → 影像统一经 DICOMweb 读取，层级与安全标识由 DICOM 标签直接提供，
      前端不再拼接静态文件路径（顺带解决切换病例时的浏览器缓存串图）。

一条必须遵守的约定
    取像时必须显式声明传输语法。Orthanc 默认会把内嵌的 JPEG 转码成未压缩
    再返回：实测同一张眼底照 0.28 MB 变 34.94 MB，相差 125 倍。
    本模块的所有取像请求都带 transfer-syntax，不给调用方漏写的机会。
"""

from typing import Any, Dict, List, Optional, Tuple

import requests
from fastapi import HTTPException, status

from app.common.image_safety import EYE_TEXT
from app.core.config import settings

# ---- 常用 DICOM 标签 ----
TAG_STUDY_UID = "0020000D"
TAG_SERIES_UID = "0020000E"
TAG_SOP_UID = "00080018"
TAG_PATIENT_ID = "00100020"
TAG_MODALITY = "00080060"
TAG_IMAGE_LATERALITY = "00200062"
TAG_LATERALITY = "00200060"
TAG_ROWS = "00280010"
TAG_COLUMNS = "00280011"
TAG_ACQ_DATETIME = "0008002A"
TAG_STUDY_DATE = "00080020"
TAG_INSTANCE_NUMBER = "00200013"

# DICOM 的 Image Laterality 只有 R/L；平台内部用 OD/OS/OU
_LATERALITY_TO_EYE = {"R": "OD", "L": "OS"}


# ---------------------------------------------------------------------------
# 访问 PACS 的凭据
# ---------------------------------------------------------------------------
# Orthanc 已改为纯 Authorization 插件鉴权（AuthenticationEnabled=false），
# 因此后端用 Keycloak 服务账号令牌访问，而不是静态口令。
_sa_token: Dict[str, Any] = {"value": "", "exp": 0.0}


def _service_account_token() -> str:
    """
    取后端自己的服务账号令牌（client_credentials）。

    带缓存并提前 30 秒过期，避免每次请求都打 Keycloak。
    """
    import time

    now = time.time()
    if _sa_token["value"] and now < _sa_token["exp"]:
        return _sa_token["value"]

    url = (
        f"{settings.KEYCLOAK_BASE_URL.rstrip('/')}"
        f"/realms/{settings.KEYCLOAK_REALM}/protocol/openid-connect/token"
    )
    try:
        r = requests.post(
            url,
            data={
                "grant_type": "client_credentials",
                "client_id": settings.KEYCLOAK_CLIENT_ID,
                "client_secret": settings.KEYCLOAK_CLIENT_SECRET,
            },
            timeout=15,
        )
        r.raise_for_status()
        data = r.json()
    except requests.RequestException as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"无法获取 PACS 访问令牌：{exc}",
        )

    _sa_token["value"] = data.get("access_token", "")
    _sa_token["exp"] = now + max(0, int(data.get("expires_in", 60)) - 30)
    return _sa_token["value"]


def _headers(accept: str) -> Dict[str, str]:
    return {
        "Accept": accept,
        "Authorization": f"Bearer {_service_account_token()}",
    }


def _url(path: str) -> str:
    return f"{settings.ORTHANC_BASE_URL.rstrip('/')}{path}"


def _first(item: Dict[str, Any], tag: str, default: Any = None) -> Any:
    """取 DICOMweb JSON 中某标签的首个值"""
    node = item.get(tag) or {}
    values = node.get("Value") or []
    return values[0] if values else default


def _get_json(path: str, params: Optional[dict] = None) -> Any:
    try:
        r = requests.get(
            _url(path), params=params,
            headers=_headers("application/json"),
            timeout=settings.ORTHANC_TIMEOUT_SEC,
        )
    except requests.RequestException as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"影像服务不可用：{exc}",
        )
    if r.status_code == 404:
        return None
    if r.status_code >= 400:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"影像服务返回 {r.status_code}",
        )
    return r.json()


# ---------------------------------------------------------------------------
# 查询
# ---------------------------------------------------------------------------

def is_available() -> bool:
    """探活；用于降级判断，失败不抛异常"""
    try:
        r = requests.get(_url("/system"),
                         headers=_headers("application/json"), timeout=8)
        return r.status_code == 200
    except HTTPException:
        return False
    except requests.RequestException:
        return False


def find_study_uid(case_no: str) -> Optional[str]:
    """
    按病例编号定位 Study。

    转换时把 case_no 写入了 PatientID，因此这里用 PatientID 精确匹配。
    """
    if not case_no:
        return None
    data = _get_json("/dicom-web/studies", params={"PatientID": case_no})
    if not data:
        return None
    return _first(data[0], TAG_STUDY_UID)


def list_instances(case_no: str) -> List[Dict[str, Any]]:
    """
    列出该病例的全部实例及安全标识。

    返回结构与 image_safety.build_image_meta 对齐，便于安全条直接消费。
    """
    study_uid = find_study_uid(case_no)
    if not study_uid:
        return []

    meta = _get_json(f"/dicom-web/studies/{study_uid}/metadata") or []
    out: List[Dict[str, Any]] = []

    for item in meta:
        lat = _first(item, TAG_IMAGE_LATERALITY) or _first(item, TAG_LATERALITY) or ""
        eye = _LATERALITY_TO_EYE.get(lat, "UNKNOWN")
        sop = _first(item, TAG_SOP_UID, "")
        out.append({
            "sopInstanceUid": sop,
            "seriesInstanceUid": _first(item, TAG_SERIES_UID, ""),
            "studyInstanceUid": study_uid,
            "eye": eye,
            # 未标注时如实返回「眼别未知」，不猜成双眼
            "eyeText": EYE_TEXT.get(eye, "眼别未知"),
            "modality": _first(item, TAG_MODALITY, ""),
            "rows": int(_first(item, TAG_ROWS, 0) or 0),
            "columns": int(_first(item, TAG_COLUMNS, 0) or 0),
            "acquisitionDateTime": _first(item, TAG_ACQ_DATETIME, "") or "",
            "instanceNumber": int(_first(item, TAG_INSTANCE_NUMBER, 0) or 0),
            # 供前端直接取像；带鉴权，由后端代理
            "frameUrl": f"/dicomweb/instances/{sop}/frame" if sop else "",
        })

    out.sort(key=lambda x: (x["instanceNumber"], x["sopInstanceUid"]))
    return out


TAG_SEGMENT_SEQUENCE = "00620002"
TAG_SEGMENT_NUMBER = "00620004"
TAG_SEGMENT_LABEL = "00620005"
TAG_NUMBER_OF_FRAMES = "00280008"

SEG_MODALITY = "SEG"


def _segments_of(item: Dict[str, Any]) -> List[Dict[str, Any]]:
    """从 SEG 实例元数据中提取分段清单"""
    seq = (item.get(TAG_SEGMENT_SEQUENCE) or {}).get("Value") or []
    out = []
    for seg in seq:
        out.append({
            "number": _first(seg, TAG_SEGMENT_NUMBER, 0),
            "label": _first(seg, TAG_SEGMENT_LABEL, ""),
        })
    return out


def split_instances(case_no: str) -> Dict[str, Any]:
    """
    把病例实例分成「原始影像」与「分割标注」两类。

    报告 P1 要求「医生无法确认是否完整阅完原始检查」得到解决：
    影像张数只统计 OP 实例，SEG 属于派生对象单独列出，两者不混算。
    """
    study_uid, all_items = _study_and_metadata(case_no)
    images: List[Dict[str, Any]] = []
    segmentations: List[Dict[str, Any]] = []

    for item in all_items:
        modality = _first(item, TAG_MODALITY, "")
        sop = _first(item, TAG_SOP_UID, "")
        if modality == SEG_MODALITY:
            segments = _segments_of(item)
            segmentations.append({
                "sopInstanceUid": sop,
                "seriesInstanceUid": _first(item, TAG_SERIES_UID, ""),
                "studyInstanceUid": study_uid,
                "modality": modality,
                "segments": segments,
                "segmentCount": len(segments),
                "frameCount": int(_first(item, TAG_NUMBER_OF_FRAMES, 0) or 0),
                # 分割数据体积远大于原图，前端应按需加载而不是随病例一起拉
                "frameUrlTemplate": f"/dicomweb/instances/{sop}/frames/{{frame}}"
                                    if sop else "",
            })
        else:
            lat = _first(item, TAG_IMAGE_LATERALITY) or _first(item, TAG_LATERALITY) or ""
            eye = _LATERALITY_TO_EYE.get(lat, "UNKNOWN")
            images.append({
                "sopInstanceUid": sop,
                "seriesInstanceUid": _first(item, TAG_SERIES_UID, ""),
                # wadors 需要完整的 study/series/instance 三级路径
                "studyInstanceUid": study_uid,
                "eye": eye,
                "eyeText": EYE_TEXT.get(eye, "眼别未知"),
                "modality": modality,
                "rows": int(_first(item, TAG_ROWS, 0) or 0),
                "columns": int(_first(item, TAG_COLUMNS, 0) or 0),
                "acquisitionDateTime": _first(item, TAG_ACQ_DATETIME, "") or "",
                "instanceNumber": int(_first(item, TAG_INSTANCE_NUMBER, 0) or 0),
                "frameUrl": f"/dicomweb/instances/{sop}/frame" if sop else "",
            })

    images.sort(key=lambda x: (x["instanceNumber"], x["sopInstanceUid"]))
    return {"images": images, "segmentations": segmentations}


def _study_and_metadata(case_no: str) -> Tuple[str, List[Dict[str, Any]]]:
    """
    取该病例的 Study UID 与全部实例元数据。

    收敛为单一入口：拆分逻辑只依赖这一个函数，
    便于测试注入，也避免调用方各自拼路径。
    """
    study_uid = find_study_uid(case_no)
    if not study_uid:
        return "", []
    return study_uid, (_get_json(f"/dicom-web/studies/{study_uid}/metadata") or [])


def study_summary(case_no: str) -> Dict[str, Any]:
    """
    病例级汇总。

    「影像张数」只统计原始影像（OP），分割标注单独计数——
    这正是报告 P1 要求的：让医生能确认是否完整阅完原始检查。
    """
    split = split_instances(case_no)
    images = split["images"]
    segs = split["segmentations"]

    eyes = sorted({i["eye"] for i in images if i["eye"] in EYE_TEXT})
    dates = {i["acquisitionDateTime"] for i in images if i["acquisitionDateTime"]}
    return {
        # 原始影像张数：不含任何派生对象
        "imageCount": len(images),
        "segmentationCount": len(segs),
        "segmentTotal": sum(s["segmentCount"] for s in segs),
        "eyes": eyes,
        "eyesText": "、".join(EYE_TEXT[e] for e in eyes) if eyes else "眼别未知",
        "examDateKnown": bool(dates),
        "examDate": sorted(dates)[0] if dates else None,
        "images": images,
        "segmentations": segs,
        # 兼容旧字段名，前端切换完成后可移除
        "instanceCount": len(images),
        "instances": images,
    }


# ---------------------------------------------------------------------------
# 取像
# ---------------------------------------------------------------------------

def fetch_frame(sop_instance_uid: str) -> Tuple[bytes, str]:
    """
    取回单帧像素。

    必须带 transfer-syntax：不带的话 Orthanc 会转码成未压缩，
    单张眼底照从 0.28 MB 膨胀到 34.94 MB。

    :return: (二进制内容, Content-Type)
    """
    if not sop_instance_uid:
        raise HTTPException(status_code=400, detail="缺少 SOP Instance UID")

    # 先按 SOP UID 定位所属 study / series
    found = _get_json("/dicom-web/instances",
                      params={"SOPInstanceUID": sop_instance_uid})
    if not found:
        raise HTTPException(status_code=404, detail="影像不存在")

    item = found[0]
    study_uid = _first(item, TAG_STUDY_UID)
    series_uid = _first(item, TAG_SERIES_UID)

    ts = settings.ORTHANC_TRANSFER_SYNTAX
    accept = f'multipart/related; type="image/jpeg"; transfer-syntax={ts}'
    url = _url(
        f"/dicom-web/studies/{study_uid}/series/{series_uid}"
        f"/instances/{sop_instance_uid}/frames/1"
    )

    try:
        r = requests.get(url, headers=_headers(accept),
                         timeout=settings.ORTHANC_TIMEOUT_SEC)
    except requests.RequestException as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"影像服务不可用：{exc}",
        )
    if r.status_code >= 400:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"取像失败：HTTP {r.status_code}",
        )

    payload = extract_multipart_part(r.content)
    return payload, "image/jpeg"


def render_segment_mask(
    sop_instance_uid: str,
    segment_number: int,
    *,
    color: str = "255,64,64",
    opacity: float = 0.55,
) -> Tuple[bytes, str]:
    """
    把 SEG 中某个分段渲染成带透明通道的 PNG。

    取回整份 SEG 实例后按分段抽取对应帧——SEG 是多帧多分段结构，
    帧与分段的对应关系记在 PerFrameFunctionalGroups 里，不能想当然按序号取。
    """
    import io as _io

    import numpy as np
    import pydicom
    from PIL import Image

    found = _get_json("/dicom-web/instances",
                      params={"SOPInstanceUID": sop_instance_uid})
    if not found:
        raise HTTPException(status_code=404, detail="分割实例不存在")

    item = found[0]
    study_uid = _first(item, TAG_STUDY_UID)
    series_uid = _first(item, TAG_SERIES_UID)

    raw, _ = proxy_wado(
        f"studies/{study_uid}/series/{series_uid}/instances/{sop_instance_uid}",
        accept='multipart/related; type="application/dicom"; transfer-syntax=*',
    )
    ds = pydicom.dcmread(_io.BytesIO(extract_multipart_part(raw)))

    arr = ds.pixel_array
    if arr.ndim == 2:
        arr = arr[np.newaxis, ...]

    # 找出属于该分段的帧：以 SegmentIdentificationSequence 为准
    frame_idx = None
    per_frame = getattr(ds, "PerFrameFunctionalGroupsSequence", None)
    if per_frame:
        for i, fg in enumerate(per_frame):
            seg_id = getattr(fg, "SegmentIdentificationSequence", None)
            if seg_id and int(seg_id[0].ReferencedSegmentNumber) == segment_number:
                frame_idx = i
                break
    if frame_idx is None:
        # 退化情形：单帧或缺少功能组时按顺序对应
        frame_idx = segment_number - 1

    if frame_idx < 0 or frame_idx >= arr.shape[0]:
        raise HTTPException(status_code=404, detail=f"分段 {segment_number} 不存在")

    mask = (arr[frame_idx] > 0)

    try:
        rgb = tuple(int(x) for x in color.split(","))[:3]
        if len(rgb) != 3:
            raise ValueError
    except Exception:
        rgb = (255, 64, 64)
    alpha = max(0, min(255, int(opacity * 255)))

    h, w = mask.shape
    rgba = np.zeros((h, w, 4), dtype=np.uint8)
    rgba[mask, 0] = rgb[0]
    rgba[mask, 1] = rgb[1]
    rgba[mask, 2] = rgb[2]
    rgba[mask, 3] = alpha

    buf = _io.BytesIO()
    # 稀疏掩码 PNG 压缩率极高，通常只有原始分段帧的几十分之一
    Image.fromarray(rgba, mode="RGBA").save(buf, format="PNG", optimize=True)
    return buf.getvalue(), "image/png"


def proxy_wado(path: str, accept: Optional[str] = None) -> Tuple[bytes, str]:
    """
    WADO-RS 透传：把 /dicom-web/<path> 原样转发给 Orthanc。

    供 Cornerstone3D 等标准阅片器直接使用，同时保证：
      1. PACS 不对浏览器暴露，凭据只留在服务端；
      2. 取帧时强制带 transfer-syntax——漏写会让单张眼底照
         从 0.28 MB 膨胀到 34.94 MB，这个约定不能交给前端保证。
    """
    # ---- 路径校验（安全边界）----
    # 后端用 ADMIN 权限的服务账号访问 PACS，若把用户给的路径原样拼进 URL，
    # 任何登录用户都能用 ../ 跳出 /dicom-web/ 抵达 Orthanc 的管理接口
    # （实测可读到 /patients、/system）。因此只放行 DICOMweb 的只读资源路径。
    raw_path = (path or "").split("?", 1)[0]
    if ".." in raw_path or "%2e%2e" in raw_path.lower() or raw_path.startswith("/"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="非法的影像路径",
        )
    allowed_roots = ("studies", "series", "instances")
    if raw_path.split("/", 1)[0] not in allowed_roots:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="仅允许访问 DICOMweb 资源路径",
        )

    is_frames = "/frames/" in path
    if is_frames:
        # transfer-syntax=* 表示「按原样返回，不要转码」。
        #
        # 不能写死成 JPEG Baseline：原图是 JPEG 内嵌，但 SEG 是未压缩存储，
        # 对 SEG 请求 JPEG 会直接失败（实测 502）。用 * 同时满足两者——
        # 原图保持 0.28 MB，SEG 保持原始编码。
        # 关键是必须显式声明；不写的话 Orthanc 会把 JPEG 转码成未压缩，
        # 单张眼底照从 0.28 MB 膨胀到 34.94 MB。
        use_accept = 'multipart/related; type="application/octet-stream"; transfer-syntax=*'
    elif accept:
        use_accept = accept
    else:
        use_accept = "application/dicom+json"

    try:
        r = requests.get(
            _url(f"/dicom-web/{path.lstrip('/')}"),
            headers=_headers(use_accept),
            timeout=settings.ORTHANC_TIMEOUT_SEC,
        )
    except requests.RequestException as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"影像服务不可用：{exc}",
        )
    if r.status_code >= 400:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"影像服务返回 {r.status_code}",
        )
    return r.content, r.headers.get("Content-Type", "application/octet-stream")


def extract_multipart_part(body: bytes) -> bytes:
    """
    从 multipart/related 响应体中取出第一段的负载。

    DICOMweb 的取像响应恒为 multipart，直接把整段交给浏览器会显示不出来。
    """
    marker = b"\r\n\r\n"
    start = body.find(marker)
    if start < 0:
        return body
    payload = body[start + len(marker):]
    # 去掉结尾的 boundary
    tail = payload.rfind(b"\r\n--")
    return payload[:tail] if tail > 0 else payload
