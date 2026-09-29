package com.huiyan.dto.screening;

import com.fasterxml.jackson.annotation.JsonFormat;
import com.fasterxml.jackson.annotation.JsonProperty;
import lombok.AllArgsConstructor;
import lombok.Builder;
import lombok.Data;
import lombok.NoArgsConstructor;

import java.io.Serializable;
import java.time.LocalDateTime;
import java.util.List;

public class ScreeningDTO {

    @Data
    @Builder
    @NoArgsConstructor
    @AllArgsConstructor
    public static class ScreeningTaskOut implements Serializable {
        private String id; // case_no
        private Integer caseId;
        private String patientId;
        private String patientName;
        private String patientPhone;
        private String eye;
        private Integer age;
        private String gender;
        private String status;
        private String risk;
        private String dr;
        private Double confidence;
        private String createdAt;
        private String fileName;
        private String fileUrl;
        private String thumbUrl;
        private String hospital;
        private String doctor;
        private String remark;
        private Boolean patientBound;
        private Boolean confirmed;
        private String reviewer;
        private String reviewedAt;
        private String diagnosisType;
        private String diagnosisSummary;
        private String heatmapUrl;
    }

    @Data
    @NoArgsConstructor
    @AllArgsConstructor
    public static class PatientMetaForm implements Serializable {
        private String patientId;
        private String patientName;
        private String gender;
        private Integer age;
        private String eye;
        private String hospital;
        private String doctor;
        private String remark;
        private String patientPhone;
    }

    @Data
    @Builder
    @NoArgsConstructor
    @AllArgsConstructor
    public static class UploadFundusResult implements Serializable {
        private String taskId;
        private String fileUrl;
        private String fileName;
        private Long fileSize;
        @Builder.Default
        private Boolean queued = true;
    }

    @Data
    @Builder
    @NoArgsConstructor
    @AllArgsConstructor
    public static class ScreeningStatsOut implements Serializable {
        private int total;
        private int red;
        private int yellow;
        private int green;
        private int pending;
        private int failed;
        private int todayCount;
        private int weekCount;
    }

    @Data
    @Builder
    @NoArgsConstructor
    @AllArgsConstructor
    public static class ScreeningReportOut implements Serializable {
        private String taskId;
        private Integer caseId;
        private String patientId;
        private String patientName;
        private String gender;
        private Integer age;
        private String eye;
        private String hospital;
        private String doctor;
        private String remark;
        private String dr;
        private String risk;
        private Double confidence;
        private String fileUrl;
        private String heatmapUrl;
        private String doctorDiagnosis;
        private String createdAt;
        private String confirmedReportUrl;
        private Boolean confirmed;
    }

    @Data
    @NoArgsConstructor
    @AllArgsConstructor
    public static class ReanalyzeParams implements Serializable {
        private String taskId;
        private Boolean force;
    }

    @Data
    @NoArgsConstructor
    @AllArgsConstructor
    public static class ReferParams implements Serializable {
        private String taskId;
        private String hospital;
        private String department;
        private String notes;
    }

    @Data
    @NoArgsConstructor
    @AllArgsConstructor
    public static class CaseUpdateParams implements Serializable {
        private String patientName;
        private String patientIdCard;
        private String gender;
        private Integer age;
        private String phone;
        private String chiefComplaint;
        private String medicalHistory;
        private Integer diabetesYears;
        private String remark;
    }
}
