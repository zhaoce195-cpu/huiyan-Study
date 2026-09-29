package com.huiyan.common.util;

import cn.dev33.satoken.stp.StpUtil;
import com.huiyan.common.exception.BusinessException;
import com.huiyan.common.response.R;
import com.huiyan.entity.User;
import com.huiyan.mapper.UserMapper;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.stereotype.Component;

@Component
public class SecurityUtils {

    private static UserMapper userMapper;

    @Autowired
    public void setUserMapper(UserMapper mapper) {
        SecurityUtils.userMapper = mapper;
    }

    public static Integer getCurrentUserId() {
        if (!StpUtil.isLogin()) {
            throw new BusinessException(R.CODE_UNAUTHORIZED, "未登录或登录已失效");
        }
        return Integer.parseInt(StpUtil.getLoginId().toString());
    }

    public static User getCurrentUser() {
        Integer userId = getCurrentUserId();
        User user = userMapper.selectById(userId);
        if (user == null) {
            throw new BusinessException(R.CODE_UNAUTHORIZED, "用户不存在");
        }
        if (Boolean.FALSE.equals(user.getIsActive())) {
            throw new BusinessException(R.CODE_FORBIDDEN, "账号已被停用，请联系管理员");
        }
        return user;
    }
}
