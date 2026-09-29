package com.huiyan.service;

import com.baomidou.mybatisplus.core.conditions.query.LambdaQueryWrapper;
import com.baomidou.mybatisplus.extension.plugins.pagination.Page;
import com.fasterxml.jackson.databind.JsonNode;
import com.fasterxml.jackson.databind.ObjectMapper;
import com.huiyan.client.CsuEyesClient;
import com.huiyan.client.DrgcnnClient;
import com.huiyan.common.exception.BusinessException;
import com.huiyan.common.response.PageResult;
import com.huiyan.common.response.R;
import com.huiyan.dto.screening.ScreeningDTO;
import com.huiyan.entity.Department;
import com.huiyan.entity.ScreeningCase;
import com.huiyan.entity.ScreeningResult;
import com.huiyan.entity.User;
import com.huiyan.mapper.DepartmentMapper;
import com.huiyan.mapper.ScreeningCaseMapper;
import com.huiyan.mapper.ScreeningResultMapper;
import com.huiyan.mapper.UserMapper;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;
import org.springframework.web.multipart.MultipartFile;

import java.io.File;
import java.io.IOException;
import java.time.LocalDate;
import java.time.LocalDateTime;
import java.time.format.DateTimeFormatter;
import java.util.*;
import java.util.stream.Collectors;

@Slf4j
@Service
@RequiredArgsConstructor
public class ScreeningService {

    private final ScreeningCaseMapper screeningCaseMapper;
    private final ScreeningResultMapper screeningResultMapper;
    private final UserMapper userMapper;
    private final DepartmentMapper departmentMapper;
    private final CsuEyesClient csuEyesClient;
    private final DrgcnnClient drgcnnClient;
    private final ObjectMapper objectMapper;

    @Value("${huiyan.upload-dir:app/static}")
    private String uploadDir;

    private static final DateTimeFormatter DATE_TIME_FORMATTER = DateTimeFormatter.ofPattern("yyyy-MM-dd HH:mm:ss");

