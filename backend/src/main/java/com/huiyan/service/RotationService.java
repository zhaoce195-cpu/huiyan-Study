package com.huiyan.service;

import com.baomidou.mybatisplus.core.conditions.query.LambdaQueryWrapper;
import com.huiyan.common.exception.BusinessException;
import com.huiyan.common.response.R;
import com.huiyan.entity.*;
import com.huiyan.mapper.*;
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
public class RotationService {

    private final RotationMapper rotationMapper;
    private final RotationTaskMapper rotationTaskMapper;
    private final RotationTaskAckMapper rotationTaskAckMapper;
    private final TrainingCaseMapper trainingCaseMapper;
    private final LearningResourceMapper learningResourceMapper;
    private final PracticeSessionMapper practiceSessionMapper;
    private final UserMapper userMapper;
    private final RoleMapper roleMapper;

    public Map<String, Object> home(User user) {
        Rotation rotation = rotationMapper.selectOne(new LambdaQueryWrapper<Rotation>()
                .eq(Rotation::getStatus, "ACTIVE")
                .orderByDesc(Rotation::getId).last("LIMIT 1"));

        if (rotation == null) {
            rotation = Rotation.builder()
                    .title("本轮转学习计划")
                    .startOn("2026-03-01")
                    .dueOn("2026-07-01")
                    .passScore(60)
                    .status("ACTIVE")
                    .creatorId(1)
                    .build();
            rotation.setCreatedAt(LocalDateTime.now());
            rotation.setUpdatedAt(LocalDateTime.now());
            rotationMapper.insert(rotation);
        }

        List<RotationTask> rawTasks = rotationTaskMapper.selectList(new LambdaQueryWrapper<RotationTask>()
                .eq(RotationTask::getRotationId, rotation.getId())
                .orderByAsc(RotationTask::getSortOrder));

        Set<Integer> caseIds = rawTasks.stream()
                .map(RotationTask::getCaseId)
                .filter(Objects::nonNull)
                .collect(Collectors.toSet());
        Map<Integer, TrainingCase> caseMap = new HashMap<>();
        if (!caseIds.isEmpty()) {
            List<TrainingCase> caseList = trainingCaseMapper.selectBatchIds(caseIds);
            for (TrainingCase tc : caseList) {
                caseMap.put(tc.getId(), tc);
            }
        }

        String todayStr = java.time.LocalDate.now().toString();

        Role role = user.getRoleId() != null ? roleMapper.selectById(user.getRoleId()) : null;
        String roleCode = role != null ? role.getCode() : (user.getRoleCode() != null ? user.getRoleCode() : "STUDENT");
        boolean isTeacher = "ADMIN".equalsIgnoreCase(roleCode) || "TEACHER".equalsIgnoreCase(roleCode) || "DOCTOR".equalsIgnoreCase(roleCode);

        if (isTeacher) {
            return buildTeacherHome(rotation, rawTasks, caseMap, todayStr);
        } else {
            return buildStudentHome(user, rotation, rawTasks, caseMap, todayStr);
        }
    }

