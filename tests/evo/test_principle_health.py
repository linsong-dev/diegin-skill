"""Tests for evo.main.principle_health —— 一二不过三健康看板回归测试

v3.8.2 回归：fix_status=verified 的 strike 视为已修复闭环，
不应计入待干预升级率（修复前已闭环的 count>=3 会导致 🔴 误报）。
"""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "engine"))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "engine", "evo"))

import evidence_vault
import evo.main as main


class _FakeEngine:
    def get_interceptions(self, active_only=True):
        return []

    def get_patterns(self, active_only=True):
        return []


class _FakeTracker:
    def __init__(self, db):
        self._db = db

    def _load_strikes_db(self):
        return self._db


class _FakeArbiter:
    pending_conflicts = []


class _FakePace:
    _classify_log = []

    def _check_downtime(self):
        return False


class _FakeClosure:
    def get_open_items(self):
        return []

    def get_closed_count(self):
        return 0


class _FakeVault:
    def get_stats(self):
        return {}


def _patch(monkeypatch, db):
    monkeypatch.setattr(main, "_get_engine", lambda: _FakeEngine())
    monkeypatch.setattr(main, "_get_tracker", lambda: _FakeTracker(db))
    monkeypatch.setattr(main, "_get_arbiter", lambda: _FakeArbiter())
    monkeypatch.setattr(main, "_get_pacemaker_inst", lambda: _FakePace())
    monkeypatch.setattr(main, "_get_closure_inst", lambda: _FakeClosure())
    monkeypatch.setattr(evidence_vault, "get_vault", lambda: _FakeVault())


def _strike_health(monkeypatch, db):
    _patch(monkeypatch, db)
    return main.principle_health()["一二不过三"]


def test_all_verified_green(monkeypatch):
    """全部已修复验证 → 无待干预 → 绿灯（修复前误报红灯）"""
    db = {
        "command_failure": {"count": 3, "fix_status": "verified"},
        "tool_error_Bash": {"count": 3, "fix_status": "verified"},
        "image_url": {"count": 1, "fix_status": "verified"},
    }
    h = _strike_health(monkeypatch, db)
    assert h["health"] == "🟢"
    assert h["strike_types"] == 0
    assert h["strikes_total"] == 3
    assert h["strikes_verified"] == 3
    assert h["escalation_rate"] == 0.0


def test_mixed_verified_and_pending_green(monkeypatch):
    """verified + 未升级 pending → 绿灯（修复前误报红灯）"""
    db = {
        "command_failure": {"count": 3, "fix_status": "verified"},
        "tool_error_Bash": {"count": 3, "fix_status": "verified"},
        "image_url": {"count": 1},
    }
    h = _strike_health(monkeypatch, db)
    assert h["health"] == "🟢"
    assert h["strike_types"] == 1
    assert h["strikes_total"] == 3
    assert h["strikes_verified"] == 2
    assert h["escalation_rate"] == 0.0


def test_pending_escalated_red(monkeypatch):
    """未修复且升级 → 仍须红灯干预（修复不得掩盖真实异常）"""
    db = {
        "command_failure": {"count": 3, "fix_status": "verified"},
        "new_critical": {"count": 3},
    }
    h = _strike_health(monkeypatch, db)
    assert h["health"] == "🔴"
    assert h["strike_types"] == 1
    assert h["escalation_rate"] == 1.0


def test_pending_mid_yellow(monkeypatch):
    """未修复中危升级率 → 黄灯关注"""
    db = {
        "a": {"count": 3},
        "b": {"count": 1},
        "c": {"count": 1},
        "d": {"count": 1},
        "e": {"count": 1},
    }
    h = _strike_health(monkeypatch, db)
    assert h["escalation_rate"] == 0.2
    assert h["health"] == "🟡"