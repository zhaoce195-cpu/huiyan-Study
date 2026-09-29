package com.huiyan.dto.common;

import com.fasterxml.jackson.annotation.JsonFormat;
import lombok.AllArgsConstructor;
import lombok.Builder;
import lombok.Data;
import lombok.NoArgsConstructor;

import java.io.Serializable;
import java.time.LocalDateTime;
import java.util.List;
import java.util.Map;

public class CommonDTO {

    @Data
    @Builder
    @NoArgsConstructor
    @AllArgsConstructor
    public static class SystemConfig implements Serializable {
        private String projectName;
        private String projectVersion;
        private String apiPrefix;
        private Boolean orthancEnabled;
        private Boolean drgcnnEnabled;
        private Boolean keycloakLoginEnabled;
    }

    @Data
    @Builder
    @NoArgsConstructor
    @AllArgsConstructor
    public static class DictItem implements Serializable {
        private String label;
        private Object value;
        private String color;
        private String description;
    }

    @Data
    @NoArgsConstructor
    @AllArgsConstructor
    public static class DictBatchRequest implements Serializable {
        private List<String> types;
    }

    @Data
    @NoArgsConstructor
    @AllArgsConstructor
    public static class DepartmentSaveRequest implements Serializable {
        private String code;
        private String name;
        private String shortName;
        private String leader;
        private String phone;
        private Integer sortOrder;
        private Boolean isActive;
        private String remark;
        private Integer hospitalId;
    }

    @Data
    @NoArgsConstructor
    @AllArgsConstructor
    public static class NoticeSaveRequest implements Serializable {
        private String title;
        private String summary;
        private String content;
        private String coverUrl;
        private String noticeType;
        private String status;
        private String visibleRoles;
        private Boolean isTop;

        @JsonFormat(pattern = "yyyy-MM-dd HH:mm:ss")
        private LocalDateTime publishAt;

        @JsonFormat(pattern = "yyyy-MM-dd HH:mm:ss")
        private LocalDateTime expireAt;
    }

    @Data
    @NoArgsConstructor
    @AllArgsConstructor
    public static class NotificationReadRequest implements Serializable {
        private Integer id;
        private List<Integer> ids;
    }

    @Data
    @Builder
    @NoArgsConstructor
    @AllArgsConstructor
    public static class TrainingStats implements Serializable {
        private long totalCases;
        private long totalPractices;
        private long totalStudents;
        private double avgScore;
        private double passRate;
        private double avgIou;
        private long totalStudyHours;
        private List<Map<String, Object>> categoryDistribution;
        private List<Map<String, Object>> scoreTrend;
    }
}
