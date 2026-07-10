"""
dgen_pre_check_runner.py
由 dgen OpenClaw 插件调用的 Python 桥接脚本。
通过 stdin 接收 JSON（task context），输出 JSON 预检结果到 stdout。
"""

import json
import sys
import os
from dataclasses import asdict

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "evo"))


def safe_get(obj, key, default=""):
    """Safely get attribute from dataclass or key from dict."""
    if hasattr(obj, key):
        val = getattr(obj, key)
    elif isinstance(obj, dict):
        val = obj.get(key, default)
    else:
        return default
    if val is None:
        return default
    return str(val)[:100]


def main():
    # Read context JSON from stdin
    context_str = sys.stdin.read().strip()
    if not context_str:
        print(json.dumps({"error": "No input received"}, ensure_ascii=False))
        return 1

    try:
        context = json.loads(context_str)
    except json.JSONDecodeError as e:
        print(json.dumps({"error": f"Invalid JSON input: {e}"}, ensure_ascii=False))
        return 1

    ctx = {
        "task_type": context.get("task_type", "question"),
        "channel": context.get("channel", "direct_chat"),
        "context": context.get("context", ""),
        "keywords": context.get("keywords", ""),
    }

    try:
        from rule_engine import RuleEngine

        eng = RuleEngine()
        eng._load_all()

        result = eng.retrieve_for_task(ctx)
        interceptions = result.get("interceptions", [])
        patterns = result.get("patterns", [])

                # Arbitration
        arbitration = {}
        try:
            from evo.main import arbitrate as main_arbitrate
            arb_result = main_arbitrate(interceptions, patterns)
            arbitration = {
                "decision": arb_result.get("decision", "allow"),
                "display_line": arb_result.get("display_line", ""),
                "reason": arb_result.get("reason", ""),
                "winning_rule_id": arb_result.get("winning_rule_id"),
            }
        except ImportError:
            pass

        # Fallback resolve (only if primary arbitration returned empty)
        if not arbitration:
            if interceptions:
                severities = [safe_get(r, "severity", "low") for r in interceptions]
                if "critical" in severities:
                    action = "iron_wall_block"
                elif any(s in ("high") for s in severities):
                    action = "block"
                elif "medium" in severities:
                    action = "escalate"
                else:
                    action = "allow"
            else:
                action = "allow"
            arbitration = {"decision": action, "display_line": "", "reason": "fallback", "winning_rule_id": None}
        # Build safe output (dataclass or dict)
        out_interceptions = []
        for r in interceptions[:5]:
            out_interceptions.append({
                "id": safe_get(r, "id", "?"),
                "description": safe_get(r, "description", ""),
            })

        out_patterns = []
        for p in patterns[:5]:
            out_patterns.append({
                "id": safe_get(p, "id", "?"),
                "description": safe_get(p, "description", ""),
            })

        output = {
            "interception_count": len(interceptions),
            "pattern_count": len(patterns),
            "interceptions": out_interceptions,
            "patterns": out_patterns,
            "arbitration": arbitration,
        }

        print(json.dumps(output, ensure_ascii=False))
        return 0

    except Exception as e:
        print(json.dumps({"error": f"{type(e).__name__}: {e}"}, ensure_ascii=False))
        return 1


if __name__ == "__main__":
    sys.exit(main())



