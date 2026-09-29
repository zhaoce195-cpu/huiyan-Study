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
@TableName("biz_exam_paper")
public class ExamPaper extends BaseEntity {

    private String title;
    private Integer teacherId;
    private String status;
    private Integer durationMinutes;
    private Integer passScore;
    private Boolean allowBack;
    private String pickMode;
    private String category;
    private String difficulty;
    private String caseIds; // JSON 字符串 [1, 2, 3]

    @JsonFormat(pattern = "yyyy-MM-dd HH:mm:ss")
    private LocalDateTime openedAt;

    @JsonFormat(pattern = "yyyy-MM-dd HH:mm:ss")
    private LocalDateTime closedAt;

    @TableField(exist = false)
    private String teacherName;
}
