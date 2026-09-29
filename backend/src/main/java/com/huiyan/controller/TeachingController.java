package com.huiyan.controller;

import com.huiyan.common.response.PageResult;
import com.huiyan.common.response.R;
import com.huiyan.common.util.SecurityUtils;
import com.huiyan.dto.teaching.TeachingDTO;
import com.huiyan.entity.TeachingShare;
import com.huiyan.entity.User;
import com.huiyan.service.TeachingService;
import lombok.RequiredArgsConstructor;
import org.springframework.web.bind.annotation.*;

import java.util.Map;

@RestController
@RequestMapping("/api/v1/teaching")
@RequiredArgsConstructor
public class TeachingController {

    private final TeachingService teachingService;

    @PostMapping("/share")
    public R<TeachingShare> createShare(@RequestBody Map<String, Object> req) {
        User user = SecurityUtils.getCurrentUser();
        return R.ok(teachingService.createShare(req, user), "课堂分享已创建");
    }

    @PostMapping("/share/{shareId}/reveal")
    public R<TeachingShare> revealShare(@PathVariable Integer shareId) {
        User user = SecurityUtils.getCurrentUser();
        return R.ok(teachingService.revealShare(shareId, user), "已向学员公布金标准");
    }

    @PostMapping("/share/{shareId}/revoke")
    public R<TeachingShare> revokeShare(@PathVariable Integer shareId) {
        User user = SecurityUtils.getCurrentUser();
        return R.ok(teachingService.revokeShare(shareId, user), "分享已收回");
    }

    @PostMapping("/submit")
    public R<TeachingShare> submitForReview(@RequestBody Map<String, Object> req) {
        User user = SecurityUtils.getCurrentUser();
        return R.ok(teachingService.submitForReview(req, user), "入库申请已提交");
    }

    @GetMapping("/my-shares")
    public R<PageResult<TeachingDTO.TeachingShareOut>> myShares(
            @RequestParam(defaultValue = "1") long page,
            @RequestParam(defaultValue = "20") long pageSize,
            @RequestParam(required = false) String shareType,
            @RequestParam(required = false) String status
    ) {
        User user = SecurityUtils.getCurrentUser();
        return R.ok(teachingService.listMyShares(page, pageSize, shareType, status, user));
    }

    @GetMapping("/share-targets")
    public R<TeachingDTO.ShareTargetsOut> shareTargets() {
        return R.ok(teachingService.shareTargets());
    }

    @GetMapping("/student/cases")
    public R<PageResult<TeachingDTO.StudentCaseOut>> studentCases(
            @RequestParam(defaultValue = "1") long page,
            @RequestParam(defaultValue = "20") long pageSize
    ) {
        User user = SecurityUtils.getCurrentUser();
        return R.ok(teachingService.listForStudent(page, pageSize, user));
    }

    @GetMapping("/student/cases/{shareId}")
    public R<TeachingDTO.StudentCaseOut> studentCaseDetail(@PathVariable Integer shareId) {
        User user = SecurityUtils.getCurrentUser();
        return R.ok(teachingService.getStudentCaseDetail(shareId, user));
    }

    @GetMapping("/admin/reviews")
    public R<PageResult<TeachingDTO.TeachingShareOut>> adminReviews(
            @RequestParam(defaultValue = "1") long page,
            @RequestParam(defaultValue = "20") long pageSize,
            @RequestParam(required = false) String status,
            @RequestParam(required = false) String keyword
    ) {
        return R.ok(teachingService.listForAdmin(page, pageSize, status, keyword));
    }

    @PostMapping("/admin/reviews/{shareId}")
    public R<TeachingShare> adminReview(
            @PathVariable Integer shareId,
            @RequestBody Map<String, Object> req
    ) {
        User reviewer = SecurityUtils.getCurrentUser();
        String status = (String) req.getOrDefault("status", "APPROVED");
        String comment = (String) req.getOrDefault("comment", "");
        return R.ok(teachingService.review(shareId, status, comment, reviewer), "审核已处理");
    }

    @PostMapping("/admin/shelve/{shareId}")
    public R<TeachingShare> adminShelve(@PathVariable Integer shareId) {
        User user = SecurityUtils.getCurrentUser();
        return R.ok(teachingService.shelve(shareId, user), "病例已下架");
    }
}
