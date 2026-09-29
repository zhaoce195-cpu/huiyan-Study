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
@TableName("biz_training_case")
public class TrainingCase extends BaseEntity {

    private String caseNo;
    private String caseSn;
    private String title;
    private String description;
    private String category;
    private String difficulty;
    private String patientName;
    private Integer patientAge;
    private String patientGender;
    private String patientPhone;
    private String subjectNo;
    private String examOn;
    private String clinicalInfo;
    private String imagePaths; // JSON 字符串: {"OD": [...], "OS": [...]}

    // 金标准
    private String goldDrGrade;
    private String goldDiagnosis;
    private String goldLesions; // JSON 字符串
    private String goldAnnotations; // JSON 字符串
    private String goldHeatmapPath;
    private String teachingPoints;

    private Integer passScore;
    private Boolean isPublished;
    private Boolean isTrainCase;
    private String archiveStatus;
    private Integer creatorId;

    @TableField(exist = false)
    private String creatorName;
}
