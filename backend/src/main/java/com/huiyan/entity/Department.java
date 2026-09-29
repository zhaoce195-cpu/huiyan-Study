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
@TableName("biz_department")
public class Department extends BaseEntity {

    private Integer hospitalId;
    private String code;
    private String name;
    private String shortName;
    private String leader;
    private String phone;
    private Integer sortOrder;
    private Boolean isActive;
    private String remark;
}
