package com.huiyan.controller;

import cn.dev33.satoken.stp.StpUtil;
import com.huiyan.common.response.PageResult;
import com.huiyan.common.response.R;
import com.huiyan.common.util.SecurityUtils;
import com.huiyan.entity.Organization;
import com.huiyan.entity.OrganizationApplication;
import com.huiyan.entity.User;
import com.huiyan.service.OrganizationService;
import lombok.RequiredArgsConstructor;
import org.springframework.web.bind.annotation.*;

import java.util.List;
import java.util.Map;

@RestController
@RequestMapping("/api/v1/organization")
@RequiredArgsConstructor
public class OrganizationController {

    private final OrganizationService organizationService;

    @GetMapping("/orgs")
    public R<List<Organization>> listOrgs(@RequestParam(required = false) String keyword) {
        return R.ok(organizationService.listOrgs(keyword));
    }

    @PostMapping("/apply")
    public R<OrganizationApplication> apply(@RequestBody Map<String, Object> req) {
        User user = SecurityUtils.getCurrentUser();
        Object orgIdObj = req.get("organizationId") != null ? req.get("organizationId") : req.get("organization_id");
        if (orgIdObj == null) {
            return R.fail(R.CODE_BAD_REQUEST, "机构ID不能为空");
        }
        Integer orgId = Integer.valueOf(orgIdObj.toString());
        String reason = (String) req.getOrDefault("reason", "");
        return R.ok(organizationService.apply(orgId, reason, user), "申请已提交，请等待审核");
    }

    @GetMapping("/applications/mine")
    public R<PageResult<OrganizationApplication>> listMyApplications(
            @RequestParam(defaultValue = "1") long page,
            @RequestParam(defaultValue = "20") long pageSize
    ) {
        User user = SecurityUtils.getCurrentUser();
        return R.ok(organizationService.listMyApplications(page, pageSize, user));
    }

    @GetMapping("/applications")
    public R<PageResult<OrganizationApplication>> listApplications(
            @RequestParam(required = false) String keyword,
            @RequestParam(required = false) String status,
            @RequestParam(required = false) Integer organizationId,
            @RequestParam(defaultValue = "1") long page,
            @RequestParam(defaultValue = "20") long pageSize
    ) {
        // Teacher or Admin can view
        if (!StpUtil.hasRole("TEACHER") && !StpUtil.hasRole("ADMIN")) {
            StpUtil.checkRole("ADMIN"); // will throw NotRoleException
        }
        return R.ok(organizationService.listForAdmin(page, pageSize, keyword, status, organizationId));
    }

    @PostMapping("/applications/{appId}/review")
    public R<OrganizationApplication> review(
            @PathVariable Integer appId,
            @RequestBody Map<String, Object> req
    ) {
        StpUtil.checkRole("ADMIN");
        User reviewer = SecurityUtils.getCurrentUser();
        boolean accept = Boolean.TRUE.equals(req.get("accept"));
        String comment = (String) req.getOrDefault("comment", "");
        OrganizationApplication app = organizationService.review(appId, accept, comment, reviewer);
        return R.ok(app, accept ? "已通过" : "已驳回");
    }
}
