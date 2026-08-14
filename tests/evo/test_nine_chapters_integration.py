# -*- coding: utf-8 -*-
"""九章联动集成测试（L2 关联章联动联测，2026-08-14 决策落地）
按定稿关联路径构造场景链，验证章间数据流真实贯通：
  1攻七→4举一反三→6预策 / 2守三→3一二不过三 /
  7恒常门→8止观→9自照镜 / 5去伪存真证据支撑
第3章章级入口：无错误时空转 + 3次错误完整升级三步。
"""
import json
import os
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "engine"))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "engine", "evo"))

import evo.main as main
from evo import constancy, closure, self_mirror, evidence_vault
from evo.tracker import BehaviorTracker
from evo.rule_engine import RuleEngine, InterceptionRule, SuccessPattern
from evo.arbiter import ConflictArbiter
from evo.evidence_vault import EvidenceVault


@pytest.fixture()
def nine_env(tmp_path, monkeypatch):
    """九章联动环境：全部状态路径隔离到临时目录 + 单例重置 + 共享引擎/tracker"""
    base = str(tmp_path)
    # 恒常门
    monkeypatch.setattr(constancy, "_get_tasks_path", lambda: os.path.join(base, "constancy_tasks.json"))
    monkeypatch.setattr(constancy, "_inst", None)
    monkeypatch.setattr(main, "_get_constancy_inst", constancy.get_constancy)
    # 止观门
    monkeypatch.setattr(closure, "_get_closure_dir", lambda: base)
    monkeypatch.setattr(closure, "_inst", None)
    monkeypatch.setattr(main, "_get_closure_inst", closure.get_closure)
    # 自照镜
    monkeypatch.setattr(self_mirror, "_get_state_path", lambda: os.path.join(base, "self_mirror.json"))
    # 规则引擎（共享）
    eng = RuleEngine(rules_dir=os.path.join(base, "rules"))
    monkeypatch.setattr(main, "_get_engine", lambda: eng)
    monkeypatch.setattr(main, "_arbiter", None)
    # tracker（共享引擎）
    tr = BehaviorTracker(eng)
    monkeypatch.setattr(tr, "_strikes_db_path", lambda: os.path.join(base, "strikes_db.json"))
    monkeypatch.setattr(main, "_get_tracker", lambda: tr)
    # 证据库
    vault = EvidenceVault()
    vault._log_path = os.path.join(base, "evidence_trail.json")
    vault._trail = []
    monkeypatch.setattr(main, "_get_vault_inst", lambda: vault)
    return {"eng": eng, "tracker": tr, "vault": vault, "base": base}


# ───────────── 关联链 1：1攻七 → 4举一反三 → 6预策 ─────────────

def test_chain_gongqi_generalize_arbitrate(nine_env):
    eng = nine_env["eng"]
    # 攻七：成功模式入库（复用≥2次触发泛化条件）
    eng.add_pattern(SuccessPattern(
        id="pat_chain_1", pattern_name="先测后改", trigger_scenario="修改迭进引擎代码",
        decision_logic="修改后立即做回归验证与引擎自检，全绿再回灌", confidence=5.0,
        triggered_count=3, source="learned"))
    # 举一反三：从成功模式泛化 → staging 规则
    created = main.generalize_from_patterns()
    assert "pat_rule_pat_chain_1" in created
    staging = [r for r in eng.get_interceptions(active_only=False)
               if getattr(r, "lifecycle_status", "") == "staging"]
    assert any(r.id == "pat_rule_pat_chain_1" for r in staging)
    # 预策：裁决含 staging 规则（P5 不参与实时仲裁）+ active 规则（P4 裁决）
    eng.add_interception(InterceptionRule(
        id="chain_guard_1", trigger_condition="cmd contains apply_patch", action="block",
        severity="medium", tags=["risk_control"], confidence=6.0))
    r = main.arbitrate(eng.get_interceptions(active_only=True), eng.get_patterns(active_only=True))
    assert r.get("decision") in ("allow", "block", "suggest")
    assert isinstance(r.get("reason", ""), str)


