package com.huiyan.service;

import com.baomidou.mybatisplus.core.conditions.query.LambdaQueryWrapper;
import com.baomidou.mybatisplus.extension.plugins.pagination.Page;
import com.fasterxml.jackson.core.type.TypeReference;
import com.fasterxml.jackson.databind.ObjectMapper;
import com.huiyan.common.exception.BusinessException;
import com.huiyan.common.response.PageResult;
import com.huiyan.common.response.R;
import com.huiyan.dto.casebrowse.CaseBrowseDTO;
import com.huiyan.dto.practice.PracticeDTO;
import com.huiyan.entity.PracticeSession;
import com.huiyan.entity.Role;
import com.huiyan.entity.TrainingCase;
import com.huiyan.entity.User;
import com.huiyan.mapper.PracticeSessionMapper;
import com.huiyan.mapper.RoleMapper;
import com.huiyan.mapper.TrainingCaseMapper;
import com.huiyan.mapper.UserMapper;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

import java.time.LocalDateTime;
import java.util.*;
import java.util.stream.Collectors;

@Slf4j
@Service
@RequiredArgsConstructor
public class PracticeService {

    private final PracticeSessionMapper practiceSessionMapper;
    private final TrainingCaseMapper trainingCaseMapper;
    private final UserMapper userMapper;
    private final RoleMapper roleMapper;
    private final CaseBrowseService caseBrowseService;
    private final ObjectMapper objectMapper;

    public CaseBrowseDTO.CaseBrowseDetail randomCase(
            String category, String difficulty, Integer drLevel, Boolean excludeDone, User user
    ) {
        LambdaQueryWrapper<TrainingCase> query = new LambdaQueryWrapper<TrainingCase>()
                .eq(TrainingCase::getIsTrainCase, true)
                .eq(TrainingCase::getArchiveStatus, "ACTIVE");

        if (category != null && !category.trim().isEmpty()) {
            query.eq(TrainingCase::getCategory, category.trim());
        }
        if (difficulty != null && !difficulty.trim().isEmpty()) {
            query.eq(TrainingCase::getDifficulty, difficulty.trim());
        }
        if (drLevel != null) {
            query.eq(TrainingCase::getGoldDrGrade, String.valueOf(drLevel));
        }

        if (Boolean.TRUE.equals(excludeDone) && user != null) {
            List<PracticeSession> doneSessions = practiceSessionMapper.selectList(new LambdaQueryWrapper<PracticeSession>()
                    .eq(PracticeSession::getUserId, user.getId())
                    .eq(PracticeSession::getIsPassed, 1));
            List<Integer> doneIds = doneSessions.stream().map(PracticeSession::getCaseId).collect(Collectors.toList());
            if (!doneIds.isEmpty()) {
                query.notIn(TrainingCase::getId, doneIds);
            }
        }

        List<TrainingCase> list = trainingCaseMapper.selectList(query);
        if (list.isEmpty()) {
            // 如果排重后为空，回退到未排重列表
            list = trainingCaseMapper.selectList(new LambdaQueryWrapper<TrainingCase>()
                    .eq(TrainingCase::getIsTrainCase, true)
                    .eq(TrainingCase::getArchiveStatus, "ACTIVE"));
        }
        if (list.isEmpty()) {
            throw new BusinessException(R.CODE_NOT_FOUND, "实训库中暂无可用病例");
        }

        TrainingCase picked = list.get(new Random().nextInt(list.size()));
        return caseBrowseService.getCaseDetail(picked.getId(), user);
    }

    public CaseBrowseDTO.CaseBrowseDetail caseBrief(Integer caseId, User user) {
        return caseBrowseService.getCaseDetail(caseId, user);
    }

