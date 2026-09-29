package com.huiyan.controller;

import com.huiyan.common.response.R;
import com.huiyan.common.util.SecurityUtils;
import com.huiyan.dto.user.UserDTO;
import com.huiyan.entity.UserSetting;
import com.huiyan.service.AuthService;
import lombok.RequiredArgsConstructor;
import org.springframework.web.bind.annotation.*;
import org.springframework.web.multipart.MultipartFile;

import java.util.HashMap;
import java.util.Map;

@RestController
@RequestMapping("/api/v1/user")
@RequiredArgsConstructor
public class UserController {

    private final AuthService authService;

    @GetMapping("/profile")
    public R<UserDTO.UserInfo> getProfile() {
        Integer userId = SecurityUtils.getCurrentUserId();
        return R.ok(authService.getUserProfile(userId));
    }

    @PutMapping("/profile")
    public R<UserDTO.UserInfo> updateProfile(@RequestBody UserDTO.UpdateProfileRequest req) {
        Integer userId = SecurityUtils.getCurrentUserId();
        return R.ok(authService.updateProfile(userId, req), "个人资料修改成功");
    }

    @PutMapping("/password")
    public R<Void> changePassword(@RequestBody UserDTO.ChangePasswordRequest req) {
        Integer userId = SecurityUtils.getCurrentUserId();
        authService.changePassword(userId, req);
        return R.ok(null, "密码修改成功");
    }

    @PostMapping("/avatar")
    public R<Map<String, Object>> uploadAvatar(@RequestParam("file") MultipartFile file) {
        Integer userId = SecurityUtils.getCurrentUserId();
        String avatarUrl = authService.uploadAvatar(userId, file);
        Map<String, Object> map = new HashMap<>();
        map.put("avatar_url", avatarUrl);
        map.put("avatarUrl", avatarUrl);
        map.put("file_name", file.getOriginalFilename());
        map.put("file_size", file.getSize());
        return R.ok(map, "头像上传成功");
    }

    @GetMapping("/setting")
    public R<UserSetting> getSetting() {
        Integer userId = SecurityUtils.getCurrentUserId();
        return R.ok(authService.getUserSetting(userId));
    }

    @PutMapping("/setting")
    public R<UserSetting> updateSetting(@RequestBody UserSetting req) {
        Integer userId = SecurityUtils.getCurrentUserId();
        return R.ok(authService.updateUserSetting(userId, req), "配置保存成功");
    }
}
