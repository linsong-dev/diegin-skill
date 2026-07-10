"""Tests for evo.dashboard"""
import os, sys, shutil
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "engine"))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "engine", "evo"))
from dashboard import HealthDashboard, run_health_check
from rule_engine import RuleEngine, InterceptionRule, SuccessPattern, Precedent
TEST_DIR = os.path.join(os.path.dirname(__file__), "_test_dash")
def setup():
    if os.path.exists(TEST_DIR): shutil.rmtree(TEST_DIR)
    os.makedirs(TEST_DIR, exist_ok=True)
def teardown():
    if os.path.exists(TEST_DIR): shutil.rmtree(TEST_DIR)
def _make_dash():
    setup()
    eng = RuleEngine(rules_dir=TEST_DIR)
    return HealthDashboard(eng), eng
def test_init():
    dash, eng = _make_dash()
    assert dash.rule_engine is not None
    assert len(dash._scenario_keywords) == 13
    teardown(); print("  [PASS] init")
def test_generate_report_empty():
    dash, eng = _make_dash()
    report = dash.generate_report()
    assert report["total_rules"] == 0
    assert report["cognitive_entropy"] == 0
    assert report["decision_snr"] == 1.0
    assert report["satisfaction"] == 1.0
    teardown(); print("  [PASS] generate_report empty")
def test_generate_report_with_rules():
    dash, eng = _make_dash()
    eng.add_interception(InterceptionRule(id="r1", trigger_condition="x", action="block", severity="high", tags=["风险"], triggered_count=5))
    eng.add_interception(InterceptionRule(id="r2", trigger_condition="y", action="block", severity="low", tags=["通用"], triggered_count=3, ignored_count=1))
    eng.add_pattern(SuccessPattern(id="p1", pattern_name="safe", trigger_scenario="风险", decision_logic="allow"))
    report = dash.generate_report()
    assert report["total_rules"] == 3
    assert report["active_rules"] == 3
    assert report["cached_rules"] == 0
    assert report["decision_snr"] > 0
    assert report["strategy_capacity"] >= 1
    assert len(report["recommendations"]) > 0
    teardown(); print("  [PASS] generate_report with rules")
def test_generate_report_full_stats():
    dash, eng = _make_dash()
    eng.add_interception(InterceptionRule(id="r1", trigger_condition="a", action="block", severity="high", tags=["风险"], triggered_count=10, lifecycle_status="active"))
    eng.add_interception(InterceptionRule(id="r2", trigger_condition="b", action="block", severity="medium", tags=["宏观"], triggered_count=5, ignored_count=2, lifecycle_status="deprecating"))
    eng.add_interception(InterceptionRule(id="r3", trigger_condition="c", action="block", severity="low", tags=["项目"], triggered_count=0, lifecycle_status="cached"))
    report = dash.generate_report()
    assert report["active_rules"] == 1
    assert report["deprecating_rules"] == 1
    assert report["cached_rules"] == 1
    teardown(); print("  [PASS] generate_report full stats")
def test_count_conflicts():
    dash, eng = _make_dash()
    eng.add_precedent(Precedent(id="p1", conflict_rules=["a","b"], resolution="auto_degraded"))
    eng.add_precedent(Precedent(id="p2", conflict_rules=["c","d"], resolution="human_resolved"))
    assert dash._count_conflicts() == 1
    teardown(); print("  [PASS] _count_conflicts")
def test_calculate_snr():
    dash, eng = _make_dash()
    r1 = InterceptionRule(id="r1", trigger_condition="x", action="block", severity="high", tags=["t"], triggered_count=10, ignored_count=2, override_count=1)
    snr = dash._calculate_snr([r1])
    # (10-2-1)/10 = 0.7
    assert snr == 0.7, f"Expected 0.7, got {snr}"
    teardown(); print("  [PASS] _calculate_snr")
def test_calculate_snr_no_triggers():
    dash, eng = _make_dash()
    assert dash._calculate_snr([]) == 1.0
    teardown(); print("  [PASS] _calculate_snr no triggers")
def test_count_scenarios():
    dash, eng = _make_dash()
    r1 = InterceptionRule(id="r1", trigger_condition="风险", action="block", severity="high", tags=["t"])
    r2 = InterceptionRule(id="r2", trigger_condition="项目", action="block", severity="low", tags=["t"])
    p1 = SuccessPattern(id="p1", pattern_name="safe", trigger_scenario="宏观", decision_logic="allow")
    cnt = dash._count_scenarios([r1, r2, p1])
    assert cnt == 3
    teardown(); print("  [PASS] _count_scenarios")
def test_status_functions():
    dash, eng = _make_dash()
    assert "健康" in dash._status_entropy(3)
    assert "过高" in dash._status_entropy(11)
    assert "健康" in dash._status_snr(0.8)
    assert "过低" in dash._status_snr(0.2)
    assert "不足" in dash._status_capacity(1)
    assert "一般" in dash._status_capacity(4)
    assert "充足" in dash._status_capacity(6)
    assert "良好" in dash._status_satisfaction(0.8)
    assert "极低" in dash._status_satisfaction(0.1)
    teardown(); print("  [PASS] _status_* functions")
def test_recommendations():
    dash, eng = _make_dash()
    recs = dash._generate_recommendations(entropy=15, snr=0.2, capacity=1, satisfaction=0.1, redundancy=0.5)
    assert len(recs) >= 4  # Should generate many warnings
    # Healthy case
    recs2 = dash._generate_recommendations(entropy=1, snr=0.9, capacity=6, satisfaction=0.9, redundancy=0.0)
    assert any("[OK]" in r for r in recs2)
    teardown(); print("  [PASS] _generate_recommendations")
def test_run_health_check():
    eng = RuleEngine(rules_dir=TEST_DIR)
    eng.add_interception(InterceptionRule(id="r1", trigger_condition="x", action="block", severity="high", tags=["t"]))
    report = run_health_check(eng)
    assert isinstance(report, dict)
    assert report["total_rules"] == 1
    shutil.rmtree(TEST_DIR)
    print("  [PASS] run_health_check")
if __name__ == "__main__":
    print("=== evo.dashboard Test Suite ===\n")
    tests = [test_init, test_generate_report_empty, test_generate_report_with_rules, test_generate_report_full_stats, test_count_conflicts, test_calculate_snr, test_calculate_snr_no_triggers, test_count_scenarios, test_status_functions, test_recommendations, test_run_health_check]
    passed=0
    for t in tests:
        try: t(); passed+=1
        except Exception as e:
            import traceback; print(f"  [FAIL] {t.__name__}: {e}"); traceback.print_exc()
    print(f"\n=== {passed}/{len(tests)} tests passed ===")