package com.huiyan.service;

import com.baomidou.mybatisplus.core.conditions.query.LambdaQueryWrapper;
import com.baomidou.mybatisplus.extension.plugins.pagination.Page;
import com.fasterxml.jackson.core.type.TypeReference;
import com.fasterxml.jackson.databind.ObjectMapper;
import com.huiyan.common.exception.BusinessException;
import com.huiyan.common.response.PageResult;
import com.huiyan.common.response.R;
import com.huiyan.dto.teaching.TeachingDTO;
import com.huiyan.entity.CaseImage;
import com.huiyan.entity.TeachingShare;
import com.huiyan.entity.TrainingCase;
import com.huiyan.entity.User;
import com.huiyan.mapper.CaseImageMapper;
import com.huiyan.mapper.TeachingShareMapper;
import com.huiyan.mapper.TrainingCaseMapper;
import com.huiyan.mapper.UserMapper;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

import java.time.LocalDateTime;
import java.util.*;

@Slf4j
@Service
@RequiredArgsConstructor
public class TeachingService {

    private final TeachingShareMapper teachingShareMapper;
    private final TrainingCaseMapper trainingCaseMapper;
    private final CaseImageMapper caseImageMapper;
    private final UserMapper userMapper;
    private final ObjectMapper objectMapper;

    @Transactional
    public TeachingShare createShare(Map<String, Object> params, User user) {
        Integer caseId = (Integer) params.get("sourceCaseId");
        if (caseId == null) caseId = (Integer) params.get("caseId");
        if (caseId == null) {
            throw new BusinessException(R.CODE_BAD_REQUEST, "来源病例 ID 不能为空");
        }

        String sourceType = (String) params.getOrDefault("sourceType", "TRAINING");
        String shareScope = (String) params.getOrDefault("shareScope", "ALL");
        String scopeValue = (String) params.getOrDefault("scopeValue", "");
        Integer expireHours = (Integer) params.getOrDefault("expireHours", 24);

        Map<String, Object> desensitized = buildCaseSnapshot(sourceType, caseId, params);

        String desensitizedJson = "";
        try {
            desensitizedJson = objectMapper.writeValueAsString(desensitized);
        } catch (Exception ignored) {
        }

        TeachingShare share = TeachingShare.builder()
                .shareType("TEMPORARY")
                .sourceType(sourceType)
                .sourceCaseId(caseId)
                .teachingCaseId(null)
                .desensitizedData(desensitizedJson)
                .shareScope(shareScope)
                .scopeValue(scopeValue)
                .audienceIds("[]")
                .expireHours(expireHours)
                .expiredAt(LocalDateTime.now().plusHours(expireHours))
                .answersRevealed(false)
                .status("SHARING")
                .teacherId(user.getId())
                .reviewComment("")
                .build();
        share.setCreatedAt(LocalDateTime.now());
        share.setUpdatedAt(LocalDateTime.now());
        teachingShareMapper.insert(share);
        return share;
    }

    @Transactional
    public TeachingShare revealShare(Integer shareId, User user) {
        TeachingShare share = teachingShareMapper.selectById(shareId);
        if (share == null) throw new BusinessException(R.CODE_NOT_FOUND, "分享不存在");
        share.setAnswersRevealed(true);
        share.setUpdatedAt(LocalDateTime.now());
        teachingShareMapper.updateById(share);
        return share;
    }

    @Transactional
    public TeachingShare revokeShare(Integer shareId, User user) {
        TeachingShare share = teachingShareMapper.selectById(shareId);
        if (share == null) throw new BusinessException(R.CODE_NOT_FOUND, "分享不存在");
        share.setStatus("REVOKED");
        share.setUpdatedAt(LocalDateTime.now());
        teachingShareMapper.updateById(share);
        return share;
    }

