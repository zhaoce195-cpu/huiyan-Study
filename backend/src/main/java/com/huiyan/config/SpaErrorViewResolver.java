package com.huiyan.config;

import jakarta.servlet.http.HttpServletRequest;
import org.springframework.boot.autoconfigure.web.servlet.error.ErrorViewResolver;
import org.springframework.http.HttpStatus;
import org.springframework.stereotype.Component;
import org.springframework.web.servlet.ModelAndView;

import java.util.Map;

/**
 * SPA 单页面应用路由支持
 * 当前端路由在浏览器刷新或直接输入时，由 Spring Boot 将 404 请求优雅转发到 index.html
 */
@Component
public class SpaErrorViewResolver implements ErrorViewResolver {

    @Override
    public ModelAndView resolveErrorView(HttpServletRequest request, HttpStatus status, Map<String, Object> model) {
        if (status == HttpStatus.NOT_FOUND) {
            String path = request.getRequestURI();
            if (!path.startsWith("/api") && !path.startsWith("/static")) {
                return new ModelAndView("forward:/index.html");
            }
        }
        return null;
    }
}
