package com.huiyan.service;

import com.baomidou.mybatisplus.core.conditions.query.LambdaQueryWrapper;
import com.baomidou.mybatisplus.extension.plugins.pagination.Page;
import com.huiyan.common.exception.BusinessException;
import com.huiyan.common.response.PageResult;
import com.huiyan.common.response.R;
import com.huiyan.dto.common.CommonDTO;
import com.huiyan.entity.Department;
import com.huiyan.entity.PracticeSession;
import com.huiyan.entity.Role;
import com.huiyan.entity.TrainingCase;
import com.huiyan.entity.User;
import com.huiyan.mapper.DepartmentMapper;
import com.huiyan.mapper.PracticeSessionMapper;
import com.huiyan.mapper.RoleMapper;
import com.huiyan.mapper.TrainingCaseMapper;
import com.huiyan.mapper.UserMapper;
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
public class CommonService {

    private final DepartmentMapper departmentMapper;
    private final UserMapper userMapper;
    private final RoleMapper roleMapper;
    private final TrainingCaseMapper trainingCaseMapper;
    private final PracticeSessionMapper practiceSessionMapper;

    @Value("${huiyan.upload-dir:app/static}")
    private String uploadDir;

    @Value("${huiyan.orthanc-enabled:true}")
    private boolean orthancEnabled;

    @Value("${huiyan.drgcnn-enabled:true}")
    private boolean drgcnnEnabled;

    @Value("${huiyan.keycloak-login-enabled:false}")
    private boolean keycloakLoginEnabled;

    public CommonDTO.SystemConfig getSystemConfig() {
        return CommonDTO.SystemConfig.builder()
                .projectName("慧眼教学云后端服务")
                .projectVersion("1.0.0")
                .apiPrefix("/api/v1")
                .orthancEnabled(orthancEnabled)
                .drgcnnEnabled(drgcnnEnabled)
                .keycloakLoginEnabled(keycloakLoginEnabled)
                .build();
    }

    public List<CommonDTO.DictItem> getDict(String type) {
        List<CommonDTO.DictItem> list = new ArrayList<>();
        if ("dr_grade".equalsIgnoreCase(type) || "dr_stage".equalsIgnoreCase(type)) {
            list.add(new CommonDTO.DictItem("0期（无明显视网膜病变）", "0", "#52c41a", ""));
            list.add(new CommonDTO.DictItem("1期（轻度非增殖期）", "1", "#1890ff", ""));
            list.add(new CommonDTO.DictItem("2期（中度非增殖期）", "2", "#faad14", ""));
            list.add(new CommonDTO.DictItem("3期（重度非增殖期）", "3", "#fa8c16", ""));
            list.add(new CommonDTO.DictItem("4期（增殖期）", "4", "#f5222d", ""));
        } else if ("case_difficulty".equalsIgnoreCase(type)) {
            list.add(new CommonDTO.DictItem("简单", "EASY", "#52c41a", ""));
            list.add(new CommonDTO.DictItem("中等", "MEDIUM", "#faad14", ""));
            list.add(new CommonDTO.DictItem("困难", "HARD", "#f5222d", ""));
        } else if ("case_category".equalsIgnoreCase(type)) {
            list.add(new CommonDTO.DictItem("糖尿病视网膜病变", "DR", "#1890ff", ""));
            list.add(new CommonDTO.DictItem("老年性黄斑变性", "AMD", "#722ed1", ""));
            list.add(new CommonDTO.DictItem("青光眼", "GLAUCOMA", "#13c2c2", ""));
            list.add(new CommonDTO.DictItem("高血压视网膜病变", "HYPERTENSION", "#eb2f96", ""));
            list.add(new CommonDTO.DictItem("正常眼底", "NORMAL", "#52c41a", ""));
            list.add(new CommonDTO.DictItem("其他眼底病", "OTHER", "#8c8c8c", ""));
        } else if ("eye_side".equalsIgnoreCase(type)) {
            list.add(new CommonDTO.DictItem("右眼 (OD)", "OD", "", ""));
            list.add(new CommonDTO.DictItem("左眼 (OS)", "OS", "", ""));
            list.add(new CommonDTO.DictItem("双眼 (OU)", "OU", "", ""));
        } else if ("gender".equalsIgnoreCase(type)) {
            list.add(new CommonDTO.DictItem("男", "M", "", ""));
            list.add(new CommonDTO.DictItem("女", "F", "", ""));
            list.add(new CommonDTO.DictItem("未知", "U", "", ""));
        } else if ("roles".equalsIgnoreCase(type)) {
            list.add(new CommonDTO.DictItem("学员", "STUDENT", "", ""));
            list.add(new CommonDTO.DictItem("教师", "TEACHER", "", ""));
            list.add(new CommonDTO.DictItem("管理员", "ADMIN", "", ""));
        }
        return list;
    }

