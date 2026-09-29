package com.huiyan.entity;

import com.baomidou.mybatisplus.annotation.TableField;
import com.baomidou.mybatisplus.annotation.TableName;
import com.fasterxml.jackson.annotation.JsonFormat;
import lombok.AllArgsConstructor;
import lombok.Builder;
import lombok.Data;
import lombok.EqualsAndHashCode;
import lombok.NoArgsConstructor;

import java.time.LocalDateTime;

@Data
@Builder
@NoArgsConstructor
@AllArgsConstructor
@EqualsAndHashCode(callSuper = true)
@TableName("biz_practice_session")
public class PracticeSession extends BaseEntity {

    private Integer userId;
    private Integer caseId;
    private String mode;
    private String attemptKind;
    private String examGroupId;
    private Integer examIndex;
    private Integer examTotal;
    private Integer examPaperId;
    private Integer hintStep;
    private String status;

    private String studentDrGrade;
    private String studentDiagnosis;
    private String studentDiagnosisForm; // JSON 字符串
    private String scoringMode;
    private Integer scoreRuleVersion;
    private String submitRequestId;
    private String studentAnnotations; // JSON 字符串
    private String studentMeasurements; // JSON 字符串
    private String viewportSnapshot; // JSON 字符串

    private Double scoreTotal;
    private Double scoreGrade;
    private Double scoreAnnotation;
    private Double scoreDiagnosis;
    private Double scoreText;
    private String textQuestionIds; // JSON 字符串
    private String textAnswers; // JSON 字符串

    private Double iouAvg;
    private Double accuracy;
    private Integer missedCount;
    private Integer falsePositiveCount;
    private Integer gradeMatch;
    private Integer isPassed;
    private String errorPoints; // JSON 字符串
    private String suggestion;

    @JsonFormat(pattern = "yyyy-MM-dd HH:mm:ss")
    private LocalDateTime startedAt;

    @JsonFormat(pattern = "yyyy-MM-dd HH:mm:ss")
    private LocalDateTime submittedAt;

    private Integer durationSeconds;
    private String teacherComment;
    private Integer teacherId;

    @TableField(exist = false)
    private String caseNo;

    @TableField(exist = false)
    private String caseTitle;

    @TableField(exist = false)
    private String userName;

    @TableField(exist = false)
    private String teacherName;
}