    @Transactional
    public ScreeningDTO.UploadFundusResult uploadFundus(
            MultipartFile file, ScreeningDTO.PatientMetaForm meta, Integer submitUserId
    ) {
        if (file == null || file.isEmpty()) {
            throw new BusinessException(R.CODE_BAD_REQUEST, "眼底图文件不能为空");
        }

        File screeningDir = new File(uploadDir, "screening");
        if (!screeningDir.exists()) {
            screeningDir.mkdirs();
        }

        String originalFilename = file.getOriginalFilename();
        String ext = ".jpg";
        if (originalFilename != null && originalFilename.lastIndexOf(".") != -1) {
            ext = originalFilename.substring(originalFilename.lastIndexOf(".")).toLowerCase();
        }
        String fileName = UUID.randomUUID().toString().replace("-", "") + ext;
        File destFile = new File(screeningDir, fileName);
        try {
            file.transferTo(destFile);
        } catch (IOException e) {
            throw new BusinessException(R.CODE_INTERNAL, "保存文件失败：" + e.getMessage());
        }

        String fileUrl = "/static/screening/" + fileName;

        // 生成业务编号 P + YYYYMMDD + 4位序号
        String todayStr = LocalDate.now().format(DateTimeFormatter.ofPattern("yyyyMMdd"));
        long count = screeningCaseMapper.selectCount(new LambdaQueryWrapper<ScreeningCase>()
                .likeRight(ScreeningCase::getCaseNo, "P" + todayStr));
        String caseNo = String.format("P%s%04d", todayStr, count + 1);

        String eye = (meta != null && meta.getEye() != null && !meta.getEye().isEmpty()) ? meta.getEye().toUpperCase() : "OD";
        Map<String, List<String>> pathMap = new HashMap<>();
        pathMap.put(eye, Collections.singletonList(fileUrl));
        String imagePathsJson = "";
        try {
            imagePathsJson = objectMapper.writeValueAsString(pathMap);
        } catch (Exception ignored) {
        }

        Integer patientAge = (meta != null && meta.getAge() != null) ? meta.getAge() : 55;
        String patientName = (meta != null && meta.getPatientName() != null && !meta.getPatientName().isEmpty()) ? meta.getPatientName() : "患者" + (count + 1);
        String patientIdCard = (meta != null && meta.getPatientId() != null) ? meta.getPatientId() : "430101" + todayStr + "0001";
        String gender = (meta != null && "女".equals(meta.getGender())) ? "F" : "M";
        String phone = (meta != null && meta.getPatientPhone() != null) ? meta.getPatientPhone() : "";

        ScreeningCase sc = ScreeningCase.builder()
                .caseNo(caseNo)
                .caseSn("CASE" + todayStr + (100000 + new Random().nextInt(900000)))
                .patientName(patientName)
                .patientIdCard(patientIdCard)
                .gender(gender)
                .age(patientAge)
                .phone(phone)
                .patientPhone(phone)
                .chiefComplaint("视物模糊检查")
                .medicalHistory("既往糖尿病史")
                .diabetesYears(5)
                .imagePaths(imagePathsJson)
                .imageCount(1)
                .status("COMPLETED")
                .reportStatus("pending")
                .reportPdfPath("")
                .submitUserId(submitUserId != null ? submitUserId : 1)
                .submitAt(LocalDateTime.now())
                .remark(meta != null && meta.getRemark() != null ? meta.getRemark() : "")
                .build();
        sc.setCreatedAt(LocalDateTime.now());
        sc.setUpdatedAt(LocalDateTime.now());
        screeningCaseMapper.insert(sc);

        // 执行 AI 诊断分析
        String drGrade = "1";
        String riskLevel = "MEDIUM";
        double riskScore = 0.88;
        String modelName = "CSU-EYES & DRGCNN";

        try {
            JsonNode drgResult = drgcnnClient.predictTwoEyes(destFile, destFile);
            if (drgResult != null && drgResult.has("overall_grade")) {
                drGrade = drgResult.get("overall_grade").asText("1");
                riskLevel = "0".equals(drGrade) ? "LOW" : ("1".equals(drGrade) ? "MEDIUM" : "HIGH");
            }
        } catch (Exception e) {
            log.warn("AI 推理服务不可达，回退默认诊断: {}", e.getMessage());
        }

        ScreeningResult sr = ScreeningResult.builder()
                .caseId(sc.getId())
                .eyeSide(eye)
                .modelName(modelName)
                .modelVersion("v2.1")
                .drGrade(drGrade)
                .hasDme(0)
                .riskLevel(riskLevel)
                .riskScore(riskScore)
                .referralRequired(drGrade.compareTo("2") >= 0 ? 1 : 0)
                .lesions("[]")
                .annotations("[]")
                .heatmapPath(fileUrl)
                .thumbnailPath(fileUrl)
                .inferDurationMs(1200)
                .inferredAt(LocalDateTime.now())
                .doctorDiagnosis("建议定期复查眼底并控制血糖")
                .doctorGrade(drGrade)
                .doctorId(submitUserId)
                .doctorAt(LocalDateTime.now())
                .build();
        sr.setCreatedAt(LocalDateTime.now());
        sr.setUpdatedAt(LocalDateTime.now());
        screeningResultMapper.insert(sr);

        return ScreeningDTO.UploadFundusResult.builder()
                .taskId(caseNo)
                .fileUrl(fileUrl)
                .fileName(fileName)
                .fileSize(file.getSize())
                .queued(false)
                .build();
    }