    public Map<String, List<CommonDTO.DictItem>> getDictBatch(List<String> types) {
        Map<String, List<CommonDTO.DictItem>> result = new HashMap<>();
        if (types != null) {
            for (String t : types) {
                result.put(t, getDict(t));
            }
        }
        return result;
    }

    public List<Map<String, Object>> getHospitals() {
        List<Map<String, Object>> list = new ArrayList<>();
        Map<String, Object> h1 = new HashMap<>();
        h1.put("id", 1);
        h1.put("name", "中南大学湘雅医院");
        h1.put("code", "XYH");
        list.add(h1);
        return list;
    }

    public PageResult<Department> getDepartments(long page, long pageSize, String name, Boolean isActive) {
        LambdaQueryWrapper<Department> query = new LambdaQueryWrapper<>();
        if (name != null && !name.trim().isEmpty()) {
            query.like(Department::getName, name.trim());
        }
        if (isActive != null) {
            query.eq(Department::getIsActive, isActive);
        }
        query.orderByAsc(Department::getSortOrder);

        Page<Department> pageParam = new Page<>(page, pageSize);
        Page<Department> result = departmentMapper.selectPage(pageParam, query);
        return PageResult.of(result.getTotal(), page, pageSize, result.getRecords());
    }

    @Transactional
    public Department saveDepartment(CommonDTO.DepartmentSaveRequest req) {
        if (req.getName() == null || req.getName().trim().isEmpty()) {
            throw new BusinessException(R.CODE_BAD_REQUEST, "科室名称不能为空");
        }
        String code = req.getCode() != null && !req.getCode().trim().isEmpty() ? req.getCode().trim() : ("DEPT_" + System.currentTimeMillis());
        Department dept = Department.builder()
                .code(code)
                .name(req.getName().trim())
                .shortName(req.getShortName() != null ? req.getShortName() : "")
                .leader(req.getLeader() != null ? req.getLeader() : "")
                .phone(req.getPhone() != null ? req.getPhone() : "")
                .sortOrder(req.getSortOrder() != null ? req.getSortOrder() : 0)
                .isActive(req.getIsActive() != null ? req.getIsActive() : true)
                .remark(req.getRemark() != null ? req.getRemark() : "")
                .hospitalId(req.getHospitalId())
                .build();
        dept.setCreatedAt(LocalDateTime.now());
        dept.setUpdatedAt(LocalDateTime.now());
        departmentMapper.insert(dept);
        return dept;
    }

    @Transactional
    public void updateDepartment(Integer id, CommonDTO.DepartmentSaveRequest req) {
        Department dept = departmentMapper.selectById(id);
        if (dept == null) {
            throw new BusinessException(R.CODE_NOT_FOUND, "科室不存在");
        }
        if (req.getName() != null) dept.setName(req.getName());
        if (req.getShortName() != null) dept.setShortName(req.getShortName());
        if (req.getLeader() != null) dept.setLeader(req.getLeader());
        if (req.getPhone() != null) dept.setPhone(req.getPhone());
        if (req.getSortOrder() != null) dept.setSortOrder(req.getSortOrder());
        if (req.getIsActive() != null) dept.setIsActive(req.getIsActive());
        if (req.getRemark() != null) dept.setRemark(req.getRemark());
        if (req.getHospitalId() != null) dept.setHospitalId(req.getHospitalId());
        dept.setUpdatedAt(LocalDateTime.now());
        departmentMapper.updateById(dept);
    }

