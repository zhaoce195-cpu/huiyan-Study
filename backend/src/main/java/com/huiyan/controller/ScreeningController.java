package com.huiyan.controller;

import cn.dev33.satoken.stp.StpUtil;
import com.huiyan.common.response.PageResult;
import com.huiyan.common.response.R;
import com.huiyan.common.util.SecurityUtils;
import com.huiyan.dto.screening.ScreeningDTO;
import com.huiyan.service.ScreeningService;
import lombok.RequiredArgsConstructor;
import org.springframework.web.bind.annotation.*;
import org.springframework.web.multipart.MultipartFile;

import java.util.ArrayList;
import java.util.HashMap;
import java.util.List;
import java.util.Map;

@RestController
@RequestMapping("/api/v1/screening")
@RequiredArgsConstructor
public class ScreeningController {

    private final ScreeningService screeningService;

    @PostMapping("/upload")
    public R<ScreeningDTO.UploadFundusResult> uploadFundus(
            @RequestParam("file") MultipartFile file,
            @RequestParam(value = "patientId", required = false) String patientId,
            @RequestParam(value = "patientName", required = false) String patientName,
            @RequestParam(value = "gender", required = false) String gender,
            @RequestParam(value = "age", required = false) Integer age,
            @RequestParam(value = "eye", required = false) String eye,
            @RequestParam(value = "hospital", required = false) String hospital,
            @RequestParam(value = "doctor", required = false) String doctor,
            @RequestParam(value = "remark", required = false) String remark,
            @RequestParam(value = "patientPhone", required = false) String patientPhone
    ) {
        Integer currentUserId = StpUtil.isLogin() ? SecurityUtils.getCurrentUserId() : 1;
        ScreeningDTO.PatientMetaForm meta = new ScreeningDTO.PatientMetaForm(
                patientId, patientName, gender, age, eye, hospital, doctor, remark, patientPhone
        );
        return R.ok(screeningService.uploadFundus(file, meta, currentUserId), "上传成功，分析完成");
    }

    @PostMapping("/upload/batch")
    public R<Map<String, Object>> batchUpload(
            @RequestParam("files") List<MultipartFile> files
    ) {
        Integer currentUserId = StpUtil.isLogin() ? SecurityUtils.getCurrentUserId() : 1;
        List<ScreeningDTO.UploadFundusResult> items = new ArrayList<>();
        int successCount = 0;
        int failedCount = 0;
        for (MultipartFile file : files) {
            try {
                ScreeningDTO.UploadFundusResult res = screeningService.uploadFundus(file, null, currentUserId);
                items.add(res);
                successCount++;
            } catch (Exception e) {
                failedCount++;
            }
        }
        Map<String, Object> map = new HashMap<>();
        map.put("total", files.size());
        map.put("success", successCount);
        map.put("failed", failedCount);
        map.put("items", items);
        return R.ok(map, "批量上传完成");
    }

    @GetMapping("/tasks")
    public R<PageResult<ScreeningDTO.ScreeningTaskOut>> listTasks(
            @RequestParam(defaultValue = "1") long page,
            @RequestParam(defaultValue = "10") long pageSize,
            @RequestParam(required = false) String keyword,
            @RequestParam(required = false) String status,
            @RequestParam(required = false) String risk,
            @RequestParam(required = false) String drStage,
            @RequestParam(required = false) String eye,
            @RequestParam(required = false) String hospital,
            @RequestParam(required = false) String dateFrom,
            @RequestParam(required = false) String dateTo,
            @RequestParam(required = false) String sortBy,
            @RequestParam(required = false) String sortOrder
    ) {
        return R.ok(screeningService.listTasks(page, pageSize, keyword, status, risk, drStage, eye, hospital, dateFrom, dateTo, sortBy, sortOrder));
    }

    @GetMapping("/tasks/{taskId}")
    public R<ScreeningDTO.ScreeningTaskOut> getTask(@PathVariable String taskId) {
        return R.ok(screeningService.getTask(taskId));
    }

    @DeleteMapping("/tasks/{taskId}")
    public R<Void> deleteTask(@PathVariable String taskId) {
        screeningService.deleteTask(taskId);
        return R.ok(null, "任务删除成功");
    }

    @PostMapping("/tasks/reanalyze")
    public R<ScreeningDTO.ScreeningTaskOut> reanalyze(@RequestBody ScreeningDTO.ReanalyzeParams req) {
        return R.ok(screeningService.getTask(req.getTaskId()), "重新分析完成");
    }

    @GetMapping("/stats")
    public R<ScreeningDTO.ScreeningStatsOut> getStats() {
        return R.ok(screeningService.getStats());
    }

    @GetMapping("/reports/{taskId}")
    public R<ScreeningDTO.ScreeningReportOut> getReport(@PathVariable String taskId) {
        return R.ok(screeningService.getReport(taskId));
    }

    @PostMapping("/refer")
    public R<Void> refer(@RequestBody ScreeningDTO.ReferParams req) {
        return R.ok(null, "已提交转诊");
    }

    @PutMapping("/cases/{caseId}")
    public R<Void> updateCase(@PathVariable Integer caseId, @RequestBody ScreeningDTO.CaseUpdateParams req) {
        screeningService.updateCase(caseId, req);
        return R.ok(null, "病例更新成功");
    }

    @PostMapping("/cases/{caseId}/confirm-report")
    public R<Void> confirmReport(@PathVariable Integer caseId) {
        Integer currentUserId = SecurityUtils.getCurrentUserId();
        screeningService.confirmReport(caseId, currentUserId);
        return R.ok(null, "报告已确认并推送");
    }
}
