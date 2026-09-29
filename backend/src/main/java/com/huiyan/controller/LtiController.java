package com.huiyan.controller;

import com.huiyan.common.response.R;
import lombok.RequiredArgsConstructor;
import org.springframework.web.bind.annotation.*;

import java.util.Collections;
import java.util.Map;

@RestController
@RequestMapping("/api/v1/lti")
@RequiredArgsConstructor
public class LtiController {

    @GetMapping("/jwks")
    public Map<String, Object> jwks() {
        return Map.of("keys", Collections.emptyList());
    }

    @GetMapping("/platforms")
    public R<Map<String, Object>> listPlatforms() {
        return R.ok(Map.of("platforms", Collections.emptyList()));
    }
}
