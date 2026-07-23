# ============================================
# 迭进路DGEN 核心引擎
# 元原则框架(全域常驻不可绕过):
#   守三(负向纠错): 观不足->省其因->正其行
#   攻七(正向强化): 识长处->炼精华->固其用
#   一二不过三(三错阀): 初错立规->再错固规->三错请裁决
#   举一反三(跨域泛化): 举一->反三->通百
#   去伪存真(真伪门): 言必有证->证必可验->验证为真
# ============================================

#!/usr/bin/env python3


# -*- coding: utf-8 -*-


"""


diegin-evo 统一入口模块


迭进自主生成和维护


"""


import os


import sys


import json


from pathlib import Path


from typing import Dict, List, Any, Optional


sys.path.insert(0, str(Path(__file__).parent))


from rule_engine import (


    RuleEngine,


    InterceptionRule,


    SuccessPattern,


    MetaExperience,


    Precedent,


    get_seed_interceptions,


    init_rules_if_empty


)


from arbiter import ConflictArbiter, ResolutionType, ArbitrationResult


from reviewer import Reviewer, ROIReviewer, ReviewSignal, ReviewResult


from tracker import BehaviorTracker


from war_game import WarGameEngine


from dashboard import HealthDashboard, run_health_check

from pacemaker import PaceMaker, get_pacemaker as _get_pacemaker_inst
from closure import ClosureGate, get_closure as _get_closure_inst
from evidence_vault import EvidenceVault, get_vault as _get_vault_inst


# ============================================================


# Memory V2 适配层（迭进 ↔ 长期记忆）— 替代 MemPalace

# ============================================================

_ENGINE_DIR = str(Path(__file__).parent.parent)  # engine/
if _ENGINE_DIR not in sys.path:
    sys.path.insert(0, _ENGINE_DIR)
from mindol.diegin_integration import (
    memory_search as mempalace_search,
    memory_archive as dgen_archive,
    get_memory_stats,
    close_memory,
    memory_format_context,
)
_MEMPALACE_AVAILABLE = True

#


import datetime


try:

    from error_detector import ErrorDetector, get as get_detector

    _detector = ErrorDetector()


    # 初始化 tracker

    try:

        _tk = None

        _detector._tracker = _tk

    except Exception:

        pass


    _detector_active = True

except Exception:

    _detector = None

    _detector_active = False


# detect_success 全局成功模式检测入口

def detect_failure(ctx: dict) -> dict:

    """

    全局操作失败检测

    检测

    ctx = {

        "op": "file_write" | "cmd" | "git_push",

        "path": "...",           # file path (for file_write)

        "data": b"...",          # written content (for file_write)

        "cmd": "...",            # command (for cmd/git_push)

        "exit": 0,               # exit code

        "out": "...",            # stdout

        "err": "...",            # stderr

        "dur": 1234              # duration ms

    }

    返回检测结果dict

    """

    if not _detector_active or _detector is None:

        return {}

    return _detector.detect_and_record(ctx) or {}


# detect_success 全局成功模式检测入口

_SUCCESS_LOG_FILE = os.path.join(os.path.dirname(os.path.dirname(__file__)), "workspace", "success_log.json")