    @Transactional
    public TeachingShare submitForReview(Map<String, Object> params, User user) {
        Integer caseId = (Integer) params.get("sourceCaseId");
        if (caseId == null) caseId = (Integer) params.get("caseId");
        if (caseId == null) {
            throw new BusinessException(R.CODE_BAD_REQUEST, "来源病例 ID 不能为空");
        }

        String sourceType = (String) params.getOrDefault("sourceType", "TRAINING");
        Map<String, Object> desensitized = buildCaseSnapshot(sourceType, caseId, params);

        String desensitizedJson = "{}";
        try {
            desensitizedJson = objectMapper.writeValueAsString(desensitized);
        } catch (Exception ignored) {
        }

        TeachingShare share = TeachingShare.builder()
                .shareType("PERMANENT")
                .sourceType(sourceType)
                .sourceCaseId(caseId)
                .teachingCaseId(null)
                .desensitizedData(desensitizedJson)
                .shareScope("ALL")
                .scopeValue("")
                .audienceIds("[]")
                .expireHours(0)
                .expiredAt(null)
                .answersRevealed(true)
                .status("PENDING")
                .teacherId(user.getId())
                .reviewComment("")
                .build();
        share.setCreatedAt(LocalDateTime.now());
        share.setUpdatedAt(LocalDateTime.now());
        teachingShareMapper.insert(share);
        return share;
    }

    public PageResult<TeachingDTO.TeachingShareOut> listMyShares(long page, long pageSize, String shareType, String status, User user) {
        LambdaQueryWrapper<TeachingShare> query = new LambdaQueryWrapper<TeachingShare>()
                .eq(TeachingShare::getTeacherId, user.getId());
        if (shareType != null && !shareType.trim().isEmpty()) {
            query.eq(TeachingShare::getShareType, shareType.trim());
        }
        if (status != null && !status.trim().isEmpty()) {
            query.eq(TeachingShare::getStatus, status.trim());
        }
        query.orderByDesc(TeachingShare::getId);

        Page<TeachingShare> pageParam = new Page<>(page, pageSize);
        Page<TeachingShare> result = teachingShareMapper.selectPage(pageParam, query);
        List<TeachingDTO.TeachingShareOut> outList = result.getRecords().stream()
                .map(this::toTeachingShareOut)
                .toList();
        return PageResult.of(result.getTotal(), page, pageSize, outList);
    }

    public PageResult<TeachingDTO.StudentCaseOut> listForStudent(long page, long pageSize, User user) {
        LocalDateTime now = LocalDateTime.now();
        LambdaQueryWrapper<TeachingShare> query = new LambdaQueryWrapper<TeachingShare>()
                .and(w -> w
                        .and(sub -> sub
                                .eq(TeachingShare::getShareType, "TEMPORARY")
                                .eq(TeachingShare::getStatus, "SHARING")
                                .gt(TeachingShare::getExpiredAt, now)
                        )
                        .or(sub -> sub
                                .eq(TeachingShare::getShareType, "PERMANENT")
                                .eq(TeachingShare::getStatus, "APPROVED")
                        )
                )
                .orderByDesc(TeachingShare::getId);

        List<TeachingShare> allShares = teachingShareMapper.selectList(query);
        List<TeachingShare> filtered = allShares.stream()
                .filter(s -> shareReaches(s, user))
                .toList();

        long total = filtered.size();
        long fromIndex = (page - 1) * pageSize;
        List<TeachingDTO.StudentCaseOut> list = new ArrayList<>();
        if (fromIndex < total) {
            long toIndex = Math.min(fromIndex + pageSize, total);
            for (int i = (int) fromIndex; i < (int) toIndex; i++) {
                list.add(toStudentCaseOut(filtered.get(i)));
            }
        }
        return PageResult.of(total, page, pageSize, list);
    }

    public TeachingDTO.StudentCaseOut getStudentCaseDetail(Integer shareId, User user) {
        TeachingShare share = teachingShareMapper.selectById(shareId);
        if (share == null) {
            throw new BusinessException(R.CODE_NOT_FOUND, "演示病例不存在");
        }
        if (!shareReaches(share, user)) {
            throw new BusinessException(R.CODE_FORBIDDEN, "该病例暂未向您开放");
        }
        return toStudentCaseOut(share);
    }

    public PageResult<TeachingDTO.TeachingShareOut> listForAdmin(long page, long pageSize, String status, String keyword) {
        LambdaQueryWrapper<TeachingShare> query = new LambdaQueryWrapper<>();
        if (status != null && !status.trim().isEmpty()) {
            query.eq(TeachingShare::getStatus, status.trim());
        }
        query.orderByDesc(TeachingShare::getId);

        Page<TeachingShare> pageParam = new Page<>(page, pageSize);
        Page<TeachingShare> result = teachingShareMapper.selectPage(pageParam, query);
        List<TeachingDTO.TeachingShareOut> outList = result.getRecords().stream()
                .map(this::toTeachingShareOut)
                .toList();
        return PageResult.of(result.getTotal(), page, pageSize, outList);
    }

