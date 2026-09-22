# -*- coding: utf-8 -*-
"""
影像质量门控服务

对应《医学培训端评估与工作流重构报告》：
    P0/P1「缺图像质量入口：低质量图可能被当正常或被强制作答」
    「先质量后诊断：图像未加载、眼别冲突或质量不可判读时，不能默认为正常」

实现要点：
    1. 直接复用 CSU-EYES 已上线的 ConvNeXt 图像质量三分类模型，不训练新模型；
    2. 算法服务不可用时降级为「未评估」并记录原因，绝不伪造合格结论
       （报告风险表：算法服务单点，质量门控失败应降级而非阻断）；
    3. 结果作为派生对象存入 biz_case_image_quality，与原始影像记录解耦。
"""

from datetime import datetime
from typing import Dict, List, Optional

from sqlalchemy.orm import Session

from app.common.image_safety import UNKNOWN_QUALITY, is_ungradable
from app.db.models.case_image import CaseImage
from app.db.models.case_image_quality import CaseImageQuality

# 上游返回的英文类别 → 平台内部质量编码
_UPSTREAM_QUALITY_MAP = {
    "good": "good",
    "usable": "usable",
    "poor": "poor",
    "ungradable": "ungradable",
    # 上游可能返回中文类别名
    "好": "good",
    "可用": "usable",
    "差": "poor",
}


def normalize_quality(raw: Optional[str]) -> str:
    """把上游类别名归一化为平台质量编码；无法识别时返回 unknown（不猜）"""
    if not raw:
        return UNKNOWN_QUALITY
    key = str(raw).strip().lower()
    return _UPSTREAM_QUALITY_MAP.get(key, _UPSTREAM_QUALITY_MAP.get(str(raw).strip(), UNKNOWN_QUALITY))


def parse_upstream(payload: dict) -> dict:
    """
    解析 CSU-EYES /inference/image-quality 的返回。

    只提取需要的字段，且对缺字段保持容错——上游变更不应让整个门控崩掉，
    而应退化为「未评估」。
    """
    result = (payload or {}).get("result") or {}
    probs = result.get("probabilities") or {}

    # 线上 CSU-EYES 实际返回 quality_level_en / quality_name，
    # 不是文档里的 prediction_en / prediction_name。两种都认，
    # 否则调用成功也会被记成 unknown，界面上就是「评估完成，共 0 张 / 未评估」。
    quality = normalize_quality(
        result.get("prediction_en")
        or result.get("quality_level_en")
        or result.get("prediction_name")
        or result.get("quality_name")
    )

    confidence = 0.0
    if isinstance(probs, dict) and probs:
        try:
            confidence = float(max(probs.values()))
        except (TypeError, ValueError):
            confidence = 0.0

    model = (payload or {}).get("model") or {}
    return {
        "quality": quality,
        "confidence": round(confidence, 4),
        "probabilities": probs if isinstance(probs, dict) else {},
        "model_name": str(model.get("name") or "")[:64],
    }


