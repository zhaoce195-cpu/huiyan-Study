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
@TableName("biz_student_application")
public class StudentApplication extends BaseEntity {

    private String realName;
    private String phone;
    private String department;
    private String reason;
    private String status;
    private Integer reviewerId;
    private String reviewComment;

    @JsonFormat(pattern = "yyyy-MM-dd HH:mm:ss")
    private LocalDateTime reviewedAt;

    private Integer createdUserId;
    private String notifySms;

    @TableField(exist = false)
    private String reviewerName;

    @TableField(exist = false)
    private String createdUserName;

    @TableField(exist = false)
    private String accountUsername;

    @TableField(exist = false)
    private String tempPassword;
}
