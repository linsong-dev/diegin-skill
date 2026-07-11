"""Tests for evo.rule_engine"""
import os, sys, json, tempfile, shutil
from datetime import datetime
from pathlib import Path

# Insert engine path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "engine"))
from evo.rule_engine import (
    InterceptionRule, SuccessPattern, MetaExperience, Precedent,
    RuleEngine, get_seed_interceptions, init_rules_if_empty
)

TEST_DIR = os.path.join(os.path.dirname(__file__), "_test_rules")

def setup():
    """Create a fresh test rules directory"""
    if os.path.exists(TEST_DIR):
        shutil.rmtree(TEST_DIR)
    os.makedirs(TEST_DIR, exist_ok=True)

def teardown():
    if os.path.exists(TEST_DIR):
        shutil.rmtree(TEST_DIR)

# ─── Dataclass Construction ───

def test_interception_rule_defaults():
    r = InterceptionRule(id="test_001", trigger_condition="x > 1", action="block", severity="high", tags=["test"])
    assert r.id == "test_001"
    assert r.logic_score == 5.0
    assert r.confidence == 5.0
    assert r.lifecycle_status == "active"
    assert r.source == "seed"
    assert r.triggered_count == 0
    print("  [PASS] InterceptionRule defaults")

def test_success_pattern_defaults():
    p = SuccessPattern(id="pat_001", pattern_name="test", trigger_scenario="qa", decision_logic="always_allow")
    assert p.id == "pat_001"
    assert p.lifecycle_status == "active"
    assert p.confidence == 5.0
    assert p.luck_factor == "low"
    assert p.triggered_count == 0
    print("  [PASS] SuccessPattern defaults")

def test_meta_experience():
    m = MetaExperience(id="meta_001", insight="test insight", applicable_contexts=["qa", "dev"])
    assert m.confidence == 5.0
    assert m.id == "meta_001"
    print("  [PASS] MetaExperience")

def test_precedent():
    pr = Precedent(id="pre_001", conflict_rules=["r1", "r2"], resolution="human_resolved")
    assert pr.winning_rule == ""
    assert pr.decision_logic == ""
    print("  [PASS] Precedent")

# ─── RuleEngine CRUD ───

def test_engine_init():
    setup()
    eng = RuleEngine(rules_dir=TEST_DIR)
    assert eng.get_interceptions() == []
    assert eng.get_patterns() == []
    assert eng.get_metas() == []
    assert eng.get_precedents() == []
    teardown()
    print("  [PASS] Engine init with empty dir")

def test_add_interception():
    setup()
    eng = RuleEngine(rules_dir=TEST_DIR)
    r = InterceptionRule(id="crud_001", trigger_condition="x > 5", action="block", severity="high", tags=["test"])
    rid = eng.add_interception(r)
    assert rid == "crud_001"
    assert len(eng.get_interceptions()) == 1
    assert len(eng.get_interceptions(active_only=False)) == 1
    teardown()
    print("  [PASS] add_interception")

def test_add_interception_auto_id():
    setup()
    eng = RuleEngine(rules_dir=TEST_DIR)
    r = InterceptionRule(id="", trigger_condition="x > 5", action="block", severity="high", tags=["test"])
    rid = eng.add_interception(r)
    assert rid != ""
    assert rid.startswith("rule_")
    teardown()
    print("  [PASS] add_interception auto ID")

def test_get_interception_by_id():
    setup()
    eng = RuleEngine(rules_dir=TEST_DIR)
    r = InterceptionRule(id="get_001", trigger_condition="x > 5", action="block", severity="high", tags=["test"])
    eng.add_interception(r)
    found = eng.get_interception_by_id("get_001")
    assert found is not None
    assert found.id == "get_001"
    assert eng.get_interception_by_id("nonexistent") is None
    teardown()
    print("  [PASS] get_interception_by_id")