# ───────────── 关联链 2：2守三 → 3一二不过三（升级三步）─────────────

def test_chain_strike_to_three_strikes_escalation(nine_env):
    tr = nine_env["tracker"]
    # 守三：3 次同类错误 → 一二不过三升级三步
    for _ in range(3):
        tr.record_self_error("chain_escalation_error", "测试错误详情")
    db = tr._load_strikes_db()
    assert db["chain_escalation_error"]["count"] == 3
    # 升级三步①：fatal 永久记录
    fatal = tr._load_json_safe(tr._fatal_errors_path(), {})
    assert "chain_escalation_error" in fatal
    assert fatal["chain_escalation_error"].get("permanent") is True
    # 升级三步③：人工介入 + 24h 截止
    esc = tr._load_json_safe(tr._human_escalation_path(), {})
    assert "chain_escalation_error" in esc
    assert esc["chain_escalation_error"].get("status") == "awaiting_human"
    # 第3章章级入口：达到3次后不再累加（封顶）
    r = tr.record_self_error("chain_escalation_error", "再犯一次")
    assert r.get("action") == "capped_at_3"


def test_chapter3_entry_no_error_noop(nine_env):
    """第3章章级入口：无错误 → 不触发任何升级（今日运行时 0 触发的正常语义）"""
    tr = nine_env["tracker"]
    fatal = tr._load_json_safe(tr._fatal_errors_path(), {})
    esc = tr._load_json_safe(tr._human_escalation_path(), {})
    assert fatal == {} and esc == {}


def test_chapter3_entry_three_strikes_escalate(nine_env):
    """第3章章级入口：3 次错误完整升级三步（①fatal ②人工介入 ③锁止可查）"""
    tr = nine_env["tracker"]
    for _ in range(3):
        tr.record_self_error("chapter3_entry_err", "详情")
    fatal = tr._load_json_safe(tr._fatal_errors_path(), {})
    esc = tr._load_json_safe(tr._human_escalation_path(), {})
    assert fatal["chapter3_entry_err"].get("permanent") is True
    assert esc["chapter3_entry_err"].get("status") == "awaiting_human"
    assert "静默锁止" in esc["chapter3_entry_err"].get("escalation_report", "")


# ───────────── 关联链 3：7恒常门 → 8止观 → 9自照镜 ─────────────

def test_chain_constancy_closure_mirror(nine_env):
    # 恒常门：任务落库
    r = main.constancy_track_prompt("实现九章联动测试任务并整理归档")
    assert r["ok"] is True and r["action"] == "begin"
    task_id = r["task_id"]
    # 恒常门：可恢复检查
    rec = main.constancy_recoverable()
    assert rec and rec[0]["task_id"] == task_id
    # 止观：封存任务 + 只读快照（定稿第八章）
    snap = {"block_records": ["block: x exit=1"], "tool_call_sequence": ["Bash: apply_patch"],
            "arbitration_log": "exit=0 decision=allow"}
    item = closure.get_closure().close(task_id, summary="联动测试完成",
                                       intent_summary="实现九章联动测试任务并整理归档",
                                       snapshot=snap)
    assert item["readonly_snapshot"]["tool_call_sequence"] == ["Bash: apply_patch"]
    assert closure.get_closure().is_closed(task_id)
    # 自照镜：报告读取恒常门完成率/中断率 + 止观封存数（章间数据流）
    m = self_mirror.SelfMirror()
    report = m.generate_report()
    assert report["止观"]["封存轮次数"] >= 1
    assert report["持存"]["总任务数"] >= 1


def test_chain_constancy_suspend_resume(nine_env):
    """恒常门→预策 P3：任务挂起 → 恢复优先分流"""
    r = main.constancy_track_prompt("推进九章联动场景链A")
    task_id = r["task_id"]
    main.constancy_suspend(task_id, reason="切换到任务B")
    assert main.constancy_recoverable()[0]["task_id"] == task_id
    assert main.constancy_resume(task_id) is True


# ───────────── 关联链 4：5去伪存真 证据支撑 staging ─────────────

