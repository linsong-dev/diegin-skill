#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""迭进 × Claude Code 适配器模拟验证（M2，无需真实 Claude 环境）

两段式：
  1. 翻译层单测 —— import 各适配器 translate()，喂预置统一响应，断言 Claude hook 协议输出
  2. 端到端模拟 —— 以 Claude 格式 stdin 子进程调用各适配器，断言退出码/输出符合契约
     （走真实 engine/contract.py + 真实规则；DGEN_ROOT 指向本仓库根）

用法：python deploy/adapters/claude-code/simulate_test.py
"""
import json
import os
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, "..", "..", ".."))
PY = sys.executable
sys.path.insert(0, HERE)

import diegin_claude_pre_tool as pre_tool
import diegin_claude_prompt as prompt
import diegin_claude_session_start as session_start
import diegin_claude_post_tool as post_tool
import diegin_claude_stop as stop


def run(script: str, stdin_data: dict) -> subprocess.CompletedProcess:
    env = dict(os.environ)
    env["DGEN_ROOT"] = ROOT
    return subprocess.run(
        [PY, os.path.join(HERE, script)],
        input=json.dumps(stdin_data, ensure_ascii=False),
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=120,
        env=env,
    )


def main() -> int:
    ok = fail = 0

    def check(name, cond, detail=""):
        nonlocal ok, fail
        if cond:
            ok += 1
            print("  [PASS] " + name)
        else:
            fail += 1
            print("  [FAIL] " + name + (" | " + detail if detail else ""))

    print("=== DGEN x Claude Code Adapter Simulation ===")

    # ── 1. 翻译层单测（不触发引擎）──
    print("\n[1] 翻译层")
    code, out, err = pre_tool.translate({"decision": "block", "reason": "rule_demo 命中"})
    obj = json.loads(out) if out else {}
    check("pre_tool block -> exit 0", code == 0)
    check("pre_tool block -> permissionDecision deny",
          obj.get("hookSpecificOutput", {}).get("permissionDecision") == "deny")
    check("pre_tool block -> reason 前缀 [迭进]",
          str(obj.get("hookSpecificOutput", {}).get("permissionDecisionReason", "")).startswith("[迭进]"))
    code, out, err = pre_tool.translate({"decision": "allow"})
    check("pre_tool allow -> 空输出 exit 0", code == 0 and out == "" and err == "")

    code, out, err = prompt.translate({"decision": "block", "reason": "rule_demo 命中"})
    check("prompt block -> exit 2", code == 2)
    check("prompt block -> stderr 回显", err.startswith("[迭进]") and out == "")
    code, out, err = prompt.translate({"decision": "allow", "inject": "[DGEN] PASS 攻七·推荐采用已验证做法"})
    obj = json.loads(out) if out else {}
    check("prompt inject -> additionalContext",
          obj.get("hookSpecificOutput", {}).get("additionalContext", "") != "")
    code, out, err = prompt.translate({"decision": "allow", "inject": None})
    check("prompt allow 无注入 -> 空输出", code == 0 and out == "" and err == "")

    code, out, err = session_start.translate(
        {"decision": "allow", "health": {"total_rules": 255, "active_rules": 60, "satisfaction": 1.0}})
    obj = json.loads(out) if out else {}
    ctx_text = obj.get("hookSpecificOutput", {}).get("additionalContext", "")
    check("session_start -> additionalContext 注入", ctx_text.startswith("[迭进]"))
    check("session_start -> 含健康数据", "active_rules=60" in ctx_text)

    code, out, err = post_tool.translate({"decision": "allow"})
    check("post_tool -> 空输出 exit 0", code == 0 and out == "" and err == "")
    code, out, err = stop.translate({"decision": "allow"})
    check("stop -> 空输出 exit 0", code == 0 and out == "" and err == "")

    # ── 2. 端到端模拟（真实契约层，allow 路径）──
    print("\n[2] 端到端（真实 engine/contract.py）")
    p = run("diegin_claude_session_start.py", {"session_id": "sim-1", "hook_event_name": "SessionStart"})
    obj = json.loads(p.stdout.strip()) if p.stdout.strip() else {}
    check("e2e session_start exit 0 + 注入",
          p.returncode == 0 and obj.get("hookSpecificOutput", {}).get("additionalContext", "").startswith("[迭进]"))

    p = run("diegin_claude_prompt.py", {"session_id": "sim-1", "prompt": "继续 M2 模拟验证"})
    check("e2e prompt exit 0（allow/audit 路径）", p.returncode == 0)

    p = run("diegin_claude_pre_tool.py",
            {"session_id": "sim-1", "tool_name": "Bash",
             "tool_input": {"command": "Get-ChildItem", "text": "Get-ChildItem"}})
    check("e2e pre_tool exit 0（allow/audit 路径）", p.returncode == 0)

    p = run("diegin_claude_post_tool.py",
            {"session_id": "sim-1", "tool_name": "Bash", "tool_input": {"command": "Get-ChildItem"}})
    check("e2e post_tool exit 0", p.returncode == 0)

    p = run("diegin_claude_stop.py", {"session_id": "sim-1", "hook_event_name": "Stop"})
    check("e2e stop exit 0", p.returncode == 0)

    # ── 3. fail-open 边界（DGEN_ROOT 指向不存在目录，契约层不可达）──
    print("\n[3] fail-open（引擎/契约不可达）")

    def run_bad(script: str, stdin_data: dict) -> subprocess.CompletedProcess:
        env = dict(os.environ)
        env["DGEN_ROOT"] = os.path.join(ROOT, "no-such-dir")
        return subprocess.run(
            [PY, os.path.join(HERE, script)],
            input=json.dumps(stdin_data, ensure_ascii=False),
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=60,
            env=env,
        )

    p = run_bad("diegin_claude_pre_tool.py",
                {"session_id": "sim-x", "tool_name": "Bash", "tool_input": {"command": "del *"}})
    check("fail-open pre_tool -> exit 0 空输出", p.returncode == 0 and p.stdout.strip() == "")

    p = run_bad("diegin_claude_prompt.py", {"session_id": "sim-x", "prompt": "任意提问"})
    check("fail-open prompt -> exit 0 空输出（不阻断）", p.returncode == 0 and p.stdout.strip() == "")

    p = run_bad("diegin_claude_session_start.py", {"session_id": "sim-x"})
    check("fail-open session_start -> exit 0 空输出（不注入）", p.returncode == 0 and p.stdout.strip() == "")

    p = run_bad("diegin_claude_post_tool.py",
                {"session_id": "sim-x", "tool_name": "Bash", "tool_input": {"command": "Get-ChildItem"}})
    check("fail-open post_tool -> exit 0", p.returncode == 0)

    p = run_bad("diegin_claude_stop.py", {"session_id": "sim-x"})
    check("fail-open stop -> exit 0", p.returncode == 0)

    print("\n---")
    print("  Result: %d/%d passed (%d failed)" % (ok, ok + fail, fail))
    return 0 if fail == 0 else 1


if __name__ == "__main__":
    sys.exit(main())