def test_update_interception():
    setup()
    eng = RuleEngine(rules_dir=TEST_DIR)
    r = InterceptionRule(id="upd_001", trigger_condition="x > 5", action="block", severity="high", tags=["test"])
    eng.add_interception(r)
    ok = eng.update_interception("upd_001", severity="low", confidence=3.0)
    assert ok == True
    updated = eng.get_interception_by_id("upd_001")
    assert updated.severity == "low"
    assert updated.confidence == 3.0
    # Update nonexistent
    assert eng.update_interception("nope", severity="high") == False
    teardown()
    print("  [PASS] update_interception")

def test_delete_interception():
    setup()
    eng = RuleEngine(rules_dir=TEST_DIR)
    r = InterceptionRule(id="del_001", trigger_condition="x > 5", action="block", severity="high", tags=["test"])
    eng.add_interception(r)
    assert eng.delete_interception("del_001") == True
    assert len(eng.get_interceptions()) == 0
    assert eng.delete_interception("nope") == False
    teardown()
    print("  [PASS] delete_interception")

def test_add_pattern():
    setup()
    eng = RuleEngine(rules_dir=TEST_DIR)
    p = SuccessPattern(id="pat_crud_001", pattern_name="test", trigger_scenario="qa", decision_logic="allow")
    pid = eng.add_pattern(p)
    assert pid == "pat_crud_001"
    assert len(eng.get_patterns()) == 1
    teardown()
    print("  [PASS] add_pattern")

def test_pattern_crud():
    setup()
    eng = RuleEngine(rules_dir=TEST_DIR)
    p = SuccessPattern(id="pat_002", pattern_name="test2", trigger_scenario="dev", decision_logic="check")
    eng.add_pattern(p)
    # get by id
    found = eng.get_pattern_by_id("pat_002")
    assert found is not None
    assert found.pattern_name == "test2"
    # update
    eng.update_pattern("pat_002", confidence=4.0, triggered_count=3)
    updated = eng.get_pattern_by_id("pat_002")
    assert updated.confidence == 4.0
    assert updated.triggered_count == 3
    # delete
    assert eng.delete_pattern("pat_002") == True
    assert eng.get_pattern_by_id("pat_002") is None
    teardown()
    print("  [PASS] pattern CRUD")

def test_active_only_filter():
    setup()
    eng = RuleEngine(rules_dir=TEST_DIR)
    r1 = InterceptionRule(id="act_001", trigger_condition="x", action="block", severity="high", tags=["t"], lifecycle_status="active")
    r2 = InterceptionRule(id="act_002", trigger_condition="y", action="block", severity="medium", tags=["t"], lifecycle_status="cached")
    eng.add_interception(r1); eng.add_interception(r2)
    active = eng.get_interceptions(active_only=True)
    assert len(active) == 1
    assert active[0].id == "act_001"
    all_rules = eng.get_interceptions(active_only=False)
    assert len(all_rules) == 2
    teardown()
    print("  [PASS] active_only filter")

def test_meta_and_precedent():
    setup()
    eng = RuleEngine(rules_dir=TEST_DIR)
    m = MetaExperience(id="meta_001", insight="test", applicable_contexts=["qa"])
    eng.add_meta(m)
    assert len(eng.get_metas()) == 1
    pr = Precedent(id="pre_001", conflict_rules=["a", "b"], resolution="human_resolved")
    eng.add_precedent(pr)
    assert len(eng.get_precedents()) == 1
    teardown()
    print("  [PASS] meta & precedent")

# ─── Rule Matching ───

def test_retrieve_for_task():
    setup()
    eng = RuleEngine(rules_dir=TEST_DIR)
    r = InterceptionRule(id="match_001", trigger_condition="task_type == 'danger'", action="block", severity="high", tags=["risk_control"])
    eng.add_interception(r)
    p = SuccessPattern(id="pat_match_001", pattern_name="safe", trigger_scenario="qa", decision_logic="allow")
    eng.add_pattern(p)

    result = eng.retrieve_for_task({"task_type": "danger", "channel": "chat"})
    assert "interceptions" in result
    assert "patterns" in result
    assert len(result["interceptions"]) == 1  # match_001 matches 'danger'
    assert result["interceptions"][0].id == "match_001"

    result2 = eng.retrieve_for_task({"task_type": "safe", "channel": "chat"})
    assert len(result2["interceptions"]) == 0
    teardown()
    print("  [PASS] retrieve_for_task")

