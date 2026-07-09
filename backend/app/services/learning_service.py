"""
学习资料 / 收藏 / 笔记 服务层
- 角色矩阵：
  STUDENT  仅可查看公共资料、管理个人收藏与笔记
  TEACHER  可上传、维护公共学习资料；可查看自己的收藏与笔记
  ADMIN    全量数据管理权限（可删除任意笔记、维护任意资料）
"""

from typing import List, Optional

from fastapi import HTTPException
from sqlalchemy import desc, or_
from sqlalchemy.orm import Session

from app.db.models import (
    LearningNote,
    LearningResource,
    ResourceFavorite,
    ResourceStatusEnum,
    RoleEnum,
    TrainingCase,
    User,
)
from app.schemas.learning import (
    FavoriteListQuery,
    FavoriteParams,
    NoteCreateParams,
    NoteListQuery,
    NoteOut,
    NotePage,
    NoteUpdateParams,
    ResourceCreateParams,
    ResourceListQuery,
    ResourceOut,
    ResourcePage,
    ResourceUpdateParams,
)


_TYPE_TEXT = {
    "CASE_TEMPLATE": "病例范本",
    "COURSEWARE": "实训课件",
    "KNOWLEDGE": "知识点文档",
    "IMAGE_DEMO": "教学影像",
}


# ====================== 工具 ======================

def _role_code(user: User) -> str:
    return user.role.code if user.role else ""


def _is_teacher(user: User) -> bool:
    return _role_code(user) in (RoleEnum.TEACHER.value, RoleEnum.ADMIN.value)


def _is_admin(user: User) -> bool:
    return _role_code(user) == RoleEnum.ADMIN.value


def _resource_to_out(
    r: LearningResource,
    favorite_label_map: Optional[dict] = None,
) -> ResourceOut:
    publisher_name = ""
    if r.publisher:
        publisher_name = r.publisher.real_name or r.publisher.username or ""
    fav_map = favorite_label_map or {}
    is_fav = r.id in fav_map
    return ResourceOut(
        id=r.id,
        title=r.title,
        summary=r.summary or "",
        content=r.content or "",
        resource_type=r.resource_type,  # type: ignore[arg-type]
        resource_type_text=_TYPE_TEXT.get(r.resource_type, r.resource_type),
        tags=r.tags or "",
        cover_url=r.cover_url or "",
        file_url=r.file_url or "",
        file_type=r.file_type or "",
        case_id=r.case_id,
        status=r.status,  # type: ignore[arg-type]
        publisher_id=r.publisher_id,
        publisher_name=publisher_name,
        view_count=r.view_count or 0,
        favorite_count=r.favorite_count or 0,
        is_favorited=is_fav,
        favorite_label=fav_map.get(r.id, ""),
        created_at=r.created_at,
        updated_at=r.updated_at,
    )


def _note_to_out(n: LearningNote) -> NoteOut:
    user_name = ""
    if n.user:
        user_name = n.user.real_name or n.user.username or ""
    case_no = ""
    case_title = ""
    if n.case:
        case_no = n.case.case_no or ""
        case_title = n.case.title or ""
    res_title = ""
    if n.resource:
        res_title = n.resource.title or ""
    return NoteOut(
        id=n.id,
        user_id=n.user_id,
        user_name=user_name,
        title=n.title or "",
        content=n.content or "",
        tags=n.tags or "",
        case_id=n.case_id,
        case_no=case_no,
        case_title=case_title,
        image_index=n.image_index if n.image_index is not None else -1,
        image_url=n.image_url or "",
        resource_id=n.resource_id,
        resource_title=res_title,
        created_at=n.created_at,
        updated_at=n.updated_at,
    )


def _favorite_label_map(db: Session, user_id: int, resource_ids: List[int]) -> dict:
    """返回 {resource_id: label}，用于批量标记 is_favorited"""
    if not resource_ids:
        return {}
    favs = (
        db.query(ResourceFavorite)
        .filter(
            ResourceFavorite.user_id == user_id,
            ResourceFavorite.resource_id.in_(resource_ids),
        )
        .all()
    )
    return {f.resource_id: (f.label or "") for f in favs}


