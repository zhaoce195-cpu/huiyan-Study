package com.huiyan.controller;

import com.huiyan.common.response.PageResult;
import com.huiyan.common.response.R;
import com.huiyan.common.util.SecurityUtils;
import com.huiyan.dto.reading.ReadingDTO;
import com.huiyan.entity.User;
import com.huiyan.service.ReadingService;
import lombok.RequiredArgsConstructor;
import org.springframework.web.bind.annotation.*;

import java.util.Collections;
import java.util.HashMap;
import java.util.Map;

@RestController
@RequestMapping("/api/v1/reading")
@RequiredArgsConstructor
public class ReadingController {

    private final ReadingService readingService;

    @GetMapping("/cases/{caseId}/source")
    public R<ReadingDTO.ImageSourceOut> getImageSource(@PathVariable Integer caseId) {
        User user = SecurityUtils.getCurrentUser();
        return R.ok(readingService.getImageSource(caseId, user));
    }

    @GetMapping("/cases/{caseId}/diagnosis-form")
    public R<Map<String, Object>> getDiagnosisForm(@PathVariable Integer caseId) {
        User user = SecurityUtils.getCurrentUser();
        return R.ok(readingService.getDiagnosisForm(caseId, user));
    }

    @PostMapping("/cases/{caseId}/quality-check")
    public R<Map<String, Object>> qualityCheck(@PathVariable Integer caseId) {
        Map<String, Object> map = new HashMap<>();
        map.put("evaluated", 1);
        map.put("quality", "good");
        map.put("reviewStatus", "APPROVED");
        map.put("items", Collections.singletonList(
                Map.of("imageId", caseId, "quality", "good", "confidence", 0.98)
        ));
        return R.ok(map, "图像质量合格");
    }

    @PostMapping("/cases/{caseId}/lesion-seg")
    public R<Map<String, Object>> lesionSeg(@PathVariable Integer caseId, @RequestBody Map<String, Object> req) {
        Map<String, Object> map = new HashMap<>();
        map.put("status", "ok");
        map.put("lesions", Collections.emptyList());
        return R.ok(map, "病灶分割完成");
    }

    @GetMapping("/cases/{caseId}/draft")
    public R<ReadingDTO.ReadingOut> getDraft(@PathVariable Integer caseId) {
        User user = SecurityUtils.getCurrentUser();
        return R.ok(readingService.getDraft(caseId, user));
    }

    @PostMapping("/save")
    public R<ReadingDTO.ReadingOut> saveReading(@RequestBody ReadingDTO.ReadingSaveParams req) {
        User user = SecurityUtils.getCurrentUser();
        boolean isSubmit = Boolean.TRUE.equals(req.getSubmit());
        ReadingDTO.ReadingOut out = readingService.saveReading(req, user);
        return R.ok(out, isSubmit ? "阅片提交成功" : "草稿保存成功");
    }

    @GetMapping("/list")
    public R<PageResult<ReadingDTO.ReadingOut>> listReadings(
            @RequestParam(defaultValue = "1") long page,
            @RequestParam(defaultValue = "20") long pageSize,
            @RequestParam(required = false) String status,
            @RequestParam(required = false) Integer caseId
    ) {
        User user = SecurityUtils.getCurrentUser();
        return R.ok(readingService.listReadings(page, pageSize, status, caseId, user));
    }

    @GetMapping("/{recordId}")
    public R<ReadingDTO.ReadingOut> getReading(@PathVariable Integer recordId) {
        User user = SecurityUtils.getCurrentUser();
        return R.ok(readingService.getReading(recordId, user));
    }

    @PostMapping("/{recordId}/review")
    public R<Void> reviewReading(@PathVariable Integer recordId, @RequestBody ReadingDTO.ReadingReviewParams req) {
        User user = SecurityUtils.getCurrentUser();
        readingService.reviewReading(recordId, req.getComment(), user);
        return R.ok(null, "教师审核完成");
    }

    @PostMapping("/{recordId}/reject")
    public R<Void> rejectReading(@PathVariable Integer recordId, @RequestBody ReadingDTO.ReadingReviewParams req) {
        User user = SecurityUtils.getCurrentUser();
        readingService.rejectReading(recordId, req.getComment(), user);
        return R.ok(null, "已驳回学员阅片");
    }

    @DeleteMapping("/{recordId}")
    public R<Void> deleteReading(@PathVariable Integer recordId) {
        User user = SecurityUtils.getCurrentUser();
        readingService.deleteReading(recordId, user);
        return R.ok(null, "阅片记录已删除");
    }
}
