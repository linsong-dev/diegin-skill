# ============================================
# 迭进(Diegin) 核心引擎 - 泛化模块
# 举一反三: generalize_cross_domain / generalize_from_patterns / generalize_rule
# ============================================

import os
import sys
import json
import datetime
from pathlib import Path
from typing import Dict, List, Any, Optional

# ------------------------------------------------------------
# 泛化状态跟踪
# ------------------------------------------------------------
_last_generalization_check = None

# ------------------------------------------------------------
# generalize_cross_domain: 跨域泛化
# 将一个领域的 domain_rule 自适应到其他领域
# ------------------------------------------------------------
def generalize_cross_domain() -> list:
    import json
    from evo.main import _get_engine
    from rule_engine import InterceptionRule
    import datetime as dt
    domain_dir = os.path.join(os.path.dirname(__file__), "rules", "domain_rules")
    if not os.path.exists(domain_dir):
        return []
    domain_files = [f for f in os.listdir(domain_dir) if f.endswith(".json") and f != ".gitkeep" and not f.startswith("session")]
    if not domain_files:
        return []
    all_domains = {}
    for df in domain_files:
        dpath = os.path.join(domain_dir, df)
        with open(dpath, "r", encoding="utf-8") as f:
            try:
                rules = json.load(f)
                if isinstance(rules, list):
                    all_domains[df.replace(".json", "")] = rules
            except Exception:
                pass
    if len(all_domains) < 2:
        return []
    domain_names = list(all_domains.keys())
    engine = _get_engine()
    created = []
    for src_name in domain_names:
        src_rules = all_domains[src_name]
        for src_rule in src_rules:
            name = src_rule.get("name", "")
            desc = src_rule.get("description", "")
            for tgt_name in domain_names:
                if tgt_name == src_name:
                    continue
                tgt_label = tgt_name.replace("domain_", "").replace("_", " ")
                adapted_desc = desc.replace("code", tgt_label).replace("data", tgt_label).replace("writing", tgt_label)
                if adapted_desc == desc:
                    adapted_desc = tgt_label + ": " + desc
                rid = "xdomain_" + src_name.replace("domain_", "") + "_to_" + tgt_name.replace("domain_", "") + "_" + src_rule.get("id", name)[:20]
                existing = engine.get_interception_by_id(rid)
                if existing:
                    continue
                trig = "domain == " + repr(tgt_name.replace("domain_", ""))
                new_rule = InterceptionRule(
                    id=rid,
                    trigger_condition=trig,
                    action="suggest_cross_domain; " + adapted_desc[:80],
                    severity="low",
                    tags=["attack", "举一反三", "cross_domain", tgt_name],
                    logic_score=3.0, outcome_score=3.0, confidence=3.0,
                    source="learned",
                    source_review="generalize_cross_domain: " + src_name + " -> " + tgt_name,
                    lifecycle_status="staging",
                    created_at=dt.datetime.now().isoformat(),
                    valid_until="", last_triggered="",
                    boundary_conditions=[adapted_desc],
                    invalid_conditions=[], triggered_count=0, ignored_count=0, override_count=0,
                    last_ignored="", block_count=0, blocked_rules=[]
                )
                engine.add_interception(new_rule)
                created.append(rid)
    if created:
        engine.save_all()
    return created

# ------------------------------------------------------------
# generalize_from_patterns: 从成功模式泛化为拦截规则
# ------------------------------------------------------------
def generalize_from_patterns() -> list:
    from evo.main import _get_engine
    from rule_engine import InterceptionRule, SuccessPattern
    import datetime as dt
    engine = _get_engine()
    patterns = engine.get_patterns(active_only=True)
    created = []
    for p in patterns:
        tc = getattr(p, "triggered_count", 0) or 0
        conf = getattr(p, "confidence", 0) or 0
        os_val = getattr(p, "outcome_score", 0) or 0
        if tc < 3 and conf < 3.0 and os_val < 3.0:
            continue
        cond = getattr(p, "trigger_condition", "") or p.trigger_scenario
        rid = "pat_rule_" + p.id
        existing = engine.get_interception_by_id(rid)
        if existing:
            continue
        new_rule = InterceptionRule(
            id=rid,
            trigger_condition=cond,
            action="suggest_from_pattern; " + (p.decision_logic[:60] if hasattr(p, "decision_logic") else ""),
            severity="low" if conf < 4.0 else "medium",
            tags=["attack", "举一反三", "from_pattern"],
            logic_score=conf, outcome_score=os_val, confidence=conf,
            source="learned",
            source_review="generalize_from_patterns: " + p.id,
            lifecycle_status="staging",
            created_at=dt.datetime.now().isoformat(),
            valid_until="", last_triggered="",
            boundary_conditions=[p.micro_template if hasattr(p, "micro_template") else ""],
            invalid_conditions=[], triggered_count=0, ignored_count=0, override_count=0,
            last_ignored="", block_count=0, blocked_rules=[]
        )
        engine.add_interception(new_rule)
        created.append(rid)
        engine.update_pattern(p.id, auto_promoted=True, promoted_from="generalize", promoted_at=dt.datetime.now().isoformat())
    if created:
        engine.save_all()
    return created

