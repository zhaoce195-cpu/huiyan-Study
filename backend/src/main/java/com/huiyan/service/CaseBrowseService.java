package com.huiyan.service;

import com.baomidou.mybatisplus.core.conditions.query.LambdaQueryWrapper;
import com.baomidou.mybatisplus.extension.plugins.pagination.Page;
import com.fasterxml.jackson.core.type.TypeReference;
import com.fasterxml.jackson.databind.JsonNode;
import com.fasterxml.jackson.databind.ObjectMapper;
import com.huiyan.common.exception.BusinessException;
import com.huiyan.common.response.PageResult;
import com.huiyan.common.response.R;
import com.huiyan.dto.casebrowse.CaseBrowseDTO;
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
public class CaseBrowseService {

    private final TrainingCaseMapper trainingCaseMapper;
    private final PracticeSessionMapper practiceSessionMapper;
    private final UserMapper userMapper;
    private final RoleMapper roleMapper;
    private final ObjectMapper objectMapper;

    public PageResult<CaseBrowseDTO.CaseBrowseItem> listCases(
            long page, long pageSize, String keyword, String category, Integer drLevel,
            String difficulty, String archiveStatus, String creatorRole,
            LocalDateTime startTime, LocalDateTime endTime, Boolean onlyIncomplete, User user
    ) {
        LambdaQueryWrapper<TrainingCase> query = new LambdaQueryWrapper<>();

        String roleCode = getRoleCode(user);
        if ("STUDENT".equalsIgnoreCase(roleCode)) {
            query.eq(TrainingCase::getIsTrainCase, true);
            query.eq(TrainingCase::getArchiveStatus, "ACTIVE");
        } else if ("TEACHER".equalsIgnoreCase(roleCode)) {
            query.and(q -> q.eq(TrainingCase::getCreatorId, user.getId())
                    .or().eq(TrainingCase::getIsPublished, true));
        }

        if (keyword != null && !keyword.trim().isEmpty()) {
            String kw = keyword.trim();
            query.and(q -> q.like(TrainingCase::getCaseNo, kw)
                    .or().like(TrainingCase::getTitle, kw)
                    .or().like(TrainingCase::getDescription, kw)
                    .or().like(TrainingCase::getPatientName, kw)
                    .or().like(TrainingCase::getPatientPhone, kw));
        }
        if (category != null && !category.trim().isEmpty()) {
            query.eq(TrainingCase::getCategory, category.trim());
        }
        if (difficulty != null && !difficulty.trim().isEmpty()) {
            query.eq(TrainingCase::getDifficulty, difficulty.trim());
        }
        if (archiveStatus != null && !archiveStatus.trim().isEmpty()) {
            query.eq(TrainingCase::getArchiveStatus, archiveStatus.trim());
        }
        if (drLevel != null) {
            query.eq(TrainingCase::getGoldDrGrade, String.valueOf(drLevel));
        }
        if (startTime != null) {
            query.ge(TrainingCase::getCreatedAt, startTime);
        }
        if (endTime != null) {
            query.le(TrainingCase::getCreatedAt, endTime);
        }

        query.orderByDesc(TrainingCase::getId);

        Page<TrainingCase> pageParam = new Page<>(page, pageSize);
        Page<TrainingCase> result = trainingCaseMapper.selectPage(pageParam, query);

        // 盲训鉴权：如果当前用户是学生，查询其已作答提交的病例集合
        Set<Integer> answeredCaseIds = Collections.emptySet();
        if ("STUDENT".equalsIgnoreCase(roleCode) && !result.getRecords().isEmpty()) {
            List<Integer> caseIds = result.getRecords().stream().map(TrainingCase::getId).collect(Collectors.toList());
            List<PracticeSession> practices = practiceSessionMapper.selectList(new LambdaQueryWrapper<PracticeSession>()
                    .eq(PracticeSession::getUserId, user.getId())
                    .in(PracticeSession::getCaseId, caseIds)
                    .in(PracticeSession::getStatus, "SUBMITTED", "REVIEWED"));
            answeredCaseIds = practices.stream().map(PracticeSession::getCaseId).collect(Collectors.toSet());
        }

        List<User> creators = userMapper.selectList(null);
        Map<Integer, User> creatorMap = creators.stream().collect(Collectors.toMap(User::getId, u -> u, (a, b) -> a));

        final Set<Integer> finalAnswered = answeredCaseIds;
        List<CaseBrowseDTO.CaseBrowseItem> items = result.getRecords().stream().map(tc -> {
            boolean isAnswered = !"STUDENT".equalsIgnoreCase(roleCode) || finalAnswered.contains(tc.getId());
            User creator = creatorMap.get(tc.getCreatorId());
            return toBrowseItem(tc, creator, isAnswered, roleCode);
        }).collect(Collectors.toList());

        return PageResult.of(result.getTotal(), page, pageSize, items);
    }

