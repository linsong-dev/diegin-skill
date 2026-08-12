"""Tests for evo.reviewer._anchor_baseline —— 守三·锚定优先级（定稿第二章）
同场景 success_patterns≥4.0 优先；否则回退 intent_summary
"""
import os, sys, shutil
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "engine"))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "engine", "evo"))
from reviewer import Reviewer
from rule_engine import RuleEngine, SuccessPattern

TEST_DIR = os.path.join(os.path.dirname(__file__), "_test_review_anchor")


def setup():
    if os.path.exists(TEST_DIR):
        shutil.rmtree(TEST_DIR)
    os.makedirs(TEST_DIR, exist_ok=True)


def teardown():
    if os.path.exists(TEST_DIR):
        shutil.rmtree(TEST_DIR)


def _make_reviewer():
    setup()
    eng = RuleEngine(rules_dir=TEST_DIR)
    return Reviewer(eng), eng


def test_anchor_prefers_same_scene_high_conf():
    rev, eng = _make_reviewer()
    eng.add_pattern(SuccessPattern(
        id="pat_bash_write_20260812", pattern_name="bash写入", confidence=5.0,
        trigger_scenario="bash", decision_logic="用 Set-Content 写文件"
    ))
    anchor = rev._anchor_baseline({"task_type": "bash", "intent_summary": "写配置文件"})
    assert anchor["source"] == "success_pattern"
    assert anchor["pattern_id"] == "pat_bash_write_20260812"


def test_anchor_low_conf_fallback_to_intent():
    rev, eng = _make_reviewer()
    eng.add_pattern(SuccessPattern(
        id="pat_low_conf", pattern_name="低置信", confidence=3.5,
        trigger_scenario="bash", decision_logic="低置信模式"
    ))
    anchor = rev._anchor_baseline({"task_type": "bash", "intent_summary": "写配置文件"})
    assert anchor["source"] == "intent_summary"
    assert anchor["baseline"] == "写配置文件"


def test_anchor_no_scene_match_fallback():
    rev, eng = _make_reviewer()
    eng.add_pattern(SuccessPattern(
        id="pat_other_scene", pattern_name="其他场景", confidence=5.0,
        trigger_scenario="python", decision_logic="其他场景模式"
    ))
    anchor = rev._anchor_baseline({"task_type": "bash", "intent_summary": "写配置文件"})
    assert anchor["source"] == "intent_summary"
    assert anchor["baseline"] == "写配置文件"


def test_anchor_empty_patterns_fallback():
    rev, _ = _make_reviewer()
    anchor = rev._anchor_baseline({"task_type": "bash", "intent_summary": "无模式基线"})
    assert anchor["source"] == "intent_summary"
    assert anchor["baseline"] == "无模式基线"


def teardown_module(module):
    teardown()
