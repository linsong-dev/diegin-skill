"""一二不过三·警觉窗口（定稿第三章）：第 1 次 strike → alerting 警觉规则（不阻断，
仲裁 P4 对相关攻七模式置信度 -0.2）；第 2 次起才升级为 active 阻断规则。
load_principle_rules 通过 monkeypatch 隔离引擎与 strikes_db。
"""
import json
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "engine"))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "engine", "evo"))

import call_diegin
from evo.rule_engine import RuleEngine, InterceptionRule
from evo.arbiter import ConflictArbiter, ResolutionType


class _FakeTracker:
    def __init__(self, strikes_path):
        self._p = strikes_path

    def _strikes_db_path(self):
        return self._p


def _setup_env(tmp_path, strikes, monkeypatch):
    rules_dir = tmp_path / "rules"
    rules_dir.mkdir(exist_ok=True)
    eng = RuleEngine(rules_dir=str(rules_dir))
    sf = tmp_path / "strikes_db.json"
    sf.write_text(json.dumps(strikes, ensure_ascii=False), encoding="utf-8")
    monkeypatch.setattr(call_diegin, "_get_engine", lambda: eng)
    monkeypatch.setattr(call_diegin, "_get_tracker", lambda: _FakeTracker(str(sf)))
    return eng


def test_count1_builds_alerting_rule(tmp_path, monkeypatch):
    eng = _setup_env(tmp_path, {"img_err": {"count": 1, "first_seen": "2026-08-13"}}, monkeypatch)
    extra = call_diegin.load_principle_rules({"error_type": "img_err"})
    alert = [r for r in extra if r.id == "self_error_img_err"]
    assert len(alert) == 1
    r = alert[0]
    assert r.lifecycle_status == "alerting"
    assert r.severity == "low"
    assert "alert" in r.action
    assert r.triggered_count == 1


def test_count2_builds_active_block_rule(tmp_path, monkeypatch):
    _setup_env(tmp_path, {"img_err": {"count": 2, "first_seen": "2026-08-13"}}, monkeypatch)
    extra = call_diegin.load_principle_rules({"error_type": "img_err"})
    blk = [r for r in extra if r.id == "self_error_img_err"]
    assert len(blk) == 1
    r = blk[0]
    assert r.lifecycle_status == "active"
    assert r.action == "block_operation"
    assert r.severity == "high"
    assert r.triggered_count == 2


def test_count0_skipped(tmp_path, monkeypatch):
    _setup_env(tmp_path, {"img_err": {"count": 0}}, monkeypatch)
    extra = call_diegin.load_principle_rules({"error_type": "img_err"})
    assert not any(getattr(r, "id", "") == "self_error_img_err" for r in extra)


def test_alerting_rule_not_blocking_in_arbitration(tmp_path, monkeypatch):
    eng = _setup_env(tmp_path, {"img_err": {"count": 1}}, monkeypatch)
    extra = call_diegin.load_principle_rules({"error_type": "img_err"})
    alert = [r for r in extra if r.id == "self_error_img_err"]
    arb = ConflictArbiter(eng)
    result = arb.resolve(alert, [])
    assert result.decision == ResolutionType.ALLOW  # 警觉不阻断


def test_alerting_window_vigilance_delta(tmp_path, monkeypatch):
    """警觉窗口端到端：count==1 alerting 规则 + 守三规则 + 相关攻七模式 → 落动作 -0.2。"""
    eng = _setup_env(tmp_path, {"img_err": {"count": 1}}, monkeypatch)
    extra = call_diegin.load_principle_rules({"error_type": "img_err"})
    alert = [r for r in extra if r.id == "self_error_img_err"][0]
    guard = InterceptionRule(
        id="guard_img", trigger_condition="image_url in cmd", action="report",
        severity="low", tags=["守三"], lifecycle_status="active", confidence=3.8,
    )
    from evo.rule_engine import SuccessPattern
    pat = SuccessPattern(
        id="pat_img", pattern_name="pat_img", trigger_scenario="img_err 修复",
        trigger_condition="img_err", decision_logic="修复 img_err", confidence=4.0,
    )
    arb = ConflictArbiter(eng)
    result = arb.resolve([guard, alert], [pat])
    # pat 4.0-0.2=3.8 → 与守三持平 → 守三负向纠错 BLOCK + 警觉标记
    assert result.decision == ResolutionType.BLOCK
    assert "警觉落动作" in result.reason
