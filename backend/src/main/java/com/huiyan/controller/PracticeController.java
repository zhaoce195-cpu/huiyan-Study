package com.huiyan.controller;

import com.huiyan.common.response.PageResult;
import com.huiyan.common.response.R;
import com.huiyan.common.util.SecurityUtils;
import com.huiyan.dto.casebrowse.CaseBrowseDTO;
import com.huiyan.dto.practice.PracticeDTO;
import com.huiyan.entity.User;
import com.huiyan.service.PracticeService;
import lombok.RequiredArgsConstructor;
import org.springframework.web.bind.annotation.*;

import java.util.Map;

@RestController
@RequestMapping("/api/v1/practice")
@RequiredArgsConstructor
public class PracticeController {

    private final PracticeService practiceService;

    @GetMapping("/random")
    public R<CaseBrowseDTO.CaseBrowseDetail> randomCase(
            @RequestParam(required = false) String category,
            @RequestParam(required = false) String difficulty,
            @RequestParam(required = false) Integer drLevel,
            @RequestParam(required = false, defaultValue = "true") Boolean excludeDone
    ) {
        User user = SecurityUtils.getCurrentUser();
        return R.ok(practiceService.randomCase(category, difficulty, drLevel, excludeDone, user));
    }

    @GetMapping("/cases/{caseId}")
    public R<CaseBrowseDTO.CaseBrowseDetail> caseBrief(@PathVariable Integer caseId) {
        User user = SecurityUtils.getCurrentUser();
        return R.ok(practiceService.caseBrief(caseId, user));
    }

    @GetMapping("/cases/{caseId}/gold")
    public R<Map<String, Object>> getGold(@PathVariable Integer caseId) {
        User user = SecurityUtils.getCurrentUser();
        return R.ok(practiceService.getGoldStandard(caseId, user));
    }

    @GetMapping("/cases/{caseId}/hint")
    public R<Map<String, Object>> getHint(@PathVariable Integer caseId) {
        User user = SecurityUtils.getCurrentUser();
        return R.ok(practiceService.getHint(caseId, user));
    }

    @PostMapping("/start")
    public R<PracticeDTO.PracticeOut> startPractice(@RequestBody PracticeDTO.PracticeStartParams req) {
        User user = SecurityUtils.getCurrentUser();
        return R.ok(practiceService.startPractice(req, user), "练习开始");
    }

    @PostMapping("/submit")
    public R<PracticeDTO.PracticeOut> submitPractice(@RequestBody PracticeDTO.PracticeSubmitParams req) {
        User user = SecurityUtils.getCurrentUser();
        return R.ok(practiceService.submitPractice(req, user), "作答提交成功，已评分");
    }

    @GetMapping("/list")
    public R<PageResult<PracticeDTO.PracticeOut>> listPractices(
            @RequestParam(defaultValue = "1") long page,
            @RequestParam(defaultValue = "20") long pageSize,
            @RequestParam(required = false) String status,
            @RequestParam(required = false) Integer caseId
    ) {
        User user = SecurityUtils.getCurrentUser();
        return R.ok(practiceService.listPractices(page, pageSize, status, caseId, user));
    }

    @GetMapping("/{recordId}")
    public R<PracticeDTO.PracticeOut> getPractice(@PathVariable Integer recordId) {
        User user = SecurityUtils.getCurrentUser();
        return R.ok(practiceService.getPractice(recordId, user));
    }

    @PostMapping("/{recordId}/review")
    public R<Void> reviewPractice(@PathVariable Integer recordId, @RequestBody PracticeDTO.PracticeReviewParams req) {
        User user = SecurityUtils.getCurrentUser();
        practiceService.reviewPractice(recordId, req.getComment(), user);
        return R.ok(null, "教师点评保存成功");
    }

    @DeleteMapping("/{recordId}")
    public R<Void> deletePractice(@PathVariable Integer recordId) {
        User user = SecurityUtils.getCurrentUser();
        practiceService.deletePractice(recordId, user);
        return R.ok(null, "练习记录已删除");
    }

    @GetMapping("/stats/me")
    public R<PracticeDTO.PracticeStatsOut> getStatsMe() {
        User user = SecurityUtils.getCurrentUser();
        return R.ok(practiceService.getStats(user.getId()));
    }

    @GetMapping("/stats/user/{userId}")
    public R<PracticeDTO.PracticeStatsOut> getStatsUser(@PathVariable Integer userId) {
        return R.ok(practiceService.getStats(userId));
    }

    @GetMapping("/stats/all")
    public R<PracticeDTO.PracticeStatsOut> getStatsAll() {
        User user = SecurityUtils.getCurrentUser();
        return R.ok(practiceService.getStats(user.getId()));
    }
}
