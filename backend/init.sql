-- =====================================================================
--  慧眼教学云后端 · 数据库初始化脚本（MySQL 8.0+ / 兼容 5.7）
--  字符集统一 utf8mb4，引擎 InnoDB
--  使用方式：
--      mysql -uroot -p < init.sql
-- =====================================================================

-- 1. 建库
CREATE DATABASE IF NOT EXISTS `edu_eye`
    DEFAULT CHARACTER SET utf8mb4
    DEFAULT COLLATE utf8mb4_unicode_ci;

USE `edu_eye`;

-- 2. 角色表
DROP TABLE IF EXISTS `sys_role`;
CREATE TABLE `sys_role`
(
    `id`         INT AUTO_INCREMENT             NOT NULL COMMENT '角色ID',
    `code`       VARCHAR(32)                    NOT NULL COMMENT '角色编码：STUDENT / TEACHER / ADMIN',
    `name`       VARCHAR(32)                    NOT NULL COMMENT '角色显示名',
    `remark`     VARCHAR(255) DEFAULT ''        NOT NULL COMMENT '角色描述',
    `created_at` DATETIME     DEFAULT CURRENT_TIMESTAMP NOT NULL COMMENT '创建时间',
    `updated_at` DATETIME     DEFAULT CURRENT_TIMESTAMP NOT NULL ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间',
    PRIMARY KEY (`id`),
    UNIQUE KEY `uk_role_code` (`code`)
) ENGINE = InnoDB
  DEFAULT CHARSET = utf8mb4
  COLLATE = utf8mb4_unicode_ci COMMENT = '角色表';

-- 3. 用户表
DROP TABLE IF EXISTS `sys_user`;
CREATE TABLE `sys_user`
(
    `id`             INT AUTO_INCREMENT                NOT NULL COMMENT '用户ID',
    `username`       VARCHAR(64)                       NOT NULL COMMENT '登录账号',
    `password_hash`  VARCHAR(128)                      NOT NULL COMMENT '密码哈希（bcrypt）',
    `real_name`      VARCHAR(32)  DEFAULT ''           NOT NULL COMMENT '真实姓名',
    `phone`          VARCHAR(20)  DEFAULT ''           NOT NULL COMMENT '手机号',
    `email`          VARCHAR(128) DEFAULT ''           NOT NULL COMMENT '邮箱',
    `department`     VARCHAR(64)  DEFAULT ''           NOT NULL COMMENT '所属科室',
    `title`          VARCHAR(32)  DEFAULT ''           NOT NULL COMMENT '职称',
    `avatar`         VARCHAR(255) DEFAULT ''           NOT NULL COMMENT '头像URL',
    `role_id`        INT                               NOT NULL COMMENT '角色ID',
    `is_active`      TINYINT(1)   DEFAULT 1            NOT NULL COMMENT '账号是否启用：1启用 0停用',
    `last_login_at`  DATETIME     DEFAULT NULL                  COMMENT '最近登录时间',
    `last_login_ip`  VARCHAR(64)  DEFAULT ''           NOT NULL COMMENT '最近登录IP',
    `created_at`     DATETIME     DEFAULT CURRENT_TIMESTAMP NOT NULL COMMENT '创建时间',
    `updated_at`     DATETIME     DEFAULT CURRENT_TIMESTAMP NOT NULL ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间',
    PRIMARY KEY (`id`),
    UNIQUE KEY `uk_user_username` (`username`),
    KEY `idx_user_role` (`role_id`),
    CONSTRAINT `fk_user_role` FOREIGN KEY (`role_id`) REFERENCES `sys_role` (`id`) ON DELETE RESTRICT
) ENGINE = InnoDB
  DEFAULT CHARSET = utf8mb4
  COLLATE = utf8mb4_unicode_ci COMMENT = '用户信息表';

