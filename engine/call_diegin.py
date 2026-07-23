# 迭进DGEN 引擎入口(去伪存真真伪门: 言必有证->证必可验->验证为真)

"""

迭进 · DGEN 实战调用入口

迭进引擎入口

"""

import sys, json, os, re

import io

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

from pathlib import Path
from mindol.diegin_integration import memory_format_context, memory_archive



sys.path.insert(0, str(Path(__file__).parent))
from mindol.diegin_integration import memory_format_context, memory_archive

from evo.main import (get_rules_for_task, arbitrate, full_review, record_behavior,
                      health_check, run_maintenance, dgen_archive, mempalace_search,
                      auto_sandwich, record_user_feedback, auto_sandwich_trigger,
                      generalize_rule, generalize_from_patterns, generalize_cross_domain,
                      ensure_three_strikes, get_strike_status,
                      pace_classify, should_skip_deep_review,
                      get_pacemaker, get_closure,
                      closure_open, closure_close, closure_is_closed,
                      _get_engine, _get_tracker)
from evo.error_detector import ErrorDetector








def load_principle_rules(context: dict) -> list:
    """Load strike (一二不过三) + staging (举一反三) rules into arbitration pipeline"""
    engine = _get_engine()
    extra = []
    seen_ids = set()

    # 1. Get non-active but arbitration-relevant rules from engine
    all_rules = engine.get_interceptions(active_only=False)
    for rule in all_rules:
        lifecycle = getattr(rule, "lifecycle_status", "")
        if lifecycle in ("alerting", "staging", "critical", "blocking"):
            tags = getattr(rule, "tags", []) or []
            trigger = getattr(rule, "trigger_condition", "") or ""
            if trigger:
                if not engine._rule_applies_to_context(tags, context):
                    continue
                if not engine._match_condition(trigger, context):
                    continue
                extra.append(rule)
                seen_ids.add(rule.id)
            else:
                if engine._rule_applies_to_context(tags, context):
                    extra.append(rule)
                    seen_ids.add(rule.id)

    # 2. Load from tracker strikes_db for any missed strike records
    try:
        tracker = _get_tracker()
        db_path = tracker._strikes_db_path()
        if os.path.exists(db_path):
            with open(db_path, "r", encoding="utf-8") as f:
                strikes_db = json.load(f)
            for error_type, entry in strikes_db.items():
                count = entry.get("count", 0)
                if count < 2:
                    continue
                rule_id = "self_error_" + error_type
                if rule_id in seen_ids:
                    continue
                active_rules = engine.get_interceptions(active_only=True)
                if any(r.id == rule_id for r in active_rules):
                    continue
                temp_trigger = "error_type==" + repr(error_type)
                if not engine._match_condition(temp_trigger, context):
                    continue
                from evo.rule_engine import InterceptionRule as _IR
                nr = _IR(
                    id=rule_id,
                    trigger_condition=temp_trigger,
                    action="block_operation",
                    severity="high",
                    tags=["self_error", "one-two-no-three", "auto_block"],
                    logic_score=4.5,
                    outcome_score=3.5,
                    confidence=4.5,
                    source="auto_self_error_tracker",
                    lifecycle_status="active",
                    created_at=entry.get("first_seen", ""),
                    triggered_count=count
                )
                extra.append(nr)
                seen_ids.add(rule_id)
    except Exception as e:
        import sys as _sys
        print("[DG] load_principle_rules error: " + str(e), file=_sys.stderr)

    return extra

def evidence_filter(interceptions: list, context: dict) -> list:
    """去伪存真：过滤无证据支持的规则（带证据链记录）"""
    filtered = []
    try:
        from evo.main import evidence_record
    except ImportError:
        evidence_record = None

    for rule in interceptions:
        rid = getattr(rule, 'id', '?')
        lifecycle = getattr(rule, 'lifecycle_status', '')

        if lifecycle == 'active':
            filtered.append(rule)
            if evidence_record:
                evidence_record(rid, 'pass', 'active规则已通过验证', source='evidence_filter')
            continue

        if lifecycle == 'staging':
            triggered = getattr(rule, 'triggered_count', 0) or 0
            confidence = getattr(rule, 'confidence', 0) or 0
            if triggered >= 2 or confidence >= 4.5:
                filtered.append(rule)
                if evidence_record:
                    evidence_record(rid, 'pass', f'staging规则通过验证(触发={triggered},置信度={confidence})', source='evidence_filter')
                continue
            if evidence_record:
                evidence_record(rid, 'skip', f'staging规则证据不足(触发={triggered},置信度={confidence})', source='evidence_filter')
            continue

        filtered.append(rule)

    return filtered

