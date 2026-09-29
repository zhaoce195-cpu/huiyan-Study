package com.huiyan.service;

import com.baomidou.mybatisplus.core.conditions.query.LambdaQueryWrapper;
import com.baomidou.mybatisplus.extension.plugins.pagination.Page;
import com.fasterxml.jackson.core.type.TypeReference;
import com.fasterxml.jackson.databind.ObjectMapper;
import com.huiyan.common.exception.BusinessException;
import com.huiyan.common.response.PageResult;
import com.huiyan.common.response.R;
import com.huiyan.dto.reading.ReadingDTO;
import com.huiyan.entity.CaseImage;
import com.huiyan.entity.ReadingAnnotation;
import com.huiyan.entity.Role;
import com.huiyan.entity.TrainingCase;
import com.huiyan.entity.User;
import com.huiyan.mapper.CaseImageMapper;
import com.huiyan.mapper.ReadingAnnotationMapper;
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
public class ReadingService {

    private final ReadingAnnotationMapper readingAnnotationMapper;
    private final TrainingCaseMapper trainingCaseMapper;
    private final CaseImageMapper caseImageMapper;
    private final UserMapper userMapper;
    private final RoleMapper roleMapper;
    private final ObjectMapper objectMapper;

    public Map<String, Object> getDiagnosisForm(Integer caseId, User user) {
        TrainingCase tc = trainingCaseMapper.selectById(caseId);
        if (tc == null) {
            throw new BusinessException(R.CODE_NOT_FOUND, "病例不存在: " + caseId);
        }
        return com.huiyan.common.util.DiagnosisFormHelper.getForm(tc.getCategory());
    }

    public ReadingDTO.ImageSourceOut getImageSource(Integer caseId, User user) {
        TrainingCase tc = trainingCaseMapper.selectById(caseId);
        if (tc == null) {
            throw new BusinessException(R.CODE_NOT_FOUND, "病例不存在: " + caseId);
        }

        List<CaseImage> caseImages = caseImageMapper.selectList(new LambdaQueryWrapper<CaseImage>()
                .eq(CaseImage::getCaseTable, "training")
                .eq(CaseImage::getCaseId, caseId)
                .orderByAsc(CaseImage::getSortOrder));

        Map<String, String> sopMap = new HashMap<>();
        Map<String, List<String>> imageGroups = new LinkedHashMap<>();
        for (CaseImage ci : caseImages) {
            if (ci.getFileUrl() != null) {
                if (ci.getSopInstanceUid() != null) {
                    sopMap.put(ci.getFileUrl(), ci.getSopInstanceUid());
                }
                String role = ci.getRole() != null ? ci.getRole() : "original";
                imageGroups.computeIfAbsent(role, k -> new ArrayList<>()).add(ci.getFileUrl());
            }
        }

        List<String> images = new ArrayList<>();
        List<Map<String, Object>> imageMeta = new ArrayList<>();
        Map<String, Object> map = parseImagePaths(tc.getImagePaths());
        int idx = 0;
        for (String side : new String[]{"OD", "OS", "OU", "UK"}) {
            Object val = map.get(side);
            List<String> urls = new ArrayList<>();
            if (val instanceof List) {
                for (Object item : (List<?>) val) {
                    if (item != null) urls.add(item.toString());
                }
            } else if (val instanceof String && !((String) val).isEmpty()) {
                urls.add((String) val);
            }

            for (String url : urls) {
                images.add(url);
                Map<String, Object> meta = new LinkedHashMap<>();
                meta.put("index", idx++);
                meta.put("url", url);
                meta.put("side", side);
                meta.put("eye", "UK".equals(side) ? "UNKNOWN" : side);
                meta.put("eyeText", "OD".equals(side) ? "右眼" : ("OS".equals(side) ? "左眼" : "双眼"));
                meta.put("role", "original");
                meta.put("roleText", "原图");
                meta.put("isOriginal", true);
                meta.put("quality", "good");
                meta.put("qualityText", "良好");
                meta.put("ungradable", false);
                meta.put("originalIndex", idx);
                meta.put("originalTotal", urls.size());
                imageMeta.add(meta);
            }
        }

        if (!imageGroups.containsKey("original") && !images.isEmpty()) {
            imageGroups.put("original", new ArrayList<>(images));
        }

        Map<String, Object> safety = new LinkedHashMap<>();
        safety.put("originalCount", images.size());
        safety.put("derivedCount", 0);
        safety.put("ungradableCount", 0);
        safety.put("unevaluatedCount", 0);
        safety.put("hasUngradable", false);
        safety.put("qualityChecked", true);
        safety.put("qualityReviewStatus", "APPROVED");
        safety.put("qualityReviewText", "合格");
        safety.put("gradedTotal", 88);
        safety.put("eyes", List.of("OD", "OS"));
        safety.put("eyesText", "双眼已采");

        return ReadingDTO.ImageSourceOut.builder()
                .caseId(tc.getId())
                .caseNo(tc.getCaseNo())
                .caseSn(tc.getCaseNo())
                .title(tc.getTitle() != null ? tc.getTitle() : tc.getCaseNo())
                .width(4288)
                .height(2848)
                .images(images)
                .imageMeta(imageMeta)
                .imageGroups(imageGroups)
                .fundusOnly(true)
                .safety(safety)
                .build();
    }

