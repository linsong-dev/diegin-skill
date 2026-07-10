"""Tests for evo.arbiter"""
import os, sys, tempfile, shutil
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "engine"))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "engine", "evo"))
from evo.arbiter import ConflictArbiter, ResolutionType, ArbitrationResult
from evo.rule_engine import RuleEngine, InterceptionRule, SuccessPattern

TEST_DIR = os.path.join(os.path.dirname(__file__), "_test_rules_arb")

def setup():
    if os.path.exists(TEST_DIR):
        shutil.rmtree(TEST_DIR)
    os.makedirs(TEST_DIR, exist_ok=True)

def teardown():
    if os.path.exists(TEST_DIR):
        shutil.rmtree(TEST_DIR)

def _make_eng():
    setup()
    return RuleEngine(rules_dir=TEST_DIR)

# ─── ResolutionType Enum ───

def test_resolution_type_values():
    assert ResolutionType.IRON_WALL_BLOCK.value == "iron_wall_block"
    assert ResolutionType.BLOCK.value == "block"
    assert ResolutionType.ESCALATE.value == "escalate"
    assert ResolutionType.ALLOW.value == "allow"
    assert ResolutionType.CONFIDENCE_WIN.value == "confidence_win"
    assert ResolutionType.HUMAN_REQUIRED.value == "human_required"
    assert ResolutionType.AUTO_DEGRADED.value == "auto_degraded"
    print("  [PASS] ResolutionType values")

# ─── to_display mapping ───

def test_to_display_allow():
    eng = _make_eng()
    arb = ConflictArbiter(eng)
    result = ArbitrationResult(decision=ResolutionType.ALLOW, reason="no issues")
    display = arb.to_display(result)
    assert display["decision"] == "allow"
    assert "[DGEN] ✅ 通过" in display["display_line"]
    teardown()
    print("  [PASS] to_display ALLOW")

def test_to_display_block():
    eng = _make_eng()
    arb = ConflictArbiter(eng)
    r = InterceptionRule(id="test_rule", trigger_condition="x > 5", action="block", severity="high", tags=["test"])
    result = ArbitrationResult(decision=ResolutionType.BLOCK, winning_rule=r, reason="danger")
    display = arb.to_display(result)
    assert display["decision"] == "block"
    assert "🛑" in display["display_line"]
    assert display["winning_rule_id"] == "test_rule"
    teardown()
    print("  [PASS] to_display BLOCK")

def test_to_display_iron_wall():
    eng = _make_eng()
    arb = ConflictArbiter(eng)
    result = ArbitrationResult(decision=ResolutionType.IRON_WALL_BLOCK, reason="critical")
    display = arb.to_display(result)
    assert display["decision"] == "iron_wall_block"
    assert "铁律" in display["display_line"] or "iron_wall" in display["display_line"]
    teardown()
    print("  [PASS] to_display IRON_WALL_BLOCK")

def test_to_display_escalate():
    eng = _make_eng()
    arb = ConflictArbiter(eng)
    result = ArbitrationResult(decision=ResolutionType.ESCALATE, reason="ambiguous")
    display = arb.to_display(result)
    assert display["decision"] == "escalate"
    teardown()
    print("  [PASS] to_display ESCALATE")

def test_to_display_internal_mapping():
    eng = _make_eng()
    arb = ConflictArbiter(eng)
    r1 = arb.to_display(ArbitrationResult(decision=ResolutionType.CONFIDENCE_WIN))
    assert r1["decision"] == "allow"
    r2 = arb.to_display(ArbitrationResult(decision=ResolutionType.HUMAN_REQUIRED))
    assert r2["decision"] == "escalate"
    r3 = arb.to_display(ArbitrationResult(decision=ResolutionType.AUTO_DEGRADED))
    assert r3["decision"] == "block"
    teardown()
    print("  [PASS] to_display internal type mapping")

# ─── Core resolve logic (aligned with actual code behavior) ───

def test_resolve_no_rules():
    eng = _make_eng()
    arb = ConflictArbiter(eng)
    result = arb.resolve([], [])
    assert result.decision == ResolutionType.ALLOW
    assert result.reason == "无规则触发或全部放行"
    teardown()
    print("  [PASS] resolve no rules → ALLOW")

def test_resolve_iron_wall_irreversible():
    """IRON_WALL_BLOCK requires severity high/critical + 'irreversible' tag"""
    eng = _make_eng()
    arb = ConflictArbiter(eng)
    r = InterceptionRule(id="wall_001", trigger_condition="danger", action="block",
                         severity="high", tags=["irreversible"])
    result = arb.resolve([r], [])
    assert result.decision == ResolutionType.IRON_WALL_BLOCK
    teardown()
    print("  [PASS] resolve high+irreversible → IRON_WALL_BLOCK")

