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
@TableName("biz_lti_launch")
public class LtiLaunch extends BaseEntity {

    private Integer platformId;
    private Integer userId;
    private String ltiUserId;
    private String contextId;
    private String resourceLinkId;
    private String lineitemUrl;
    private String scope;
    private String roles;
}
