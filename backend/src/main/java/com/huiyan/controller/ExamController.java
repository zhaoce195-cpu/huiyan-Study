package com.huiyan.controller;

import com.huiyan.common.response.R;
import com.huiyan.common.util.SecurityUtils;
import com.huiyan.entity.ExamPaper;
import com.huiyan.entity.User;
import com.huiyan.service.ExamService;
import lombok.RequiredArgsConstructor;
import org.springframework.web.bind.annotation.*;

import java.util.List;
import java.util.Map;

@RestController
@RequestMapping("/api/v1/exams")
@RequiredArgsConstructor
public class ExamController {

    private final ExamService examService;

    @GetMapping("/case-options")
    public R<List<Map<String, Object>>> caseOptions() {
        User user = SecurityUtils.getCurrentUser();
        return R.ok(examService.caseOptions(user));
    }

    @GetMapping
    public R<List<Map<String, Object>>> listExams() {
        User user = SecurityUtils.getCurrentUser();
        return R.ok(examService.listPapers(user));
    }

    @PostMapping
    public R<ExamPaper> createExam(@RequestBody Map<String, Object> req) {
        User user = SecurityUtils.getCurrentUser();
        return R.ok(examService.create(user, req), "考试已发布");
    }

    @PostMapping("/{paperId}/start")
    public R<Map<String, Object>> startExam(@PathVariable Integer paperId) {
        User user = SecurityUtils.getCurrentUser();
        return R.ok(examService.start(user, paperId));
    }

    @PostMapping("/{paperId}/close")
    public R<Void> closeExam(@PathVariable Integer paperId) {
        User user = SecurityUtils.getCurrentUser();
        examService.close(user, paperId);
        return R.ok(null, "考试已收卷");
    }

    @GetMapping("/{paperId}/results")
    public R<Map<String, Object>> getResults(@PathVariable Integer paperId) {
        User user = SecurityUtils.getCurrentUser();
        return R.ok(examService.getResults(user, paperId));
    }
}
