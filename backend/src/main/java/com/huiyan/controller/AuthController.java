package com.huiyan.controller;

import com.huiyan.common.response.R;
import com.huiyan.dto.user.UserDTO;
import com.huiyan.service.AuthService;
import jakarta.servlet.http.HttpServletRequest;
import lombok.RequiredArgsConstructor;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.web.bind.annotation.*;

import java.util.HashMap;
import java.util.Map;

@RestController
@RequestMapping("/api/v1/auth")
@RequiredArgsConstructor
public class AuthController {

    private final AuthService authService;

    @Value("${huiyan.keycloak-base-url:http://localhost:8085}")
    private String keycloakBaseUrl;

    @Value("${huiyan.keycloak-login-enabled:false}")
    private boolean keycloakLoginEnabled;

    @PostMapping("/login")
    public R<UserDTO.LoginResponse> login(@RequestBody UserDTO.LoginRequest req, HttpServletRequest request) {
        String clientIp = request.getHeader("X-Forwarded-For");
        if (clientIp == null || clientIp.isEmpty()) {
            clientIp = request.getRemoteAddr();
        }
        UserDTO.LoginResponse response = authService.login(req, clientIp);
        return R.ok(response, "登录成功");
    }

    @PostMapping("/logout")
    public R<Void> logout() {
        authService.logout();
        return R.ok(null, "已退出登录");
    }

    @GetMapping("/oidc/config")
    public R<Map<String, Object>> getOidcConfig() {
        Map<String, Object> map = new HashMap<>();
        map.put("enabled", keycloakLoginEnabled);
        map.put("issuer", keycloakBaseUrl + "/realms/huiyan");
        map.put("clientId", "huiyan-frontend");
        map.put("authorizationEndpoint", keycloakBaseUrl + "/realms/huiyan/protocol/openid-connect/auth");
        map.put("tokenEndpoint", keycloakBaseUrl + "/realms/huiyan/protocol/openid-connect/token");
        map.put("endSessionEndpoint", keycloakBaseUrl + "/realms/huiyan/protocol/openid-connect/logout");
        map.put("accountUrl", keycloakBaseUrl + "/realms/huiyan/account");
        return R.ok(map);
    }

    @PostMapping("/wechat/login")
    public R<Map<String, Object>> wechatLogin(@RequestBody UserDTO.WechatLoginRequest req) {
        Map<String, Object> map = new HashMap<>();
        map.put("needBind", true);
        map.put("ticket", "ticket_" + System.currentTimeMillis());
        map.put("login", null);
        return R.ok(map);
    }

    @PostMapping("/wechat/bind")
    public R<UserDTO.LoginResponse> wechatBind(@RequestBody UserDTO.WechatBindRequest req, HttpServletRequest request) {
        UserDTO.LoginRequest loginReq = new UserDTO.LoginRequest();
        loginReq.setUsername(req.getUsername());
        loginReq.setPassword(req.getPassword());
        return login(loginReq, request);
    }

    private final com.huiyan.service.PatientService patientService;

    @PostMapping("/send_code")
    public R<Map<String, Object>> sendCode(@RequestBody Map<String, Object> req) {
        String phone = (String) req.get("phone");
        return R.ok(patientService.sendCode(phone), "验证码已发送");
    }

    @PostMapping("/register")
    public R<UserDTO.LoginResponse> register(@RequestBody Map<String, Object> req) {
        String phone = (String) req.get("phone");
        String password = (String) req.get("password");
        String code = (String) req.get("code");
        return R.ok(patientService.register(phone, password, code), "注册成功");
    }
}
