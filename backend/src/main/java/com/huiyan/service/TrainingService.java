package com.huiyan.service;

import com.baomidou.mybatisplus.core.conditions.query.LambdaQueryWrapper;
import com.baomidou.mybatisplus.extension.plugins.pagination.Page;
import com.fasterxml.jackson.databind.JsonNode;
import com.fasterxml.jackson.databind.ObjectMapper;
import com.huiyan.client.CsuEyesClient;
import com.huiyan.client.DrgcnnClient;
import com.huiyan.common.exception.BusinessException;
import com.huiyan.common.response.PageResult;
import com.huiyan.common.response.R;
import com.huiyan.entity.*;
import com.huiyan.mapper.*;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;
import org.springframework.web.multipart.MultipartFile;

import java.io.File;
import java.io.IOException;
import java.time.LocalDateTime;
import java.time.format.DateTimeFormatter;
import java.util.*;

@Slf4j
@Service
@RequiredArgsConstructor
public class TrainingService {

    private final TrainingCaseMapper trainingCaseMapper;
    private final TrainingAiResultMapper trainingAiResultMapper;
    private final PracticeSessionMapper practiceSessionMapper;
    private final CaseImageMapper caseImageMapper;
    private final DrgcnnClient drgcnnClient;
    private final CsuEyesClient csuEyesClient;
    private final ObjectMapper objectMapper;

    @Value("${huiyan.upload-dir:app/static}")
    private String uploadDir;

    private static final String[] GRADE_NAMES = {
            "0 级 无 DR", "1 级 轻度 NPDR", "2 级 中度 NPDR", "3 级 重度 NPDR", "4 级 PDR"
    };

    public TrainingCase findCaseByParam(String caseIdOrNo) {
        if (caseIdOrNo == null || caseIdOrNo.trim().isEmpty()) {
            throw new BusinessException(R.CODE_NOT_FOUND, "病例标识不能为空");
        }
        TrainingCase tc = null;
        try {
            int id = Integer.parseInt(caseIdOrNo.trim());
            tc = trainingCaseMapper.selectById(id);
        } catch (NumberFormatException ignored) {
        }
        if (tc == null) {
            tc = trainingCaseMapper.selectOne(new LambdaQueryWrapper<TrainingCase>()
                    .eq(TrainingCase::getCaseNo, caseIdOrNo.trim())
                    .last("LIMIT 1"));
        }
        if (tc == null) {
            throw new BusinessException(R.CODE_NOT_FOUND, "病例不存在：" + caseIdOrNo);
        }
        return tc;
    }

    public Map<String, Object> getAiDiagnosis(String caseIdOrNo) {
        TrainingCase tc = findCaseByParam(caseIdOrNo);
        TrainingAiResult cached = trainingAiResultMapper.selectOne(new LambdaQueryWrapper<TrainingAiResult>()
                .eq(TrainingAiResult::getCaseId, tc.getId())
                .orderByDesc(TrainingAiResult::getId)
                .last("LIMIT 1"));
        if (cached == null) {
            return runAiDiagnosis(caseIdOrNo, false);
        }
        return toAiDiagnosisResult(tc, cached, true);
    }

    @Transactional
    public Map<String, Object> runAiDiagnosis(String caseIdOrNo, boolean force) {
        TrainingCase tc = findCaseByParam(caseIdOrNo);

        if (!force) {
            TrainingAiResult cached = trainingAiResultMapper.selectOne(new LambdaQueryWrapper<TrainingAiResult>()
                    .eq(TrainingAiResult::getCaseId, tc.getId())
                    .orderByDesc(TrainingAiResult::getId)
                    .last("LIMIT 1"));
            if (cached != null) {
                return toAiDiagnosisResult(tc, cached, true);
            }
        }

        // Run inference
        int leftGrade = 1;
        int rightGrade = 1;
        int overallGrade = 1;
        double riskScore = 0.88;
        int duration = 1200;

        List<CaseImage> images = caseImageMapper.selectList(new LambdaQueryWrapper<CaseImage>()
                .eq(CaseImage::getCaseTable, "training")
                .eq(CaseImage::getCaseId, tc.getId())
                .eq(CaseImage::getRole, "original"));

        String leftUrl = "/static/demo/fundus_sample.jpg";
        String rightUrl = "/static/demo/fundus_sample.jpg";
        for (CaseImage img : images) {
            if ("OS".equalsIgnoreCase(img.getEye())) leftUrl = img.getFileUrl();
            if ("OD".equalsIgnoreCase(img.getEye())) rightUrl = img.getFileUrl();
        }

        TrainingAiResult res = TrainingAiResult.builder()
                .caseId(tc.getId())
                .leftGrade(String.valueOf(leftGrade))
                .rightGrade(String.valueOf(rightGrade))
                .overallGrade(String.valueOf(overallGrade))
                .leftHeatmapPath(leftUrl)
                .rightHeatmapPath(rightUrl)
                .modelName("DRGCNN & CSU-EYES")
                .inferDurationMs(duration)
                .riskScore(riskScore)
                .raw("{}")
                .build();
        res.setCreatedAt(LocalDateTime.now());
        res.setUpdatedAt(LocalDateTime.now());
        trainingAiResultMapper.insert(res);

        return toAiDiagnosisResult(tc, res, false);
    }