-- 4. 用户个性化配置表
DROP TABLE IF EXISTS `sys_user_setting`;
CREATE TABLE `sys_user_setting`
(
    `id`              INT AUTO_INCREMENT             NOT NULL COMMENT '配置ID',
    `user_id`         INT                            NOT NULL COMMENT '用户ID（一对一）',
    `theme`           VARCHAR(16)  DEFAULT 'light'   NOT NULL COMMENT '主题：light/dark/auto',
    `font_size`       VARCHAR(16)  DEFAULT 'normal'  NOT NULL COMMENT '字体大小：small/normal/large',
    `language`        VARCHAR(16)  DEFAULT 'zh-CN'   NOT NULL COMMENT '界面语言',
    `notify_message`  TINYINT(1)   DEFAULT 1         NOT NULL COMMENT '是否开启站内消息通知',
    `notify_email`    TINYINT(1)   DEFAULT 0         NOT NULL COMMENT '是否开启邮件通知',
    `notify_sms`      TINYINT(1)   DEFAULT 0         NOT NULL COMMENT '是否开启短信通知',
    `notify_sound`    TINYINT(1)   DEFAULT 1         NOT NULL COMMENT '是否启用消息提示音',
    `created_at`      DATETIME     DEFAULT CURRENT_TIMESTAMP NOT NULL COMMENT '创建时间',
    `updated_at`      DATETIME     DEFAULT CURRENT_TIMESTAMP NOT NULL ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间',
    PRIMARY KEY (`id`),
    UNIQUE KEY `uk_setting_user` (`user_id`),
    CONSTRAINT `fk_setting_user` FOREIGN KEY (`user_id`) REFERENCES `sys_user` (`id`) ON DELETE CASCADE
) ENGINE = InnoDB
  DEFAULT CHARSET = utf8mb4
  COLLATE = utf8mb4_unicode_ci COMMENT = '用户个性化配置表';

-- 5. 默认角色
INSERT INTO `sys_role` (`code`, `name`, `remark`) VALUES
    ('STUDENT', '学员',     '学员用户：仅学习和阅片练习权限'),
    ('TEACHER', '带教老师', '教学带教用户：负责课程与考核'),
    ('ADMIN',   '管理员',   '管理员用户：拥有系统全部权限')
ON DUPLICATE KEY UPDATE `name` = VALUES(`name`), `remark` = VALUES(`remark`);

-- 6. 默认账号（密码均使用 bcrypt 占位；实际推荐通过 init_data.py 生成）
--    若需先用 SQL 体验，可使用以下哈希：
--    admin   / Admin@123
--    teacher / Huiyan@123
--    student / Huiyan@123
--    （bcrypt 哈希在不同机器上签发结果不同，建议运行 `python init_data.py` 自动生成）


-- =====================================================================
--  业务模块（公共 / AI 筛查 / 实训培训）
--  表名前缀 biz_，与系统表 sys_ 区分
-- =====================================================================

-- 7. 科室表
DROP TABLE IF EXISTS `biz_department`;
CREATE TABLE `biz_department`
(
    `id`         INT AUTO_INCREMENT             NOT NULL COMMENT '科室ID',
    `code`       VARCHAR(32)                    NOT NULL COMMENT '科室编码',
    `name`       VARCHAR(64)                    NOT NULL COMMENT '科室名称',
    `short_name` VARCHAR(32)  DEFAULT ''        NOT NULL COMMENT '科室简称',
    `leader`     VARCHAR(32)  DEFAULT ''        NOT NULL COMMENT '科室负责人姓名',
    `phone`      VARCHAR(32)  DEFAULT ''        NOT NULL COMMENT '联系电话',
    `sort_order` INT          DEFAULT 0         NOT NULL COMMENT '排序值',
    `is_active`  TINYINT(1)   DEFAULT 1         NOT NULL COMMENT '是否启用',
    `remark`     VARCHAR(255) DEFAULT ''        NOT NULL COMMENT '备注',
    `created_at` DATETIME     DEFAULT CURRENT_TIMESTAMP NOT NULL COMMENT '创建时间',
    `updated_at` DATETIME     DEFAULT CURRENT_TIMESTAMP NOT NULL ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间',
    PRIMARY KEY (`id`),
    UNIQUE KEY `uk_department_code` (`code`)
) ENGINE = InnoDB
  DEFAULT CHARSET = utf8mb4
  COLLATE = utf8mb4_unicode_ci COMMENT = '科室表';

