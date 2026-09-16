# -*- coding: utf-8 -*-
"""
AI 辅助诊断的眼别展示（2026-08 用户测试报告 D-2）

「数据库明明只有一张右眼的，但显示是双眼。」

原因：_pick_eye_images 里 `left = os_url or ou_url or od_url`，只有 OD 的病例
会回退到右眼图，前端又写死渲染 left + right 两张卡，于是一张右眼眼底照被打上
「左眼 OS」的标签，还配一个由它算出来的假左眼分级。

把右眼影像当左眼展示是错误信息，不是显示瑕疵，所以这里守的是眼别标注的正确性：
两个 URL 仍然都填（算法接口要两张图），但 eye_cards 必须只列真实存在的眼别。
"""

import pytest

from app.db.models import TrainingCase
from app.services.training_ai_service import _pick_eye_images


def _case(paths):
    c = TrainingCase()
    c.image_paths = paths
    return c


def test_right_eye_only_is_not_shown_as_both():
    """报告里的原始场景"""
    left, right, cards = _pick_eye_images(_case({"OD": ["/static/od.jpg"]}))

    assert cards == ["right"], "只有右眼影像时不能再画出左眼卡"
    # 送检仍然是两张（算法要求），但展示只认右眼
    assert right == "/static/od.jpg"
    assert left == "/static/od.jpg"


def test_left_eye_only():
    left, right, cards = _pick_eye_images(_case({"OS": ["/static/os.jpg"]}))
    assert cards == ["left"]
    assert left == "/static/os.jpg"


def test_true_binocular_case_shows_both():
    left, right, cards = _pick_eye_images(
        _case({"OS": ["/static/os.jpg"], "OD": ["/static/od.jpg"]})
    )
    assert cards == ["left", "right"]
    assert left == "/static/os.jpg"
    assert right == "/static/od.jpg"


def test_ou_single_image_shows_one_card():
    """OU 是一张双眼图，画两张一模一样的卡只会让人以为有两份影像"""
    left, right, cards = _pick_eye_images(_case({"OU": ["/static/ou.jpg"]}))
    assert cards == ["ou"]
    assert left == right == "/static/ou.jpg"


def test_no_image_yields_no_cards():
    left, right, cards = _pick_eye_images(_case({}))
    assert cards == []
    assert left is None and right is None


@pytest.mark.parametrize("paths", [None, "not-a-dict", []])
def test_malformed_image_paths_do_not_crash(paths):
    """存量数据里 image_paths 不一定是规整的 dict"""
    left, right, cards = _pick_eye_images(_case(paths))
    assert cards == []
    assert left is None and right is None
