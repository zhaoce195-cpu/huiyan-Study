package com.huiyan.entity;

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
@TableName("biz_training_record")
public class TrainingRecord extends BaseEntity {

    private Integer userId;
    private Integer caseId;
    private Integer attemptNo;
    private String status;

    private String studentDrGrade;
    private String studentDiagnosis;
    private String studentLesions;
    private String studentAnnotations;

    private Double gradeScore;
    private Double annotationScore;
    private Double diagnosisScore;
    private Double totalScore;
    private Double iouAvg;
    private Integer isPassed;
    private Integer durationSeconds;

    @JsonFormat(pattern = "yyyy-MM-dd HH:mm:ss")
    private LocalDateTime startedAt;

    @JsonFormat(pattern = "yyyy-MM-dd HH:mm:ss")
    private LocalDateTime submittedAt;

    @JsonFormat(pattern = "yyyy-MM-dd HH:mm:ss")
    private LocalDateTime gradedAt;

    private String teacherComment;
    private Integer teacherId;

    @JsonFormat(pattern = "yyyy-MM-dd HH:mm:ss")
    private LocalDateTime reviewedAt;
}
