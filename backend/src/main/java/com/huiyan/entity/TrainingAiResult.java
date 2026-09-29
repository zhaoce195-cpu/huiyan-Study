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
@TableName("biz_training_ai_result")
public class TrainingAiResult extends BaseEntity {

    private Integer caseId;
    private String leftGrade;
    private String rightGrade;
    private String overallGrade;
    private String leftHeatmapPath;
    private String rightHeatmapPath;
    private String modelName;
    private Integer inferDurationMs;
    private String raw; // JSON 字符串
    private Double riskScore;
}
