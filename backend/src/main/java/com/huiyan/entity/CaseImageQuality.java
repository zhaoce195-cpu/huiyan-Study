package com.huiyan.entity;

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
@TableName("biz_case_image_quality")
public class CaseImageQuality extends BaseEntity {

    private Integer caseImageId;
    private String quality;
    private Double confidence;
    private String probabilities; // JSON 字符串
    private String modelName;
    private Integer inferDurationMs;

    @JsonFormat(pattern = "yyyy-MM-dd HH:mm:ss")
    private LocalDateTime checkedAt;

    private String errorMsg;
}
