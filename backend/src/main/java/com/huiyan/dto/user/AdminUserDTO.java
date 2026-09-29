package com.huiyan.dto.user;

import com.fasterxml.jackson.annotation.JsonFormat;
import lombok.AllArgsConstructor;
import lombok.Builder;
import lombok.Data;
import lombok.NoArgsConstructor;

import java.io.Serializable;
import java.time.LocalDateTime;

public class AdminUserDTO {

    @Data
    @Builder
    @NoArgsConstructor
    @AllArgsConstructor
    public static class AdminUserItem implements Serializable {
        private Integer id;
        private String username;
        private String realName;
        private String role;
        private String roleName;
        private String department;
        private String hospitalName;
        private Boolean isActive;
        private Boolean mustChangePassword;

        @JsonFormat(pattern = "yyyy-MM-dd HH:mm:ss")
        private LocalDateTime lastLoginAt;

        @JsonFormat(pattern = "yyyy-MM-dd HH:mm:ss")
        private LocalDateTime createdAt;
    }

    @Data
    @NoArgsConstructor
    @AllArgsConstructor
    public static class AdminUserCreate implements Serializable {
        private String username;
        private String password;
        private String realName;
        private String role;
        private String department;
        private Integer departmentId;
        private String title;
        private String phone;
        private String email;
    }

    @Data
    @NoArgsConstructor
    @AllArgsConstructor
    public static class AdminUserUpdate implements Serializable {
        private String realName;
        private String role;
        private String department;
        private Integer departmentId;
        private String title;
        private String phone;
        private String email;
        private Boolean isActive;
        private Boolean mustChangePassword;
    }
}
