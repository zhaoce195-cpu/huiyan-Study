package com.huiyan.config;

import cn.dev33.satoken.interceptor.SaInterceptor;
import cn.dev33.satoken.stp.StpUtil;
import org.springframework.context.annotation.Configuration;
import org.springframework.web.servlet.config.annotation.InterceptorRegistry;
import org.springframework.web.servlet.config.annotation.WebMvcConfigurer;

@Configuration
public class SaTokenConfig implements WebMvcConfigurer {

    @Override
    public void addInterceptors(InterceptorRegistry registry) {
        registry.addInterceptor(new SaInterceptor(handle -> StpUtil.checkLogin()))
                .addPathPatterns("/api/v1/**")
                .excludePathPatterns(
                        "/api/v1/auth/login",
                        "/api/v1/auth/register",
                        "/api/v1/auth/send_code",
                        "/api/v1/auth/wechat/**",
                        "/api/v1/auth/oidc/**",
                        "/api/v1/student-applications",
                        "/api/v1/student-applications/status",
                        "/api/v1/lti/**",
                        "/api/v1/orthanc/**",
                        "/api/v1/orthanc-auth/**",
                        "/health",
                        "/",
                        "/error",
                        "/static/**"
                );
    }
}
