package com.huiyan.controller;

import com.huiyan.common.response.PageResult;
import com.huiyan.common.response.R;
import com.huiyan.common.util.SecurityUtils;
import com.huiyan.entity.ScreeningCase;
import com.huiyan.entity.User;
import com.huiyan.service.PatientService;
import com.huiyan.service.ScreeningService;
import lombok.RequiredArgsConstructor;
import org.springframework.http.HttpHeaders;
import org.springframework.http.MediaType;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.*;

import java.net.URLEncoder;
import java.nio.charset.StandardCharsets;
import java.util.Map;

@RestController
@RequestMapping("/api/v1/patient")
@RequiredArgsConstructor
public class PatientController {

    private final PatientService patientService;
    private final ScreeningService screeningService;

    @GetMapping("/my_reports")
    public R<PageResult<ScreeningCase>> myReports(
            @RequestParam(defaultValue = "1") long page,
            @RequestParam(defaultValue = "20") long pageSize,
            @RequestParam(required = false) String status
    ) {
        User user = SecurityUtils.getCurrentUser();
        return R.ok(patientService.myReports(page, pageSize, status, user));
    }

    @GetMapping("/my-reports")
    public R<PageResult<ScreeningCase>> myReportsKebab(
            @RequestParam(defaultValue = "1") long page,
            @RequestParam(defaultValue = "20") long pageSize,
            @RequestParam(required = false) String status
    ) {
        return myReports(page, pageSize, status);
    }

    @GetMapping("/my_reports/{caseId}")
    public R<Map<String, Object>> myReportDetail(@PathVariable Integer caseId) {
        User user = SecurityUtils.getCurrentUser();
        return R.ok(patientService.myReportDetail(caseId, user));
    }

    @PostMapping("/bind_case")
    public R<Void> bindCase(@RequestBody Map<String, Object> req) {
        User user = SecurityUtils.getCurrentUser();
        Integer caseId = Integer.valueOf(req.get("caseId").toString());
        String phone = (String) req.get("phone");
        patientService.bindCase(caseId, phone, user);
        return R.ok(null, "已绑定");
    }

    @GetMapping("/report-pdf/{caseId}")
    public ResponseEntity<byte[]> reportPdf(
            @PathVariable Integer caseId,
            @RequestParam(defaultValue = "inline") String disposition
    ) {
        byte[] pdfBytes = screeningService.getReportPdfBytes(caseId);
        String filename = "report_" + caseId + ".pdf";
        String encodedFilename = URLEncoder.encode(filename, StandardCharsets.UTF_8).replaceAll("\\+", "%20");
        String dispHeader = "attachment".equalsIgnoreCase(disposition) ? "attachment" : "inline";

        return ResponseEntity.ok()
                .header(HttpHeaders.CONTENT_DISPOSITION, dispHeader + "; filename=\"" + filename + "\"; filename*=UTF-8''" + encodedFilename)
                .contentType(MediaType.APPLICATION_PDF)
                .body(pdfBytes);
    }
}
