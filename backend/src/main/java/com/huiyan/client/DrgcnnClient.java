package com.huiyan.client;

import com.fasterxml.jackson.databind.JsonNode;
import com.fasterxml.jackson.databind.ObjectMapper;
import lombok.extern.slf4j.Slf4j;
import okhttp3.*;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.stereotype.Component;

import java.io.File;
import java.io.IOException;
import java.nio.file.Files;
import java.util.Base64;
import java.util.HashMap;
import java.util.Map;
import java.util.concurrent.TimeUnit;

@Slf4j
@Component
public class DrgcnnClient {

    private final String baseUrl;
    private final boolean enabled;
    private final OkHttpClient httpClient;
    private final ObjectMapper objectMapper;

    public DrgcnnClient(
            @Value("${huiyan.drgcnn-base-url:http://192.168.2.103:5000}") String baseUrl,
            @Value("${huiyan.drgcnn-enabled:true}") boolean enabled,
            ObjectMapper objectMapper
    ) {
        this.baseUrl = baseUrl.replaceAll("/+$", "");
        this.enabled = enabled;
        this.objectMapper = objectMapper;
        this.httpClient = new OkHttpClient.Builder()
                .connectTimeout(15, TimeUnit.SECONDS)
                .readTimeout(60, TimeUnit.SECONDS)
                .writeTimeout(30, TimeUnit.SECONDS)
                .retryOnConnectionFailure(true)
                .build();
    }

    public JsonNode predictTwoEyes(File leftEyeFile, File rightEyeFile) {
        if (!enabled) {
            return null;
        }
        try {
            Map<String, String> payload = new HashMap<>();
            if (leftEyeFile != null && leftEyeFile.exists()) {
                byte[] bytes = Files.readAllBytes(leftEyeFile.toPath());
                payload.put("left_eye", "data:image/jpeg;base64," + Base64.getEncoder().encodeToString(bytes));
            }
            if (rightEyeFile != null && rightEyeFile.exists()) {
                byte[] bytes = Files.readAllBytes(rightEyeFile.toPath());
                payload.put("right_eye", "data:image/jpeg;base64," + Base64.getEncoder().encodeToString(bytes));
            }

            String json = objectMapper.writeValueAsString(payload);
            RequestBody body = RequestBody.create(json, MediaType.parse("application/json; charset=utf-8"));
            Request request = new Request.Builder()
                    .url(baseUrl + "/predict_twoeyes")
                    .header("Accept", "application/json")
                    .post(body)
                    .build();

            try (Response response = httpClient.newCall(request).execute()) {
                if (response.isSuccessful() && response.body() != null) {
                    return objectMapper.readTree(response.body().string());
                } else {
                    log.warn("DRGCNN 服务响应异常: code={}", response.code());
                    return null;
                }
            }
        } catch (Exception e) {
            log.warn("DRGCNN 调用失败 (自动回退至模拟推理): {}", e.getMessage());
            return null;
        }
    }
}