def _load_success_log():
    try:
        if os.path.exists(_SUCCESS_LOG_FILE):
            with open(_SUCCESS_LOG_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
    except Exception:
        pass
    return []

def _save_success_log(log):
    try:
        os.makedirs(os.path.dirname(_SUCCESS_LOG_FILE), exist_ok=True)
        with open(_SUCCESS_LOG_FILE, "w", encoding="utf-8") as f:
            json.dump(log, f, ensure_ascii=False, indent=2)
    except Exception:
        pass

_success_log = _load_success_log()   # file-backed


def detect_success(ctx: dict) -> dict:

    """检测操作成功并持久化到 success_patterns.json"""

    global _success_log


    if not _detector_active:

        return {}


    score = 0

    reasons = []


    # 时间因素

    dur = ctx.get("duration_ms", 0)

    if dur > 0 and dur < 10000:

        score += 1

        reasons.append("fast")


    # 零重试

    retry = ctx.get("retry_count", 0)

    if retry == 0:

        score += 1

        reasons.append("no_retry")


    # 复杂操作成功

    op = ctx.get("op", "")

    if op in ("git_push", "release", "file_write"):

        if retry == 0 and dur < 60000:

            score += 2

            reasons.append("complex_ops_success")


    if score >= 2:

        entry = {

            "time": datetime.datetime.now().isoformat(),

            "op": op,

            "detail": ctx.get("detail", "")[:80],

            "score": score,

            "reasons": reasons

        }

        _success_log.append(entry)
        _save_success_log(_success_log)


        # 持久化到 success_patterns.json

        if score >= 3:

            try:

                from rule_engine import RuleEngine, SuccessPattern

                import datetime as dt

                engine = _get_engine()

                pattern_id = f"auto_success_{op}_{len(_success_log)}"

                # 检查是否已有同类模式，有则加强置信度

                existing_pattern = engine.get_pattern_by_id(pattern_id)

                if existing_pattern:

                    engine.update_pattern(pattern_id, confidence=min(5.0, existing_pattern.confidence + 0.5),

                                          triggered_count=existing_pattern.triggered_count + 1)

                else:

                    new_pattern = SuccessPattern(

                        id=pattern_id,

                        pattern_name=f"自动提取: {op} 成功模式",

                        trigger_scenario=f"{op} 操作成功",

                        decision_logic=f"op={op} score={score} reasons={','.join(reasons)}",

                        micro_template=f"{op}成功: {','.join(reasons)}",

                        logic_score=4.0,

                        outcome_score=4.0,

                        confidence=min(5.0, score + 1.0),

                        source="auto_detect",

                        lifecycle_status="active",

                        created_at=dt.datetime.now().isoformat(),

                        triggered_count=1

                    )

                    engine.add_pattern(new_pattern)

                engine.save_all()

            except Exception:

                pass


        return {"detected": True, "score": score, "reasons": reasons}


    return {"detected": False}


def ensure_three_strikes(error_type: str, detail: str = "", severity: str = "high") -> dict:

    """

    ??检测

    检测

    由 detect_failure 自动调用


    示例:

        ensure_three_strikes("encoding_write_corruption", "PowerShell写入编码错误")

    """

    if not _detector_active or _detector is None:

        return {}

    return _detector.detect_and_record({

        "op": "file_write",

        "path": "",

        "data": b"",

        "force_error": error_type,

        "force_detail": detail,
        "force_severity": severity

    }) or {}


def get_strike_status(error_type: str = None) -> dict:

    """获取错误触发状态"""

    try:

        try:

            from main import _get_tracker as _gt

            tracker = _gt()

        except:

            tracker = None

        if tracker is None:

            return {"status": "tracker_not_available"}

        if error_type:

            rule = tracker.rule_engine.get_interception_by_id(f"self_error_{error_type}")

            if rule:

                return {

                    "error_type": error_type,

                    "triggered_count": getattr(rule, "triggered_count", 0),

                    "severity": getattr(rule, "severity", "unknown"),

                    "confidence": getattr(rule, "confidence", 0),

                    "lifecycle": getattr(rule, "lifecycle_status", "unknown")

                }

            return {"error_type": error_type, "status": "never_triggered"}

        # ??全局操作失败检测

        rules = tracker.rule_engine.get_interceptions(active_only=False)

        strikes = []

        for r in rules:

            if getattr(r, "triggered_count", 0) > 0:

                strikes.append({

                    "id": getattr(r, "id", ""),

                    "triggered": getattr(r, "triggered_count", 0),

                    "severity": getattr(r, "severity", ""),

                    "lifecycle": getattr(r, "lifecycle_status", "")

                })

        return {"status": "ok", "strike_rules": strikes}

    except Exception as e:

        return {"status": "error", "detail": str(e)}


# [自动修复] 迭进引擎注释

_last_generalization_check = None


def generalize_cross_domain() -> list:
    """举一反三：跨域泛化
    将一个领域的 domain_rule 自适应制其他领域
    例: code_dev的"提交前语法检查" → data_analysis的"提交前格式检查"
    """
    import json
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
            # 对每个目标域生成适配版
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
                import datetime as dt
                from rule_engine import InterceptionRule
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


def generalize_from_patterns() -> list:
    """举一反三：从成功模式泛化为拦截规则
    将 high-confidence success_patterns 转化为 seed 类型的拦截规则
    让 AI 在正确行为被检测到时获得正向引导
    """
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


def generalize_rule(new_rule_id: str = None) -> list:

    """举一反三：从单条规则推导跨场景通用候选规则

    步骤:

    1. 解析源规则的 trigger_condition + action + severity

    2. 判断源规则所属类别

    3. 查找其他类别中是否有同类规则

    4. 为缺失类别生成适配候选规则

    5. 结果写入 _last_generalization_check 供外部读取

    """

    global _last_generalization_check


    try:

        from rule_engine import InterceptionRule

        engine = _get_engine()

        all_rules = engine.get_interceptions(active_only=False)


        if not all_rules:

            _last_generalization_check = {"time": "", "candidates": [], "groups": {}}

            return []


        # Step 1: 分类规则

        groups = {}  # category -> [(rule_id, severity, trigger_condition, action)]

        cat_map = {}  # rule_id -> category


        for r in all_rules:

            rid = getattr(r, 'id', '') or ''

            sev = getattr(r, 'severity', 'medium') or 'medium'

            trig = getattr(r, 'trigger_condition', '') or ''

            act = getattr(r, 'action', '') or ''

            tags = getattr(r, 'tags', []) or []


            # deduce category from tags & id (priority: specific -> general)

            # Check specific tags FIRST, 'global' is too broad

            if 'self_error' in tags or '一二不过三' in tags:

                cat = 'self_healing'

            elif 'irreversible' in tags or 'risk_control' in tags:

                cat = 'risk_security'

            elif 'filesystem' in tags or 'io' in tags or 'encoding' in tags:

                cat = 'io_filesystem'

            elif 'toolchain' in tags or 'execution' in tags or 'shell' in tags or 'powershell' in tags:

                cat = 'toolchain'

            elif 'marker' in tags or 'decision_enforcement' in tags or 'routing_coverage' in tags or 'marker_enforcement' in tags:

                cat = 'marker_coverage'

            elif 'safety_valve' in tags or 'loop' in tags:

                cat = 'loop_protection'

            elif 'context_guard' in tags or 'interruption' in tags or 'subagent' in tags:

                cat = 'context_guard'

            elif 'communication' in tags or 'logic' in tags or 'task_management' in tags:

                cat = 'communication_logic'

            elif 'safety' in tags or 'quality' in tags or 'delivery' in tags:

                cat = 'quality_delivery'

            elif 'system_safety' in tags:

                cat = 'system_safety'

            else:

                cat = 'general'


            key = f"{sev}/{cat}"

            if key not in groups:

                groups[key] = []

            groups[key].append((rid, sev, trig, act))

            cat_map[rid] = cat


        # Step 2: 获取所有类别

        all_cats = set()

        for key in groups:

            _, cat = key.split('/', 1)

            all_cats.add(cat)

        all_sevs = {'critical', 'high', 'medium', 'low'}


        candidates = []


        # Strategy A: 严重度缺失泛化 (existing logic enhanced)

        for cat in all_cats:

            cat_sevs = set()

            for key in groups:

                k_sev, k_cat = key.split('/', 1)

                if k_cat == cat:

                    cat_sevs.add(k_sev)

            missing = all_sevs - cat_sevs

            if missing:

                # Find a similar rule from another category to use as template

                template_rule = None

                template_cat = None

                for key in groups:

                    k_sev, k_cat = key.split('/', 1)

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

                        "reason": f"类别 [{cat}] 缺少 {list(missing)} 严重度规则，建议从 [{template_cat}] 的 {rid} 适配"

                    })


        # Strategy B: 跨类别触发条件泛化

        for cat in all_cats:

            cat_rules = []

            for key in groups:

                k_sev, k_cat = key.split('/', 1)

                if k_cat == cat:

                    cat_rules.extend(groups[key])


            if not cat_rules:

                continue


            # Pick the highest severity rule as the "seed" for this category

            seed = max(cat_rules, key=lambda x: ('critical','high','medium','low').index(x[1]) if x[1] in ('critical','high','medium','low') else 99)

            seed_rid, seed_sev, seed_trig, seed_act = seed


            # Check other categories for similar patterns

            for other_cat in all_cats:

                if other_cat == cat:

                    continue


                # Count how many rules other_cat has at this severity

                other_key = f"{seed_sev}/{other_cat}"

                other_rules_count = len(groups.get(other_key, []))


                if other_rules_count == 0:

                    # This category doesn't have a similar high-severity rule - candidate!

                    candidates.append({

                        "type": "cross_domain_adapt",

                        "source": seed_rid,

                        "source_cat": cat,

                        "target_cat": other_cat,

                        "target_severity": seed_sev,

                        "suggested_condition": f"{other_cat}_related_{seed_trig.split('_')[-1] if '_' in seed_trig else seed_trig[:20]}",

                        "suggested_action": seed_act,

                        "reason": f"[{cat}] 有 {seed_sev} 规则 {seed_rid}，但 [{other_cat}] 无同等级规则，建议适配"

                    })


        # Strategy C: 一二不过三模式泛化

        self_error_rules = [r for r in all_rules if 'self_error' in (getattr(r, 'id', '') or '')]

        if len(self_error_rules) >= 2:

            # Key insight: two+ self-error rules detected → create a general "error pattern detection" rule

            error_types = set()

            for r in self_error_rules:

                rid = getattr(r, 'id', '') or ''

                etype = rid.replace('self_error_', '')

                error_types.add(etype)

            if len(error_types) >= 2:

                candidates.append({

                    "type": "self_healing_generalization",

                    "source": ', '.join([getattr(r, 'id', '') or '' for r in self_error_rules[:3]]),

                    "source_cat": "self_healing",

                    "target_cat": "general",

                    "target_severity": "medium",

                    "suggested_condition": "detected_known_error_pattern",

                    "suggested_action": "auto_apply_一二不过三",

                    "reason": f"已检测到 {len(self_error_rules)} 个自愈规则 ({', '.join(list(error_types)[:3])})，建议创建通用错误模式检测规则"

                })


        # Deduplicate

        seen = set()

        unique_candidates = []

        for c in candidates:

            key = f"{c['type']}|{c.get('target_cat','')}|{c.get('source','')}"

            if key not in seen:

                seen.add(key)

                unique_candidates.append(c)


        _last_generalization_check = {

            "time": __import__('datetime').datetime.now().isoformat(),

            "candidates": unique_candidates,

            "groups": {k: len(v) for k, v in groups.items()},

            "strategies": ["severity_gap", "cross_domain_adapt", "self_healing_generalization"]

        }


        # [规则] 自动泛化规则超过10条critical/high时，清理旧规则
        _auto_written = []
        _high_sev = {"critical", "high"}
        
        # 规则数量达到30条时触发清理
        try:
            old_auto = [r for r in engine.get_interceptions(active_only=False) if r.source == "auto_generalized"]
            if len(old_auto) >= 30:
                old_auto.sort(key=lambda r: getattr(r, "created_at", "") or "")
                to_remove = old_auto[:-20]  # 保留最新20条规则
                for r in to_remove:
                    try:
                        engine.delete_interception(r.id)
                    except Exception:
                        pass
        except Exception:
            pass
        
        for c in unique_candidates:
            if len(_auto_written) >= 10:
                break
            # 清理完成
            sev = c.get("target_severity", None)
            if sev is None and "missing_severity" in c:
                sev_list = c["missing_severity"]
                sev = sev_list[0] if sev_list else "medium"
            if sev is None:
                sev = "medium"
            # ?? critical/high
            if str(sev) not in _high_sev:
                continue
            try:
                from rule_engine import InterceptionRule
                import datetime as dt
                target_cat = c.get("target_cat", "general")
                source_id = c.get("source", "auto")
                rid = f"gen_{source_id[:20]}_{target_cat[:15]}_{dt.datetime.now().strftime('%H%M%S%f')[:10]}"
                existing = engine.get_interception_by_id(rid)
                if not existing:
                    # Determine severity
                    sev = c.get("target_severity", None)
                    if sev is None and "missing_severity" in c:
                        sev_list = c["missing_severity"]
                        sev = sev_list[0] if sev_list else "medium"
                    if sev is None:
                        sev = "medium"
                    # Determine trigger condition
                    trig = c.get("suggested_condition", c.get("source", "auto"))
                    # Determine action
                    act = c.get("suggested_action", "check_and_auto_resolve")
                    new_rule = InterceptionRule(
                        id=rid,
                        trigger_condition=str(trig),
                        action=str(act),
                        severity=str(sev),
                        tags=["auto_generalized", target_cat],
                        logic_score=3.0, outcome_score=3.0, confidence=3.0,
                        source="auto_generalized",
                        lifecycle_status="cached",
                        created_at=dt.datetime.now().isoformat(),
                    )
                    engine.add_interception(new_rule)
                    _auto_written.append(rid)
            except Exception:
                pass

        if _auto_written:
            try:
                engine.save_all()
                _last_generalization_check["auto_written"] = _auto_written
                print(f"[DGEN:AUTO] 自动写入 {len(_auto_written)} 条规则")
            except Exception:
                pass


        return unique_candidates


    except Exception as e:

        return []


