# -*- coding: utf-8 -*-
"""
LTI 1.3 平台注册

慧眼作为 LTI Tool（工具端），Moodle 等 LMS 作为 Platform（平台端）。
一次注册对应一个 (issuer, client_id, deployment_id) 三元组 ——
同一个 Moodle 站点可以把慧眼装在多个课程里，deployment_id 才是
真正区分「哪一次安装」的键。

采用 LTI 1.3 而不是自己实现一套对接协议：不管院方现在有没有 LMS，
支持这个标准本身就是国际背书；而且换一家 LMS 时不用重做集成。
"""

from typing import Optional

from sqlalchemy import Boolean, Index, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, TimestampMixin


class LtiPlatform(Base, TimestampMixin):
    """已登记的 LTI 平台（LMS）"""

    __tablename__ = "biz_lti_platform"
    __table_args__ = (
        # 同一 issuer 下可有多个 client_id，同一 client_id 下可有多个部署
        Index("ux_lti_platform_triple", "issuer", "client_id", "deployment_id",
              unique=True),
        {"comment": "LTI 1.3 平台注册表"},
    )

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)

    name: Mapped[str] = mapped_column(
        String(128), nullable=False, default="", comment="便于识别的名称",
    )
    issuer: Mapped[str] = mapped_column(
        String(255), nullable=False, index=True, comment="平台 issuer（iss）",
    )
    client_id: Mapped[str] = mapped_column(
        String(255), nullable=False, comment="平台为本工具分配的 client_id",
    )
    deployment_id: Mapped[str] = mapped_column(
        String(255), nullable=False, comment="部署 ID：区分同一平台的多次安装",
    )

    # 平台端点。JWKS 用于验签平台签发的 id_token；
    # token url 用于换取访问令牌回传成绩（AGS）。
    auth_login_url: Mapped[str] = mapped_column(
        String(512), nullable=False, default="", comment="平台的 OIDC 授权端点",
    )
    auth_token_url: Mapped[str] = mapped_column(
        String(512), nullable=False, default="", comment="平台的令牌端点",
    )
    key_set_url: Mapped[str] = mapped_column(
        String(512), nullable=False, default="", comment="平台 JWKS 地址",
    )

    # 是否允许该平台的用户在本地自动建号。
    # 默认关闭：教学系统里凭空多出来的账号，成绩归属会说不清。
    auto_provision: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False,
        comment="是否允许自动建号；默认关闭",
    )
    enabled: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=True,
    )
    note: Mapped[str] = mapped_column(Text, nullable=False, default="")


class LtiNonce(Base, TimestampMixin):
    """
    已使用过的 nonce。

    LTI 1.3 要求工具端拒绝重放：同一个 id_token 被截获后再发一次，
    必须打不开。只验签名和过期时间挡不住重放 —— 签名依然有效。
    """

    __tablename__ = "biz_lti_nonce"
    __table_args__ = {"comment": "LTI nonce 防重放"}

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    nonce: Mapped[str] = mapped_column(
        String(128), nullable=False, unique=True, index=True,
    )
    issuer: Mapped[str] = mapped_column(String(255), nullable=False, default="")


class LtiLaunch(Base, TimestampMixin):
    """
    一次 LTI 启动的上下文。

    成绩要回传到平台的作业栏，必须记住这次启动带来的
    line item 地址与用户标识 —— 学员做完练习是几分钟后的事，
    那时原始的 id_token 早就不在手上了。
    """

    __tablename__ = "biz_lti_launch"
    __table_args__ = {"comment": "LTI 启动上下文"}

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    platform_id: Mapped[int] = mapped_column(nullable=False, index=True)
    user_id: Mapped[Optional[int]] = mapped_column(nullable=True, index=True)

    lti_user_id: Mapped[str] = mapped_column(
        String(255), nullable=False, default="", comment="平台侧用户标识（sub）",
    )
    context_id: Mapped[str] = mapped_column(
        String(255), nullable=False, default="", comment="课程/上下文 ID",
    )
    resource_link_id: Mapped[str] = mapped_column(
        String(255), nullable=False, default="", comment="资源链接 ID",
    )
    # AGS：成绩回传地址。平台未授予该服务时为空，此时不回传，
    # 而不是假装成功。
    lineitem_url: Mapped[str] = mapped_column(
        String(1024), nullable=False, default="", comment="AGS line item 地址",
    )
    scope: Mapped[str] = mapped_column(
        Text, nullable=False, default="", comment="平台授予的 AGS scope",
    )
    roles: Mapped[str] = mapped_column(Text, nullable=False, default="")
