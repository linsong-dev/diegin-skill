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

        "force_detail": detail

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


        # [????] ????????????????????????10???critical/high?
        _auto_written = []
        _high_sev = {"critical", "high"}
        
        # ??????????????? 30 ?????????
        try:
            old_auto = [r for r in engine.get_interceptions(active_only=False) if r.source == "auto_generalized"]
            if len(old_auto) >= 30:
                old_auto.sort(key=lambda r: getattr(r, "created_at", "") or "")
                to_remove = old_auto[:-20]  # ????? 20 ?
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
            # ?????
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
                print(f"[DGEN:AUTO] ???????? {len(_auto_written)} ???")
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


    守三攻七自动化：重要工作后自动复盘


    先负向纠错 → 再正向强化


    """


    from datetime import datetime


    ts = datetime.now().strftime("%Y-%m-%d %H:%M")


    tracker = _get_tracker()


    engine = _get_engine()


    report_lines = [f"# 守三攻七复盘 | {ts}\n"]


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


        dgen_archive(f"[守三攻七] {task_type}", report, "auto_review")


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


    for rule in engine.get_interceptions(active_only=True):


        if rule.confidence < 2.0:


            engine.update_interception(rule.id, lifecycle_status="deprecating")


            print(f"  [DOWN] 降权: {rule.id} (置信度 {rule.confidence:.2f})")


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