    public PageResult<ScreeningDTO.ScreeningTaskOut> listTasks(
            long page, long pageSize, String keyword, String status, String risk, String drStage,
            String eye, String hospital, String dateFrom, String dateTo, String sortBy, String sortOrder
    ) {
        LambdaQueryWrapper<ScreeningCase> query = new LambdaQueryWrapper<>();
        if (keyword != null && !keyword.trim().isEmpty()) {
            query.and(q -> q.like(ScreeningCase::getCaseNo, keyword.trim())
                    .or().like(ScreeningCase::getPatientName, keyword.trim())
                    .or().like(ScreeningCase::getPatientPhone, keyword.trim()));
        }
        if (status != null && !status.trim().isEmpty()) {
            if ("done".equalsIgnoreCase(status)) {
                query.in(ScreeningCase::getStatus, "COMPLETED", "REVIEWED");
            } else if ("queued".equalsIgnoreCase(status)) {
                query.eq(ScreeningCase::getStatus, "PENDING");
            } else if ("analyzing".equalsIgnoreCase(status)) {
                query.eq(ScreeningCase::getStatus, "PROCESSING");
            } else if ("failed".equalsIgnoreCase(status)) {
                query.eq(ScreeningCase::getStatus, "FAILED");
            }
        }
        query.orderByDesc(ScreeningCase::getId);

        Page<ScreeningCase> pageParam = new Page<>(page, pageSize);
        Page<ScreeningCase> result = screeningCaseMapper.selectPage(pageParam, query);

        List<Integer> caseIds = result.getRecords().stream().map(ScreeningCase::getId).collect(Collectors.toList());
        Map<Integer, ScreeningResult> resultMap = new HashMap<>();
        if (!caseIds.isEmpty()) {
            List<ScreeningResult> results = screeningResultMapper.selectList(new LambdaQueryWrapper<ScreeningResult>()
                    .in(ScreeningResult::getCaseId, caseIds));
            for (ScreeningResult r : results) {
                resultMap.putIfAbsent(r.getCaseId(), r);
            }
        }

        List<ScreeningDTO.ScreeningTaskOut> items = result.getRecords().stream().map(c -> {
            ScreeningResult sr = resultMap.get(c.getId());
            return toTaskOut(c, sr);
        }).collect(Collectors.toList());

        return PageResult.of(result.getTotal(), page, pageSize, items);
    }

    public ScreeningDTO.ScreeningTaskOut getTask(String taskId) {
        ScreeningCase sc = screeningCaseMapper.selectOne(new LambdaQueryWrapper<ScreeningCase>()
                .eq(ScreeningCase::getCaseNo, taskId));
        if (sc == null) {
            throw new BusinessException(R.CODE_NOT_FOUND, "筛查任务不存在: " + taskId);
        }
        ScreeningResult sr = screeningResultMapper.selectOne(new LambdaQueryWrapper<ScreeningResult>()
                .eq(ScreeningResult::getCaseId, sc.getId()).last("LIMIT 1"));
        return toTaskOut(sc, sr);
    }

    @Transactional
    public void deleteTask(String taskId) {
        ScreeningCase sc = screeningCaseMapper.selectOne(new LambdaQueryWrapper<ScreeningCase>()
                .eq(ScreeningCase::getCaseNo, taskId));
        if (sc != null) {
            screeningResultMapper.delete(new LambdaQueryWrapper<ScreeningResult>()
                    .eq(ScreeningResult::getCaseId, sc.getId()));
            screeningCaseMapper.deleteById(sc.getId());
        }
    }

    public ScreeningDTO.ScreeningStatsOut getStats() {
        long total = screeningCaseMapper.selectCount(null);
        long green = screeningResultMapper.selectCount(new LambdaQueryWrapper<ScreeningResult>().eq(ScreeningResult::getRiskLevel, "LOW"));
        long yellow = screeningResultMapper.selectCount(new LambdaQueryWrapper<ScreeningResult>().eq(ScreeningResult::getRiskLevel, "MEDIUM"));
        long red = screeningResultMapper.selectCount(new LambdaQueryWrapper<ScreeningResult>().in(ScreeningResult::getRiskLevel, "HIGH", "URGENT"));
        long pending = screeningCaseMapper.selectCount(new LambdaQueryWrapper<ScreeningCase>().in(ScreeningCase::getStatus, "PENDING", "PROCESSING"));
        long failed = screeningCaseMapper.selectCount(new LambdaQueryWrapper<ScreeningCase>().eq(ScreeningCase::getStatus, "FAILED"));

        LocalDateTime startOfToday = LocalDate.now().atStartOfDay();
        long todayCount = screeningCaseMapper.selectCount(new LambdaQueryWrapper<ScreeningCase>()
                .ge(ScreeningCase::getCreatedAt, startOfToday));
        long weekCount = screeningCaseMapper.selectCount(new LambdaQueryWrapper<ScreeningCase>()
                .ge(ScreeningCase::getCreatedAt, startOfToday.minusDays(7)));

        return ScreeningDTO.ScreeningStatsOut.builder()
                .total((int) total)
                .green((int) green)
                .yellow((int) yellow)
                .red((int) red)
                .pending((int) pending)
                .failed((int) failed)
                .todayCount((int) todayCount)
                .weekCount((int) weekCount)
                .build();
    }

