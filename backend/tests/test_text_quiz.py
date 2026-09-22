# -*- coding: utf-8 -*-
from app.services.text_quiz import BANK, build_paper, grade_answers, is_correct, public_question


def test_paper_mixes_three_kinds_and_hides_the_key():
    paper = build_paper(4)
    kinds = {item.kind for item in paper}
    assert kinds == {"knowledge", "choice", "blank"}
    assert len({item.id for item in paper}) == 4
    face = public_question(paper[0])
    assert "explanation" not in face
    assert "answer" not in face


def test_choice_and_knowledge_match_the_option_text():
    choice = next(item for item in BANK if item.id == "c-dr1")
    assert is_correct(choice, "仅有微动脉瘤")
    assert not is_correct(choice, "视盘新生血管")
    false_stmt = next(item for item in BANK if item.id == "k-ma-not-pdr")
    assert is_correct(false_stmt, "错")
    assert not is_correct(false_stmt, "对")


def test_blank_accepts_alias_and_blank_is_wrong():
    ma = next(item for item in BANK if item.id == "b-ma")
    vb = next(item for item in BANK if item.id == "b-vb")
    assert is_correct(ma, "ma")
    assert is_correct(vb, "两个")
    assert not is_correct(vb, "")


def test_text_answers_change_the_practice_total():
    from app.services.practice_service import _score
    from tests.test_dr_grade import FakeCase

    ids = ["c-dr1", "k-av-ratio", "b-ma", "b-vb"]
    wrong, _ = _score(
        FakeCase("3"), "3", "出血 渗出", [],
        text_ids=ids, text_values={},
    )
    right, _ = _score(
        FakeCase("3"), "3", "出血 渗出", [],
        text_ids=ids,
        text_values={
            "c-dr1": "仅有微动脉瘤",
            "k-av-ratio": "对",
            "b-ma": "MA",
            "b-vb": "2",
        },
    )
    plain, _ = _score(FakeCase("3"), "3", "出血 渗出", [])
    assert wrong["text_applicable"] is True
    assert wrong["score_text"] == 0
    assert wrong["score_total"] < plain["score_total"]
    assert right["score_text"] == 100
    assert right["score_total"] == 100


def test_grade_counts_only_known_questions():
    result = grade_answers([
        ("c-dr1", "仅有微动脉瘤"),
        ("b-ma", "MA"),
        ("no-such", "对"),
        ("k-av-ratio", "错"),
    ])
    assert result["question_count"] == 3
    assert result["correct_count"] == 2
    assert result["score"] == 67
    assert result["items"][2]["explanation"]
