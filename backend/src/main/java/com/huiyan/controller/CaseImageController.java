package com.huiyan.controller;

import cn.dev33.satoken.stp.StpUtil;
import com.huiyan.common.response.R;
import com.huiyan.common.util.SecurityUtils;
import com.huiyan.entity.CaseImage;
import com.huiyan.entity.User;
import com.huiyan.service.CaseImageService;
import lombok.RequiredArgsConstructor;
import org.springframework.web.bind.annotation.*;
import org.springframework.web.multipart.MultipartFile;

import java.util.*;

@RestController
@RequestMapping("/api/v1/case-images")
@RequiredArgsConstructor
public class CaseImageController {

    private final CaseImageService caseImageService;

    @GetMapping("")
    public R<Map<String, Object>> listCaseImages(
            @RequestParam String caseTable,
            @RequestParam Integer caseId,
            @RequestParam(required = false) String roles
    ) {
        List<String> rolesList = null;
        if (roles != null && !roles.trim().isEmpty()) {
            rolesList = Arrays.stream(roles.split(",")).map(String::trim).filter(s -> !s.isEmpty()).toList();
        }
        return R.ok(caseImageService.listGrouped(caseTable, caseId, rolesList));
    }

    @PostMapping("/upload")
    public R<Map<String, Object>> uploadCaseImage(
            @RequestParam String caseTable,
            @RequestParam Integer caseId,
            @RequestParam String role,
            @RequestParam(defaultValue = "UK") String eye,
            @RequestParam("files") List<MultipartFile> files
    ) {
        User user = SecurityUtils.getCurrentUser();
        List<Map<String, Object>> saved = new ArrayList<>();
        for (MultipartFile f : files) {
            CaseImage img = caseImageService.addUpload(caseTable, caseId, role, eye, f, user);
            saved.add(Map.of(
                    "id", img.getId(),
                    "fileUrl", img.getFileUrl(),
                    "role", img.getRole(),
                    "eye", img.getEye()
            ));
        }
        return R.ok(Map.of("items", saved), "已上传");
    }

    @DeleteMapping("/{imageId}")
    public R<Void> deleteCaseImage(@PathVariable Integer imageId) {
        User user = SecurityUtils.getCurrentUser();
        caseImageService.delete(imageId, user);
        return R.ok(null, "已删除");
    }
}
