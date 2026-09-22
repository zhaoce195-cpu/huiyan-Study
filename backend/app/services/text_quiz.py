# -*- coding: utf-8 -*-
"""
文字练习题。

阅片一次一张图、一种判读。这里另出一组文字题：知识点判断、单选、填空。
题干和答案都来自平台已有的教学要点和分级用语，不另编临床表现。
作答前不下发答案和讲解。
"""

from __future__ import annotations

import random
from dataclasses import dataclass
from typing import Iterable, Optional, Sequence


@dataclass(frozen=True)
class QuizItem:
    id: str
    kind: str  # knowledge | choice | blank
    stem: str
    answer: str
    options: tuple[str, ...] = ()
    accept: tuple[str, ...] = ()
    explanation: str = ""


KIND_TEXT = {
    "knowledge": "知识点",
    "choice": "选择",
    "blank": "填空",
}

_TF = ("对", "错")

BANK: tuple[QuizItem, ...] = (
    QuizItem(
        "k-av-ratio",
        "knowledge",
        "正常眼底的动静脉比例大约是 2:3。",
        "对",
        _TF,
        explanation="正常眼底要点：视盘界限清晰、动静脉比例约 2:3、黄斑反光锐利。",
    ),
    QuizItem(
        "k-ma-not-pdr",
        "knowledge",
        "只有微动脉瘤、没有出血和渗出，就可以定为增殖期。",
        "错",
        _TF,
        explanation="只有微动脉瘤是 1 级轻度。增殖期要看到新生血管。",
    ),
    QuizItem(
        "k-he-severe",
        "knowledge",
        "大面积视网膜出血提示重度非增殖期，还不等于已经有新生血管。",
        "对",
        _TF,
        explanation="大面积出血提示重度。新生血管才是增殖期的关键。",
    ),
    QuizItem(
        "k-amd-vessels",
        "knowledge",
        "干性黄斑变性和糖网要分开看：前者看黄斑区玻璃膜疣，后者看血管病变。",
        "对",
        _TF,
        explanation="干性 AMD 的要点是黄斑区玻璃膜疣和色素紊乱，和糖网的区别在血管病变。",
    ),
    QuizItem(
        "c-dr1",
        "choice",
        "DR 1 级的关键体征是哪一项？",
        "仅有微动脉瘤",
        ("仅有微动脉瘤", "四个象限都有出血", "视盘新生血管", "黄斑玻璃膜疣"),
        explanation="1 级只有微动脉瘤，没有出血、渗出和 IRMA。",
    ),
    QuizItem(
        "c-421",
        "choice",
        "重度非增殖期的 4-2-1 法则，下面哪一条成立就可以诊断？",
        "4 个象限出血，或 2 个象限静脉串珠，或 1 个象限 IRMA",
        (
            "4 个象限出血，或 2 个象限静脉串珠，或 1 个象限 IRMA",
            "三种表现必须同时出现",
            "只要有硬性渗出",
            "只要眼压升高",
        ),
        explanation="4 个象限出血、2 个象限静脉串珠、1 个象限 IRMA，符合其中任一即是重度。",
    ),
    QuizItem(
        "c-amd",
        "choice",
        "干性年龄相关性黄斑变性，首先要在图上找什么？",
        "黄斑区玻璃膜疣和色素紊乱",
        ("黄斑区玻璃膜疣和色素紊乱", "视盘新生血管", "静脉串珠", "大面积视网膜出血"),
        explanation="干性 AMD 看黄斑区玻璃膜疣、色素紊乱。",
    ),
    QuizItem(
        "c-cd",
        "choice",
        "杯盘比达到多少，再结合神经纤维层缺损、视野缺损和高眼压，提示青光眼？",
        "≥0.6",
        ("≥0.6", "≤0.2", "必须等于 0", "与杯盘比无关"),
        explanation="C/D 比 ≥0.6，加上神经纤维层缺损、视野缺损和高眼压，提示青光眼。",
    ),
    QuizItem(
        "c-grade4",
        "choice",
        "本平台把 DR 4 级写成哪一期？",
        "增殖性",
        ("增殖性", "轻度非增殖", "无 DR", "中度非增殖"),
        explanation="0 到 4 级依次是无 DR、轻度、中度、重度、增殖性。",
    ),
    QuizItem(
        "b-nv",
        "blank",
        "增殖期要找的是视盘或视盘外的____。",
        "新生血管",
        accept=("新生血管", "新生血管（NVD/NVE）", "NVD", "NVE"),
        explanation="增殖期的关键是视盘或视盘外新生血管。",
    ),
    QuizItem(
        "b-ma",
        "blank",
        "微动脉瘤的缩写是____。",
        "MA",
        accept=("MA",),
        explanation="微动脉瘤缩写为 MA，是 1 级最主要的体征。",
    ),
    QuizItem(
        "b-vb",
        "blank",
        "4-2-1 法则里，静脉串珠要累及____个象限。",
        "2",
        accept=("2", "二", "两个", "两"),
        explanation="4 个象限出血、2 个象限静脉串珠、1 个象限 IRMA。",
    ),
    QuizItem(
        "b-ex",
        "blank",
        "硬性渗出反映的是慢性____。",
        "渗漏",
        accept=("渗漏", "慢性渗漏"),
        explanation="硬性渗出反映慢性渗漏。",
    ),
)

