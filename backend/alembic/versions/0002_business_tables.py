"""add business tables: department / notice / screening / training / exam

Revision ID: 0002_business_tables
Revises: 0001_baseline
Create Date: 2026-05-22 00:10:00

新增表：
    biz_department
    biz_notice
    biz_screening_case
    biz_screening_result
    biz_training_case
    biz_training_record
    biz_exam_record
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0002_business_tables"
down_revision: Union[str, None] = "0001_baseline"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ============================================================
    # 1. biz_department
    # ============================================================
    op.create_table(
        "biz_department",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False, comment="科室ID"),
        sa.Column("code", sa.String(length=32), nullable=False, comment="科室编码"),
        sa.Column("name", sa.String(length=64), nullable=False, comment="科室名称"),
        sa.Column("short_name", sa.String(length=32), nullable=False, server_default="", comment="科室简称"),
        sa.Column("leader", sa.String(length=32), nullable=False, server_default="", comment="科室负责人姓名"),
        sa.Column("phone", sa.String(length=32), nullable=False, server_default="", comment="联系电话"),
        sa.Column("sort_order", sa.Integer(), nullable=False, server_default="0", comment="排序值"),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("1"), comment="是否启用"),
        sa.Column("remark", sa.String(length=255), nullable=False, server_default="", comment="备注"),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("code", name="uk_department_code"),
        comment="科室表",
        mysql_engine="InnoDB",
        mysql_charset="utf8mb4",
        mysql_collate="utf8mb4_unicode_ci",
    )
    op.create_index("ix_biz_department_code", "biz_department", ["code"])

    # ============================================================
    # 2. biz_notice
    # ============================================================
    op.create_table(
        "biz_notice",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False, comment="公告ID"),
        sa.Column("title", sa.String(length=128), nullable=False, comment="公告标题"),
        sa.Column("summary", sa.String(length=255), nullable=False, server_default="", comment="公告摘要"),
        sa.Column("content", sa.Text(), nullable=False, comment="公告正文"),
        sa.Column("cover_url", sa.String(length=255), nullable=False, server_default="", comment="封面图URL"),
        sa.Column("notice_type", sa.String(length=16), nullable=False, server_default="SYSTEM", comment="公告分类"),
        sa.Column("status", sa.String(length=16), nullable=False, server_default="DRAFT", comment="状态"),
        sa.Column("visible_roles", sa.String(length=64), nullable=False, server_default="", comment="可见角色"),
        sa.Column("is_top", sa.Boolean(), nullable=False, server_default=sa.text("0"), comment="是否置顶"),
        sa.Column("publisher_id", sa.Integer(), nullable=False, comment="发布者用户ID"),
        sa.Column("publish_at", sa.DateTime(), nullable=True, comment="发布时间"),
        sa.Column("expire_at", sa.DateTime(), nullable=True, comment="失效时间"),
        sa.Column("view_count", sa.Integer(), nullable=False, server_default="0", comment="阅读次数"),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(
            ["publisher_id"], ["sys_user.id"],
            name="fk_notice_publisher", ondelete="RESTRICT",
        ),
        comment="公告表",
        mysql_engine="InnoDB",
        mysql_charset="utf8mb4",
        mysql_collate="utf8mb4_unicode_ci",
    )
    op.create_index("ix_biz_notice_title", "biz_notice", ["title"])
    op.create_index("ix_biz_notice_type", "biz_notice", ["notice_type"])
    op.create_index("ix_biz_notice_status", "biz_notice", ["status"])

    # ============================================================
    # 3. biz_screening_case
    # ============================================================
    op.create_table(
        "biz_screening_case",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False, comment="筛查病例ID"),
        sa.Column("case_no", sa.String(length=32), nullable=False, comment="业务编号"),
        sa.Column("patient_name", sa.String(length=64), nullable=False, server_default="", comment="患者姓名"),
        sa.Column("patient_id_card", sa.String(length=32), nullable=False, server_default="", comment="身份证/就诊号"),
        sa.Column("gender", sa.String(length=2), nullable=False, server_default="U", comment="性别"),
        sa.Column("age", sa.Integer(), nullable=True, comment="年龄"),
        sa.Column("birth_date", sa.Date(), nullable=True, comment="出生日期"),
        sa.Column("phone", sa.String(length=20), nullable=False, server_default="", comment="联系电话"),
        sa.Column("chief_complaint", sa.String(length=255), nullable=False, server_default="", comment="主诉"),
        sa.Column("medical_history", sa.Text(), nullable=False, comment="病史摘要"),
        sa.Column("diabetes_years", sa.Integer(), nullable=True, comment="糖尿病病程"),
        sa.Column("image_paths", sa.JSON(), nullable=True, comment="影像路径 JSON"),
        sa.Column("image_count", sa.Integer(), nullable=False, server_default="0", comment="影像数量"),
        sa.Column("status", sa.String(length=16), nullable=False, server_default="PENDING", comment="筛查状态"),
        sa.Column("department_id", sa.Integer(), nullable=True, comment="送检科室"),
        sa.Column("submit_user_id", sa.Integer(), nullable=False, comment="送检/录入用户ID"),
        sa.Column("review_user_id", sa.Integer(), nullable=True, comment="复核医生ID"),
        sa.Column("submit_at", sa.DateTime(), nullable=True, comment="送检时间"),
        sa.Column("review_at", sa.DateTime(), nullable=True, comment="复核时间"),
        sa.Column("remark", sa.String(length=255), nullable=False, server_default="", comment="备注"),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("case_no", name="uk_screening_case_no"),
        sa.ForeignKeyConstraint(
            ["department_id"], ["biz_department.id"],
            name="fk_screening_dept", ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["submit_user_id"], ["sys_user.id"],
            name="fk_screening_submit_user", ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["review_user_id"], ["sys_user.id"],
            name="fk_screening_review_user", ondelete="SET NULL",
        ),
        comment="AI筛查病例表",
        mysql_engine="InnoDB",
        mysql_charset="utf8mb4",
        mysql_collate="utf8mb4_unicode_ci",
    )
    op.create_index("ix_screening_case_no", "biz_screening_case", ["case_no"])
    op.create_index("ix_screening_id_card", "biz_screening_case", ["patient_id_card"])
    op.create_index("ix_screening_status", "biz_screening_case", ["status"])
    op.create_index("ix_screening_department", "biz_screening_case", ["department_id"])
    op.create_index("ix_screening_submit_user", "biz_screening_case", ["submit_user_id"])

    # ============================================================
    # 4. biz_screening_result
    # ============================================================
    op.create_table(
        "biz_screening_result",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False, comment="结果ID"),
        sa.Column("case_id", sa.Integer(), nullable=False, comment="所属筛查病例ID"),
        sa.Column("eye_side", sa.String(length=4), nullable=False, server_default="OU", comment="眼别"),
        sa.Column("model_name", sa.String(length=64), nullable=False, server_default="", comment="AI模型名称"),
        sa.Column("model_version", sa.String(length=32), nullable=False, server_default="", comment="模型版本"),
        sa.Column("dr_grade", sa.String(length=4), nullable=False, server_default="0", comment="DR分级"),
        sa.Column("has_dme", sa.Integer(), nullable=False, server_default="0", comment="是否伴有DME"),
        sa.Column("risk_level", sa.String(length=16), nullable=False, server_default="LOW", comment="风险等级"),
        sa.Column("risk_score", sa.Float(), nullable=False, server_default="0", comment="风险分0~1"),
        sa.Column("referral_required", sa.Integer(), nullable=False, server_default="0", comment="是否建议转诊"),
        sa.Column("lesions", sa.JSON(), nullable=True, comment="病变检出JSON"),
        sa.Column("annotations", sa.JSON(), nullable=True, comment="标注几何JSON"),
        sa.Column("heatmap_path", sa.String(length=255), nullable=False, server_default="", comment="热力图URL"),
        sa.Column("thumbnail_path", sa.String(length=255), nullable=False, server_default="", comment="缩略图URL"),
        sa.Column("infer_duration_ms", sa.Integer(), nullable=False, server_default="0", comment="推理耗时ms"),
        sa.Column("inferred_at", sa.DateTime(), nullable=True, comment="AI完成时间"),
        sa.Column("doctor_diagnosis", sa.Text(), nullable=False, comment="医生诊断意见"),
        sa.Column("doctor_grade", sa.String(length=4), nullable=False, server_default="", comment="医生定级"),
        sa.Column("doctor_id", sa.Integer(), nullable=True, comment="复核医生ID"),
        sa.Column("doctor_at", sa.DateTime(), nullable=True, comment="医生复核时间"),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(
            ["case_id"], ["biz_screening_case.id"],
            name="fk_result_case", ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["doctor_id"], ["sys_user.id"],
            name="fk_result_doctor", ondelete="SET NULL",
        ),
        comment="AI筛查结果表",
        mysql_engine="InnoDB",
        mysql_charset="utf8mb4",
        mysql_collate="utf8mb4_unicode_ci",
    )
    op.create_index("ix_screening_result_case", "biz_screening_result", ["case_id"])
    op.create_index("ix_screening_result_dr", "biz_screening_result", ["dr_grade"])
    op.create_index("ix_screening_result_risk", "biz_screening_result", ["risk_level"])

    # ============================================================
    # 5. biz_training_case
    # ============================================================
    op.create_table(
        "biz_training_case",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False, comment="实训病例ID"),
        sa.Column("case_no", sa.String(length=32), nullable=False, comment="实训病例编号"),
        sa.Column("title", sa.String(length=128), nullable=False, comment="病例标题"),
        sa.Column("description", sa.Text(), nullable=False, comment="病例描述"),
        sa.Column("category", sa.String(length=16), nullable=False, server_default="DR", comment="病例类别"),
        sa.Column("difficulty", sa.String(length=8), nullable=False, server_default="EASY", comment="难度"),
        sa.Column("patient_age", sa.Integer(), nullable=True, comment="患者年龄"),
        sa.Column("patient_gender", sa.String(length=2), nullable=False, server_default="U", comment="患者性别"),
        sa.Column("clinical_info", sa.Text(), nullable=False, comment="临床信息"),
        sa.Column("image_paths", sa.JSON(), nullable=True, comment="影像路径JSON"),
        sa.Column("gold_dr_grade", sa.String(length=4), nullable=False, server_default="0", comment="金标准DR分级"),
        sa.Column("gold_diagnosis", sa.Text(), nullable=False, comment="金标准诊断"),
        sa.Column("gold_lesions", sa.JSON(), nullable=True, comment="金标准病变"),
        sa.Column("gold_annotations", sa.JSON(), nullable=True, comment="金标准标注"),
        sa.Column("gold_heatmap_path", sa.String(length=255), nullable=False, server_default="", comment="金标准热力图URL"),
        sa.Column("teaching_points", sa.Text(), nullable=False, comment="教学要点"),
        sa.Column("pass_score", sa.Integer(), nullable=False, server_default="60", comment="及格分"),
        sa.Column("is_published", sa.Boolean(), nullable=False, server_default=sa.text("0"), comment="是否发布"),
        sa.Column("creator_id", sa.Integer(), nullable=False, comment="创建教师ID"),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("case_no", name="uk_training_case_no"),
        sa.ForeignKeyConstraint(
            ["creator_id"], ["sys_user.id"],
            name="fk_training_case_creator", ondelete="RESTRICT",
        ),
        comment="实训病例表",
        mysql_engine="InnoDB",
        mysql_charset="utf8mb4",
        mysql_collate="utf8mb4_unicode_ci",
    )
    op.create_index("ix_training_case_no", "biz_training_case", ["case_no"])
    op.create_index("ix_training_case_cat", "biz_training_case", ["category"])
    op.create_index("ix_training_case_diff", "biz_training_case", ["difficulty"])
    op.create_index("ix_training_case_pub", "biz_training_case", ["is_published"])

    # ============================================================
    # 6. biz_training_record
    # ============================================================
    op.create_table(
        "biz_training_record",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False, comment="实训记录ID"),
        sa.Column("user_id", sa.Integer(), nullable=False, comment="学员用户ID"),
        sa.Column("case_id", sa.Integer(), nullable=False, comment="实训病例ID"),
        sa.Column("attempt_no", sa.Integer(), nullable=False, server_default="1", comment="第几次尝试"),
        sa.Column("status", sa.String(length=16), nullable=False, server_default="DRAFT", comment="状态"),
        sa.Column("student_dr_grade", sa.String(length=4), nullable=False, server_default="", comment="学员DR分级"),
        sa.Column("student_diagnosis", sa.Text(), nullable=False, comment="学员诊断"),
        sa.Column("student_lesions", sa.JSON(), nullable=True, comment="学员病变标注"),
        sa.Column("student_annotations", sa.JSON(), nullable=True, comment="学员几何坐标"),
        sa.Column("grade_score", sa.Float(), nullable=False, server_default="0", comment="分级题得分"),
        sa.Column("annotation_score", sa.Float(), nullable=False, server_default="0", comment="标注题得分"),
        sa.Column("diagnosis_score", sa.Float(), nullable=False, server_default="0", comment="诊断题得分"),
        sa.Column("total_score", sa.Float(), nullable=False, server_default="0", comment="总分"),
        sa.Column("iou_avg", sa.Float(), nullable=False, server_default="0", comment="平均IoU"),
        sa.Column("is_passed", sa.Integer(), nullable=False, server_default="0", comment="是否通过"),
        sa.Column("duration_seconds", sa.Integer(), nullable=False, server_default="0", comment="作答用时秒"),
        sa.Column("started_at", sa.DateTime(), nullable=True, comment="开始时间"),
        sa.Column("submitted_at", sa.DateTime(), nullable=True, comment="提交时间"),
        sa.Column("graded_at", sa.DateTime(), nullable=True, comment="评分时间"),
        sa.Column("teacher_comment", sa.Text(), nullable=False, comment="教师点评"),
        sa.Column("teacher_id", sa.Integer(), nullable=True, comment="点评教师ID"),
        sa.Column("reviewed_at", sa.DateTime(), nullable=True, comment="点评时间"),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(
            ["user_id"], ["sys_user.id"],
            name="fk_training_record_user", ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["case_id"], ["biz_training_case.id"],
            name="fk_training_record_case", ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["teacher_id"], ["sys_user.id"],
            name="fk_training_record_teacher", ondelete="SET NULL",
        ),
        comment="学员实训记录表",
        mysql_engine="InnoDB",
        mysql_charset="utf8mb4",
        mysql_collate="utf8mb4_unicode_ci",
    )
    op.create_index("ix_training_record_user", "biz_training_record", ["user_id"])
    op.create_index("ix_training_record_case", "biz_training_record", ["case_id"])
    op.create_index("ix_training_record_status", "biz_training_record", ["status"])
    op.create_index("ix_training_record_score", "biz_training_record", ["total_score"])

    # ============================================================
    # 7. biz_exam_record
    # ============================================================
    op.create_table(
        "biz_exam_record",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False, comment="考核记录ID"),
        sa.Column("exam_no", sa.String(length=32), nullable=False, comment="考核批次编号"),
        sa.Column("exam_title", sa.String(length=128), nullable=False, comment="考核标题"),
        sa.Column("exam_round", sa.String(length=64), nullable=False, server_default="", comment="期次/轮次"),
        sa.Column("user_id", sa.Integer(), nullable=False, comment="学员ID"),
        sa.Column("question_records", sa.JSON(), nullable=True, comment="题目明细JSON"),
        sa.Column("total_questions", sa.Integer(), nullable=False, server_default="0", comment="总题数"),
        sa.Column("correct_count", sa.Integer(), nullable=False, server_default="0", comment="正确题数"),
        sa.Column("total_score", sa.Float(), nullable=False, server_default="0", comment="总成绩"),
        sa.Column("grade_score", sa.Float(), nullable=False, server_default="0", comment="分级题得分"),
        sa.Column("annotation_score", sa.Float(), nullable=False, server_default="0", comment="标注题得分"),
        sa.Column("diagnosis_score", sa.Float(), nullable=False, server_default="0", comment="诊断题得分"),
        sa.Column("pass_score", sa.Integer(), nullable=False, server_default="60", comment="及格分"),
        sa.Column("is_passed", sa.Boolean(), nullable=False, server_default=sa.text("0"), comment="是否合格"),
        sa.Column("rank", sa.Integer(), nullable=True, comment="同批次排名"),
        sa.Column("status", sa.String(length=16), nullable=False, server_default="NOT_STARTED", comment="状态"),
        sa.Column("duration_seconds", sa.Integer(), nullable=False, server_default="0", comment="作答用时秒"),
        sa.Column("started_at", sa.DateTime(), nullable=True, comment="开考时间"),
        sa.Column("submitted_at", sa.DateTime(), nullable=True, comment="交卷时间"),
        sa.Column("graded_at", sa.DateTime(), nullable=True, comment="批阅时间"),
        sa.Column("examiner_id", sa.Integer(), nullable=True, comment="主考教师ID"),
        sa.Column("teacher_comment", sa.Text(), nullable=False, comment="教师总评"),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(
            ["user_id"], ["sys_user.id"],
            name="fk_exam_user", ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["examiner_id"], ["sys_user.id"],
            name="fk_exam_examiner", ondelete="SET NULL",
        ),
        comment="考核成绩表",
        mysql_engine="InnoDB",
        mysql_charset="utf8mb4",
        mysql_collate="utf8mb4_unicode_ci",
    )
    op.create_index("ix_exam_record_no", "biz_exam_record", ["exam_no"])
    op.create_index("ix_exam_record_user", "biz_exam_record", ["user_id"])
    op.create_index("ix_exam_record_status", "biz_exam_record", ["status"])
    op.create_index("ix_exam_record_score", "biz_exam_record", ["total_score"])


def downgrade() -> None:
    """按外键依赖反向删除"""
    op.drop_table("biz_exam_record")
    op.drop_table("biz_training_record")
    op.drop_table("biz_training_case")
    op.drop_table("biz_screening_result")
    op.drop_table("biz_screening_case")
    op.drop_table("biz_notice")
    op.drop_table("biz_department")