    public CaseBrowseDTO.CaseBrowseDetail getCaseDetail(Integer caseId, User user) {
        TrainingCase tc = trainingCaseMapper.selectById(caseId);
        if (tc == null) {
            throw new BusinessException(R.CODE_NOT_FOUND, "病例不存在: " + caseId);
        }

        String roleCode = getRoleCode(user);
        boolean isAnswered = true;
        if ("STUDENT".equalsIgnoreCase(roleCode)) {
            Long count = practiceSessionMapper.selectCount(new LambdaQueryWrapper<PracticeSession>()
                    .eq(PracticeSession::getUserId, user.getId())
                    .eq(PracticeSession::getCaseId, caseId)
                    .in(PracticeSession::getStatus, "SUBMITTED", "REVIEWED"));
            isAnswered = count != null && count > 0;
        }

        User creator = userMapper.selectById(tc.getCreatorId());
        Map<String, Object> imagePathsMap = parseImagePaths(tc.getImagePaths());
        List<String> images = flattenImagePaths(imagePathsMap);

        Integer drLevel = null;
        String drGradeText = "";
        String goldDrGrade = null;
        String goldDiagnosis = "";
        String teachingPoints = "";
        Object goldLesions = Collections.emptyList();

        if (isAnswered) {
            try {
                drLevel = Integer.parseInt(tc.getGoldDrGrade());
                drGradeText = formatDrGrade(tc.getGoldDrGrade());
            } catch (Exception ignored) {
            }
            goldDrGrade = tc.getGoldDrGrade();
            goldDiagnosis = tc.getGoldDiagnosis();
            teachingPoints = tc.getTeachingPoints();
            goldLesions = parseJson(tc.getGoldLesions());
        }

        String phone = tc.getPatientPhone() != null ? tc.getPatientPhone() : "";
        if ("STUDENT".equalsIgnoreCase(roleCode) && phone.length() >= 7) {
            phone = phone.substring(0, 3) + "****" + phone.substring(phone.length() - 4);
        }

        return CaseBrowseDTO.CaseBrowseDetail.builder()
                .id(tc.getId())
                .caseNo(tc.getCaseNo())
                .caseSn(tc.getCaseSn())
                .title(tc.getTitle())
                .description(tc.getDescription())
                .category(tc.getCategory())
                .categoryText(formatCategory(tc.getCategory()))
                .difficulty(tc.getDifficulty())
                .difficultyText(formatDifficulty(tc.getDifficulty()))
                .drLevel(drLevel)
                .drGradeText(drGradeText)
                .archiveStatus(tc.getArchiveStatus())
                .isPublished(Boolean.TRUE.equals(tc.getIsPublished()))
                .isTrainCase(Boolean.TRUE.equals(tc.getIsTrainCase()))
                .creatorId(tc.getCreatorId())
                .creatorName(creator != null ? (creator.getRealName() != null ? creator.getRealName() : creator.getUsername()) : "")
                .creatorRole(creator != null ? creator.getUserType() : "")
                .thumbUrl(!images.isEmpty() ? images.get(0) : "")
                .imageCount(images.size())
                .derivedCount(0)
                .imageComplete(true)
                .fundusOnly(true)
                .patientName(tc.getPatientName())
                .patientGender(tc.getPatientGender())
                .patientAge(tc.getPatientAge() != null ? tc.getPatientAge() : 0)
                .patientPhone(phone)
                .phoneVisible(!"STUDENT".equalsIgnoreCase(roleCode))
                .subjectNo(tc.getSubjectNo() != null ? tc.getSubjectNo() : "")
                .examOn(tc.getExamOn() != null ? tc.getExamOn() : "")
                .visitIndex(1)
                .visitCount(1)
                .createdAt(tc.getCreatedAt())
                .updatedAt(tc.getUpdatedAt())
                .clinicalInfo(tc.getClinicalInfo() != null ? tc.getClinicalInfo() : "")
                .imagePaths(imagePathsMap)
                .images(images)
                .goldDrGrade(goldDrGrade)
                .goldDiagnosis(goldDiagnosis)
                .teachingPoints(teachingPoints)
                .goldLesions(goldLesions)
                .passScore(tc.getPassScore() != null ? tc.getPassScore() : 60)
                .isAnswered(isAnswered)
                .build();
    }

