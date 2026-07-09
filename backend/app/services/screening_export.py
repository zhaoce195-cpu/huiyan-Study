"""
筛查报告导出
- 单份 PDF（reportlab）
- 汇总 PDF（按筛选条件多任务合并）
- 列表 Excel（openpyxl）

注：reportlab 默认不带中文字体，使用 Windows / Linux 常见 SimHei 字体注册。
若运行环境无该字体，会自动回退到 Helvetica（英文 + 数字仍可读）。
"""

import io
import os
from datetime import datetime
from typing import List, Optional

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import (
    Image as RLImage,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)

from openpyxl import Workbook
from openpyxl.styles import Alignment, Font, PatternFill

from app.common.utils import resolve_screening_file
from app.schemas.screening import ScreeningReportOut, ScreeningTaskOut


# ============================================================
#                    字体注册
# ============================================================

_CN_FONT_NAME = "Helvetica"  # 默认回退
_FONT_REGISTERED = False


def _register_cn_font() -> str:
    """注册中文字体（懒加载，仅首次调用时尝试）"""
    global _CN_FONT_NAME, _FONT_REGISTERED
    if _FONT_REGISTERED:
        return _CN_FONT_NAME

    candidates = [
        # Windows
        r"C:\Windows\Fonts\msyh.ttc",
        r"C:\Windows\Fonts\msyh.ttf",
        r"C:\Windows\Fonts\simhei.ttf",
        r"C:\Windows\Fonts\simsun.ttc",
        # macOS
        "/System/Library/Fonts/STHeiti Medium.ttc",
        # Linux
        "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc",
        "/usr/share/fonts/truetype/wqy/wqy-microhei.ttc",
    ]
    for fp in candidates:
        if os.path.exists(fp):
            try:
                pdfmetrics.registerFont(TTFont("CNFont", fp))
                _CN_FONT_NAME = "CNFont"
                _FONT_REGISTERED = True
                return _CN_FONT_NAME
            except Exception:
                continue
    _FONT_REGISTERED = True  # 标记尝试过，避免反复扫盘
    return _CN_FONT_NAME


# ============================================================
#                    PDF 样式
# ============================================================

def _resolve_image_for_pdf(url: Optional[str]) -> Optional[str]:
    """
    把报告里的影像 URL 解析成 reportlab 能直接吃的本地文件路径。
    - /static/screening/xxx.webp → 落到磁盘 → 返回绝对路径
    - http(s)://... → reportlab 可直接传 URL（PIL 会下载），返回原值
    - 其它 / 解析失败 → None（调用方会跳过图片块）
    """
    if not url:
        return None
    s = str(url).strip()
    if s.startswith("http://") or s.startswith("https://"):
        return s
    p = resolve_screening_file(s)
    return str(p) if p else None


def _safe_image_flowable(
    src: str,
    *,
    max_width_mm: float = 130,
    max_height_mm: float = 90,
):
    """
    构造一个尺寸受限的 reportlab Image flowable。
    任何解析 / 解码 / IO 异常都吞掉，返回 None，让 PDF 继续生成。
    """
    try:
        img = RLImage(src)
        # 原始尺寸（reportlab 单位是 1/72 英寸 = 1 point）
        iw = float(img.imageWidth) or 1.0
        ih = float(img.imageHeight) or 1.0
        max_w = max_width_mm * mm
        max_h = max_height_mm * mm
        ratio = min(max_w / iw, max_h / ih, 1.0)
        img.drawWidth = iw * ratio
        img.drawHeight = ih * ratio
        img.hAlign = "CENTER"
        return img
    except Exception:
        return None


def _styles():
    font = _register_cn_font()
    base = getSampleStyleSheet()
    title = ParagraphStyle(
        "ZhTitle",
        parent=base["Title"],
        fontName=font,
        fontSize=20,
        alignment=1,
        spaceAfter=12,
    )
    h2 = ParagraphStyle(
        "ZhH2",
        parent=base["Heading2"],
        fontName=font,
        fontSize=12,
        spaceBefore=10,
        spaceAfter=6,
        textColor=colors.HexColor("#1f6feb"),
    )
    body = ParagraphStyle(
        "ZhBody",
        parent=base["BodyText"],
        fontName=font,
        fontSize=10,
        leading=16,
    )
    return font, title, h2, body


# ============================================================
#                    单份 PDF
# ============================================================