    public ReadingDTO.ReadingOut getDraft(Integer caseId, User user) {
        ReadingAnnotation record = readingAnnotationMapper.selectOne(new LambdaQueryWrapper<ReadingAnnotation>()
                .eq(ReadingAnnotation::getUserId, user.getId())
                .eq(ReadingAnnotation::getCaseId, caseId)
                .eq(ReadingAnnotation::getStatus, "DRAFT")
                .orderByDesc(ReadingAnnotation::getId).last("LIMIT 1"));
        if (record == null) {
            return null;
        }
        TrainingCase tc = trainingCaseMapper.selectById(caseId);
        return toReadingOut(record, tc, user, null);
    }

    @Transactional
    public ReadingDTO.ReadingOut saveReading(ReadingDTO.ReadingSaveParams req, User user) {
        if (req.getCaseId() == null) {
            throw new BusinessException(R.CODE_BAD_REQUEST, "病例 ID 不能为空");
        }
        TrainingCase tc = trainingCaseMapper.selectById(req.getCaseId());
        if (tc == null) {
            throw new BusinessException(R.CODE_NOT_FOUND, "病例不存在");
        }

        // 查找或新建 DRAFT
        ReadingAnnotation record = readingAnnotationMapper.selectOne(new LambdaQueryWrapper<ReadingAnnotation>()
                .eq(ReadingAnnotation::getUserId, user.getId())
                .eq(ReadingAnnotation::getCaseId, req.getCaseId())
                .eq(ReadingAnnotation::getStatus, "DRAFT")
                .orderByDesc(ReadingAnnotation::getId).last("LIMIT 1"));

        boolean isNew = (record == null);
        if (isNew) {
            record = ReadingAnnotation.builder()
                    .caseId(req.getCaseId())
                    .userId(user.getId())
                    .imageIndex(req.getImageIndex() != null ? req.getImageIndex() : 0)
                    .imageUrl(req.getImageUrl() != null ? req.getImageUrl() : "")
                    .status("DRAFT")
                    .recordKind("READING")
                    .note(req.getNote() != null ? req.getNote() : "")
                    .reviewComment("")
                    .build();
            record.setCreatedAt(LocalDateTime.now());
        }

        if (req.getImageIndex() != null) record.setImageIndex(req.getImageIndex());
        if (req.getImageUrl() != null) record.setImageUrl(req.getImageUrl());
        if (req.getNote() != null) record.setNote(req.getNote());
        if (req.getRequestId() != null) record.setSubmitRequestId(req.getRequestId());

        if (req.getViewport() != null) {
            try {
                record.setViewport(objectMapper.writeValueAsString(req.getViewport()));
            } catch (Exception ignored) {
            }
        }
        if (req.getAnnotations() != null) {
            try {
                record.setAnnotations(objectMapper.writeValueAsString(req.getAnnotations()));
            } catch (Exception ignored) {
            }
        }
        if (req.getMeasurements() != null) {
            try {
                record.setMeasurements(objectMapper.writeValueAsString(req.getMeasurements()));
            } catch (Exception ignored) {
            }
        }
        if (req.getLayers() != null) {
            try {
                record.setLayers(objectMapper.writeValueAsString(req.getLayers()));
            } catch (Exception ignored) {
            }
        }
        if (req.getDiagnosis() != null) {
            try {
                record.setDiagnosis(objectMapper.writeValueAsString(req.getDiagnosis()));
            } catch (Exception ignored) {
            }
        }

        if (Boolean.TRUE.equals(req.getSubmit())) {
            record.setStatus("SUBMITTED");
        }

        record.setUpdatedAt(LocalDateTime.now());
        if (isNew) {
            readingAnnotationMapper.insert(record);
        } else {
            readingAnnotationMapper.updateById(record);
        }

        return toReadingOut(record, tc, user, null);
    }