def pre_check(context: dict) -> dict:

    """任务前预检 - 检索规则 + 仲裁（对齐 AGENTS.md 裁决格式）
    集成：缓急律（优先分流）→ 止观门（去重封存）→ 去伪存真 → 裁决律
    """

    # ========== P0: raw_chat 写入 Mindol ==========
    try:
        _chat_text = context.get("context", context.get("task", context.get("message", context.get("cmd", ""))))
        if _chat_text and len(str(_chat_text)) > 5:
            from mindol.diegin_integration import save_chat
            import threading
            _ = threading.Thread(target=save_chat, args=(str(_chat_text)[:2000],), daemon=True).start()
    except Exception:
        pass

    # ========== P3: 缓急律·优先分流 ==========
    from evo.main import pace_classify, should_skip_deep_review
    pace_result = pace_classify(context)
    skip_deep = should_skip_deep_review(context)

    # ========== P2: 止观门·去重封存 ==========
    from evo.main import closure_is_closed
    task_id = context.get("task_id", context.get("cmd", context.get("message", "")))
    if task_id and closure_is_closed(task_id):
        return {
            "matched_interceptions": 0,
            "matched_patterns": 0,
            "decision": "allow",
            "display_line": "[DGEN] PASS (止观门: 已封存事项，跳过)",
            "reason": "止观门: 该任务已封存，不再重复处理",
            "pace_result": pace_result,
            "closure_skip": True
        }

    rules = get_rules_for_task(context)

    # Five principle network: inject strike + staging rules
    extra_rules = load_principle_rules(context)
    if extra_rules:
        rules["interceptions"].extend(extra_rules)

    # 去伪存真：过滤无证据支持的规则
    rules["interceptions"] = evidence_filter(rules["interceptions"], context)

    # 缓急律：紧急任务跳过深度复盘标记
    if skip_deep:
        for r in rules["interceptions"]:
            if getattr(r, "lifecycle_status", "") == "active":
                pass  # 基础规则仍有效

    # ========== 去伪存真·Mindol语义上下文注入 ==========
    mindol_context = ""
    try:
        ctx_str = json.dumps(context, ensure_ascii=False)[:300]
        mindol_context = memory_format_context(query=ctx_str, top_k=3)
    except Exception:
        pass

    result = arbitrate(rules["interceptions"], rules["patterns"])

    return {
        "matched_interceptions": len(rules["interceptions"]),
        "matched_patterns": len(rules["patterns"]),
        "decision": result["decision"],
        "display_line": result.get("display_line", ""),
        "reason": result["reason"],
        "winning_rule_id": result.get("winning_rule_id"),
        "pace_result": pace_result,
        "mindol_context": mindol_context if mindol_context else "",
    }

def post_review(task_context: dict, task_result: dict) -> dict:

    """任务后复盘"""

    result = full_review(task_context, task_result)

    # ========== Mindol 语义归档 ==========
    try:
        ctx_str = json.dumps(task_context, ensure_ascii=False)[:200]
        res_str = json.dumps(task_result, ensure_ascii=False)[:200]
        memory_archive("post_review", f"{result.get('decision','?')} | ctx={ctx_str} | res={res_str}")
    except Exception:
        pass

    return result





def system_health() -> dict:

    """系统健康度"""

    return health_check()





