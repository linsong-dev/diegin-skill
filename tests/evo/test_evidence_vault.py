"""Tests for evo.evidence_vault 证据有效性门（v3.8.1）"""
import os, sys, tempfile
from unittest.mock import patch

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "engine"))
from evo.evidence_vault import EvidenceVault


def _make_vault():
    ev = EvidenceVault.__new__(EvidenceVault)  # 绕过 __init__ 的固定日志路径
    ev._log_path = os.path.join(tempfile.mkdtemp(), "evidence_trail.json")
    ev._trail = []
    ev._attribution_log = []
    ev._attribution_max = 200
    return ev


def test_reject_shell_empty_pass():
    """post_tool 空壳 pass（rule_id=工具名 + tool=xxx exit=）必须被拒绝"""
    ev = _make_vault()
    r = ev.record("Bash", "pass", "tool=Bash exit=", "post_tool")
    assert r.get("rejected") is True
    assert len(ev._trail) == 0


def test_reject_toolname_pass():
    """工具名 rule_id + 空壳 reason → 拒绝"""
    ev = _make_vault()
    r = ev.record("update_plan", "pass", "tool=update_plan exit=0", "post_tool")
    assert r.get("rejected") is True
    assert len(ev._trail) == 0


def test_reject_blank_reason():
    ev = _make_vault()
    r = ev.record("rule_x", "pass", "   ", "post_tool")
    assert r.get("rejected") is True


def test_accept_fail():
    """真实失败必须保留（即使 rule_id 是工具名）"""
    ev = _make_vault()
    r = ev.record("Bash", "fail", "exit=1 command failed", "post_tool")
    assert r.get("rejected") is None
    assert len(ev._trail) == 1


def test_accept_quarterly():
    """内置季度证伪审计放行"""
    ev = _make_vault()
    r = ev.record("_quarterly_falsification", "pass", "季度证伪: 扫描1条无重复", "quarterly_falsification")
    assert r.get("rejected") is None
    assert len(ev._trail) == 1


def test_accept_real_rule_pass():
    """真实规则 id + 实质 reason → 放行"""
    class FakeEngine:
        def get_interception_by_id(self, rid):
            return object() if rid == "rule_x" else None
        def get_pattern_by_id(self, rid):
            return None
    ev = _make_vault()
    with patch("evo.main._get_engine", return_value=FakeEngine()):
        r = ev.record("rule_x", "pass", "规则验证通过且记录实质内容", "post_tool")
    assert r.get("rejected") is None
    assert len(ev._trail) == 1


def test_accept_skip_audit():
    """evidence_filter 审计 skip 记录放行（有实质 reason）"""
    ev = _make_vault()
    r = ev.record("rule_staging_x", "skip", "staging规则证据不足(触发=0,置信度=4.1)", "evidence_filter")
    assert r.get("rejected") is None
    assert len(ev._trail) == 1

def test_staging_ttl_expires():
    """定稿第五章：暂存 7 天超时自动淘汰（50轮/7天先到者）"""
    import datetime
    ev = _make_vault()
    ev._is_valid_evidence = lambda *a, **k: True
    old = (datetime.datetime.now() - datetime.timedelta(days=8)).isoformat()
    ev._trail.append({"rule_id": "r1", "verdict": "pending", "ts": old,
                      "staging_created_at": old, "staging_round": 1,
                      "reset_count": 0, "expired": False})
    n = ev.staging_ttl_check()
    assert n == 1
    assert ev._trail[0]["expired"] is True


def test_staging_reset_once():
    """定稿第五章：保留期内新证据重置计时器一次，第二次拒绝"""
    ev = _make_vault()
    ev._is_valid_evidence = lambda *a, **k: True
    ev.record("rx", "pending", "待验证", source="auto")
    assert ev.reset_staging_timer("rx") is True
    assert ev.reset_staging_timer("rx") is False
    p = [e for e in ev._trail if e["rule_id"] == "rx" and e["verdict"] == "pending"][0]
    assert p.get("reset_count") == 1


def test_record_new_evidence_auto_reset():
    """新证据（非 pending 判定）→ record 自动重置暂存计时器"""
    ev = _make_vault()
    ev._is_valid_evidence = lambda *a, **k: True
    ev.record("ry", "pending", "待验证", source="auto")
    ev.record("ry", "pass", "验证通过", source="external")
    p = [e for e in ev._trail if e["rule_id"] == "ry" and e["verdict"] == "pending"][0]
    assert p.get("reset_count") == 1