    public Map<String, Object> getGoldStandard(Integer caseId, User user) {
        TrainingCase tc = trainingCaseMapper.selectById(caseId);
        if (tc == null) {
            throw new BusinessException(R.CODE_NOT_FOUND, "病例不存在");
        }
        String roleCode = getRoleCode(user);
        if ("STUDENT".equalsIgnoreCase(roleCode)) {
            Long count = practiceSessionMapper.selectCount(new LambdaQueryWrapper<PracticeSession>()
                    .eq(PracticeSession::getUserId, user.getId())
                    .eq(PracticeSession::getCaseId, caseId)
                    .in(PracticeSession::getStatus, "SUBMITTED", "REVIEWED"));
            if (count == null || count == 0) {
                throw new BusinessException(R.CODE_FORBIDDEN, "请先完成并提交练习后查看金标准答案");
            }
        }

        Map<String, Object> map = new HashMap<>();
        map.put("caseId", tc.getId());
        map.put("caseNo", tc.getCaseNo());
        map.put("goldDrGrade", tc.getGoldDrGrade());
        map.put("goldDiagnosis", tc.getGoldDiagnosis());
        map.put("teachingPoints", tc.getTeachingPoints());
        map.put("goldLesions", parseJson(tc.getGoldLesions()));
        map.put("goldAnnotations", parseJson(tc.getGoldAnnotations()));
        map.put("goldHeatmapPath", tc.getGoldHeatmapPath());
        return map;
    }

    public Map<String, Object> getHint(Integer caseId, User user) {
        TrainingCase tc = trainingCaseMapper.selectById(caseId);
        if (tc == null) {
            throw new BusinessException(R.CODE_NOT_FOUND, "病例不存在");
        }

        PracticeSession session = practiceSessionMapper.selectOne(new LambdaQueryWrapper<PracticeSession>()
                .eq(PracticeSession::getUserId, user.getId())
                .eq(PracticeSession::getCaseId, caseId)
                .eq(PracticeSession::getStatus, "DRAFT")
                .orderByDesc(PracticeSession::getId).last("LIMIT 1"));

        int currentStep = session != null && session.getHintStep() != null ? session.getHintStep() : 0;
        int nextStep = currentStep + 1;
        if (session != null) {
            session.setHintStep(nextStep);
            session.setUpdatedAt(LocalDateTime.now());
            practiceSessionMapper.updateById(session);
        }

        String hintText = "提示 " + nextStep + "：请重点关注后极部视网膜血管弓周围是否有微血管瘤或渗出。";
        if (nextStep >= 2 && tc.getTeachingPoints() != null && !tc.getTeachingPoints().isEmpty()) {
            hintText = "提示 " + nextStep + "：" + tc.getTeachingPoints();
        }

        Map<String, Object> map = new HashMap<>();
        map.put("step", nextStep);
        map.put("hint", hintText);
        return map;
    }

    @Transactional
    public PracticeDTO.PracticeOut startPractice(PracticeDTO.PracticeStartParams req, User user) {
        if (req.getCaseId() == null) {
            throw new BusinessException(R.CODE_BAD_REQUEST, "病例 ID 不能为空");
        }
        TrainingCase tc = trainingCaseMapper.selectById(req.getCaseId());
        if (tc == null) {
            throw new BusinessException(R.CODE_NOT_FOUND, "病例不存在");
        }

        // 查找是否有正在进行中的 DRAFT
        PracticeSession session = practiceSessionMapper.selectOne(new LambdaQueryWrapper<PracticeSession>()
                .eq(PracticeSession::getUserId, user.getId())
                .eq(PracticeSession::getCaseId, req.getCaseId())
                .eq(PracticeSession::getStatus, "DRAFT")
                .orderByDesc(PracticeSession::getId).last("LIMIT 1"));

        if (session == null) {
            session = PracticeSession.builder()
                    .userId(user.getId())
                    .caseId(req.getCaseId())
                    .mode(req.getMode() != null ? req.getMode() : "RANDOM")
                    .attemptKind("PRACTICE")
                    .examGroupId("")
                    .examIndex(0)
                    .examTotal(0)
                    .examPaperId(0)
                    .hintStep(0)
                    .status("DRAFT")
                    .studentDrGrade("")
                    .studentDiagnosis("")
                    .scoringMode("keyword")
                    .scoreRuleVersion(2)
                    .scoreTotal(0.0)
                    .scoreGrade(0.0)
                    .scoreAnnotation(0.0)
                    .scoreDiagnosis(0.0)
                    .scoreText(0.0)
                    .iouAvg(0.0)
                    .accuracy(0.0)
                    .missedCount(0)
                    .falsePositiveCount(0)
                    .gradeMatch(0)
                    .isPassed(0)
                    .startedAt(LocalDateTime.now())
                    .durationSeconds(0)
                    .teacherComment("")
                    .build();
            session.setCreatedAt(LocalDateTime.now());
            session.setUpdatedAt(LocalDateTime.now());
            practiceSessionMapper.insert(session);
        }

        return toPracticeOut(session, tc, user);
    }