    @Transactional
    public void deleteDepartment(Integer id) {
        departmentMapper.deleteById(id);
    }

    public CommonDTO.TrainingStats getTrainingStats() {
        long totalCases = trainingCaseMapper.selectCount(new LambdaQueryWrapper<TrainingCase>().eq(TrainingCase::getIsTrainCase, true));
        long totalPractices = practiceSessionMapper.selectCount(new LambdaQueryWrapper<PracticeSession>().in(PracticeSession::getStatus, "SUBMITTED", "REVIEWED"));

        Role studentRole = roleMapper.selectOne(new LambdaQueryWrapper<Role>().eq(Role::getCode, "STUDENT"));
        long totalStudents = studentRole != null ? userMapper.selectCount(new LambdaQueryWrapper<User>().eq(User::getRoleId, studentRole.getId())) : 0;

        List<PracticeSession> practices = practiceSessionMapper.selectList(new LambdaQueryWrapper<PracticeSession>()
                .in(PracticeSession::getStatus, "SUBMITTED", "REVIEWED"));

        double scoreSum = 0;
        double iouSum = 0;
        long passedCount = 0;
        long totalSeconds = 0;
        int validScoreCount = 0;
        int validIouCount = 0;

        for (PracticeSession p : practices) {
            if (p.getScoreTotal() != null) {
                scoreSum += p.getScoreTotal();
                validScoreCount++;
            }
            if (p.getIouAvg() != null && p.getIouAvg() >= 0) {
                iouSum += p.getIouAvg();
                validIouCount++;
            }
            if (Integer.valueOf(1).equals(p.getIsPassed())) {
                passedCount++;
            }
            if (p.getDurationSeconds() != null) {
                totalSeconds += p.getDurationSeconds();
            }
        }

        double avgScore = validScoreCount > 0 ? Math.round((scoreSum / validScoreCount) * 10.0) / 10.0 : 0.0;
        double avgIou = validIouCount > 0 ? Math.round((iouSum / validIouCount) * 1000.0) / 1000.0 : 0.0;
        double passRate = practices.size() > 0 ? Math.round(((double) passedCount / practices.size()) * 1000.0) / 10.0 : 0.0;
        long totalHours = totalSeconds / 3600;

        return CommonDTO.TrainingStats.builder()
                .totalCases(totalCases)
                .totalPractices(totalPractices)
                .totalStudents(totalStudents)
                .avgScore(avgScore)
                .passRate(passRate)
                .avgIou(avgIou)
                .totalStudyHours(totalHours)
                .categoryDistribution(Collections.emptyList())
                .scoreTrend(Collections.emptyList())
                .build();
    }

    public String uploadFile(MultipartFile file, String subDir) {
        if (file == null || file.isEmpty()) {
            throw new BusinessException(R.CODE_BAD_REQUEST, "上传文件不能为空");
        }
        String folder = (subDir != null && !subDir.trim().isEmpty()) ? subDir.trim() : "uploads";
        File dir = new File(uploadDir, folder);
        if (!dir.exists()) {
            dir.mkdirs();
        }

        String original = file.getOriginalFilename();
        String ext = "";
        if (original != null && original.lastIndexOf(".") != -1) {
            ext = original.substring(original.lastIndexOf(".")).toLowerCase();
        }
        String fileName = UUID.randomUUID().toString().replace("-", "") + ext;
        File dest = new File(dir, fileName);
        try {
            file.transferTo(dest);
        } catch (IOException e) {
            throw new BusinessException(R.CODE_INTERNAL, "文件保存失败：" + e.getMessage());
        }

        return "/static/" + folder + "/" + fileName;
    }
}
