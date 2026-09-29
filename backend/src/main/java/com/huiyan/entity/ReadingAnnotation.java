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
@TableName("biz_reading_annotation")
public class ReadingAnnotation extends BaseEntity {

    private Integer caseId;
    private Integer userId;
    private Integer imageIndex;
    private String imageUrl;
    private String viewport; // JSON 字符串
    private String annotations; // JSON 字符串
    private String measurements; // JSON 字符串
    private String layers; // JSON 字符串
    private String status;
    private String recordKind;
    private String diagnosis; // JSON 字符串
    private String note;
    private String submitRequestId;
    private String reviewComment;
    private Integer reviewerId;

    @TableField(exist = false)
    private String caseNo;

    @TableField(exist = false)
    private String caseTitle;

    @TableField(exist = false)
    private String userName;

    @TableField(exist = false)
    private String reviewerName;
}
