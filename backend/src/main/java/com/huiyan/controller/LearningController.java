package com.huiyan.controller;

import com.huiyan.common.response.PageResult;
import com.huiyan.common.response.R;
import com.huiyan.common.util.SecurityUtils;
import com.huiyan.entity.LearningNote;
import com.huiyan.entity.LearningResource;
import com.huiyan.entity.User;
import com.huiyan.service.LearningService;
import lombok.RequiredArgsConstructor;
import org.springframework.web.bind.annotation.*;

import java.util.Map;

@RestController
@RequestMapping("/api/v1/learning")
@RequiredArgsConstructor
public class LearningController {

    private final LearningService learningService;

    // ====================== 资料 ======================

    @GetMapping("/resources")
    public R<PageResult<LearningResource>> listResources(
            @RequestParam(required = false) String keyword,
            @RequestParam(required = false) String resourceType,
            @RequestParam(required = false) String status,
            @RequestParam(defaultValue = "false") Boolean onlyMine,
            @RequestParam(defaultValue = "1") long page,
            @RequestParam(defaultValue = "20") long pageSize
    ) {
        User user = SecurityUtils.getCurrentUser();
        return R.ok(learningService.listResources(page, pageSize, keyword, resourceType, status, onlyMine, user));
    }

    @GetMapping("/resources/{resourceId}")
    public R<LearningResource> getResource(@PathVariable Integer resourceId) {
        User user = SecurityUtils.getCurrentUser();
        return R.ok(learningService.getResource(resourceId, user));
    }

    @PostMapping("/resources")
    public R<LearningResource> createResource(@RequestBody Map<String, Object> req) {
        User user = SecurityUtils.getCurrentUser();
        return R.ok(learningService.createResource(req, user), "上传成功");
    }

    @PutMapping("/resources/{resourceId}")
    public R<LearningResource> updateResource(
            @PathVariable Integer resourceId,
            @RequestBody Map<String, Object> req
    ) {
        User user = SecurityUtils.getCurrentUser();
        return R.ok(learningService.updateResource(resourceId, req, user), "已更新");
    }

    @DeleteMapping("/resources/{resourceId}")
    public R<Void> deleteResource(@PathVariable Integer resourceId) {
        User user = SecurityUtils.getCurrentUser();
        learningService.deleteResource(resourceId, user);
        return R.ok(null, "已删除");
    }

    // ====================== 收藏 ======================

    @GetMapping("/favorites")
    public R<PageResult<LearningResource>> listFavorites(
            @RequestParam(required = false) String keyword,
            @RequestParam(required = false) String resourceType,
            @RequestParam(required = false) String label,
            @RequestParam(defaultValue = "1") long page,
            @RequestParam(defaultValue = "20") long pageSize
    ) {
        User user = SecurityUtils.getCurrentUser();
        return R.ok(learningService.listFavorites(page, pageSize, keyword, resourceType, label, user));
    }

    @PostMapping("/favorites")
    public R<LearningResource> addFavorite(@RequestBody Map<String, Object> req) {
        User user = SecurityUtils.getCurrentUser();
        Object rIdObj = req.get("resourceId") != null ? req.get("resourceId") : req.get("resource_id");
        if (rIdObj == null) {
            return R.fail(R.CODE_BAD_REQUEST, "资料ID不能为空");
        }
        Integer resourceId = Integer.valueOf(rIdObj.toString());
        String label = (String) req.getOrDefault("label", "");
        return R.ok(learningService.addFavorite(resourceId, label, user), "已收藏");
    }

    @DeleteMapping("/favorites/{resourceId}")
    public R<Void> removeFavorite(@PathVariable Integer resourceId) {
        User user = SecurityUtils.getCurrentUser();
        learningService.removeFavorite(resourceId, user);
        return R.ok(null, "已取消收藏");
    }

    // ====================== 笔记 ======================

    @GetMapping("/notes")
    public R<PageResult<LearningNote>> listNotes(
            @RequestParam(required = false) String keyword,
            @RequestParam(required = false) Integer caseId,
            @RequestParam(required = false) Integer resourceId,
            @RequestParam(required = false) Integer userId,
            @RequestParam(defaultValue = "1") long page,
            @RequestParam(defaultValue = "20") long pageSize
    ) {
        User user = SecurityUtils.getCurrentUser();
        return R.ok(learningService.listNotes(page, pageSize, keyword, caseId, resourceId, userId, user));
    }

    @PostMapping("/notes")
    public R<LearningNote> createNote(@RequestBody Map<String, Object> req) {
        User user = SecurityUtils.getCurrentUser();
        return R.ok(learningService.createNote(req, user), "笔记已创建");
    }

    @GetMapping("/notes/{noteId}")
    public R<LearningNote> getNote(@PathVariable Integer noteId) {
        User user = SecurityUtils.getCurrentUser();
        return R.ok(learningService.getNote(noteId, user));
    }

    @PutMapping("/notes/{noteId}")
    public R<LearningNote> updateNote(
            @PathVariable Integer noteId,
            @RequestBody Map<String, Object> req
    ) {
        User user = SecurityUtils.getCurrentUser();
        return R.ok(learningService.updateNote(noteId, req, user), "已更新");
    }

    @DeleteMapping("/notes/{noteId}")
    public R<Void> deleteNote(@PathVariable Integer noteId) {
        User user = SecurityUtils.getCurrentUser();
        learningService.deleteNote(noteId, user);
        return R.ok(null, "已删除");
    }
}