-- 8. 公告表
DROP TABLE IF EXISTS `biz_notice`;
CREATE TABLE `biz_notice`
(
    `id`             INT AUTO_INCREMENT                NOT NULL COMMENT '公告ID',
    `title`          VARCHAR(128)                      NOT NULL COMMENT '公告标题',
    `summary`        VARCHAR(255) DEFAULT ''           NOT NULL COMMENT '公告摘要',
    `content`        TEXT                              NOT NULL COMMENT '公告正文',
    `cover_url`      VARCHAR(255) DEFAULT ''           NOT NULL COMMENT '封面图URL',
    `notice_type`    VARCHAR(16)  DEFAULT 'SYSTEM'     NOT NULL COMMENT '公告分类：SYSTEM/TRAINING/SCREENING/EXAM',
    `status`         VARCHAR(16)  DEFAULT 'DRAFT'      NOT NULL COMMENT '状态：DRAFT/PUBLISHED/ARCHIVED',
    `visible_roles`  VARCHAR(64)  DEFAULT ''           NOT NULL COMMENT '可见角色，逗号分隔；空表示全员',
    `is_top`         TINYINT(1)   DEFAULT 0            NOT NULL COMMENT '是否置顶',
    `publisher_id`   INT                               NOT NULL COMMENT '发布者用户ID',
    `publish_at`     DATETIME     DEFAULT NULL                  COMMENT '发布时间',
    `expire_at`      DATETIME     DEFAULT NULL                  COMMENT '失效时间',
    `view_count`     INT          DEFAULT 0            NOT NULL COMMENT '阅读次数',
    `created_at`     DATETIME     DEFAULT CURRENT_TIMESTAMP NOT NULL COMMENT '创建时间',
    `updated_at`     DATETIME     DEFAULT CURRENT_TIMESTAMP NOT NULL ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间',
    PRIMARY KEY (`id`),
    KEY `ix_notice_title` (`title`),
    KEY `ix_notice_type`  (`notice_type`),
    KEY `ix_notice_status`(`status`),
    CONSTRAINT `fk_notice_publisher` FOREIGN KEY (`publisher_id`) REFERENCES `sys_user` (`id`) ON DELETE RESTRICT
) ENGINE = InnoDB
  DEFAULT CHARSET = utf8mb4
  COLLATE = utf8mb4_unicode_ci COMMENT = '公告表';

