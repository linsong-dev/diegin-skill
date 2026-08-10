#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""迭进 × Claude Code：PreToolUse 适配器（tool_pre）

- 输入：Claude hooks stdin JSON（session_id / tool_name / tool_input / tool_use_id）
- 翻译：契约 block → permissionDecision deny（exit 0，现代官方语义）；
        allow/audit → 空输出 exit 0（audit 精神：记录不阻断）
- 纪律：fail-open——引擎/契约异常一律放行，不阻断业务

配置示例见同目录 settings.json.template。
"""
import json
import sys

from diegin_claude_common import call_contract, ensure_utf8, make_envelope, read_stdin

HOOK_EVENT = "PreToolUse"


def translate(resp: dict) -> tuple:
    """统一响应 → Claude hook 响应。(exit_code, stdout_text, stderr_text)"""
    decision = resp.get("decision", "allow")
    if decision == "block":
        reason = str(resp.get("reason") or "blocked by 迭进规则").strip()
        out = {
            "hookSpecificOutput": {
                "hookEventName": HOOK_EVENT,
                "permissionDecision": "deny",
                "permissionDecisionReason": "[迭进] " + reason,
            }
        }
        return (0, json.dumps(out, ensure_ascii=False), "")
    return (0, "", "")


def main() -> int:
    ensure_utf8()
    data = read_stdin()
    tool_input = data.get("tool_input")
    if not isinstance(tool_input, dict):
        tool_input = {}
    command = tool_input.get("command") or tool_input.get("text") or ""
    envelope = make_envelope(
        "tool_pre",
        session_id=data.get("session_id", "") or "",
        tool={"name": data.get("tool_name", "") or "", "input": {"command": command}},
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