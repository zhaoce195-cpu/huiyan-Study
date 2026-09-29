package com.huiyan.controller;

import com.huiyan.common.response.R;
import org.springframework.stereotype.Controller;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.ResponseBody;

import java.io.File;
import java.util.HashMap;
import java.util.Map;

@Controller
public class RootController {

    @GetMapping(value = "/", produces = "application/json")
    @ResponseBody
    public R<Map<String, Object>> root() {
        Map<String, Object> map = new HashMap<>();
        map.put("name", "慧眼教学云后端服务");
        map.put("version", "1.0.0");
        map.put("api", "/api/v1");
        map.put("runtime", "Java 17 / Spring Boot 3");
        return R.ok(map, "ok");
    }

    @GetMapping(value = "/", produces = "text/html")
    public String index() {
        File dist = new File("../frontend/dist/index.html");
        if (!dist.exists()) {
            dist = new File("frontend/dist/index.html");
        }
        if (dist.exists()) {
            return "forward:/index.html";
        }
        return "forward:/api/info";
    }

    @GetMapping("/api/info")
    @ResponseBody
    public R<Map<String, Object>> apiInfo() {
        return root();
    }

    @GetMapping("/health")
    @ResponseBody
    public R<Map<String, String>> health() {
        Map<String, String> map = new HashMap<>();
        map.put("status", "ok");
        return R.ok(map, "ok");
    }
}