class ImageQualityService:
    # ---------- 读取 ----------

    @staticmethod
    def quality_map(db: Session, image_ids: List[int]) -> Dict[int, CaseImageQuality]:
        """批量取影像质量结果，避免 N+1"""
        if not image_ids:
            return {}
        rows = (
            db.query(CaseImageQuality)
            .filter(CaseImageQuality.case_image_id.in_(image_ids))
            .all()
        )
        return {r.case_image_id: r for r in rows}

    @staticmethod
    def graded_original_count(db: Session) -> int:
        """
        已成功评出质量等级的原始影像张数（按影像去重）。

        单次评估只覆盖当前病例，病例又常常只有 1 张原图，
        界面若只报这一次的张数，连续评估多张不同影像时会一直显示 1 张。
        """
        rows = (
            db.query(CaseImageQuality.case_image_id)
            .join(CaseImage, CaseImage.id == CaseImageQuality.case_image_id)
            .filter(
                CaseImage.case_table == "training",
                CaseImage.role == "original",
                CaseImageQuality.quality != UNKNOWN_QUALITY,
                CaseImageQuality.error_msg == "",
            )
            .distinct()
            .all()
        )
        return len(rows)

    @staticmethod
    def case_has_ungradable(db: Session, case_id: int) -> bool:
        """
        该病例是否存在不可判读的原始影像。

        用于提交前校验：不可判读时不得给出默认阴性结论。
        """
        rows = (
            db.query(CaseImageQuality.quality)
            .join(CaseImage, CaseImage.id == CaseImageQuality.case_image_id)
            .filter(
                CaseImage.case_table == "training",
                CaseImage.case_id == case_id,
                CaseImage.role == "original",
            )
            .all()
        )
        return any(is_ungradable(r[0]) for r in rows)

    # ---------- 写入 ----------

    @staticmethod
    def save_result(
        db: Session,
        *,
        case_image_id: int,
        parsed: Optional[dict] = None,
        error_msg: str = "",
        duration_ms: int = 0,
    ) -> CaseImageQuality:
        """
        写入（或覆盖）一张影像的质量结果。

        评估失败时 parsed 为 None：质量记为 unknown 并保留失败原因，
        界面显示「未评估」——绝不因为调用失败就当作合格。
        """
        row = (
            db.query(CaseImageQuality)
            .filter(CaseImageQuality.case_image_id == case_image_id)
            .first()
        )
        if row is None:
            row = CaseImageQuality(case_image_id=case_image_id)
            db.add(row)

        if parsed:
            row.quality = parsed.get("quality", UNKNOWN_QUALITY)
            row.confidence = float(parsed.get("confidence") or 0.0)
            row.probabilities = parsed.get("probabilities") or {}
            row.model_name = parsed.get("model_name") or ""
            row.error_msg = ""
        else:
            row.quality = UNKNOWN_QUALITY
            row.confidence = 0.0
            row.probabilities = {}
            row.error_msg = (error_msg or "算法服务不可用")[:255]

        row.infer_duration_ms = int(duration_ms or 0)
        row.checked_at = datetime.now()
        db.commit()
        db.refresh(row)
        return row

    # ---------- 评估 ----------

    @staticmethod
    async def evaluate_case(db: Session, case_id: int) -> dict:
        """
        评估某病例全部原始影像的质量。

        算法服务异常时不抛出，逐张记录失败原因并继续，
        最终返回汇总供调用方展示。
        """
        import time
        from pathlib import Path

        from app.services import csu_eyes_client
        from app.services.training_ai_service import _resolve_static_file

        images = (
            db.query(CaseImage)
            .filter(
                CaseImage.case_table == "training",
                CaseImage.case_id == case_id,
                CaseImage.role == "original",
            )
            .order_by(CaseImage.sort_order, CaseImage.id)
            .all()
        )

        summary = {"total": len(images), "evaluated": 0, "failed": 0, "items": []}

        for img in images:
            local: Optional[Path] = _resolve_static_file(img.file_url or "")
            if local is None:
                ImageQualityService.save_result(
                    db, case_image_id=img.id, error_msg="影像文件不存在或路径不可达",
                )
                summary["failed"] += 1
                summary["items"].append(
                    {"imageId": img.id, "quality": UNKNOWN_QUALITY,
                     "error": "影像文件不存在或路径不可达"}
                )
                continue

            started = time.time()
            try:
                payload = await csu_eyes_client.assess_image_quality(image_path=local)
                parsed = parse_upstream(payload)
                cost = int((time.time() - started) * 1000)
                if parsed.get("quality") == UNKNOWN_QUALITY:
                    ImageQualityService.save_result(
                        db,
                        case_image_id=img.id,
                        error_msg="算法已返回，但没有可识别的质量等级",
                        duration_ms=cost,
                    )
                    summary["failed"] += 1
                    summary["items"].append(
                        {"imageId": img.id, "quality": UNKNOWN_QUALITY,
                         "error": "算法已返回，但没有可识别的质量等级"}
                    )
                    continue
                ImageQualityService.save_result(
                    db, case_image_id=img.id, parsed=parsed, duration_ms=cost,
                )
                summary["evaluated"] += 1
                summary["items"].append(
                    {"imageId": img.id, "quality": parsed["quality"],
                     "confidence": parsed["confidence"]}
                )
            except Exception as exc:  # 算法服务不可用 → 降级，不阻断
                cost = int((time.time() - started) * 1000)
                msg = getattr(exc, "detail", None) or str(exc)
                ImageQualityService.save_result(
                    db, case_image_id=img.id, error_msg=str(msg), duration_ms=cost,
                )
                summary["failed"] += 1
                summary["items"].append(
                    {"imageId": img.id, "quality": UNKNOWN_QUALITY, "error": str(msg)[:200]}
                )

        summary["hasUngradable"] = ImageQualityService.case_has_ungradable(db, case_id)
        summary["gradedTotal"] = ImageQualityService.graded_original_count(db)
        return summary
