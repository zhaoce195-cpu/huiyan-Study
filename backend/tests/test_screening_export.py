# -*- coding: utf-8 -*-
"""汇总报告的中文必须写进 PDF。缺中文字体时不能再落回 Helvetica，否则浏览器用黑块代替汉字。"""

from app.schemas.screening import ScreeningTaskOut
from app.services.screening_export import _register_cn_font, render_summary_pdf


def test_summary_pdf_embeds_chinese_instead_of_black_boxes():
    font = _register_cn_font()
    assert font != "Helvetica"
    pdf = render_summary_pdf([
        ScreeningTaskOut(
            id="D20260619-0001",
            patient_id="P001",
            patient_name="张三",
            eye="OS",
            status="done",
            risk="green",
            dr="0 级 无 DR",
            confidence=0.75,
            created_at="2026-06-16 01:53:44",
        )
    ])
    from pypdf import PdfReader
    import io

    text = PdfReader(io.BytesIO(pdf)).pages[0].extract_text() or ""
    assert "筛查任务汇总" in text
    assert "张三" in text
    assert "眼别" in text
