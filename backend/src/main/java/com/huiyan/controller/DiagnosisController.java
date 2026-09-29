package com.huiyan.controller;

import cn.dev33.satoken.stp.StpUtil;
import com.huiyan.common.response.R;
import com.huiyan.common.util.SecurityUtils;
import com.huiyan.dto.diagnosis.DiagnosisDTO;
import com.huiyan.entity.User;
import com.huiyan.service.DiagnosisService;
import lombok.RequiredArgsConstructor;
import org.springframework.web.bind.annotation.*;
import org.springframework.web.multipart.MultipartFile;

import java.util.List;

@RestController
@RequestMapping("/api/v1/diagnosis")
@RequiredArgsConstructor
public class DiagnosisController {

    private final DiagnosisService diagnosisService;

    @PostMapping("/ma")
    public R<DiagnosisDTO.DiagnosisOut> diagnoseMa(
            @RequestParam("file") MultipartFile file,
            @RequestParam(defaultValue = "UK") String eye,
            @RequestParam(value = "model_id", required = false) Integer modelId
    ) {
        checkTeacherOrAdmin();
        User user = SecurityUtils.getCurrentUser();
        DiagnosisDTO.DiagnosisOut out = diagnosisService.diagnoseMa(file, eye, modelId, user);
        return R.ok(out, "MA 检测完成：检出 " + (out.getMa() != null ? out.getMa().getMaCount() : 0) + " 个微动脉瘤");
    }

    @PostMapping("/dr")
    public R<DiagnosisDTO.DiagnosisOut> diagnoseDr(
            @RequestParam("left_eye") MultipartFile leftEye,
            @RequestParam("right_eye") MultipartFile rightEye,
            @RequestParam(value = "model_id", required = false) Integer modelId
    ) {
        checkTeacherOrAdmin();
        User user = SecurityUtils.getCurrentUser();
        DiagnosisDTO.DiagnosisOut out = diagnosisService.diagnoseDr(leftEye, rightEye, modelId, user);
        return R.ok(out, "DR 分级完成：综合 " + (out.getDr() != null ? out.getDr().getOverallGrade() : 0) + " 级");
    }

    @PostMapping("/comprehensive")
    public R<DiagnosisDTO.DiagnosisOut> diagnoseComprehensive(
            @RequestParam("file") MultipartFile file,
            @RequestParam(required = false) List<String> tasks
    ) {
        checkTeacherOrAdmin();
        User user = SecurityUtils.getCurrentUser();
        DiagnosisDTO.DiagnosisOut out = diagnosisService.diagnoseComprehensive(file, tasks, user);
        return R.ok(out, "综合诊断完成");
    }

    private void checkTeacherOrAdmin() {
        if (!StpUtil.hasRole("TEACHER") && !StpUtil.hasRole("ADMIN")) {
            StpUtil.checkRole("ADMIN"); // Throws NotRoleException
        }
    }
}