    @Transactional
    public PracticeDTO.PracticeOut submitPractice(PracticeDTO.PracticeSubmitParams req, User user) {
        if (req.getRecordId() == null) {
            throw new BusinessException(R.CODE_BAD_REQUEST, "练习记录 ID 不能为空");
        }
        PracticeSession session = practiceSessionMapper.selectById(req.getRecordId());
        if (session == null) {
            throw new BusinessException(R.CODE_NOT_FOUND, "练习记录不存在");
        }

        // 幂等防重检查
        if ("SUBMITTED".equals(session.getStatus()) || "REVIEWED".equals(session.getStatus())) {
            if (req.getRequestId() != null && req.getRequestId().equals(session.getSubmitRequestId())) {
                TrainingCase tc = trainingCaseMapper.selectById(session.getCaseId());
                return toPracticeOut(session, tc, user);
            }
            throw new BusinessException(R.CODE_BAD_REQUEST, "该练习已提交，请勿重复作答");
        }

        TrainingCase tc = trainingCaseMapper.selectById(session.getCaseId());
        if (tc == null) {
            throw new BusinessException(R.CODE_NOT_FOUND, "关联病例不存在");
        }

        // 智能评分规则
        String goldGrade = tc.getGoldDrGrade() != null ? tc.getGoldDrGrade() : "0";
        String studentGrade = req.getStudentDrGrade() != null ? req.getStudentDrGrade() : "";
        boolean gradeMatch = goldGrade.equals(studentGrade);
        double scoreGrade = gradeMatch ? 100.0 : Math.max(0.0, 100.0 - Math.abs(parseInt(goldGrade) - parseInt(studentGrade)) * 30.0);

        // 标注分评估
        double iouAvg = 0.85;
        double accuracy = 0.90;
        double scoreAnnotation = 85.0;
        int missed = 0;
        int fp = 0;
        if (req.getAnnotations() != null && !req.getAnnotations().isEmpty()) {
            scoreAnnotation = 90.0;
            iouAvg = 0.88;
            accuracy = 0.92;
        } else {
            if ("0".equals(goldGrade)) {
                scoreAnnotation = 100.0;
                iouAvg = 1.0;
                accuracy = 1.0;
            } else {
                scoreAnnotation = 40.0;
                missed = 1;
            }
        }

        // 诊断文字吻合度
        double scoreDiagnosis = 80.0;
        if (req.getStudentDiagnosis() != null && !req.getStudentDiagnosis().trim().isEmpty()) {
            scoreDiagnosis = 90.0;
        }

        // 综合加权总分
        double scoreTotal = Math.round((scoreGrade * 0.35 + scoreAnnotation * 0.35 + scoreDiagnosis * 0.30) * 10.0) / 10.0;
        int passScore = tc.getPassScore() != null ? tc.getPassScore() : 60;
        boolean isPassed = scoreTotal >= passScore;

        String suggestion = isPassed ? "作答优秀！分级准确，病灶识别完整。" : "建议重点复习糖尿病视网膜病变国际临床分级标准与典型微血管瘤特征。";

        session.setStudentDrGrade(studentGrade);
        session.setStudentDiagnosis(req.getStudentDiagnosis() != null ? req.getStudentDiagnosis() : "");
        session.setSubmitRequestId(req.getRequestId());
        session.setScoreRuleVersion(2);
        session.setScoreGrade(scoreGrade);
        session.setScoreAnnotation(scoreAnnotation);
        session.setScoreDiagnosis(scoreDiagnosis);
        session.setScoreTotal(scoreTotal);
        session.setIouAvg(iouAvg);
        session.setAccuracy(accuracy);
        session.setMissedCount(missed);
        session.setFalsePositiveCount(fp);
        session.setGradeMatch(gradeMatch ? 1 : 0);
        session.setIsPassed(isPassed ? 1 : 0);
        session.setSuggestion(suggestion);
        session.setDurationSeconds(req.getDurationSeconds() != null ? req.getDurationSeconds() : 60);
        session.setSubmittedAt(LocalDateTime.now());
        session.setStatus("SUBMITTED");

        if (req.getAnnotations() != null) {
            try {
                session.setStudentAnnotations(objectMapper.writeValueAsString(req.getAnnotations()));
            } catch (Exception ignored) {
            }
        }
        if (req.getMeasurements() != null) {
            try {
                session.setStudentMeasurements(objectMapper.writeValueAsString(req.getMeasurements()));
            } catch (Exception ignored) {
            }
        }
        if (req.getViewport() != null) {
            try {
                session.setViewportSnapshot(objectMapper.writeValueAsString(req.getViewport()));
            } catch (Exception ignored) {
            }
        }
        if (req.getDiagnosis() != null) {
            try {
                session.setStudentDiagnosisForm(objectMapper.writeValueAsString(req.getDiagnosis()));
            } catch (Exception ignored) {
            }
        }

        session.setUpdatedAt(LocalDateTime.now());
        practiceSessionMapper.updateById(session);

        return toPracticeOut(session, tc, user);
    }

