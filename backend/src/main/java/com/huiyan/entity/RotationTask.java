package com.huiyan.entity;

import com.baomidou.mybatisplus.annotation.TableField;
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
@TableName("biz_rotation_task")
public class RotationTask extends BaseEntity {

    private Integer rotationId;
    private String kind;
    private Integer caseId;
    private Integer resourceId;
    private String title;
    private String summary;
    private Integer passScore;
    private String dueOn;
    private Integer sortOrder;
    private String tier;
    private String scope;
    private String scopeValue;

    @TableField(exist = false)
    private Boolean isDone;
}
