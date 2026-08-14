# -*- coding: utf-8 -*-
"""运维手册养护建议·可选增强（trail §45 待处理①）：
2.1 温启动（自照镜连续跳过≥5次/距上次≥3天 → 轻量校准模式）
2.2 用户意图温度计（当前输入 vs 最近 pending 任务意图相似度<0.5 → 意图漂移信号）
2.3 决策超时熔断（衡阶段耗时>2s → 标记降级提示）
2.8 主动推进上限（每次最多验证 1 条 staging 规则）
2.9 参数调整记录 + 参数扰动警告（近30天>3次）
"""
import datetime
import json
import os
import shutil
import sys
import time

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "engine"))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "engine", "evo"))

from evo import self_mirror
from evo.self_mirror import SelfMirror, WARM_START_SKIPS, WARM_START_DAYS
from tracker import BehaviorTracker
from rule_engine import RuleEngine
import evo.main as evo_main
import call_diegin

_SRC_STATE = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(call_diegin.__file__))),
    "var", "state")
_SRC_LOG = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(call_diegin.__file__))),
    "var", "logs", "diegin_audit.log")

_SNAP_FILES = ["constancy_proactive.json", "self_mirror.json", "emergency_track.json",
               "rule_counter_deltas.json", "dgen_marker_pending.json", "dgen_last_reply.json",
               "dgen_verify_result.json", "strikes_db.json", "param_adjustments.json"]


@pytest.fixture()
def snap_restore():
    """pre_check 会写源码库 var/state 与审计日志：快照 → 测试后还原"""
    snap = {}
    for n in _SNAP_FILES:
        p = os.path.join(_SRC_STATE, n)
        snap[n] = open(p, "rb").read() if os.path.exists(p) else None
    log_tail = None
    if os.path.exists(_SRC_LOG):
        with open(_SRC_LOG, "rb") as f:
            f.seek(0, 2)
            size = f.tell()
            f.seek(max(0, size - 8192))
            log_tail = (size, f.read())
    yield
    for n, b in snap.items():
        p = os.path.join(_SRC_STATE, n)
        if b is None:
            if os.path.exists(p):
                os.remove(p)
        else:
            with open(p, "wb") as f:
                f.write(b)
    if log_tail is not None:
        size, tail = log_tail
        with open(_SRC_LOG, "rb+") as f:
            f.truncate(size)


def _make_mirror(tmp_path, monkeypatch):
    target = os.path.join(str(tmp_path), "self_mirror.json")
    monkeypatch.setattr(self_mirror, "_get_state_path", lambda: target)
    return SelfMirror()


# ───────────────────── 2.1 温启动 ─────────────────────

def test_warm_start_not_due_below_threshold(tmp_path, monkeypatch):
    m = _make_mirror(tmp_path, monkeypatch)
    for _ in range(WARM_START_SKIPS - 1):
        m.note_skip()
    assert m._state["consecutive_skips"] == WARM_START_SKIPS - 1
    assert m.warm_start_due() is False


def test_warm_start_due_after_skips_light_mirror(tmp_path, monkeypatch):
    m = _make_mirror(tmp_path, monkeypatch)
    for _ in range(WARM_START_SKIPS):
        m.note_skip()
    assert m.warm_start_due() is True
    report = m.mirror(emergency=True, light=True)
    assert report.get("warm_start") is True
    assert "wakeup_report" in report
    assert report.get("direction_calibration") == []  # 轻量模式不产出 P6 调权
    m.reset_skip()
    assert m._state["consecutive_skips"] == 0


def test_warm_start_due_by_days(tmp_path, monkeypatch):
    m = _make_mirror(tmp_path, monkeypatch)
    m._state["last_mirror_at"] = (
        datetime.datetime.now() - datetime.timedelta(days=WARM_START_DAYS)).isoformat()
    assert m.warm_start_due() is True


def test_mirror_run_if_due_light_when_warm(tmp_path, monkeypatch):
    m = _make_mirror(tmp_path, monkeypatch)
    monkeypatch.setattr(evo_main, "_get_self_mirror_inst", lambda: m)
    for _ in range(WARM_START_SKIPS):
        m.note_skip()
    report = evo_main.mirror_run_if_due()
    assert report is not None
    assert report.get("warm_start") is True
    assert m._state["consecutive_skips"] == 0  # 触发后清零


def test_mirror_run_if_due_normal_resets_skip(tmp_path, monkeypatch):
    m = _make_mirror(tmp_path, monkeypatch)
    monkeypatch.setattr(evo_main, "_get_self_mirror_inst", lambda: m)
    m.note_skip()
    m.note_skip()
    m._state["round"] = 10  # 每10轮到期 → 正常自照
    report = evo_main.mirror_run_if_due()
    assert report is not None
    assert report.get("warm_start") is None  # 正常模式，非轻量
    assert m._state["consecutive_skips"] == 0


# ───────────────────── 2.2 意图温度计 ─────────────────────

def _fake_recoverable(summary="清理开发目录冗余过期文件并整理归档"):
    return [{"task_id": "task_test_0001", "status": "paused",
             "intent_summary": summary, "updated_at": "2026-08-13T10:00:00"}]