    private Map<String, Object> buildStudentHome(User user, Rotation rotation, List<RotationTask> rawTasks, Map<Integer, TrainingCase> caseMap, String todayStr) {
        List<RotationTaskAck> acks = rotationTaskAckMapper.selectList(new LambdaQueryWrapper<RotationTaskAck>()
                .eq(RotationTaskAck::getUserId, user.getId()));
        Set<Integer> ackTaskIds = acks.stream().map(RotationTaskAck::getTaskId).collect(Collectors.toSet());

        List<PracticeSession> practices = practiceSessionMapper.selectList(new LambdaQueryWrapper<PracticeSession>()
                .eq(PracticeSession::getUserId, user.getId()));
        Map<Integer, List<PracticeSession>> casePractices = new HashMap<>();
        for (PracticeSession ps : practices) {
            if (ps.getCaseId() != null) {
                casePractices.computeIfAbsent(ps.getCaseId(), k -> new ArrayList<>()).add(ps);
            }
        }

        List<Map<String, Object>> taskOuts = new ArrayList<>();
        int defaultPassScore = rotation.getPassScore() != null ? rotation.getPassScore() : 60;

        for (RotationTask t : rawTasks) {
            Map<String, Object> out = new LinkedHashMap<>();
            out.put("id", t.getId());
            out.put("kind", t.getKind());
            String tier = t.getTier() != null ? t.getTier() : "REQUIRED";
            out.put("tier", tier);
            out.put("kindText", "CASE".equalsIgnoreCase(t.getKind()) ? ("EXTENSION".equalsIgnoreCase(tier) ? "拓展病例" : "必做病例") : "必学知识点");

            TrainingCase tc = t.getCaseId() != null ? caseMap.get(t.getCaseId()) : null;
            String caseNo = tc != null && tc.getCaseNo() != null ? tc.getCaseNo() : "";
            String title = t.getTitle() != null && !t.getTitle().isEmpty() ? t.getTitle() : (tc != null ? tc.getTitle() : "未命名任务");
            out.put("title", title);
            out.put("summary", t.getSummary() != null ? t.getSummary() : "");

            String dueOn = t.getDueOn() != null && !t.getDueOn().isEmpty() ? t.getDueOn() : (rotation.getDueOn() != null ? rotation.getDueOn() : "");
            out.put("dueOn", dueOn);
            int taskPassScore = t.getPassScore() != null ? t.getPassScore() : defaultPassScore;
            out.put("passScore", taskPassScore);

            String status = "TODO";
            String statusText = "未开始";
            Double score = null;

            if ("CASE".equalsIgnoreCase(t.getKind()) && t.getCaseId() != null) {
                List<PracticeSession> pList = casePractices.getOrDefault(t.getCaseId(), Collections.emptyList());
                if (!pList.isEmpty()) {
                    boolean anyPassed = pList.stream().anyMatch(p -> Integer.valueOf(1).equals(p.getIsPassed()) || (p.getScoreTotal() != null && p.getScoreTotal() >= taskPassScore));
                    OptionalDouble maxScore = pList.stream().filter(p -> p.getScoreTotal() != null).mapToDouble(PracticeSession::getScoreTotal).max();
                    if (anyPassed) {
                        status = "DONE";
                        statusText = "已合格";
                        score = maxScore.isPresent() ? Math.round(maxScore.getAsDouble() * 10.0) / 10.0 : 100.0;
                    } else {
                        boolean anySubmitted = pList.stream().anyMatch(p -> "SUBMITTED".equalsIgnoreCase(p.getStatus()) || "REVIEWED".equalsIgnoreCase(p.getStatus()));
                        if (anySubmitted) {
                            status = "SHORT";
                            statusText = "未合格";
                            score = maxScore.isPresent() ? Math.round(maxScore.getAsDouble() * 10.0) / 10.0 : 0.0;
                        } else {
                            status = "DOING";
                            statusText = "进行中";
                        }
                    }
                }
            } else if ("KNOWLEDGE".equalsIgnoreCase(t.getKind())) {
                if (ackTaskIds.contains(t.getId())) {
                    status = "DONE";
                    statusText = "已学习";
                } else {
                    status = "TODO";
                    statusText = "未学习";
                }
            }

            out.put("status", status);
            out.put("statusText", statusText);
            out.put("score", score);

            boolean isDone = "DONE".equals(status);
            boolean overdue = !dueOn.isEmpty() && dueOn.compareTo(todayStr) < 0 && !isDone;
            boolean dueToday = !dueOn.isEmpty() && dueOn.equals(todayStr) && !isDone;
            out.put("overdue", overdue);
            out.put("dueToday", dueToday);

            out.put("caseId", t.getCaseId());
            out.put("caseNo", caseNo);
            out.put("resourceId", t.getResourceId());
            out.put("doneCount", 0);
            out.put("studentCount", 1);
            out.put("scope", t.getScope() != null ? t.getScope() : "ALL");
            out.put("scopeValue", t.getScopeValue() != null ? t.getScopeValue() : "");
            out.put("scopeText", "全员");

            taskOuts.add(out);
        }

        List<Map<String, Object>> required = taskOuts.stream()
                .filter(row -> !"EXTENSION".equalsIgnoreCase((String) row.get("tier")))
                .collect(Collectors.toList());

        List<Map<String, Object>> today = required.stream()
                .filter(row -> !"DONE".equals(row.get("status")))
                .sorted((a, b) -> {
                    Boolean ao = (Boolean) a.get("overdue");
                    Boolean bo = (Boolean) b.get("overdue");
                    if (!ao.equals(bo)) return bo.compareTo(ao);
                    String ad = (String) a.get("dueOn");
                    String bd = (String) b.get("dueOn");
                    return ad.compareTo(bd);
                })
                .collect(Collectors.toList());

        int total = required.size();
        long doneCount = required.stream().filter(row -> "DONE".equals(row.get("status"))).count();
        int progress = total > 0 ? (int) Math.round(100.0 * doneCount / total) : 0;

        Map<String, Object> rotationBrief = new LinkedHashMap<>();
        rotationBrief.put("id", rotation.getId());
        rotationBrief.put("title", rotation.getTitle());
        rotationBrief.put("startOn", rotation.getStartOn() != null ? rotation.getStartOn() : "");
        rotationBrief.put("dueOn", rotation.getDueOn() != null ? rotation.getDueOn() : "");
        rotationBrief.put("passScore", defaultPassScore);
        rotationBrief.put("total", total);
        rotationBrief.put("done", doneCount);
        rotationBrief.put("progress", progress);

        Map<String, Object> map = new LinkedHashMap<>();
        map.put("role", "student");
        map.put("rotation", rotationBrief);
        map.put("today", today);
        map.put("tasks", taskOuts);
        map.put("studyYear", user.getStudyYear() != null && !user.getStudyYear().isEmpty() ? user.getStudyYear() : "2024级");
        map.put("rotationBatch", user.getRotationBatch() != null && !user.getRotationBatch().isEmpty() ? user.getRotationBatch() : "第一批");
        map.put("mentorGroup", user.getMentorGroup() != null && !user.getMentorGroup().isEmpty() ? user.getMentorGroup() : "带教一组");
        map.put("groupEditorName", "教学管理组");
        map.put("groupEditorRole", "ADMIN");
        map.put("groupEditedAt", null);
        return map;
    }