BY_ID = {item.id: item for item in BANK}


def _norm(text: str) -> str:
    raw = (text or "").strip().replace(" ", "").replace("　", "")
    raw = raw.translate(str.maketrans("０１２３４５６７８９", "0123456789"))
    return raw.casefold()


def is_correct(item: QuizItem, value: str) -> bool:
    got = _norm(value)
    if not got:
        return False
    accepted = {_norm(item.answer), *(_norm(x) for x in item.accept)}
    return got in accepted


def build_paper(size: int = 4, rng: Optional[random.Random] = None) -> list[QuizItem]:
    """一组里三种题型都有。默认 4 题。"""
    picker = rng or random
    size = max(3, min(size, len(BANK)))
    by_kind: dict[str, list[QuizItem]] = {"knowledge": [], "choice": [], "blank": []}
    for item in BANK:
        by_kind[item.kind].append(item)
    picked: list[QuizItem] = []
    for kind in ("knowledge", "choice", "blank"):
        picked.append(picker.choice(by_kind[kind]))
    used = {item.id for item in picked}
    rest = [item for item in BANK if item.id not in used]
    picker.shuffle(rest)
    picked.extend(rest[: size - len(picked)])
    picker.shuffle(picked)
    return picked


def public_question(item: QuizItem, rng: Optional[random.Random] = None) -> dict:
    """发给学员的题面。选择题选项按题号固定打乱，刷新不会换顺序，也不含答案。"""
    options = list(item.options)
    if item.kind == "choice" and options:
        (rng or random.Random(item.id)).shuffle(options)
    return {
        "id": item.id,
        "kind": item.kind,
        "kind_text": KIND_TEXT[item.kind],
        "stem": item.stem,
        "options": options,
    }


def grade_answers(pairs: Sequence[tuple[str, str]]) -> dict:
    """按题库判分。没写、写错都算错。未知题号不计分。"""
    seen: set[str] = set()
    items = []
    for qid, value in pairs:
        item = BY_ID.get(qid)
        if item is None or qid in seen:
            continue
        seen.add(qid)
        ok = is_correct(item, value)
        items.append({
            "id": item.id,
            "kind": item.kind,
            "kind_text": KIND_TEXT[item.kind],
            "stem": item.stem,
            "yours": (value or "").strip(),
            "expected": item.answer,
            "correct": ok,
            "explanation": item.explanation,
        })
    total = len(items)
    correct = sum(1 for row in items if row["correct"])
    score = round(100 * correct / total) if total else 0
    return {
        "score": score,
        "correct_count": correct,
        "question_count": total,
        "passed": score >= 60,
        "items": items,
    }


def iter_bank() -> Iterable[QuizItem]:
    return BANK


def draw_paper(size: int = 4) -> list[dict]:
    return [public_question(item) for item in build_paper(size)]


def submit_paper(db, user, pairs: Sequence[tuple[str, str]]) -> dict:
    from datetime import datetime

    from fastapi import HTTPException, status

    from app.db.models.text_quiz_attempt import TextQuizAttempt

    result = grade_answers(pairs)
    if result["question_count"] == 0:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "没有可判的题")
    db.add(TextQuizAttempt(
        user_id=user.id,
        score=result["score"],
        correct_count=result["correct_count"],
        question_count=result["question_count"],
        passed=1 if result["passed"] else 0,
        detail=[{
            "id": row["id"],
            "correct": row["correct"],
            "yours": row["yours"],
        } for row in result["items"]],
        submitted_at=datetime.now(),
    ))
    db.commit()
    return result
