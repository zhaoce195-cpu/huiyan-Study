# -*- coding: utf-8 -*-
"""
状态机：把「哪些流转是合法的」写在一处

对应《医学培训端评估与工作流重构报告》：
    「阅片与练习的状态流转散落在各处，缺少显式建模与留痕」

原先每个写入点各自 if 一遍当前状态，漏一处就是一个非法跃迁。
实际已经漏了一处：阅片审核只在「驳回」分支校验了状态，
「通过」分支没校验 —— 教师可以直接通过一份从未提交的草稿，
DRAFT 一步跳到 REVIEWED，跳过了学员提交这一环。

集中定义之后，新增状态或新增流转只改这张表，
写入点一律走 ensure()，漏不掉。
"""

from typing import Dict, FrozenSet, Optional

from fastapi import HTTPException, status as http_status


class Workflow:
    """一个实体的合法流转表"""

    def __init__(
        self,
        name: str,
        transitions: Dict[str, FrozenSet[str]],
        labels: Dict[str, str],
    ):
        self.name = name
        self.transitions = transitions
        self.labels = labels

    def label(self, state: str) -> str:
        return self.labels.get(state, state)

    def can(self, current: str, target: str) -> bool:
        return target in self.transitions.get(current, frozenset())

    def ensure(self, current: str, target: str) -> None:
        """
        不合法就抛 409 Conflict。

        用 409 而不是 400：请求本身没写错，是实体当前状态不允许这个动作。
        前端据此可以提示「请刷新后重试」，而不是让用户去改表单。
        """
        if self.can(current, target):
            return
        raise HTTPException(
            status_code=http_status.HTTP_409_CONFLICT,
            detail=(
                f"当前状态为「{self.label(current)}」，"
                f"不能变更为「{self.label(target)}」"
            ),
        )


# --------------------------------------------------------------------------
# 阅片
# --------------------------------------------------------------------------
#
# 驳回落到 REJECTED 而不是倒回 DRAFT。
# 倒回 DRAFT 会抹掉「从未提交」和「提交过但被驳回」的区别 ——
# 教师的待办列表分不出哪些是学员还没写完、哪些是等着改回来的。

READING_DRAFT = "DRAFT"
READING_SUBMITTED = "SUBMITTED"
READING_REVIEWED = "REVIEWED"
READING_REJECTED = "REJECTED"

READING = Workflow(
    name="reading",
    transitions={
        READING_DRAFT: frozenset({READING_SUBMITTED}),
        READING_SUBMITTED: frozenset({READING_REVIEWED, READING_REJECTED}),
        # 驳回后学员改完再交，回到待审
        READING_REJECTED: frozenset({READING_SUBMITTED}),
        # 审核通过即终态。要改结论只能重新阅片，不在原记录上改 ——
        # 已通过的结论被就地改掉，审核就失去意义了
        READING_REVIEWED: frozenset(),
    },
    labels={
        READING_DRAFT: "草稿",
        READING_SUBMITTED: "待审核",
        READING_REVIEWED: "已通过",
        READING_REJECTED: "已驳回",
    },
)


# --------------------------------------------------------------------------
# 练习
# --------------------------------------------------------------------------
#
# 练习没有驳回：提交即自动评分，成绩已经产生，退回去改没有意义。
# 教师点评允许重复（改措辞、补充意见），所以 REVIEWED → REVIEWED 合法。

PRACTICE_DRAFT = "DRAFT"
PRACTICE_SUBMITTED = "SUBMITTED"
PRACTICE_REVIEWED = "REVIEWED"

PRACTICE = Workflow(
    name="practice",
    transitions={
        PRACTICE_DRAFT: frozenset({PRACTICE_SUBMITTED}),
        PRACTICE_SUBMITTED: frozenset({PRACTICE_REVIEWED}),
        PRACTICE_REVIEWED: frozenset({PRACTICE_REVIEWED}),
    },
    labels={
        PRACTICE_DRAFT: "进行中",
        PRACTICE_SUBMITTED: "已提交",
        PRACTICE_REVIEWED: "已点评",
    },
)


def transition_detail(
    wf: Workflow,
    entity_id: int,
    current: str,
    target: str,
    extra: Optional[str] = None,
) -> str:
    """审计正文：状态流转要能看出从哪来、到哪去，只写「已提交」是不够的"""
    text = (
        f"{wf.name} #{entity_id} "
        f"{wf.label(current)} → {wf.label(target)}"
    )
    return f"{text} {extra}" if extra else text
