"""
dgen_pre_check_runner.py — 由 OpenClaw 插件调用的 Python 桥接脚本。
通过 stdin 接收 JSON（task context），输出 JSON 预检结果到 stdout。

统一委托给 call_diegin.pre_check()，消除与 evo.main 的仲裁重复。
"""
import json, sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from call_diegin import pre_check

def main():
    context_str = sys.stdin.read().strip()
    if not context_str:
        print(json.dumps({"error": "No input received"}, ensure_ascii=False))
        return 1

    try:
        context = json.loads(context_str)
    except json.JSONDecodeError as e:
        print(json.dumps({"error": f"Invalid JSON input: {e}"}, ensure_ascii=False))
        return 1

    try:
        result = pre_check({
            "task_type": context.get("task_type", "question"),
            "channel": context.get("channel", "direct_chat"),
            "context": context.get("context", ""),
            "keywords": context.get("keywords", ""),
        })
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 0
    except Exception as e:
        print(json.dumps({"error": f"{type(e).__name__}: {e}"}, ensure_ascii=False))
        return 1

if __name__ == "__main__":
    sys.exit(main())