package com.huiyan.config;

import cn.dev33.satoken.stp.StpInterface;
import com.huiyan.entity.Role;
import com.huiyan.entity.User;
import com.huiyan.mapper.RoleMapper;
import com.huiyan.mapper.UserMapper;
import lombok.RequiredArgsConstructor;
import org.springframework.stereotype.Component;

import java.util.Collections;
import java.util.List;

@Component
@RequiredArgsConstructor
public class StpInterfaceImpl implements StpInterface {

    private final UserMapper userMapper;
    private final RoleMapper roleMapper;

    @Override
    public List<String> getPermissionList(Object loginId, String loginType) {
        return Collections.emptyList();
    }

    @Override
    public List<String> getRoleList(Object loginId, String loginType) {
        try {
            int userId = Integer.parseInt(loginId.toString());
            User user = userMapper.selectById(userId);
            if (user != null && user.getRoleId() != null) {
                Role role = roleMapper.selectById(user.getRoleId());
                if (role != null && role.getCode() != null) {
                    return Collections.singletonList(role.getCode());
                }
            }
        } catch (Exception ignored) {
        }
        return Collections.emptyList();
    }
}