    private Map<String, Object> buildTeacherHome(Rotation rotation, List<RotationTask> rawTasks, Map<Integer, TrainingCase> caseMap, String todayStr) {
        List<User> students = userMapper.selectList(new LambdaQueryWrapper<User>()
                .eq(User::getRoleId, 3));
        if (students.isEmpty()) {
            students = userMapper.selectList(new LambdaQueryWrapper<User>()
                    .ne(User::getRoleId, 1));
        }

        List<Map<String, Object>> teacherTasks = new ArrayList<>();
        int defaultPassScore = rotation.getPassScore() != null ? rotation.getPassScore() : 60;

        for (RotationTask t : rawTasks) {
            Map<String, Object> out = new LinkedHashMap<>();
            out.put("id", t.getId());
            out.put("kind", t.getKind());
            String tier = t.getTier() != null ? t.getTier() : "REQUIRED";
            out.put("tier", tier);
            out.put("kindText", "CASE".equalsIgnoreCase(t.getKind()) ? ("EXTENSION".equalsIgnoreCase(tier) ? "拓展病例" : "必做病例") : "必学知识点");
            TrainingCase tc = t.getCaseId() != null ? caseMap.get(t.getCaseId()) : null;
            String caseNo = tc != null && tc.getCaseNo() != null ? tc.getCaseNo() : "";
            out.put("title", t.getTitle() != null && !t.getTitle().isEmpty() ? t.getTitle() : (tc != null ? tc.getTitle() : "未命名任务"));
            out.put("summary", t.getSummary() != null ? t.getSummary() : "");
            String dueOn = t.getDueOn() != null && !t.getDueOn().isEmpty() ? t.getDueOn() : (rotation.getDueOn() != null ? rotation.getDueOn() : "");
            out.put("dueOn", dueOn);
            out.put("passScore", t.getPassScore() != null ? t.getPassScore() : defaultPassScore);
            out.put("caseId", t.getCaseId());
            out.put("caseNo", caseNo);
            out.put("resourceId", t.getResourceId());
            out.put("doneCount", 0);
            out.put("studentCount", students.size());
            out.put("status", "TODO");
            out.put("statusText", "0/" + students.size() + " 人完成");
            out.put("score", null);
            out.put("overdue", false);
            out.put("dueToday", false);
            out.put("scope", t.getScope() != null ? t.getScope() : "ALL");
            out.put("scopeValue", t.getScopeValue() != null ? t.getScopeValue() : "");
            out.put("scopeText", "全员");
            teacherTasks.add(out);
        }

        List<Map<String, Object>> studentProgressList = new ArrayList<>();
        for (User s : students) {
            Map<String, Object> sp = new LinkedHashMap<>();
            sp.put("userId", s.getId());
            sp.put("name", s.getRealName() != null ? s.getRealName() : s.getUsername());
            sp.put("username", s.getUsername());
            sp.put("studyYear", s.getStudyYear() != null && !s.getStudyYear().isEmpty() ? s.getStudyYear() : "未分组");
            sp.put("rotationBatch", s.getRotationBatch() != null && !s.getRotationBatch().isEmpty() ? s.getRotationBatch() : "未分组");
            sp.put("mentorGroup", s.getMentorGroup() != null && !s.getMentorGroup().isEmpty() ? s.getMentorGroup() : "未分组");
            sp.put("groupEditorName", "管理员");
            sp.put("groupEditorRole", "ADMIN");
            sp.put("groupEditedAt", null);
            sp.put("done", 0);
            sp.put("total", teacherTasks.size());
            sp.put("progress", 0);
            sp.put("practiceCount", 0);
            sp.put("completedCases", 0);
            sp.put("avgScore", 0.0);
            sp.put("studySeconds", 0);
            sp.put("tasks", Collections.emptyList());
            studentProgressList.add(sp);
        }

        Map<String, Object> rotationBrief = new LinkedHashMap<>();
        rotationBrief.put("id", rotation.getId());
        rotationBrief.put("title", rotation.getTitle());
        rotationBrief.put("startOn", rotation.getStartOn() != null ? rotation.getStartOn() : "");
        rotationBrief.put("dueOn", rotation.getDueOn() != null ? rotation.getDueOn() : "");
        rotationBrief.put("passScore", defaultPassScore);
        rotationBrief.put("total", teacherTasks.size());
        rotationBrief.put("done", 0);
        rotationBrief.put("progress", 0);

        Map<String, Object> map = new LinkedHashMap<>();
        map.put("role", "teacher");
        map.put("rotation", rotationBrief);
        map.put("tasks", teacherTasks);
        map.put("students", studentProgressList);
        map.put("groups", Collections.emptyList());
        return map;
    }