def get_generalization_status() -> dict:

    """获取泛化状态"""

    return {

        "last_check": _last_generalization_check,

        "detector_active": _detector_active,

        "success_log_count": len(_success_log)

    }


# [自动修复] 迭进引擎注释

def quad_health() -> dict:

    """四引擎健康度报告"""

    return {

        "detector": {

            "active": _detector_active,

            "detections": len(_detector._log) if _detector and _detector_active else 0

        },

        "success": {

            "logged": len(_success_log)

        },

        "three_strikes": get_strike_status().get("strike_rules", []),

        "generalization": get_generalization_status()

    }

# ============================================================


# 全局单例（懒加载）


# ============================================================


_engine: Optional[RuleEngine] = None


_arbiter: Optional[ConflictArbiter] = None


_reviewer: Optional[Reviewer] = None


_tracker: Optional[BehaviorTracker] = None


_wargame: Optional[WarGameEngine] = None


def _get_engine() -> RuleEngine:


    global _engine


    if _engine is None:


        _engine = RuleEngine()


        init_rules_if_empty(_engine)


    return _engine


def _get_arbiter() -> ConflictArbiter:


    global _arbiter


    if _arbiter is None:


        _arbiter = ConflictArbiter(_get_engine())


    return _arbiter


def _get_reviewer() -> Reviewer:


    global _reviewer


    if _reviewer is None:


        _reviewer = Reviewer(_get_engine())


    return _reviewer


