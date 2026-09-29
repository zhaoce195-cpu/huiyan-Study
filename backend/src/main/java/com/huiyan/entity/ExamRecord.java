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
@TableName("biz_exam_record")
public class ExamRecord extends BaseEntity {

    private String examNo;
    private String examTitle;
    private String examRound;
    private Integer userId;
    private String questionRecords; // JSON 字符串
    private Integer totalQuestions;
    private Integer correctCount;

    private Double totalScore;
    private Double gradeScore;
    private Double annotationScore;
    private Double diagnosisScore;
    private Integer passScore;
    private Boolean isPassed;
    private Integer rank;
    private String status;
    private Integer durationSeconds;

    @JsonFormat(pattern = "yyyy-MM-dd HH:mm:ss")
    private LocalDateTime startedAt;

    @JsonFormat(pattern = "yyyy-MM-dd HH:mm:ss")
    private LocalDateTime submittedAt;

    @JsonFormat(pattern = "yyyy-MM-dd HH:mm:ss")
    private LocalDateTime gradedAt;

    private Integer examinerId;
    private String teacherComment;

    @TableField(exist = false)
    private String studentName;

    @TableField(exist = false)
    private String examinerName;
}
