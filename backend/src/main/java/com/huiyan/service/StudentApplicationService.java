package com.huiyan.service;

import com.baomidou.mybatisplus.core.conditions.query.LambdaQueryWrapper;
import com.baomidou.mybatisplus.extension.plugins.pagination.Page;
import com.huiyan.common.exception.BusinessException;
import com.huiyan.common.response.PageResult;
import com.huiyan.common.response.R;
import com.huiyan.common.util.PasswordUtils;
import com.huiyan.entity.*;
import com.huiyan.mapper.*;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

import java.security.SecureRandom;
import java.time.LocalDateTime;
import java.util.*;
import java.util.stream.Collectors;

@Slf4j
@Service
@RequiredArgsConstructor
public class StudentApplicationService {

    private final StudentApplicationMapper studentApplicationMapper;
    private final UserMapper userMapper;
    private final RoleMapper roleMapper;
    private final DepartmentMapper departmentMapper;
    private final UserMessageMapper userMessageMapper;

    public StudentApplication apply(Map<String, Object> req) {
        String phone = (String) req.get("phone");
        String realName = (String) req.get("realName");
        String department = (String) req.getOrDefault("department", "");
        String reason = (String) req.getOrDefault("reason", "");

        if (phone == null || phone.trim().isEmpty() || realName == null || realName.trim().isEmpty()) {
            throw new BusinessException(R.CODE_BAD_REQUEST, "姓名与手机号不能为空");
        }
        phone = phone.trim();
        realName = realName.trim();

        StudentApplication pending = studentApplicationMapper.selectOne(new LambdaQueryWrapper<StudentApplication>()
                .eq(StudentApplication::getPhone, phone)
                .eq(StudentApplication::getStatus, "PENDING")
                .last("LIMIT 1"));
        if (pending != null) {
            throw new BusinessException(R.CODE_BAD_REQUEST, "该手机号已有待审核申请，请等待审核结果");
        }

        User taken = userMapper.selectOne(new LambdaQueryWrapper<User>()
                .eq(User::getUsername, phone)
                .or().eq(User::getPhone, phone)
                .last("LIMIT 1"));
        if (taken != null) {
            Role role = taken.getRoleId() != null ? roleMapper.selectById(taken.getRoleId()) : null;
            if (role != null && "STUDENT".equalsIgnoreCase(role.getCode())) {
                throw new BusinessException(R.CODE_BAD_REQUEST, "该手机号已是学员账号，请从学生入口登录");
            }
            throw new BusinessException(R.CODE_BAD_REQUEST, "该手机号已被其他账号使用，请联系管理员");
        }

        StudentApplication app = StudentApplication.builder()
                .realName(realName)
                .phone(phone)
                .department(department)
                .reason(reason)
                .status("PENDING")
                .build();
        app.setCreatedAt(LocalDateTime.now());
        app.setUpdatedAt(LocalDateTime.now());
        studentApplicationMapper.insert(app);

        return app;
    }

    public Map<String, Object> queryByPhone(String phone) {
        if (phone == null || phone.trim().isEmpty()) {
            return Map.of("found", false);
        }
        String p = phone.trim();
        StudentApplication app = studentApplicationMapper.selectOne(new LambdaQueryWrapper<StudentApplication>()
                .eq(StudentApplication::getPhone, p)
                .orderByDesc(StudentApplication::getId)
                .last("LIMIT 1"));

        if (app == null) {
            return Map.of("found", false);
        }

        String username = "";
        if (app.getCreatedUserId() != null) {
            User u = userMapper.selectById(app.getCreatedUserId());
            if (u != null) username = u.getUsername();
        }

        Map<String, Object> res = new HashMap<>();
        res.put("found", true);
        res.put("status", app.getStatus());
        res.put("realName", app.getRealName());
        res.put("reviewComment", "REJECTED".equalsIgnoreCase(app.getStatus()) ? app.getReviewComment() : "");
        res.put("accountUsername", "APPROVED".equalsIgnoreCase(app.getStatus()) ? username : "");
        res.put("createdAt", app.getCreatedAt());
        res.put("reviewedAt", app.getReviewedAt());
        return res;
    }

    public PageResult<StudentApplication> listApps(long page, long pageSize, String keyword, String status) {
        LambdaQueryWrapper<StudentApplication> query = new LambdaQueryWrapper<>();
        if (status != null && !status.trim().isEmpty()) {
            query.eq(StudentApplication::getStatus, status.trim());
        }
        if (keyword != null && !keyword.trim().isEmpty()) {
            String kw = keyword.trim();
            query.and(q -> q.like(StudentApplication::getRealName, kw)
                    .or().like(StudentApplication::getPhone, kw)
                    .or().like(StudentApplication::getDepartment, kw)
                    .or().like(StudentApplication::getReason, kw));
        }
        query.orderByDesc(StudentApplication::getId);

        Page<StudentApplication> pageParam = new Page<>(Math.max(1, page), Math.max(1, Math.min(200, pageSize)));
        Page<StudentApplication> result = studentApplicationMapper.selectPage(pageParam, query);

        populateMetadata(result.getRecords());
        return PageResult.of(result.getTotal(), page, pageSize, result.getRecords());
    }