def _get_tracker() -> BehaviorTracker:


    global _tracker


    if _tracker is None:


        _tracker = BehaviorTracker(_get_engine())


    return _tracker


def _get_wargame() -> WarGameEngine:


    global _wargame


    if _wargame is None:


        _wargame = WarGameEngine(_get_engine())


    return _wargame


# ============================================================


# 对外暴露的公共 API


# ============================================================


def get_rules_for_task(task_context: Dict[str, Any]) -> Dict[str, List]:


    """根据任务上下文检索匹配的规则"""


    engine = _get_engine()


    return engine.retrieve_for_task(task_context)


def arbitrate(interceptions: List[InterceptionRule],


              patterns: List[SuccessPattern]) -> Dict[str, Any]:


    """冲突仲裁 — 使用 arbiter.to_display() 对齐 AGENTS.md 裁决格式"""


    import dataclasses


    arbiter_obj = _get_arbiter()


    result = arbiter_obj.resolve(interceptions, patterns)


    display = arbiter_obj.to_display(result)


    response = {


        "decision": display["decision"],


        "display_line": display["display_line"],


        "reason": result.reason,


        "winning_rule": None,


        "winning_rule_id": display.get("winning_rule_id"),


        "conflict_set": []


    }


    if result.winning_rule:


        if hasattr(result.winning_rule, '__dataclass_fields__'):


            response["winning_rule"] = dataclasses.asdict(result.winning_rule)


        else:


            response["winning_rule"] = result.winning_rule


    if result.conflict_set:


        response["conflict_set"] = [


            dataclasses.asdict(r) if hasattr(r, '__dataclass_fields__') else r


            for r in result.conflict_set


        ]


    if result.requires_precedent:


        engine = _get_engine()


        precedent = Precedent(


            id="",


            conflict_rules=[r.id for r in result.conflict_set] if result.conflict_set else [],


            resolution="auto_degraded",


            degradation_reason=result.reason,


            winning_rule=response["winning_rule"].get("id", "") if response["winning_rule"] else "",


            winning_rule_type="interception" if response["winning_rule"] and "severity" in response["winning_rule"] else "success_pattern",


            decision_logic=result.reason


        )


        engine.add_precedent(precedent)


    return response


