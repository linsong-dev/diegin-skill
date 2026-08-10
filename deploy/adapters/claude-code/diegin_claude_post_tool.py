#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""迭进 × Claude Code：PostToolUse 适配器（tool_post）

- 输入：Claude hooks stdin JSON（session_id / tool_name / tool_input）
- 行为：契约确认 + 健康上报；平台侧不注入、不阻断（空输出 exit 0）
"""
import sys

from diegin_claude_common import call_contract, ensure_utf8, make_envelope, read_stdin

HOOK_EVENT = "PostToolUse"


def translate(resp: dict) -> tuple:
    """统一响应 → Claude hook 响应。(exit_code, stdout_text, stderr_text)"""
    return (0, "", "")


def main() -> int:
    ensure_utf8()
    data = read_stdin()
    tool_input = data.get("tool_input")
    if not isinstance(tool_input, dict):
        tool_input = {}
    command = tool_input.get("command") or tool_input.get("text") or ""
    envelope = make_envelope(
        "tool_post",
        session_id=data.get("session_id", "") or "",
        tool={"name": data.get("tool_name", "") or "", "input": {"command": command}},
        context={"platform": "claude", "hook": HOOK_EVENT},
    )
    call_contract(envelope)  # 响应仅用于审计/健康上报；平台侧不阻断
    return 0


if __name__ == "__main__":
    sys.exit(main())