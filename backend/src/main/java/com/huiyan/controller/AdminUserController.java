package com.huiyan.controller;

import cn.dev33.satoken.annotation.SaCheckRole;
import com.huiyan.common.response.PageResult;
import com.huiyan.common.response.R;
import com.huiyan.dto.user.AdminUserDTO;
import com.huiyan.entity.User;
import com.huiyan.service.AdminUserService;
import lombok.RequiredArgsConstructor;
import org.springframework.web.bind.annotation.*;

import java.util.Map;

@RestController
@RequestMapping("/api/v1/admin/users")
@RequiredArgsConstructor
public class AdminUserController {

    private final AdminUserService adminUserService;

    @GetMapping
    public R<PageResult<AdminUserDTO.AdminUserItem>> listUsers(
            @RequestParam(defaultValue = "1") long page,
            @RequestParam(defaultValue = "20") long pageSize,
            @RequestParam(required = false) String username,
            @RequestParam(required = false) String realName,
            @RequestParam(required = false) String role,
            @RequestParam(required = false) String department,
            @RequestParam(required = false) Boolean isActive
    ) {
        return R.ok(adminUserService.listUsers(page, pageSize, username, realName, role, department, isActive));
    }

    @PostMapping
    public R<User> createUser(@RequestBody AdminUserDTO.AdminUserCreate req) {
        return R.ok(adminUserService.createUser(req), "用户创建成功");
    }

    @PutMapping("/{id}")
    public R<Void> updateUser(@PathVariable Integer id, @RequestBody AdminUserDTO.AdminUserUpdate req) {
        adminUserService.updateUser(id, req);
        return R.ok(null, "用户更新成功");
    }

    @DeleteMapping("/{id}")
    public R<Void> deleteUser(@PathVariable Integer id) {
        adminUserService.deleteUser(id);
        return R.ok(null, "用户删除成功");
    }

    @PostMapping("/{id}/reset-password")
    public R<Map<String, Object>> resetPassword(@PathVariable Integer id) {
        return R.ok(adminUserService.resetPassword(id), "密码已重置");
    }

    @PostMapping("/{id}/toggle-status")
    public R<Void> toggleStatus(@PathVariable Integer id) {
        adminUserService.toggleStatus(id);
        return R.ok(null, "用户状态已切换");
    }
}
