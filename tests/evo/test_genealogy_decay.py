"""去伪存真·谱系距离衰减（定稿第五章）+ 守三·快照时间戳衰减（定稿第二章）
2026-08-13 完整终版细则
"""
import os
import sys
import tempfile
import datetime

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "engine"))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "engine", "evo"))

from evo.evidence_vault import EvidenceVault
from evo.tracker import snapshot_age_days, snapshot_age_decay
from evo.rule_engine import RuleEngine, InterceptionRule


def _make_vault():
    ev = EvidenceVault.__new__(EvidenceVault)
    ev._log_path = os.path.join(tempfile.mkdtemp(), "evidence_trail.json")
    ev._trail = []
    ev._attribution_log = []
    ev._attribution_max = 200
    return ev


def _make_engine(tmp_path):
    return RuleEngine(rules_dir=str(tmp_path / "rules"))


def _rule(rid, source_review="", **kw):
    return InterceptionRule(id=rid, trigger_condition="x", action="log", severity="low",
                            tags=["test"], source_review=source_review, **kw)


# ─── 谱系距离深度 ───

def test_depth_0_seed_rule(tmp_path):
    eng = _make_engine(tmp_path)
    eng.add_interception(_rule("seed_a"))
    ev = _make_vault()
    assert ev.generalization_depth("seed_a", engine=eng) == 0


def test_depth_1_generalized(tmp_path):
    eng = _make_engine(tmp_path)
    eng.add_interception(_rule("pat_rule_pat_x", "generalize_from_patterns: pat_x"))
    ev = _make_vault()
    assert ev.generalization_depth("pat_rule_pat_x", engine=eng) == 1


def test_depth_1_xdomain(tmp_path):
    eng = _make_engine(tmp_path)
    eng.add_interception(_rule("xdomain_merged_a_b", "跨域: 从 domain_a 泛化到 2 个领域"))
    ev = _make_vault()
    assert ev.generalization_depth("xdomain_merged_a_b", engine=eng) == 1


def test_depth_2_source_generalized(tmp_path):
    """二级泛化：pat_x 本身是泛化产物（source_review 含 generalize）→ pat_rule_pat_x 为 2 级"""
    eng = _make_engine(tmp_path)
    eng.add_interception(_rule("pat_x", "generalize_from_patterns: pat_y"))
    eng.add_interception(_rule("pat_rule_pat_x", "generalize_from_patterns: pat_x"))
    ev = _make_vault()
    assert ev.generalization_depth("pat_rule_pat_x", engine=eng) == 2


# ─── 谱系衰减支撑度 ───

def test_verify_non_generalized_pass_stays(tmp_path):
    eng = _make_engine(tmp_path)
    eng.add_interception(_rule("seed_a"))
    ev = _make_vault()
    assert ev.verify_with_genealogy("seed_a", "pass", engine=eng) == "pass"


def test_verify_generalized_no_history_pending(tmp_path):
    """泛化规则首次验证无历史对比证据 → 支撑度不足 → 暂存"""
    eng = _make_engine(tmp_path)
    eng.add_interception(_rule("pat_rule_pat_x", "generalize_from_patterns: pat_x"))
    ev = _make_vault()
    assert ev.verify_with_genealogy("pat_rule_pat_x", "pass", engine=eng) == "pending"


def test_verify_generalized_support_below_half(tmp_path):
    """1 级衰减 ×0.8：历史 1 pass 1 fail → 0.8/2=0.4 <0.5 → 暂存"""
    eng = _make_engine(tmp_path)
    eng.add_interception(_rule("pat_rule_pat_x", "generalize_from_patterns: pat_x"))
    ev = _make_vault()
    ev._trail = [
        {"rule_id": "pat_rule_pat_x", "verdict": "pass", "ts": "t1"},
        {"rule_id": "pat_rule_pat_x", "verdict": "fail", "ts": "t2"},
    ]
    assert ev.verify_with_genealogy("pat_rule_pat_x", "pass", engine=eng) == "pending"


def test_verify_generalized_support_above_half(tmp_path):
    """1 级衰减 ×0.8：历史 2 pass 1 fail → 1.6/3≈0.53 ≥0.5 → pass"""
    eng = _make_engine(tmp_path)
    eng.add_interception(_rule("pat_rule_pat_x", "generalize_from_patterns: pat_x"))
    ev = _make_vault()
    ev._trail = [
        {"rule_id": "pat_rule_pat_x", "verdict": "pass", "ts": "t1"},
        {"rule_id": "pat_rule_pat_x", "verdict": "pass", "ts": "t2"},
        {"rule_id": "pat_rule_pat_x", "verdict": "fail", "ts": "t3"},
    ]
    assert ev.verify_with_genealogy("pat_rule_pat_x", "pass", engine=eng) == "pass"


def test_verify_second_level_decay(tmp_path):
    """2 级衰减 ×0.64：1 pass 1 fail → 0.64/2=0.32 <0.5 → 暂存"""
    eng = _make_engine(tmp_path)
    eng.add_interception(_rule("pat_x", "generalize_from_patterns: pat_y"))
    eng.add_interception(_rule("pat_rule_pat_x", "generalize_from_patterns: pat_x"))
    ev = _make_vault()
    ev._trail = [
        {"rule_id": "pat_rule_pat_x", "verdict": "pass", "ts": "t1"},
        {"rule_id": "pat_rule_pat_x", "verdict": "fail", "ts": "t2"},
    ]
    assert ev.verify_with_genealogy("pat_rule_pat_x", "pass", engine=eng) == "pending"


def test_record_generalized_pass_downgraded_to_pending(tmp_path, monkeypatch):
    """record() 接入：泛化规则 pass 验证被降级为 pending（进入暂存区）"""
    eng = _make_engine(tmp_path)
    eng.add_interception(_rule("pat_rule_pat_x", "generalize_from_patterns: pat_x"))
    ev = _make_vault()
    monkeypatch.setattr("evo.evidence_vault.EvidenceVault._is_valid_evidence",
                        lambda self, *a, **k: True)
    monkeypatch.setattr("evo.evidence_vault.EvidenceVault.generalization_depth",
                        lambda self, rid, engine=None: 1)
    r = ev.record("pat_rule_pat_x", "pass", "泛化规则验证通过但证据权重衰减", "test")
    assert r.get("verdict") == "pending"
    assert r.get("stage") == "staging"


# ─── 守三快照时间戳衰减 ───

def test_snapshot_age_decay_grace(tmp_path):
    assert snapshot_age_decay(0) == 1.0
    assert snapshot_age_decay(7) == 1.0


def test_snapshot_age_decay_after_grace(tmp_path):
    assert abs(snapshot_age_decay(8) - 0.95) < 1e-6
    assert abs(snapshot_age_decay(9) - 0.9025) < 1e-6
    assert abs(snapshot_age_decay(12) - round(0.95 ** 5, 4)) < 1e-6


def test_snapshot_age_days_parse(tmp_path):
    d = (datetime.datetime.now() - datetime.timedelta(days=10)).isoformat()
    assert snapshot_age_days(d) == 10
    assert snapshot_age_days("invalid") == 0
    assert snapshot_age_days("") == 0