def test_resolve_critical_block():
    """critical without irreversible → BLOCK (not iron wall)"""
    eng = _make_eng()
    arb = ConflictArbiter(eng)
    r = InterceptionRule(id="crit_001", trigger_condition="danger", action="block",
                         severity="critical", tags=["risk"])
    result = arb.resolve([r], [])
    assert result.decision == ResolutionType.BLOCK
    assert "critical" in result.reason
    teardown()
    print("  [PASS] resolve critical → BLOCK")

def test_resolve_high_block():
    eng = _make_eng()
    arb = ConflictArbiter(eng)
    r = InterceptionRule(id="high_001", trigger_condition="risky", action="block",
                         severity="high", tags=["risk"])
    result = arb.resolve([r], [])
    assert result.decision == ResolutionType.BLOCK
    teardown()
    print("  [PASS] resolve high → BLOCK")

def test_resolve_medium_escalate():
    eng = _make_eng()
    arb = ConflictArbiter(eng)
    r = InterceptionRule(id="med_001", trigger_condition="maybe", action="ask",
                         severity="medium", tags=["check"])
    result = arb.resolve([r], [])
    assert result.decision == ResolutionType.ESCALATE
    teardown()
    print("  [PASS] resolve medium → ESCALATE")

def test_resolve_low_allow():
    eng = _make_eng()
    arb = ConflictArbiter(eng)
    r = InterceptionRule(id="low_001", trigger_condition="trivial", action="log",
                         severity="low", tags=["info"])
    result = arb.resolve([r], [])
    assert result.decision == ResolutionType.ALLOW
    teardown()
    print("  [PASS] resolve low → ALLOW")

def test_resolve_severity_priority_highest_wins():
    eng = _make_eng()
    arb = ConflictArbiter(eng)
    med = InterceptionRule(id="med_001", trigger_condition="medium", action="ask",
                           severity="medium", tags=["t"])
    high = InterceptionRule(id="high_001", trigger_condition="high", action="block",
                            severity="high", tags=["t"])
    # High should win over medium
    result = arb.resolve([med, high], [])
    assert result.decision == ResolutionType.BLOCK
    assert result.winning_rule.id == "high_001"
    teardown()
    print("  [PASS] resolve severity priority (high > medium)")

def test_resolve_critical_over_high():
    """critical severity wins over high"""
    eng = _make_eng()
    arb = ConflictArbiter(eng)
    high_r = InterceptionRule(id="high_001", trigger_condition="high", action="block",
                              severity="high", tags=["t"])
    crit_r = InterceptionRule(id="crit_001", trigger_condition="critical", action="block",
                              severity="critical", tags=["t"])
    result = arb.resolve([high_r, crit_r], [])
    assert result.decision == ResolutionType.BLOCK
    assert result.winning_rule.id == "crit_001"
    teardown()
    print("  [PASS] resolve critical over high")

def test_resolve_high_interception_overrides_pattern_conflict():
    """High-severity interception → BLOCK before Layer 3 (conflict detection)"""
    eng = _make_eng()
    arb = ConflictArbiter(eng)
    r = InterceptionRule(id="int_001", trigger_condition="x", action="block",
                         severity="high", tags=["t"], confidence=4.0)
    p = SuccessPattern(id="pat_001", pattern_name="safe", trigger_scenario="qa",
                       decision_logic="allow", confidence=4.2)
    # Layer 2 (high→BLOCK) triggers before Layer 3
    result = arb.resolve([r], [p])
    assert result.decision == ResolutionType.BLOCK
    teardown()
    print("  [PASS] high interception > pattern (Layer 2 preempts Layer 3)")

def test_resolve_low_interception_with_pattern_goes_to_layer2():
    """Low severity interceptions → ESCALATE when pattern conflict (Layer 3)"""
    eng = _make_eng()
    arb = ConflictArbiter(eng)
    r = InterceptionRule(id="low_001", trigger_condition="x", action="log",
                         severity="low", tags=["t"], confidence=4.0)
    p = SuccessPattern(id="pat_001", pattern_name="safe", trigger_scenario="qa",
                       decision_logic="allow", confidence=4.2)
    result = arb.resolve([r], [p])
    # Layer 3 now reachable: low(4.0) + pattern(4.2), delta=0.2 < 0.5 → ESCALATE
    assert result.decision == ResolutionType.ESCALATE
    teardown()
    print("  [PASS] low interception → ESCALATE (Layer 3 conflict detection)")

