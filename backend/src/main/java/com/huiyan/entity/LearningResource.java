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
@TableName("biz_learning_resource")
public class LearningResource extends BaseEntity {

    private String title;
    private String summary;
    private String content;
    private String resourceType;
    private String tags;
    private String coverUrl;
    private String fileUrl;
    private String fileType;
    private Integer caseId;
    private String status;
    private Integer publisherId;
    private Integer viewCount;
    private Integer favoriteCount;

    @TableField(exist = false)
    private String publisherName;

    @TableField(exist = false)
    private String resourceTypeText;

    @TableField(exist = false)
    private Boolean isFavorited;

    @TableField(exist = false)
    private String favoriteLabel;
}