    public Map<String, Object> options(User user) {
        List<TrainingCase> cases = trainingCaseMapper.selectList(new LambdaQueryWrapper<TrainingCase>()
                .eq(TrainingCase::getIsTrainCase, true));
        List<LearningResource> resources = learningResourceMapper.selectList(new LambdaQueryWrapper<LearningResource>()
                .eq(LearningResource::getStatus, "PUBLISHED"));

        List<Map<String, Object>> caseOptions = new ArrayList<>();
        for (TrainingCase c : cases) {
            Map<String, Object> opt = new HashMap<>();
            opt.put("id", c.getId());
            opt.put("label", (c.getCaseNo() != null ? c.getCaseNo() : "") + " · " + (c.getTitle() != null ? c.getTitle() : ""));
            caseOptions.add(opt);
        }

        List<Map<String, Object>> resourceOptions = new ArrayList<>();
        for (LearningResource r : resources) {
            Map<String, Object> opt = new HashMap<>();
            opt.put("id", r.getId());
            opt.put("label", r.getTitle() != null ? r.getTitle() : "资料 " + r.getId());
            resourceOptions.add(opt);
        }

        Map<String, Object> map = new HashMap<>();
        map.put("cases", caseOptions);
        map.put("resources", resourceOptions);
        return map;
    }

