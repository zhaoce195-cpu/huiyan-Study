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
@TableName("biz_organization_application")
public class OrganizationApplication extends BaseEntity {

    private Integer applicantId;
    private Integer organizationId;
    private String reason;
    private String status;
    private Integer reviewerId;
    private String reviewComment;

    @JsonFormat(pattern = "yyyy-MM-dd HH:mm:ss")
    private LocalDateTime reviewedAt;

    @TableField(exist = false)
    private String applicantName;

    @TableField(exist = false)
    private String applicantPhone;

    @TableField(exist = false)
    private String organizationName;

    @TableField(exist = false)
    private String reviewerName;
}
