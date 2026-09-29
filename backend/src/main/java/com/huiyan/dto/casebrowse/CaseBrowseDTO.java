package com.huiyan.dto.casebrowse;

import com.fasterxml.jackson.annotation.JsonFormat;
import lombok.AllArgsConstructor;
import lombok.Builder;
import lombok.Data;
import lombok.NoArgsConstructor;

import java.io.Serializable;
import java.time.LocalDateTime;
import java.util.Collections;
import java.util.List;
import java.util.Map;

public class CaseBrowseDTO {

    @Data
    @Builder
    @NoArgsConstructor
    @AllArgsConstructor
    public static class CaseBrowseItem implements Serializable {
        private Integer id;
        private String caseNo;
        private String caseSn;
        private String title;
        private String description;
        private String category;
        private String categoryText;
        private String difficulty;
        private String difficultyText;
        private Integer drLevel;
        private String drGradeText;
        private String archiveStatus;
        private Boolean isPublished;
        private Boolean isTrainCase;
        private Integer creatorId;
        private String creatorName;
        private String creatorRole;
        private String thumbUrl;
        private Integer imageCount;
        private Integer derivedCount;
        private Boolean imageComplete;
        private Boolean fundusOnly;
        private List<String> missingRoles;
        private String patientName;
        private String patientGender;
        private Integer patientAge;
        private String patientPhone;
        private Boolean phoneVisible;
        private String subjectNo;
        private String examOn;
        private Integer visitIndex;
        private Integer visitCount;

        @JsonFormat(pattern = "yyyy-MM-dd HH:mm:ss")
        private LocalDateTime createdAt;

        @JsonFormat(pattern = "yyyy-MM-dd HH:mm:ss")
        private LocalDateTime updatedAt;
    }

    @Data
    @Builder
    @NoArgsConstructor
    @AllArgsConstructor
    public static class CaseBrowseDetail implements Serializable {
        private Integer id;
        private String caseNo;
        private String caseSn;
        private String title;
        private String description;
        private String category;
        private String categoryText;
        private String difficulty;
        private String difficultyText;
        private Integer drLevel;
        private String drGradeText;
        private String archiveStatus;
        private Boolean isPublished;
        private Boolean isTrainCase;
        private Integer creatorId;
        private String creatorName;
        private String creatorRole;
        private String thumbUrl;
        private Integer imageCount;
        private Integer derivedCount;
        private Boolean imageComplete;
        private Boolean fundusOnly;
        private String patientName;
        private String patientGender;
        private Integer patientAge;
        private String patientPhone;
        private Boolean phoneVisible;
        private String subjectNo;
        private String examOn;
        private Integer visitIndex;
        private Integer visitCount;

        @JsonFormat(pattern = "yyyy-MM-dd HH:mm:ss")
        private LocalDateTime createdAt;

        @JsonFormat(pattern = "yyyy-MM-dd HH:mm:ss")
        private LocalDateTime updatedAt;

        // 详情特有字段
        private String clinicalInfo;
        private Map<String, Object> imagePaths;
        private List<String> images;
        private String goldDrGrade;
        private String goldDiagnosis;
        private String teachingPoints;
        private Object goldLesions;
        private Integer passScore;
        private Boolean isAnswered; // 是否已作答揭晓
    }

    @Data
    @NoArgsConstructor
    @AllArgsConstructor
    public static class CaseArchiveParams implements Serializable {
        private String archiveStatus; // ACTIVE / ARCHIVED
        private String reason;
    }

    @Data
    @NoArgsConstructor
    @AllArgsConstructor
    public static class GoldStandardUpdate implements Serializable {
        private String goldDrGrade;
        private String goldDiagnosis;
        private String teachingPoints;
        private Integer passScore;
        private Object goldLesions;
        private Boolean publish;
    }
}
