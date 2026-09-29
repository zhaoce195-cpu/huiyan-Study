package com.huiyan.entity;

import com.baomidou.mybatisplus.annotation.TableField;
import com.baomidou.mybatisplus.annotation.TableName;
import com.fasterxml.jackson.annotation.JsonFormat;
import lombok.AllArgsConstructor;
import lombok.Builder;
import lombok.Data;
import lombok.EqualsAndHashCode;
import lombok.NoArgsConstructor;

import java.time.LocalDate;
import java.time.LocalDateTime;

@Data
@Builder
@NoArgsConstructor
@AllArgsConstructor
@EqualsAndHashCode(callSuper = true)
@TableName("biz_screening_case")
public class ScreeningCase extends BaseEntity {

    private String caseNo;
    private String caseSn;
    private String patientName;
    private String patientIdCard;
    private String gender;
    private Integer age;

    @JsonFormat(pattern = "yyyy-MM-dd")
    private LocalDate birthDate;

    private String phone;
    private String patientPhone;
    private String chiefComplaint;
    private String medicalHistory;
    private Integer diabetesYears;
    private String imagePaths; // JSON 字符串: {"OD": [...], "OS": [...]}
    private Integer imageCount;
    private String status;
    private String reportStatus;
    private String reportPdfPath;
    private Integer patientUserId;
    private Integer departmentId;
    private Integer submitUserId;
    private Integer reviewUserId;

    @JsonFormat(pattern = "yyyy-MM-dd HH:mm:ss")
    private LocalDateTime submitAt;

    @JsonFormat(pattern = "yyyy-MM-dd HH:mm:ss")
    private LocalDateTime reviewAt;

    private String remark;

    @TableField(exist = false)
    private String departmentName;

    @TableField(exist = false)
    private String submitUserName;

    @TableField(exist = false)
    private String reviewUserName;
}
