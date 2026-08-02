"""
ORM 模型统一出口
方便：
    from app.db.models import User, Role, UserSetting, ...
"""

# ===== 用户 / 权限（已存在，未改动） =====
from app.db.models.role import Role  # noqa: F401
from app.db.models.user import User, RoleEnum, UserTypeEnum  # noqa: F401
from app.db.models.user_setting import UserSetting, ThemeEnum, FontSizeEnum  # noqa: F401

# ===== 公共模块 =====
from app.db.models.department import Department  # noqa: F401
from app.db.models.notice import (  # noqa: F401
    Notice,
    NoticeTypeEnum,
    NoticeStatusEnum,
)
from app.db.models.operation_log import OperationLog  # noqa: F401

# ===== AI 筛查模块 =====
from app.db.models.screening_case import (  # noqa: F401
    ScreeningCase,
    GenderEnum,
    ScreeningStatusEnum,
)
from app.db.models.screening_result import (  # noqa: F401
    ScreeningResult,
    EyeSideEnum,
    DrGradeEnum,
    RiskLevelEnum,
)

# ===== 实训培训模块 =====
from app.db.models.training_case import (  # noqa: F401
    TrainingCase,
    CaseDifficultyEnum,
    CaseCategoryEnum,
    CaseArchiveStatusEnum,
)
from app.db.models.training_record import (  # noqa: F401
    TrainingRecord,
    RecordStatusEnum,
)
from app.db.models.training_ai_result import TrainingAiResult  # noqa: F401
from app.db.models.exam_record import (  # noqa: F401
    ExamRecord,
    ExamStatusEnum,
)
from app.db.models.reading_annotation import (  # noqa: F401
    ReadingAnnotation,
    ReadingStatusEnum,
)
from app.db.models.practice_session import (  # noqa: F401
    PracticeSession,
    PracticeStatusEnum,
    PracticeModeEnum,
)

# ===== 学习资料 / 收藏 / 笔记 模块 =====
from app.db.models.learning import (  # noqa: F401
    LearningResource,
    ResourceFavorite,
    LearningNote,
    ResourceTypeEnum,
    ResourceStatusEnum,
)

# ===== 病例影像（一对多） =====
from app.db.models.case_image import (  # noqa: F401
    CaseImage,
    CaseImageRoleEnum,
    CaseImageTableEnum,
    REQUIRED_ROLES_IDRID,
)

# ===== 影像质量评估结果（派生对象，先质量后诊断） =====
from app.db.models.case_image_quality import CaseImageQuality  # noqa: F401

# ===== 机构申请 / 用户站内消息（PATIENT 端新增功能，纯追加） =====
from app.db.models.organization import Organization  # noqa: F401
from app.db.models.organization_application import (  # noqa: F401
    OrganizationApplication,
    AppStatusEnum,
)
from app.db.models.user_message import UserMessage, MessageTypeEnum  # noqa: F401

# ===== 教学实训分享（医生→学员病例分享、入库申请，纯追加） =====
from app.db.models.teaching_share import (  # noqa: F401
    TeachingShare,
    ShareTypeEnum,
    ShareSourceEnum,
    ShareStatusEnum,
)

# ===== LTI 1.3 平台对接（慧眼作为 Tool，Moodle 等 LMS 作为 Platform） =====
from app.db.models.lti_platform import (  # noqa: F401
    LtiLaunch,
    LtiNonce,
    LtiPlatform,
)

# ===== 公告已读记录（原先存进程内存，重启即丢失） =====
from app.db.models.notice_read import NoticeRead  # noqa: F401
