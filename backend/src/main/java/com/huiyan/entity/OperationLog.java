package com.huiyan.entity;

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
@TableName("biz_op_log")
public class OperationLog extends BaseEntity {

    private Integer userId;
    private String username;
    private String module;
    private String action;
    private String detail;
    private String ip;
}
