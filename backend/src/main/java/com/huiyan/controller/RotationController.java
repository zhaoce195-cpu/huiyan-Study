package com.huiyan.controller;

import com.huiyan.common.response.R;
import com.huiyan.common.util.SecurityUtils;
import com.huiyan.entity.Rotation;
import com.huiyan.entity.RotationTask;
import com.huiyan.entity.User;
import com.huiyan.service.RotationService;
import lombok.RequiredArgsConstructor;
import org.springframework.web.bind.annotation.*;

import java.util.Map;

@RestController
@RequestMapping("/api/v1/rotation")
@RequiredArgsConstructor
public class RotationController {

    private final RotationService rotationService;

    @GetMapping("/home")
    public R<Map<String, Object>> home() {
        User user = SecurityUtils.getCurrentUser();
        return R.ok(rotationService.home(user));
    }

    @GetMapping("/options")
    public R<Map<String, Object>> options() {
        User user = SecurityUtils.getCurrentUser();
        return R.ok(rotationService.options(user));
    }

    @PutMapping("/students/{userId}/group")
    public R<Void> setStudentGroup(@PathVariable Integer userId, @RequestBody Map<String, Object> req) {
        User user = SecurityUtils.getCurrentUser();
        rotationService.setStudentGroup(userId, req, user);
        return R.ok(null, "分组已保存");
    }

    @PutMapping("/current")
    public R<Rotation> updateCurrent(@RequestBody Map<String, Object> req) {
        User user = SecurityUtils.getCurrentUser();
        return R.ok(rotationService.updateRotation(req, user), "轮转计划已更新");
    }

    @PostMapping("/tasks")
    public R<RotationTask> addTask(@RequestBody Map<String, Object> req) {
        User user = SecurityUtils.getCurrentUser();
        return R.ok(rotationService.addTask(req, user), "必做项已添加");
    }

    @DeleteMapping("/tasks/{taskId}")
    public R<Void> deleteTask(@PathVariable Integer taskId) {
        User user = SecurityUtils.getCurrentUser();
        rotationService.deleteTask(taskId, user);
        return R.ok(null, "任务已移除");
    }

    @PostMapping("/tasks/{taskId}/ack")
    public R<Void> ackTask(@PathVariable Integer taskId) {
        User user = SecurityUtils.getCurrentUser();
        rotationService.ackTask(taskId, user);
        return R.ok(null, "已标记为已完成");
    }
}