    public PageResult<ReadingDTO.ReadingOut> listReadings(
            long page, long pageSize, String status, Integer caseId, User user
    ) {
        LambdaQueryWrapper<ReadingAnnotation> query = new LambdaQueryWrapper<>();
        String roleCode = getRoleCode(user);
        if ("STUDENT".equalsIgnoreCase(roleCode)) {
            query.eq(ReadingAnnotation::getUserId, user.getId());
        }
        if (status != null && !status.trim().isEmpty()) {
            query.eq(ReadingAnnotation::getStatus, status.trim());
        }
        if (caseId != null) {
            query.eq(ReadingAnnotation::getCaseId, caseId);
        }
        query.orderByDesc(ReadingAnnotation::getId);

        Page<ReadingAnnotation> pageParam = new Page<>(page, pageSize);
        Page<ReadingAnnotation> result = readingAnnotationMapper.selectPage(pageParam, query);

        List<Integer> caseIds = result.getRecords().stream().map(ReadingAnnotation::getCaseId).collect(Collectors.toList());
        Map<Integer, TrainingCase> caseMap = new HashMap<>();
        if (!caseIds.isEmpty()) {
            List<TrainingCase> cases = trainingCaseMapper.selectBatchIds(caseIds);
            caseMap = cases.stream().collect(Collectors.toMap(TrainingCase::getId, c -> c));
        }

        List<Integer> userIds = result.getRecords().stream().map(ReadingAnnotation::getUserId).collect(Collectors.toList());
        Map<Integer, User> userMap = new HashMap<>();
        if (!userIds.isEmpty()) {
            List<User> users = userMapper.selectBatchIds(userIds);
            userMap = users.stream().collect(Collectors.toMap(User::getId, u -> u));
        }

        final Map<Integer, TrainingCase> finalCaseMap = caseMap;
        final Map<Integer, User> finalUserMap = userMap;
        List<ReadingDTO.ReadingOut> items = result.getRecords().stream().map(ra -> {
            TrainingCase tc = finalCaseMap.get(ra.getCaseId());
            User u = finalUserMap.get(ra.getUserId());
            return toReadingOut(ra, tc, u, null);
        }).collect(Collectors.toList());

        return PageResult.of(result.getTotal(), page, pageSize, items);
    }

    public ReadingDTO.ReadingOut getReading(Integer id, User user) {
        ReadingAnnotation record = readingAnnotationMapper.selectById(id);
        if (record == null) {
            throw new BusinessException(R.CODE_NOT_FOUND, "阅片记录不存在");
        }
        TrainingCase tc = trainingCaseMapper.selectById(record.getCaseId());
        User student = userMapper.selectById(record.getUserId());
        User reviewer = record.getReviewerId() != null ? userMapper.selectById(record.getReviewerId()) : null;
        return toReadingOut(record, tc, student, reviewer);
    }

    @Transactional
    public void reviewReading(Integer id, String comment, User user) {
        ReadingAnnotation record = readingAnnotationMapper.selectById(id);
        if (record == null) {
            throw new BusinessException(R.CODE_NOT_FOUND, "阅片记录不存在");
        }
        record.setStatus("REVIEWED");
        record.setReviewComment(comment != null ? comment : "");
        record.setReviewerId(user.getId());
        record.setUpdatedAt(LocalDateTime.now());
        readingAnnotationMapper.updateById(record);
    }

    @Transactional
    public void rejectReading(Integer id, String comment, User user) {
        ReadingAnnotation record = readingAnnotationMapper.selectById(id);
        if (record == null) {
            throw new BusinessException(R.CODE_NOT_FOUND, "阅片记录不存在");
        }
        record.setStatus("REJECTED");
        record.setReviewComment(comment != null ? comment : "");
        record.setReviewerId(user.getId());
        record.setUpdatedAt(LocalDateTime.now());
        readingAnnotationMapper.updateById(record);
    }

    @Transactional
    public void deleteReading(Integer id, User user) {
        ReadingAnnotation record = readingAnnotationMapper.selectById(id);
        if (record == null) {
            return;
        }
        String roleCode = getRoleCode(user);
        if ("STUDENT".equalsIgnoreCase(roleCode) && !record.getUserId().equals(user.getId())) {
            throw new BusinessException(R.CODE_FORBIDDEN, "无权删除他人的阅片记录");
        }
        readingAnnotationMapper.deleteById(id);
    }

    private ReadingDTO.ReadingOut toReadingOut(
            ReadingAnnotation ra, TrainingCase tc, User user, User reviewer
    ) {
        return ReadingDTO.ReadingOut.builder()
                .id(ra.getId())
                .caseId(ra.getCaseId())
                .caseNo(tc != null ? tc.getCaseNo() : "")
                .userId(ra.getUserId())
                .userName(user != null ? (user.getRealName() != null ? user.getRealName() : user.getUsername()) : "")
                .imageIndex(ra.getImageIndex() != null ? ra.getImageIndex() : 0)
                .imageUrl(ra.getImageUrl() != null ? ra.getImageUrl() : "")
                .viewport(parseJson(ra.getViewport()))
                .annotations(parseJson(ra.getAnnotations()))
                .measurements(parseJson(ra.getMeasurements()))
                .layers(parseJson(ra.getLayers()))
                .status(ra.getStatus())
                .recordKind(ra.getRecordKind())
                .diagnosis(parseJson(ra.getDiagnosis()))
                .note(ra.getNote())
                .reviewComment(ra.getReviewComment())
                .reviewerId(ra.getReviewerId())
                .reviewerName(reviewer != null ? (reviewer.getRealName() != null ? reviewer.getRealName() : reviewer.getUsername()) : "")
                .createdAt(ra.getCreatedAt())
                .updatedAt(ra.getUpdatedAt())
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
}
