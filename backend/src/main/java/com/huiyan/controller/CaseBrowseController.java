package com.huiyan.controller;

import com.huiyan.common.response.PageResult;
import com.huiyan.common.response.R;
import com.huiyan.common.util.SecurityUtils;
import com.huiyan.dto.casebrowse.CaseBrowseDTO;
import com.huiyan.entity.User;
import com.huiyan.service.CaseBrowseService;
import lombok.RequiredArgsConstructor;
import org.springframework.format.annotation.DateTimeFormat;
import org.springframework.http.HttpHeaders;
import org.springframework.http.MediaType;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.*;

import java.nio.charset.StandardCharsets;
import java.time.LocalDateTime;
import java.util.HashMap;
import java.util.Map;

@RestController
@RequestMapping("/api/v1/case-browse")
@RequiredArgsConstructor
public class CaseBrowseController {

    private final CaseBrowseService caseBrowseService;

    @GetMapping("/list")
    public R<PageResult<CaseBrowseDTO.CaseBrowseItem>> listCases(
            @RequestParam(defaultValue = "1") long page,
            @RequestParam(defaultValue = "20") long pageSize,
            @RequestParam(required = false) String keyword,
            @RequestParam(required = false) String category,
            @RequestParam(required = false) Integer drLevel,
            @RequestParam(required = false) String difficulty,
            @RequestParam(required = false) String archiveStatus,
            @RequestParam(required = false) String creatorRole,
            @RequestParam(required = false) @DateTimeFormat(pattern = "yyyy-MM-dd HH:mm:ss") LocalDateTime startTime,
            @RequestParam(required = false) @DateTimeFormat(pattern = "yyyy-MM-dd HH:mm:ss") LocalDateTime endTime,
            @RequestParam(required = false, defaultValue = "false") Boolean onlyIncomplete
    ) {
        User currentUser = SecurityUtils.getCurrentUser();
        return R.ok(caseBrowseService.listCases(
                page, pageSize, keyword, category, drLevel, difficulty, archiveStatus,
                creatorRole, startTime, endTime, onlyIncomplete, currentUser
        ));
    }

    @GetMapping("/{caseId}")
    public R<CaseBrowseDTO.CaseBrowseDetail> getCaseDetail(@PathVariable Integer caseId) {
        User currentUser = SecurityUtils.getCurrentUser();
        return R.ok(caseBrowseService.getCaseDetail(caseId, currentUser));
    }

    @PutMapping("/{caseId}/archive")
    public R<Void> archiveCase(@PathVariable Integer caseId, @RequestBody CaseBrowseDTO.CaseArchiveParams req) {
        User currentUser = SecurityUtils.getCurrentUser();
        caseBrowseService.archiveCase(caseId, req.getArchiveStatus(), req.getReason(), currentUser);
        return R.ok(null, "归档状态已更新");
    }

    @PutMapping("/{caseId}/gold-standard")
    public R<Void> updateGoldStandard(@PathVariable Integer caseId, @RequestBody CaseBrowseDTO.GoldStandardUpdate req) {
        User currentUser = SecurityUtils.getCurrentUser();
        caseBrowseService.updateGoldStandard(caseId, req, currentUser);
        return R.ok(null, "金标准修订成功");
    }

    @PostMapping("/{caseId}/join-training")
    public R<Void> joinTraining(@PathVariable Integer caseId) {
        User currentUser = SecurityUtils.getCurrentUser();
        caseBrowseService.joinTraining(caseId, currentUser);
        return R.ok(null, "已加入实训库");
    }

    @GetMapping("/import/template")
    public ResponseEntity<byte[]> importTemplate() {
        String csv = "病人编号,检查日期,病例编号,标题,病种分类,难度,DR等级,主诉与病史,右眼图像,左眼图像\n" +
                "SUBJ001,2026-05-01,T2026001,示例病例,DR,EASY,1,视力下降3月,IDRiD_01_OD.jpg,IDRiD_01_OS.jpg\n";
        byte[] bytes = csv.getBytes(StandardCharsets.UTF_8);
        return ResponseEntity.ok()
                .header(HttpHeaders.CONTENT_DISPOSITION, "attachment; filename=case-register.csv")
                .contentType(MediaType.parseMediaType("text/csv; charset=utf-8"))
                .body(bytes);
    }

    @GetMapping("/import/rules")
    public R<Map<String, Object>> importRules() {
        Map<String, Object> map = new HashMap<>();
        map.put("naming", "支持标准眼底图命名规则，文件名包含 OD 为右眼，包含 OS 为左眼");
        return R.ok(map);
    }
}
