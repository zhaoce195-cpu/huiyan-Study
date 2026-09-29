package com.huiyan.controller;

import cn.dev33.satoken.stp.StpUtil;
import com.huiyan.common.response.PageResult;
import com.huiyan.common.response.R;
import com.huiyan.common.util.SecurityUtils;
import com.huiyan.entity.TrainingCase;
import com.huiyan.entity.User;
import com.huiyan.service.TrainingService;
import lombok.RequiredArgsConstructor;
import org.springframework.web.bind.annotation.*;
import org.springframework.web.multipart.MultipartFile;

import java.util.List;
import java.util.Map;

@RestController
@RequestMapping("/api/v1/training")
@RequiredArgsConstructor
public class TrainingController {

    private final TrainingService trainingService;

    @GetMapping("/cases")
    public R<PageResult<TrainingCase>> listCases(
            @RequestParam(defaultValue = "1") long page,
            @RequestParam(defaultValue = "100") long pageSize,
            @RequestParam(required = false) String keyword,
            @RequestParam(required = false) Integer drLevel,
            @RequestParam(required = false) String difficulty,
            @RequestParam(required = false) Boolean done
    ) {
        User user = SecurityUtils.getCurrentUser();
        return R.ok(trainingService.listCases(page, pageSize, keyword, drLevel, difficulty, done, user));
    }

    @GetMapping("/cases/{caseId}")
    public R<TrainingCase> getCase(@PathVariable String caseId) {
        return R.ok(trainingService.getCase(caseId));
    }

    @GetMapping("/cases/{caseId}/heatmap")
    public R<Map<String, Object>> getHeatmap(@PathVariable String caseId) {
        return R.ok(trainingService.getHeatmap(caseId));
    }

    @GetMapping("/cases/{caseId}/gold")
    public R<Map<String, Object>> getGoldStandard(@PathVariable String caseId) {
        return R.ok(trainingService.getGoldStandard(caseId));
    }

    @GetMapping("/cases/{caseId}/iou-history")
    public R<List<Map<String, Object>>> getIouHistory(@PathVariable String caseId) {
        User user = SecurityUtils.getCurrentUser();
        return R.ok(trainingService.getIouHistory(caseId, user));
    }

    @PutMapping("/cases/{caseId}/done")
    public R<Void> markCaseDone(@PathVariable String caseId) {
        return R.ok(null, "已标记为完成");
    }

    @PostMapping("/annotations/submit")
    public R<Map<String, Object>> submitAnnotation(@RequestBody Map<String, Object> req) {
        return R.ok(trainingService.calculateIoU(req), "标注已提交");
    }

    @PostMapping("/iou/calculate")
    public R<Map<String, Object>> calculateIoU(@RequestBody Map<String, Object> req) {
        return R.ok(trainingService.calculateIoU(req));
    }

    @GetMapping("/stats")
    public R<Map<String, Object>> getTrainingStats() {
        User user = SecurityUtils.getCurrentUser();
        return R.ok(trainingService.getTrainingStats(user));
    }

    @GetMapping("/cases/{caseId}/ai-diagnosis")
    public R<Map<String, Object>> getAiDiagnosis(@PathVariable String caseId) {
        return R.ok(trainingService.getAiDiagnosis(caseId));
    }

    @PostMapping("/cases/{caseId}/ai-diagnosis")
    public R<Map<String, Object>> runAiDiagnosis(
            @PathVariable String caseId,
            @RequestParam(defaultValue = "false") boolean force
    ) {
        return R.ok(trainingService.runAiDiagnosis(caseId, force));
    }

    @PostMapping("/ai-cases")
    public R<Map<String, Object>> createAiCase(
            @RequestParam("left_eye") MultipartFile leftEye,
            @RequestParam("right_eye") MultipartFile rightEye,
            @RequestParam(required = false) String title,
            @RequestParam(required = false) String difficulty
    ) {
        User user = SecurityUtils.getCurrentUser();
        return R.ok(trainingService.createAiCase(leftEye, rightEye, title, difficulty, user), "AI 智能建案完成");
    }
}
