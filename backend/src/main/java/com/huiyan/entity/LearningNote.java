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
@TableName("biz_learning_note")
public class LearningNote extends BaseEntity {

    private Integer userId;
    private String title;
    private String content;
    private String tags;
    private Integer caseId;
    private Integer imageIndex;
    private String imageUrl;
    private Integer resourceId;

    @TableField(exist = false)
    private String userName;

    @TableField(exist = false)
    private String caseNo;

    @TableField(exist = false)
    private String caseTitle;

    @TableField(exist = false)
    private String resourceTitle;
}
