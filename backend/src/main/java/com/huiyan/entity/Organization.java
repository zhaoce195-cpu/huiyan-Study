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
@TableName("biz_organization")
public class Organization extends BaseEntity {

    private String name;
    private String code;
    private String category;
    private String address;
    private String contact;
    private String phone;
    private String description;
    private Boolean isActive;
}
