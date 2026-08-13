# -*- coding: utf-8 -*-
"""一二不过三·升级三步（定稿第三章）：dgen_fatal_errors 永久记录 + 人工介入通知 + 24h 静默锁止
2026-08-13 完整终版细则
"""
import json
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "engine"))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "engine", "evo"))

from evo.tracker import BehaviorTracker
from evo.rule_engine import RuleEngine


def _make_tracker(tmp_path, monkeypatch):
    eng = RuleEngine(rules_dir=str(tmp_path / "rules"))
    tr = BehaviorTracker(eng)
    sp = str(tmp_path / "strikes_db.json")
    monkeypatch.setattr(tr, "_strikes_db_path", lambda: sp)
    return tr


def _strike3(tr, et="test_escalation_x"):
    """连续 3 次同类错误 → 触发升级三步"""
    for _ in range(3):
        tr.record_self_error(et, "测试内部错误详情")
    return et


# ── 升级三步①：dgen_fatal_errors 永久记录 ──

def test_fatal_errors_recorded_on_third_breach(tmp_path, monkeypatch):
    tr = _make_tracker(tmp_path, monkeypatch)
    et = _strike3(tr)
    fatal = tr._load_json_safe(tr._fatal_errors_path(), {})
    assert et in fatal
    e = fatal[et]
    assert e.get("permanent") is True
    assert e.get("confidence") == 0.0
    assert e.get("strike_count") == 3
    assert e["prototype"]["rule_id"].startswith("self_error_")
    assert "trigger" in e["prototype"]


# ── 升级三步③：人工介入通知 ──

def test_human_escalation_notified_with_24h_deadline(tmp_path, monkeypatch):
    from datetime import datetime, timedelta
    tr = _make_tracker(tmp_path, monkeypatch)
    et = _strike3(tr)
    esc = tr._load_json_safe(tr._human_escalation_path(), {})
    assert et in esc
    e = esc[et]
    assert e.get("status") == "awaiting_human"
    deadline = datetime.fromisoformat(e["deadline"])
    gap = deadline - datetime.fromisoformat(e["notified_at"])
    assert 23 < gap.total_seconds() / 3600 <= 24
    assert "静默锁止" in e.get("escalation_report", "")


def test_check_human_escalation_before_deadline_no_lock(tmp_path, monkeypatch):
    from datetime import datetime, timedelta
    tr = _make_tracker(tmp_path, monkeypatch)
    et = _strike3(tr)
    esc = tr._load_json_safe(tr._human_escalation_path(), {})
    esc[et]["deadline"] = (datetime.now() + timedelta(hours=1)).isoformat()
    tr._save_json_safe(tr._human_escalation_path(), esc)
    lockdown = tr.check_human_escalation()
    assert et not in lockdown
    assert tr._load_json_safe(tr._silent_lockdown_path(), {}).get(et) is None


def test_check_human_escalation_after_deadline_locks(tmp_path, monkeypatch):
    from datetime import datetime, timedelta
    tr = _make_tracker(tmp_path, monkeypatch)
    et = _strike3(tr)
    esc = tr._load_json_safe(tr._human_escalation_path(), {})
    esc[et]["deadline"] = (datetime.now() - timedelta(minutes=1)).isoformat()
    tr._save_json_safe(tr._human_escalation_path(), esc)
    lockdown = tr.check_human_escalation()
    assert et in lockdown
    assert lockdown[et]["status"] == "locked"
    esc2 = tr._load_json_safe(tr._human_escalation_path(), {})
    assert esc2[et]["status"] == "silent_locked"


# ── 人工确认 ──

def test_human_confirm_clears_escalation_and_lockdown(tmp_path, monkeypatch):
    from datetime import datetime, timedelta
    tr = _make_tracker(tmp_path, monkeypatch)
    et = _strike3(tr)
    esc = tr._load_json_safe(tr._human_escalation_path(), {})
    esc[et]["deadline"] = (datetime.now() - timedelta(minutes=1)).isoformat()
    tr._save_json_safe(tr._human_escalation_path(), esc)
    tr.check_human_escalation()
    r = tr.human_confirm(et, "已人工复核：根因为外部配置，调整策略")
    assert r["confirmed"] is True
    esc2 = tr._load_json_safe(tr._human_escalation_path(), {})
    assert esc2[et]["status"] == "confirmed"
    assert esc2[et].get("note", "") != ""
    assert et not in tr._load_json_safe(tr._silent_lockdown_path(), {})


def test_human_confirm_unknown_type(tmp_path, monkeypatch):
    tr = _make_tracker(tmp_path, monkeypatch)
    r = tr.human_confirm("no_such_error")
    assert r["confirmed"] is False


# ── 状态查询 ──

def test_get_escalation_status_awaiting_and_locked(tmp_path, monkeypatch):
    from datetime import datetime, timedelta
    tr = _make_tracker(tmp_path, monkeypatch)
    et1 = _strike3(tr, "test_algo_x")
    et2 = _strike3(tr, "test_db_y")
    esc = tr._load_json_safe(tr._human_escalation_path(), {})
    esc[et2]["deadline"] = (datetime.now() - timedelta(minutes=1)).isoformat()
    tr._save_json_safe(tr._human_escalation_path(), esc)
    tr.check_human_escalation()
    st = tr.get_escalation_status()
    awaiting = [a["error_type"] for a in st["awaiting"]]
    locked = [l["error_type"] for l in st["locked"]]
    assert et1 in awaiting
    assert et2 in locked
