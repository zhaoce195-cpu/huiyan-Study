package com.huiyan.entity;

import com.baomidou.mybatisplus.annotation.TableField;
import com.baomidou.mybatisplus.annotation.TableName;
import com.fasterxml.jackson.annotation.JsonFormat;
import com.fasterxml.jackson.annotation.JsonIgnore;
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
@TableName("sys_user")
public class User extends BaseEntity {

    private String username;

    @JsonIgnore
    private String passwordHash;

    private String realName;
    private String phone;
    private String email;
    private String department;
    private Integer departmentId;
    private String title;
    private String studyYear;
    private String rotationBatch;
    private String mentorGroup;
    private Integer groupEditorId;

    @JsonFormat(pattern = "yyyy-MM-dd HH:mm:ss")
    private LocalDateTime groupEditedAt;

    private String avatar;
    private String wxOpenid;
    private String userType;
    private Integer roleId;
    private Boolean isActive;
    private Boolean mustChangePassword;

    @JsonFormat(pattern = "yyyy-MM-dd HH:mm:ss")
    private LocalDateTime lastLoginAt;

    private String lastLoginIp;

    // 非表字段，业务关联填充
    @TableField(exist = false)
    private String roleCode;

    @TableField(exist = false)
    private String roleName;

    @TableField(exist = false)
    private String hospitalName;
}