def test_resolve_patterns_only():
    """Only patterns (no interceptions) → ALLOW"""
    eng = _make_eng()
    arb = ConflictArbiter(eng)
    p = SuccessPattern(id="pat_001", pattern_name="safe", trigger_scenario="qa",
                       decision_logic="allow")
    result = arb.resolve([], [p])
    assert result.decision == ResolutionType.ALLOW
    teardown()
    print("  [PASS] patterns only → ALLOW")
def test_degradation_queue_full():
    """Direct _check_degradation test"""
    eng = _make_eng()
    arb = ConflictArbiter(eng, max_queue_size=2)
    # Manually add pending conflicts to trigger degradation
    arb.pending_conflicts = [
        {"timestamp": 0, "interception": None, "pattern": None, "delta": 0, "resolved": False},
        {"timestamp": 0, "interception": None, "pattern": None, "delta": 0, "resolved": False},
        {"timestamp": 0, "interception": None, "pattern": None, "delta": 0, "resolved": False},
    ]
    degraded = arb._check_degradation()
    assert degraded is not None
    assert degraded.decision == ResolutionType.AUTO_DEGRADED
    teardown()
    print("  [PASS] _check_degradation queue full")

def test_degradation_timeout():
    eng = _make_eng()
    arb = ConflictArbiter(eng, timeout_minutes=0)  # 0 minutes = immediate timeout
    arb.pending_conflicts = [{"timestamp": 0, "interception": None, "pattern": None, "delta": 0, "resolved": False}]
    degraded = arb._check_degradation()
    assert degraded is not None
    assert degraded.decision == ResolutionType.AUTO_DEGRADED
    teardown()
    print("  [PASS] _check_degradation timeout")

def test_degradation_no_trigger():
    eng = _make_eng()
    arb = ConflictArbiter(eng, max_queue_size=5)
    result = arb._check_degradation()
    assert result is None
    teardown()
    print("  [PASS] _check_degradation no trigger (empty queue)")

# ─── Human Resolve ───

def test_human_resolve_valid():
    eng = _make_eng()
    arb = ConflictArbiter(eng)
    r = InterceptionRule(id="int_001", trigger_condition="x", action="block",
                         severity="high", tags=["t"])
    arb.pending_conflicts.append({"resolved": False})
    result = arb.human_resolve(0, r)
    assert result.decision == ResolutionType.ALLOW
    teardown()
    print("  [PASS] human_resolve valid index")

def test_human_resolve_invalid():
    eng = _make_eng()
    arb = ConflictArbiter(eng)
    result = arb.human_resolve(99, None)
    assert result.decision == ResolutionType.ESCALATE
    teardown()
    print("  [PASS] human_resolve invalid index")

# ─── Edge Cases ───

def test_resolve_multiple_rules_same_severity():
    eng = _make_eng()
    arb = ConflictArbiter(eng)
    r1 = InterceptionRule(id="high_a", trigger_condition="a", action="block",
                          severity="high", tags=["t"])
    r2 = InterceptionRule(id="high_b", trigger_condition="b", action="block",
                          severity="high", tags=["t"])
    result = arb.resolve([r1, r2], [])
    assert result.decision == ResolutionType.BLOCK
    assert result.winning_rule.id == "high_a"  # first high rule wins
    teardown()
    print("  [PASS] resolve multiple rules same severity")

if __name__ == "__main__":
    print("=== evo.arbiter Test Suite (aligned) ===\n")
    tests = [
        test_resolution_type_values,
        test_to_display_allow,
        test_to_display_block,
        test_to_display_iron_wall,
        test_to_display_escalate,
        test_to_display_internal_mapping,
        test_resolve_no_rules,
        test_resolve_iron_wall_irreversible,
        test_resolve_critical_block,
        test_resolve_high_block,
        test_resolve_medium_escalate,
        test_resolve_low_allow,
        test_resolve_severity_priority_highest_wins,
        test_resolve_critical_over_high,
        test_resolve_high_interception_overrides_pattern_conflict,
        test_resolve_low_interception_with_pattern_goes_to_layer2,
        test_resolve_patterns_only,
        test_degradation_queue_full,
        test_degradation_timeout,
        test_degradation_no_trigger,
        test_human_resolve_valid,
        test_human_resolve_invalid,
        test_resolve_multiple_rules_same_severity,
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
