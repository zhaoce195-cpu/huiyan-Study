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
@TableName("biz_case_image")
public class CaseImage extends BaseEntity {

    private String caseTable;
    private Integer caseId;
    private String role;
    private String eye;
    private String fileUrl;
    private String fileName;
    private Integer fileSize;
    private Integer width;
    private Integer height;
    private Integer sortOrder;
    private String sopInstanceUid;
    private String seriesInstanceUid;
    private String studyInstanceUid;
    private Integer uploadedBy;

    @TableField(exist = false)
    private String uploaderName;
}
