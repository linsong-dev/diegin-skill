"""Tests for evo.tracker"""
import os, sys, shutil
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "engine"))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "engine", "evo"))
from tracker import BehaviorTracker
from rule_engine import RuleEngine, InterceptionRule, SuccessPattern
TEST_DIR = os.path.join(os.path.dirname(__file__), "_test_tracker")
def setup():
    if os.path.exists(TEST_DIR): shutil.rmtree(TEST_DIR)
    os.makedirs(TEST_DIR, exist_ok=True)
def teardown():
    if os.path.exists(TEST_DIR): shutil.rmtree(TEST_DIR)
def _make_tracker():
    setup()
    eng = RuleEngine(rules_dir=TEST_DIR)
    return BehaviorTracker(eng), eng
def test_init():
    tr, eng = _make_tracker()
    assert tr.rule_engine is not None
    assert tr.soft_elimination_threshold == 0.8
    assert tr.decay_factor == 0.9
    teardown(); print("  [PASS] init")
def test_record_ignore_not_found():
    tr, eng = _make_tracker()
    r = tr.record_ignore("nonexistent")
    assert r["action"] == "not_found"
    teardown(); print("  [PASS] record_ignore not_found")
def test_record_ignore_increment():
    tr, eng = _make_tracker()
    eng.add_interception(InterceptionRule(id="r1", trigger_condition="x", action="block", severity="high", tags=["t"], triggered_count=10))
    r = tr.record_ignore("r1")
    assert r["action"] == "updated"
    rule = eng.get_interception_by_id("r1")
    assert rule.ignored_count == 1
    teardown(); print("  [PASS] record_ignore increment")
def test_record_ignore_soft_eliminated():
    tr, eng = _make_tracker()
    # Create a rule with high triggered_count and then ignored many times
    eng.add_interception(InterceptionRule(id="r2", trigger_condition="x", action="block", severity="high", tags=["t"], triggered_count=0, ignored_count=0))
    # Ignore it 6 times (0 triggered, 6 ignored = 100% ignored rate > 0.8)
    for _ in range(6):
        tr.record_ignore("r2")
    rule = eng.get_interception_by_id("r2")
    assert rule.ignored_count == 6
    # Check if it got deprecating
    assert rule.lifecycle_status == "deprecating", f"Expected deprecating, got {rule.lifecycle_status}"
    teardown(); print("  [PASS] record_ignore soft_eliminated")
def test_record_override():
    tr, eng = _make_tracker()
    eng.add_interception(InterceptionRule(id="r3", trigger_condition="x", action="block", severity="high", tags=["t"]))
    r = tr.record_override("r3")
    assert r["action"] == "updated"
    rule = eng.get_interception_by_id("r3")
    assert rule.override_count == 1
    teardown(); print("  [PASS] record_override")
def test_record_triggered():
    tr, eng = _make_tracker()
    eng.add_interception(InterceptionRule(id="r4", trigger_condition="x", action="block", severity="high", tags=["t"]))
    r = tr.record_triggered("r4")
    assert r["action"] == "updated"
    rule = eng.get_interception_by_id("r4")
    assert rule.triggered_count == 1
    teardown(); print("  [PASS] record_triggered")
def test_record_self_error():
    tr, eng = _make_tracker()
    r = tr.record_self_error("test_error", "something went wrong", {"task_type": "test"})
    assert "action" in r
    assert r.get("action") != "error"
    teardown(); print("  [PASS] record_self_error")
def test_record_user_feedback_agree():
    tr, eng = _make_tracker()
    eng.add_interception(InterceptionRule(id="r5", trigger_condition="x", action="block", severity="high", tags=["t"]))
    r = tr.record_user_feedback("r5", "agree")
    assert r["action"] in ("confirmed", "updated", "not_found")
    teardown(); print("  [PASS] record_user_feedback agree")
def test_record_user_feedback_veto():
    tr, eng = _make_tracker()
    eng.add_interception(InterceptionRule(id="r6", trigger_condition="x", action="block", severity="high", tags=["t"]))
    r = tr.record_user_feedback("r6", "veto")
    assert r["action"] in ("vetoed", "updated", "not_found")
    teardown(); print("  [PASS] record_user_feedback veto")
def test_record_user_feedback_not_found():
    tr, eng = _make_tracker()
    r = tr.record_user_feedback("no_such_rule", "agree")
    assert r["action"] == "not_found"
    teardown(); print("  [PASS] record_user_feedback not_found")
def test_get_ignored_rules():
    tr, eng = _make_tracker()
    eng.add_interception(InterceptionRule(id="g1", trigger_condition="x", action="block", severity="high", tags=["t"], ignored_count=5))
    eng.add_interception(InterceptionRule(id="g2", trigger_condition="y", action="block", severity="low", tags=["t"], ignored_count=0))
    ignored = tr.get_ignored_rules()
    assert len(ignored) >= 1
    teardown(); print("  [PASS] get_ignored_rules")
if __name__ == "__main__":
    print("=== evo.tracker Test Suite ===\n")
    tests = [test_init, test_record_ignore_not_found, test_record_ignore_increment, test_record_ignore_soft_eliminated, test_record_override, test_record_triggered, test_record_self_error, test_record_user_feedback_agree, test_record_user_feedback_veto, test_record_user_feedback_not_found, test_get_ignored_rules]
    passed=0
    for t in tests:
        try: t(); passed+=1
        except Exception as e:
            import traceback; print(f"  [FAIL] {t.__name__}: {e}"); traceback.print_exc()
    print(f"\n=== {passed}/{len(tests)} tests passed ===")