def full_review(task_context: Dict[str, Any],


                task_result: Dict[str, Any]) -> Dict[str, Any]:


    """执行完整的三明治复盘（自动归档到Memory V2）"""


    reviewer = _get_reviewer()


    result = reviewer.full_review(task_context, task_result)


    # Memory V2 归档：复盘后自动同步


    if _MEMPALACE_AVAILABLE:


        dgen_archive("review", "completed", {


            "task_type": task_context.get("task_type", ""),


            "clean": len(result.clean_signals),


            "filtered": len(result.filtered_signals),


            "fused": len(result.fused_outputs)


        })


    return {


        "clean_signals_count": len(result.clean_signals),


        "filtered_signals_count": len(result.filtered_signals),


        "fused_outputs_count": len(result.fused_outputs),


        "meta_insights_count": len(result.meta_insights),


        "anomalies_count": len(result.anomaly_observations),


        "fused_outputs": result.fused_outputs,


        "filtered_signals": result.filtered_signals


    }


def auto_sandwich(positive: List[str], negative: List[str], task_type: str = "general") -> Dict:


    """


    守三攻七：重要工作后自动复盘


    先负向纠错 → 再正向强化


    """


    from datetime import datetime


    ts = datetime.now().strftime("%Y-%m-%d %H:%M")


    tracker = _get_tracker()


    engine = _get_engine()


    report_lines = [f"# 迭进复盘 | {ts}\n"]


    # 负向纠错（守三）


    report_lines.append("## 守三·纠错\n")


    for i, n in enumerate(negative, 1):


        report_lines.append(f"{i}. {n}\n")


        # 为每个负向点创建或加固拦截规则


        error_key = f"auto_{task_type}_error_{i}"


        result = tracker.record_self_error(


            error_type=f"{task_type}_{i}",


            detail=n,


            task_context={"task_type": task_type}


        )


        if result.get("warning"):


            report_lines.append(f"   ⚠️ {result['warning']}\n")


        if result.get("alert"):


            report_lines.append(f"   🔴 {result['alert']}\n")


    # 正向强化（攻七）


    report_lines.append("\n## 攻七·强化\n")


    for i, p in enumerate(positive, 1):


        report_lines.append(f"{i}. {p}\n")


        # 为每个正向点尝试提炼成功模式


        pat_id = f"pat_auto_{task_type}_{i}"


        existing = engine.get_pattern_by_id(pat_id)


        if existing:


            # 已存在 → 置信度+0.3


            existing.confidence = min(5.0, existing.confidence + 0.3)


            existing.triggered_count += 1


            engine.update_pattern(pat_id,


                confidence=existing.confidence,


                triggered_count=existing.triggered_count)


            report_lines.append(f"   ✅ 已有模式，置信度+0.3 → {existing.confidence}\n")


        else:


            # 新模式


            from rule_engine import SuccessPattern


            new_pat = SuccessPattern(


                id=pat_id,


                pattern_name=f"auto_{task_type}_{i}",


                trigger_scenario=task_type,


                decision_logic=p,


                micro_template=p[:80],


                logic_score=4.0,


                outcome_score=3.5,


                confidence=3.8,


                source="auto_sandwich",


                lifecycle_status="active",


                created_at=datetime.now().isoformat(),


                triggered_count=1


            )


            engine.add_pattern(new_pat)


            report_lines.append(f"   ✅ 已创建新模式, conf=3.8\n")


    engine.save_all()


    report = "".join(report_lines)


    # 归档到Memory V2


    if _MEMPALACE_AVAILABLE:


        dgen_archive(f"[迭进] {task_type}", report, "auto_review")


    return {


        "task_type": task_type,


        "negative_count": len(negative),


        "positive_count": len(positive),


        "report": report


    }


def record_user_feedback(rule_id: str, feedback: str, user_action: str = None) -> Dict[str, Any]:


    """


    用户反馈三态模型


    feedback: 'agree' | 'veto' | 'silent'


    user_action: None | 'consistent' | 'inconsistent'


    """


    tracker = _get_tracker()


    result = tracker.record_user_feedback(rule_id, feedback, user_action)


    if _MEMPALACE_AVAILABLE and result.get("action") not in ("not_found",):


        dgen_archive(rule_id, f"user_feedback_{feedback}_{result.get('action', 'unknown')}", {})


    return result


