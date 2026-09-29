package com.huiyan.client;

import com.fasterxml.jackson.databind.JsonNode;
import com.fasterxml.jackson.databind.ObjectMapper;
import lombok.extern.slf4j.Slf4j;
import okhttp3.*;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.stereotype.Component;

import java.io.File;
import java.io.IOException;
import java.util.concurrent.TimeUnit;

@Slf4j
@Component
public class CsuEyesClient {

    private final String baseUrl;
    private final OkHttpClient httpClient;
    private final ObjectMapper objectMapper;

    public CsuEyesClient(
            @Value("${huiyan.csu-eyes-base-url:http://192.168.2.103:5000}") String baseUrl,
            ObjectMapper objectMapper
    ) {
        this.baseUrl = baseUrl.replaceAll("/+$", "");
        this.objectMapper = objectMapper;
        this.httpClient = new OkHttpClient.Builder()
                .connectTimeout(15, TimeUnit.SECONDS)
                .readTimeout(45, TimeUnit.SECONDS)
                .writeTimeout(30, TimeUnit.SECONDS)
                .retryOnConnectionFailure(true)
                .build();
    }

    /**
     * 微血管瘤(MA)检测
     */
    public JsonNode detectMa(File imageFile) {
        String url = baseUrl + "/api/v1/inference/ma-detection";
        RequestBody fileBody = RequestBody.create(imageFile, MediaType.parse("image/jpeg"));
        RequestBody requestBody = new MultipartBody.Builder()
                .setType(MultipartBody.FORM)
                .addFormDataPart("image", imageFile.getName(), fileBody)
                .build();

        Request request = new Request.Builder()
                .url(url)
                .header("Accept", "application/json")
                .header("User-Agent", "huiyan-cloud/1.0 (csu-eyes-client)")
                .post(requestBody)
                .build();

        return executeRequest(request);
    }

    /**
     * DR 分级
     */
    public JsonNode gradeDr(File leftEyeFile, File rightEyeFile) {
        String url = baseUrl + "/api/v1/inference/dr-grading";
        MultipartBody.Builder builder = new MultipartBody.Builder().setType(MultipartBody.FORM);
        if (leftEyeFile != null && leftEyeFile.exists()) {
            builder.addFormDataPart("left_eye", leftEyeFile.getName(),
                    RequestBody.create(leftEyeFile, MediaType.parse("image/jpeg")));
        }
        if (rightEyeFile != null && rightEyeFile.exists()) {
            builder.addFormDataPart("right_eye", rightEyeFile.getName(),
                    RequestBody.create(rightEyeFile, MediaType.parse("image/jpeg")));
        }

        Request request = new Request.Builder()
                .url(url)
                .header("Accept", "application/json")
                .header("User-Agent", "huiyan-cloud/1.0 (csu-eyes-client)")
                .post(builder.build())
                .build();

        return executeRequest(request);
    }

    private JsonNode executeRequest(Request request) {
        try (Response response = httpClient.newCall(request).execute()) {
            if (!response.isSuccessful()) {
                String errorBody = response.body() != null ? response.body().string() : "";
                log.warn("CSU-EYES 请求返回非200状态: code={}, body={}", response.code(), errorBody);
                return null;
            }
            if (response.body() == null) {
                return null;
            }
            return objectMapper.readTree(response.body().string());
        } catch (IOException e) {
            log.warn("CSU-EYES 连接失败 (将由业务降级处理): {}", e.getMessage());
            return null;
        }
    }
}