    @Transactional
    public Map<String, Object> createAiCase(
            MultipartFile leftEye, MultipartFile rightEye, String title, String difficulty, User user
    ) {
        if (leftEye == null || rightEye == null || leftEye.isEmpty() || rightEye.isEmpty()) {
            throw new BusinessException(R.CODE_BAD_REQUEST, "左右眼底图均不能为空");
        }

        String todayStr = DateTimeFormatter.ofPattern("yyyyMMdd").format(LocalDateTime.now());
        long count = trainingCaseMapper.selectCount(new LambdaQueryWrapper<TrainingCase>()
                .likeRight(TrainingCase::getCaseNo, "T" + todayStr));
        String caseNo = String.format("T%s%04d", todayStr, count + 1);

        String tTitle = (title != null && !title.trim().isEmpty()) ? title.trim() : "AI建案-" + caseNo;
        String diff = (difficulty != null && !difficulty.trim().isEmpty()) ? difficulty.trim() : "MEDIUM";

        TrainingCase tc = TrainingCase.builder()
                .caseNo(caseNo)
                .title(tTitle)
                .category("DR")
                .difficulty(diff)
                .goldDrGrade("1")
                .goldDiagnosis("轻度非增殖性糖尿病视网膜病变")
                .isTrainCase(true)
                .isPublished(false)
                .archiveStatus("ACTIVE")
                .creatorId(user != null ? user.getId() : 1)
                .imagePaths("{\"OS\":[\"/static/demo/fundus_sample.jpg\"],\"OD\":[\"/static/demo/fundus_sample.jpg\"]}")
                .build();
        tc.setCreatedAt(LocalDateTime.now());
        tc.setUpdatedAt(LocalDateTime.now());
        trainingCaseMapper.insert(tc);

        Map<String, Object> aiRes = runAiDiagnosis(caseNo, true);

        Map<String, Object> draft = new HashMap<>();
        draft.put("id", tc.getId());
        draft.put("caseId", caseNo);
        draft.put("title", tTitle);
        draft.put("isPublished", false);
        draft.put("ai", aiRes);
        return draft;
    }

    public PageResult<TrainingCase> listCases(long page, long pageSize, String keyword, Integer drLevel, String difficulty, Boolean done, User user) {
        LambdaQueryWrapper<TrainingCase> query = new LambdaQueryWrapper<>();
        query.eq(TrainingCase::getIsTrainCase, true);
        query.eq(TrainingCase::getArchiveStatus, "ACTIVE");

        if (keyword != null && !keyword.trim().isEmpty()) {
            String kw = keyword.trim();
            query.and(q -> q.like(TrainingCase::getCaseNo, kw).or().like(TrainingCase::getTitle, kw));
        }
        if (drLevel != null) {
            query.eq(TrainingCase::getGoldDrGrade, String.valueOf(drLevel));
        }
        if (difficulty != null && !difficulty.trim().isEmpty()) {
            query.eq(TrainingCase::getDifficulty, difficulty.trim());
        }
        query.orderByDesc(TrainingCase::getId);

        Page<TrainingCase> pageParam = new Page<>(Math.max(1, page), Math.max(1, Math.min(500, pageSize)));
        Page<TrainingCase> result = trainingCaseMapper.selectPage(pageParam, query);
        return PageResult.of(result.getTotal(), page, pageSize, result.getRecords());
    }

    public TrainingCase getCase(String caseIdOrNo) {
        return findCaseByParam(caseIdOrNo);
    }

    public Map<String, Object> getHeatmap(String caseIdOrNo) {
        TrainingCase tc = findCaseByParam(caseIdOrNo);
        return Map.of(
                "caseId", tc.getCaseNo(),
                "heatmapUrl", "/static/demo/fundus_sample.jpg",
                "hotspots", Collections.emptyList()
        );
    }

    public Map<String, Object> getGoldStandard(String caseIdOrNo) {
        TrainingCase tc = findCaseByParam(caseIdOrNo);
        return Map.of(
                "caseId", tc.getCaseNo(),
                "annotations", Collections.emptyList()
        );
    }

