# -*- coding: utf-8 -*-
"""verdict_anchor.py - 判定锚定（三重判断）纯函数
定稿第一章攻七（成功：工具成功/用户未不满/意图一致性≥0.7，至少两重）
与第二章守三（失败：工具失败/用户不满/意图一致性<0.5，至少一重）。

与迭进其他模块解耦：不写规则库、不碰状态文件，便于独立回归测试。
"""
from __future__ import annotations

import re
from typing import List, Tuple

_CN_PUNCT = "，。！？；：、""''（）【】《》—…·"


def _tokens(text: str) -> List[str]:
    """中文按字符、英文按词元切分（一致性评分的轻量近似）"""
    t = (text or "").lower()
    out = []
    buf = []

    def flush():
        if buf:
            out.append("".join(buf))
            buf.clear()

    for ch in t:
        if "一" <= ch <= "鿿":
            flush()
            out.append(ch)
        elif ch.isalnum() or ch == "_":
            buf.append(ch)
        else:
            flush()
    flush()
    return out


def intent_consistency_score(intent: str, result: str) -> float:
    """执行结果与原始用户意图的一致性（0-1）。

    近似：意图词元与结果词元的 Jaccard 重叠，再与结果长度覆盖折中，
    避免短结果/空结果虚高。无意图或结果为空 → 0.0（不可判定）。
    """
    intent = (intent or "").strip()
    result = (result or "").strip()
    if not intent or not result:
        return 0.0
    a = _tokens(intent)
    b = _tokens(result)
    if not a or not b:
        return 0.0
    set_a, set_b = set(a), set(b)
    inter = len(set_a & set_b)
    union = len(set_a | set_b)
    if union == 0:
        return 0.0
    jaccard = inter / union
    # 结果长度覆盖：结果过短（<意图词元一半）时按比例折中，防"只含一个命中词"虚高
    coverage = min(1.0, len(b) / max(1, len(a)))
    return round(min(1.0, jaccard * 0.7 + coverage * 0.3), 4)


def judge_success(tool_ok: bool, user_not_negative: bool | None,
                  consistency: float | None, cons_threshold: float = 0.7) -> Tuple[bool, List[str]]:
    """攻七·成功三重判定：工具成功 / 用户未不满 / 一致性≥阈值，至少两重。

    user_not_negative=None 表示该重无观测数据（不算满足，也不计失败）；
    consistency=None 表示无意图对比数据（不算满足）。
    返回 (是否判定成功, 各重判定说明列表)。
    """
    reasons: List[str] = []
    met = 0
    if tool_ok:
        met += 1
        reasons.append("工具返回成功")
    else:
        reasons.append("工具返回失败/异常")
    if user_not_negative is True:
        met += 1
        reasons.append("用户未表示不满意")
    elif user_not_negative is False:
        reasons.append("用户明确不满意/指正")
    else:
        reasons.append("用户反馈无观测")
    if consistency is not None and consistency >= cons_threshold:
        met += 1
        reasons.append("意图一致性≥%s(%.2f)" % (cons_threshold, consistency))
    elif consistency is not None:
        reasons.append("意图一致性<%s(%.2f)" % (cons_threshold, consistency))
    else:
        reasons.append("意图一致性无观测")
    return (met >= 2, reasons)


def judge_failure(tool_fail: bool, user_negative: bool | None,
                  consistency: float | None, cons_threshold: float = 0.5) -> Tuple[bool, List[str]]:
    """守三·失败三重判定：工具失败 / 用户不满 / 一致性<阈值，至少一重。

    无观测的重视为不满足（守三采"至少一重即触发"，缺观测不虚增）。
    返回 (是否触发 strike, 各重判定说明列表)。
    """
    reasons: List[str] = []
    met = 0
    if tool_fail:
        met += 1
        reasons.append("工具返回失败/异常")
    else:
        reasons.append("工具返回成功")
    if user_negative is True:
        met += 1
        reasons.append("用户明确不满意/指正")
    elif user_negative is False:
        reasons.append("用户未表示不满意")
    else:
        reasons.append("用户反馈无观测")
    if consistency is not None and consistency < cons_threshold:
        met += 1
        reasons.append("意图一致性<%s(%.2f)" % (cons_threshold, consistency))
    elif consistency is not None:
        reasons.append("意图一致性≥%s(%.2f)" % (cons_threshold, consistency))
    else:
        reasons.append("意图一致性无观测")
    return (met >= 1, reasons)