    @Transactional
    public TeachingShare review(Integer shareId, String status, String comment, User reviewer) {
        TeachingShare share = teachingShareMapper.selectById(shareId);
        if (share == null) throw new BusinessException(R.CODE_NOT_FOUND, "申请记录不存在");
        share.setStatus("APPROVED".equalsIgnoreCase(status) ? "APPROVED" : "REJECTED");
        share.setReviewComment(comment != null ? comment : "");
        share.setReviewerId(reviewer.getId());
        share.setReviewedAt(LocalDateTime.now());
        share.setUpdatedAt(LocalDateTime.now());
        teachingShareMapper.updateById(share);
        return share;
    }

    @Transactional
    public TeachingShare shelve(Integer shareId, User user) {
        TeachingShare share = teachingShareMapper.selectById(shareId);
        if (share == null) throw new BusinessException(R.CODE_NOT_FOUND, "记录不存在");
        share.setStatus("SHELVED");
        share.setUpdatedAt(LocalDateTime.now());
        teachingShareMapper.updateById(share);
        return share;
    }

    public TeachingDTO.ShareTargetsOut shareTargets() {
        Set<String> years = new TreeSet<>();
        Set<String> batches = new TreeSet<>();
        Set<String> groups = new TreeSet<>();
        List<TeachingDTO.ShareStudentOut> students = new ArrayList<>();

        List<User> userList = userMapper.selectList(new LambdaQueryWrapper<User>()
                .and(w -> w.eq(User::getUserType, "student").or().eq(User::getRoleId, 1))
                .orderByAsc(User::getStudyYear)
                .orderByAsc(User::getRealName));

        for (User u : userList) {
            String y = u.getStudyYear() != null ? u.getStudyYear().trim() : "";
            String b = u.getRotationBatch() != null ? u.getRotationBatch().trim() : "";
            String g = u.getMentorGroup() != null ? u.getMentorGroup().trim() : "";
            if (!y.isEmpty()) years.add(y);
            if (!b.isEmpty()) batches.add(b);
            if (!g.isEmpty()) groups.add(g);
            students.add(TeachingDTO.ShareStudentOut.builder()
                    .id(u.getId())
                    .name(u.getRealName() != null ? u.getRealName() : u.getUsername())
                    .studyYear(y)
                    .rotationBatch(b)
                    .mentorGroup(g)
                    .build());
        }
        return TeachingDTO.ShareTargetsOut.builder()
                .years(new ArrayList<>(years))
                .batches(new ArrayList<>(batches))
                .groups(new ArrayList<>(groups))
                .students(students)
                .build();
    }

    // ============================================================
    // 核心转换与数据构建 Helper
    // ============================================================

