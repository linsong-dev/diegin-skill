#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""迭进 × Claude Code：UserPromptSubmit 适配器（prompt_pre）

- 输入：Claude hooks stdin JSON（prompt / session_id）
- 翻译：契约 block → exit 2 + stderr 回显（UserPromptSubmit 可靠阻断语义）；
        契约 inject → hookSpecificOutput.additionalContext 注入（exit 0）；
        其余 → 空输出 exit 0
- 纪律：fail-open——引擎/契约异常一律不阻断（空输出 exit 0）
"""
import json
import sys

from diegin_claude_common import call_contract, ensure_utf8, make_envelope, read_stdin

HOOK_EVENT = "UserPromptSubmit"


def translate(resp: dict) -> tuple:
    """统一响应 → Claude hook 响应。(exit_code, stdout_text, stderr_text)"""
    decision = resp.get("decision", "allow")
    if decision == "block":
        reason = str(resp.get("reason") or "blocked by 迭进规则").strip()
        return (2, "", "[迭进] " + reason + "\n")
    inject = resp.get("inject")
    if inject:
        out = {
            "hookSpecificOutput": {
                "hookEventName": HOOK_EVENT,
                "additionalContext": str(inject),
            }
        }
        return (0, json.dumps(out, ensure_ascii=False), "")
    return (0, "", "")


def main() -> int:
    ensure_utf8()
    data = read_stdin()
    envelope = make_envelope(
        "prompt_pre",
        session_id=data.get("session_id", "") or "",
        context={"platform": "claude", "hook": HOOK_EVENT,
                 "prompt": data.get("prompt", "") or ""},
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