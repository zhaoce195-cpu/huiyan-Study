"""
操作日志服务
- record() 静态方法可在任意业务点调用：失败不抛异常，只静默忽略，避免影响主流程
"""

from datetime import datetime
from typing import List, Optional

from sqlalchemy import desc
from sqlalchemy.orm import Session

from app.db.models import OperationLog, User
from app.schemas.common import OperationLogOut, OperationLogPageOut


class OpLogService:

    @staticmethod
    def record(
        db: Session,
        *,
        user: Optional[User],
        module: str,
        action: str,
        detail: str = "",
        ip: str = "",
        commit: bool = True,
    ) -> Optional[OperationLog]:
        """
        通用日志写入。失败时静默吞掉异常，避免影响主业务。

        参数：
            user   : 当前登录用户（可为 None，比如未登录的 ping）
            module : 模块名 auth/screening/training/user/common
            action : 动作 login/upload/delete/refer ...
            detail : 描述性文字（建议 ≤ 200 字）
            ip     : 客户端 IP
            commit : 是否立即 commit；若调用方已处于事务，传 False
        """
        try:
            row = OperationLog(
                user_id=user.id if user else None,
                username=(user.username if user else "") or "",
                module=module[:32],
                action=action[:64],
                detail=detail or "",
                ip=ip[:64] if ip else "",
            )
            db.add(row)
            if commit:
                db.commit()
                db.refresh(row)
            return row
        except Exception:
            try:
                db.rollback()
            except Exception:
                pass
            return None

    @staticmethod
    def list(
        db: Session,
        module: Optional[str] = None,
        start_time: Optional[str] = None,
        end_time: Optional[str] = None,
        page: int = 1,
        page_size: int = 20,
    ) -> OperationLogPageOut:
        q = db.query(OperationLog)
        if module:
            q = q.filter(OperationLog.module == module)
        if start_time:
            try:
                q = q.filter(OperationLog.created_at >= datetime.fromisoformat(start_time.replace(" ", "T")))
            except ValueError:
                pass
        if end_time:
            try:
                q = q.filter(OperationLog.created_at <= datetime.fromisoformat(end_time.replace(" ", "T")))
            except ValueError:
                pass

        total = q.count()
        rows: List[OperationLog] = (
            q.order_by(desc(OperationLog.id))
            .offset(max(0, (page - 1) * page_size))
            .limit(page_size)
            .all()
        )

        return OperationLogPageOut(
            total=total,
            list=[
                OperationLogOut(
                    id=r.id,
                    user_id=r.user_id,
                    username=r.username,
                    module=r.module,
                    action=r.action,
                    detail=r.detail,
                    ip=r.ip,
                    created_at=r.created_at.strftime("%Y-%m-%d %H:%M:%S") if r.created_at else "",
                )
                for r in rows
            ],
        )