-- 9. AI 筛查病例表
DROP TABLE IF EXISTS `biz_screening_case`;
CREATE TABLE `biz_screening_case`
(
    `id`              INT AUTO_INCREMENT                NOT NULL COMMENT '筛查病例ID',
    `case_no`         VARCHAR(32)                       NOT NULL COMMENT '业务编号',
    `patient_name`    VARCHAR(64)  DEFAULT ''           NOT NULL COMMENT '患者姓名',
    `patient_id_card` VARCHAR(32)  DEFAULT ''           NOT NULL COMMENT '身份证/就诊号',
    `gender`          VARCHAR(2)   DEFAULT 'U'          NOT NULL COMMENT '性别：M/F/U',
    `age`             INT          DEFAULT NULL                  COMMENT '年龄',
    `birth_date`      DATE         DEFAULT NULL                  COMMENT '出生日期',
    `phone`           VARCHAR(20)  DEFAULT ''           NOT NULL COMMENT '联系电话',
    `chief_complaint` VARCHAR(255) DEFAULT ''           NOT NULL COMMENT '主诉',
    `medical_history` TEXT                              NOT NULL COMMENT '病史摘要',
    `diabetes_years`  INT          DEFAULT NULL                  COMMENT '糖尿病病程',
    `image_paths`     JSON         DEFAULT NULL                  COMMENT '影像路径JSON',
    `image_count`     INT          DEFAULT 0            NOT NULL COMMENT '影像数量',
    `status`          VARCHAR(16)  DEFAULT 'PENDING'    NOT NULL COMMENT '状态：PENDING/PROCESSING/COMPLETED/REVIEWED/FAILED',
    `department_id`   INT          DEFAULT NULL                  COMMENT '送检科室',
    `submit_user_id`  INT                               NOT NULL COMMENT '送检/录入用户ID',
    `review_user_id`  INT          DEFAULT NULL                  COMMENT '复核医生ID',
    `submit_at`       DATETIME     DEFAULT NULL                  COMMENT '送检时间',
    `review_at`       DATETIME     DEFAULT NULL                  COMMENT '复核时间',
    `remark`          VARCHAR(255) DEFAULT ''           NOT NULL COMMENT '备注',
    `created_at`      DATETIME     DEFAULT CURRENT_TIMESTAMP NOT NULL COMMENT '创建时间',
    `updated_at`      DATETIME     DEFAULT CURRENT_TIMESTAMP NOT NULL ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间',
    PRIMARY KEY (`id`),
    UNIQUE KEY `uk_screening_case_no` (`case_no`),
    KEY `ix_screening_id_card`     (`patient_id_card`),
    KEY `ix_screening_status`      (`status`),
    KEY `ix_screening_department`  (`department_id`),
    KEY `ix_screening_submit_user` (`submit_user_id`),
    CONSTRAINT `fk_screening_dept`         FOREIGN KEY (`department_id`)  REFERENCES `biz_department` (`id`) ON DELETE SET NULL,
    CONSTRAINT `fk_screening_submit_user`  FOREIGN KEY (`submit_user_id`) REFERENCES `sys_user` (`id`)       ON DELETE RESTRICT,
    CONSTRAINT `fk_screening_review_user`  FOREIGN KEY (`review_user_id`) REFERENCES `sys_user` (`id`)       ON DELETE SET NULL
) ENGINE = InnoDB
  DEFAULT CHARSET = utf8mb4
  COLLATE = utf8mb4_unicode_ci COMMENT = 'AI筛查病例表';

-- 10. AI 筛查结果表
DROP TABLE IF EXISTS `biz_screening_result`;
CREATE TABLE `biz_screening_result`
(
    `id`                INT AUTO_INCREMENT                NOT NULL COMMENT '结果ID',
    `case_id`           INT                               NOT NULL COMMENT '所属筛查病例ID',
    `eye_side`          VARCHAR(4)   DEFAULT 'OU'         NOT NULL COMMENT '眼别：OD/OS/OU',
    `model_name`        VARCHAR(64)  DEFAULT ''           NOT NULL COMMENT 'AI模型名称',
    `model_version`     VARCHAR(32)  DEFAULT ''           NOT NULL COMMENT '模型版本',
    `dr_grade`          VARCHAR(4)   DEFAULT '0'          NOT NULL COMMENT 'DR分级 0~4',
    `has_dme`           TINYINT(1)   DEFAULT 0            NOT NULL COMMENT '是否伴有DME',
    `risk_level`        VARCHAR(16)  DEFAULT 'LOW'        NOT NULL COMMENT '风险等级 LOW/MEDIUM/HIGH/URGENT',
    `risk_score`        FLOAT        DEFAULT 0            NOT NULL COMMENT '风险分0~1',
    `referral_required` TINYINT(1)   DEFAULT 0            NOT NULL COMMENT '是否建议转诊',
    `lesions`           JSON         DEFAULT NULL                  COMMENT '病变检出JSON',
    `annotations`       JSON         DEFAULT NULL                  COMMENT '标注几何JSON',
    `heatmap_path`      VARCHAR(255) DEFAULT ''           NOT NULL COMMENT '热力图URL',
    `thumbnail_path`    VARCHAR(255) DEFAULT ''           NOT NULL COMMENT '缩略图URL',
    `infer_duration_ms` INT          DEFAULT 0            NOT NULL COMMENT '推理耗时ms',
    `inferred_at`       DATETIME     DEFAULT NULL                  COMMENT 'AI完成时间',
    `doctor_diagnosis`  TEXT                              NOT NULL COMMENT '医生诊断意见',
    `doctor_grade`      VARCHAR(4)   DEFAULT ''           NOT NULL COMMENT '医生定级',
    `doctor_id`         INT          DEFAULT NULL                  COMMENT '复核医生ID',
    `doctor_at`         DATETIME     DEFAULT NULL                  COMMENT '医生复核时间',
    `created_at`        DATETIME     DEFAULT CURRENT_TIMESTAMP NOT NULL COMMENT '创建时间',
    `updated_at`        DATETIME     DEFAULT CURRENT_TIMESTAMP NOT NULL ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间',
    PRIMARY KEY (`id`),
    KEY `ix_result_case` (`case_id`),
    KEY `ix_result_dr`   (`dr_grade`),
    KEY `ix_result_risk` (`risk_level`),
    CONSTRAINT `fk_result_case`   FOREIGN KEY (`case_id`)   REFERENCES `biz_screening_case` (`id`) ON DELETE CASCADE,
    CONSTRAINT `fk_result_doctor` FOREIGN KEY (`doctor_id`) REFERENCES `sys_user` (`id`)           ON DELETE SET NULL
) ENGINE = InnoDB
  DEFAULT CHARSET = utf8mb4
  COLLATE = utf8mb4_unicode_ci COMMENT = 'AI筛查结果表';

