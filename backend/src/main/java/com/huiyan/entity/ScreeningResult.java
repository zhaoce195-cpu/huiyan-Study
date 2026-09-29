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
@TableName("biz_screening_result")
public class ScreeningResult extends BaseEntity {

    private Integer caseId;
    private String eyeSide;
    private String modelName;
    private String modelVersion;
    private String drGrade;
    private Integer hasDme;
    private String riskLevel;
    private Double riskScore;
    private Integer referralRequired;
    private String lesions; // JSON 字符串
    private String annotations; // JSON 字符串
    private String heatmapPath;
    private String thumbnailPath;
    private Integer inferDurationMs;

    @JsonFormat(pattern = "yyyy-MM-dd HH:mm:ss")
    private LocalDateTime inferredAt;

    private String doctorDiagnosis;
    private String doctorGrade;
    private Integer doctorId;

    @JsonFormat(pattern = "yyyy-MM-dd HH:mm:ss")
    private LocalDateTime doctorAt;

    @TableField(exist = false)
    private String doctorName;
}
