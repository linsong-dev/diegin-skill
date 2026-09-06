# -*- coding: utf-8 -*-
"""shousan_guard.py - 守三下调登记 与 P6 调权 50% 上限（2026-09-05 律令九章修订版 第六章）

若守三下调与 P6 调权同时作用于同一规则，P6 调权幅度不得超过守三下调幅度的 50%
（例如守三下调 -0.4，P6 最多上调 +0.2），确保客观失败信号不被方向调权完全抵消。
守三下调 = 对客观失败/阻断失效的置信度硬性下调（升级归零 / 复盘负调 / 用户否决）。
"""
from __future__ import annotations

import datetime
import json
import os

_STATE_PATH = None
P6_MAX_RATIO = 0.5      # P6 上调 <= 守三下调幅度的 50%
WINDOW_DAYS = 30        # 下调记录有效窗口：仅近窗下调钳制 P6，防历史旧账无限期压制
MAX_RECORDS = 20        # 单规则保留条数


def _path() -> str:
    global _STATE_PATH
    if _STATE_PATH is None:
        _STATE_PATH = os.path.join(
            os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
            "var", "state", "shousan_down_regs.json")
    return _STATE_PATH


def _load() -> dict:
    try:
        if os.path.exists(_path()):
            with open(_path(), "r", encoding="utf-8") as f:
                data = json.load(f)
            return data if isinstance(data, dict) else {}
    except Exception:
        pass
    return {}


def _save(data: dict) -> None:
    try:
        os.makedirs(os.path.dirname(_path()), exist_ok=True)
        with open(_path(), "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
    except Exception:
        pass


def record(rule_id, amount, reason="") -> None:
    """守三/客观失败下调规则置信度后登记（amount 为下调绝对值，>0 有效）"""
    try:
        amount = float(amount)
        if not rule_id or amount <= 0:
            return
        from datetime import timedelta
        data = _load()
        prev = data.get(rule_id) or {}
        recs = prev.get("records", []) if isinstance(prev, dict) else []
        cutoff = (datetime.datetime.now() - timedelta(days=WINDOW_DAYS)).isoformat()
        recs = [r for r in recs if str(r.get("ts", "")) >= cutoff]
        recs.append({"amount": round(amount, 4),
                     "ts": datetime.datetime.now().isoformat(),
                     "reason": str(reason)[:120]})
        recs = recs[-MAX_RECORDS:]
        total = round(sum(float(r.get("amount", 0) or 0) for r in recs), 4)
        data[rule_id] = {"records": recs, "total_recent": total,
                         "last_ts": recs[-1]["ts"] if recs else ""}
        _save(data)
    except Exception:
        pass


def cap(rule_id, proposed_up):
    """P6 正向调权前调用：返回允许的最大上调幅度 min(proposed, 0.5 * 近窗守三下调总和)"""
    try:
        proposed = float(proposed_up)
        if proposed <= 0 or not rule_id:
            return proposed_up
        data = _load()
        entry = data.get(rule_id) or {}
        total = float(entry.get("total_recent", 0) or 0) if isinstance(entry, dict) else 0
        if total <= 0:
            return proposed_up
        limit = round(total * P6_MAX_RATIO, 4)
        return min(proposed, limit)
    except Exception:
        return proposed_up


def summary() -> dict:
    """运维视图：规则 -> 近窗守三下调总量"""
    data = _load()
    return {k: (v.get("total_recent", 0) if isinstance(v, dict) else 0)
            for k, v in data.items()}