-- 11. 实训病例表
DROP TABLE IF EXISTS `biz_training_case`;
CREATE TABLE `biz_training_case`
(
    `id`                INT AUTO_INCREMENT                NOT NULL COMMENT '实训病例ID',
    `case_no`           VARCHAR(32)                       NOT NULL COMMENT '实训病例编号',
    `title`             VARCHAR(128)                      NOT NULL COMMENT '病例标题',
    `description`       TEXT                              NOT NULL COMMENT '病例描述',
    `category`          VARCHAR(16)  DEFAULT 'DR'         NOT NULL COMMENT '病例类别 DR/AMD/GLAUCOMA/HYPERTENSION/NORMAL/OTHER',
    `difficulty`        VARCHAR(8)   DEFAULT 'EASY'       NOT NULL COMMENT '难度 EASY/MEDIUM/HARD',
    `patient_age`       INT          DEFAULT NULL                  COMMENT '患者年龄',
    `patient_gender`    VARCHAR(2)   DEFAULT 'U'          NOT NULL COMMENT '患者性别',
    `clinical_info`     TEXT                              NOT NULL COMMENT '临床信息',
    `image_paths`       JSON         DEFAULT NULL                  COMMENT '影像路径JSON',
    `gold_dr_grade`     VARCHAR(4)   DEFAULT '0'          NOT NULL COMMENT '金标准DR分级',
    `gold_diagnosis`    TEXT                              NOT NULL COMMENT '金标准诊断',
    `gold_lesions`      JSON         DEFAULT NULL                  COMMENT '金标准病变',
    `gold_annotations`  JSON         DEFAULT NULL                  COMMENT '金标准标注',
    `gold_heatmap_path` VARCHAR(255) DEFAULT ''           NOT NULL COMMENT '金标准热力图URL',
    `teaching_points`   TEXT                              NOT NULL COMMENT '教学要点',
    `pass_score`        INT          DEFAULT 60           NOT NULL COMMENT '及格分',
    `is_published`      TINYINT(1)   DEFAULT 0            NOT NULL COMMENT '是否发布',
    `creator_id`        INT                               NOT NULL COMMENT '创建教师ID',
    `created_at`        DATETIME     DEFAULT CURRENT_TIMESTAMP NOT NULL COMMENT '创建时间',
    `updated_at`        DATETIME     DEFAULT CURRENT_TIMESTAMP NOT NULL ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间',
    PRIMARY KEY (`id`),
    UNIQUE KEY `uk_training_case_no` (`case_no`),
    KEY `ix_training_case_cat`  (`category`),
    KEY `ix_training_case_diff` (`difficulty`),
    KEY `ix_training_case_pub`  (`is_published`),
    CONSTRAINT `fk_training_case_creator` FOREIGN KEY (`creator_id`) REFERENCES `sys_user` (`id`) ON DELETE RESTRICT
) ENGINE = InnoDB
  DEFAULT CHARSET = utf8mb4
  COLLATE = utf8mb4_unicode_ci COMMENT = '实训病例表';

