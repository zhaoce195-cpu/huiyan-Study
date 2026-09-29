package com.huiyan.service;

import com.baomidou.mybatisplus.core.conditions.query.LambdaQueryWrapper;
import com.fasterxml.jackson.core.type.TypeReference;
import com.fasterxml.jackson.databind.ObjectMapper;
import com.huiyan.common.exception.BusinessException;
import com.huiyan.common.response.R;
import com.huiyan.entity.ExamPaper;
import com.huiyan.entity.PracticeSession;
import com.huiyan.entity.TrainingCase;
import com.huiyan.entity.User;
import com.huiyan.mapper.ExamPaperMapper;
import com.huiyan.mapper.PracticeSessionMapper;
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
public class ExamService {

    private final ExamPaperMapper examPaperMapper;
    private final TrainingCaseMapper trainingCaseMapper;
    private final PracticeSessionMapper practiceSessionMapper;
    private final UserMapper userMapper;
    private final ObjectMapper objectMapper;

    public List<Map<String, Object>> caseOptions(User user) {
        List<TrainingCase> cases = trainingCaseMapper.selectList(new LambdaQueryWrapper<TrainingCase>()
                .eq(TrainingCase::getIsTrainCase, true)
                .eq(TrainingCase::getArchiveStatus, "ACTIVE"));

        return cases.stream().map(c -> {
            Map<String, Object> map = new HashMap<>();
            map.put("id", c.getId());
            map.put("caseNo", c.getCaseNo());
            map.put("title", c.getTitle());
            map.put("category", c.getCategory());
            map.put("difficulty", c.getDifficulty());
            map.put("drLevel", c.getGoldDrGrade());
            return map;
        }).collect(Collectors.toList());
    }

    public List<Map<String, Object>> listPapers(User user) {
        List<ExamPaper> papers = examPaperMapper.selectList(new LambdaQueryWrapper<ExamPaper>()
                .orderByDesc(ExamPaper::getId));

        List<User> teachers = userMapper.selectList(null);
        Map<Integer, String> teacherMap = teachers.stream().collect(Collectors.toMap(User::getId, u -> u.getRealName() != null ? u.getRealName() : u.getUsername(), (a, b) -> a));

        return papers.stream().map(p -> {
            Map<String, Object> map = new HashMap<>();
            map.put("id", p.getId());
            map.put("title", p.getTitle());
            map.put("teacherId", p.getTeacherId());
            map.put("teacherName", teacherMap.get(p.getTeacherId()));
            map.put("status", p.getStatus());
            map.put("durationMinutes", p.getDurationMinutes());
            map.put("passScore", p.getPassScore());
            map.put("allowBack", p.getAllowBack());
            map.put("openedAt", p.getOpenedAt());
            map.put("closedAt", p.getClosedAt());
            List<Integer> caseIds = parseCaseIds(p.getCaseIds());
            map.put("caseCount", caseIds.size());
            map.put("caseIds", caseIds);
            return map;
        }).collect(Collectors.toList());
    }

    @Transactional
    public ExamPaper create(User user, Map<String, Object> params) {
        String title = (String) params.get("title");
        if (title == null || title.trim().isEmpty()) {
            throw new BusinessException(R.CODE_BAD_REQUEST, "考试标题不能为空");
        }

        Object caseIdsObj = params.get("caseIds");
        String caseIdsJson = "[]";
        try {
            if (caseIdsObj != null) {
                caseIdsJson = objectMapper.writeValueAsString(caseIdsObj);
            }
        } catch (Exception ignored) {
        }

        ExamPaper paper = ExamPaper.builder()
                .title(title.trim())
                .teacherId(user.getId())
                .status("OPEN")
                .durationMinutes((Integer) params.getOrDefault("durationMinutes", 60))
                .passScore((Integer) params.getOrDefault("passScore", 60))
                .allowBack((Boolean) params.getOrDefault("allowBack", false))
                .pickMode((String) params.getOrDefault("pickMode", "SELECTED"))
                .category((String) params.getOrDefault("category", ""))
                .difficulty((String) params.getOrDefault("difficulty", ""))
                .caseIds(caseIdsJson)
                .openedAt(LocalDateTime.now())
                .build();
        paper.setCreatedAt(LocalDateTime.now());
        paper.setUpdatedAt(LocalDateTime.now());
        examPaperMapper.insert(paper);
        return paper;
    }

    public Map<String, Object> start(User user, Integer paperId) {
        ExamPaper paper = examPaperMapper.selectById(paperId);
        if (paper == null) throw new BusinessException(R.CODE_NOT_FOUND, "试卷不存在");
        List<Integer> caseIds = parseCaseIds(paper.getCaseIds());

        Map<String, Object> map = new HashMap<>();
        map.put("paperId", paper.getId());
        map.put("title", paper.getTitle());
        map.put("durationMinutes", paper.getDurationMinutes());
        map.put("allowBack", paper.getAllowBack());
        map.put("caseIds", caseIds);
        map.put("status", paper.getStatus());
        return map;
    }

    @Transactional
    public void close(User user, Integer paperId) {
        ExamPaper paper = examPaperMapper.selectById(paperId);
        if (paper == null) throw new BusinessException(R.CODE_NOT_FOUND, "试卷不存在");
        paper.setStatus("CLOSED");
        paper.setClosedAt(LocalDateTime.now());
        paper.setUpdatedAt(LocalDateTime.now());
        examPaperMapper.updateById(paper);
    }

    public Map<String, Object> getResults(User user, Integer paperId) {
        ExamPaper paper = examPaperMapper.selectById(paperId);
        if (paper == null) throw new BusinessException(R.CODE_NOT_FOUND, "试卷不存在");

        List<PracticeSession> sessions = practiceSessionMapper.selectList(new LambdaQueryWrapper<PracticeSession>()
                .eq(PracticeSession::getExamPaperId, paperId));

        Map<String, Object> map = new HashMap<>();
        map.put("paperId", paperId);
        map.put("paperTitle", paper.getTitle());
        map.put("totalAttempts", sessions.size());
        map.put("passScore", paper.getPassScore());
        return map;
    }

    private List<Integer> parseCaseIds(String json) {
        if (json == null || json.isEmpty()) return Collections.emptyList();
        try {
            return objectMapper.readValue(json, new TypeReference<List<Integer>>() {});
        } catch (Exception e) {
            return Collections.emptyList();
        }
    }
}