    @Transactional
    public void archiveCase(Integer caseId, String archiveStatus, String reason, User user) {
        TrainingCase tc = trainingCaseMapper.selectById(caseId);
        if (tc == null) {
            throw new BusinessException(R.CODE_NOT_FOUND, "病例不存在");
        }
        tc.setArchiveStatus("ARCHIVED".equalsIgnoreCase(archiveStatus) ? "ARCHIVED" : "ACTIVE");
        tc.setUpdatedAt(LocalDateTime.now());
        trainingCaseMapper.updateById(tc);
    }

    @Transactional
    public void updateGoldStandard(Integer caseId, CaseBrowseDTO.GoldStandardUpdate req, User user) {
        TrainingCase tc = trainingCaseMapper.selectById(caseId);
        if (tc == null) {
            throw new BusinessException(R.CODE_NOT_FOUND, "病例不存在");
        }
        if (req.getGoldDrGrade() != null) tc.setGoldDrGrade(req.getGoldDrGrade());
        if (req.getGoldDiagnosis() != null) tc.setGoldDiagnosis(req.getGoldDiagnosis());
        if (req.getTeachingPoints() != null) tc.setTeachingPoints(req.getTeachingPoints());
        if (req.getPassScore() != null) tc.setPassScore(req.getPassScore());
        if (req.getGoldLesions() != null) {
            try {
                tc.setGoldLesions(objectMapper.writeValueAsString(req.getGoldLesions()));
            } catch (Exception ignored) {
            }
        }
        if (Boolean.TRUE.equals(req.getPublish())) {
            tc.setIsPublished(true);
            tc.setIsTrainCase(true);
        }
        tc.setUpdatedAt(LocalDateTime.now());
        trainingCaseMapper.updateById(tc);
    }

    @Transactional
    public void joinTraining(Integer caseId, User user) {
        TrainingCase tc = trainingCaseMapper.selectById(caseId);
        if (tc == null) {
            throw new BusinessException(R.CODE_NOT_FOUND, "病例不存在");
        }
        tc.setIsTrainCase(true);
        tc.setIsPublished(true);
        tc.setUpdatedAt(LocalDateTime.now());
        trainingCaseMapper.updateById(tc);
    }

