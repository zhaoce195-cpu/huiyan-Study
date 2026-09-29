package com.huiyan.dto.user;

import com.fasterxml.jackson.annotation.JsonFormat;
import com.fasterxml.jackson.annotation.JsonProperty;
import lombok.AllArgsConstructor;
import lombok.Builder;
import lombok.Data;
import lombok.NoArgsConstructor;

import java.io.Serializable;
import java.time.LocalDateTime;

public class UserDTO {

    @Data
    @NoArgsConstructor
    @AllArgsConstructor
    public static class LoginRequest implements Serializable {
        private String username;
        private String password;
        private Boolean remember;
    }

    @Data
    @Builder
    @NoArgsConstructor
    @AllArgsConstructor
    public static class LoginResponse implements Serializable {
        private String token;

        @JsonProperty("token_type")
        @Builder.Default
        private String tokenType = "Bearer";

        @JsonProperty("expires_at")
        @JsonFormat(pattern = "yyyy-MM-dd HH:mm:ss")
        private LocalDateTime expiresAt;

        @JsonProperty("user_info")
        private UserInfo userInfo;

        @JsonProperty("userInfo")
        public UserInfo getUserInfoCamel() {
            return userInfo;
        }
    }

    @Data
    @Builder
    @NoArgsConstructor
    @AllArgsConstructor
    public static class UserInfo implements Serializable {
        private Integer id;
        private String username;

        @JsonProperty("real_name")
        private String realName;

        public String getName() {
            return realName;
        }

        private String phone;
        private String email;
        private String department;
        private String title;
        private String avatar;
        private String role;

        @JsonProperty("role_name")
        private String roleName;

        @JsonProperty("user_type")
        private String userType;

        @JsonProperty("is_active")
        private Boolean isActive;

        @JsonProperty("must_change_password")
        private Boolean mustChangePassword;

        @JsonProperty("last_login_at")
        @JsonFormat(pattern = "yyyy-MM-dd HH:mm:ss")
        private LocalDateTime lastLoginAt;

        @JsonProperty("last_login_ip")
        private String lastLoginIp;

        @JsonProperty("created_at")
        @JsonFormat(pattern = "yyyy-MM-dd HH:mm:ss")
        private LocalDateTime createdAt;

        @JsonProperty("updated_at")
        @JsonFormat(pattern = "yyyy-MM-dd HH:mm:ss")
        private LocalDateTime updatedAt;
    }

    @Data
    @NoArgsConstructor
    @AllArgsConstructor
    public static class ChangePasswordRequest implements Serializable {
        @JsonProperty("old_password")
        private String oldPassword;

        @JsonProperty("new_password")
        private String newPassword;

        @JsonProperty("confirm_password")
        private String confirmPassword;
    }

    @Data
    @NoArgsConstructor
    @AllArgsConstructor
    public static class UpdateProfileRequest implements Serializable {
        @JsonProperty("real_name")
        private String realName;
        private String phone;
        private String email;
        private String department;
        private String title;
    }

    @Data
    @NoArgsConstructor
    @AllArgsConstructor
    public static class WechatLoginRequest implements Serializable {
        private String code;
    }

    @Data
    @NoArgsConstructor
    @AllArgsConstructor
    public static class WechatBindRequest implements Serializable {
        private String ticket;
        private String username;
        private String password;
    }
}