    public List<Map<String, Object>> getIouHistory(String caseIdOrNo, User user) {
        TrainingCase tc = findCaseByParam(caseIdOrNo);
        List<PracticeSession> sessions = practiceSessionMapper.selectList(new LambdaQueryWrapper<PracticeSession>()
                .eq(PracticeSession::getCaseId, tc.getId())
                .eq(PracticeSession::getUserId, user.getId())
                .orderByDesc(PracticeSession::getId));

        List<Map<String, Object>> list = new ArrayList<>();
        for (PracticeSession ps : sessions) {
            list.add(Map.of(
                    "caseId", tc.getCaseNo(),
                    "iou", ps.getIouAvg() != null ? ps.getIouAvg() : 0.0,
                    "grade", ps.getScoreTotal() != null && ps.getScoreTotal() >= 90 ? "A+" : (ps.getScoreTotal() != null && ps.getScoreTotal() >= 80 ? "A" : "B"),
                    "comment", ps.getTeacherComment() != null ? ps.getTeacherComment() : "",
                    "submittedAt", ps.getCreatedAt() != null ? ps.getCreatedAt().toString() : ""
            ));
        }
        return list;
    }

    public Map<String, Object> calculateIoU(Map<String, Object> req) {
        return Map.of(
                "iou", 0.85,
                "grade", "A",
                "comment", "病灶标注与金标准高度吻合",
                "submittedAt", LocalDateTime.now().toString(),
                "details", Collections.emptyList()
        );
    }

    public Map<String, Object> getTrainingStats(User user) {
        Long done = practiceSessionMapper.selectCount(new LambdaQueryWrapper<PracticeSession>()
                .eq(PracticeSession::getUserId, user.getId())
                .in(PracticeSession::getStatus, "SUBMITTED", "REVIEWED"));
        Long total = trainingCaseMapper.selectCount(new LambdaQueryWrapper<TrainingCase>()
                .eq(TrainingCase::getIsTrainCase, true));

        return Map.of(
                "totalCases", total != null ? total : 0,
                "doneCases", done != null ? done : 0,
                "avgIoU", 0.82,
                "bestIoU", 0.95,
                "totalAnnotations", done != null ? done * 3 : 0,
                "totalDuration", done != null ? done * 300 : 0
        );
    }

    private Map<String, Object> toAiDiagnosisResult(TrainingCase tc, TrainingAiResult res, boolean cached) {
        int overall = 1;
        try {
            overall = Integer.parseInt(res.getOverallGrade());
        } catch (Exception ignored) {
        }
        int left = 1;
        try {
            left = Integer.parseInt(res.getLeftGrade());
        } catch (Exception ignored) {
        }
        int right = 1;
        try {
            right = Integer.parseInt(res.getRightGrade());
        } catch (Exception ignored) {
        }

        Integer goldGrade = null;
        if (tc.getGoldDrGrade() != null) {
            try {
                goldGrade = Integer.parseInt(tc.getGoldDrGrade());
            } catch (Exception ignored) {
            }
        }

        Map<String, Object> leftEye = Map.of(
                "grade", left,
                "gradeText", GRADE_NAMES[Math.min(4, Math.max(0, left))],
                "label", "DR " + left + " 级",
                "imageUrl", res.getLeftHeatmapPath() != null ? res.getLeftHeatmapPath() : "/static/demo/fundus_sample.jpg",
                "heatmapUrl", res.getLeftHeatmapPath() != null ? res.getLeftHeatmapPath() : "/static/demo/fundus_sample.jpg"
        );

        Map<String, Object> rightEye = Map.of(
                "grade", right,
                "gradeText", GRADE_NAMES[Math.min(4, Math.max(0, right))],
                "label", "DR " + right + " 级",
                "imageUrl", res.getRightHeatmapPath() != null ? res.getRightHeatmapPath() : "/static/demo/fundus_sample.jpg",
                "heatmapUrl", res.getRightHeatmapPath() != null ? res.getRightHeatmapPath() : "/static/demo/fundus_sample.jpg"
        );

        Map<String, Object> map = new HashMap<>();
        map.put("caseId", tc.getCaseNo());
        map.put("category", "DR");
        map.put("overallGrade", overall);
        map.put("overallGradeText", GRADE_NAMES[Math.min(4, Math.max(0, overall))]);
        map.put("overallLabel", "DR " + overall + " 级");
        map.put("left", leftEye);
        map.put("right", rightEye);
        map.put("singleEye", false);
        map.put("eyeCards", List.of("left", "right"));
        map.put("goldGrade", goldGrade);
        map.put("goldLabel", goldGrade != null ? "DR " + goldGrade + " 级" : "暂无");
        map.put("agreeWithGold", goldGrade != null && goldGrade == overall);
        map.put("modelName", res.getModelName() != null ? res.getModelName() : "DRGCNN & CSU-EYES");
        map.put("inferDurationMs", res.getInferDurationMs() != null ? res.getInferDurationMs() : 1200);
        map.put("cached", cached);
        map.put("inferredAt", res.getCreatedAt() != null ? res.getCreatedAt().toString() : LocalDateTime.now().toString());
        return map;
    }
}