# ====================== Service ======================

class LearningService:

    # ---------- 学习资料 ----------

    @staticmethod
    def list_resources(
        db: Session, user: User, query: ResourceListQuery,
    ) -> ResourcePage:
        q = db.query(LearningResource)

        is_teacher = _is_teacher(user)

        # 学员只能看 PUBLISHED；教师/管理员可按 status 自筛
        if not is_teacher:
            q = q.filter(
                LearningResource.status == ResourceStatusEnum.PUBLISHED.value
            )
            # 学员可见性二级过滤：当资料关联了病例时，只展示已加入实训的病例对应资料
            # 没有关联病例的资料（如通用知识点/课件）不受影响
            q = q.outerjoin(
                TrainingCase, TrainingCase.id == LearningResource.case_id,
            ).filter(
                or_(
                    LearningResource.case_id.is_(None),
                    TrainingCase.is_train_case == True,  # noqa: E712
                )
            )
        else:
            if query.status:
                q = q.filter(LearningResource.status == query.status)
            if query.only_mine:
                q = q.filter(LearningResource.publisher_id == user.id)

        if query.keyword:
            kw = f"%{query.keyword.strip()}%"
            q = q.filter(
                or_(
                    LearningResource.title.like(kw),
                    LearningResource.summary.like(kw),
                    LearningResource.tags.like(kw),
                )
            )
        if query.resource_type:
            q = q.filter(LearningResource.resource_type == query.resource_type)

        total = q.count()
        page = max(1, query.page)
        size = max(1, min(200, query.page_size))
        rows: List[LearningResource] = (
            q.order_by(desc(LearningResource.id))
            .offset((page - 1) * size)
            .limit(size)
            .all()
        )

        fav_map = _favorite_label_map(db, user.id, [r.id for r in rows])

        return ResourcePage(
            total=total,
            page=page,
            page_size=size,
            list=[_resource_to_out(r, fav_map) for r in rows],
        )

    @staticmethod
    def get_resource(db: Session, user: User, resource_id: int) -> ResourceOut:
        r = (
            db.query(LearningResource)
            .filter(LearningResource.id == resource_id)
            .first()
        )
        if not r:
            raise HTTPException(404, detail=f"资料不存在：{resource_id}")
        if (
            r.status != ResourceStatusEnum.PUBLISHED.value
            and not _is_teacher(user)
            and r.publisher_id != user.id
        ):
            raise HTTPException(403, detail="该资料未发布，无权查看")

        # 学员：若资料关联了病例，则该病例必须已加入实训
        if not _is_teacher(user) and r.case_id is not None:
            case = (
                db.query(TrainingCase)
                .filter(TrainingCase.id == r.case_id)
                .first()
            )
            if not case or not bool(getattr(case, "is_train_case", False)):
                raise HTTPException(
                    403,
                    detail="该资料关联病例尚未加入实训，暂不可查看",
                )

        # 阅读量 +1
        r.view_count = (r.view_count or 0) + 1
        db.commit()
        db.refresh(r)
        fav_map = _favorite_label_map(db, user.id, [r.id])
        return _resource_to_out(r, fav_map)

    @staticmethod
    def create_resource(
        db: Session, user: User, params: ResourceCreateParams,
    ) -> ResourceOut:
        if not _is_teacher(user):
            raise HTTPException(403, detail="仅教师/管理员可上传学习资料")
        r = LearningResource(
            title=params.title,
            summary=params.summary or "",
            content=params.content or "",
            resource_type=params.resource_type,
            tags=params.tags or "",
            cover_url=params.cover_url or "",
            file_url=params.file_url or "",
            file_type=params.file_type or "",
            case_id=params.case_id,
            status=params.status,
            publisher_id=user.id,
        )
        db.add(r)
        db.commit()
        db.refresh(r)
        return _resource_to_out(r)

    @staticmethod
    def update_resource(
        db: Session, user: User, resource_id: int, params: ResourceUpdateParams,
    ) -> ResourceOut:
        r = (
            db.query(LearningResource)
            .filter(LearningResource.id == resource_id)
            .first()
        )
        if not r:
            raise HTTPException(404, detail=f"资料不存在：{resource_id}")
        if not _is_admin(user) and r.publisher_id != user.id:
            raise HTTPException(403, detail="仅可编辑自己上传的资料")
        if not _is_teacher(user):
            raise HTTPException(403, detail="无编辑权限")

        for field in (
            "title", "summary", "content", "resource_type", "tags",
            "cover_url", "file_url", "file_type", "case_id", "status",
        ):
            val = getattr(params, field)
            if val is not None:
                setattr(r, field, val)
        db.commit()
        db.refresh(r)
        return _resource_to_out(r)

    @staticmethod
    def delete_resource(db: Session, user: User, resource_id: int) -> None:
        r = (
            db.query(LearningResource)
            .filter(LearningResource.id == resource_id)
            .first()
        )
        if not r:
            raise HTTPException(404, detail=f"资料不存在：{resource_id}")
        if not _is_admin(user) and r.publisher_id != user.id:
            raise HTTPException(403, detail="仅可删除自己上传的资料")
        db.delete(r)
        db.commit()

    # ---------- 收藏 ----------

    @staticmethod
    def add_favorite(
        db: Session, user: User, params: FavoriteParams,
    ) -> ResourceOut:
        r = (
            db.query(LearningResource)
            .filter(LearningResource.id == params.resource_id)
            .first()
        )
        if not r:
            raise HTTPException(404, detail=f"资料不存在：{params.resource_id}")
        if r.status != ResourceStatusEnum.PUBLISHED.value:
            raise HTTPException(400, detail="资料未发布，无法收藏")

        existing = (
            db.query(ResourceFavorite)
            .filter(
                ResourceFavorite.user_id == user.id,
                ResourceFavorite.resource_id == params.resource_id,
            )
            .first()
        )
        if existing:
            existing.label = params.label or existing.label
        else:
            db.add(ResourceFavorite(
                user_id=user.id,
                resource_id=params.resource_id,
                label=params.label or "",
            ))
            r.favorite_count = (r.favorite_count or 0) + 1

        db.commit()
        db.refresh(r)
        fav_map = _favorite_label_map(db, user.id, [r.id])
        return _resource_to_out(r, fav_map)

    @staticmethod
    def remove_favorite(db: Session, user: User, resource_id: int) -> None:
        existing = (
            db.query(ResourceFavorite)
            .filter(
                ResourceFavorite.user_id == user.id,
                ResourceFavorite.resource_id == resource_id,
            )
            .first()
        )
        if not existing:
            return
        db.delete(existing)
        r = (
            db.query(LearningResource)
            .filter(LearningResource.id == resource_id)
            .first()
        )
        if r and (r.favorite_count or 0) > 0:
            r.favorite_count = r.favorite_count - 1
        db.commit()

    @staticmethod
    def list_favorites(
        db: Session, user: User, query: FavoriteListQuery,
    ) -> ResourcePage:
        q = (
            db.query(ResourceFavorite, LearningResource)
            .join(
                LearningResource,
                LearningResource.id == ResourceFavorite.resource_id,
            )
            .filter(ResourceFavorite.user_id == user.id)
        )

        if query.keyword:
            kw = f"%{query.keyword.strip()}%"
            q = q.filter(
                or_(
                    LearningResource.title.like(kw),
                    LearningResource.summary.like(kw),
                    LearningResource.tags.like(kw),
                )
            )
        if query.resource_type:
            q = q.filter(LearningResource.resource_type == query.resource_type)
        if query.label:
            q = q.filter(ResourceFavorite.label == query.label)

        total = q.count()
        page = max(1, query.page)
        size = max(1, min(200, query.page_size))
        rows = (
            q.order_by(desc(ResourceFavorite.created_at))
            .offset((page - 1) * size)
            .limit(size)
            .all()
        )

        out_list: List[ResourceOut] = []
        for fav, res in rows:
            ro = _resource_to_out(res, {res.id: fav.label or ""})
            out_list.append(ro)

        return ResourcePage(
            total=total, page=page, page_size=size, list=out_list,
        )

    # ---------- 笔记 ----------

    @staticmethod
    def create_note(
        db: Session, user: User, params: NoteCreateParams,
    ) -> NoteOut:
        if not (params.title or params.content):
            raise HTTPException(400, detail="标题与正文不能同时为空")
        # 校验关联资源
        if params.case_id:
            exists = db.query(TrainingCase.id).filter(
                TrainingCase.id == params.case_id
            ).first()
            if not exists:
                raise HTTPException(400, detail=f"病例不存在：{params.case_id}")
        if params.resource_id:
            exists = db.query(LearningResource.id).filter(
                LearningResource.id == params.resource_id
            ).first()
            if not exists:
                raise HTTPException(400, detail=f"资料不存在：{params.resource_id}")

        n = LearningNote(
            user_id=user.id,
            title=params.title or "",
            content=params.content or "",
            tags=params.tags or "",
            case_id=params.case_id,
            image_index=(
                params.image_index
                if params.image_index is not None and params.image_index >= 0
                else -1
            ),
            image_url=params.image_url or "",
            resource_id=params.resource_id,
        )
        db.add(n)
        db.commit()
        db.refresh(n)
        return _note_to_out(n)

    @staticmethod
    def update_note(
        db: Session, user: User, note_id: int, params: NoteUpdateParams,
    ) -> NoteOut:
        n = (
            db.query(LearningNote)
            .filter(LearningNote.id == note_id)
            .first()
        )
        if not n:
            raise HTTPException(404, detail=f"笔记不存在：{note_id}")
        if n.user_id != user.id and not _is_admin(user):
            raise HTTPException(403, detail="仅本人可编辑该笔记")

        for field in (
            "title", "content", "tags", "case_id",
            "image_index", "image_url", "resource_id",
        ):
            val = getattr(params, field)
            if val is not None:
                setattr(n, field, val)
        db.commit()
        db.refresh(n)
        return _note_to_out(n)

    @staticmethod
    def delete_note(db: Session, user: User, note_id: int) -> None:
        n = (
            db.query(LearningNote)
            .filter(LearningNote.id == note_id)
            .first()
        )
        if not n:
            raise HTTPException(404, detail=f"笔记不存在：{note_id}")
        if n.user_id != user.id and not _is_admin(user):
            raise HTTPException(403, detail="仅本人或管理员可删除该笔记")
        db.delete(n)
        db.commit()

    @staticmethod
    def get_note(db: Session, user: User, note_id: int) -> NoteOut:
        n = (
            db.query(LearningNote)
            .filter(LearningNote.id == note_id)
            .first()
        )
        if not n:
            raise HTTPException(404, detail=f"笔记不存在：{note_id}")
        if n.user_id != user.id and not _is_admin(user):
            raise HTTPException(403, detail="无权查看该笔记")
        return _note_to_out(n)

    @staticmethod
    def list_notes(
        db: Session, user: User, query: NoteListQuery,
    ) -> NotePage:
        q = db.query(LearningNote)

        # 学员/教师只能看自己；管理员且指定 user_id 时按 user_id 过滤，否则看全部
        if _is_admin(user):
            if query.user_id:
                q = q.filter(LearningNote.user_id == query.user_id)
        else:
            q = q.filter(LearningNote.user_id == user.id)

        if query.keyword:
            kw = f"%{query.keyword.strip()}%"
            q = q.filter(
                or_(
                    LearningNote.title.like(kw),
                    LearningNote.content.like(kw),
                    LearningNote.tags.like(kw),
                )
            )
        if query.case_id:
            q = q.filter(LearningNote.case_id == query.case_id)
        if query.resource_id:
            q = q.filter(LearningNote.resource_id == query.resource_id)

        total = q.count()
        page = max(1, query.page)
        size = max(1, min(200, query.page_size))
        rows: List[LearningNote] = (
            q.order_by(desc(LearningNote.updated_at), desc(LearningNote.id))
            .offset((page - 1) * size)
            .limit(size)
            .all()
        )
        return NotePage(
            total=total,
            page=page,
            page_size=size,
            list=[_note_to_out(r) for r in rows],
        )