    public TeachingDTO.StudentCaseOut toStudentCaseOut(TeachingShare share) {
        Map<String, Object> snapshot = new HashMap<>();
        if (share.getDesensitizedData() != null && !share.getDesensitizedData().isEmpty()) {
            try {
                snapshot = objectMapper.readValue(share.getDesensitizedData(), new TypeReference<Map<String, Object>>() {});
            } catch (Exception ignored) {
            }
        }

        TrainingCase tc = null;
        if ("TRAINING".equalsIgnoreCase(share.getSourceType())) {
            if (share.getTeachingCaseId() != null) {
                tc = trainingCaseMapper.selectById(share.getTeachingCaseId());
            }
            if (tc == null && share.getSourceCaseId() != null) {
                tc = trainingCaseMapper.selectById(share.getSourceCaseId());
            }
        }

        boolean revealed = !"TEMPORARY".equalsIgnoreCase(share.getShareType())
                || (share.getAnswersRevealed() != null && share.getAnswersRevealed());

        String title = (String) snapshot.getOrDefault("title", "");
        if ((title == null || title.isEmpty()) && tc != null) {
            title = tc.getTitle();
        }
        if (!revealed) {
            String caseNo = tc != null && tc.getCaseNo() != null ? tc.getCaseNo() : "";
            title = ("课堂病例 " + caseNo).trim();
        }

        String desc = (String) snapshot.getOrDefault("description", "");
        if ((desc == null || desc.isEmpty()) && tc != null) {
            desc = tc.getDescription();
        }
        if (!revealed) {
            desc = "";
        }

        String clinicalInfo = (String) snapshot.getOrDefault("clinical_info", "");
        if ((clinicalInfo == null || clinicalInfo.isEmpty()) && tc != null) {
            clinicalInfo = tc.getClinicalInfo();
        }
        if (!revealed) {
            clinicalInfo = "";
        }

        String category = (String) snapshot.getOrDefault("category", "");
        if ((category == null || category.isEmpty()) && tc != null) {
            category = tc.getCategory();
        }

        String difficulty = (String) snapshot.getOrDefault("difficulty", "");
        if ((difficulty == null || difficulty.isEmpty()) && tc != null) {
            difficulty = tc.getDifficulty();
        }

        String teachingPoints = (String) snapshot.getOrDefault("teaching_points", "");
        if (tc != null && tc.getTeachingPoints() != null && !tc.getTeachingPoints().trim().isEmpty()) {
            teachingPoints = tc.getTeachingPoints();
        }
        if (!revealed) {
            teachingPoints = "";
        }

        String goldDiagnosis = (String) snapshot.getOrDefault("gold_diagnosis", "");
        if (tc != null && tc.getGoldDiagnosis() != null && !tc.getGoldDiagnosis().trim().isEmpty()) {
            goldDiagnosis = tc.getGoldDiagnosis();
        }
        if (!revealed) {
            goldDiagnosis = "";
        }

        String goldDrGrade = (String) snapshot.getOrDefault("gold_dr_grade", "");
        if (tc != null && tc.getGoldDrGrade() != null && !tc.getGoldDrGrade().trim().isEmpty()) {
            goldDrGrade = tc.getGoldDrGrade();
        }
        String goldGradeText = revealed ? getGoldGradeText(category, goldDrGrade) : "";

        Object rawLesions = tc != null && tc.getGoldLesions() != null ? tc.getGoldLesions() : snapshot.get("gold_lesions");
        List<Map<String, Object>> lesions = revealed ? formatLesions(rawLesions) : Collections.emptyList();

        Object rawAnnotations = tc != null && tc.getGoldAnnotations() != null ? tc.getGoldAnnotations() : snapshot.get("gold_annotations");
        List<Object> annotations = revealed ? parseAnnotations(rawAnnotations) : Collections.emptyList();

        String maskUrl = (revealed && tc != null) ? getLesionMaskUrl(tc.getId()) : "";

        Map<String, Object> imagePaths = null;
        if (tc != null && tc.getImagePaths() != null && !tc.getImagePaths().isEmpty()) {
            try {
                imagePaths = objectMapper.readValue(tc.getImagePaths(), new TypeReference<Map<String, Object>>() {});
            } catch (Exception ignored) {
            }
        }
        if (imagePaths == null && snapshot.get("image_paths") instanceof Map) {
            imagePaths = (Map<String, Object>) snapshot.get("image_paths");
        }
        int imageCount = countDistinctImages(imagePaths);

        String teacherName = "";
        if (share.getTeacherId() != null) {
            User t = userMapper.selectById(share.getTeacherId());
            if (t != null) {
                teacherName = t.getRealName() != null ? t.getRealName() : t.getUsername();
            }
        }

        return TeachingDTO.StudentCaseOut.builder()
                .id(share.getId())
                .shareType(share.getShareType())
                .title(title)
                .description(desc)
                .patientAge(null)
                .patientGender("U")
                .clinicalInfo(clinicalInfo)
                .category(category)
                .difficulty(difficulty)
                .imagePaths(imagePaths)
                .imageCount(imageCount)
                .teacherName(teacherName)
                .teachingPoints(teachingPoints)
                .goldDiagnosis(goldDiagnosis)
                .goldGradeText(goldGradeText)
                .categoryText(getCategoryText(category))
                .difficultyText(getDifficultyText(difficulty))
                .lesions(lesions)
                .annotations(annotations)
                .lesionMaskUrl(maskUrl)
                .answersRevealed(revealed)
                .expiredAt(share.getExpiredAt())
                .teachingCaseId(share.getTeachingCaseId())
                .build();
    }

