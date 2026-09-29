package com.huiyan.service;

import com.baomidou.mybatisplus.core.conditions.query.LambdaQueryWrapper;
import com.baomidou.mybatisplus.extension.plugins.pagination.Page;
import com.huiyan.common.exception.BusinessException;
import com.huiyan.common.response.PageResult;
import com.huiyan.common.response.R;
import com.huiyan.common.util.PasswordUtils;
import com.huiyan.dto.user.AdminUserDTO;
import com.huiyan.entity.Role;
import com.huiyan.entity.User;
import com.huiyan.mapper.RoleMapper;
import com.huiyan.mapper.UserMapper;
import lombok.RequiredArgsConstructor;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

import java.time.LocalDateTime;
import java.util.*;
import java.util.stream.Collectors;

@Service
@RequiredArgsConstructor
public class AdminUserService {

    private final UserMapper userMapper;
    private final RoleMapper roleMapper;

    public PageResult<AdminUserDTO.AdminUserItem> listUsers(
            long page, long pageSize, String username, String realName, String roleCode, String department, Boolean isActive
    ) {
        LambdaQueryWrapper<User> query = new LambdaQueryWrapper<>();
        if (username != null && !username.trim().isEmpty()) {
            query.like(User::getUsername, username.trim());
        }
        if (realName != null && !realName.trim().isEmpty()) {
            query.like(User::getRealName, realName.trim());
        }
        if (department != null && !department.trim().isEmpty()) {
            query.like(User::getDepartment, department.trim());
        }
        if (isActive != null) {
            query.eq(User::getIsActive, isActive);
        }
        if (roleCode != null && !roleCode.trim().isEmpty()) {
            Role role = roleMapper.selectOne(new LambdaQueryWrapper<Role>().eq(Role::getCode, roleCode.trim()));
            if (role != null) {
                query.eq(User::getRoleId, role.getId());
            } else {
                return PageResult.of(0, page, pageSize, Collections.emptyList());
            }
        }
        query.orderByDesc(User::getId);

        Page<User> pageParam = new Page<>(page, pageSize);
        Page<User> result = userMapper.selectPage(pageParam, query);

        List<Role> allRoles = roleMapper.selectList(null);
        Map<Integer, Role> roleMap = allRoles.stream().collect(Collectors.toMap(Role::getId, r -> r));

        List<AdminUserDTO.AdminUserItem> items = result.getRecords().stream().map(u -> {
            Role r = roleMap.get(u.getRoleId());
            return AdminUserDTO.AdminUserItem.builder()
                    .id(u.getId())
                    .username(u.getUsername())
                    .realName(u.getRealName() != null ? u.getRealName() : "")
                    .role(r != null ? r.getCode() : "")
                    .roleName(r != null ? r.getName() : "")
                    .department(u.getDepartment() != null ? u.getDepartment() : "")
                    .hospitalName(u.getHospitalName() != null ? u.getHospitalName() : "")
                    .isActive(Boolean.TRUE.equals(u.getIsActive()))
                    .mustChangePassword(Boolean.TRUE.equals(u.getMustChangePassword()))
                    .lastLoginAt(u.getLastLoginAt())
                    .createdAt(u.getCreatedAt())
                    .build();
        }).collect(Collectors.toList());

        return PageResult.of(result.getTotal(), page, pageSize, items);
    }

