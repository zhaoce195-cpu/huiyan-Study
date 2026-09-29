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
@TableName("biz_lti_platform")
public class LtiPlatform extends BaseEntity {

    private String name;
    private String issuer;
    private String clientId;
    private String deploymentId;
    private String authLoginUrl;
    private String authTokenUrl;
    private String keySetUrl;
    private Boolean autoProvision;
    private Boolean enabled;
    private String note;
}
