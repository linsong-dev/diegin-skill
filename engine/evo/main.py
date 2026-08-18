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
from constancy import TaskRegistry, get_constancy as _get_constancy_inst
from self_mirror import SelfMirror, get_self_mirror as _get_self_mirror_inst


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


def _dgen_manifest_path() -> str:
    """泛化源清单路径（var/state/dgen_generalized.json）"""
    return os.path.join(os.path.dirname(__file__), "..", "..", "var", "state", "dgen_generalized.json")


def _load_dgen_manifest() -> dict:
    """读取泛化源清单：{src_name: [rule_id, ...]}"""
    import json as _json
    try:
        with open(_dgen_manifest_path(), "r", encoding="utf-8") as _f:
            _m = _json.load(_f)
            return _m if isinstance(_m, dict) else {}
    except Exception:
        return {}


def _mark_dgen_generalized(src_name: str, rule_id: str) -> None:
    """记录已泛化源（防删除后再生）"""
    import json as _json
    try:
        _m = _load_dgen_manifest()
        _m.setdefault(src_name, [])
        if rule_id not in _m[src_name]:
            _m[src_name].append(rule_id)
        with open(_dgen_manifest_path(), "w", encoding="utf-8") as _f:
            _json.dump(_m, _f, ensure_ascii=False, indent=2)
    except Exception:
        pass


_VECTORIZER = None

def _get_vectorizer():
    """语义距离向量器（懒加载单例）"""
    global _VECTORIZER
    if _VECTORIZER is None:
        try:
            from mindol.vectorizer import SimpleVectorizer
            _VECTORIZER = SimpleVectorizer()
        except Exception:
            _VECTORIZER = None
    return _VECTORIZER

def _is_pseudo_generalization(candidate_text: str, existing_texts: List[str],
                              threshold: float = 0.7) -> Optional[str]:
    """定稿第四章：推导的跨场景候选规则之间须满足语义距离阈值（向量余弦相似度<0.7），
    否则判定伪泛化（复制而非泛化），不进入 staging。返回与之过度相似的既有候选文本。"""
    vz = _get_vectorizer()
    if vz is None or not candidate_text.strip():
        return None
    for et in existing_texts:
        if not et or not et.strip():
            continue
        try:
            sim = vz.calc_similarity(candidate_text, et)
            if sim >= threshold:
                return et
        except Exception:
            continue
    return None


