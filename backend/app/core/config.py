"""
全局配置模块
- 通过 pydantic-settings 自动加载根目录 .env 文件
- 项目其它位置统一通过 `from app.core.config import settings` 引用
"""

from functools import lru_cache
from typing import Annotated, List

from pydantic import field_validator
from pydantic_settings import BaseSettings, NoDecode, SettingsConfigDict


class Settings(BaseSettings):
    # ---------- 项目基础 ----------
    PROJECT_NAME: str = "慧眼教学云后端服务"
    PROJECT_VERSION: str = "1.0.0"
    API_V1_PREFIX: str = "/api/v1"
    DEBUG: bool = True

    # ---------- 服务地址 ----------
    HOST: str = "0.0.0.0"
    PORT: int = 8000

    # ---------- 数据库 ----------
    # 支持两种数据库：
    #   1) MySQL  —— 生产推荐，按 DB_HOST/DB_PORT/DB_USER/DB_PASSWORD/DB_NAME 自动拼接
    #   2) SQLite —— 本地开发零依赖，在 .env 中设 DB_TYPE=sqlite 即可
    DB_TYPE: str = "mysql"        # mysql / sqlite
    DB_HOST: str = "127.0.0.1"
    DB_PORT: int = 3306
    DB_USER: str = "root"
    DB_PASSWORD: str = "root"
    DB_NAME: str = "edu_eye"
    # SQLite 模式专用：相对项目根目录的文件路径
    SQLITE_PATH: str = "edu_eye.db"

    @property
    def DATABASE_URL(self) -> str:
        if (self.DB_TYPE or "").lower() == "sqlite":
            return f"sqlite:///{self.SQLITE_PATH}"
        return (
            f"mysql+pymysql://{self.DB_USER}:{self.DB_PASSWORD}"
            f"@{self.DB_HOST}:{self.DB_PORT}/{self.DB_NAME}?charset=utf8mb4"
        )

    # ---------- JWT ----------
    SECRET_KEY: str = "change-me"
    JWT_ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60 * 12  # 默认 12 小时

    # ---------- 微信小程序登录 ----------
    # 在 .env 配置 WECHAT_APPID / WECHAT_SECRET 后启用真实 jscode2session；
    # 二者任一为空时进入「开发模拟模式」：直接把前端传来的 code 当作 openid，
    # 便于在微信开发者工具/本地联调时无需真实 appid 即可跑通登录绑定流程。
    WECHAT_APPID: str = ""
    WECHAT_SECRET: str = ""
    WECHAT_API_TIMEOUT_SEC: int = 10
    # 「未绑定」场景下签发的临时绑定票据有效期（分钟）
    WECHAT_BIND_TICKET_TTL_MIN: int = 10

    # ---------- 跨域 ----------
    # NoDecode：禁用 pydantic-settings 的 JSON 预解析，
    # 让 .env 既能写 ["http://a","http://b"] 也能写 a,b
    CORS_ORIGINS: Annotated[List[str], NoDecode] = []

    @field_validator("CORS_ORIGINS", mode="before")
    @classmethod
    def parse_cors_origins(cls, v):
        if isinstance(v, str):
            s = v.strip()
            if not s:
                return []
            # 兼容 JSON 数组写法
            if s.startswith("["):
                import json
                try:
                    return json.loads(s)
                except Exception:
                    pass
            return [item.strip() for item in s.split(",") if item.strip()]
        return v

    # ---------- 静态资源 / 上传 ----------
    STATIC_URL: str = "/static"
    UPLOAD_DIR: str = "app/static"
    AVATAR_SUBDIR: str = "avatars"
    AVATAR_MAX_SIZE_MB: int = 5
    AVATAR_ALLOWED_EXT: Annotated[List[str], NoDecode] = [
        ".jpg", ".jpeg", ".png", ".webp", ".bmp",
    ]

    # IDRiD 批量导入约定目录（运维把数据集放到服务器上的这个路径）
    # 相对路径相对 backend 根目录；可用 .env 覆盖为绝对路径。
    IDRID_DATASET_ROOT: str = "data/idrid"

    # 眼底图（AI 筛查）上传配置
    SCREENING_SUBDIR: str = "screening"
    SCREENING_MAX_SIZE_MB: int = 20
    SCREENING_ALLOWED_EXT: Annotated[List[str], NoDecode] = [
        ".jpg", ".jpeg", ".png", ".bmp", ".webp",
    ]

    # ---------- DRGCNN 真实模型 API ----------
    # 关闭时（默认）走原 mock 推理；
    # 开启时由 _run_ai_inference 调用 http://...:9050/predict_twoeyes，
    # 调用失败会自动回退到 mock，保证体检端流程不中断。
    DRGCNN_ENABLED: bool = False
    DRGCNN_BASE_URL: str = "http://113.219.243.122:9050"
    DRGCNN_TIMEOUT_SEC: int = 60
    # 单只眼图片传给 DRGCNN 的最大体积（base64 前），超过会就地等比缩放
    DRGCNN_MAX_BYTES: int = 6 * 1024 * 1024
    # 服务端拉 URL 超时是 20s，所以默认走「读本地文件 → base64」的稳妥路径
    DRGCNN_PREFER_BASE64: bool = True

    # ---------- CSU-EYES 眼科 AI 平台 ----------
    # 提供：MA 检测 / DR 分级 / 综合诊断
    # 公网 API 域（默认，经 SSH 隧道）：http://113.219.243.122:9050/api/v1
    # 内网直连（后端与算法机同网段时更快）：http://192.168.2.103:5000
    #   —— 由 .env 里的 CSU_EYES_BASE_URL 覆盖本默认值；公网部署保持 9050 不变
    # 注意：9080 是静态门户站点（GET 方便浏览，POST 会 405），API 必须用 9050/5000
    CSU_EYES_BASE_URL: str = "http://113.219.243.122:9050"
    # 单次推理超时。正常推理约 5~30 秒（界面上也是这么写的），
    # 45 秒已相当宽裕。
    #
    # 原值 90 秒过长：算法服务经 SSH 反向隧道映射，隧道断掉时端口仍在
    # 监听、TCP 连得上但永不回数据，用户会对着转圈干等一分半。
    # 上游是间歇性的，短超时的连通性预检未必每次都能检出，
    # 所以这个上限本身必须是可接受的等待时长。
    CSU_EYES_TIMEOUT_SEC: int = 45
    # 推理结果中的 base64 图（heatmap/overlay）落盘到 /static/csu/
    CSU_EYES_RESULT_SUBDIR: str = "csu"

    # 多病灶分割（VM-UNet，出血 / 硬性渗出 / 软性渗出）。
    # 空字符串时依次找 backend/data/multi_lesions/best_mdice.pth
    # 和 D:/huiyan/multi_lesions_seg/weights/best_mdice.pth。
    MULTI_LESION_WEIGHTS: str = ""

    # ---------- Orthanc / DICOMweb ----------
    # LTI 1.3：平台要按固定地址回调（redirect_uri 必须与注册时一致），
    # 不能靠请求头推断。反向代理后面 request.base_url 拿到的是内网地址，
    # 平台按它跳转会直接失败，所以这里必须显式配。
    PUBLIC_BASE_URL: str = ""
    # 前端地址。开发期前后端不同端口，启动完成后要跳到前端而不是后端；
    # 留空则回落到 PUBLIC_BASE_URL（前后端同域部署时正确）。
    FRONTEND_BASE_URL: str = ""

    # 影像层改造（方案决策三「全量 DICOM 化」）：
    # 影像经 DICOMweb 读取，不再由前端拼接静态文件路径。
    # 关闭时全部回退到旧的文件路径方案，便于灰度切换。
    ORTHANC_ENABLED: bool = False
    ORTHANC_BASE_URL: str = "http://localhost:8042"
    ORTHANC_USER: str = "huiyan"
    # 机器间凭据，务必由 .env 覆盖；不要把生产口令写进代码
    ORTHANC_PASSWORD: str = "huiyan-local-dev"
    ORTHANC_TIMEOUT_SEC: int = 60

    # 取像必须显式声明传输语法，否则 Orthanc 会把内嵌的 JPEG
    # 转码成未压缩再返回——实测同一张眼底照 0.28 MB 变 34.94 MB（125 倍）。
    ORTHANC_TRANSFER_SYNTAX: str = "1.2.840.10008.1.2.4.50"  # JPEG Baseline

    # ---------- Keycloak ----------
    # 身份统一由 Keycloak 承担（报告 P0：强制改密 / 限流 / 会话超时 / 审计）。
    # Orthanc 通过授权插件回调后端校验同一套令牌，PACS 不再使用静态口令。
    KEYCLOAK_BASE_URL: str = "http://localhost:8085"
    KEYCLOAK_REALM: str = "huiyan"
    KEYCLOAK_CLIENT_ID: str = "huiyan-backend"
    KEYCLOAK_CLIENT_SECRET: str = "huiyan-backend-local-dev-secret"
    # 登录口令是否交给 Keycloak 校验。开启后口令策略、登录限流、
    # 会话时长与失败审计立即生效；Keycloak 不可达时自动回退本地校验。
    KEYCLOAK_LOGIN_ENABLED: bool = False

    @field_validator("AVATAR_ALLOWED_EXT", "SCREENING_ALLOWED_EXT", mode="before")
    @classmethod
    def parse_ext_list(cls, v):
        if isinstance(v, str):
            s = v.strip()
            if not s:
                return []
            if s.startswith("["):
                import json
                try:
                    return [str(x).strip().lower() for x in json.loads(s)]
                except Exception:
                    pass
            return [e.strip().lower() for e in s.split(",") if e.strip()]
        return v

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=True,
        extra="ignore",
    )


@lru_cache()
def get_settings() -> Settings:
    """缓存配置单例，避免每次访问重新加载 .env"""
    return Settings()


settings: Settings = get_settings()
