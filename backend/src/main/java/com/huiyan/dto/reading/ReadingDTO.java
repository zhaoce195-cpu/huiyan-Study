package com.huiyan.dto.reading;

import com.fasterxml.jackson.annotation.JsonFormat;
import lombok.AllArgsConstructor;
import lombok.Builder;
import lombok.Data;
import lombok.NoArgsConstructor;

import java.io.Serializable;
import java.time.LocalDateTime;
import java.util.List;
import java.util.Map;

public class ReadingDTO {

    @Data
    @Builder
    @NoArgsConstructor
    @AllArgsConstructor
    public static class ImageSourceItem implements Serializable {
        private int index;
        private String url;
        private String side;
        private String sopInstanceUid;
        private String modality;
    }

    @Data
    @Builder
    @NoArgsConstructor
    @AllArgsConstructor
    public static class ImageSourceOut implements Serializable {
        private int caseId;
        private String caseNo;
        private String caseSn;
        private String title;
        private Integer width;
        private Integer height;
        private List<String> images;
        private List<Map<String, Object>> imageMeta;
        private Map<String, List<String>> imageGroups;
        private Boolean fundusOnly;
        private Map<String, Object> safety;
        private Map<String, Object> dicomInstances;
        private Map<String, Object> segmentation;
        private List<Map<String, Object>> goldAnnotations;
        private String lesionMaskUrl;
        private String heatmapUrl;
    }

    @Data
    @NoArgsConstructor
    @AllArgsConstructor
    public static class ReadingSaveParams implements Serializable {
        private Integer caseId;
        private Integer imageIndex;
        private String imageUrl;
        private Map<String, Object> viewport;
        private List<Map<String, Object>> annotations;
        private List<Map<String, Object>> measurements;
        private Map<String, Object> layers;
        private Map<String, Object> diagnosis;
        private String note;
        private Boolean submit;
        private String requestId;
    }

    @Data
    @Builder
    @NoArgsConstructor
    @AllArgsConstructor
    public static class ReadingOut implements Serializable {
        private Integer id;
        private Integer caseId;
        private String caseNo;
        private Integer userId;
        private String userName;
        private Integer imageIndex;
        private String imageUrl;
        private Object viewport;
        private Object annotations;
        private Object measurements;
        private Object layers;
        private String status;
        private String recordKind;
        private Object diagnosis;
        private String note;
        private String reviewComment;
        private Integer reviewerId;
        private String reviewerName;

        @JsonFormat(pattern = "yyyy-MM-dd HH:mm:ss")
        private LocalDateTime createdAt;

        @JsonFormat(pattern = "yyyy-MM-dd HH:mm:ss")
        private LocalDateTime updatedAt;
    }

    @Data
    @NoArgsConstructor
    @AllArgsConstructor
    public static class ReadingReviewParams implements Serializable {
        private String comment;
    }
}
