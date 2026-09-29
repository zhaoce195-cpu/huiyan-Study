package com.huiyan.dto.practice;

import com.fasterxml.jackson.annotation.JsonFormat;
import lombok.AllArgsConstructor;
import lombok.Builder;
import lombok.Data;
import lombok.NoArgsConstructor;

import java.io.Serializable;
import java.time.LocalDateTime;
import java.util.List;
import java.util.Map;

public class PracticeDTO {

    @Data
    @NoArgsConstructor
    @AllArgsConstructor
    public static class PracticeStartParams implements Serializable {
        private Integer caseId;
        private String mode; // RANDOM / SELECTED
    }

    @Data
    @NoArgsConstructor
    @AllArgsConstructor
    public static class PracticeSubmitParams implements Serializable {
        private Integer recordId;
        private String studentDrGrade;
        private String studentDiagnosis;
        private Object diagnosis; // 结构化作答
        private List<Map<String, Object>> annotations;
        private List<Map<String, Object>> measurements;
        private Map<String, Object> viewport;
        private Integer durationSeconds;
        private String requestId;
        private List<Map<String, Object>> textAnswers;
    }

    @Data
    @Builder
    @NoArgsConstructor
    @AllArgsConstructor
    public static class PracticeOut implements Serializable {
        private Integer id;
        private Integer userId;
        private String userName;
        private Integer caseId;
        private String caseNo;
        private String caseTitle;
        private String caseCategory;
        private String caseDifficulty;
        private String caseDrGradeText;
        private List<String> images;
        private String mode;
        private String status;
        private String studentDrGrade;
        private String studentDiagnosis;
        private Object studentDiagnosisForm;
        private String scoringMode;
        private Integer scoreRuleVersion;
        private Object studentAnnotations;
        private Object studentMeasurements;
        private Object viewport;

        private Double scoreTotal;
        private Double scoreGrade;
        private Double scoreAnnotation;
        private Boolean annotationApplicable;
        private Double scoreDiagnosis;
        private Double scoreText;
        private Double iouAvg;
        private Double accuracy;
        private Boolean gradeMatch;
        private Boolean isPassed;
        private Integer missedCount;
        private Integer falsePositiveCount;
        private Object errorPoints;
        private String suggestion;

        @JsonFormat(pattern = "yyyy-MM-dd HH:mm:ss")
        private LocalDateTime startedAt;

        @JsonFormat(pattern = "yyyy-MM-dd HH:mm:ss")
        private LocalDateTime submittedAt;

        private Integer durationSeconds;
        private String teacherComment;
        private Integer teacherId;
        private String teacherName;

        @JsonFormat(pattern = "yyyy-MM-dd HH:mm:ss")
        private LocalDateTime createdAt;
    }

    @Data
    @NoArgsConstructor
    @AllArgsConstructor
    public static class PracticeReviewParams implements Serializable {
        private String comment;
    }

    @Data
    @Builder
    @NoArgsConstructor
    @AllArgsConstructor
    public static class PracticeStatsOut implements Serializable {
        private int totalCount;
        private int passedCount;
        private double passRate;
        private double avgScore;
        private double maxScore;
        private double avgIou;
        private int totalStudyMinutes;
    }
}