def test_retrieve_for_task_severity_filter():
    setup()
    eng = RuleEngine(rules_dir=TEST_DIR)
    for s in ["critical", "high", "medium", "low"]:
        eng.add_interception(InterceptionRule(
            id=f"sev_{s}", trigger_condition=f"severity == '{s}'",
            action="block", severity=s, tags=["test"]
        ))
    # Query that triggers all
    ctx = {"severity": "high", "channel": "chat", "task_type": "test"}
    result = eng.retrieve_for_task(ctx)
    # Only the one matching should fire
    assert len(result["interceptions"]) == 1
    assert result["interceptions"][0].id == "sev_high"
    teardown()
    print("  [PASS] retrieve_for_task severity filter")

def test_safe_evaluate_simple():
    setup()
    eng = RuleEngine(rules_dir=TEST_DIR)
    # Test simple boolean expressions via _match_condition
    ctx = {"task_type": "file_write", "channel": "chat", "target": "app.asar"}
    r = InterceptionRule(
        id="safe_001",
        trigger_condition="task_type == 'file_write' AND target == 'app.asar'",
        action="block", severity="high", tags=["test"]
    )
    eng.add_interception(r)
    result = eng.retrieve_for_task(ctx)
    assert len(result["interceptions"]) == 1
    assert result["interceptions"][0].id == "safe_001"
    teardown()
    print("  [PASS] safe_evaluate simple AND")

# ─── Seed Rules ───

def test_seed_interceptions():
    seeds = get_seed_interceptions()
    assert len(seeds) > 0
    # Seeds should have valid fields
    for s in seeds:
        assert s.id
        assert s.trigger_condition
        assert s.action
        assert s.severity in ("critical", "high", "medium", "low")
    print(f"  [PASS] get_seed_interceptions ({len(seeds)} seeds)")

def test_init_rules_if_empty():
    setup()
    eng = RuleEngine(rules_dir=TEST_DIR)
    assert len(eng.get_interceptions(active_only=False)) == 0
    init_rules_if_empty(eng)
    assert len(eng.get_interceptions(active_only=False)) > 0
    # Second call should not duplicate
    count_before = len(eng.get_interceptions(active_only=False))
    init_rules_if_empty(eng)
    count_after = len(eng.get_interceptions(active_only=False))
    assert count_before == count_after
    teardown()
    print("  [PASS] init_rules_if_empty idempotent")

def test_persistence():
    setup()
    eng = RuleEngine(rules_dir=TEST_DIR)
    r = InterceptionRule(id="persist_001", trigger_condition="x > 1", action="block", severity="high", tags=["test"])
    eng.add_interception(r)
    # Create new engine reading same dir
    eng2 = RuleEngine(rules_dir=TEST_DIR)
    assert eng2.get_interception_by_id("persist_001") is not None
    teardown()
    print("  [PASS] persistence across engine instances")

if __name__ == "__main__":
    print("=== evo.rule_engine Test Suite ===\n")
    tests = [
        test_interception_rule_defaults,
        test_success_pattern_defaults,
        test_meta_experience,
        test_precedent,
        test_engine_init,
        test_add_interception,
        test_add_interception_auto_id,
        test_get_interception_by_id,
        test_update_interception,
        test_delete_interception,
        test_add_pattern,
        test_pattern_crud,
        test_active_only_filter,
        test_meta_and_precedent,
        test_retrieve_for_task,
        test_retrieve_for_task_severity_filter,
        test_safe_evaluate_simple,
        test_seed_interceptions,
        test_init_rules_if_empty,
        test_persistence,
    ]
    passed = 0
    for t in tests:
        try:
            t()
            passed += 1
        except Exception as e:
            import traceback
            print(f"  [FAIL] {t.__name__}: {e}")
            traceback.print_exc()
    total = len(tests)
    print(f"\n=== {passed}/{total} tests passed ===")
