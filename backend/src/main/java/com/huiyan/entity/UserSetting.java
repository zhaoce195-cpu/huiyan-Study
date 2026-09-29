package com.huiyan.entity;

import com.baomidou.mybatisplus.annotation.TableName;
import lombok.AllArgsConstructor;
import lombok.Builder;
import lombok.Data;
import lombok.EqualsAndHashCode;
import lombok.NoArgsConstructor;

@Data
@Builder
@NoArgsConstructor
@AllArgsConstructor
@EqualsAndHashCode(callSuper = true)
@TableName("sys_user_setting")
public class UserSetting extends BaseEntity {

    private Integer userId;
    private String theme;
    private String fontSize;
    private String language;
    private Boolean notifyMessage;
    private Boolean notifyEmail;
    private Boolean notifySms;
    private Boolean notifySound;
}