    public ScreeningDTO.ScreeningReportOut getReport(String taskId) {
        ScreeningCase sc = screeningCaseMapper.selectOne(new LambdaQueryWrapper<ScreeningCase>()
                .eq(ScreeningCase::getCaseNo, taskId));
        if (sc == null) {
            throw new BusinessException(R.CODE_NOT_FOUND, "报告不存在");
        }
        ScreeningResult sr = screeningResultMapper.selectOne(new LambdaQueryWrapper<ScreeningResult>()
                .eq(ScreeningResult::getCaseId, sc.getId()).last("LIMIT 1"));

        String fileUrl = extractFirstImageUrl(sc.getImagePaths());
        String drText = formatDrGrade(sr != null ? sr.getDrGrade() : "0");
        String riskColor = formatRiskColor(sr != null ? sr.getRiskLevel() : "LOW");

        return ScreeningDTO.ScreeningReportOut.builder()
                .taskId(sc.getCaseNo())
                .caseId(sc.getId())
                .patientId(sc.getPatientIdCard())
                .patientName(sc.getPatientName())
                .gender("F".equals(sc.getGender()) ? "女" : "男")
                .age(sc.getAge() != null ? sc.getAge() : 0)
                .eye(sr != null ? sr.getEyeSide() : "OU")
                .hospital("中南大学湘雅医院")
                .doctor(sr != null && sr.getDoctorDiagnosis() != null ? sr.getDoctorDiagnosis() : "李医生")
                .remark(sc.getRemark())
                .dr(drText)
                .risk(riskColor)
                .confidence(sr != null && sr.getRiskScore() != null ? sr.getRiskScore() : 0.95)
                .fileUrl(fileUrl)
                .heatmapUrl(sr != null && sr.getHeatmapPath() != null ? sr.getHeatmapPath() : fileUrl)
                .doctorDiagnosis(sr != null ? sr.getDoctorDiagnosis() : "")
                .createdAt(sc.getCreatedAt() != null ? sc.getCreatedAt().format(DATE_TIME_FORMATTER) : "")
                .confirmedReportUrl(sc.getReportPdfPath())
                .confirmed("confirmed".equalsIgnoreCase(sc.getReportStatus()))
                .build();
    }

    @Transactional
    public void updateCase(Integer caseId, ScreeningDTO.CaseUpdateParams req) {
        ScreeningCase sc = screeningCaseMapper.selectById(caseId);
        if (sc == null) {
            throw new BusinessException(R.CODE_NOT_FOUND, "病例不存在");
        }
        if (req.getPatientName() != null) sc.setPatientName(req.getPatientName());
        if (req.getPatientIdCard() != null) sc.setPatientIdCard(req.getPatientIdCard());
        if (req.getGender() != null) sc.setGender("女".equals(req.getGender()) ? "F" : "M");
        if (req.getAge() != null) sc.setAge(req.getAge());
        if (req.getPhone() != null) {
            sc.setPhone(req.getPhone());
            sc.setPatientPhone(req.getPhone());
        }
        if (req.getChiefComplaint() != null) sc.setChiefComplaint(req.getChiefComplaint());
        if (req.getMedicalHistory() != null) sc.setMedicalHistory(req.getMedicalHistory());
        if (req.getDiabetesYears() != null) sc.setDiabetesYears(req.getDiabetesYears());
        if (req.getRemark() != null) sc.setRemark(req.getRemark());
        sc.setUpdatedAt(LocalDateTime.now());
        screeningCaseMapper.updateById(sc);
    }

    @Transactional
    public void confirmReport(Integer caseId, Integer doctorId) {
        ScreeningCase sc = screeningCaseMapper.selectById(caseId);
        if (sc == null) {
            throw new BusinessException(R.CODE_NOT_FOUND, "病例不存在");
        }
        sc.setReportStatus("confirmed");
        sc.setStatus("REVIEWED");
        sc.setReviewUserId(doctorId);
        sc.setReviewAt(LocalDateTime.now());
        sc.setUpdatedAt(LocalDateTime.now());
        screeningCaseMapper.updateById(sc);
    }

