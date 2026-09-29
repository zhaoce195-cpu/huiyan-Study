package com.huiyan.controller;

import org.springframework.web.bind.annotation.*;

import java.util.Map;

@RestController
@RequestMapping("/api/v1/orthanc-auth")
public class OrthancAuthController {

    @PostMapping("/v1/authorization")
    public Map<String, Object> authorize(@RequestBody Map<String, Object> req) {
        return Map.of(
                "granted", true,
                "validity", 300
        );
    }
}
