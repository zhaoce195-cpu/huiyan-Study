package com.huiyan.controller;

import com.huiyan.common.response.R;
import lombok.RequiredArgsConstructor;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.web.bind.annotation.*;

import java.util.Collections;
import java.util.Map;

@RestController
@RequestMapping("/api/v1/dicomweb")
@RequiredArgsConstructor
public class DicomwebController {

    @Value("${huiyan.orthanc-enabled:false}")
    private boolean orthancEnabled;

    @GetMapping("/status")
    public R<Map<String, Object>> pacsStatus() {
        return R.ok(Map.of(
                "enabled", orthancEnabled,
                "available", false
        ));
    }

    @GetMapping("/cases/{caseNo}/instances")
    public R<Map<String, Object>> listCaseInstances(@PathVariable String caseNo) {
        return R.ok(Map.of(
                "caseNo", caseNo,
                "instances", Collections.emptyList()
        ));
    }

    @GetMapping("/cases/{caseNo}/segmentations")
    public R<Map<String, Object>> listCaseSegmentations(@PathVariable String caseNo) {
        return R.ok(Map.of(
                "segmentations", Collections.emptyList(),
                "count", 0
        ));
    }
}