def render_single_report_pdf(report: ScreeningReportOut) -> bytes:
    font, title_style, h2_style, body_style = _styles()
    buf = io.BytesIO()
    doc = SimpleDocTemplate(
        buf, pagesize=A4,
        leftMargin=20 * mm, rightMargin=20 * mm,
        topMargin=20 * mm, bottomMargin=20 * mm,
        title=f"筛查报告 {report.task_id}",
    )
    story = []

    story.append(Paragraph("慧眼医疗云 · AI 眼底筛查报告", title_style))
    story.append(Paragraph(f"报告编号：{report.report_no}", body_style))
    story.append(Spacer(1, 6 * mm))

    # ---- 患者信息表 ----
    story.append(Paragraph("患者信息", h2_style))
    info_data = [
        ["患者ID", report.patient_id, "姓名", report.patient_name],
        ["性别", report.gender, "年龄", str(report.age)],
        ["眼别", report.eye, "送检医院", report.hospital or "—"],
        ["送检医师", report.doctor or "—", "检查时间", report.exam_time],
    ]
    info_table = Table(info_data, colWidths=[28 * mm, 50 * mm, 28 * mm, 50 * mm])
    info_table.setStyle(TableStyle([
        ("FONTNAME", (0, 0), (-1, -1), font),
        ("FONTSIZE", (0, 0), (-1, -1), 10),
        ("BACKGROUND", (0, 0), (0, -1), colors.HexColor("#f5f7fa")),
        ("BACKGROUND", (2, 0), (2, -1), colors.HexColor("#f5f7fa")),
        ("BOX", (0, 0), (-1, -1), 0.5, colors.HexColor("#dcdfe6")),
        ("INNERGRID", (0, 0), (-1, -1), 0.25, colors.HexColor("#dcdfe6")),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("LEFTPADDING", (0, 0), (-1, -1), 6),
        ("RIGHTPADDING", (0, 0), (-1, -1), 6),
        ("TOPPADDING", (0, 0), (-1, -1), 4),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
    ]))
    story.append(info_table)
    story.append(Spacer(1, 4 * mm))

    # ---- 眼底图（居中嵌入） ----
    origin_src = _resolve_image_for_pdf(getattr(report.image_urls, "origin", None))
    heatmap_src = _resolve_image_for_pdf(getattr(report.image_urls, "heatmap", None))
    has_any_image = False
    if origin_src or heatmap_src:
        story.append(Paragraph("眼底图像", h2_style))
    if origin_src:
        flowable = _safe_image_flowable(origin_src)
        if flowable is not None:
            story.append(flowable)
            story.append(Paragraph(
                "<font color='#909399' size='8'>原始眼底图</font>",
                body_style,
            ))
            story.append(Spacer(1, 3 * mm))
            has_any_image = True
    if heatmap_src and heatmap_src != origin_src:
        flowable = _safe_image_flowable(heatmap_src)
        if flowable is not None:
            story.append(flowable)
            story.append(Paragraph(
                "<font color='#909399' size='8'>AI 标注 / 热力图</font>",
                body_style,
            ))
            has_any_image = True
    if has_any_image:
        story.append(Spacer(1, 4 * mm))

    # ---- AI 分析结果 ----
    story.append(Paragraph("AI 分析结果", h2_style))
    risk_text = {"red": "🔴 高风险", "yellow": "🟡 中风险", "green": "🟢 低风险"}.get(report.risk, report.risk)
    risk_data = [
        ["风险等级", risk_text, "DR 分级", report.dr],
        ["AI 置信度", f"{report.confidence:.2%}", "报告生成时间", report.report_time],
    ]
    risk_table = Table(risk_data, colWidths=[28 * mm, 50 * mm, 28 * mm, 50 * mm])
    risk_table.setStyle(TableStyle([
        ("FONTNAME", (0, 0), (-1, -1), font),
        ("FONTSIZE", (0, 0), (-1, -1), 10),
        ("BACKGROUND", (0, 0), (0, -1), colors.HexColor("#f5f7fa")),
        ("BACKGROUND", (2, 0), (2, -1), colors.HexColor("#f5f7fa")),
        ("BOX", (0, 0), (-1, -1), 0.5, colors.HexColor("#dcdfe6")),
        ("INNERGRID", (0, 0), (-1, -1), 0.25, colors.HexColor("#dcdfe6")),
    ]))
    story.append(risk_table)
    story.append(Spacer(1, 4 * mm))

    # ---- 病灶检出 ----
    if report.lesions:
        story.append(Paragraph("病灶检出", h2_style))
        rows = [["病灶类型", "数量", "位置"]]
        for it in report.lesions:
            rows.append([it.type, str(it.count), it.location or "—"])
        ltable = Table(rows, colWidths=[50 * mm, 30 * mm, 80 * mm])
        ltable.setStyle(TableStyle([
            ("FONTNAME", (0, 0), (-1, -1), font),
            ("FONTSIZE", (0, 0), (-1, -1), 10),
            ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#1f6feb")),
            ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
            ("ALIGN", (1, 1), (1, -1), "CENTER"),
            ("BOX", (0, 0), (-1, -1), 0.5, colors.HexColor("#dcdfe6")),
            ("INNERGRID", (0, 0), (-1, -1), 0.25, colors.HexColor("#dcdfe6")),
        ]))
        story.append(ltable)
        story.append(Spacer(1, 4 * mm))

    # ---- 诊断意见 / 建议 ----
    story.append(Paragraph("诊断意见", h2_style))
    story.append(Paragraph(report.conclusion or "—", body_style))

    story.append(Paragraph("建议处置", h2_style))
    story.append(Paragraph(report.suggestion or "—", body_style))

    if report.reviewer:
        story.append(Spacer(1, 4 * mm))
        story.append(Paragraph(
            f"审核医师：{report.reviewer}　审核时间：{report.reviewed_at or '—'}",
            body_style,
        ))

    # ---- 页脚说明 ----
    story.append(Spacer(1, 8 * mm))
    story.append(Paragraph(
        "<font color='#909399' size='8'>本报告由慧眼医疗云 AI 系统自动生成，"
        "结果仅供临床医师参考，不能作为最终诊断依据。</font>",
        body_style,
    ))

    doc.build(story)
    return buf.getvalue()


