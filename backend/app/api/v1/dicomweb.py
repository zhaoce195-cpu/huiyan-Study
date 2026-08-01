# -*- coding: utf-8 -*-
"""
DICOMweb 影像路由

对应方案决策三「全量 DICOM 化」：
    影像经 PACS 读取，层级与安全标识（眼别、模态、采集时间）由 DICOM 标签
    直接提供，前端不再拼接静态文件路径。

为什么由后端代理而不是让前端直连 Orthanc：
    1. Orthanc 不必对外暴露，凭据留在服务端；
    2. 鉴权与盲训内容策略统一在一处执行；
    3. 取像的 transfer-syntax 约定收敛在服务端，避免前端漏写导致
       单张影像从 0.28 MB 膨胀到 34.94 MB。
"""

from fastapi import APIRouter, Depends, Path, Request, Response

from app.common.response import success
from app.core.config import settings
from app.core.dependencies import CurrentUser, DbSession, require_roles
from app.db.models.user import RoleEnum
from app.services import dicomweb_client

router = APIRouter(
    prefix="/dicomweb",
    tags=["13. DICOM 影像"],
    dependencies=[Depends(require_roles(
        RoleEnum.STUDENT, RoleEnum.TEACHER, RoleEnum.ADMIN,
    ))],
)


@router.get("/status", summary="影像服务可用性", response_model=None)
def pacs_status(current_user: CurrentUser):
    """供前端决定走 DICOMweb 还是回退到旧的文件路径"""
    enabled = bool(settings.ORTHANC_ENABLED)
    return success(data={
        "enabled": enabled,
        "available": dicomweb_client.is_available() if enabled else False,
    })


@router.get(
    "/cases/{caseNo}/instances",
    summary="按病例编号列出 DICOM 实例（含眼别等安全标识）",
    response_model=None,
)
def list_case_instances(
    current_user: CurrentUser,
    db: DbSession,
    caseNo: str = Path(..., description="病例编号，如 T2026001"),
):
    data = dicomweb_client.study_summary(caseNo)
    return success(data=data)


@router.get(
    "/cases/{caseNo}/segmentations",
    summary="按病例列出病灶分割（SEG）及其分段清单",
    response_model=None,
)
def list_case_segmentations(
    current_user: CurrentUser,
    caseNo: str = Path(..., description="病例编号"),
):
    """
    单独列出分割标注。

    分割数据体积远大于原图（实测单个 SEG 约 5.8 MB，原图约 0.4 MB），
    因此与影像分开提供，由前端按需加载而不是随病例一次拉全。
    """
    data = dicomweb_client.split_instances(caseNo)
    return success(data={
        "segmentations": data["segmentations"],
        "count": len(data["segmentations"]),
    })


@router.get(
    "/segmentations/{sopUid}/segments/{segment}/mask.png",
    summary="把 SEG 的某个分段渲染为带透明通道的 PNG 掩码",
    response_model=None,
)
def segment_mask_png(
    current_user: CurrentUser,
    sopUid: str = Path(..., description="SEG 实例的 SOP Instance UID"),
    segment: int = Path(..., ge=1, description="分段编号，从 1 开始"),
    color: str = "255,64,64",
    opacity: float = 0.55,
):
    """
    服务端渲染分段掩码。

    为什么不用 Cornerstone3D 的 SEG 适配器：
        该适配器按断层类影像设计，要求 SEG 携带患者坐标系方位
        （ImageOrientationPatient）。眼底照是二维摄影，本就没有这一概念，
        要让适配器工作只能往 DICOM 里写入伪造的空间信息——不可接受。

    改为服务端解出比特打包的分段位图、渲染成带透明通道的 PNG：
        · 前端按普通图层叠加即可，不依赖任何三维几何假设；
        · 传输量也更小（原始分段帧 1.46 MB，稀疏掩码 PNG 通常几十 KB）。
    """
    payload, content_type = dicomweb_client.render_segment_mask(
        sopUid, segment, color=color, opacity=opacity,
    )
    return Response(
        content=payload,
        media_type=content_type,
        headers={"Cache-Control": "private, max-age=300"},
    )


@router.get(
    "/wado/{path:path}",
    summary="WADO-RS 透传（供 Cornerstone3D 等标准阅片器直接使用）",
    response_model=None,
)
def wado_passthrough(
    request: Request,
    current_user: CurrentUser,
    path: str = Path(..., description="Orthanc /dicom-web 之后的路径"),
):
    """
    把 DICOMweb 请求转发给 PACS。

    走后端而不是让浏览器直连 Orthanc，是为了：
      1. PACS 不对外暴露，凭据只留服务端；
      2. 鉴权统一由平台承担；
      3. 取帧的 transfer-syntax 由服务端强制，前端漏写不会导致
         单张影像膨胀到 34.94 MB。
    """
    qs = request.url.query
    full = f"{path}?{qs}" if qs else path
    payload, content_type = dicomweb_client.proxy_wado(
        full, accept=request.headers.get("Accept"),
    )
    return Response(
        content=payload,
        media_type=content_type,
        headers={"Cache-Control": "private, max-age=300"},
    )


@router.get(
    "/instances/{sopUid}/frame",
    summary="取回单帧影像像素",
    response_model=None,
)
def get_frame(
    current_user: CurrentUser,
    sopUid: str = Path(..., description="SOP Instance UID"),
):
    """
    代理取像。

    Cache-Control 用 private：影像按登录用户鉴权，不能进共享缓存；
    但同一用户重复查看同一张图可走浏览器缓存。
    """
    payload, content_type = dicomweb_client.fetch_frame(sopUid)
    return Response(
        content=payload,
        media_type=content_type,
        headers={"Cache-Control": "private, max-age=300"},
    )
