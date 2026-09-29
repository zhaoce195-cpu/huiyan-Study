package com.huiyan.controller;

import cn.dev33.satoken.stp.StpUtil;
import com.huiyan.common.response.PageResult;
import com.huiyan.common.response.R;
import com.huiyan.common.util.SecurityUtils;
import com.huiyan.entity.StudentApplication;
import com.huiyan.entity.User;
import com.huiyan.service.StudentApplicationService;
import lombok.RequiredArgsConstructor;
import org.springframework.web.bind.annotation.*;

import java.util.Map;

@RestController
@RequestMapping("/api/v1/student-applications")
@RequiredArgsConstructor
public class StudentApplicationController {

    private final StudentApplicationService studentApplicationService;

    @PostMapping("")
    public R<StudentApplication> apply(@RequestBody Map<String, Object> req) {
        StudentApplication app = studentApplicationService.apply(req);
        return R.ok(app, "申请已提交，请等待管理员审核");
    }

    @GetMapping("/status")
    public R<Map<String, Object>> queryStatus(@RequestParam String phone) {
        return R.ok(studentApplicationService.queryByPhone(phone));
    }

    @GetMapping("")
    public R<PageResult<StudentApplication>> listApps(
            @RequestParam(required = false) String keyword,
            @RequestParam(required = false) String status,
            @RequestParam(defaultValue = "1") long page,
            @RequestParam(defaultValue = "20") long pageSize
    ) {
        StpUtil.checkRole("ADMIN");
        return R.ok(studentApplicationService.listApps(page, pageSize, keyword, status));
    }

    @PostMapping("/{appId}/review")
    public R<StudentApplication> review(
            @PathVariable Integer appId,
            @RequestBody Map<String, Object> req
    ) {
        StpUtil.checkRole("ADMIN");
        User reviewer = SecurityUtils.getCurrentUser();
        boolean accept = Boolean.TRUE.equals(req.get("accept"));
        String comment = (String) req.getOrDefault("comment", "");
        StudentApplication app = studentApplicationService.review(appId, accept, comment, reviewer);
        String msg = accept ? "已通过并开通学员账号" : "已驳回，理由已短信告知申请人";
        return R.ok(app, msg);
    }
}