-- 12. 学员实训记录表
DROP TABLE IF EXISTS `biz_training_record`;
CREATE TABLE `biz_training_record`
(
    `id`                  INT AUTO_INCREMENT                NOT NULL COMMENT '实训记录ID',
    `user_id`             INT                               NOT NULL COMMENT '学员用户ID',
    `case_id`             INT                               NOT NULL COMMENT '实训病例ID',
    `attempt_no`          INT          DEFAULT 1            NOT NULL COMMENT '第几次尝试',
    `status`              VARCHAR(16)  DEFAULT 'DRAFT'      NOT NULL COMMENT '状态 DRAFT/SUBMITTED/GRADED/REVIEWED',
    `student_dr_grade`    VARCHAR(4)   DEFAULT ''           NOT NULL COMMENT '学员DR分级',
    `student_diagnosis`   TEXT                              NOT NULL COMMENT '学员诊断',
    `student_lesions`     JSON         DEFAULT NULL                  COMMENT '学员病变标注',
    `student_annotations` JSON         DEFAULT NULL                  COMMENT '学员几何坐标',
    `grade_score`         FLOAT        DEFAULT 0            NOT NULL COMMENT '分级题得分',
    `annotation_score`    FLOAT        DEFAULT 0            NOT NULL COMMENT '标注题得分',
    `diagnosis_score`     FLOAT        DEFAULT 0            NOT NULL COMMENT '诊断题得分',
    `total_score`         FLOAT        DEFAULT 0            NOT NULL COMMENT '总分',
    `iou_avg`             FLOAT        DEFAULT 0            NOT NULL COMMENT '平均IoU',
    `is_passed`           TINYINT(1)   DEFAULT 0            NOT NULL COMMENT '是否通过',
    `duration_seconds`    INT          DEFAULT 0            NOT NULL COMMENT '作答用时秒',
    `started_at`          DATETIME     DEFAULT NULL                  COMMENT '开始时间',
    `submitted_at`        DATETIME     DEFAULT NULL                  COMMENT '提交时间',
    `graded_at`           DATETIME     DEFAULT NULL                  COMMENT '评分时间',
    `teacher_comment`     TEXT                              NOT NULL COMMENT '教师点评',
    `teacher_id`          INT          DEFAULT NULL                  COMMENT '点评教师ID',
    `reviewed_at`         DATETIME     DEFAULT NULL                  COMMENT '点评时间',
    `created_at`          DATETIME     DEFAULT CURRENT_TIMESTAMP NOT NULL COMMENT '创建时间',
    `updated_at`          DATETIME     DEFAULT CURRENT_TIMESTAMP NOT NULL ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间',
    PRIMARY KEY (`id`),
    KEY `ix_training_record_user`   (`user_id`),
    KEY `ix_training_record_case`   (`case_id`),
    KEY `ix_training_record_status` (`status`),
    KEY `ix_training_record_score`  (`total_score`),
    CONSTRAINT `fk_training_record_user`    FOREIGN KEY (`user_id`)    REFERENCES `sys_user` (`id`)         ON DELETE CASCADE,
    CONSTRAINT `fk_training_record_case`    FOREIGN KEY (`case_id`)    REFERENCES `biz_training_case` (`id`) ON DELETE CASCADE,
    CONSTRAINT `fk_training_record_teacher` FOREIGN KEY (`teacher_id`) REFERENCES `sys_user` (`id`)         ON DELETE SET NULL
) ENGINE = InnoDB
  DEFAULT CHARSET = utf8mb4
  COLLATE = utf8mb4_unicode_ci COMMENT = '学员实训记录表';