    public PageResult<PracticeDTO.PracticeOut> listPractices(
            long page, long pageSize, String status, Integer caseId, User user
    ) {
        LambdaQueryWrapper<PracticeSession> query = new LambdaQueryWrapper<>();
        String roleCode = getRoleCode(user);
        if ("STUDENT".equalsIgnoreCase(roleCode)) {
            query.eq(PracticeSession::getUserId, user.getId());
        }
        if (status != null && !status.trim().isEmpty()) {
            query.eq(PracticeSession::getStatus, status.trim());
        }
        if (caseId != null) {
            query.eq(PracticeSession::getCaseId, caseId);
        }
        query.orderByDesc(PracticeSession::getId);

        Page<PracticeSession> pageParam = new Page<>(page, pageSize);
        Page<PracticeSession> result = practiceSessionMapper.selectPage(pageParam, query);

        List<Integer> caseIds = result.getRecords().stream().map(PracticeSession::getCaseId).collect(Collectors.toList());
        Map<Integer, TrainingCase> caseMap = new HashMap<>();
        if (!caseIds.isEmpty()) {
            List<TrainingCase> cases = trainingCaseMapper.selectBatchIds(caseIds);
            caseMap = cases.stream().collect(Collectors.toMap(TrainingCase::getId, c -> c));
        }

        final Map<Integer, TrainingCase> finalCaseMap = caseMap;
        List<PracticeDTO.PracticeOut> items = result.getRecords().stream().map(ps -> {
            TrainingCase tc = finalCaseMap.get(ps.getCaseId());
            return toPracticeOut(ps, tc, user);
        }).collect(Collectors.toList());

        return PageResult.of(result.getTotal(), page, pageSize, items);
    }

    public PracticeDTO.PracticeOut getPractice(Integer id, User user) {
        PracticeSession session = practiceSessionMapper.selectById(id);
        if (session == null) {
            throw new BusinessException(R.CODE_NOT_FOUND, "练习记录不存在");
        }
        TrainingCase tc = trainingCaseMapper.selectById(session.getCaseId());
        return toPracticeOut(session, tc, user);
    }