def test_intent_drift_triggered_on_unrelated_input(monkeypatch, tmp_path, snap_restore):
    monkeypatch.setattr(evo_main, "constancy_recoverable", lambda: _fake_recoverable())
    monkeypatch.setattr(self_mirror, "_get_state_path",
                        lambda: os.path.join(str(tmp_path), "self_mirror.json"))
    out = call_diegin.pre_check({"task": "帮我查一下今天A股市场主线是什么"})
    drift = out.get("intent_drift")
    assert drift and drift.get("triggered") is True
    assert drift.get("score") < 0.5
    assert isinstance(out.get("decision_elapsed_ms"), (int, float))
    assert isinstance(out.get("decision_timeout"), bool)


def test_intent_drift_absent_on_related_input(monkeypatch, tmp_path, snap_restore):
    monkeypatch.setattr(evo_main, "constancy_recoverable", lambda: _fake_recoverable(
        summary="清理开发目录冗余过期文件并整理归档"))
    monkeypatch.setattr(self_mirror, "_get_state_path",
                        lambda: os.path.join(str(tmp_path), "self_mirror.json"))
    out = call_diegin.pre_check({"task": "继续清理开发目录的冗余文件"})
    drift = out.get("intent_drift")
    assert drift is None  # 语义相似度≥0.5 → 不标记漂移


# ───────────────────── 2.3 决策超时熔断 ─────────────────────

def test_decision_timeout_flag_when_slow(monkeypatch, tmp_path, snap_restore):
    monkeypatch.setattr(evo_main, "constancy_recoverable", lambda: [])
    monkeypatch.setattr(self_mirror, "_get_state_path",
                        lambda: os.path.join(str(tmp_path), "self_mirror.json"))
    orig = call_diegin.arbitrate

    def slow_arbitrate(*args, **kwargs):
        time.sleep(2.1)
        return orig(*args, **kwargs)

    monkeypatch.setattr(call_diegin, "arbitrate", slow_arbitrate)
    out = call_diegin.pre_check({"task": "决策超时测试"})
    assert out.get("decision_timeout") is True
    assert out.get("decision_elapsed_ms", 0.0) >= 2000.0


# ───────────────────── 2.8 主动推进上限 ─────────────────────

def test_proactive_pace_cap_one_candidate(monkeypatch, tmp_path, snap_restore):
    monkeypatch.setattr(evo_main, "constancy_recoverable", lambda: [])
    monkeypatch.setattr(self_mirror, "_get_state_path",
                        lambda: os.path.join(str(tmp_path), "self_mirror.json"))

    class _FakeRule:
        def __init__(self, rid):
            self.id = rid
            self.lifecycle_status = "staging"

    class _FakeEng:
        def retrieve_for_task(self, task_context):
            return {"interceptions": [], "patterns": []}

        def get_interceptions(self, active_only=False):
            return [_FakeRule("staging_r1"), _FakeRule("staging_r2")]

    monkeypatch.setattr(evo_main, "_get_engine", lambda: _FakeEng())
    pro_file = os.path.join(_SRC_STATE, "constancy_proactive.json")
    with open(pro_file, "w", encoding="utf-8") as f:
        json.dump({"streak": 2}, f)  # 本轮无输入 +1 → 3
    out = call_diegin.pre_check({})
    prop = out.get("proactive_proposal")
    assert prop and prop.get("triggered") is True
    assert prop.get("staging_candidates") == ["staging_r1"]  # 每次最多 1 条
    assert prop.get("staging_total") == 2
    assert prop.get("pace_note")


# ───────────────────── 2.9 参数调整记录 ─────────────────────

def _make_tracker(tmp_path):
    eng = RuleEngine(rules_dir=str(tmp_path))
    return BehaviorTracker(eng), eng


def test_param_adjustment_record_and_cap(tmp_path, monkeypatch):
    tr, _ = _make_tracker(tmp_path)
    monkeypatch.setattr(tr, "_strikes_db_path",
                        lambda: os.path.join(str(tmp_path), "state", "strikes_db.json"))
    r = tr.record_param_adjustment("自照镜_勇气衰减系数", "运维调整", "预期降低扰动")
    assert r.get("ok") is True and r.get("count") == 1
    r2 = tr.record_param_adjustment("arbiter_P6限幅", "运维调整2")
    assert r2.get("count") == 2


def test_param_adjustment_warning_below_threshold(tmp_path, monkeypatch):
    tr, _ = _make_tracker(tmp_path)
    monkeypatch.setattr(tr, "_strikes_db_path",
                        lambda: os.path.join(str(tmp_path), "state", "strikes_db.json"))
    tr.record_param_adjustment("参数A")
    st = tr.param_adjustment_warning()
    assert st.get("warning") is False
    assert st.get("count") == 1


def test_param_adjustment_warning_above_threshold(tmp_path, monkeypatch):
    tr, _ = _make_tracker(tmp_path)
    monkeypatch.setattr(tr, "_strikes_db_path",
                        lambda: os.path.join(str(tmp_path), "state", "strikes_db.json"))
    for i in range(4):
        tr.record_param_adjustment("参数%d" % i)
    st = tr.param_adjustment_warning()
    assert st.get("warning") is True  # 4 次 > 3 次/30天
    assert "参数调整频繁" in st.get("note", "")
