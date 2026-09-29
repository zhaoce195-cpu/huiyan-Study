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
@TableName("biz_teaching_share")
public class TeachingShare extends BaseEntity {

    private String shareType;
    private String sourceType;
    private Integer sourceCaseId;
    private Integer teachingCaseId;
    private String desensitizedData; // JSON 字符串
    private String shareScope;
    private String scopeValue;
    private String audienceIds; // JSON 字符串
    private Integer expireHours;

    @JsonFormat(pattern = "yyyy-MM-dd HH:mm:ss")
    private LocalDateTime expiredAt;

    private Boolean answersRevealed;
    private String status;
    private Integer reviewerId;
    private String reviewComment;

    @JsonFormat(pattern = "yyyy-MM-dd HH:mm:ss")
    private LocalDateTime reviewedAt;

    private Integer teacherId;

    @TableField(exist = false)
    private String teacherName;

    @TableField(exist = false)
    private String reviewerName;

    @TableField(exist = false)
    private String caseTitle;
}