-- 13. 考核成绩表
DROP TABLE IF EXISTS `biz_exam_record`;
CREATE TABLE `biz_exam_record`
(
    `id`               INT AUTO_INCREMENT                NOT NULL COMMENT '考核记录ID',
    `exam_no`          VARCHAR(32)                       NOT NULL COMMENT '考核批次编号',
    `exam_title`       VARCHAR(128)                      NOT NULL COMMENT '考核标题',
    `exam_round`       VARCHAR(64)  DEFAULT ''           NOT NULL COMMENT '期次/轮次',
    `user_id`          INT                               NOT NULL COMMENT '学员ID',
    `question_records` JSON         DEFAULT NULL                  COMMENT '题目明细JSON',
    `total_questions`  INT          DEFAULT 0            NOT NULL COMMENT '总题数',
    `correct_count`    INT          DEFAULT 0            NOT NULL COMMENT '正确题数',
    `total_score`      FLOAT        DEFAULT 0            NOT NULL COMMENT '总成绩',
    `grade_score`      FLOAT        DEFAULT 0            NOT NULL COMMENT '分级题得分',
    `annotation_score` FLOAT        DEFAULT 0            NOT NULL COMMENT '标注题得分',
    `diagnosis_score`  FLOAT        DEFAULT 0            NOT NULL COMMENT '诊断题得分',
    `pass_score`       INT          DEFAULT 60           NOT NULL COMMENT '及格分',
    `is_passed`        TINYINT(1)   DEFAULT 0            NOT NULL COMMENT '是否合格',
    `rank`             INT          DEFAULT NULL                  COMMENT '同批次排名',
    `status`           VARCHAR(16)  DEFAULT 'NOT_STARTED' NOT NULL COMMENT '状态 NOT_STARTED/IN_PROGRESS/SUBMITTED/GRADED/EXPIRED',
    `duration_seconds` INT          DEFAULT 0            NOT NULL COMMENT '作答用时秒',
    `started_at`       DATETIME     DEFAULT NULL                  COMMENT '开考时间',
    `submitted_at`     DATETIME     DEFAULT NULL                  COMMENT '交卷时间',
    `graded_at`        DATETIME     DEFAULT NULL                  COMMENT '批阅时间',
    `examiner_id`      INT          DEFAULT NULL                  COMMENT '主考教师ID',
    `teacher_comment`  TEXT                              NOT NULL COMMENT '教师总评',
    `created_at`       DATETIME     DEFAULT CURRENT_TIMESTAMP NOT NULL COMMENT '创建时间',
    `updated_at`       DATETIME     DEFAULT CURRENT_TIMESTAMP NOT NULL ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间',
    PRIMARY KEY (`id`),
    KEY `ix_exam_record_no`     (`exam_no`),
    KEY `ix_exam_record_user`   (`user_id`),
    KEY `ix_exam_record_status` (`status`),
    KEY `ix_exam_record_score`  (`total_score`),
    CONSTRAINT `fk_exam_user`     FOREIGN KEY (`user_id`)     REFERENCES `sys_user` (`id`) ON DELETE CASCADE,
    CONSTRAINT `fk_exam_examiner` FOREIGN KEY (`examiner_id`) REFERENCES `sys_user` (`id`) ON DELETE SET NULL
) ENGINE = InnoDB
  DEFAULT CHARSET = utf8mb4
  COLLATE = utf8mb4_unicode_ci COMMENT = '考核成绩表';

-- 14. 默认科室种子数据
INSERT INTO `biz_department` (`code`, `name`, `short_name`, `sort_order`, `remark`) VALUES
    ('OPHTH', '眼科',       '眼科',     10, '眼科住院/门诊'),
    ('ENDO',  '内分泌科',   '内分泌',   20, '糖尿病慢病管理'),
    ('INFO',  '信息中心',   '信息中心', 90, '系统管理与运维')
ON DUPLICATE KEY UPDATE `name` = VALUES(`name`), `remark` = VALUES(`remark`);

