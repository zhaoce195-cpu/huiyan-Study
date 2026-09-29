package com.huiyan.common.util;

import java.util.*;

public class DiagnosisFormHelper {

    public static final String UNGRADABLE_VALUE = "ungradable";

    public static Map<String, Object> getForm(String category) {
        String cat = (category != null && !category.trim().isEmpty()) ? category.trim().toUpperCase() : "DR";
        List<Map<String, Object>> fields = new ArrayList<>();

        // 1. 影像可判读性 (quality)
        Map<String, Object> quality = new LinkedHashMap<>();
        quality.put("key", "readability");
        quality.put("label", "影像可判读性");
        quality.put("type", "radio");
        quality.put("required", true);
        quality.put("order", 1);
        quality.put("options", List.of(
                Map.of("value", "readable", "label", "可判读"),
                Map.of("value", "partially", "label", "部分可判读"),
                Map.of("value", "ungradable", "label", "不可判读")
        ));
        quality.put("hint", "先判断可判读性再下结论；不可判读时应重拍或转诊，不得给出阴性结论");
        fields.add(quality);

        boolean categoryKnown = false;
        List<String> skipWhenUngradable = new ArrayList<>();

        if ("DR".equals(cat) || "DIABETIC_RETINOPATHY".equals(cat)) {
            categoryKnown = true;
            cat = "DR";

            Map<String, Object> drGrade = new LinkedHashMap<>();
            drGrade.put("key", "dr_grade");
            drGrade.put("label", "DR 分级");
            drGrade.put("type", "select");
            drGrade.put("required", true);
            drGrade.put("order", 20);
            drGrade.put("hint", "这里只判断视网膜病变的级别。黄斑水肿另填，不要用级别高低代替。");
            drGrade.put("options", List.of(
                    Map.of("value", "0", "label", "0 级 无 DR"),
                    Map.of("value", "1", "label", "1 级 轻度 NPDR"),
                    Map.of("value", "2", "label", "2 级 中度 NPDR"),
                    Map.of("value", "3", "label", "3 级 重度 NPDR"),
                    Map.of("value", "4", "label", "4 级 PDR（增殖性）"),
                    Map.of("value", "NA", "label", "不适用")
            ));
            fields.add(drGrade);
            skipWhenUngradable.add("dr_grade");

            Map<String, Object> findings = new LinkedHashMap<>();
            findings.put("key", "findings");
            findings.put("label", "关键征象");
            findings.put("type", "checkbox");
            findings.put("required", false);
            findings.put("order", 30);
            findings.put("options", List.of(
                    Map.of("value", "MA", "label", "微动脉瘤"),
                    Map.of("value", "HE", "label", "视网膜出血"),
                    Map.of("value", "EX", "label", "硬性渗出"),
                    Map.of("value", "SE", "label", "软性渗出（棉绒斑）"),
                    Map.of("value", "IRMA", "label", "视网膜内微血管异常"),
                    Map.of("value", "VB", "label", "静脉串珠样改变"),
                    Map.of("value", "NV", "label", "新生血管")
            ));
            fields.add(findings);
            skipWhenUngradable.add("findings");

            Map<String, Object> dme = new LinkedHashMap<>();
            dme.put("key", "dme");
            dme.put("label", "黄斑水肿（与 DR 分级分开）");
            dme.put("type", "radio");
            dme.put("required", false);
            dme.put("order", 45);
            dme.put("hint", "黄斑水肿和 DR 分级分开判断。这例只有普通眼底照，不能诊断中心受累黄斑水肿。");
            dme.put("options", List.of(
                    Map.of("value", "not_from_photo", "label", "这张眼底照不能判断黄斑水肿"),
                    Map.of("value", "no_exudate_clue", "label", "黄斑区未见硬性渗出，仍不能排除黄斑水肿"),
                    Map.of("value", "suspect_needs_oct", "label", "黄斑附近有硬性渗出，可疑黄斑水肿；是否中心受累要看 OCT 和视力")
            ));
            fields.add(dme);
            skipWhenUngradable.add("dme");

        } else if ("GLAUCOMA".equals(cat)) {
            categoryKnown = true;
            Map<String, Object> cdr = new LinkedHashMap<>();
            cdr.put("key", "cdr");
            cdr.put("label", "杯盘比（C/D）");
            cdr.put("type", "select");
            cdr.put("required", true);
            cdr.put("order", 20);
            cdr.put("options", List.of(
                    Map.of("value", "<0.4", "label", "<0.4"),
                    Map.of("value", "0.4-0.5", "label", "0.4-0.5"),
                    Map.of("value", "0.5-0.6", "label", "0.5-0.6"),
                    Map.of("value", "0.6-0.7", "label", "0.6-0.7"),
                    Map.of("value", "0.7-0.8", "label", "0.7-0.8"),
                    Map.of("value", ">0.8", "label", ">0.8")
            ));
            fields.add(cdr);
            skipWhenUngradable.add("cdr");

            Map<String, Object> gFindings = new LinkedHashMap<>();
            gFindings.put("key", "glaucoma_findings");
            gFindings.put("label", "关键征象");
            gFindings.put("type", "checkbox");
            gFindings.put("required", false);
            gFindings.put("order", 30);
            gFindings.put("options", List.of(
                    Map.of("value", "rim_notch", "label", "盘沿切迹"),
                    Map.of("value", "rnfl_defect", "label", "视网膜神经纤维层缺损"),
                    Map.of("value", "disc_hemorrhage", "label", "视盘出血"),
                    Map.of("value", "peripapillary_atrophy", "label", "视盘周围萎缩")
            ));
            fields.add(gFindings);
            skipWhenUngradable.add("glaucoma_findings");

            Map<String, Object> risk = new LinkedHashMap<>();
            risk.put("key", "glaucoma_risk");
            risk.put("label", "青光眼风险");
            risk.put("type", "radio");
            risk.put("required", true);
            risk.put("order", 40);
            risk.put("hint", "眼底照仅能提示风险，确诊需结合眼压、视野与 OCT");
            risk.put("options", List.of(
                    Map.of("value", "low", "label", "低"),
                    Map.of("value", "suspect", "label", "可疑"),
                    Map.of("value", "high", "label", "高")
            ));
            fields.add(risk);
            skipWhenUngradable.add("glaucoma_risk");

        } else if ("AMD".equals(cat)) {
            categoryKnown = true;
            Map<String, Object> amdType = new LinkedHashMap<>();
            amdType.put("key", "amd_type");
            amdType.put("label", "AMD 类型");
            amdType.put("type", "radio");
            amdType.put("required", true);
            amdType.put("order", 20);
            amdType.put("options", List.of(
                    Map.of("value", "none", "label", "无"),
                    Map.of("value", "dry", "label", "干性（萎缩型）"),
                    Map.of("value", "wet", "label", "湿性（渗出型）")
            ));
            fields.add(amdType);
            skipWhenUngradable.add("amd_type");

            Map<String, Object> amdFindings = new LinkedHashMap<>();
            amdFindings.put("key", "amd_findings");
            amdFindings.put("label", "关键征象");
            amdFindings.put("type", "checkbox");
            amdFindings.put("required", false);
            amdFindings.put("order", 30);
            amdFindings.put("options", List.of(
                    Map.of("value", "drusen", "label", "玻璃膜疣"),
                    Map.of("value", "pigment", "label", "色素紊乱"),
                    Map.of("value", "ga", "label", "地图状萎缩"),
                    Map.of("value", "cnv", "label", "脉络膜新生血管")
            ));
            fields.add(amdFindings);
            skipWhenUngradable.add("amd_findings");

        } else {
            Map<String, Object> impression = new LinkedHashMap<>();
            impression.put("key", "impression");
            impression.put("label", "主要结论");
            impression.put("type", "text");
            impression.put("required", true);
            impression.put("order", 20);
            impression.put("placeholder", "用一句话概括主要发现");
            fields.add(impression);
            skipWhenUngradable.add("impression");
        }

        // 置信度
        Map<String, Object> confidence = new LinkedHashMap<>();
        confidence.put("key", "confidence");
        confidence.put("label", "结论置信度");
        confidence.put("type", "radio");
        confidence.put("required", true);
        confidence.put("order", 90);
        confidence.put("options", List.of(
                Map.of("value", "high", "label", "高"),
                Map.of("value", "medium", "label", "中"),
                Map.of("value", "low", "label", "低")
        ));
        confidence.put("hint", "置信度低的结论应进入教师复核队列");
        fields.add(confidence);
        skipWhenUngradable.add("confidence");

        // 处置建议
        Map<String, Object> disposition = new LinkedHashMap<>();
        disposition.put("key", "disposition");
        disposition.put("label", "处置建议");
        disposition.put("type", "select");
        disposition.put("required", true);
        disposition.put("order", 95);
        disposition.put("options", List.of(
                Map.of("value", "routine", "label", "常规随访"),
                Map.of("value", "followup_3m", "label", "3 个月内复查"),
                Map.of("value", "followup_6m", "label", "6 个月内复查"),
                Map.of("value", "followup_12m", "label", "12 个月复查"),
                Map.of("value", "refer", "label", "转诊眼科"),
                Map.of("value", "refer_urgent", "label", "紧急转诊"),
                Map.of("value", "retake", "label", "重新拍摄")
        ));
        fields.add(disposition);

        // 补充说明
        Map<String, Object> note = new LinkedHashMap<>();
        note.put("key", "note");
        note.put("label", "补充说明");
        note.put("type", "textarea");
        note.put("required", false);
        note.put("order", 99);
        note.put("placeholder", "结构化字段之外需要补充的内容");
        note.put("hint", "自由文本仅作补充，不替代上面的结构化结论");
        fields.add(note);

        fields.sort(Comparator.comparingInt(f -> (Integer) f.get("order")));

        Map<String, Object> result = new LinkedHashMap<>();
        result.put("category", cat.isEmpty() ? "OTHER" : cat);
        result.put("categoryKnown", categoryKnown);
        result.put("ungradableValue", UNGRADABLE_VALUE);
        result.put("skipWhenUngradable", skipWhenUngradable);
        result.put("fields", fields);
        return result;
    }
}
