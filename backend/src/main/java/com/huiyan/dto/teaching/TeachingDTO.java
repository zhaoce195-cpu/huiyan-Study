package com.huiyan.dto.teaching;

import com.fasterxml.jackson.annotation.JsonFormat;
import lombok.AllArgsConstructor;
import lombok.Builder;
import lombok.Data;
import lombok.NoArgsConstructor;

import java.io.Serializable;
import java.time.LocalDateTime;
import java.util.List;
import java.util.Map;

public class TeachingDTO {

    @Data
    @Builder
    @NoArgsConstructor
    @AllArgsConstructor
    public static class StudentCaseOut implements Serializable {
        private Integer id;
        private String shareType;
        private String title;
        private String description;
        private Integer patientAge;
        private String patientGender;
        private String clinicalInfo;
        private String category;
        private String difficulty;
        private Map<String, Object> imagePaths;
        private Integer imageCount;
        private String teacherName;
        private String teachingPoints;
        private String goldDiagnosis;
        private String goldGradeText;
        private String categoryText;
        private String difficultyText;
        private List<Map<String, Object>> lesions;
        private List<Object> annotations;
        private String lesionMaskUrl;
        private Boolean answersRevealed;

        @JsonFormat(pattern = "yyyy-MM-dd HH:mm:ss")
        private LocalDateTime expiredAt;

        private Integer teachingCaseId;
    }

    @Data
    @Builder
    @NoArgsConstructor
    @AllArgsConstructor
    public static class TeachingShareOut implements Serializable {
        private Integer id;
        private String shareType;
        private String sourceType;
        private Integer sourceCaseId;
        private Integer teachingCaseId;
        private Map<String, Object> desensitizedData;
        private String shareScope;
        private String scopeValue;
        private List<Integer> audienceIds;
        private String audienceLabel;
        private Integer expireHours;

        @JsonFormat(pattern = "yyyy-MM-dd HH:mm:ss")
        private LocalDateTime expiredAt;

        private String status;
        private String reviewComment;

        @JsonFormat(pattern = "yyyy-MM-dd HH:mm:ss")
        private LocalDateTime reviewedAt;

        private String reviewerName;
        private Integer teacherId;
        private String teacherName;
        private Boolean answersRevealed;

        @JsonFormat(pattern = "yyyy-MM-dd HH:mm:ss")
        private LocalDateTime createdAt;

        @JsonFormat(pattern = "yyyy-MM-dd HH:mm:ss")
        private LocalDateTime updatedAt;
    }

    @Data
    @Builder
    @NoArgsConstructor
    @AllArgsConstructor
    public static class ShareStudentOut implements Serializable {
        private Integer id;
        private String name;
        private String studyYear;
        private String rotationBatch;
        private String mentorGroup;
    }

    @Data
    @Builder
    @NoArgsConstructor
    @AllArgsConstructor
    public static class ShareTargetsOut implements Serializable {
        private List<String> years;
        private List<String> batches;
        private List<String> groups;
        private List<ShareStudentOut> students;
    }
}
