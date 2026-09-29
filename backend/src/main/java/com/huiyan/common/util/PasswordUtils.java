package com.huiyan.common.util;

import lombok.extern.slf4j.Slf4j;
import org.mindrot.jbcrypt.BCrypt;

@Slf4j
public class PasswordUtils {

    /**
     * 对明文密码进行 BCrypt 哈希加密
     */
    public static String hashPassword(String plainPassword) {
        if (plainPassword == null) {
            return null;
        }
        return BCrypt.hashpw(plainPassword, BCrypt.gensalt(12));
    }

    /**
     * 校验明文密码与库中哈希值是否匹配（兼容 Python passlib 生成的 $2b$ 和 $2y$ 版本）
     */
    public static boolean verifyPassword(String plainPassword, String hashedPassword) {
        if (plainPassword == null || hashedPassword == null || hashedPassword.isEmpty()) {
            return false;
        }
        try {
            String normalizedHash = hashedPassword;
            if (hashedPassword.startsWith("$2b$") || hashedPassword.startsWith("$2y$")) {
                normalizedHash = "$2a$" + hashedPassword.substring(4);
            }
            return BCrypt.checkpw(plainPassword, normalizedHash);
        } catch (Exception e) {
            log.warn("BCrypt 密码校验异常: {}", e.getMessage());
            return false;
        }
    }
}
