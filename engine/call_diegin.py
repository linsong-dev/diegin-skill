# 迭进DGEN 引擎入口(去伪存真真伪门: 言必有证->证必可验->验证为真)

"""

迭进 · DGEN 实战调用入口

迭进引擎入口

"""

import sys, json, os

import io

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

from pathlib import Path



sys.path.insert(0, str(Path(__file__).parent))

from evo.main import (get_rules_for_task, arbitrate, full_review, record_behavior,

                      health_check, run_maintenance, dgen_archive, mempalace_search,

                      auto_sandwich, record_user_feedback, auto_sandwich_trigger, generalize_rule)





def pre_check(context: dict) -> dict:

    """任务前预检 - 检索规则 + 仲裁（对齐 AGENTS.md 裁决格式）"""

    rules = get_rules_for_task(context)

    result = arbitrate(rules["interceptions"], rules["patterns"])

    return {

        "matched_interceptions": len(rules["interceptions"]),

        "matched_patterns": len(rules["patterns"]),

        "decision": result["decision"],

        "display_line": result.get("display_line", ""),

        "reason": result["reason"],

        "winning_rule_id": result.get("winning_rule_id"),

    }

def post_review(task_context: dict, task_result: dict) -> dict:

    """任务后复盘"""

    result = full_review(task_context, task_result)

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









