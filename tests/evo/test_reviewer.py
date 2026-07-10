"""Tests for evo.reviewer"""
import os, sys, shutil
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "engine"))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "engine", "evo"))
from reviewer import ReviewSignal, ReviewResult, Reviewer, ROIReviewer
from rule_engine import RuleEngine, InterceptionRule, SuccessPattern
TEST_DIR = os.path.join(os.path.dirname(__file__), "_test_review")
def setup():
    if os.path.exists(TEST_DIR): shutil.rmtree(TEST_DIR)
    os.makedirs(TEST_DIR, exist_ok=True)
def teardown():
    if os.path.exists(TEST_DIR): shutil.rmtree(TEST_DIR)
def _make_reviewer():
    setup(); eng = RuleEngine(rules_dir=TEST_DIR)
    return Reviewer(eng), eng
def test_review_signal():
    s = ReviewSignal(description="test", type="positive")
    assert s.type == "positive"
    print("  [PASS] ReviewSignal")
def test_review_result():
    r = ReviewResult([],[],[],[],[],[],[])
    assert r.positive_signals == []
    print("  [PASS] ReviewResult")
def test_reviewer_init():
    rev, eng = _make_reviewer()
    assert rev.rule_engine is not None
    teardown(); print("  [PASS] Reviewer init")
def test_assess_luck_none():
    rev, eng = _make_reviewer()
    assert rev._assess_luck("data") == "low"
    teardown(); print("  [PASS] _assess_luck none")
def test_assess_luck_one():
    rev, eng = _make_reviewer()
    kw = rev.luck_keywords[0]
    assert rev._assess_luck(kw) == "medium"
    teardown(); print("  [PASS] _assess_luck one kw")
def test_assess_luck_two():
    rev, eng = _make_reviewer()
    kws = rev.luck_keywords[:2]
    assert rev._assess_luck(kws[0]+kws[1]) == "high"
    teardown(); print("  [PASS] _assess_luck two kw")
def test_assess_emotion_none():
    rev, eng = _make_reviewer()
    assert rev._assess_emotion("logic") == "low"
    teardown(); print("  [PASS] _assess_emotion none")
def test_assess_emotion_one():
    rev, eng = _make_reviewer()
    kw = rev.emotion_keywords[0]
    assert rev._assess_emotion(kw) == "medium"
    teardown(); print("  [PASS] _assess_emotion one kw")
def test_full_review_empty():
    rev, eng = _make_reviewer()
    r = rev.full_review({"task_type":"test"},{"status":"ok"})
    assert isinstance(r, ReviewResult)
    teardown(); print("  [PASS] full_review empty")
def test_full_review_with_rules():
    rev, eng = _make_reviewer()
    eng.add_interception(InterceptionRule(id="r1",trigger_condition="x",action="block",severity="high",tags=["t"]))
    eng.add_pattern(SuccessPattern(id="p1",pattern_name="safe",trigger_scenario="qa",decision_logic="allow"))
    r = rev.full_review({"task_type":"code"},{"status":"ok"})
    assert isinstance(r, ReviewResult)
    teardown(); print("  [PASS] full_review with rules")
def test_roi_get_tier():
    assert ROIReviewer.get_tier("x") == "medium"
    print("  [PASS] ROIReviewer.get_tier")
def test_roi_get_review_prompt():
    p = ROIReviewer.get_review_prompt("full")
    assert "三明治" in p.get("description","")
    print("  [PASS] ROIReviewer.get_review_prompt")
if __name__ == "__main__":
    print("=== evo.reviewer Test Suite ===\n")
    tests = [test_review_signal,test_review_result,test_reviewer_init,test_assess_luck_none,test_assess_luck_one,test_assess_luck_two,test_assess_emotion_none,test_assess_emotion_one,test_full_review_empty,test_full_review_with_rules,test_roi_get_tier,test_roi_get_review_prompt]
    passed=0
    for t in tests:
        try: t(); passed+=1
        except Exception as e:
            import traceback; print(f"  [FAIL] {t.__name__}: {e}"); traceback.print_exc()
    print(f"\n=== {passed}/{len(tests)} tests passed ===")