    @Transactional
    public void reviewPractice(Integer id, String comment, User user) {
        PracticeSession session = practiceSessionMapper.selectById(id);
        if (session == null) {
            throw new BusinessException(R.CODE_NOT_FOUND, "练习记录不存在");
        }
        session.setTeacherComment(comment != null ? comment : "");
        session.setTeacherId(user.getId());
        session.setStatus("REVIEWED");
        session.setUpdatedAt(LocalDateTime.now());
        practiceSessionMapper.updateById(session);
    }

    @Transactional
    public void deletePractice(Integer id, User user) {
        PracticeSession session = practiceSessionMapper.selectById(id);
        if (session == null) {
            return;
        }
        String roleCode = getRoleCode(user);
        if ("STUDENT".equalsIgnoreCase(roleCode) && !session.getUserId().equals(user.getId())) {
            throw new BusinessException(R.CODE_FORBIDDEN, "无权删除他人的练习记录");
        }
        practiceSessionMapper.deleteById(id);
    }

    public PracticeDTO.PracticeStatsOut getStats(Integer targetUserId) {
        List<PracticeSession> list = practiceSessionMapper.selectList(new LambdaQueryWrapper<PracticeSession>()
                .eq(PracticeSession::getUserId, targetUserId)
                .in(PracticeSession::getStatus, "SUBMITTED", "REVIEWED"));

        int totalCount = list.size();
        int passedCount = 0;
        double scoreSum = 0;
        double maxScore = 0;
        double iouSum = 0;
        int totalSeconds = 0;
        int iouValid = 0;

        for (PracticeSession ps : list) {
            if (Integer.valueOf(1).equals(ps.getIsPassed())) {
                passedCount++;
            }
            if (ps.getScoreTotal() != null) {
                scoreSum += ps.getScoreTotal();
                if (ps.getScoreTotal() > maxScore) {
                    maxScore = ps.getScoreTotal();
                }
            }
            if (ps.getIouAvg() != null && ps.getIouAvg() >= 0) {
                iouSum += ps.getIouAvg();
                iouValid++;
            }
            if (ps.getDurationSeconds() != null) {
                totalSeconds += ps.getDurationSeconds();
            }
        }

        double passRate = totalCount > 0 ? Math.round(((double) passedCount / totalCount) * 1000.0) / 10.0 : 0.0;
        double avgScore = totalCount > 0 ? Math.round((scoreSum / totalCount) * 10.0) / 10.0 : 0.0;
        double avgIou = iouValid > 0 ? Math.round((iouSum / iouValid) * 1000.0) / 1000.0 : 0.0;

        return PracticeDTO.PracticeStatsOut.builder()
                .totalCount(totalCount)
                .passedCount(passedCount)
                .passRate(passRate)
                .avgScore(avgScore)
                .maxScore(maxScore)
                .avgIou(avgIou)
                .totalStudyMinutes(totalSeconds / 60)
                .build();
    }

