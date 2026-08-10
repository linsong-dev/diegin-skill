#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""迭进 × Claude Code：SessionStart 适配器（session_start）

- 输入：Claude hooks stdin JSON（session_id）
- 输出：hookSpecificOutput.additionalContext 注入迭进规则常驻上下文（exit 0）
- 纪律：fail-open——契约异常时空输出 exit 0（不注入也不报错）
"""
import json
import sys

from diegin_claude_common import call_contract, ensure_utf8, make_envelope, read_stdin

HOOK_EVENT = "SessionStart"


def build_context(health: dict) -> str:
    """从契约 health 响应构造注入文本（无字段时用占位）。"""
    def g(*keys, default="?"):
        for k in keys:
            v = health.get(k)
            if v is not None and v != "":
                return v
        return default

    return (
        "[迭进] 全域常驻自我迭代进化系统已激活（钩子契约 v1 · Claude Code 适配器）。\n"
        "八元原则：攻七(正向强化) / 守三(负向纠错) / 一二不过三(三错熔断) / 举一反三(跨域泛化) / "
        "去伪存真(真伪门) / 裁决律(P0-P5) / 缓急律(节奏门) / 止观门(完形律)。\n"
        "引擎健康：total_rules=" + str(g("total_rules")) +
        " / active_rules=" + str(g("active_rules")) +
        " / entropy=" + str(g("entropy_status", "cognitive_entropy")) +
        " / snr=" + str(g("snr_status", "decision_snr")) +
        " / satisfaction=" + str(g("satisfaction")) + "。\n"
        "响应纪律：每轮回复开头输出 [迭进] 标记；工具调用前迭进预检；"
        "命中规则按裁决执行（block/audit/allow）；攻七推荐优先采用已验证做法。"
    )


def translate(resp: dict) -> tuple:
    """统一响应 → Claude hook 响应。(exit_code, stdout_text, stderr_text)"""
    if resp.get("error"):  # fail-open：契约/引擎异常时不注入，空输出 exit 0
        return (0, "", "")
    health = resp.get("health")
    if not isinstance(health, dict):
        health = {}
    ctx_text = build_context(health)
    out = {
        "hookSpecificOutput": {
            "hookEventName": HOOK_EVENT,
            "additionalContext": ctx_text,
        }
    }
    return (0, json.dumps(out, ensure_ascii=False), "")


def main() -> int:
    ensure_utf8()
    data = read_stdin()
    envelope = make_envelope(
        "session_start",
        session_id=data.get("session_id", "") or "",
        context={"platform": "claude", "hook": HOOK_EVENT},
    )
    resp = call_contract(envelope)
    code, out, err = translate(resp)
    if out:
        print(out)
    if err:
        sys.stderr.write(err)
        sys.stderr.flush()
    return code


if __name__ == "__main__":
    sys.exit(main())