    public TeachingDTO.TeachingShareOut toTeachingShareOut(TeachingShare share) {
        Map<String, Object> data = new HashMap<>();
        if (share.getDesensitizedData() != null && !share.getDesensitizedData().isEmpty()) {
            try {
                data = objectMapper.readValue(share.getDesensitizedData(), new TypeReference<Map<String, Object>>() {});
            } catch (Exception ignored) {
            }
        }
        enrichDemoFields(share, data);

        String teacherName = "";
        if (share.getTeacherId() != null) {
            User t = userMapper.selectById(share.getTeacherId());
            if (t != null) teacherName = t.getRealName() != null ? t.getRealName() : t.getUsername();
        }
        String reviewerName = "";
        if (share.getReviewerId() != null) {
            User r = userMapper.selectById(share.getReviewerId());
            if (r != null) reviewerName = r.getRealName() != null ? r.getRealName() : r.getUsername();
        }
        List<Integer> audienceIds = new ArrayList<>();
        if (share.getAudienceIds() != null && !share.getAudienceIds().isEmpty()) {
            try {
                audienceIds = objectMapper.readValue(share.getAudienceIds(), new TypeReference<List<Integer>>() {});
            } catch (Exception ignored) {
            }
        }

        boolean answersRevealed = !"TEMPORARY".equalsIgnoreCase(share.getShareType())
                || (share.getAnswersRevealed() != null && share.getAnswersRevealed());

        return TeachingDTO.TeachingShareOut.builder()
                .id(share.getId())
                .shareType(share.getShareType())
                .sourceType(share.getSourceType())
                .sourceCaseId(share.getSourceCaseId())
                .teachingCaseId(share.getTeachingCaseId())
                .desensitizedData(data)
                .shareScope(share.getShareScope() != null ? share.getShareScope() : "ALL")
                .scopeValue(share.getScopeValue() != null ? share.getScopeValue() : "")
                .audienceIds(audienceIds)
                .audienceLabel("")
                .expireHours(share.getExpireHours() != null ? share.getExpireHours() : 24)
                .expiredAt(share.getExpiredAt())
                .status(share.getStatus())
                .reviewComment(share.getReviewComment() != null ? share.getReviewComment() : "")
                .reviewedAt(share.getReviewedAt())
                .reviewerName(reviewerName)
                .teacherId(share.getTeacherId())
                .teacherName(teacherName)
                .answersRevealed(answersRevealed)
                .createdAt(share.getCreatedAt())
                .updatedAt(share.getUpdatedAt())
                .build();
    }

    private void enrichDemoFields(TeachingShare share, Map<String, Object> data) {
        TrainingCase tc = null;
        if ("TRAINING".equalsIgnoreCase(share.getSourceType())) {
            if (share.getTeachingCaseId() != null) {
                tc = trainingCaseMapper.selectById(share.getTeachingCaseId());
            }
            if (tc == null && share.getSourceCaseId() != null) {
                tc = trainingCaseMapper.selectById(share.getSourceCaseId());
            }
        }
        if (tc != null) {
            if (!data.containsKey("title") || data.get("title") == null || ((String) data.get("title")).isEmpty()) {
                data.put("title", tc.getTitle());
            }
            if (tc.getTeachingPoints() != null && !tc.getTeachingPoints().trim().isEmpty()) {
                data.put("teaching_points", tc.getTeachingPoints());
                data.put("teachingPoints", tc.getTeachingPoints());
            }
            if (tc.getGoldDiagnosis() != null && !tc.getGoldDiagnosis().trim().isEmpty()) {
                data.put("gold_diagnosis", tc.getGoldDiagnosis());
                data.put("goldDiagnosis", tc.getGoldDiagnosis());
            }
            if (tc.getCategory() != null) {
                data.put("category", tc.getCategory());
                data.put("category_text", getCategoryText(tc.getCategory()));
                data.put("categoryText", getCategoryText(tc.getCategory()));
            }
            if (tc.getDifficulty() != null) {
                data.put("difficulty", tc.getDifficulty());
                data.put("difficulty_text", getDifficultyText(tc.getDifficulty()));
                data.put("difficultyText", getDifficultyText(tc.getDifficulty()));
            }
            if (tc.getGoldDrGrade() != null) {
                data.put("gold_dr_grade", tc.getGoldDrGrade());
                data.put("gold_grade_text", getGoldGradeText(tc.getCategory(), tc.getGoldDrGrade()));
                data.put("goldGradeText", getGoldGradeText(tc.getCategory(), tc.getGoldDrGrade()));
            }
            if (tc.getClinicalInfo() != null) {
                data.put("clinical_info", tc.getClinicalInfo());
                data.put("clinicalInfo", tc.getClinicalInfo());
            }
            if (tc.getImagePaths() != null) {
                try {
                    Object paths = objectMapper.readValue(tc.getImagePaths(), Object.class);
                    data.put("image_paths", paths);
                    data.put("imagePaths", paths);
                } catch (Exception ignored) {
                }
            }
            data.put("lesion_mask_url", getLesionMaskUrl(tc.getId()));
            data.put("lesionMaskUrl", getLesionMaskUrl(tc.getId()));
        }
    }

