package com.huiyan.service;

import com.baomidou.mybatisplus.core.conditions.query.LambdaQueryWrapper;
import com.huiyan.common.exception.BusinessException;
import com.huiyan.common.response.R;
import com.huiyan.entity.CaseImage;
import com.huiyan.entity.User;
import com.huiyan.mapper.CaseImageMapper;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;
import org.springframework.web.multipart.MultipartFile;

import java.io.File;
import java.io.IOException;
import java.time.LocalDateTime;
import java.util.*;

@Slf4j
@Service
@RequiredArgsConstructor
public class CaseImageService {

    private final CaseImageMapper caseImageMapper;

    @Value("${huiyan.upload-dir:app/static}")
    private String uploadDir;

    public Map<String, Object> listGrouped(String caseTable, Integer caseId, List<String> rolesFilter) {
        LambdaQueryWrapper<CaseImage> query = new LambdaQueryWrapper<>();
        query.eq(CaseImage::getCaseTable, caseTable.trim());
        query.eq(CaseImage::getCaseId, caseId);
        if (rolesFilter != null && !rolesFilter.isEmpty()) {
            query.in(CaseImage::getRole, rolesFilter);
        }
        query.orderByAsc(CaseImage::getId);

        List<CaseImage> images = caseImageMapper.selectList(query);

        Map<String, List<CaseImage>> grouped = new LinkedHashMap<>();
        for (CaseImage img : images) {
            String role = img.getRole() != null ? img.getRole() : "other";
            grouped.computeIfAbsent(role, k -> new ArrayList<>()).add(img);
        }

        Map<String, Object> res = new HashMap<>();
        res.put("total", images.size());
        res.put("groups", grouped);
        res.put("items", images);
        return res;
    }

    @Transactional
    public CaseImage addUpload(
            String caseTable, Integer caseId, String role, String eye, MultipartFile file, User user
    ) {
        if (file == null || file.isEmpty()) {
            throw new BusinessException(R.CODE_BAD_REQUEST, "上传文件不能为空");
        }

        File targetDir = new File(uploadDir, "cases/" + caseTable);
        if (!targetDir.exists()) targetDir.mkdirs();

        String originalFilename = file.getOriginalFilename();
        String ext = ".jpg";
        if (originalFilename != null && originalFilename.lastIndexOf(".") != -1) {
            ext = originalFilename.substring(originalFilename.lastIndexOf(".")).toLowerCase();
        }
        String fileName = UUID.randomUUID().toString().replace("-", "") + ext;
        File destFile = new File(targetDir, fileName);

        try {
            file.transferTo(destFile);
        } catch (IOException e) {
            throw new BusinessException(R.CODE_INTERNAL, "保存影像文件失败: " + e.getMessage());
        }

        String fileUrl = "/static/cases/" + caseTable + "/" + fileName;

        CaseImage ci = CaseImage.builder()
                .caseTable(caseTable)
                .caseId(caseId)
                .role(role != null ? role : "original")
                .eye(eye != null ? eye.toUpperCase() : "UK")
                .fileUrl(fileUrl)
                .fileName(originalFilename != null ? originalFilename : fileName)
                .fileSize((int) file.getSize())
                .width(1024)
                .height(1024)
                .uploadedBy(user != null ? user.getId() : 1)
                .build();
        ci.setCreatedAt(LocalDateTime.now());
        ci.setUpdatedAt(LocalDateTime.now());
        caseImageMapper.insert(ci);

        return ci;
    }

    @Transactional
    public void delete(Integer imageId, User user) {
        CaseImage img = caseImageMapper.selectById(imageId);
        if (img == null) {
            throw new BusinessException(R.CODE_NOT_FOUND, "影像不存在：" + imageId);
        }
        caseImageMapper.deleteById(imageId);
    }
}