if __name__ == "__main__":

    import sys

    if len(sys.argv) < 2:

        print("用法: python call_diegin.py <check|review|health|maintain|archive|search> [args...]")

        sys.exit(1)



    mode = sys.argv[1]



    if mode == "check" or mode == "stdin":

        if len(sys.argv) > 2:

            raw = sys.argv[2]

        else:

            raw = sys.stdin.read().strip()

        ctx = json.loads(raw)

        result = pre_check(ctx)

        print(json.dumps(result, ensure_ascii=False, indent=2))



    elif mode == "check_file":

        fp = sys.argv[2]

        with open(fp, 'r', encoding='utf-8-sig') as f:

            ctx = json.loads(f.read())  # Handle BOM

        result = pre_check(ctx)

        print(json.dumps(result, ensure_ascii=False, indent=2))



    elif mode == "review":

        ctx = json.loads(sys.argv[2]) if len(sys.argv) > 2 else {"task_id": "unknown"}

        result = json.loads(sys.argv[3]) if len(sys.argv) > 3 else {"status": "completed"}

        result = post_review(ctx, result)

        print(json.dumps(result, ensure_ascii=False, indent=2))



    elif mode == "health":

        import io

        old_out = sys.stdout

        sys.stdout = io.StringIO()

        result = system_health()

        sys.stdout = old_out

        print(json.dumps(result, ensure_ascii=False, indent=2))



    elif mode == "maintain":

        run_maintenance()



    elif mode == "archive":

        content = sys.argv[2] if len(sys.argv) > 2 else sys.stdin.read()

        source = sys.argv[3] if len(sys.argv) > 3 else "dgen_cli"

        ok = dgen_archive(content, source)

        print(json.dumps({"ok": ok}, ensure_ascii=False))



    elif mode == "search":

        query = sys.argv[2] if len(sys.argv) > 2 else ""

        results = mempalace_search(query)

        print(json.dumps(results, ensure_ascii=False, indent=2))



    elif mode == "feedback":

        """用户反馈三态模型"""

        rule_id = sys.argv[2] if len(sys.argv) > 2 else ""

        feedback = sys.argv[3] if len(sys.argv) > 3 else "silent"

        user_action = sys.argv[4] if len(sys.argv) > 4 else None

        result = record_user_feedback(rule_id, feedback, user_action)

        print(json.dumps(result, ensure_ascii=False, indent=2, default=str))



    elif mode == "sandwich":

        """守三攻七复盘（自动钩子版）：python call_diegin.py sandwich <task_type> '<pos_json>' '<neg_json>'"""

        task_type = sys.argv[2] if len(sys.argv) > 2 else "general"

        positive = json.loads(sys.argv[3]) if len(sys.argv) > 3 else []

        negative = json.loads(sys.argv[4]) if len(sys.argv) > 4 else []

        result = auto_sandwich_trigger(task_type, positive, negative)

        print(json.dumps(result, ensure_ascii=False, indent=2))



    

    elif mode == "suggest":

        """攻七：返回与当前上下文匹配的成功模式建议（引擎级匹配）

        用法: python call_diegin.py suggest '<context_json>'

        支持:

          纯文本: 自动转为 {"prompt": "<text>"}

          JSON: 直接作为上下文，支持 tool/op/task_type 等字段

        """

        if not sys.stdin.isatty():
            raw = sys.stdin.read().strip()
        elif len(sys.argv) > 2:
            raw = sys.argv[2]
        else:
            raw = ""

        from evo.main import _get_engine, _get_arbiter

        engine = _get_engine()

        # 解析输入

        try:

            context = json.loads(raw)

        except json.JSONDecodeError:

            context = {"prompt": raw, "task_type": "general", "op": "unknown"}

        # 双通道仲裁：先检查守三是否有拦截

        interceptions = engine.get_interceptions(active_only=True)

        matched_inters = []

        for rule in interceptions:

            if engine._match_condition(rule.trigger_condition, context):

                matched_inters.append(rule)

        arbiter_obj = _get_arbiter()

        arb_result = arbiter_obj.resolve(matched_inters, [])

        is_blocked = arb_result.decision.value in ("BLOCK", "IRON_WALL_BLOCK", "ESCALATE")

        # 用引擎匹配（复用 _match_condition AST解析器）

        matched = engine.match_patterns(context, top_k=5)

        suggestions = []

        for p in matched:

            suggestions.append({

                "id": p.id if hasattr(p, 'id') else '',

                "scenario": p.trigger_scenario if hasattr(p, 'trigger_scenario') else '',

                "decision": p.decision_logic if hasattr(p, 'decision_logic') else '',

                "confidence": getattr(p, 'confidence', 0),

                "auto_promoted": getattr(p, 'auto_promoted', False),

            })

        result = {

            "suggestions": [] if is_blocked else suggestions,

            "count": 0 if is_blocked else len(suggestions),

            "total_patterns": len(engine.get_patterns(active_only=True)),

            "matched_via": "engine_ast",

            "guard_decision": arb_result.decision.value if hasattr(arb_result, 'decision') else 'ALLOW',

            "guard_blocked": is_blocked,

            "guard_reason": arb_result.reason if is_blocked else "",

        }

        print(json.dumps(result, ensure_ascii=False, indent=2))

        # 按关键词匹配排序

    elif mode == "record_success":

        """攻七：记录一次成功的工具调用（简化版，自动提取成功模式）

        用法: python call_diegin.py record_success <tool_name>

        """

        tool_name = sys.argv[2] if len(sys.argv) > 2 else "unknown"

        from evo.main import auto_sandwich_trigger

        result = auto_sandwich_trigger(f"tool_{tool_name.replace('.','_')}", positive=[tool_name], negative=[])

        print(json.dumps(result, ensure_ascii=False, indent=2, default=str))
    elif mode == "record_error":
        """一二不过三：记录并追踪一次错误
        用法: python call_diegin.py record_error <error_type> [detail] [severity]
        第1次：自动创建拦截规则
        第2次：加固规则
        第3次：写 override.json 强制阻断
        """
        error_type = sys.argv[2] if len(sys.argv) > 2 else "unknown"
        detail = sys.argv[3] if len(sys.argv) > 3 else ""
        severity = sys.argv[4] if len(sys.argv) > 4 else "high"
        result = ensure_three_strikes(error_type, detail, severity)
        print(json.dumps(result, ensure_ascii=False, indent=2, default=str))
    elif mode == "arbitrate_detail":
        """去伪存真：完整冲突仲裁详情（带规则冲突分析）
        用法: echo '<context_json>' | python call_diegin.py arbitrate_detail
        或: python call_diegin.py arbitrate_detail '<context_json>'
        返回: 完整冲突集、胜出规则、降级信息、仲裁链路
        """
        if len(sys.argv) > 2:
            raw = sys.argv[2]
        else:
            raw = sys.stdin.read().strip()
        ctx = json.loads(raw)
        rules = get_rules_for_task(ctx)
        result = arbitrate(rules["interceptions"], rules["patterns"])
        output = {
            "matched_interceptions": len(rules["interceptions"]),
            "matched_patterns": len(rules["patterns"]),
            "decision": result["decision"],
            "reason": result["reason"],
            "winning_rule_id": result.get("winning_rule_id"),
            "conflict_rules": [
                {"id": r.id, "severity": getattr(r, "severity", "?"), "reason": getattr(r, "reason", "")}
                for r in rules["interceptions"]
            ] if rules["interceptions"] else [],
            "degradation": result.get("degradation_type", ""),
        }
        print(json.dumps(output, ensure_ascii=False, indent=2, default=str))


    elif mode == "verify":
        """去伪存真：一致性验证（跨检查对比）
        用法: python call_diegin.py verify '<current_check_json>' [last_check_file]
        比较当前检查结果与上一次检查，检测决策是否反转
        """
        import os as _os
        raw = sys.argv[2] if len(sys.argv) > 2 else sys.stdin.read().strip()
        current = json.loads(raw) if raw else {}
        last_file = sys.argv[3] if len(sys.argv) > 3 else _os.path.join(_os.path.dirname(__file__), "..", "var", "state", "last_check_result.json")
        result = {
            "current_decision": current.get("decision", "unknown"),
            "consistency": "first_check",
            "flip_detected": False,
        }
        if _os.path.exists(last_file):
            try:
                with open(last_file, "r", encoding="utf-8") as f:
                    last = json.load(f)
                prev = last.get("decision", "unknown")
                curr = current.get("decision", "unknown")
                if prev != curr:
                    result["consistency"] = "flipped"
                    result["flip_detected"] = True
                    result["previous_decision"] = prev
                    result["reason"] = f"决策反转: {prev} → {curr}, 需人工确认"
                else:
                    result["consistency"] = "consistent"
            except Exception:
                pass
        # 保存当前结果供下次对比
        try:
            _os.makedirs(_os.path.dirname(last_file), exist_ok=True)
            with open(last_file, "w", encoding="utf-8") as f:
                json.dump(current, f, ensure_ascii=False)
        except Exception:
            pass
        print(json.dumps(result, ensure_ascii=False, indent=2, default=str))








    elif mode == "verify_rules":
        """去伪存真·验证增强：批量验证规则库质量"""
        import os as _os_vr, json as _j_vr

        rules_path = _os_vr.path.join(_os_vr.path.dirname(__file__), "evo", "rules", "interception_rules.json")
        patterns_path = _os_vr.path.join(_os_vr.path.dirname(__file__), "evo", "rules", "success_patterns.json")

        rules = []
        if _os_vr.path.exists(rules_path):
            with open(rules_path, "r", encoding="utf-8") as f:
                rules = _j_vr.load(f)

        patterns = []
        if _os_vr.path.exists(patterns_path):
            with open(patterns_path, "r", encoding="utf-8") as f:
                patterns = _j_vr.load(f)

        checks = {"passed": 0, "warnings": 0, "errors": 0, "items": []}

        # 检查每条拦截规则
        for rule in rules:
            rid = rule.get("id", "?")
            items = []

            # 1. 必须有关键字段
            if not rule.get("trigger_condition"):
                items.append({"severity": "error", "msg": f"{rid}: 缺少 trigger_condition"})
            if not rule.get("action"):
                items.append({"severity": "error", "msg": f"{rid}: 缺少 action"})

            # 2. 必须有原则归属标签
            tags = rule.get("tags", [])
            tag_str = " ".join(tags)
            principle_tags = [t for t in tags if "principle:" in t]
            if not principle_tags:
                # 推断归属
                lifecycle = rule.get("lifecycle_status", "")
                source = rule.get("source", "")
                if lifecycle in ("blocking", "critical") or "self_error" in tag_str:
                    inferred = "principle:一二不过三"
                elif lifecycle in ("staging", "cached") or "举一反三" in tag_str:
                    inferred = "principle:举一反三"
                elif source == "war_game" or "pattern" in tag_str:
                    inferred = "principle:攻七"
                else:
                    inferred = "principle:守三"
                items.append({"severity": "warning", "msg": f"{rid}: 缺少principle标签，推断为 {inferred}"})

            # 3. 检查置信度合理性
            conf = rule.get("confidence", 0)
            if conf <= 0:
                items.append({"severity": "error", "msg": f"{rid}: 置信度为0，规则无效"})
            elif conf < 2.0:
                items.append({"severity": "warning", "msg": f"{rid}: 置信度过低({conf})，建议降权"})

            # 4. 严重度标签标准
            sev = rule.get("severity", "")
            if sev not in ("critical", "high", "medium", "low"):
                items.append({"severity": "warning", "msg": f"{rid}: 严重度'{sev}'非标准值(critical/high/medium/low)"})

            # 汇总
            for item in items:
                if item["severity"] == "error":
                    checks["errors"] += 1
                elif item["severity"] == "warning":
                    checks["warnings"] += 1
                if item not in checks["items"]:
                    checks["items"].append(item)
            if not items:
                checks["passed"] += 1

        # 检查规则间冲突
        for i, r1 in enumerate(rules):
            for r2 in rules[i+1:]:
                if r1.get("id") == r2.get("id"):
                    continue
                c1 = r1.get("trigger_condition", "")
                c2 = r2.get("trigger_condition", "")
                a1 = r1.get("action", "")
                a2 = r2.get("action", "")
                # 相同触发条件但不同动作 → 潜在冲突
                if c1 and c2 and c1 == c2 and a1 != a2:
                    checks["items"].append({
                        "severity": "warning",
                        "msg": f"规则冲突: {r1['id']}和{r2['id']} 触发条件相同但动作不同"
                    })
                    checks["warnings"] += 1

        result = {
            "principle": "去伪存真·规则验证",
            "total_rules": len(rules),
            "total_patterns": len(patterns),
            "checks": checks,
            "health": "good" if checks["errors"] == 0 else "needs_attention",
        }
        print(_j_vr.dumps(result, ensure_ascii=False, indent=2, default=str))

    elif mode == "generalize_cross_domain":

        """举一反三：跨域泛化"""

        result = generalize_cross_domain()

        print(json.dumps({"created": result}, ensure_ascii=False, indent=2))


    elif mode == "generalize_patterns":

        """举一反三：从成功模式泛化为拦截规则"""

        result = generalize_from_patterns()

        print(json.dumps({"created": result}, ensure_ascii=False, indent=2))


    elif mode == "pace_check":
        """缓急律：检查当前任务类型分类"""
        if len(sys.argv) > 2:
            ctx = json.loads(sys.argv[2])
        else:
            ctx = json.loads(sys.stdin.read().strip() or "{}")
        pm = get_pacemaker()
        result = pm.classify(ctx)
        print(json.dumps(result, ensure_ascii=False, indent=2, default=str))

    elif mode == "pace_status":
        """缓急律：查看调度器状态"""
        pm = get_pacemaker()
        result = pm.get_status()
        print(json.dumps(result, ensure_ascii=False, indent=2, default=str))

    elif mode == "pace_status":
        """缓急律：查看调度器状态"""
        pm = get_pacemaker()
        result = pm.get_status()
        print(json.dumps(result, ensure_ascii=False, indent=2, default=str))

    elif mode == "closure_open":
        """止观门：打开一个事项"""
        item_id = sys.argv[2]
        desc = sys.argv[3] if len(sys.argv) > 3 else ""
        cg = get_closure()
        result = cg.open(item_id, desc)
        print(json.dumps(result, ensure_ascii=False, indent=2))

    elif mode == "closure_close":
        """止观门：封存一个事项"""
        item_id = sys.argv[2]
        summary = sys.argv[3] if len(sys.argv) > 3 else ""
        cg = get_closure()
        result = cg.close(item_id, summary)
        print(json.dumps(result, ensure_ascii=False, indent=2))

    elif mode == "closure_status":
        """止观门：查看封存状态"""
        cg = get_closure()
        result = cg.get_status()
        print(json.dumps(result, ensure_ascii=False, indent=2, default=str))

    elif mode == "evidence_status":
        """去伪存真：查看证据库状态"""
        try:
            from evo.main import get_vault
            v = get_vault()
            result = v.get_stats()
        except Exception as e:
            result = {"error": str(e), "principle": "去伪存真·证据库"}
        print(json.dumps(result, ensure_ascii=False, indent=2, default=str))

    elif mode == "evidence_trail":
        """去伪存真：查看最近证据链"""
        try:
            from evo.main import get_vault
            v = get_vault()
            result = {"principle": "去伪存真·证据链", "recent": v.get_recent(15)}
        except Exception as e:
            result = {"error": str(e)}
        print(json.dumps(result, ensure_ascii=False, indent=2, default=str))

    elif mode == "generalize":

        """举一反三：从单条或所有规则推导跨场景候选规则"""

        rule_id = sys.argv[2] if len(sys.argv) > 2 else None

        result = generalize_rule(rule_id)

        print(json.dumps(result, ensure_ascii=False, indent=2, default=str))



    elif mode == "sandwich_legacy":

        """守三攻七复盘（旧版无钩子）：python call_diegin.py sandwich_legacy <task_type> '<pos_json>' '<neg_json>'"""

        task_type = sys.argv[2] if len(sys.argv) > 2 else "general"

        positive = json.loads(sys.argv[3]) if len(sys.argv) > 3 else []

        negative = json.loads(sys.argv[4]) if len(sys.argv) > 4 else []

        result = auto_sandwich(positive, negative, task_type)

        print(json.dumps(result, ensure_ascii=False, indent=2))



    elif mode == "dgen_check":

        """全量预检：检索+仲裁+归档到MemPalace（一次性完整调用）"""

        ctx = json.loads(sys.argv[2]) if len(sys.argv) > 2 else {}

        result = pre_check(ctx)

        print(json.dumps(result, ensure_ascii=False, indent=2))



    elif mode == "activate":

        """

        统一接入入口：任何对话中执行此命令实现迭进接入。

        效果：加载规则库   健康检查   输出接入摘要

        """

        from evo.main import self_check

        from datetime import datetime

        

        # 加载并自检

        check_ok = self_check()

        import io

        _old_stdout, sys.stdout = sys.stdout, io.StringIO()

        health = system_health()

        sys.stdout = _old_stdout

        

        # 组装接入报告

        report = {

            "status": "activated" if check_ok else "failed",

            "activated_at": datetime.now().isoformat(),

            "engine": "迭进-diegin",

            "interception_rules": health.get("interception_rules", 0),

            "success_patterns": health.get("success_patterns", 0),

            "meta_experiences": health.get("meta_experiences", 0),

            "precedents": health.get("precedents", 0),

            "health_summary": health,

            "note": "迭进已就绪。使用规则: 守三攻七+一二不过三+三态反馈"

        }

        print(json.dumps(report, ensure_ascii=False, indent=2, default=str))
    elif mode == "analyze":
        """Analyze tool execution result and record strikes (post-tool analysis)"""
        ctx = json.loads(sys.argv[2] if len(sys.argv) > 2 else sys.stdin.read().strip())
        tool_name = ctx.get("tool_name", ctx.get("tool", ""))
        exit_code = ctx.get("exit_code", ctx.get("exit", 0))
        cmd = ctx.get("cmd", ctx.get("command", ""))
        error_out = ctx.get("error", ctx.get("stderr", ctx.get("err", "")))
        stdout_out = ctx.get("stdout", ctx.get("out", ""))

        if tool_name in ("Bash", "PowerShell", "Shell", "cmd"):
            op = "cmd"
        elif "git" in tool_name.lower() or "git" in cmd.lower():
            op = "git_push"
        elif tool_name in ("FileWrite", "file_write", "write"):
            op = "file_write"
        else:
            op = "cmd"

        if exit_code == 0 and not error_out:
            result = {"action": "skip", "reason": "no error"}
            print(json.dumps(result, ensure_ascii=False, indent=2, default=str))
        else:
            detect_ctx = {
                "op": op, "cmd": cmd, "exit": exit_code,
                "out": stdout_out, "err": error_out,
                "dur": ctx.get("dur", ctx.get("duration", 0)),
                "path": ctx.get("path", ctx.get("file", "")),
            }
            detector = ErrorDetector()  # Uses singleton tracker
            result = detector.detect_and_record(detect_ctx)
            print(json.dumps(result or {}, ensure_ascii=False, indent=2, default=str))

    elif mode == "record_error":
        """Record a self-detected error for one-two-no-three tracking"""
        ctx = json.loads(sys.argv[2] if len(sys.argv) > 2 else sys.stdin.read().strip())
        error_type = ctx.get("error_type", ctx.get("type", "unknown"))
        detail = ctx.get("detail", ctx.get("error", ""))
        severity = ctx.get("severity", "high")
        result = ensure_three_strikes(error_type, detail, severity)
        print(json.dumps(result or {}, ensure_ascii=False, indent=2, default=str))

    elif mode == "generate_fix":
        ctx = json.loads(sys.argv[2] if len(sys.argv) > 2 else sys.stdin.read().strip())
        error_type = ctx.get("error_type", ctx.get("type", ctx.get("detected_type", "unknown")))
        detail = ctx.get("detail", ctx.get("error", ""))
        severity = ctx.get("severity", "high")
        cmd = ctx.get("cmd", ctx.get("command", ""))
        tool_name = ctx.get("tool_name", ctx.get("tool", ""))

        strike_result = ensure_three_strikes(error_type, detail, severity)

        fix_suggestion = {}
        fix_suggestion["error_type"] = error_type
        fix_suggestion["detail"] = detail
        fix_suggestion["severity"] = severity
        fix_suggestion["strike_action"] = strike_result.get("action", "recorded")
        fix_suggestion["fix_available"] = False

        if "encoding" in error_type.lower() or "encode" in detail.lower():
            fix_suggestion["fix_available"] = True
            fix_suggestion["fix_type"] = "encoding"
            fix_suggestion["fix_instruction"] = ('在文件写入操作中显式指定 encoding="utf-8" 参数, '
                                                  "避免系统默认编码导致的 UnicodeEncodeError")
            fix_suggestion["verify_steps"] = ["检查 exit_code=0", "检查输出无乱码"]

        elif "command" in error_type.lower() or "syntax" in detail.lower():
            fix_suggestion["fix_available"] = True
            fix_suggestion["fix_type"] = "command_syntax"
            if cmd:
                fix_suggestion["fix_instruction"] = "命令语法可能存在问题: " + cmd[:100]
            else:
                fix_suggestion["fix_instruction"] = "检查命令语法、参数路径、环境依赖是否正确"
            fix_suggestion["verify_steps"] = ["检查 exit_code=0", "验证输出符合预期"]

        elif "timeout" in error_type.lower() or "timeout" in detail.lower():
            fix_suggestion["fix_available"] = True
            fix_suggestion["fix_type"] = "timeout"
            fix_suggestion["fix_instruction"] = "操作超时，建议增加超时时间、分步骤执行或改用异步方式"
            fix_suggestion["verify_steps"] = ["重新执行并检查是否完成"]

        elif "git" in error_type.lower() or "git" in tool_name.lower():
            fix_suggestion["fix_available"] = True
            fix_suggestion["fix_type"] = "git"
            fix_suggestion["fix_instruction"] = "Git操作失败，建议检查网络连接、认证信息、远程仓库状态"
            fix_suggestion["verify_steps"] = ["检查 git remote -v", "检查认证状态", "重新尝试"]

        else:
            fix_suggestion["fix_instruction"] = "检测到错误: " + detail[:100] + "，建议检查操作参数和环境配置"
            fix_suggestion["verify_steps"] = ["分析错误日志", "修正参数后重试"]

        output = {
            "fix": fix_suggestion,
            "strike": strike_result,
            "principle": "一二不过三·立改",
            "note": "fix_instruction 包含建议的修复操作，执行后请调用 verify_fix 验证"
        }
        print(json.dumps(output, ensure_ascii=False, indent=2, default=str))

    elif mode == "verify_fix":
        ctx = json.loads(sys.argv[2] if len(sys.argv) > 2 else sys.stdin.read().strip())
        error_type = ctx.get("error_type", "unknown")
        fix_exit_code = ctx.get("exit_code", ctx.get("exit", -1))
        fix_error = ctx.get("error", ctx.get("err", ""))

        verified = fix_exit_code == 0 and not fix_error
        result = {
            "error_type": error_type,
            "verified": verified,
            "exit_code": fix_exit_code,
            "detail": "修复验证通过" if verified else "修复验证失败: exit=" + str(fix_exit_code),
            "principle": "一二不过三·改毕验",
        }

        if verified:
            result["reset_strike"] = True
            result["success_pattern_eligible"] = True
            result["next_step"] = "修复成功，可纳入攻七成功模式"
        else:
            result["reset_strike"] = False
            result["next_step"] = "修复失败，请检查 fix_instruction 后重试，或进入第2次阻断流程"

        print(json.dumps(result, ensure_ascii=False, indent=2, default=str))
    elif mode == "deep_review":
        """守三·深度复盘：系统性回顾strike日志并生成改进建议"""
        import json as _j, os as _o
        import datetime as _dt

        strikes_path = _o.path.join(_o.path.dirname(_o.path.dirname(__file__)), "var", "state", "strikes_db.json")
        overrides_path = _o.path.join(_o.path.dirname(_o.path.dirname(__file__)), "var", "state", "dgen_overrides.json")

        strikes = {}
        if _o.path.exists(strikes_path):
            with open(strikes_path, "r", encoding="utf-8") as f:
                strikes = _j.load(f)

        overrides = []
        if _o.path.exists(overrides_path):
            with open(overrides_path, "r", encoding="utf-8") as f:
                overrides = _j.load(f)

        # 分析
        total_errors = len(strikes)
        total_strikes = sum(e.get("count", 0) for e in strikes.values())
        high_severity = sum(1 for e in strikes.values() if e.get("severity", "") in ("high", "critical"))
        blocked = len(overrides)

        # 按错误频率排序
        sorted_errors = sorted(strikes.items(), key=lambda x: -x[1].get("count", 0))

        # 生成改进建议
        suggestions = []
        for error_type, entry in sorted_errors:
            count = entry.get("count", 0)
            sev = entry.get("severity", "medium")
            if count >= 3:
                suggestions.append(f"[P0] {error_type}: 已触发{count}次(严重度:{sev})，建议: 推翻现有阻断方案，升级处理")
            elif count >= 2:
                suggestions.append(f"[P1] {error_type}: 已触发{count}次(严重度:{sev})，建议: 阻断已生效，持续监控")
            elif count >= 1:
                suggestions.append(f"[P2] {error_type}: 已触发{count}次(严重度:{sev})，建议: 保持警觉")

        # 未阻断的高频错误
        unblocked = []
        for error_type, entry in sorted_errors:
            count = entry.get("count", 0)
            if count >= 2:
                already_blocked = any(
                    o.get("blocked_error_type") == error_type for o in overrides
                )
                if not already_blocked:
                    unblocked.append(error_type)

        report = {
            "generated_at": _dt.datetime.now().isoformat(),
            "principle": "守三·深度复盘",
            "statistics": {
                "total_error_types": total_errors,
                "total_strikes": total_strikes,
                "high_severity_count": high_severity,
                "blocked_count": blocked,
                "unblocked_high_count": len(unblocked),
            },
            "error_ranking": [
                {"error_type": et, "count": e.get("count", 0), "severity": e.get("severity", "medium")}
                for et, e in sorted_errors[:10]
            ],
            "suggestions": suggestions,
            "unblocked_high_risk": unblocked,
            "next_step": "建议执行 deep_review_apply 应用本次复盘结果" if unblocked else "系统状态良好"
        }

        print(_j.dumps(report, ensure_ascii=False, indent=2, default=str))

    elif mode == "deep_review_apply":
        """守三·深度复盘：执行复盘结果——自动补全未阻断的高频错误"""
        import json as _j2, os as _o2

        strikes_path = _o2.path.join(_o2.path.dirname(_o2.path.dirname(__file__)), "var", "state", "strikes_db.json")
        overrides_path = _o2.path.join(_o2.path.dirname(_o2.path.dirname(__file__)), "var", "state", "dgen_overrides.json")
        legacy_path = _o2.path.join(_o2.path.dirname(_o2.path.dirname(__file__)), "var", "state", "dgen_override.json")

        strikes = {}
        if _o2.path.exists(strikes_path):
            with open(strikes_path, "r", encoding="utf-8") as f:
                strikes = _j2.load(f)

        overrides = []
        if _o2.path.exists(overrides_path):
            with open(overrides_path, "r", encoding="utf-8") as f:
                overrides = _j2.load(f)

        # 为所有count>=2但未阻断的错误新建阻断
        new_blocks = []
        for error_type, entry in strikes.items():
            count = entry.get("count", 0)
            if count >= 2:
                already_blocked = any(
                    o.get("blocked_error_type") == error_type for o in overrides
                )
                if not already_blocked:
                    new_entry = {
                        "blocked_error_type": error_type,
                        "strike_count": count,
                        "blocked_at": entry.get("last_seen", ""),
                        "last_detail": entry.get("last_detail", ""),
                        "cause": {"verdict": "internal", "reason": "守三·深度复盘自动补全"},
                        "escalated": True if count >= 3 else False,
                        "reason": f"守三·深度复盘: {error_type} 已触发{count}次，自动创建阻断"
                    }
                    overrides.append(new_entry)
                    new_blocks.append(error_type)

        if new_blocks:
            with open(overrides_path, "w", encoding="utf-8") as f:
                _j2.dump(overrides, f, ensure_ascii=False, indent=2)
            # 同步 legacy
            if overrides:
                legacy = overrides[0]
                for o in overrides:
                    if o.get("escalated"):
                        legacy = o
                        break
                with open(legacy_path, "w", encoding="utf-8") as f:
                    _j2.dump(legacy, f, ensure_ascii=False, indent=2)

        result = {
            "principle": "守三·深度复盘-应用",
            "new_blocks_created": len(new_blocks),
            "blocked_types": new_blocks,
            "total_overrides": len(overrides),
        }
        print(_j2.dumps(result, ensure_ascii=False, indent=2, default=str))