def generalize_cross_domain() -> list:
    """举一反三：跨域泛化（v3.7 多领域合并 + 迁移性证明）
    将一个领域的 domain_rule 合并泛化到其余全部领域
    置信度 3.0 → 7.0；created 带迁移理由（src→targets + 适配说明）
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
    _all_rule_ids = [r.id for r in engine.get_interceptions(active_only=False)]
    manifest = _load_dgen_manifest()
    created = []
    for src_name in domain_names:
        src_rules = all_domains[src_name]
        src_manifest = manifest.get(src_name, [])
        tgts = [t for t in domain_names if t != src_name]
        if not tgts:
            continue
        tgt_labels = [t.replace("domain_", "").replace("_", " ") for t in tgts]
        for src_rule in src_rules:
            name = src_rule.get("name", "")
            _src_id = src_rule.get("id", name)
            if _src_id in src_manifest:
                continue
            # P4-13 泛化源兜底：任何状态已有规则 ID 含该领域规则 id（如 L4 归档 xdomain_*）→ 视为已泛化，防新环境无 manifest 时再生
            if any(_src_id in _rid or _rid.endswith(_src_id[:20]) for _rid in _all_rule_ids):
                _mark_dgen_generalized(src_name, _src_id)
                continue
            desc = src_rule.get("description", "")
            adapted_desc = desc
            for _t in tgts:
                _tl = _t.replace("domain_", "").replace("_", " ")
                adapted_desc = adapted_desc.replace("code", _tl).replace("data", _tl).replace("writing", _tl)
            if adapted_desc == desc:
                adapted_desc = "跨域: " + desc
            rid = "xdomain_merged_" + src_name.replace("domain_", "") + "_" + _src_id[:20]
            existing = engine.get_interception_by_id(rid)
            if existing:
                _mark_dgen_generalized(src_name, _src_id)
                continue
            trig = "domain in " + repr(tgts)
            import datetime as dt
            from rule_engine import InterceptionRule
            reason = "从 " + src_name.replace("domain_", "") + " 泛化到 " + str(len(tgts)) + " 个领域: " + ", ".join(tgt_labels)
            new_rule = InterceptionRule(
                id=rid,
                trigger_condition=trig,
                action="suggest_cross_domain; " + adapted_desc[:80],
                severity="low",
                tags=["attack", "举一反三", "cross_domain", "merged"] + tgts,
                logic_score=7.0, outcome_score=7.0, confidence=7.0,
                source="learned",
                source_review=reason,
                lifecycle_status="staging",
                created_at=dt.datetime.now().isoformat(),
                valid_until="", last_triggered="",
                boundary_conditions=[adapted_desc[:120]],
                invalid_conditions=[], triggered_count=0, ignored_count=0, override_count=0,
                last_ignored="", block_count=0, blocked_rules=[]
            )
            engine.add_interception(new_rule)
            created.append({"id": rid, "src": src_name, "targets": list(tgts), "reason": reason})
            _mark_dgen_generalized(src_name, _src_id)
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
        # P4-13 泛化源拦截①：空壳模式（decision_logic 为空）不泛化，避免复制无实质决策逻辑的空壳规则
        if not (getattr(p, "decision_logic", "") or "").strip():
            continue
        # P4-13 泛化源拦截②：已泛化过的模式（auto_promoted）不重复泛化，防删除后再生
        if getattr(p, "auto_promoted", False):
            continue
        # [P4-20260806] 自动提取质量门：噪音模式不派生规则（去伪存真·证必可验）
        try:
            from rule_engine import _noise_reason as _nr
            _why = _nr(getattr(p, "decision_logic", "") or "")
            if _why:
                continue
        except Exception:
            pass
        tc = getattr(p, "triggered_count", 0) or 0
        conf = getattr(p, "confidence", 0) or 0
        os_val = getattr(p, "outcome_score", 0) or 0
        # 攻七强化 Q3: 泛化提速 - 同场景复用≥2次 或 高置信度(≥4.5) 即触发泛化
        # 复用本身即验证信号（人类跨域迁移也是先快后验证）
        if tc < 2 and conf < 4.5:
            continue
        cond = getattr(p, "trigger_condition", "") or p.trigger_scenario
        rid = "pat_rule_" + p.id
        existing = engine.get_interception_by_id(rid)
        if existing:
            continue
        # 定稿第四章：语义距离阈值——候选与既有 staging 候选相似度≥0.7 → 伪泛化，不入 staging
        _existing_staging_texts = [
            (str(getattr(r, "trigger_condition", "") or "") + " " + str(getattr(r, "action", "") or ""))
            for r in engine.get_interceptions(active_only=False)
            if getattr(r, "lifecycle_status", "") == "staging"
        ]
        _cand_text = (cond + " " + str(getattr(p, "decision_logic", "") or ""))[:200]
        _pseudo_sim = _is_pseudo_generalization(_cand_text, _existing_staging_texts)
        if _pseudo_sim is not None:
            # 伪泛化记录边界（去伪存真·证必可验）：不进入 staging
            try:
                _v = _get_vault_inst()
                _v.record(rid, "skip", f"伪泛化拦截: 与既有staging候选语义相似度≥0.7", source="generalize_semantic_gate")
            except Exception:
                pass
            continue
        new_rule = InterceptionRule(
            id=rid,
            trigger_condition=cond,
            action="suggest_from_pattern; " + (p.decision_logic[:60] if hasattr(p, "decision_logic") else ""),
            severity="low",  # [FIX v3.8.1] suggest_from_pattern 为正向建议语义, 固定 low 防 medium→escalate 误判
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
              patterns: List[SuccessPattern],
              mindol_hits: Optional[List[Dict]] = None,
              closure_state: Optional[Dict] = None,
              pace_channel: Optional[Dict] = None,
              context: Optional[Dict] = None,
              constancy_state: Optional[Dict] = None) -> Dict[str, Any]:


    """冲突仲裁 — 使用 arbiter.to_display() 对齐 AGENTS.md 裁决格式"""


    import dataclasses


    arbiter_obj = _get_arbiter()


    result = arbiter_obj.resolve(interceptions, patterns, mindol_hits=mindol_hits,
                                closure_state=closure_state, pace_channel=pace_channel,
                                context=context, constancy_state=constancy_state)


    display = arbiter_obj.to_display(result)


    response = {


        "decision": display["decision"],


        "display_line": display["display_line"],


        "reason": result.reason,


        "winning_rule": None,


        "winning_rule_id": display.get("winning_rule_id"),


        "conflict_set": [],
        "mindol_memory_note": getattr(result, "reason", "") if mindol_hits and "P6记忆" in getattr(result, "reason", "") else ""


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


def auto_sandwich(positive: List[str], negative: List[str], task_type: str = "general", method: str = "") -> Dict:


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
            # [L4-防再生] archived 为终态：跳过一切强化/补全/promote，防自动复活
            if getattr(existing, "lifecycle_status", "") == "archived":
                report_lines.append(f"   ⛔ 已归档模式，跳过强化（archived 终态）\n")
                continue


            # 已存在 → 置信度+0.3


            existing.confidence = min(5.0, existing.confidence + 0.3)


            existing.triggered_count += 1


            _upd = {


                "confidence": existing.confidence,


                "triggered_count": existing.triggered_count,


            }


            # v3.6.1 攻七·模式实质化：空壳模式（无方法内容）用本次成功做法补全


            if method and (not existing.decision_logic or existing.decision_logic.strip() == "" or existing.decision_logic.strip() == p):


                _upd["decision_logic"] = method[:200]


                _upd["micro_template"] = method[:80]


                if task_type.startswith("tool_"):


                    _upd["trigger_condition"] = "tool_name == " + repr(p)


                # v3.8 归档复活：空壳被补全为实质内容后，重新进入 staging 验证门
                if getattr(existing, "lifecycle_status", "") == "archived":
                    _upd["lifecycle_status"] = "staging"
                    _upd.pop("archive_reason", None)
            engine.update_pattern(pat_id, **_upd)


            # v3.6.3 攻七⑤验证门：staging 第2次成功 → active；active 达标 → auto_promoted


            _promoted = engine.promote_pattern(pat_id)


            if _promoted and (getattr(existing, "lifecycle_status", "") == "staging"):


                _upd2 = {"lifecycle_status": "active"}


                engine.update_pattern(pat_id, **_upd2)


                report_lines.append(f"   🟢 验证门通过：staging→active\n")


            report_lines.append(f"   ✅ 已有模式，置信度+0.3 → {existing.confidence}\n")


        else:


            # 新模式


            from rule_engine import SuccessPattern


            # v3.7 攻七质量门槛：仅实质方法文本入库（工具名/状态词不算决策逻辑）
            if not method or len(method.strip()) < 8:
                report_lines.append(f"   ⚠️ 跳过空壳模式（无实质决策逻辑）\n")
                continue
            _dl_hollow = method.strip().replace(" ", "").replace(chr(0x3000), "").lower()
            if len(_dl_hollow) < 6 or any(_h in _dl_hollow for _h in ("成功完成exit=0", "completedexit=0", "工具成功完成")):
                report_lines.append(f"   ⚠️ 跳过空壳模式（决策逻辑无学习价值）\n")
                continue
                report_lines.append(f"   ⚠️ 跳过空壳模式（决策逻辑无学习价值）\n")
                continue
            _dl = method[:200] if method else p


            # [P4-20260806] 自动提取质量门：噪音内容不建模式（乱码/测试样本/只读查询）
            try:
                from rule_engine import _noise_reason as _nr2
                _why2 = _nr2(_dl)
                if _why2:
                    report_lines.append(f"   \u26a0\ufe0f 跳过噪音模式（{_why2}）\n")
                    continue
            except Exception:
                pass


            _mt = method[:80] if method else p[:80]


            _tc = ("tool_name == " + repr(p)) if (task_type.startswith("tool_") and method) else ""


            new_pat = SuccessPattern(


                id=pat_id,


                pattern_name=f"auto_{task_type}_{i}",


                trigger_scenario=task_type,


                decision_logic=_dl,


                micro_template=_mt,


                trigger_condition=_tc,


                logic_score=4.0,


                outcome_score=3.5,


                confidence=3.8,


                source="auto_sandwich",


                # v3.6.3 攻七⑤验证门：新模式先进 staging，第2次成功触发转 active


                lifecycle_status="staging",


                created_at=datetime.now().isoformat(),


                triggered_count=1


            )


            engine.add_pattern(new_pat)


            report_lines.append(f"   ✅ 已创建新模式(staging待验证), conf=3.8\n")


    engine.save_all()


    # v3.6.3 攻七⑥生命周期维护：staging验证转正 / 无效模式淘汰


    try:


        engine.auto_promote_all()


        engine.demote_patterns()


    except Exception:


        pass


    # v3.6.3 攻七→举一反三互联：满足条件的模式泛化为 staging 拦截规则


    _gen_count = 0


    try:


        if any((getattr(p, "triggered_count", 0) or 0) >= 3 for p in engine.get_patterns(active_only=True)):


            _gen_count = len(generalize_from_patterns() or [])


    except Exception:


        pass


    if _gen_count:


        report_lines.append(f"\n   🔗 举一反三: 泛化出 {_gen_count} 条 staging 规则\n")


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


def adjust_rule_confidence(rule_id: str, delta: float, reason: str = "", source: str = "post_review") -> bool:
    """复盘/反馈回流：调整规则或模式的置信度（双向反馈闭环）"""
    try:
        engine = _get_engine()
        rule = engine.get_interception_by_id(rule_id)
        if rule:
            new_conf = max(0.5, min(5.0, (rule.confidence or 5.0) + delta))
            engine.update_interception(rule.id, confidence=new_conf)
            try:
                from evidence_vault import get_vault
                get_vault().record(rule_id, "review_adjust", f"{source}: conf {rule.confidence:.2f}->{new_conf:.2f} | {reason[:80]}", source=source)
            except Exception:
                pass
            return True
        pattern = engine.get_pattern_by_id(rule_id)
        if pattern:
            new_conf = max(0.5, min(5.0, (pattern.confidence or 5.0) + delta))
            engine.update_pattern(pattern.id, confidence=new_conf)
            return True
    except Exception:
        pass
    return False


def audit_strike_summary(strikes: dict) -> dict:
    """一二不过三审核口径（v3.8.2 对齐）：fix_status=verified 视为已修复闭环。

    供 audit 标准审核使用，与 principle_health 的待干预口径一致：
    已修复验证的 strike 不列为"已达阈值"告警（防误报），
    未修复且 count>=3 仍须高亮待干预。
    返回:
        total: 记录总数
        verified: [{"error_type","count"}] 已修复闭环
        pending_high: [{"error_type","count"}] 未修复且 count>=3
        pending_warn: [{"error_type","count"}] 未修复且 count==2
        pending_ok: [{"error_type","count"}] 未修复且 count<2
    """
    summary = {"total": 0, "verified": [], "pending_high": [], "pending_warn": [], "pending_ok": []}
    for _et, _v in (strikes or {}).items():
        if not isinstance(_v, dict):
            continue
        summary["total"] += 1
        _cnt = int(_v.get("count", 0) or 0)
        _item = {"error_type": _et, "count": _cnt}
        if (_v.get("fix_status") or "") == "verified":
            summary["verified"].append(_item)
        elif _cnt >= 3:
            summary["pending_high"].append(_item)
        elif _cnt == 2:
            summary["pending_warn"].append(_item)
        else:
            summary["pending_ok"].append(_item)
    return summary


def principle_health() -> dict:
    """P2 八原则健康看板：每个原则一个健康报告（🟢正常 / 🟡关注 / 🔴干预）"""
    try:
        engine = _get_engine()
        tracker = _get_tracker()
    except Exception:
        return {"error": "engine_unavailable"}

    report = {}

    # 守三：规则命中率与无视率
    try:
        rules = engine.get_interceptions(active_only=True)
        total_trig = sum(getattr(r, "triggered_count", 0) or 0 for r in rules)
        total_ign = sum(getattr(r, "ignored_count", 0) or 0 for r in rules)
        ignore_rate = total_ign / total_trig if total_trig > 0 else 0.0
        report["守三"] = {
            "active_rules": len(rules),
            "total_triggers": total_trig,
            "ignore_rate": round(ignore_rate, 3),
            "health": "🟢" if ignore_rate < 0.3 else ("🟡" if ignore_rate < 0.5 else "🔴"),
        }
    except Exception as e:
        report["守三"] = {"error": str(e)[:80]}

    # 攻七：模式数量与晋升率
    try:
        pats = engine.get_patterns(active_only=True)
        promoted = len([p for p in pats if getattr(p, "auto_promoted", False)])
        report["攻七"] = {
            "patterns": len(pats),
            "promoted_rate": round(promoted / len(pats), 3) if pats else 0.0,
            "health": "🟢" if len(pats) >= 5 else "🟡",
        }
    except Exception as e:
        report["攻七"] = {"error": str(e)[:80]}

    # 一二不过三：升级率
    try:
        db = tracker._load_strikes_db()
        # v3.8.2: fix_status=verified 视为已修复闭环，不计入待干预升级率（防误报）
        pending = {k: v for k, v in db.items() if (v.get("fix_status") or "") != "verified"}
        types = len(pending)
        escalated = len([e for e in pending.values() if (e.get("count", 0) or 0) >= 3])
        report["一二不过三"] = {
            "strike_types": types,
            "strikes_total": len(db),
            "strikes_verified": len(db) - types,
            "escalation_rate": round(escalated / types, 3) if types else 0.0,
            "health": "🟢" if types == 0 or escalated / types < 0.2 else ("🟡" if escalated / types < 0.4 else "🔴"),
        }
    except Exception as e:
        report["一二不过三"] = {"error": str(e)[:80]}

    # 举一反三：staging 通过率
    try:
        all_r = engine.get_interceptions(active_only=False)
        staging = [r for r in all_r if getattr(r, "lifecycle_status", "") == "staging"]
        staging_ok = [r for r in staging if (getattr(r, "triggered_count", 0) or 0) >= 2]
        report["举一反三"] = {
            "staging_count": len(staging),
            "staging_pass_rate": round(len(staging_ok) / len(staging), 3) if staging else 0.0,
            "health": "🟢" if not staging or len(staging_ok) / len(staging) >= 0.3 else "🟡",
        }
    except Exception as e:
        report["举一反三"] = {"error": str(e)[:80]}

    # 去伪存真：证据链规模与归因
    try:
        from evidence_vault import get_vault
        vault = get_vault()
        stats = vault.get_stats()
        report["去伪存真"] = {
            "evidence_verdicts": stats.get("total_verdicts", 0),
            "attributions": len(vault._attribution_log) if hasattr(vault, "_attribution_log") else 0,
            "health": "🟢",
        }
    except Exception as e:
        report["去伪存真"] = {"error": str(e)[:80]}

    # 裁决律：待决冲突
    try:
        arb = _get_arbiter()
        pending = len(getattr(arb, "pending_conflicts", []))
        report["裁决律"] = {
            "pending_conflicts": pending,
            "health": "🟢" if pending < 3 else ("🟡" if pending < 6 else "🔴"),
        }
    except Exception as e:
        report["裁决律"] = {"error": str(e)[:80]}

    # 缓急律：分类次数与宕机
    try:
        pm = _get_pacemaker_inst()
        log = getattr(pm, "_classify_log", [])
        report["缓急律"] = {
            "total_classifications": len(log),
            "downtime_active": pm._check_downtime() if hasattr(pm, "_check_downtime") else False,
            "health": "🟢",
        }
    except Exception as e:
        report["缓急律"] = {"error": str(e)[:80]}

    # 止观门：开放事项
    try:
        cg = _get_closure_inst()
        open_items = len(cg.get_open_items())
        report["止观门"] = {
            "open_items": open_items,
            "closed_items": cg.get_closed_count(),
            "health": "🟢" if open_items < 10 else ("🟡" if open_items < 20 else "🔴"),
        }
    except Exception as e:
        report["止观门"] = {"error": str(e)[:80]}

    report["generated_at"] = datetime.datetime.now().isoformat()
    return report


def health_check(verbose: bool = True) -> Dict[str, Any]:


    """运行健康度检查"""


    engine = _get_engine()


    return run_health_check(engine)


def maintenance_staging_ttl(engine):
    """B1 防再生：staging 规则 14 天未验证 → 弃用 + 记边界（防 HOLD 僵尸 staging 堆积）"""
    from datetime import datetime as _dt
    _cfg_path = os.path.join(os.path.dirname(__file__), '..', 'config', 'config.toml')
    _max_age = 14
    try:
        if os.path.isfile(_cfg_path):
            import tomllib
            with open(_cfg_path, 'r', encoding='utf-8-sig') as _f:
                _cfg = tomllib.loads(_f.read())
            _max_age = int(_cfg.get('maintenance', {}).get('staging_max_age_days', 14) or 14)
    except Exception:
        _max_age = 14
    _now = _dt.now()
    _dep = 0
    for rule in engine.get_interceptions(active_only=False):
        if rule.lifecycle_status != 'staging':
            continue
        # 已有 TTL 边界记录则跳过（幂等）
        if any('staging_ttl' in str(b) for b in (getattr(rule, 'boundary_conditions', None) or [])):
            continue
        if not rule.created_at:
            continue
        try:
            _base = _dt.fromisoformat(rule.created_at)
        except Exception:
            continue
        _age = (_now - _base).days
        if _age >= _max_age:
            _bc = list(getattr(rule, 'boundary_conditions', None) or [])
            _bc.append('staging_ttl: %d天未验证淘汰 @ %s' % (_age, _now.isoformat()))
            engine.update_interception(rule.id, lifecycle_status='deprecating', boundary_conditions=_bc)
            print('  [STAGING-TTL] 弃用未验证 staging: %s (创建%d天 >= %d天)' % (rule.id, _age, _max_age))
            _dep += 1
    if _dep > 0:
        print('  [STAGING-TTL] %d 条 staging 因超期未验证被弃用（边界已记录）' % _dep)
    return _dep


def maintenance_failure_ttl(engine):
    """A2 守三·失败模式 TTL：self_error 规则 30 天未复现 → 阶梯降级（blocking/critical→alerting，alerting→deprecating）"""
    from datetime import datetime as _dt
    _cfg_path = os.path.join(os.path.dirname(__file__), '..', 'config', 'config.toml')
    _ttl = 30
    try:
        if os.path.isfile(_cfg_path):
            import tomllib
            with open(_cfg_path, 'r', encoding='utf-8-sig') as _f:
                _cfg = tomllib.loads(_f.read())
            _ttl = int(_cfg.get('maintenance', {}).get('failure_ttl_days', 30) or 30)
    except Exception:
        _ttl = 30
    _now = _dt.now()
    _down = 0
    for rule in engine.get_interceptions(active_only=False):
        if rule.lifecycle_status not in ('blocking', 'critical', 'alerting'):
            continue
        _src = str(getattr(rule, 'source', '') or '')
        _tags = ' '.join(getattr(rule, 'tags', []) or [])
        if 'self_error' not in _src and 'self_error' not in _tags:
            continue
        if any('failure_ttl' in str(b) for b in (getattr(rule, 'boundary_conditions', None) or [])):
            continue
        _ref = rule.last_triggered or rule.created_at
        if not _ref:
            continue
        try:
            _base = _dt.fromisoformat(_ref)
            if _base.tzinfo is not None:
                _base = _base.replace(tzinfo=None)
        except Exception:
            continue
        _age = (_now - _base).days
        if _age < _ttl:
            continue
        _bc = list(getattr(rule, 'boundary_conditions', None) or [])
        _bc.append('failure_ttl: %d天未复现降级 @ %s' % (_age, _now.isoformat()))
        _old_lc = rule.lifecycle_status
        _target = 'deprecating' if _old_lc == 'alerting' else 'alerting'
        engine.update_interception(rule.id, lifecycle_status=_target, boundary_conditions=_bc)
        print(f"  [FAILURE-TTL] {rule.id}: {_old_lc}→{_target} ({_age}天未复现)")
        _down += 1
    if _down > 0:
        print(f"  [FAILURE-TTL] {_down} 条失败模式规则因 {_ttl} 天未复现降级")
    return _down


def maintenance_archived_purge(engine):
    """P3-10 archived 清理策略：超期(默认90天)且零触发的 archived 规则物理删除（Mindol 语义记忆保留）"""
    from datetime import datetime as _dt
    _cfg_path = os.path.join(os.path.dirname(__file__), '..', 'config', 'config.toml')
    _retention = 90
    try:
        if os.path.isfile(_cfg_path):
            import tomllib
            with open(_cfg_path, 'r', encoding='utf-8-sig') as _f:
                _cfg = tomllib.loads(_f.read())
            _retention = int(_cfg.get('maintenance', {}).get('archived_retention_days', 90) or 90)
    except Exception:
        _retention = 90
    _now = _dt.now()
    _del = 0
    for rule in engine.get_interceptions(active_only=False):
        if rule.lifecycle_status != 'archived':
            continue
        if (rule.triggered_count or 0) > 0 or (rule.ignored_count or 0) > 0 or (rule.block_count or 0) > 0:
            continue  # 有历史触发的保留
        _ref = rule.created_at or rule.last_triggered
        if not _ref:
            continue
        try:
            _base = _dt.fromisoformat(_ref)
            if _base.tzinfo is not None:
                _base = _base.replace(tzinfo=None)
        except Exception:
            continue
        _age = (_now - _base).days
        if _age >= _retention:
            print(f"  [ARCHIVE-PURGE] 物理删除零触发 archived: {rule.id} (归档{_age}天)")
            engine.delete_interception(rule.id)
            _del += 1
    if _del > 0:
        print(f"  [ARCHIVE-PURGE] {_del} 条零触发 archived 规则超 {_retention} 天已物理清理（Mindol 语义记忆保留）")
    return _del


def maintenance_staging_queue(engine):
    """P3-10 staging 校验队列：汇总待验证 staging 规则 + 写 var/state/staging_queue.json 供复审"""
    from datetime import datetime as _dt
    from collections import Counter as _Counter
    _now = _dt.now()
    queue = []
    for rule in engine.get_interceptions(active_only=False):
        if rule.lifecycle_status != 'staging':
            continue
        total = (rule.triggered_count or 0) + (rule.ignored_count or 0) + (rule.block_count or 0)
        age = None
        if rule.created_at:
            try:
                _base = _dt.fromisoformat(rule.created_at)
                if _base.tzinfo is not None:
                    _base = _base.replace(tzinfo=None)
                age = (_now - _base).days
            except Exception:
                pass
        status = 'hold'
        if total >= 3:
            rate = ((rule.triggered_count or 0) + (rule.block_count or 0)) / total
            status = 'promote' if rate >= 0.667 else 'archive'
        queue.append({
            "id": rule.id, "created_at": rule.created_at, "age_days": age,
            "triggered_count": rule.triggered_count or 0,
            "ignored_count": rule.ignored_count or 0,
            "block_count": rule.block_count or 0,
            "eval_total": total, "status": status,
            "confidence": rule.confidence, "source": rule.source,
        })
    queue.sort(key=lambda x: (-(x['age_days'] or 0), x['id']))
    _qpath = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), 'var', 'state', 'staging_queue.json')
    try:
        os.makedirs(os.path.dirname(_qpath), exist_ok=True)
        with open(_qpath, 'w', encoding='utf-8') as _f:
            import json as _json
            _json.dump(queue, _f, ensure_ascii=False, indent=1)
    except Exception as _e:
        print(f"  [STAGING-QUEUE] 写队列文件失败: {_e}")
    _cnt = _Counter(q['status'] for q in queue)
    _n = len(queue)
    if _n > 0:
        print(f"  [STAGING-QUEUE] 待校验 {_n} 条: hold={_cnt.get('hold',0)} promote={_cnt.get('promote',0)} archive={_cnt.get('archive',0)}")
    return _n


def run_maintenance():


    from datetime import datetime  # 维护函数统一导入
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
            with open(_cfg_path, 'r', encoding='utf-8-sig') as _f:
                _cfg = tomllib.loads(_f.read())
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
    # B1 防再生: staging TTL 淘汰（14天未验证 → 弃用 + 记边界）
    try:
        maintenance_staging_ttl(engine)
    except Exception as _e:
        print(f"  [STAGING-TTL] 跳过: {_e}")
    # P3-10: 失败模式 TTL（30天未复现降级）
    try:
        maintenance_failure_ttl(engine)
    except Exception as _e:
        print(f"  [FAILURE-TTL] 跳过: {_e}")
    # P3-10: archived 超期零触发清理策略
    try:
        maintenance_archived_purge(engine)
    except Exception as _e:
        print(f"  [ARCHIVE-PURGE] 跳过: {_e}")
    # P3-10: staging 校验队列（复审报告）
    try:
        maintenance_staging_queue(engine)
    except Exception as _e:
        print(f"  [STAGING-QUEUE] 跳过: {_e}")
    # 守三循环闭环: 检查shousan规则触发效果
    tracker.cycle_shousan_rules()
    tracker.cycle_gongqi_patterns()

    # === Phase 4.4: 去伪存真季度证伪 ===
    try:
        _cfg_path = os.path.join(os.path.dirname(__file__), '..', 'config', 'config.toml')
        _qf_enabled = True
        if os.path.isfile(_cfg_path):
            import tomllib
            with open(_cfg_path, 'r', encoding='utf-8-sig') as _f:
                _cfg = tomllib.loads(_f.read())
            _qf_enabled = _cfg.get('evidence_vault', {}).get('quarterly_falsification_enabled', True)
        if _qf_enabled:
            _last_qf = getattr(tracker, '_last_quarterly_falsification', None)
            _now_q = f"{datetime.now().year}-Q{(datetime.now().month - 1) // 3 + 1}"
            if _last_qf != _now_q:
                from evidence_vault import get_vault
                _vault = get_vault()
                _qr = _vault.run_quarterly_falsification()
                tracker._last_quarterly_falsification = _now_q
                if _qr.get('needs_revision'):
                    print(f"  [QF] 建议: {len(_qr.get('repeated_failures', []))} 个失效模式需修订")
                    # v3.5：实际复审 —— 重复失效规则降权 + 标记 deprecating
                    for _rr in _qr.get('repeated_rules', [])[:5]:
                        _rr_id = _rr.get('rule_id', '')
                        _rr_rule = engine.get_interception_by_id(_rr_id)
                        if _rr_rule:
                            _nc = max(0.5, (_rr_rule.confidence or 5.0) * 0.7)
                            engine.update_interception(_rr_id, confidence=_nc, lifecycle_status='deprecating')
                            print(f"    [APPLY] 证伪复审: {_rr_id} → deprecating, conf={_nc:.2f}")
                print(f"  [QF] 季度证伪({_now_q}) 完成")
    except Exception as e:
        print(f"  [QF] 季度证伪跳过: {e}")

    # === P0 #6: 归因正确率回溯（v3.5：实际应用，不只是打印） ===
    try:
        from evidence_vault import get_vault
        _vault = get_vault()
        _ar = _vault.verify_attribution(max_check=20)
        if _ar.get('misattributed', 0) > 0:
            print(f"  [ATTRIB] 发现 {_ar['misattributed']} 条可能误判的归因")
            for _sug in _ar.get('suggestions', [])[:3]:
                print(f"    [SUG] {_sug}")
                # 实际应用：误判归因涉及的规则降权
                _rid = _sug.split("归因重审:")[1].strip().split()[0] if "归因重审:" in _sug else ""
                if _rid:
                    _r = engine.get_interception_by_id(_rid)
                    if _r:
                        _nc = max(0.5, (_r.confidence or 5.0) * 0.8)
                        engine.update_interception(_rid, confidence=_nc)
                        print(f"    [APPLY] {_rid} 置信度 {_r.confidence:.2f} -> {_nc:.2f}（归因误判降权）")
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

    # v3.4.1: ①改毕验自动验证（24h 未再犯 → 修复成功 → 攻七固化）
    try:
        _tk = _get_tracker()
        _auto = _tk._auto_verify_pending_fixes(max_age_hours=24)
        for _a in _auto:
            print(f"  [FIX-VERIFY] 自动改毕验通过: {_a['error_type']} (age={_a['age_hours']}h) → 攻七经验已固化")
    except Exception as _e:
        print(f"  [FIX-VERIFY] 跳过: {_e}")

    # === P2: 八原则健康看板（写 Mindol + 三态响应） ===
    try:
        _ph = principle_health()
        _red = [k for k, v in _ph.items() if isinstance(v, dict) and v.get("health") == "🔴"]
        _yellow = [k for k, v in _ph.items() if isinstance(v, dict) and v.get("health") == "🟡"]
        if _red:
            print(f"  [HEALTH] 🔴 需要干预: {_red}")
        if _yellow:
            print(f"  [HEALTH] 🟡 建议关注: {_yellow}")
        if not _red and not _yellow:
            print(f"  [HEALTH] 八原则健康看板: 全部 🟢")
        # 写入 Mindol codex 空间（下一轮 pre_check 可检索到）
        try:
            from mindol.diegin_integration import memory_archive
            memory_archive("principle_health", json.dumps({k: v for k, v in _ph.items() if k != "generated_at"}, ensure_ascii=False)[:800])
        except Exception:
            pass
    except Exception as _e:
        print(f"  [HEALTH] 健康看板跳过: {_e}")

    # 恒常门：30天快照清理（paused/blocked 超时任务自动清理；completed/abandoned 永久保留）
    try:
        _cg = _get_constancy_inst()
        _removed = _cg.cleanup_expired()
        if _removed:
            print(f"  [CLEAN] 恒常门超时任务快照清理: {_removed} 条")
    except Exception as _ce:
        print(f"  [CLEAN] 恒常门清理跳过: {_ce}")

    # 去伪存真：暂存区 50轮/7天（先到者）超时自动淘汰（定稿第五章）
    try:
        _vault = get_vault()
        _expired = _vault.staging_ttl_check()
        if _expired:
            print(f"  [CLEAN] 去伪存真暂存区超时淘汰: {_expired} 条")
    except Exception as _ve:
        print(f"  [CLEAN] 暂存区淘汰跳过: {_ve}")

    print("[OK] 定期维护完成")

    # 一击即中: strikes 过期清理（14 天无活动则归档）—— 自 evidence_record 死代码迁入
    try:
        _sp2 = os.path.join(os.path.dirname(__file__), '..', 'var', 'state', 'strikes_db.json')
        if os.path.isfile(_sp2):
            with open(_sp2, 'r', encoding='utf-8') as _sf2:
                _st2 = json.load(_sf2)
            _ttl2 = _cfg.get('maintenance', {}).get('strike_ttl_days', 14) if '_cfg' in dir() else 14
            _now2 = datetime.now()
            _ch2 = False
            for _et2 in list(_st2.keys()):
                _last2 = _st2[_et2].get('last_seen', '')
                if _last2:
                    try:
                        if (_now2 - datetime.fromisoformat(_last2)).days >= _ttl2:
                            del _st2[_et2]
                            _ch2 = True
                            print(f"  [CLEAN] strike 过期清理: {_et2} (最后触发 {_last2[:10]})")
                    except Exception:
                        pass
            if _ch2:
                with open(_sp2, 'w', encoding='utf-8') as _sf2:
                    json.dump(_st2, _sf2, ensure_ascii=False, indent=2)
                print("  [CLEAN] strikes_db 清理完成")
    except Exception as _se2:
        print(f"  [CLEAN] strikes 清理跳过: {_se2}")

    # B2 防再生: dgen_evolve 最小接入——维护统计写入健康度基线
    try:
        _evo_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        if _evo_dir not in sys.path:
            sys.path.insert(0, _evo_dir)
        from dgen_evolve import maintenance_report
        _all_r = engine.get_interceptions(active_only=False)
        _stats = {
            "rules": len(_all_r),
            "staging": sum(1 for r in _all_r if r.lifecycle_status == "staging"),
            "deprecated": sum(1 for r in _all_r if r.lifecycle_status == "deprecating"),
            "strikes": len(tracker._load_strikes_db()) if hasattr(tracker, "_load_strikes_db") else 0,
        }
        if maintenance_report(_stats):
            print("  [DGEN] dgen_evolve 健康度已更新")
    except Exception as _e2:
        print(f"  [DGEN] dgen_evolve 接入跳过: {_e2}")

    # v3.7.2 记忆代谢：Mindol 经验类空间时间衰减 + 自动休眠（权威空间豁免）
    try:
        _evo_dir2 = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        if _evo_dir2 not in sys.path:
            sys.path.insert(0, _evo_dir2)
        from mindol.diegin_integration import memory_decay
        _decay_stats = memory_decay()
        print(f"  [MINDOL] 记忆代谢: {_decay_stats}")
    except Exception as _e3:
        print(f"  [MINDOL] 记忆代谢异常: {_e3}")


def auto_sandwich_trigger(task_type: str, positive: List[str] = None, negative: List[str] = None, method: str = ""):


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


    result = auto_sandwich(positive, negative, task_type, method)


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

def closure_close(item_id, summary='', result='completed', status='completed',
                 intent_summary='', completion_criteria='', pending_items=None,
                 parent_task_id='', snapshot=None):
    """止观门：封存事项（定稿四态 + 状态摘要 + 执行轨迹只读快照）"""
    cg = _get_closure_inst()
    return cg.close(item_id, summary, result, status=status,
                    intent_summary=intent_summary, completion_criteria=completion_criteria,
                    pending_items=pending_items, parent_task_id=parent_task_id,
                    snapshot=snapshot)

def closure_readonly_snapshot(item_id):
    """止观门：封存后只读豁免权——守三应急复盘只读访问执行轨迹快照"""
    cg = _get_closure_inst()
    return cg.export_readonly_snapshot(item_id)

def closure_is_closed(item_id):
    """止观门：检查是否已封存"""
    cg = _get_closure_inst()
    return cg.is_closed(item_id)

def get_constancy():
    """获取恒常门（持存）实例"""
    return _get_constancy_inst()

def _constancy_archive(action, task_id, ok=True):
    """恒常门：写操作后归档 Mindol codex（JSON↔Mindol 互为备份，单向重建 JSON→Mindol）"""
    try:
        if not ok or not task_id:
            return
        _t = _get_constancy_inst().snapshot(task_id)
        dgen_archive("constancy", json.dumps(
            {"action": action, "task_id": task_id,
             "status": _t.get("status", ""), "intent_summary": str(_t.get("intent_summary", ""))[:200]},
            ensure_ascii=False)[:1500], {})
    except Exception:
        pass


def constancy_begin(intent_summary, completion_criteria="", pending_items=None,
                    parent_task_id=None, context=None):
    """恒常门：启而探——创建新任务（含嵌套深度≤3 溢出保护）"""
    _r = _get_constancy_inst().begin(intent_summary, completion_criteria,
                                     pending_items, parent_task_id, context)
    if _r.get("ok"):
        _constancy_archive("begin", _r.get("task_id", ""))
    return _r

def constancy_find_by_intent(text, top_k=3, mindol_fallback=True):
    """恒常门·模糊查找：按意图检索可恢复任务（自然语言恢复，无 task_id 时）。
    v3.9.2：无高置信候选时降级 Mindol 语义检索兜底（kind=memory 片段候选）。"""
    try:
        return _get_constancy_inst().find_by_intent(text, top_k=top_k,
                                                    mindol_fallback=mindol_fallback)
    except Exception:
        return []

def constancy_recoverable():
    """恒常门：续而接——检索可恢复任务（paused/blocked 且未超时）"""
    return _get_constancy_inst().find_recoverable()

def constancy_snapshot(task_id):
    """恒常门：状态摘要快照"""
    return _get_constancy_inst().snapshot(task_id)

def constancy_suspend(task_id, reason=""):
    """恒常门：断而存——任务中断/切换时挂起"""
    _ok = _get_constancy_inst().suspend(task_id, reason)
    if _ok:
        _constancy_archive("suspend", task_id)
    return _ok

def constancy_resume(task_id):
    """恒常门：续而接——用户确认后恢复（completed/abandoned 永不自动恢复）"""
    _ok = _get_constancy_inst().resume(task_id)
    if _ok:
        _constancy_archive("resume", task_id)
    return _ok

def constancy_complete(task_id):
    """恒常门：标记完成"""
    _ok = _get_constancy_inst().complete(task_id)
    if _ok:
        _constancy_archive("complete", task_id)
    return _ok

def constancy_abandon(task_id, reason=""):
    """恒常门：标记用户放弃"""
    _ok = _get_constancy_inst().abandon(task_id, reason)
    if _ok:
        _constancy_archive("abandon", task_id)
    return _ok

def constancy_block(task_id, blocker_report):
    """恒常门：子任务受阻上报（status=blocked，上报父任务）"""
    _ok = _get_constancy_inst().block(task_id, blocker_report)
    if _ok:
        _constancy_archive("block", task_id)
    return _ok

_CONSTANCY_SYSTEM_MARKERS = (
    "memory writing agent",
    "you are a memory writing",
    "## memory writing",
    "consolidate raw memories and rollout summaries",
)


def _derive_completion_criteria(text):
    """轻量推导完成标准：取含完成语义的首句，否则全文截断"""
    import re as _re
    _sent = [_s.strip() for _s in _re.split(r"[。；;\n！？]", text) if _s.strip()]
    _keys = ("完成", "实现", "修复", "直到", "确保", "全部", "交付", "产出", "最终", "验收")
    for s in _sent:
        if any(k in s for k in _keys):
            return s[:2000]
    return text[:2000]


def _derive_pending_items(text):
    """轻量推导待办清单：提取编号/步骤句（最多 20 条）"""
    _items = []
    import re as _re
    for line in text.splitlines():
        _l = line.strip()
        if _re.match(r"^(\d+[.、]|[-*]\s|第一步|第二步|然后|接着|其次|最后)", _l):
            _items.append(_l[:200])
        if len(_items) >= 20:
            break
    return _items


def constancy_track_prompt(prompt, source="pre_reply", current_task_id=None,
                           turn_id=None):
    """恒常门·写侧接线：新用户意图 → begin；切换任务 → suspend 旧任务；同意图去重；恢复续接 → extend。
    返回 {"ok": True, "action": "begin"|"extend"|"none", "task_id": ...} 或 {"ok": False}
    """
    try:
        _txt = (prompt or "").strip()
        if not _txt or len(_txt) < 3:
            return {"ok": True, "action": "none", "task_id": ""}
        # P2: 系统输入过滤（记忆代理等非用户输入不入库）
        _low = _txt.lower()
        if any(_m in _low for _m in _CONSTANCY_SYSTEM_MARKERS):
            return {"ok": True, "action": "none", "task_id": ""}
        _reg = _get_constancy_inst()
        # 恢复续接：当前轮已恢复任务 → 不新建、不切换
        if current_task_id and bool(_reg.snapshot(current_task_id)):
            return {"ok": True, "action": "extend", "task_id": current_task_id}
        _rec = constancy_recoverable()
        _latest = _rec[0] if _rec else None
        if _latest and str(_latest.get("intent_summary", ""))[:50] == _txt[:50]:
            return {"ok": True, "action": "extend", "task_id": _latest.get("task_id", "")}
        if _latest:
            constancy_suspend(_latest["task_id"], reason="切换到新任务")
        _criteria = _derive_completion_criteria(_txt)
        _pending = _derive_pending_items(_txt)
        _ctx = {"source": source}
        if turn_id:
            _ctx["turn_id"] = str(turn_id)[:80]
        _r = constancy_begin(_txt, completion_criteria=_criteria,
                             pending_items=_pending, context=_ctx)
        return {"ok": bool(_r.get("ok")), "action": "begin",
                "task_id": _r.get("task_id", "")}
    except Exception:
        return {"ok": False, "action": "none", "task_id": ""}

def get_self_mirror():
    """获取自照镜（方向之镜）实例"""
    return _get_self_mirror_inst()

def mirror_tick():
    """自照镜：每轮调用——轮次+1，勇气信号 ×0.6 半衰期衰减"""
    return _get_self_mirror_inst().tick()

def mirror_add_courage(amount=0.5, reason="", pending=True):
    """自照镜：勇气信号——主动冒险获得超额收益 → P6 正面加权（对冲纠偏偏好）"""
    return _get_self_mirror_inst().add_courage(amount, reason, pending=pending)

def mirror_run_if_due(emergency=False):
    """自照镜：跟随守三深度复盘频率（每10轮或每日）触发自照，未到期静默跳过。
    emergency=True（守三应急复盘触发）：仅记录素材，不产出 P6 调权（定稿第九章）。
    温启动（运维手册 2.1）：连续跳过≥5次 或 距上次≥3天 → 强制轻量校准模式（仅统计，不产 P6 调权）。"""
    m = _get_self_mirror_inst()
    if m.should_mirror():
        m.reset_skip()
        return m.mirror(emergency=emergency)
    m.note_skip()
    if m.warm_start_due():
        m.reset_skip()
        return m.mirror(emergency=True, light=True)
    return None


def mirror_confirm_courage(confirmed=True):
    """自照镜：勇气信号下一轮用户交互确认（定稿第九章）——未负面反馈且任务目标达成 → 生效；否则归零"""
    return _get_self_mirror_inst().confirm_courage(bool(confirmed))

def mirror_status():
    """自照镜：状态查看"""
    return _get_self_mirror_inst().get_status()

def get_vault():
    """获取证据库实例"""
    return _get_vault_inst()

def evidence_record(rule_id, verdict, reason, source="auto", context=None):
    """去伪存真：记录证据判定"""
    v = _get_vault_inst()
    return v.record(rule_id, verdict, reason, source, context)