def record_behavior(rule_id: str, action: str) -> Dict[str, Any]:


    """记录对规则的隐性行为（触发/无视/覆盖）自动归档到Memory V2"""


    tracker = _get_tracker()


    if action == "ignored":


        result = tracker.record_ignore(rule_id)


    elif action == "override":


        result = tracker.record_override(rule_id)


    elif action == "triggered":


        result = tracker.record_triggered(rule_id)


    else:


        return {"action": "unknown", "error": f"不支持的操作: {action}"}


    # Memory V2 归档


    if _MEMPALACE_AVAILABLE:


        dgen_archive(rule_id, action, {})


    return result


def run_war_game(portfolio: Dict, macro_data: Dict) -> List[Dict]:


    """运行沙盘推演"""


    wargame = _get_wargame()


    return wargame.run_scenarios(portfolio, macro_data)


def health_check(verbose: bool = True) -> Dict[str, Any]:


    """运行健康度检查"""


    engine = _get_engine()


    return run_health_check(engine)


def run_maintenance():


    """执行定期维护（降权/归档/软淘汰）"""


    engine = _get_engine()


    tracker = _get_tracker()


    print("[TOOL] 开始执行定期维护...")


    ignored_rules = tracker.get_ignored_rules(threshold=0.8)


    for item in ignored_rules:


        rule_id = item["id"]


        tracker.record_ignore(rule_id)


        print(f"  [DOWN] 软淘汰: {rule_id} (无视率 {item['ignore_rate']:.1%})")


    for pattern in engine.get_patterns(active_only=False):


        if pattern.lifecycle_status == "cached" and pattern.valid_until:


            from datetime import datetime


            if datetime.now().isoformat() > pattern.valid_until:


                engine.update_pattern(pattern.id, lifecycle_status="archived")


                print(f"  [ARCHIVE] 归档过期缓存: {pattern.id}")

    # 4.3 生命周期管理: cached 规则超期自动归档
    try:
        _cfg_path = os.path.join(os.path.dirname(__file__), '..', 'config', 'config.toml')
        _max_age_days = 30
        if os.path.isfile(_cfg_path):
            import tomllib
            with open(_cfg_path, 'rb') as _f:
                _cfg = tomllib.load(_f)
            _max_age_days = _cfg.get('maintenance', {}).get('cached_max_age_days', 30)
    except Exception:
        _max_age_days = 30
    _now_dt = datetime.now()
    for rule in engine.get_interceptions(active_only=False):
        if rule.lifecycle_status != 'cached':
            continue
        if rule.valid_until:
            try:
                if _now_dt > datetime.fromisoformat(rule.valid_until):
                    engine.update_interception(rule.id, lifecycle_status='archived')
                    print(f"  [ARCHIVE] cached 规则过期: {rule.id} (valid_until={rule.valid_until})")
                    continue
            except Exception:
                pass
        if rule.last_triggered:
            try:
                _age = (_now_dt - datetime.fromisoformat(rule.last_triggered)).days
                if _age >= _max_age_days:
                    engine.update_interception(rule.id, lifecycle_status='archived')
                    print(f"  [ARCHIVE] cached 规则未触发 {_age}天: {rule.id}")
            except Exception:
                pass
        if not rule.last_triggered and rule.created_at:
            try:
                _age = (_now_dt - datetime.fromisoformat(rule.created_at)).days
                if _age >= _max_age_days:
                    engine.update_interception(rule.id, lifecycle_status='archived')
                    print(f"  [ARCHIVE] cached 规则从未触发 {_age}天: {rule.id}")
            except Exception:
                pass

    for rule in engine.get_interceptions(active_only=True):


        if rule.confidence < 2.0:


            engine.update_interception(rule.id, lifecycle_status="deprecating")


            print(f"  [DOWN] 降权: {rule.id} (置信度 {rule.confidence:.2f})")


    # P1 #1: 规则半衰期(简化版)
    try:
        _max_age = _max_age_days  # 从配置读取（30天）
        _now_dt = datetime.now()
        _dep_count = 0
        _arc_count = 0
        for rule in engine.get_interceptions(active_only=True):
            # 规则已活跃但从未触发 → 降权
            if not rule.last_triggered and rule.created_at:
                try:
                    _age = (_now_dt - datetime.fromisoformat(rule.created_at)).days
                    if _age >= _max_age:
                        engine.update_interception(rule.id, lifecycle_status="deprecating")
                        print(f"  [DECAY] 降权(从未触发): {rule.id} (创建{_age}天)")
                        _dep_count += 1
                except Exception:
                    pass
            # 规则已活跃但长期未触发 → 降权
            elif rule.last_triggered and rule.triggered_count <= 1:
                try:
                    _last = (_now_dt - datetime.fromisoformat(rule.last_triggered)).days
                    if _last >= _max_age:
                        engine.update_interception(rule.id, lifecycle_status="deprecating")
                        print(f"  [DECAY] 降权(长期未触发): {rule.id} (最后触发{_last}天前)")
                        _dep_count += 1
                except Exception:
                    pass
        # deprecating 超期 → 归档
        for rule in engine.get_interceptions(active_only=False):
            if rule.lifecycle_status == "deprecating" and rule.created_at:
                try:
                    _age = (_now_dt - datetime.fromisoformat(rule.created_at)).days
                    if _age >= _max_age * 2:  # 60天
                        engine.update_interception(rule.id, lifecycle_status="archived")
                        print(f"  [ARCHIVE] deprecating→归档: {rule.id} (创建{_age}天)")
                        _arc_count += 1
                except Exception:
                    pass
        if _dep_count > 0 or _arc_count > 0:
            print(f"  [DECAY] {_dep_count} 降权, {_arc_count} 归档")
    except Exception as e:
        print(f"  [DECAY] 规则半衰期跳过: {e}")

    # 举一反三: 从成功模式泛化
    from_patterns = generalize_from_patterns()
    if from_patterns:
        print(f"  [DGEN] 举一反三: 从成功模式创建 {len(from_patterns)} 条规则")
        # P1: 同步写入 meta experience → abstract 空间
        for _rp in from_patterns[:3]:
            try:
                _insight = _rp.get("action", _rp.get("trigger_condition", ""))[:100]
                if _insight:
                    from datetime import datetime as _dt2
                    _meta = type("MetaExperience", (), {"id": "", "insight": _insight, "created_at": _dt2.now().isoformat()})()
                    engine.add_meta(_meta)
                    if hasattr(engine, "_mindol") and engine._mindol:
                        _muid = f"meta_auto_{_dt2.now().strftime('%Y%m%d_%H%M%S')}"
                        engine._mindol.add_unit(text=_insight, source="diegin_meta", uid=_muid, space=engine._mindol.SPACE_ABSTRACT)
                print(f"    [META] abstract: {_insight[:50]}")
            except Exception:
                pass

    # 举一反三: 跨域泛化
    cross = generalize_cross_domain()
    if cross:
        print(f"  [DGEN] 跨域泛化: 创建 {len(cross)} 条新规则")

    # 举一反三活化：评估 cached gen_rule，去重后激活
    activated = 0
    cleaned = 0
    for rule in engine.get_interceptions(active_only=False):
        if rule.lifecycle_status == "cached" and rule.source == "auto_generalized":
            # 去重检查：是否已有 active 规则用相同 action
            existing_same_action = [
                r for r in engine.get_interceptions(active_only=True)
                if r.action == rule.action and r.id != rule.id
            ]
            if existing_same_action:
                engine.delete_interception(rule.id)
                cleaned += 1
                print(f"  [CLEAN] 删除重复 cached: {rule.id}")
            else:
                engine.update_interception(rule.id, lifecycle_status="active")
                activated += 1
                print(f"  [ACTIVATE] cached→active: {rule.id}")
    if activated > 0 or cleaned > 0:
        print(f"  [DGEN] 举一反三: +{activated} active / 删{cleaned} 重复")
    # 举一反三->去伪存真验证门: staging 规则需验证通过>=2/3才晋升
    staging_rules = [r for r in engine.get_interceptions(active_only=False) if r.lifecycle_status == "staging"]
    promoted = 0
    archived = 0
    for rule in staging_rules:
        total = rule.triggered_count + rule.ignored_count + rule.block_count
        if total >= 3:
            success = rule.triggered_count + rule.block_count
            rate = success / total
            if rate >= 0.667:
                engine.update_interception(rule.id, lifecycle_status="active")
                promoted += 1
                print(f"  [PROMOTE] staging->active: {rule.id} (rate={rate:.0%})")
            else:
                engine.update_interception(rule.id, lifecycle_status="archived")
                archived += 1
                print(f"  [ARCHIVE] staging->archived: {rule.id} (low rate={rate:.0%})")
        else:
            print(f"  [HOLD] staging: {rule.id} (only {total} eval(s), need >=3)")
    if promoted > 0:
        print(f"  [DGEN] 验证门: {promoted} 条晋升active (成功率>=2/3)")
    if archived > 0:
        print(f"  [DGEN] 验证门: {archived} 条已归档 (成功率<2/3)")
    # 守三循环闭环: 检查shousan规则触发效果
    tracker.cycle_shousan_rules()
    tracker.cycle_gongqi_patterns()

    # === Phase 4.4: 去伪存真季度证伪 ===
    try:
        _cfg_path = os.path.join(os.path.dirname(__file__), '..', 'config', 'config.toml')
        _qf_enabled = True
        if os.path.isfile(_cfg_path):
            import tomllib
            with open(_cfg_path, 'rb') as _f:
                _cfg = tomllib.load(_f)
            _qf_enabled = _cfg.get('evidence_vault', {}).get('quarterly_falsification_enabled', True)
        if _qf_enabled:
            _last_qf = getattr(tracker, '_last_quarterly_falsification', None)
            _now_q = f"{_dt.datetime.now().year}-Q{(_dt.datetime.now().month - 1) // 3 + 1}"
            if _last_qf != _now_q:
                from evidence_vault import get_vault
                _vault = get_vault()
                _qr = _vault.run_quarterly_falsification()
                tracker._last_quarterly_falsification = _now_q
                if _qr.get('needs_revision'):
                    print(f"  [QF] 建议: {len(_qr.get('repeated_failures', []))} 个失效模式需修订")
                print(f"  [QF] 季度证伪({_now_q}) 完成")
    except Exception as e:
        print(f"  [QF] 季度证伪跳过: {e}")

    # === P0 #6: 归因正确率回溯 ===
    try:
        from evidence_vault import get_vault
        _vault = get_vault()
        _ar = _vault.verify_attribution(max_check=20)
        if _ar.get('misattributed', 0) > 0:
            print(f"  [ATTRIB] 发现 {_ar['misattributed']} 条可能误判的归因")
            for _sug in _ar.get('suggestions', [])[:3]:
                print(f"    [SUG] {_sug}")
        if _ar.get('verified', 0) > 0:
            print(f"  [ATTRIB] {_ar['verified']} 条归因已确认正确")
    except Exception as _e:
        print(f"  [ATTRIB] 归因回溯跳过: {_e}")

    # === Phase 4.1: 守三深度复盘(每日) ===
    try:
        import datetime as _dt
        _now = _dt.datetime.now()
        _last_deep = getattr(tracker, "_last_deep_review", None)
        if _last_deep is None:
            tracker._last_deep_review = _now.isoformat()
        else:
            try:
                _last = _dt.datetime.fromisoformat(_last_deep)
                _elapsed = (_now - _last).total_seconds() / 3600
                if _elapsed >= 24:
                    _all = engine.get_interceptions(active_only=False)
                    _alerting = [r for r in _all if getattr(r, "lifecycle_status", "") == "alerting"]
                    _blocking = [r for r in _all if getattr(r, "lifecycle_status", "") == "blocking"]
                    _low_conf = [r for r in engine.get_interceptions(active_only=True) if (getattr(r, "confidence", 5.0) or 5.0) < 2.5]
                    if _alerting:
                        print(f"  [DEEP_REVIEW] 深度复盘: {len(_alerting)} 条告警规则")
                    if _blocking:
                        print(f"  [DEEP_REVIEW] 深度复盘: {len(_blocking)} 条阻断规则")
                    if _low_conf:
                        for r in _low_conf:
                            print(f"  [DEEP_REVIEW] 低置信度: {r.id} (conf={r.confidence:.1f})")
                    tracker._last_deep_review = _now.isoformat()
            except Exception:
                tracker._last_deep_review = _now.isoformat()
    except Exception:
        pass
    engine.save_all()
    print("[OK] 定期维护完成")


