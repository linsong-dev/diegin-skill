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
        效果：加载规则库 → 健康检查 → 输出接入摘要
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





