package com.huiyan.service;

import cn.dev33.satoken.stp.StpUtil;
import com.baomidou.mybatisplus.core.conditions.query.LambdaQueryWrapper;
import com.huiyan.common.exception.BusinessException;
import com.huiyan.common.response.R;
import com.huiyan.common.util.PasswordUtils;
import com.huiyan.dto.user.UserDTO;
import com.huiyan.entity.Role;
import com.huiyan.entity.User;
import com.huiyan.entity.UserSetting;
import com.huiyan.mapper.RoleMapper;
import com.huiyan.mapper.UserMapper;
import com.huiyan.mapper.UserSettingMapper;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;
import org.springframework.web.multipart.MultipartFile;

import java.io.File;
import java.io.IOException;
import java.time.LocalDateTime;
import java.util.UUID;

@Slf4j
@Service
@RequiredArgsConstructor
public class AuthService {

    private final UserMapper userMapper;
    private final RoleMapper roleMapper;
    private final UserSettingMapper userSettingMapper;

    @Value("${huiyan.upload-dir:app/static}")
    private String uploadDir;

    @Transactional
    public UserDTO.LoginResponse login(UserDTO.LoginRequest req, String clientIp) {
        if (req.getUsername() == null || req.getPassword() == null) {
            throw new BusinessException(R.CODE_BAD_REQUEST, "账号或密码不能为空");
        }

        User user = userMapper.selectOne(new LambdaQueryWrapper<User>()
                .eq(User::getUsername, req.getUsername().trim()));
        if (user == null) {
            throw new BusinessException(R.CODE_BAD_REQUEST, "账号或密码错误");
        }

        if (!PasswordUtils.verifyPassword(req.getPassword(), user.getPasswordHash())) {
            throw new BusinessException(R.CODE_BAD_REQUEST, "账号或密码错误");
        }

        if (Boolean.FALSE.equals(user.getIsActive())) {
            throw new BusinessException(R.CODE_FORBIDDEN, "账号已被停用，请联系管理员");
        }

        Role role = roleMapper.selectById(user.getRoleId());
        if (role == null) {
            throw new BusinessException(R.CODE_INTERNAL, "账号未关联角色，请联系管理员");
        }

        // 确保个性化设置存在
        UserSetting setting = userSettingMapper.selectOne(new LambdaQueryWrapper<UserSetting>()
                .eq(UserSetting::getUserId, user.getId()));
        if (setting == null) {
            setting = UserSetting.builder()
                    .userId(user.getId())
                    .theme("light")
                    .fontSize("normal")
                    .language("zh-CN")
                    .notifyMessage(true)
                    .notifyEmail(false)
                    .notifySms(false)
                    .notifySound(true)
                    .build();
            setting.setCreatedAt(LocalDateTime.now());
            setting.setUpdatedAt(LocalDateTime.now());
            userSettingMapper.insert(setting);
        }

        // 更新登录时间与IP
        user.setLastLoginAt(LocalDateTime.now());
        if (clientIp != null && !clientIp.isEmpty()) {
            user.setLastLoginIp(clientIp.length() > 64 ? clientIp.substring(0, 64) : clientIp);
        }
        user.setUpdatedAt(LocalDateTime.now());
        userMapper.updateById(user);

        // Sa-Token 登录
        StpUtil.login(user.getId());
        String token = StpUtil.getTokenValue();
        LocalDateTime expiresAt = LocalDateTime.now().plusHours(12);

        UserDTO.UserInfo userInfo = buildUserInfo(user, role);

        return UserDTO.LoginResponse.builder()
                .token(token)
                .tokenType("Bearer")
                .expiresAt(expiresAt)
                .userInfo(userInfo)
                .build();
    }

    public void logout() {
        if (StpUtil.isLogin()) {
            StpUtil.logout();
        }
    }

    public UserDTO.UserInfo getUserProfile(Integer userId) {
        User user = userMapper.selectById(userId);
        if (user == null) {
            throw new BusinessException(R.CODE_NOT_FOUND, "用户不存在");
        }
        Role role = roleMapper.selectById(user.getRoleId());
        return buildUserInfo(user, role);
    }

    @Transactional
    public UserDTO.UserInfo updateProfile(Integer userId, UserDTO.UpdateProfileRequest req) {
        User user = userMapper.selectById(userId);
        if (user == null) {
            throw new BusinessException(R.CODE_NOT_FOUND, "用户不存在");
        }
        if (req.getRealName() != null) user.setRealName(req.getRealName());
        if (req.getPhone() != null) user.setPhone(req.getPhone());
        if (req.getEmail() != null) user.setEmail(req.getEmail());
        if (req.getDepartment() != null) user.setDepartment(req.getDepartment());
        if (req.getTitle() != null) user.setTitle(req.getTitle());
        user.setUpdatedAt(LocalDateTime.now());
        userMapper.updateById(user);

        Role role = roleMapper.selectById(user.getRoleId());
        return buildUserInfo(user, role);
    }