    private CaseBrowseDTO.CaseBrowseItem toBrowseItem(
            TrainingCase tc, User creator, boolean isAnswered, String roleCode
    ) {
        List<String> images = flattenImagePaths(parseImagePaths(tc.getImagePaths()));
        Integer drLevel = null;
        String drGradeText = "";
        if (isAnswered) {
            try {
                drLevel = Integer.parseInt(tc.getGoldDrGrade());
                drGradeText = formatDrGrade(tc.getGoldDrGrade());
            } catch (Exception ignored) {
            }
        }

        String phone = tc.getPatientPhone() != null ? tc.getPatientPhone() : "";
        if ("STUDENT".equalsIgnoreCase(roleCode) && phone.length() >= 7) {
            phone = phone.substring(0, 3) + "****" + phone.substring(phone.length() - 4);
        }

        return CaseBrowseDTO.CaseBrowseItem.builder()
                .id(tc.getId())
                .caseNo(tc.getCaseNo())
                .caseSn(tc.getCaseSn())
                .title(tc.getTitle())
                .description(tc.getDescription())
                .category(tc.getCategory())
                .categoryText(formatCategory(tc.getCategory()))
                .difficulty(tc.getDifficulty())
                .difficultyText(formatDifficulty(tc.getDifficulty()))
                .drLevel(drLevel)
                .drGradeText(drGradeText)
                .archiveStatus(tc.getArchiveStatus())
                .isPublished(Boolean.TRUE.equals(tc.getIsPublished()))
                .isTrainCase(Boolean.TRUE.equals(tc.getIsTrainCase()))
                .creatorId(tc.getCreatorId())
                .creatorName(creator != null ? (creator.getRealName() != null ? creator.getRealName() : creator.getUsername()) : "")
                .creatorRole(creator != null ? creator.getUserType() : "")
                .thumbUrl(!images.isEmpty() ? images.get(0) : "")
                .imageCount(images.size())
                .derivedCount(0)
                .imageComplete(true)
                .fundusOnly(true)
                .missingRoles(Collections.emptyList())
                .patientName(tc.getPatientName())
                .patientGender(tc.getPatientGender())
                .patientAge(tc.getPatientAge() != null ? tc.getPatientAge() : 0)
                .patientPhone(phone)
                .phoneVisible(!"STUDENT".equalsIgnoreCase(roleCode))
                .subjectNo(tc.getSubjectNo() != null ? tc.getSubjectNo() : "")
                .examOn(tc.getExamOn() != null ? tc.getExamOn() : "")
                .visitIndex(1)
                .visitCount(1)
                .createdAt(tc.getCreatedAt())
                .updatedAt(tc.getUpdatedAt())
                .build();
    }

    private Map<String, Object> parseImagePaths(String json) {
        if (json == null || json.isEmpty()) return Collections.emptyMap();
        try {
            return objectMapper.readValue(json, new TypeReference<Map<String, Object>>() {});
        } catch (Exception e) {
            return Collections.emptyMap();
        }
    }

    private List<String> flattenImagePaths(Map<String, Object> map) {
        List<String> list = new ArrayList<>();
        if (map == null) return list;
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
    }

    private Object parseJson(String json) {
        if (json == null || json.isEmpty()) return Collections.emptyList();
        try {
            return objectMapper.readValue(json, Object.class);
        } catch (Exception e) {
            return Collections.emptyList();
        }
    }

    private String getRoleCode(User user) {
        if (user == null || user.getRoleId() == null) return "STUDENT";
        Role role = roleMapper.selectById(user.getRoleId());
        return role != null ? role.getCode() : "STUDENT";
    }

    private String formatCategory(String category) {
        if ("DR".equalsIgnoreCase(category)) return "糖尿病视网膜病变";
        if ("AMD".equalsIgnoreCase(category)) return "老年性黄斑变性";
        if ("GLAUCOMA".equalsIgnoreCase(category)) return "青光眼";
        if ("HYPERTENSION".equalsIgnoreCase(category)) return "高血压性视网膜病变";
        if ("NORMAL".equalsIgnoreCase(category)) return "正常眼底";
        return "其他";
    }

    private String formatDifficulty(String diff) {
        if ("EASY".equalsIgnoreCase(diff)) return "入门";
        if ("MEDIUM".equalsIgnoreCase(diff)) return "中级";
        if ("HARD".equalsIgnoreCase(diff)) return "高级";
        return diff != null ? diff : "入门";
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