def test_chain_evidence_supports_staging(nine_env):
    eng = nine_env["eng"]
    vault = nine_env["vault"]
    # 举一反三：生成 staging 规则
    eng.add_pattern(SuccessPattern(
        id="pat_chain_ev", pattern_name="证据支撑模式", trigger_scenario="去伪存真验证",
        decision_logic="证据链完备后转正式生效", confidence=5.0, triggered_count=2))
    main.generalize_from_patterns()
    staging = [r for r in eng.get_interceptions(active_only=False)
               if getattr(r, "lifecycle_status", "") == "staging"]
    assert any(r.id == "pat_rule_pat_chain_ev" for r in staging), "泛化未生成 pat_rule_pat_chain_ev"
    rid = "pat_rule_pat_chain_ev"
    # 去伪存真：记录支撑证据（pass 引用真实规则 → 验证门通过；
    # 泛化规则按谱系距离衰减，支撑度<0.5 可降级为 pending 暂存——定稿第五章真实行为）
    r = vault.record(rid, "pass", "已通过回归验证且证据链完备", source="test_chain")
    assert r.get("verdict") in ("pass", "pending")
    recent = vault.get_recent(10)
    assert any(x.get("rule_id") == rid for x in recent)


# ───────────── 全链：九章闭环 ─────────────

def test_full_nine_chapter_chain(nine_env):
    """一条场景链打通九章：攻七学→守三纠→一二不过三锁→举一反三泛→
    去伪存真验→预策裁→恒常门续→止观封→自照镜审"""
    eng, tr, vault = nine_env["eng"], nine_env["tracker"], nine_env["vault"]
    # 1攻七：成功模式
    eng.add_pattern(SuccessPattern(
        id="pat_full", pattern_name="全链成功模式", trigger_scenario="九章闭环",
        decision_logic="按迭进修改循环执行并回归验证", confidence=5.0, triggered_count=3))
    # 2守三 + 3一二不过三：错误与升级
    tr.record_self_error("full_chain_err", "链路错误")
    tr.record_self_error("full_chain_err", "链路错误2")
    tr.record_self_error("full_chain_err", "链路错误3")
    assert tr._load_strikes_db()["full_chain_err"]["count"] == 3
    assert "full_chain_err" in tr._load_json_safe(tr._fatal_errors_path(), {})
    # 4举一反三：泛化 staging（第3次错误已触发守三复盘/攻七强化，staging 池含多个候选）
    main.generalize_from_patterns()
    staging_rules = [r for r in eng.get_interceptions(active_only=False)
                     if getattr(r, "lifecycle_status", "") == "staging"]
    assert len(staging_rules) >= 1
    assert any(r.id.startswith("pat_rule_pat_full") for r in staging_rules)
    # 5去伪存真：证据（记录到已存在的 staging 规则）
    rid = staging_rules[0].id
    vault.record(rid, "pass", "全链验证通过，证据完备", source="test_full")
    assert vault.get_recent(10)
    # 6预策：裁决
    eng.add_interception(InterceptionRule(
        id="full_guard", trigger_condition="cmd contains rm", action="block",
        severity="high", tags=["risk_control"], confidence=7.0))
    arb = main.arbitrate(eng.get_interceptions(active_only=True), eng.get_patterns(active_only=True))
    assert arb.get("decision") in ("allow", "block", "suggest")
    # 7恒常门：任务生命周期
    r7 = main.constancy_track_prompt("九章全链闭环验证")
    task_id = r7["task_id"]
    assert main.constancy_recoverable()
    # 8止观：封存
    closure.get_closure().close(task_id, summary="全链完成", snapshot={"tool_call_sequence": ["Bash: test"]})
    assert closure.get_closure().is_closed(task_id)
    # 9自照镜：报告含多章统计
    report = self_mirror.SelfMirror().generate_report()
    assert report["止观"]["封存轮次数"] >= 1
    assert report["持存"]["总任务数"] >= 1
    assert report["一二不过三"]["累计触发次数"] >= 3
    assert report["举一反三"]["staging池大小"] >= 1
    assert report["攻七"]["入库模式数"] >= 1