    @Transactional
    public void changePassword(Integer userId, UserDTO.ChangePasswordRequest req) {
        User user = userMapper.selectById(userId);
        if (user == null) {
            throw new BusinessException(R.CODE_NOT_FOUND, "用户不存在");
        }
        if (!PasswordUtils.verifyPassword(req.getOldPassword(), user.getPasswordHash())) {
            throw new BusinessException(R.CODE_BAD_REQUEST, "原密码错误");
        }
        if (req.getNewPassword() == null || req.getNewPassword().length() < 6) {
            throw new BusinessException(R.CODE_BAD_REQUEST, "新密码长度不能少于 6 位");
        }
        if (!req.getNewPassword().equals(req.getConfirmPassword())) {
            throw new BusinessException(R.CODE_BAD_REQUEST, "两次输入的新密码不一致");
        }

        user.setPasswordHash(PasswordUtils.hashPassword(req.getNewPassword()));
        user.setMustChangePassword(false);
        user.setUpdatedAt(LocalDateTime.now());
        userMapper.updateById(user);
    }

    @Transactional
    public String uploadAvatar(Integer userId, MultipartFile file) {
        if (file.isEmpty()) {
            throw new BusinessException(R.CODE_BAD_REQUEST, "上传头像不能为空");
        }
        String originalFilename = file.getOriginalFilename();
        String ext = "";
        if (originalFilename != null && originalFilename.lastIndexOf(".") != -1) {
            ext = originalFilename.substring(originalFilename.lastIndexOf(".")).toLowerCase();
        }
        if (!ext.matches("\\.(jpg|jpeg|png|webp|bmp)")) {
            throw new BusinessException(R.CODE_BAD_REQUEST, "不支持的图片格式，仅支持 jpg/png/webp/bmp");
        }

        File avatarDir = new File(uploadDir, "avatars");
        if (!avatarDir.exists()) {
            avatarDir.mkdirs();
        }

        String fileName = UUID.randomUUID().toString().replace("-", "") + ext;
        File dest = new File(avatarDir, fileName);
        try {
            file.transferTo(dest);
        } catch (IOException e) {
            throw new BusinessException(R.CODE_INTERNAL, "头像保存失败：" + e.getMessage());
        }

        String avatarUrl = "/static/avatars/" + fileName;
        User user = userMapper.selectById(userId);
        if (user != null) {
            user.setAvatar(avatarUrl);
            user.setUpdatedAt(LocalDateTime.now());
            userMapper.updateById(user);
        }
        return avatarUrl;
    }

    public UserSetting getUserSetting(Integer userId) {
        UserSetting setting = userSettingMapper.selectOne(new LambdaQueryWrapper<UserSetting>()
                .eq(UserSetting::getUserId, userId));
        if (setting == null) {
            setting = UserSetting.builder()
                    .userId(userId)
                    .theme("light")
                    .fontSize("normal")
                    .language("zh-CN")
                    .notifyMessage(true)
                    .notifyEmail(false)
                    .notifySms(false)
                    .notifySound(true)
                    .build();
            setting.setCreatedAt(LocalDateTime.now());
            setting.setUpdatedAt(LocalDateTime.now());
            userSettingMapper.insert(setting);
        }
        return setting;
    }

    @Transactional
    public UserSetting updateUserSetting(Integer userId, UserSetting req) {
        UserSetting setting = getUserSetting(userId);
        if (req.getTheme() != null) setting.setTheme(req.getTheme());
        if (req.getFontSize() != null) setting.setFontSize(req.getFontSize());
        if (req.getLanguage() != null) setting.setLanguage(req.getLanguage());
        if (req.getNotifyMessage() != null) setting.setNotifyMessage(req.getNotifyMessage());
        if (req.getNotifyEmail() != null) setting.setNotifyEmail(req.getNotifyEmail());
        if (req.getNotifySms() != null) setting.setNotifySms(req.getNotifySms());
        if (req.getNotifySound() != null) setting.setNotifySound(req.getNotifySound());
        setting.setUpdatedAt(LocalDateTime.now());
        userSettingMapper.updateById(setting);
        return setting;
    }

    private UserDTO.UserInfo buildUserInfo(User user, Role role) {
        return UserDTO.UserInfo.builder()
                .id(user.getId())
                .username(user.getUsername())
                .realName(user.getRealName() != null ? user.getRealName() : "")
                .phone(user.getPhone() != null ? user.getPhone() : "")
                .email(user.getEmail() != null ? user.getEmail() : "")
                .department(user.getDepartment() != null ? user.getDepartment() : "")
                .title(user.getTitle() != null ? user.getTitle() : "")
                .avatar(user.getAvatar() != null ? user.getAvatar() : "")
                .role(role != null ? role.getCode() : "")
                .roleName(role != null ? role.getName() : "")
                .userType(user.getUserType() != null ? user.getUserType() : "student")
                .isActive(user.getIsActive() != null ? user.getIsActive() : true)
                .mustChangePassword(Boolean.TRUE.equals(user.getMustChangePassword()))
                .lastLoginAt(user.getLastLoginAt())
                .lastLoginIp(user.getLastLoginIp() != null ? user.getLastLoginIp() : "")
                .createdAt(user.getCreatedAt())
                .updatedAt(user.getUpdatedAt())
                .build();
    }
}