# ------------------------------------------------------------
# generalize_rule: 从单条规则推导跨场景通用候选规则
# ------------------------------------------------------------
def generalize_rule(new_rule_id: str = None) -> list:
    global _last_generalization_check
    try:
        from evo.main import _get_engine
        from rule_engine import InterceptionRule
        engine = _get_engine()
        all_rules = engine.get_interceptions(active_only=False)
        if not all_rules:
            _last_generalization_check = {"time": "", "candidates": [], "groups": {}}
            return []
        groups = {}
        cat_map = {}
        for r in all_rules:
            rid = getattr(r, "id", "") or ""
            sev = getattr(r, "severity", "medium") or "medium"
            trig = getattr(r, "trigger_condition", "") or ""
            act = getattr(r, "action", "") or ""
            tags = getattr(r, "tags", []) or []
            if "self_error" in tags or "一二不过三" in tags:
                cat = "self_healing"
            elif "irreversible" in tags or "risk_control" in tags:
                cat = "risk_security"
            elif "filesystem" in tags or "io" in tags or "encoding" in tags:
                cat = "io_filesystem"
            elif "toolchain" in tags or "execution" in tags or "shell" in tags or "powershell" in tags:
                cat = "toolchain"
            elif "marker" in tags or "decision_enforcement" in tags or "routing_coverage" in tags or "marker_enforcement" in tags:
                cat = "marker_coverage"
            elif "safety_valve" in tags or "loop" in tags:
                cat = "loop_protection"
            elif "context_guard" in tags or "interruption" in tags or "subagent" in tags:
                cat = "context_guard"
            elif "communication" in tags or "logic" in tags or "task_management" in tags:
                cat = "communication_logic"
            elif "safety" in tags or "quality" in tags or "delivery" in tags:
                cat = "quality_delivery"
            elif "system_safety" in tags:
                cat = "system_safety"
            else:
                cat = "general"
            key = f"{sev}/{cat}"
            if key not in groups:
                groups[key] = []
            groups[key].append((rid, sev, trig, act))
            cat_map[rid] = cat
        all_cats = set()
        for key in groups:
            _, cat = key.split("/", 1)
            all_cats.add(cat)
        all_sevs = {"critical", "high", "medium", "low"}
        candidates = []
        for cat in all_cats:
            cat_sevs = set()
            for key in groups:
                k_sev, k_cat = key.split("/", 1)
                if k_cat == cat:
                    cat_sevs.add(k_sev)
            missing = all_sevs - cat_sevs
            if missing:
                template_rule = None
                template_cat = None
                for key in groups:
                    k_sev, k_cat = key.split("/", 1)
                    if k_sev in missing and k_cat != cat:
                        template_rule = groups[key][0]
                        template_cat = k_cat
                        break
                if template_rule:
                    rid, sev, trig, act = template_rule
                    candidates.append({
                        "type": "severity_gap",
                        "source": rid,
                        "source_cat": template_cat,
                        "target_cat": cat,
                        "missing_severity": list(missing),
                        "suggested_condition": trig.replace(template_cat, cat) if template_cat in trig else f"{cat}_related_issue",
                        "action": "review_and_adapt",
                        "reason": f"类别 [{cat}] 缺少 {list(missing)} 严重度规则, 参考 [{template_cat}]"
                    })
        # Strategy B: 单规则泛化 (when new_rule_id is provided)
        if new_rule_id:
            src_rule = engine.get_interception_by_id(new_rule_id)
            if src_rule:
                src_cat = cat_map.get(new_rule_id, "general")
                src_sev = getattr(src_rule, "severity", "medium") or "medium"
                src_trig = getattr(src_rule, "trigger_condition", "") or ""
                src_act = getattr(src_rule, "action", "") or ""
                for tgt_cat in sorted(all_cats):
                    if tgt_cat == src_cat:
                        continue
                    adapted_trig = src_trig.replace(src_cat, tgt_cat) if src_cat in src_trig else src_trig
                    adapted_act = src_act.replace(src_cat, tgt_cat) if src_cat in src_act else src_act
                    if adapted_trig == src_trig and adapted_act == src_act:
                        adapted_trig = f"{tgt_cat}_related_issue"
                    candidates.append({
                        "type": "single_rule_generalize",
                        "source": new_rule_id,
                        "source_cat": src_cat,
                        "target_cat": tgt_cat,
                        "missing_severity": [src_sev],
                        "suggested_condition": adapted_trig,
                        "action": adapted_act,
                        "reason": f"从 [{src_cat}] 推广到 [{tgt_cat}]"
                    })
        _last_generalization_check = {
            "time": datetime.datetime.now().isoformat(),
            "candidates": candidates,
            "groups": {k: len(v) for k, v in groups.items()}
        }
        return candidates
    except Exception as e:
        _last_generalization_check = {"time": "", "candidates": [], "groups": {}, "error": str(e)}
        return []

# ------------------------------------------------------------
# get_generalization_status: 获取泛化状态
# ------------------------------------------------------------
def get_generalization_status() -> dict:
    global _last_generalization_check
    return _last_generalization_check or {"time": "", "candidates": [], "groups": {}}

# ------------------------------------------------------------
# quad_health: 象限健康检查
# ------------------------------------------------------------
def quad_health() -> dict:
    from evo.main import _get_engine
    engine = _get_engine()
    rules = engine.get_interceptions(active_only=False)
    patterns = engine.get_patterns(active_only=False)
    active_rules = [r for r in rules if getattr(r, "lifecycle_status", "") == "active"]
    deprecating = [r for r in rules if getattr(r, "lifecycle_status", "") == "deprecating"]
    archived = [r for r in rules if getattr(r, "lifecycle_status", "") == "archived"]
    staging = [r for r in rules if getattr(r, "lifecycle_status", "") == "staging"]
    return {
        "principle": "举一反三 · 象限健康度",
        "total_rules": len(rules),
        "total_patterns": len(patterns),
        "active_rules": len(active_rules),
        "deprecating": len(deprecating),
        "archived": len(archived),
        "staging": len(staging),
        "cross_domain_rules": sum(1 for r in rules if "xdomain_" in getattr(r, "id", "")),
        "pattern_rules": sum(1 for r in rules if "pat_rule_" in getattr(r, "id", "")),
    }
