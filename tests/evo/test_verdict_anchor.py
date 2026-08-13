# -*- coding: utf-8 -*-
"""判定锚定·三重判断（定稿第一章攻七成功 / 第二章守三失败）
2026-08-13 完整终版细则 + record_success / record_self_error 接线验证
"""
import json
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "engine"))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "engine", "evo"))

from evo.verdict_anchor import (intent_consistency_score, judge_success, judge_failure)
from evo.tracker import BehaviorTracker
from evo.rule_engine import RuleEngine


# ── 意图一致性 ──

def test_consistency_empty():
    assert intent_consistency_score("", "结果") == 0.0
    assert intent_consistency_score("意图", "") == 0.0
    assert intent_consistency_score("", "") == 0.0


def test_consistency_overlap():
    s = intent_consistency_score("帮我写一个Python脚本解析JSON", "已生成Python脚本并解析JSON成功")
    assert s > 0.3  # 中文按字符重叠，命中"python/脚本/json"等词元


def test_consistency_unrelated():
    s = intent_consistency_score("写Python脚本", "查询股票行情数据返回列表")
    assert s < 0.5


# ── 攻七·成功三重判定（至少两重）──

def test_success_two_of_three():
    ok, reasons = judge_success(True, True, 0.8)
    assert ok is True
    assert len(reasons) == 3


def test_success_consistency_below_threshold_still_two():
    ok, reasons = judge_success(True, True, 0.6)
    assert ok is True  # 工具成功+用户未不满 已满足两重


def test_success_only_tool_ok_not_enough():
    ok, reasons = judge_success(True, None, None)
    assert ok is False  # 单重：不满足至少两重


def test_success_all_three_met():
    ok, reasons = judge_success(True, True, 0.95)
    assert ok is True


def test_success_tool_fail_but_two_others():
    ok, reasons = judge_success(False, True, 0.9)
    assert ok is True  # 用户未不满+一致性≥0.7 = 两重


# ── 守三·失败三重判定（至少一重）──

def test_failure_tool_fail_alone():
    ok, reasons = judge_failure(True, None, None)
    assert ok is True  # 工具失败即满足至少一重


def test_failure_user_negative_alone():
    ok, reasons = judge_failure(False, True, None)
    assert ok is True


def test_failure_consistency_low_alone():
    ok, reasons = judge_failure(False, None, 0.3)
    assert ok is True


def test_failure_no_evidence():
    ok, reasons = judge_failure(False, None, 0.9)
    assert ok is False


# ── record_self_error 三重证据（守三接线）──

def _make_tracker(tmp_path, monkeypatch):
    eng = RuleEngine(rules_dir=str(tmp_path / "rules"))
    tr = BehaviorTracker(eng)
    sp = str(tmp_path / "strikes_db.json")
    monkeypatch.setattr(tr, "_strikes_db_path", lambda: sp)
    return tr


def test_record_self_error_triple_anchor_evidence(tmp_path, monkeypatch):
    tr = _make_tracker(tmp_path, monkeypatch)
    tr.record_self_error("test_anchor_err", "测试失败详情", intent_summary="写Python脚本解析JSON",
                         result_text="查询股票行情返回列表", user_negative=True)
    db = tr._load_strikes_db()
    e = db["test_anchor_err"]
    ta = e.get("triple_anchor", {})
    assert ta.get("verdict") == "strike"
    assert ta.get("user_negative") is True
    assert ta.get("consistency") is not None
    assert len(ta.get("reasons", [])) == 3


def test_record_self_error_no_context_no_anchor(tmp_path, monkeypatch):
    tr = _make_tracker(tmp_path, monkeypatch)
    tr.record_self_error("test_plain_err", "测试")
    db = tr._load_strikes_db()
    assert "triple_anchor" not in db["test_plain_err"]


# 注：record_success 的 CLI 三重门经端到端冒烟验证（真实 stdin JSON 调 record_success，
# 见 trail §44）；单重兼容路径（无意图上下文）由既有 test_gongqi_recommend/audit 覆盖。
