"""
v1 路由汇总
所有子路由统一在此注册
"""

from fastapi import APIRouter

from app.api.v1 import admin_import as admin_import_router
from app.api.v1 import admin_users as admin_users_router
from app.api.v1 import student_application as student_application_router
from app.api.v1 import case_browse as case_browse_router
from app.api.v1 import case_image as case_image_router
from app.api.v1 import common as common_router
from app.api.v1 import diagnosis as diagnosis_router
from app.api.v1 import learning as learning_router
from app.api.v1 import login as login_router
from app.api.v1 import patient as patient_router_module
from app.api.v1 import physical as physical_router
from app.api.v1 import practice as practice_router
from app.api.v1 import reading as reading_router
from app.api.v1 import rotation as rotation_router
from app.api.v1 import screening as screening_router
from app.api.v1 import training as training_router
from app.api.v1 import user_center as user_router
# ===== 机构申请 / 用户消息（PATIENT 端新增功能，纯追加） =====
from app.api.v1 import organization as organization_router
from app.api.v1 import user_message as user_message_router
# ===== 教学实训分享（纯追加） =====
from app.api.v1 import teaching as teaching_router
from app.api.v1 import dicomweb as dicomweb_router
from app.api.v1 import orthanc_auth as orthanc_auth_router
# ===== LTI 1.3（慧眼作为 Tool 挂进 Moodle 等 LMS） =====
from app.api.v1 import lti as lti_router

api_v1_router = APIRouter()

api_v1_router.include_router(login_router.router)
api_v1_router.include_router(patient_router_module.auth_router)
api_v1_router.include_router(patient_router_module.patient_router)
api_v1_router.include_router(user_router.router)
api_v1_router.include_router(training_router.router)
api_v1_router.include_router(screening_router.router)
api_v1_router.include_router(diagnosis_router.router)
api_v1_router.include_router(physical_router.router)
api_v1_router.include_router(case_browse_router.router)
api_v1_router.include_router(case_image_router.router)
api_v1_router.include_router(reading_router.router)
api_v1_router.include_router(practice_router.router)
api_v1_router.include_router(rotation_router.router)
api_v1_router.include_router(learning_router.router)
api_v1_router.include_router(common_router.router)
api_v1_router.include_router(admin_import_router.router)
api_v1_router.include_router(admin_users_router.router)
api_v1_router.include_router(student_application_router.router)
# ===== 机构申请 / 用户消息（PATIENT 端新增功能，纯追加） =====
api_v1_router.include_router(organization_router.router)
api_v1_router.include_router(user_message_router.router)
api_v1_router.include_router(teaching_router.router)
api_v1_router.include_router(lti_router.router)
# 影像层改造：DICOMweb（方案决策三「全量 DICOM 化」）
api_v1_router.include_router(dicomweb_router.router)
# PACS 授权回调（Orthanc Authorization 插件 → Keycloak 令牌校验）
api_v1_router.include_router(orthanc_auth_router.router)
