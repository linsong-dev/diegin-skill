"""一二不过三·警觉落动作闭环（定稿第三章）：alerting 规则不阻断，
在预策 P4 权衡阶段对相关攻七模式置信度 -0.2，且 reason 必须携带「警觉落动作」标记（AI 可见）。
覆盖：不阻断 / 相关落动作 / 不相关不动 / 落动作翻转裁决 / 跨轮状态隔离。
"""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "engine"))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "engine", "evo"))

from evo.arbiter import ConflictArbiter, ResolutionType
from evo.rule_engine import RuleEngine, InterceptionRule, SuccessPattern


def _make_arb(tmp_path):
    eng = RuleEngine(rules_dir=str(tmp_path / "rules"))
    return ConflictArbiter(eng)


def _alert_rule(rid="alert_img_url", cond="image_url in cmd"):
    return InterceptionRule(
        id=rid, trigger_condition=cond, action="log", severity="low",
        tags=["一二不过三"], lifecycle_status="alerting", confidence=4.0,
    )


def _guard_rule(rid="guard_img", conf=3.8):
    return InterceptionRule(
        id=rid, trigger_condition="image_url in cmd", action="report",
        severity="low", tags=["守三"], lifecycle_status="active", confidence=conf,
    )


def _pattern(rid="pat_img", conf=4.0, scenario="image_url 修复"):
    return SuccessPattern(
        id=rid, pattern_name=rid, trigger_scenario=scenario,
        trigger_condition="image_url", decision_logic="修复 image_url 引用",
        confidence=conf, lifecycle_status="active",
    )


def test_alerting_rule_not_blocking(tmp_path):
    """alerting 规则不触发阻断（P1 只阻断 blocking/critical；无 active 拦截 → 放行）。"""
    arb = _make_arb(tmp_path)
    result = arb.resolve([_alert_rule()], [])
    assert result.decision == ResolutionType.ALLOW


def test_vigilance_related_applies(tmp_path):
    """相关 alerting 规则 → 模式置信度 -0.2，reason 携带「警觉落动作」（AI 可见）。"""
    arb = _make_arb(tmp_path)
    result = arb.resolve([_guard_rule(conf=4.0), _alert_rule()], [_pattern(conf=4.4)])
    # pat 4.4-0.2=4.2 vs 守三 4.0 → delta 0.2 → ESCALATE
    assert result.decision == ResolutionType.ESCALATE
    assert "警觉落动作" in result.reason
    assert "-0.2" in result.reason


def test_vigilance_unrelated_no_change(tmp_path):
    """不相关 alerting 规则（无共享关键词）→ 不扣置信度，reason 无警觉标记。"""
    arb = _make_arb(tmp_path)
    unrelated = _alert_rule(rid="alert_disk_io", cond="disk full")
    result = arb.resolve([_guard_rule(conf=4.0), unrelated], [_pattern(conf=4.4)])
    assert result.decision == ResolutionType.ESCALATE
    assert "警觉落动作" not in result.reason


def test_vigilance_flips_decision_to_block(tmp_path):
    """落动作真实改变裁决：无 alerting → ESCALATE；有相关 alerting → pat 降至持平 → 守三负向纠错 BLOCK。"""
    arb = _make_arb(tmp_path)
    pat = _pattern(conf=4.0)
    guard = _guard_rule(conf=3.8)

    plain = arb.resolve([guard], [pat])
    assert plain.decision == ResolutionType.ESCALATE  # delta 0.2 需确认
    assert "警觉落动作" not in plain.reason

    arb2 = _make_arb(tmp_path)
    vigil = arb2.resolve([guard, _alert_rule()], [pat])  # pat 4.0-0.2=3.8 → delta 0
    assert vigil.decision == ResolutionType.BLOCK
    assert "警觉落动作" in vigil.reason
    assert "-0.2" in vigil.reason


def test_alerting_state_reset_between_resolve(tmp_path):
    """跨轮隔离：同实例第二次 resolve 无 alerting 规则 → 不留存上轮落动作状态。"""
    arb = _make_arb(tmp_path)
    pat = _pattern(conf=4.0)
    guard = _guard_rule(conf=3.8)

    first = arb.resolve([guard, _alert_rule()], [pat])
    assert "警觉落动作" in first.reason

    second = arb.resolve([guard], [pat])
    assert "警觉落动作" not in second.reason
    assert second.decision == ResolutionType.ESCALATE  # 回到无落动作行为
