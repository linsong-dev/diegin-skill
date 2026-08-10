#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""迭进 × Claude Code：Stop 适配器（stop）

- 输入：Claude hooks stdin JSON（session_id）
- 行为：契约确认（无 phase_state 走 acknowledged 分支）；平台侧不阻断（空输出 exit 0）
- 复用：PreCompact 也可注册本脚本（上下文压缩场景补一次呼吸确认）
"""
import sys

from diegin_claude_common import call_contract, ensure_utf8, make_envelope, read_stdin

HOOK_EVENT = "Stop"


def translate(resp: dict) -> tuple:
    """统一响应 → Claude hook 响应。(exit_code, stdout_text, stderr_text)"""
    return (0, "", "")


def main() -> int:
    ensure_utf8()
    data = read_stdin()
    envelope = make_envelope(
        "stop",
        session_id=data.get("session_id", "") or "",
        context={"platform": "claude", "hook": HOOK_EVENT},
    )
    call_contract(envelope)
    return 0


if __name__ == "__main__":
    sys.exit(main())