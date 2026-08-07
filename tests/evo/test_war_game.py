"""Tests for evo.war_game"""
import os, sys, shutil
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "engine"))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "engine", "evo"))
from war_game import WarGameEngine
from rule_engine import RuleEngine, InterceptionRule, SuccessPattern
TEST_DIR = os.path.join(os.path.dirname(__file__), "_test_war")
def setup():
    if os.path.exists(TEST_DIR): shutil.rmtree(TEST_DIR)
    os.makedirs(TEST_DIR, exist_ok=True)
def teardown():
    if os.path.exists(TEST_DIR): shutil.rmtree(TEST_DIR)
def _make_eng():
    setup(); return RuleEngine(rules_dir=TEST_DIR)

def _full_scenario():
    """现行引擎 _generate_scenarios 的 interception 场景结构（含 type 等字段）"""
    return {
        "name": "destructive_file_op", "type": "interception",
        "condition": "op in ('delete', 'move', 'rename') AND recursive == true",
        "severity": "critical", "tags": ["global", "irreversible", "file_safety"],
        "action": "block_execution; require_explicit_approval",
        "logic_score": 5.0, "outcome_score": 4.5
    }

def test_init():
    eng = _make_eng()
    wg = WarGameEngine(eng)
    assert wg.rule_engine is not None
    assert wg.min_backtest_score == 2.5
    teardown(); print("  [PASS] init")

def test_run_scenarios():
    eng = _make_eng()
    # P0 触发验证门：wargame 场景 condition 引用 op/recursive（钩子无此字段），
    # 隔离空库下写入会被拒。临时豁免门以验证 run_scenarios 全流程。
    _orig = eng._guard_trigger
    eng._guard_trigger = lambda rule_id, trigger, kind: []
    try:
        wg = WarGameEngine(eng)
        results = wg.run_scenarios({"assets": ["A"]}, {"trend": "up"})
        assert isinstance(results, list)
        assert len(results) == 13  # 13 default scenarios (interception + pattern)
        for r in results:
            assert ("id" in r) or (r.get("status") == "rejected")
    finally:
        eng._guard_trigger = _orig
    teardown(); print("  [PASS] run_scenarios")

def test_generate_skeleton():
    eng = _make_eng()
    wg = WarGameEngine(eng)
    skeleton = wg._generate_skeleton(_full_scenario(), {"x": 1}, {"y": 2})
    assert skeleton["scenario"] == "destructive_file_op"
    assert skeleton["type"] == "interception"
    assert "condition" in skeleton
    assert "action" in skeleton
    teardown(); print("  [PASS] _generate_skeleton")

def test_validate_with_history():
    eng = _make_eng()
    wg = WarGameEngine(eng)
    skeleton = _full_scenario()
    score = wg._validate_with_history(skeleton)
    assert isinstance(score, float)
    assert 0 <= score <= 5
    teardown(); print("  [PASS] _validate_with_history")

def test_validate_with_history_boosted():
    eng = _make_eng()
    eng.add_interception(InterceptionRule(
        id="wg_ref_001",
        trigger_condition="command == 'delete'",
        action="block", severity="critical", tags=["global"], confidence=4.0))
    wg = WarGameEngine(eng)
    skeleton = _full_scenario()
    score = wg._validate_with_history(skeleton)
    assert score > 0  # 关键词交集（delete 等）提升分数
    teardown(); print("  [PASS] _validate_with_history boosted")

def test_extract_keywords():
    eng = _make_eng()
    wg = WarGameEngine(eng)
    kws = wg._extract_keywords("if market drops then sell")
    assert isinstance(kws, list)
    teardown(); print("  [PASS] _extract_keywords")

def test_package_template():
    eng = _make_eng()
    wg = WarGameEngine(eng)
    skeleton = wg._generate_skeleton(_full_scenario(), {"x": 1}, {"y": 2})
    tmpl = wg._package_template(skeleton, _full_scenario())
    assert tmpl["type"] == "interception"
    assert tmpl["trigger_condition"] == skeleton["condition"]
    assert tmpl["lifecycle_status"] == "active"
    expected_conf = skeleton["logic_score"] * 0.6 + skeleton["outcome_score"] * 0.4
    assert abs(tmpl["confidence"] - expected_conf) < 1e-6
    teardown(); print("  [PASS] _package_template")

def test_cache_template():
    eng = _make_eng()
    wg = WarGameEngine(eng)
    tmpl = {
        "type": "interception", "id": "wg_test_001",
        "trigger_condition": "task_type == 'pre_tool' AND command == 'delete'",
        "action": "block", "severity": "high", "tags": ["t"],
        "logic_score": 4.0, "outcome_score": 3.5, "confidence": 3.8,
        "source": "war_game", "lifecycle_status": "active", "created_at": "2026-01-01"
    }
    wg._cache_template(tmpl)
    cached = eng.get_interception_by_id("wg_test_001")
    assert cached is not None
    assert cached.trigger_condition == tmpl["trigger_condition"]
    teardown(); print("  [PASS] _cache_template")
if __name__ == "__main__":
    print("=== evo.war_game Test Suite ===\n")
    tests = [test_init, test_run_scenarios, test_generate_skeleton, test_validate_with_history, test_validate_with_history_boosted, test_extract_keywords, test_package_template, test_cache_template]
    passed=0
    for t in tests:
        try: t(); passed+=1
        except Exception as e:
            import traceback; print(f"  [FAIL] {t.__name__}: {e}"); traceback.print_exc()
    print(f"\n=== {passed}/{len(tests)} tests passed ===")
