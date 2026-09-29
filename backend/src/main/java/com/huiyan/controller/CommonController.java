package com.huiyan.controller;

import cn.dev33.satoken.stp.StpUtil;
import com.huiyan.common.response.PageResult;
import com.huiyan.common.response.R;
import com.huiyan.common.util.SecurityUtils;
import com.huiyan.dto.common.CommonDTO;
import com.huiyan.entity.Department;
import com.huiyan.entity.Notice;
import com.huiyan.service.CommonService;
import com.huiyan.service.NoticeService;
import lombok.RequiredArgsConstructor;
import org.springframework.web.bind.annotation.*;
import org.springframework.web.multipart.MultipartFile;

import java.time.LocalDateTime;
import java.time.format.DateTimeFormatter;
import java.util.HashMap;
import java.util.List;
import java.util.Map;

@RestController
@RequestMapping("/api/v1/common")
@RequiredArgsConstructor
public class CommonController {

    private final CommonService commonService;
    private final NoticeService noticeService;

    @GetMapping("/system/config")
    public R<CommonDTO.SystemConfig> systemConfig() {
        return R.ok(commonService.getSystemConfig());
    }

    @GetMapping("/ping")
    public R<Map<String, String>> ping() {
        Map<String, String> map = new HashMap<>();
        map.put("status", "ok");
        map.put("time", LocalDateTime.now().format(DateTimeFormatter.ofPattern("yyyy-MM-dd HH:mm:ss")));
        return R.ok(map);
    }

    @GetMapping("/time")
    public R<Map<String, Object>> time() {
        Map<String, Object> map = new HashMap<>();
        map.put("server_time", LocalDateTime.now().format(DateTimeFormatter.ofPattern("yyyy-MM-dd HH:mm:ss")));
        map.put("serverTime", LocalDateTime.now().format(DateTimeFormatter.ofPattern("yyyy-MM-dd HH:mm:ss")));
        map.put("timestamp", System.currentTimeMillis());
        return R.ok(map);
    }

    @GetMapping("/dict/{type}")
    public R<List<CommonDTO.DictItem>> getDict(@PathVariable String type) {
        return R.ok(commonService.getDict(type));
    }

    @PostMapping("/dict/batch")
    public R<Map<String, List<CommonDTO.DictItem>>> getDictBatch(@RequestBody CommonDTO.DictBatchRequest req) {
        return R.ok(commonService.getDictBatch(req.getTypes()));
    }

    @GetMapping("/hospitals")
    public R<List<Map<String, Object>>> getHospitals() {
        return R.ok(commonService.getHospitals());
    }

    @GetMapping("/departments")
    public R<PageResult<Department>> getDepartments(
            @RequestParam(defaultValue = "1") long page,
            @RequestParam(defaultValue = "100") long pageSize,
            @RequestParam(required = false) String name,
            @RequestParam(required = false) Boolean isActive
    ) {
        return R.ok(commonService.getDepartments(page, pageSize, name, isActive));
    }

    @PostMapping("/departments")
    public R<Department> createDepartment(@RequestBody CommonDTO.DepartmentSaveRequest req) {
        return R.ok(commonService.saveDepartment(req), "科室创建成功");
    }

    @PutMapping("/departments/{id}")
    public R<Void> updateDepartment(@PathVariable Integer id, @RequestBody CommonDTO.DepartmentSaveRequest req) {
        commonService.updateDepartment(id, req);
        return R.ok(null, "科室修改成功");
    }

    @DeleteMapping("/departments/{id}")
    public R<Void> deleteDepartment(@PathVariable Integer id) {
        commonService.deleteDepartment(id);
        return R.ok(null, "科室删除成功");
    }

    @GetMapping("/notices")
    public R<PageResult<Notice>> getNotices(
            @RequestParam(defaultValue = "1") long page,
            @RequestParam(defaultValue = "20") long pageSize,
            @RequestParam(required = false) String noticeType,
            @RequestParam(required = false) String status,
            @RequestParam(required = false) String keyword
    ) {
        Integer currentUserId = StpUtil.isLogin() ? SecurityUtils.getCurrentUserId() : null;
        return R.ok(noticeService.getNotices(page, pageSize, noticeType, status, keyword, currentUserId));
    }

    @GetMapping("/notices/{id}")
    public R<Notice> getNoticeDetail(@PathVariable Integer id) {
        Integer currentUserId = StpUtil.isLogin() ? SecurityUtils.getCurrentUserId() : null;
        return R.ok(noticeService.getNoticeDetail(id, currentUserId));
    }

    @PostMapping("/notices")
    public R<Notice> createNotice(@RequestBody CommonDTO.NoticeSaveRequest req) {
        Integer currentUserId = SecurityUtils.getCurrentUserId();
        return R.ok(noticeService.saveNotice(req, currentUserId), "公告创建成功");
    }

    @PutMapping("/notices/{id}")
    public R<Void> updateNotice(@PathVariable Integer id, @RequestBody CommonDTO.NoticeSaveRequest req) {
        noticeService.updateNotice(id, req);
        return R.ok(null, "公告修改成功");
    }

    @DeleteMapping("/notices/{id}")
    public R<Void> deleteNotice(@PathVariable Integer id) {
        noticeService.deleteNotice(id);
        return R.ok(null, "公告删除成功");
    }

    @GetMapping("/notifications")
    public R<PageResult<Notice>> getNotifications(
            @RequestParam(defaultValue = "1") long page,
            @RequestParam(defaultValue = "20") long pageSize
    ) {
        Integer currentUserId = SecurityUtils.getCurrentUserId();
        return R.ok(noticeService.getNotices(page, pageSize, null, "PUBLISHED", null, currentUserId));
    }

    @PostMapping("/notifications/read")
    public R<Void> markNotificationRead(@RequestBody CommonDTO.NotificationReadRequest req) {
        Integer currentUserId = SecurityUtils.getCurrentUserId();
        if (req.getId() != null) {
            noticeService.markRead(currentUserId, req.getId());
        }
        if (req.getIds() != null) {
            for (Integer id : req.getIds()) {
                noticeService.markRead(currentUserId, id);
            }
        }
        return R.ok(null, "已标记为已读");
    }

    @PostMapping("/notifications/read-all")
    public R<Void> markAllNotificationsRead() {
        Integer currentUserId = SecurityUtils.getCurrentUserId();
        noticeService.markAllRead(currentUserId);
        return R.ok(null, "已全部标记为已读");
    }

    @PostMapping("/upload")
    public R<Map<String, Object>> uploadFile(
            @RequestParam("file") MultipartFile file,
            @RequestParam(value = "sub_dir", defaultValue = "common") String subDir
    ) {
        String fileUrl = commonService.uploadFile(file, subDir);
        Map<String, Object> map = new HashMap<>();
        map.put("file_url", fileUrl);
        map.put("fileUrl", fileUrl);
        map.put("file_name", file.getOriginalFilename());
        map.put("file_size", file.getSize());
        return R.ok(map, "上传成功");
    }

    @GetMapping("/stats/training")
    public R<CommonDTO.TrainingStats> getTrainingStats() {
        return R.ok(commonService.getTrainingStats());
    }

    @GetMapping("/stats/study-hours")
    public R<Map<String, Object>> getStudyHours() {
        CommonDTO.TrainingStats stats = commonService.getTrainingStats();
        Map<String, Object> map = new HashMap<>();
        map.put("totalHours", stats.getTotalStudyHours());
        map.put("totalPractices", stats.getTotalPractices());
        return R.ok(map);
    }
}