    @Transactional
    public StudentApplication review(Integer appId, boolean accept, String comment, User reviewer) {
        StudentApplication app = studentApplicationMapper.selectById(appId);
        if (app == null) {
            throw new BusinessException(R.CODE_NOT_FOUND, "申请不存在：" + appId);
        }
        if (!"PENDING".equalsIgnoreCase(app.getStatus())) {
            throw new BusinessException(R.CODE_BAD_REQUEST, "申请已审核（" + app.getStatus() + "），无法再次操作");
        }

        String c = comment != null ? comment.trim() : "";
        if (!accept && c.isEmpty()) {
            throw new BusinessException(R.CODE_BAD_REQUEST, "驳回必须填写理由");
        }

        LocalDateTime now = LocalDateTime.now();
        app.setReviewerId(reviewer.getId());
        app.setReviewedAt(now);
        app.setReviewComment(c);

        if (accept) {
            Role studentRole = roleMapper.selectOne(new LambdaQueryWrapper<Role>()
                    .eq(Role::getCode, "STUDENT")
                    .last("LIMIT 1"));
            if (studentRole == null) {
                throw new BusinessException(R.CODE_INTERNAL, "系统未配置学员角色");
            }

            String tempPassword = generateTempPassword();
            String username = app.getPhone();
            Long existCount = userMapper.selectCount(new LambdaQueryWrapper<User>().eq(User::getUsername, username));
            if (existCount != null && existCount > 0) {
                username = "s" + app.getPhone();
            }

            Integer deptId = null;
            if (app.getDepartment() != null && !app.getDepartment().trim().isEmpty()) {
                Department dept = departmentMapper.selectOne(new LambdaQueryWrapper<Department>()
                        .eq(Department::getName, app.getDepartment().trim())
                        .eq(Department::getIsActive, true)
                        .isNull(Department::getHospitalId)
                        .last("LIMIT 1"));
                if (dept != null) deptId = dept.getId();
            }

            User user = User.builder()
                    .username(username)
                    .passwordHash(PasswordUtils.hashPassword(tempPassword))
                    .realName(app.getRealName())
                    .phone(app.getPhone())
                    .department(app.getDepartment())
                    .departmentId(deptId)
                    .roleId(studentRole.getId())
                    .userType("STUDENT")
                    .isActive(true)
                    .mustChangePassword(true)
                    .build();
            user.setCreatedAt(now);
            user.setUpdatedAt(now);
            userMapper.insert(user);

            app.setStatus("APPROVED");
            app.setCreatedUserId(user.getId());
            app.setAccountUsername(username);
            app.setTempPassword(tempPassword);

            // Create welcome message
            UserMessage msg = UserMessage.builder()
                    .userId(user.getId())
                    .type("system")
                    .title("欢迎加入慧眼医学教育实训平台")
                    .content("您的学员账号开通成功！初始密码为：" + tempPassword + "，请在首次登录后及时修改密码。")
                    .refType("student_application")
                    .refId(app.getId())
                    .isRead(false)
                    .build();
            msg.setCreatedAt(now);
            userMessageMapper.insert(msg);
        } else {
            app.setStatus("REJECTED");
        }

        app.setUpdatedAt(now);
        studentApplicationMapper.updateById(app);

        populateMetadata(List.of(app));
        return app;
    }

    private void populateMetadata(List<StudentApplication> list) {
        if (list == null || list.isEmpty()) return;

        Set<Integer> userIds = new HashSet<>();
        for (StudentApplication a : list) {
            if (a.getReviewerId() != null) userIds.add(a.getReviewerId());
            if (a.getCreatedUserId() != null) userIds.add(a.getCreatedUserId());
        }

        Map<Integer, User> userMap = new HashMap<>();
        if (!userIds.isEmpty()) {
            List<User> users = userMapper.selectBatchIds(userIds);
            for (User u : users) {
                userMap.put(u.getId(), u);
            }
        }

        for (StudentApplication a : list) {
            User reviewer = userMap.get(a.getReviewerId());
            if (reviewer != null) {
                a.setReviewerName(reviewer.getRealName() != null && !reviewer.getRealName().isEmpty() ? reviewer.getRealName() : reviewer.getUsername());
            }
            User created = userMap.get(a.getCreatedUserId());
            if (created != null) {
                a.setCreatedUserName(created.getRealName() != null && !created.getRealName().isEmpty() ? created.getRealName() : created.getUsername());
                if (a.getAccountUsername() == null) {
                    a.setAccountUsername(created.getUsername());
                }
            }
        }
    }

    private String generateTempPassword() {
        SecureRandom random = new SecureRandom();
        int digits = 100000 + random.nextInt(900000);
        return "Huiyan@" + digits;
    }
}
