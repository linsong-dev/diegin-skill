"""攻七推荐正式回归集（训练/测试分离，借鉴 Penguin GDPevo 防偷看答案）

回归集 JSON: regression/gongqi_recommend_cases.json
- train_snapshot: 真实规则库历史沉淀基线（随规则库演进人工更新，不硬断言）
- test_cases: 固定种子模式 + 输入上下文 -> 期望推荐（硬断言，不随真实规则库漂移）

防泄漏约束：每个用例注入独立临时规则目录的种子模式，只读调用
build_gongqi_suggestions / retrieve_for_task，绝不触碰真实规则库与 Mindol；
测试用例不进入引擎学习路径（不 record_triggered / 不 auto_adopt / 不写回）。
"""
import os
import sys
import json
import tempfile
import shutil

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "engine"))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "engine", "evo"))

from evo.rule_engine import RuleEngine, SuccessPattern, build_gongqi_suggestions

_CASES = os.path.join(os.path.dirname(__file__), "regression", "gongqi_recommend_cases.json")
_REG = json.load(open(_CASES, encoding="utf-8"))


def _make_seed_patterns(seeds):
    pats = []
    for s in seeds:
        pats.append(SuccessPattern(
            id=s["id"],
            pattern_name=s.get("pattern_name", s["id"]),
            trigger_scenario=s.get("trigger_scenario", ""),
            decision_logic=s.get("decision_logic", ""),
            trigger_condition=s.get("trigger_condition", ""),
            confidence=s.get("confidence", 5.0),
            source="regression_seed",
        ))
    return pats


def _collect_case(case):
    """隔离执行单个用例：临时引擎 + 种子模式注入 -> matched + suggestions"""
    tmp = tempfile.mkdtemp(prefix="dgen_gongqi_reg_")
    try:
        eng = RuleEngine(rules_dir=tmp)
        for p in _make_seed_patterns(case["seed_patterns"]):
            eng.add_pattern(p)
        ret = eng.retrieve_for_task(dict(case["context"]))
        matched = ret.get("patterns", [])
        suggestions = build_gongqi_suggestions(matched)
        return matched, suggestions
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def test_regression_meta():
    assert "train_snapshot" in _REG
    assert "test_cases" in _REG
    assert len(_REG["test_cases"]) >= 7
    print("  [PASS] 回归集 meta: %d test cases" % len(_REG["test_cases"]))


def test_all_test_cases():
    failures = []
    for case in _REG["test_cases"]:
        matched, suggestions = _collect_case(case)
        exp = case["expect"]
        try:
            # matched_count
            if "matched_count" in exp:
                assert len(matched) == exp["matched_count"], (
                    f"matched_count {len(matched)} != {exp['matched_count']}")
            # suggestions_empty
            if exp.get("suggestions_empty"):
                assert len(suggestions) == 0, f"期望空推荐, 实际 {len(suggestions)}"
                continue
            # first_id / first_priority
            if "first_id" in exp:
                assert suggestions and suggestions[0]["id"] == exp["first_id"], (
                    f"first_id {suggestions[0]['id'] if suggestions else None} != {exp['first_id']}")
            if "first_priority" in exp:
                assert suggestions and suggestions[0]["priority"] is exp["first_priority"], (
                    f"first_priority {suggestions[0]['priority'] if suggestions else None} != {exp['first_priority']}")
            # order
            if "order" in exp:
                ids = [s["id"] for s in suggestions]
                assert ids[:len(exp["order"])] == exp["order"], f"order {ids} != {exp['order']}"
            # all_priority
            if exp.get("all_priority"):
                assert all(s["priority"] for s in suggestions), f"存在非 priority: {suggestions}"
            # suggestion_count
            if "suggestion_count" in exp:
                assert len(suggestions) == exp["suggestion_count"], (
                    f"suggestion_count {len(suggestions)} != {exp['suggestion_count']}")
            # noise_not_priority：噪音模式存在时 priority 必须为 False
            for nid in exp.get("noise_not_priority", []):
                for s in suggestions:
                    if s["id"] == nid:
                        assert s["priority"] is False, f"噪音模式 {nid} 不应 priority"
            print(f"  [PASS] {case['id']}")
        except AssertionError as e:
            failures.append((case["id"], str(e)))
            print(f"  [FAIL] {case['id']}: {e}")
    assert not failures, f"{len(failures)} 个用例失败"
