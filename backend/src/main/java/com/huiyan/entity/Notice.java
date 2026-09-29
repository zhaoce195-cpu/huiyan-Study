package com.huiyan.entity;

import com.baomidou.mybatisplus.annotation.TableField;
import com.baomidou.mybatisplus.annotation.TableName;
import com.fasterxml.jackson.annotation.JsonFormat;
import lombok.AllArgsConstructor;
import lombok.Builder;
import lombok.Data;
import lombok.EqualsAndHashCode;
import lombok.NoArgsConstructor;

import java.time.LocalDateTime;

@Data
@Builder
@NoArgsConstructor
@AllArgsConstructor
@EqualsAndHashCode(callSuper = true)
@TableName("biz_notice")
public class Notice extends BaseEntity {

    private String title;
    private String summary;
    private String content;
    private String coverUrl;
    private String noticeType;
    private String status;
    private String visibleRoles;
    private Boolean isTop;
    private Integer publisherId;

    @JsonFormat(pattern = "yyyy-MM-dd HH:mm:ss")
    private LocalDateTime publishAt;

    @JsonFormat(pattern = "yyyy-MM-dd HH:mm:ss")
    private LocalDateTime expireAt;

    private Integer viewCount;

    @TableField(exist = false)
    private String publisherName;

    @TableField(exist = false)
    private Boolean isRead;
}
