package com.huiyan.config;

import org.springframework.beans.factory.annotation.Value;
import org.springframework.context.annotation.Configuration;
import org.springframework.web.servlet.config.annotation.CorsRegistry;
import org.springframework.web.servlet.config.annotation.ResourceHandlerRegistry;
import org.springframework.web.servlet.config.annotation.WebMvcConfigurer;

import java.io.File;

@Configuration
public class WebMvcConfig implements WebMvcConfigurer {

    @Value("${huiyan.upload-dir:app/static}")
    private String uploadDir;

    @Override
    public void addCorsMappings(CorsRegistry registry) {
        registry.addMapping("/**")
                .allowedOriginPatterns("*")
                .allowedMethods("GET", "POST", "PUT", "DELETE", "OPTIONS", "PATCH")
                .allowedHeaders("*")
                .exposedHeaders("Content-Disposition", "X-Process-Time")
                .allowCredentials(true)
                .maxAge(3600);
    }

    @Override
    public void addResourceHandlers(ResourceHandlerRegistry registry) {
        File dir = new File(uploadDir);
        String absolutePath = dir.getAbsolutePath().replace("\\", "/");
        if (!absolutePath.endsWith("/")) {
            absolutePath += "/";
        }
        registry.addResourceHandler("/static/**")
                .addResourceLocations("file:" + absolutePath, "file:app/static/")
                .setCachePeriod(0);

        // 托管前端构建产物 (dist)
        File frontendDist = new File("../frontend/dist");
        if (!frontendDist.exists()) {
            frontendDist = new File("frontend/dist");
        }
        if (frontendDist.exists()) {
            String distPath = frontendDist.getAbsolutePath().replace("\\", "/");
            if (!distPath.endsWith("/")) {
                distPath += "/";
            }
            registry.addResourceHandler("/**")
                    .addResourceLocations("file:" + distPath, "classpath:/static/")
                    .setCachePeriod(0);
        }
    }
}
