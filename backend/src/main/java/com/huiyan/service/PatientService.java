package com.huiyan.service;

import cn.dev33.satoken.stp.StpUtil;
import com.baomidou.mybatisplus.core.conditions.query.LambdaQueryWrapper;
import com.baomidou.mybatisplus.extension.plugins.pagination.Page;
import com.huiyan.common.exception.BusinessException;
import com.huiyan.common.response.PageResult;
import com.huiyan.common.response.R;
import com.huiyan.common.util.PasswordUtils;
import com.huiyan.dto.user.UserDTO;
import com.huiyan.entity.*;
import com.huiyan.mapper.*;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

import java.time.LocalDateTime;
import java.util.*;

@Slf4j
@Service
@RequiredArgsConstructor
public class PatientService {

    private final UserMapper userMapper;
    private final RoleMapper roleMapper;
    private final ScreeningCaseMapper screeningCaseMapper;
    private final ScreeningResultMapper screeningResultMapper;

    public Map<String, Object> sendCode(String phone) {
        if (phone == null || phone.trim().isEmpty()) {
            throw new BusinessException(R.CODE_BAD_REQUEST, "手机号不能为空");
        }
        return Map.of("code", "1234", "expireSeconds", 300);
    }

    @Transactional
    public UserDTO.LoginResponse register(String phone, String password, String code) {
        if (phone == null || phone.trim().isEmpty() || password == null || password.trim().isEmpty()) {
            throw new BusinessException(R.CODE_BAD_REQUEST, "手机号与密码不能为空");
        }
        if (!"1234".equals(code)) {
            throw new BusinessException(R.CODE_BAD_REQUEST, "验证码错误或已过期");
        }
        phone = phone.trim();

        User existing = userMapper.selectOne(new LambdaQueryWrapper<User>()
                .eq(User::getUsername, phone)
                .or().eq(User::getPhone, phone)
                .last("LIMIT 1"));
        if (existing != null) {
            throw new BusinessException(R.CODE_BAD_REQUEST, "该手机号已注册，请直接登录");
        }

        Role patientRole = roleMapper.selectOne(new LambdaQueryWrapper<Role>()
                .eq(Role::getCode, "PATIENT")
                .last("LIMIT 1"));
        Integer roleId = patientRole != null ? patientRole.getId() : 3;

        LocalDateTime now = LocalDateTime.now();
        User user = User.builder()
                .username(phone)
                .passwordHash(PasswordUtils.hashPassword(password))
                .realName("患者" + phone.substring(Math.max(0, phone.length() - 4)))
                .phone(phone)
                .roleId(roleId)
                .userType("PATIENT")
                .isActive(true)
                .mustChangePassword(false)
                .build();
        user.setCreatedAt(now);
        user.setUpdatedAt(now);
        userMapper.insert(user);

        // Bind existing cases with same phone
        List<ScreeningCase> existingCases = screeningCaseMapper.selectList(new LambdaQueryWrapper<ScreeningCase>()
                .eq(ScreeningCase::getPhone, phone)
                .or().eq(ScreeningCase::getPatientPhone, phone));
        for (ScreeningCase sc : existingCases) {
            sc.setPatientUserId(user.getId());
            sc.setUpdatedAt(now);
            screeningCaseMapper.updateById(sc);
        }

        StpUtil.login(user.getId());
        String token = StpUtil.getTokenValue();

        UserDTO.UserInfo userInfo = UserDTO.UserInfo.builder()
                .id(user.getId())
                .username(user.getUsername())
                .realName(user.getRealName())
                .phone(user.getPhone())
                .role(patientRole != null ? patientRole.getCode() : "PATIENT")
                .roleName(patientRole != null ? patientRole.getName() : "病患")
                .userType(user.getUserType())
                .build();

        return UserDTO.LoginResponse.builder()
                .token(token)
                .tokenType("Bearer")
                .expiresAt(LocalDateTime.now().plusDays(1))
                .userInfo(userInfo)
                .build();
    }

    public PageResult<ScreeningCase> myReports(long page, long pageSize, String status, User user) {
        LambdaQueryWrapper<ScreeningCase> query = new LambdaQueryWrapper<>();
        query.and(q -> q.eq(ScreeningCase::getPatientUserId, user.getId())
                .or().eq(ScreeningCase::getPhone, user.getPhone())
                .or().eq(ScreeningCase::getPatientPhone, user.getPhone()));

        if (status != null && !status.trim().isEmpty()) {
            query.eq(ScreeningCase::getStatus, status.trim());
        }
        query.orderByDesc(ScreeningCase::getId);

        Page<ScreeningCase> pageParam = new Page<>(Math.max(1, page), Math.max(1, Math.min(100, pageSize)));
        Page<ScreeningCase> result = screeningCaseMapper.selectPage(pageParam, query);

        return PageResult.of(result.getTotal(), page, pageSize, result.getRecords());
    }

    public Map<String, Object> myReportDetail(Integer caseId, User user) {
        ScreeningCase sc = screeningCaseMapper.selectById(caseId);
        if (sc == null) {
            throw new BusinessException(R.CODE_NOT_FOUND, "报告不存在");
        }

        boolean isOwner = Objects.equals(sc.getPatientUserId(), user.getId())
                || (sc.getPhone() != null && sc.getPhone().equals(user.getPhone()))
                || (sc.getPatientPhone() != null && sc.getPatientPhone().equals(user.getPhone()));
        if (!isOwner && !"ADMIN".equalsIgnoreCase(user.getUserType()) && !"TEACHER".equalsIgnoreCase(user.getUserType())) {
            throw new BusinessException(R.CODE_FORBIDDEN, "无权查看该报告");
        }

        List<ScreeningResult> results = screeningResultMapper.selectList(new LambdaQueryWrapper<ScreeningResult>()
                .eq(ScreeningResult::getCaseId, caseId));

        Map<String, Object> map = new HashMap<>();
        map.put("case", sc);
        map.put("results", results);
        return map;
    }

    @Transactional
    public void bindCase(Integer caseId, String phone, User user) {
        ScreeningCase sc = screeningCaseMapper.selectById(caseId);
        if (sc == null) {
            throw new BusinessException(R.CODE_NOT_FOUND, "病例不存在：" + caseId);
        }

        sc.setPhone(phone);
        sc.setPatientPhone(phone);

        User patientUser = userMapper.selectOne(new LambdaQueryWrapper<User>()
                .eq(User::getPhone, phone)
                .last("LIMIT 1"));
        if (patientUser != null) {
            sc.setPatientUserId(patientUser.getId());
        }
        sc.setUpdatedAt(LocalDateTime.now());
        screeningCaseMapper.updateById(sc);
    }
}