# ============================================================
#                    汇总 PDF
# ============================================================

def render_summary_pdf(tasks: List[ScreeningTaskOut]) -> bytes:
    font, title_style, h2_style, body_style = _styles()
    buf = io.BytesIO()
    doc = SimpleDocTemplate(
        buf, pagesize=A4,
        leftMargin=15 * mm, rightMargin=15 * mm,
        topMargin=15 * mm, bottomMargin=15 * mm,
        title="筛查任务汇总",
    )
    story = []
    story.append(Paragraph("慧眼医疗云 · 筛查任务汇总", title_style))
    story.append(Paragraph(
        f"导出时间：{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}　"
        f"共 {len(tasks)} 条记录",
        body_style,
    ))
    story.append(Spacer(1, 4 * mm))

    rows = [["序号", "任务ID", "患者", "眼别", "状态", "风险", "DR", "置信度", "提交时间"]]
    for i, t in enumerate(tasks, start=1):
        rows.append([
            str(i),
            t.id,
            f"{t.patient_name}({t.patient_id})",
            t.eye,
            t.status,
            (t.risk or "—"),
            t.dr or "—",
            f"{t.confidence:.0%}" if t.confidence else "—",
            t.created_at,
        ])
    table = Table(rows, repeatRows=1)
    table.setStyle(TableStyle([
        ("FONTNAME", (0, 0), (-1, -1), font),
        ("FONTSIZE", (0, 0), (-1, -1), 8.5),
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#1f6feb")),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("ALIGN", (0, 0), (-1, -1), "CENTER"),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("BOX", (0, 0), (-1, -1), 0.4, colors.HexColor("#dcdfe6")),
        ("INNERGRID", (0, 0), (-1, -1), 0.2, colors.HexColor("#dcdfe6")),
    ]))
    story.append(table)
    doc.build(story)
    return buf.getvalue()


# ============================================================
#                    Excel 列表
# ============================================================

def render_tasks_excel(tasks: List[ScreeningTaskOut]) -> bytes:
    wb = Workbook()
    ws = wb.active
    ws.title = "筛查任务"

    headers = [
        "任务ID", "患者ID", "姓名", "性别", "年龄", "眼别",
        "状态", "风险", "DR 分级", "AI 置信度",
        "送检医院", "送检医师", "文件名", "备注", "提交时间",
    ]
    ws.append(headers)
    header_fill = PatternFill("solid", fgColor="1F6FEB")
    for col_idx, _ in enumerate(headers, start=1):
        cell = ws.cell(row=1, column=col_idx)
        cell.font = Font(name="微软雅黑", size=11, bold=True, color="FFFFFF")
        cell.fill = header_fill
        cell.alignment = Alignment(horizontal="center", vertical="center")

    for t in tasks:
        ws.append([
            t.id,
            t.patient_id,
            t.patient_name,
            t.gender,
            t.age,
            t.eye,
            t.status,
            t.risk or "",
            t.dr,
            round(t.confidence, 4) if t.confidence else 0,
            t.hospital,
            t.doctor,
            t.file_name,
            t.remark,
            t.created_at,
        ])

    # 列宽自适应（粗略）
    widths = [16, 16, 12, 8, 8, 8, 12, 10, 22, 12, 18, 14, 28, 30, 20]
    for i, w in enumerate(widths, start=1):
        ws.column_dimensions[chr(ord("A") + i - 1)].width = w

    buf = io.BytesIO()
    wb.save(buf)
    return buf.getvalue()