    private Map<String, Object> buildCaseSnapshot(String sourceType, Integer caseId, Map<String, Object> params) {
        Map<String, Object> desensitized = new HashMap<>();
        desensitized.put("caseId", caseId);
        desensitized.put("title", params.getOrDefault("title", "教学分享病例"));
        if ("TRAINING".equalsIgnoreCase(sourceType)) {
            TrainingCase tc = trainingCaseMapper.selectById(caseId);
            if (tc != null) {
                desensitized.put("title", tc.getTitle());
                desensitized.put("description", tc.getDescription());
                desensitized.put("patient_age", tc.getPatientAge());
                desensitized.put("patient_gender", tc.getPatientGender());
                desensitized.put("clinical_info", tc.getClinicalInfo());
                desensitized.put("teaching_points", tc.getTeachingPoints());
                desensitized.put("category", tc.getCategory());
                desensitized.put("difficulty", tc.getDifficulty());
                desensitized.put("gold_dr_grade", tc.getGoldDrGrade());
                desensitized.put("gold_diagnosis", tc.getGoldDiagnosis());
                if (tc.getGoldLesions() != null) {
                    try {
                        desensitized.put("gold_lesions", objectMapper.readValue(tc.getGoldLesions(), Object.class));
                    } catch (Exception ignored) {
                    }
                }
                if (tc.getGoldAnnotations() != null) {
                    try {
                        desensitized.put("gold_annotations", objectMapper.readValue(tc.getGoldAnnotations(), Object.class));
                    } catch (Exception ignored) {
                    }
                }
                if (tc.getImagePaths() != null) {
                    try {
                        desensitized.put("image_paths", objectMapper.readValue(tc.getImagePaths(), Object.class));
                    } catch (Exception ignored) {
                    }
                }
            }
        }
        return desensitized;
    }

    private boolean shareReaches(TeachingShare share, User user) {
        if (!"TEMPORARY".equalsIgnoreCase(share.getShareType())) {
            return true;
        }
        if (user == null || (user.getRoleCode() != null && !"STUDENT".equalsIgnoreCase(user.getRoleCode()))) {
            return true;
        }
        String scope = share.getShareScope() != null ? share.getShareScope().trim() : "ALL";
        String value = share.getScopeValue() != null ? share.getScopeValue().trim() : "";
        if (scope.isEmpty() || "ALL".equalsIgnoreCase(scope)) {
            return true;
        }
        if ("PEOPLE".equalsIgnoreCase(scope)) {
            try {
                List<Integer> ids = objectMapper.readValue(share.getAudienceIds(), new TypeReference<List<Integer>>() {});
                return ids != null && ids.contains(user.getId());
            } catch (Exception ignored) {
                return false;
            }
        }
        String own = switch (scope) {
            case "YEAR" -> user.getStudyYear() != null ? user.getStudyYear().trim() : "";
            case "BATCH" -> user.getRotationBatch() != null ? user.getRotationBatch().trim() : "";
            case "GROUP" -> user.getMentorGroup() != null ? user.getMentorGroup().trim() : "";
            default -> "";
        };
        return !value.isEmpty() && own.equals(value);
    }

    private String getCategoryText(String category) {
        if (category == null) return "";
        return switch (category.toUpperCase()) {
            case "DR" -> "糖尿病视网膜病变";
            case "NORMAL" -> "正常眼底";
            case "AMD" -> "年龄相关性黄斑变性";
            case "GLAUCOMA" -> "青光眼";
            case "HYPERTENSION" -> "高血压眼底";
            case "OTHER" -> "其他";
            default -> category;
        };
    }

    private String getDifficultyText(String difficulty) {
        if (difficulty == null) return "";
        return switch (difficulty.toUpperCase()) {
            case "EASY" -> "入门";
            case "MEDIUM" -> "中级";
            case "HARD" -> "高级";
            default -> difficulty;
        };
    }