_last_work_context: Optional[Dict] = None


def auto_sandwich_trigger(task_type: str, positive: List[str] = None, negative: List[str] = None):


    """


    工作完成后自动钩子：检测是否已完成重要工作，自动触发守三攻七复盘。


    由 call_diegin.py 或外部工具在关键操作完成后调用。


    """


    from datetime import datetime




    global _last_work_context


    if positive is None:


        positive = []


    if negative is None:


        negative = []


    # 如果没有提供正/负向点，输出提示但不报错（允许空复盘）


    result = auto_sandwich(positive, negative, task_type)


    # 归档触发记录


    _last_work_context = {


        "task_type": task_type,


        "triggered_at": datetime.now().isoformat(),


        "positive_count": len(positive),


        "negative_count": len(negative),


        "sandwich_result": result.get("report", "")[:200]


    }


    if _MEMPALACE_AVAILABLE:


        dgen_archive(f"[auto_sandwich_trigger] {task_type}", json.dumps(_last_work_context, ensure_ascii=False), "auto")


    return result


def self_check() -> bool:


    """系统自检"""


    try:


        engine = _get_engine()


        assert engine is not None


        rules = engine.get_interceptions(active_only=False)


        if len(rules) == 0:


            print("[WARN] 规则库为空，请检查种子规则是否注入")


            return False


        print(f"[OK] 系统就绪：共加载 {len(rules)} 条拦截规则，{len(engine.get_patterns(active_only=False))} 条成功模式")


        return True


    except Exception as e:


        print(f"[ERR] 自检失败: {e}")


        return False