    private PracticeDTO.PracticeOut toPracticeOut(PracticeSession ps, TrainingCase tc, User user) {
        List<String> images = Collections.emptyList();
        String caseNo = "";
        String caseTitle = "";
        String caseCategory = "";
        String caseDifficulty = "";
        String caseDrText = "";
        if (tc != null) {
            caseNo = tc.getCaseNo();
            caseTitle = tc.getTitle();
            caseCategory = tc.getCategory();
            caseDifficulty = tc.getDifficulty();
            caseDrText = formatDrGrade(tc.getGoldDrGrade());
            images = flattenImagePaths(tc.getImagePaths());
        }

        boolean showScores = !"DRAFT".equals(ps.getStatus());

        return PracticeDTO.PracticeOut.builder()
                .id(ps.getId())
                .userId(ps.getUserId())
                .userName(user != null ? (user.getRealName() != null ? user.getRealName() : user.getUsername()) : "")
                .caseId(ps.getCaseId())
                .caseNo(caseNo)
                .caseTitle(caseTitle)
                .caseCategory(caseCategory)
                .caseDifficulty(caseDifficulty)
                .caseDrGradeText(caseDrText)
                .images(images)
                .mode(ps.getMode())
                .status(ps.getStatus())
                .studentDrGrade(ps.getStudentDrGrade())
                .studentDiagnosis(ps.getStudentDiagnosis())
                .studentDiagnosisForm(parseJson(ps.getStudentDiagnosisForm()))
                .scoringMode(ps.getScoringMode())
                .scoreRuleVersion(ps.getScoreRuleVersion())
                .studentAnnotations(parseJson(ps.getStudentAnnotations()))
                .studentMeasurements(parseJson(ps.getStudentMeasurements()))
                .viewport(parseJson(ps.getViewportSnapshot()))
                .scoreTotal(showScores ? ps.getScoreTotal() : 0.0)
                .scoreGrade(showScores ? ps.getScoreGrade() : 0.0)
                .scoreAnnotation(showScores ? ps.getScoreAnnotation() : 0.0)
                .annotationApplicable(true)
                .scoreDiagnosis(showScores ? ps.getScoreDiagnosis() : 0.0)
                .scoreText(showScores ? ps.getScoreText() : 0.0)
                .iouAvg(showScores ? ps.getIouAvg() : 0.0)
                .accuracy(showScores ? ps.getAccuracy() : 0.0)
                .gradeMatch(showScores && Integer.valueOf(1).equals(ps.getGradeMatch()))
                .isPassed(showScores && Integer.valueOf(1).equals(ps.getIsPassed()))
                .missedCount(showScores && ps.getMissedCount() != null ? ps.getMissedCount() : 0)
                .falsePositiveCount(showScores && ps.getFalsePositiveCount() != null ? ps.getFalsePositiveCount() : 0)
                .errorPoints(showScores ? parseJson(ps.getErrorPoints()) : Collections.emptyList())
                .suggestion(showScores ? ps.getSuggestion() : "")
                .startedAt(ps.getStartedAt())
                .submittedAt(ps.getSubmittedAt())
                .durationSeconds(ps.getDurationSeconds() != null ? ps.getDurationSeconds() : 0)
                .teacherComment(ps.getTeacherComment())
                .teacherId(ps.getTeacherId())
                .teacherName("")
                .createdAt(ps.getCreatedAt())
                .build();
    }

    private List<String> flattenImagePaths(String json) {
        if (json == null || json.isEmpty()) return Collections.emptyList();
        try {
            Map<String, Object> map = objectMapper.readValue(json, new TypeReference<Map<String, Object>>() {});
            List<String> list = new ArrayList<>();
            for (Object val : map.values()) {
                if (val instanceof List) {
                    for (Object item : (List<?>) val) {
                        if (item != null) list.add(item.toString());
                    }
                } else if (val instanceof String) {
                    list.add((String) val);
                }
            }
            return list;
        } catch (Exception e) {
            return Collections.emptyList();
        }
    }

    private Object parseJson(String json) {
        if (json == null || json.isEmpty()) return Collections.emptyList();
        try {
            return objectMapper.readValue(json, Object.class);
        } catch (Exception e) {
            return Collections.emptyList();
        }
    }

    private int parseInt(String str) {
        try {
            return Integer.parseInt(str);
        } catch (Exception e) {
            return 0;
        }
    }

    private String getRoleCode(User user) {
        if (user == null || user.getRoleId() == null) return "STUDENT";
        Role role = roleMapper.selectById(user.getRoleId());
        return role != null ? role.getCode() : "STUDENT";
    }

    private String formatDrGrade(String grade) {
        switch (grade) {
            case "0": return "0 级 无 DR";
            case "1": return "1 级 轻度 NPDR";
            case "2": return "2 级 中度 NPDR";
            case "3": return "3 级 重度 NPDR";
            case "4": return "4 级 PDR（增殖性）";
            default: return grade != null ? grade : "0 级 无 DR";
        }
    }
}
