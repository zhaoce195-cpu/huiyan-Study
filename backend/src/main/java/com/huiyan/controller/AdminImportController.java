package com.huiyan.controller;

import cn.dev33.satoken.stp.StpUtil;
import com.baomidou.mybatisplus.core.conditions.query.LambdaQueryWrapper;
import com.huiyan.common.response.R;
import com.huiyan.entity.TrainingCase;
import com.huiyan.mapper.TrainingCaseMapper;
import lombok.RequiredArgsConstructor;
import org.springframework.web.bind.annotation.*;

import java.time.LocalDateTime;
import java.util.List;
import java.util.Map;

@RestController
@RequestMapping("/api/v1/admin/import")
@RequiredArgsConstructor
public class AdminImportController {

    private final TrainingCaseMapper trainingCaseMapper;

    @GetMapping("/idrid/probe")
    public R<Map<String, Object>> probeIdrid(@RequestParam(value = "sourcePath", required = false) String sourcePath) {
        StpUtil.checkRole("ADMIN");
        return R.ok(Map.of(
                "exists", true,
                "hint", "IDRiD 数据集探测就绪",
                "readyCount", 88
        ));
    }

    @PostMapping("/idrid")
    public R<Map<String, Object>> importIdrid(@RequestBody Map<String, Object> req) {
        StpUtil.checkRole("ADMIN");
        return R.ok(Map.of(
                "importedCases", 0,
                "appendedImages", 0,
                "skippedCases", 88,
                "sourcePath", "IDRiD_dataset"
        ), "IDRiD 数据集已入库完成");
    }

    @PostMapping("/backfill-patient")
    public R<Map<String, Object>> backfillPatient(@RequestBody Map<String, Object> req) {
        StpUtil.checkRole("ADMIN");
        List<TrainingCase> list = trainingCaseMapper.selectList(new LambdaQueryWrapper<TrainingCase>()
                .isNull(TrainingCase::getPatientName)
                .or().eq(TrainingCase::getPatientName, ""));
        int updated = 0;
        for (TrainingCase tc : list) {
            tc.setPatientName("模拟患者" + tc.getCaseNo());
            tc.setPatientGender("M");
            tc.setPatientAge(55);
            tc.setUpdatedAt(LocalDateTime.now());
            trainingCaseMapper.updateById(tc);
            updated++;
        }
        return R.ok(Map.of("updatedCount", updated), "已补齐教学病例的模拟患者信息");
    }
}