    private String getGoldGradeText(String category, String grade) {
        if ("NORMAL".equalsIgnoreCase(category)) {
            return "未见明显眼底异常";
        }
        if ("GLAUCOMA".equalsIgnoreCase(category) || "AMD".equalsIgnoreCase(category)) {
            return "本例不按 DR 分级";
        }
        if (grade == null || grade.isEmpty()) {
            return "本例不做 DR 分级";
        }
        return switch (grade) {
            case "0" -> "DR 0 级（无 DR）";
            case "1" -> "DR 1 级（轻度 NPDR）";
            case "2" -> "DR 2 级（中度 NPDR）";
            case "3" -> "DR 3 级（重度 NPDR）";
            case "4" -> "DR 4 级（增殖性 DR / PDR）";
            default -> "DR " + grade + " 级";
        };
    }

    private String getLesionMaskUrl(Integer caseId) {
        if (caseId == null) return "";
        List<CaseImage> images = caseImageMapper.selectList(new LambdaQueryWrapper<CaseImage>()
                .eq(CaseImage::getCaseTable, "training")
                .eq(CaseImage::getCaseId, caseId)
                .in(CaseImage::getRole, List.of("color_mask", "overlay")));
        for (CaseImage img : images) {
            if ("color_mask".equalsIgnoreCase(img.getRole()) && img.getFileUrl() != null) {
                return img.getFileUrl();
            }
        }
        for (CaseImage img : images) {
            if ("overlay".equalsIgnoreCase(img.getRole()) && img.getFileUrl() != null) {
                return img.getFileUrl();
            }
        }
        return "";
    }

    private List<Map<String, Object>> formatLesions(Object rawLesions) {
        List<Map<String, Object>> result = new ArrayList<>();
        if (rawLesions == null) return result;
        List<?> list = null;
        if (rawLesions instanceof String) {
            try {
                list = objectMapper.readValue((String) rawLesions, List.class);
            } catch (Exception ignored) {
            }
        } else if (rawLesions instanceof List) {
            list = (List<?>) rawLesions;
        }
        if (list == null) return result;

        for (Object item : list) {
            if (!(item instanceof Map)) continue;
            Map<?, ?> map = (Map<?, ?>) item;
            Object val = map.get("type");
            if (val == null) val = map.get("label");
            String type = val != null ? String.valueOf(val).trim() : "";
            String name;
            String detail = "";
            if (map.containsKey("pixel_count")) {
                name = switch (type) {
                    case "MA" -> "微动脉瘤";
                    case "HE" -> "出血";
                    case "EX" -> "硬性渗出";
                    case "SE" -> "软性渗出";
                    default -> type.isEmpty() ? "病灶" : type;
                };
                detail = "着色图里有这块区域";
            } else {
                name = switch (type) {
                    case "MA" -> "微动脉瘤";
                    case "HM" -> "出血";
                    case "HE" -> "硬性渗出";
                    case "NV" -> "新生血管";
                    case "VB" -> "静脉串珠";
                    case "IRMA" -> "视网膜内微血管异常";
                    case "OpticDiskCupping" -> "视盘陷凹扩大";
                    case "Drusen" -> "玻璃膜疣";
                    default -> type.isEmpty() ? "病灶" : type;
                };
                Object count = map.get("count");
                detail = count != null ? "约 " + count + " 处" : "";
            }
            Map<String, Object> row = new HashMap<>();
            row.put("name", name);
            row.put("detail", detail);
            result.add(row);
        }
        return result;
    }

    private List<Object> parseAnnotations(Object raw) {
        if (raw == null) return Collections.emptyList();
        if (raw instanceof List) return (List<Object>) raw;
        if (raw instanceof String) {
            try {
                return objectMapper.readValue((String) raw, List.class);
            } catch (Exception ignored) {
            }
        }
        return Collections.emptyList();
    }

    private int countDistinctImages(Map<String, Object> imagePaths) {
        if (imagePaths == null) return 0;
        Set<String> urls = new HashSet<>();
        for (Object val : imagePaths.values()) {
            if (val instanceof List) {
                for (Object u : (List<?>) val) {
                    if (u != null) urls.add(String.valueOf(u));
                }
            } else if (val instanceof String) {
                urls.add((String) val);
            }
        }
        return urls.size();
    }
}