    @Transactional
    public void setStudentGroup(Integer studentUserId, Map<String, Object> params, User operator) {
        User student = userMapper.selectById(studentUserId);
        if (student == null) throw new BusinessException(R.CODE_NOT_FOUND, "学员不存在");

        if (params.containsKey("studyYear")) student.setStudyYear((String) params.get("studyYear"));
        if (params.containsKey("rotationBatch")) student.setRotationBatch((String) params.get("rotationBatch"));
        if (params.containsKey("mentorGroup")) student.setMentorGroup((String) params.get("mentorGroup"));
        student.setGroupEditorId(operator.getId());
        student.setGroupEditedAt(LocalDateTime.now());
        student.setUpdatedAt(LocalDateTime.now());
        userMapper.updateById(student);
    }

    @Transactional
    public Rotation updateRotation(Map<String, Object> params, User operator) {
        Rotation rotation = rotationMapper.selectOne(new LambdaQueryWrapper<Rotation>()
                .eq(Rotation::getStatus, "ACTIVE")
                .orderByDesc(Rotation::getId).last("LIMIT 1"));
        if (rotation == null) throw new BusinessException(R.CODE_NOT_FOUND, "当前没有进行中的轮转");

        if (params.containsKey("title")) rotation.setTitle((String) params.get("title"));
        if (params.containsKey("startOn")) rotation.setStartOn((String) params.get("startOn"));
        if (params.containsKey("dueOn")) rotation.setDueOn((String) params.get("dueOn"));
        if (params.containsKey("passScore")) rotation.setPassScore((Integer) params.get("passScore"));
        rotation.setUpdatedAt(LocalDateTime.now());
        rotationMapper.updateById(rotation);
        return rotation;
    }

    @Transactional
    public RotationTask addTask(Map<String, Object> params, User operator) {
        Rotation rotation = rotationMapper.selectOne(new LambdaQueryWrapper<Rotation>()
                .eq(Rotation::getStatus, "ACTIVE")
                .orderByDesc(Rotation::getId).last("LIMIT 1"));
        if (rotation == null) throw new BusinessException(R.CODE_NOT_FOUND, "当前没有进行中的轮转");

        String kind = (String) params.getOrDefault("kind", "CASE");
        Integer caseId = (Integer) params.get("caseId");
        Integer resourceId = (Integer) params.get("resourceId");
        String title = (String) params.getOrDefault("title", "");
        if (title.isEmpty() && caseId != null) {
            TrainingCase tc = trainingCaseMapper.selectById(caseId);
            if (tc != null) title = tc.getTitle();
        }

        RotationTask task = RotationTask.builder()
                .rotationId(rotation.getId())
                .kind(kind)
                .caseId(caseId)
                .resourceId(resourceId)
                .title(title)
                .summary((String) params.getOrDefault("summary", ""))
                .passScore((Integer) params.getOrDefault("passScore", 60))
                .dueOn((String) params.getOrDefault("dueOn", rotation.getDueOn()))
                .sortOrder((Integer) params.getOrDefault("sortOrder", 0))
                .tier((String) params.getOrDefault("tier", "REQUIRED"))
                .scope((String) params.getOrDefault("scope", "ALL"))
                .scopeValue((String) params.getOrDefault("scopeValue", ""))
                .build();
        task.setCreatedAt(LocalDateTime.now());
        task.setUpdatedAt(LocalDateTime.now());
        rotationTaskMapper.insert(task);
        return task;
    }

    @Transactional
    public void deleteTask(Integer taskId, User operator) {
        rotationTaskMapper.deleteById(taskId);
    }

    @Transactional
    public void ackTask(Integer taskId, User user) {
        RotationTaskAck ack = rotationTaskAckMapper.selectOne(new LambdaQueryWrapper<RotationTaskAck>()
                .eq(RotationTaskAck::getTaskId, taskId)
                .eq(RotationTaskAck::getUserId, user.getId()));
        if (ack == null) {
            ack = RotationTaskAck.builder()
                    .taskId(taskId)
                    .userId(user.getId())
                    .build();
            ack.setCreatedAt(LocalDateTime.now());
            ack.setUpdatedAt(LocalDateTime.now());
            rotationTaskAckMapper.insert(ack);
        }
    }
}