    @Transactional
    public User createUser(AdminUserDTO.AdminUserCreate req) {
        if (req.getUsername() == null || req.getUsername().trim().isEmpty()) {
            throw new BusinessException(R.CODE_BAD_REQUEST, "用户名不能为空");
        }
        User existing = userMapper.selectOne(new LambdaQueryWrapper<User>()
                .eq(User::getUsername, req.getUsername().trim()));
        if (existing != null) {
            throw new BusinessException(R.CODE_BAD_REQUEST, "用户名已存在");
        }

        String rawPassword = req.getPassword() != null && !req.getPassword().trim().isEmpty() ? req.getPassword() : "Huiyan@123";
        Role role = null;
        if (req.getRole() != null) {
            role = roleMapper.selectOne(new LambdaQueryWrapper<Role>().eq(Role::getCode, req.getRole().trim()));
        }
        if (role == null) {
            role = roleMapper.selectOne(new LambdaQueryWrapper<Role>().eq(Role::getCode, "STUDENT"));
        }

        User user = User.builder()
                .username(req.getUsername().trim())
                .passwordHash(PasswordUtils.hashPassword(rawPassword))
                .realName(req.getRealName() != null ? req.getRealName().trim() : "")
                .phone(req.getPhone() != null ? req.getPhone().trim() : "")
                .email(req.getEmail() != null ? req.getEmail().trim() : "")
                .department(req.getDepartment() != null ? req.getDepartment().trim() : "")
                .departmentId(req.getDepartmentId())
                .title(req.getTitle() != null ? req.getTitle().trim() : "")
                .avatar("")
                .roleId(role != null ? role.getId() : 1)
                .userType(role != null ? role.getCode().toLowerCase() : "student")
                .isActive(true)
                .mustChangePassword(false)
                .build();
        user.setCreatedAt(LocalDateTime.now());
        user.setUpdatedAt(LocalDateTime.now());
        userMapper.insert(user);
        return user;
    }

    @Transactional
    public void updateUser(Integer id, AdminUserDTO.AdminUserUpdate req) {
        User user = userMapper.selectById(id);
        if (user == null) {
            throw new BusinessException(R.CODE_NOT_FOUND, "用户不存在");
        }
        if (req.getRealName() != null) user.setRealName(req.getRealName());
        if (req.getPhone() != null) user.setPhone(req.getPhone());
        if (req.getEmail() != null) user.setEmail(req.getEmail());
        if (req.getDepartment() != null) user.setDepartment(req.getDepartment());
        if (req.getDepartmentId() != null) user.setDepartmentId(req.getDepartmentId());
        if (req.getTitle() != null) user.setTitle(req.getTitle());
        if (req.getIsActive() != null) user.setIsActive(req.getIsActive());
        if (req.getMustChangePassword() != null) user.setMustChangePassword(req.getMustChangePassword());

        if (req.getRole() != null && !req.getRole().trim().isEmpty()) {
            Role role = roleMapper.selectOne(new LambdaQueryWrapper<Role>().eq(Role::getCode, req.getRole().trim()));
            if (role != null) {
                user.setRoleId(role.getId());
                user.setUserType(role.getCode().toLowerCase());
            }
        }
        user.setUpdatedAt(LocalDateTime.now());
        userMapper.updateById(user);
    }

    @Transactional
    public void deleteUser(Integer id) {
        User user = userMapper.selectById(id);
        if (user == null) {
            throw new BusinessException(R.CODE_NOT_FOUND, "用户不存在");
        }
        if ("admin".equalsIgnoreCase(user.getUsername())) {
            throw new BusinessException(R.CODE_BAD_REQUEST, "内置超级管理员账号禁止删除");
        }
        userMapper.deleteById(id);
    }

    @Transactional
    public Map<String, Object> resetPassword(Integer id) {
        User user = userMapper.selectById(id);
        if (user == null) {
            throw new BusinessException(R.CODE_NOT_FOUND, "用户不存在");
        }
        String tempPassword = "Hy@" + (100000 + new Random().nextInt(900000));
        user.setPasswordHash(PasswordUtils.hashPassword(tempPassword));
        user.setMustChangePassword(true);
        user.setUpdatedAt(LocalDateTime.now());
        userMapper.updateById(user);

        Map<String, Object> map = new HashMap<>();
        map.put("userId", user.getId());
        map.put("username", user.getUsername());
        map.put("tempPassword", tempPassword);
        map.put("mustChangePassword", true);
        return map;
    }

    @Transactional
    public void toggleStatus(Integer id) {
        User user = userMapper.selectById(id);
        if (user == null) {
            throw new BusinessException(R.CODE_NOT_FOUND, "用户不存在");
        }
        if ("admin".equalsIgnoreCase(user.getUsername())) {
            throw new BusinessException(R.CODE_BAD_REQUEST, "超级管理员账号不能被停用");
        }
        user.setIsActive(!Boolean.TRUE.equals(user.getIsActive()));
        user.setUpdatedAt(LocalDateTime.now());
        userMapper.updateById(user);
    }
}