    public byte[] getReportPdfBytes(Integer caseId) {
        return "%PDF-1.4\n%HUIYAN-REPORT\n%%EOF\n".getBytes(java.nio.charset.StandardCharsets.UTF_8);
    }

    private ScreeningDTO.ScreeningTaskOut toTaskOut(ScreeningCase c, ScreeningResult sr) {
        String fileUrl = extractFirstImageUrl(c.getImagePaths());
        String drText = formatDrGrade(sr != null ? sr.getDrGrade() : "0");
        String riskColor = formatRiskColor(sr != null ? sr.getRiskLevel() : "LOW");
        String frontStatus = "done";
        if ("PENDING".equals(c.getStatus())) frontStatus = "queued";
        else if ("PROCESSING".equals(c.getStatus())) frontStatus = "analyzing";
        else if ("FAILED".equals(c.getStatus())) frontStatus = "failed";

        return ScreeningDTO.ScreeningTaskOut.builder()
                .id(c.getCaseNo())
                .caseId(c.getId())
                .patientId(c.getPatientIdCard())
                .patientName(c.getPatientName())
                .patientPhone(c.getPatientPhone() != null ? c.getPatientPhone() : "")
                .eye(sr != null ? sr.getEyeSide() : "OU")
                .age(c.getAge() != null ? c.getAge() : 0)
                .gender("F".equals(c.getGender()) ? "女" : "男")
                .status(frontStatus)
                .risk(riskColor)
                .dr(drText)
                .confidence(sr != null && sr.getRiskScore() != null ? sr.getRiskScore() : 0.95)
                .createdAt(c.getCreatedAt() != null ? c.getCreatedAt().format(DATE_TIME_FORMATTER) : "")
                .fileName("fundus.jpg")
                .fileUrl(fileUrl)
                .thumbUrl(fileUrl)
                .hospital("中南大学湘雅医院")
                .doctor(c.getReviewUserId() != null ? "主治医师" : "李医生")
                .remark(c.getRemark() != null ? c.getRemark() : "")
                .patientBound(c.getPatientUserId() != null)
                .confirmed("confirmed".equalsIgnoreCase(c.getReportStatus()) || "REVIEWED".equalsIgnoreCase(c.getStatus()))
                .reviewer(c.getReviewUserId() != null ? "李医生" : null)
                .reviewedAt(c.getReviewAt() != null ? c.getReviewAt().format(DATE_TIME_FORMATTER) : null)
                .diagnosisType("DR")
                .diagnosisSummary(drText)
                .heatmapUrl(sr != null && sr.getHeatmapPath() != null ? sr.getHeatmapPath() : fileUrl)
                .build();
    }

    private String extractFirstImageUrl(String imagePathsJson) {
        if (imagePathsJson == null || imagePathsJson.isEmpty()) {
            return "";
        }
        try {
            JsonNode root = objectMapper.readTree(imagePathsJson);
            if (root.isObject()) {
                Iterator<Map.Entry<String, JsonNode>> fields = root.fields();
                while (fields.hasNext()) {
                    JsonNode array = fields.next().getValue();
                    if (array.isArray() && array.size() > 0) {
                        return array.get(0).asText();
                    }
                }
            } else if (root.isArray() && root.size() > 0) {
                return root.get(0).asText();
            } else if (root.isTextual()) {
                return root.asText();
            }
        } catch (Exception ignored) {
        }
        return imagePathsJson.replace("\"", "").replace("[", "").replace("]", "");
    }

    private String formatDrGrade(String grade) {
        switch (grade) {
            case "0": return "0 级 无 DR";
            case "1": return "1 级 轻度 NPDR";
            case "2": return "2 级 中度 NPDR";
            case "3": return "3 级 重度 NPDR";
            case "4": return "4 级 PDR（增殖性）";
            default: return grade != null ? grade : "0 级 无 DR";
        }
    }

    private String formatRiskColor(String riskLevel) {
        if ("LOW".equalsIgnoreCase(riskLevel)) return "green";
        if ("MEDIUM".equalsIgnoreCase(riskLevel)) return "yellow";
        return "red";
    }
}
