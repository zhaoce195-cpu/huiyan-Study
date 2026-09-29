package com.huiyan.controller;

import com.huiyan.common.response.R;
import com.huiyan.common.util.SecurityUtils;
import com.huiyan.service.ScreeningService;
import lombok.RequiredArgsConstructor;
import org.springframework.web.bind.annotation.*;

import java.util.Map;

@RestController
@RequestMapping("/api/v1/physical")
@RequiredArgsConstructor
public class PhysicalController {

    private final ScreeningService screeningService;

    @PostMapping("/confirm-report")
    public R<Map<String, Object>> confirmReport(@RequestBody Map<String, Object> req) {
        Object caseIdObj = req.get("caseId") != null ? req.get("caseId") : req.get("case_id");
        if (caseIdObj == null) {
            return R.fail(R.CODE_BAD_REQUEST, "病例ID不能为空");
        }
        Integer caseId = Integer.valueOf(caseIdObj.toString());
        Integer currentUserId = SecurityUtils.getCurrentUserId();
        screeningService.confirmReport(caseId, currentUserId);
        return R.ok(Map.of("caseId", caseId, "confirmed", true), "报告已确认");
    }
}
