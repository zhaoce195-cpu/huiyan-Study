package com.huiyan.dto.diagnosis;

import lombok.AllArgsConstructor;
import lombok.Builder;
import lombok.Data;
import lombok.NoArgsConstructor;

import java.util.Map;

public class DiagnosisDTO {

    @Data
    @Builder
    @NoArgsConstructor
    @AllArgsConstructor
    public static class MaDiagnosisResult {
        private int maCount;
        private String overlayUrl;
        private String heatmapUrl;
        private double inferenceTime;
    }

    @Data
    @Builder
    @NoArgsConstructor
    @AllArgsConstructor
    public static class DrEyeResult {
        private int grade;
        private String gradeName;
        private String imageUrl;
        private String heatmapUrl;
    }

    @Data
    @Builder
    @NoArgsConstructor
    @AllArgsConstructor
    public static class DrDiagnosisResult {
        private int overallGrade;
        private String overallGradeName;
        private DrEyeResult left;
        private DrEyeResult right;
        private double inferenceTime;
    }

    @Data
    @Builder
    @NoArgsConstructor
    @AllArgsConstructor
    public static class ComprehensiveDiagnosisResult {
        private int overallGrade;
        private int maCount;
        private String maOverlayUrl;
        private String drHeatmapUrl;
        private String summary;
        private double inferenceTime;
    }

    @Data
    @Builder
    @NoArgsConstructor
    @AllArgsConstructor
    public static class DiagnosisOut {
        private String taskId;
        private Integer caseId;
        private String caseSn;
        private String patientName;
        private String diagnosisType;
        private String riskLevel;
        private String primaryImageUrl;
        private MaDiagnosisResult ma;
        private DrDiagnosisResult dr;
        private ComprehensiveDiagnosisResult comprehensive;
        private Map<String, Object> raw;
    }
}