if __name__ == "__main__":


    self_check()
def get_pacemaker():
    """获取缓急律实例"""
    return _get_pacemaker_inst()

def get_closure():
    """获取止观门实例"""
    return _get_closure_inst()

def pace_classify(ctx):
    """缓急律：任务类型分类"""
    pm = _get_pacemaker_inst()
    return pm.classify(ctx)

def should_skip_deep_review(ctx):
    """缓急律：是否跳过深度复盘"""
    pm = _get_pacemaker_inst()
    return pm.should_skip_deep_review(ctx)

def closure_open(item_id, description, context=None):
    """止观门：打开事项"""
    cg = _get_closure_inst()
    return cg.open(item_id, description, context)

def closure_close(item_id, summary='', result='completed'):
    """止观门：封存事项"""
    cg = _get_closure_inst()
    return cg.close(item_id, summary, result)

def closure_is_closed(item_id):
    """止观门：检查是否已封存"""
    cg = _get_closure_inst()
    return cg.is_closed(item_id)

def get_vault():
    """获取证据库实例"""
    return _get_vault_inst()

def evidence_record(rule_id, verdict, reason, source="auto", context=None):
    """去伪存真：记录证据判定"""
    v = _get_vault_inst()
    return v.record(rule_id, verdict, reason, source, context)
