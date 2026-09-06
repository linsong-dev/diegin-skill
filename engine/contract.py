# -*- coding: utf-8 -*-
"""迭进钩子契约 v1（M1 参考实现）—— 统一信封协议层

契约文档：《迭进钩子契约 v1》（v1.0，2026-08-10 定稿，随仓库文档发布）

职责（平台适配器 = 本模块 + 平台薄翻译）：
  1. parse_envelope   —— 解析/校验统一输入信封（5 标准事件，宽容补全）
  2. dispatch         —— 按 event 路由到 call_diegin.py 现有模式（subprocess 复用，零侵入）
  3. build_response   —— 生成统一响应（三态 decision + inject + suggestions）
  4. self-test        —— 内置契约自测（不触发引擎副作用）

用法：
  $envelope | python contract.py                # 返回统一响应 JSON
  python contract.py --self-test                # 契约自测
"""
import json
import os
import subprocess
import sys
import uuid
from datetime import datetime

CONTRACT_VERSION = "1.0"
EVENTS = ("session_start", "prompt_pre", "tool_pre", "tool_post", "stop")
DECISION_ALLOW = "allow"
DECISION_BLOCK = "block"
DECISION_AUDIT = "audit"


def _now_iso() -> str:
    return datetime.now().astimezone().isoformat()


def _decode_stdin_bytes(b: bytes) -> str:
    """PS5.1 管道中文加固：UTF-8 优先，失败回退 GBK，去 BOM（与 call_diegin 同策略）。"""
    if b.startswith(b"\xef\xbb\xbf"):
        b = b[3:]
    if not b:
        return ""
    for enc in ("utf-8", "gbk"):
        try:
            s = b.decode(enc)
            if "\ufffd" not in s:
                return s.strip()
        except (UnicodeDecodeError, LookupError):
            continue
    return ""


def parse_envelope(text: str) -> dict:
    """解析统一输入信封；event 非法抛 ValueError；缺失字段宽容补全。"""
    if not text or not text.strip():
        raise ValueError("empty envelope")
    data = json.loads(text)
    event = data.get("event")
    if event not in EVENTS:
        raise ValueError("unknown event: %r (valid: %s)" % (event, ", ".join(EVENTS)))
    ctx = data.get("context") or {}
    if not isinstance(ctx, dict):
        ctx = {}
    ctx.setdefault("platform", "codex")
    return {
        "contract": data.get("contract", CONTRACT_VERSION),
        "event": event,
        "session_id": data.get("session_id") or ("sess-" + uuid.uuid4().hex[:8]),
        "ts": data.get("ts") or _now_iso(),
        "tool": data.get("tool") or {},
        "context": ctx,
    }


def build_response(event, decision=DECISION_ALLOW, reason="", inject=None,
                   suggestions=None, matched_count=0, winning_rule="",
                   platform="codex", extra=None) -> dict:
    """生成统一响应（三态 decision + inject + suggestions）。"""
    resp = {
        "contract": CONTRACT_VERSION,
        "event": event,
        "decision": decision,
        "reason": reason,
        "matched_count": matched_count,
        "winning_rule": winning_rule,
        "inject": inject,
        "suggestions": suggestions or [],
        "platform": platform,
        "ts": _now_iso(),
    }
    if extra:
        resp.update(extra)
    return resp


def _normalize_decision(raw: str) -> str:
    """把引擎原生 decision 归一为契约三态。"""
    if not raw:
        return DECISION_ALLOW
    r = str(raw).lower()
    if r in ("block", "iron_wall_block"):
        return DECISION_BLOCK
    if r in ("audit", "allow_audit"):
        return DECISION_AUDIT
    return DECISION_ALLOW


def _run(py, engine_py, mode, payload: dict, timeout=40) -> subprocess.CompletedProcess:
    """subprocess 复用 call_diegin.py 现有模式（stdin JSON，UTF-8）。"""
    return subprocess.run(
        [py, engine_py, mode],
        input=json.dumps(payload, ensure_ascii=False),
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=timeout,
    )


def dispatch(envelope: dict, py=None, engine_py=None) -> dict:
    """按 event 路由到 call_diegin 现有模式，返回统一响应。"""
    event = envelope["event"]
    platform = envelope.get("context", {}).get("platform", "codex")
    base = os.path.dirname(os.path.abspath(__file__))
    py = py or sys.executable
    engine_py = engine_py or os.path.join(base, "call_diegin.py")

    try:
        if event == "tool_pre":
            tool = envelope.get("tool") or {}
            tool_input = tool.get("input") or {}
            command = tool_input.get("command") or tool_input.get("text") or ""
            ctx = {
                "task_type": "pre_tool",
                "tool_name": tool.get("name", "unknown"),
                "command": command,
                "text": command,
                "hook_event_name": "PreToolUse",
                "blocked_error_type": envelope.get("context", {}).get("blocked_error_type", ""),
                "marker_missing": False,
            }
            p = _run(py, engine_py, "check", ctx)
            out = (p.stdout or "").strip()
            try:
                r = json.loads(out)
            except json.JSONDecodeError:
                # check 模式正常输出 JSON；非 JSON = 引擎异常 → 按契约 fail-open 放行并标注
                return build_response(event, decision=DECISION_ALLOW,
                                      reason="engine check non-json output",
                                      platform=platform,
                                      extra={"engine_exit": p.returncode, "raw": out[:200]})
            return build_response(
                event,
                decision=_normalize_decision(r.get("decision", DECISION_ALLOW)),
                reason=r.get("reason", "") or "",
                matched_count=r.get("matched_interceptions", 0) or 0,
                winning_rule=r.get("winning_rule_id", "") or "",
                suggestions=r.get("suggestions", []) or [],
                platform=platform,
                extra={"routing_suggestion": r.get("routing_suggestion") or {}},
            )

        if event == "prompt_pre":
            ctx = envelope.get("context", {})
            payload = {
                "prompt": ctx.get("prompt", "") or "",
                "turn_id": ctx.get("turn_id", ""),
                "session_id": ctx.get("session_id", ""),
                "blocked_error_type": ctx.get("blocked_error_type", ""),
            }
            p = _run(py, engine_py, "pre_reply", payload)
            out = (p.stdout or "").strip()
            if p.returncode != 0:
                # pre_reply 阻断路径：stdout 即阻断提示文本
                return build_response(event, decision=DECISION_BLOCK,
                                      reason=out[:500] or "pre_reply blocked",
                                      platform=platform,
                                      extra={"engine_exit": p.returncode})
            try:
                r = json.loads(out)
            except json.JSONDecodeError:
                return build_response(event, decision=DECISION_ALLOW,
                                      reason="engine pre_reply non-json output",
                                      platform=platform,
                                      extra={"raw": out[:200]})
            return build_response(
                event,
                decision=_normalize_decision(r.get("decision", DECISION_ALLOW)),
                reason=r.get("reason", "") or "",
                matched_count=r.get("matched_count", 0) or 0,
                winning_rule=r.get("winning_rule_id", "") or "",
                inject=r.get("display_text", "") or "",
                suggestions=r.get("suggestions", []) or [],
                platform=platform,
            )

        if event == "session_start":
            p = _run(py, engine_py, "health", {})
            out = (p.stdout or "").strip()
            try:
                r = json.loads(out)
            except json.JSONDecodeError:
                r = {}
            return build_response(event, decision=DECISION_ALLOW,
                                  reason="session_start health",
                                  platform=platform,
                                  extra={"health": r, "engine_exit": p.returncode})

        if event == "tool_post":
            # 契约层事件确认 + 健康信息；平台适配器继续负责 marker/feedback/record_success
            p = _run(py, engine_py, "health", {})
            out = (p.stdout or "").strip()
            try:
                r = json.loads(out)
            except json.JSONDecodeError:
                r = {}
            return build_response(event, decision=DECISION_ALLOW,
                                  reason="tool_post health check",
                                  platform=platform,
                                  extra={"health": r, "engine_exit": p.returncode})

        if event == "stop":
            ctx = envelope.get("context", {})
            if ctx.get("phase_state"):
                # Stop 的硬地板检查：phase_state 传给引擎 pre_check（原 stop.ps1 语义）
                payload = {
                    "task_type": "stop",
                    "tool_name": "Stop",
                    "command": "stop_verification",
                    "text": "stop_verification",
                    "hook_event_name": "Stop",
                    "phase_state": ctx.get("phase_state"),
                }
                p = _run(py, engine_py, "check", payload)
                out = (p.stdout or "").strip()
                try:
                    r = json.loads(out)
                except json.JSONDecodeError:
                    r = {}
                return build_response(event,
                                      decision=_normalize_decision(r.get("decision", DECISION_ALLOW)),
                                      reason=r.get("reason", "") or "",
                                      matched_count=r.get("matched_interceptions", 0) or 0,
                                      winning_rule=r.get("winning_rule_id", "") or "",
                                      platform=platform,
                                      extra={"engine_exit": p.returncode})
            return build_response(event, decision=DECISION_ALLOW,
                                  reason="stop acknowledged by contract",
                                  platform=platform)

        return build_response(event, decision=DECISION_ALLOW,
                              reason="event not dispatched", platform=platform)
    except Exception as exc:  # noqa: BLE001 契约层兜底：fail-open 放行并标注
        return build_response(event, decision=DECISION_ALLOW,
                              reason="contract dispatch error: %s" % exc,
                              platform=platform, extra={"error": str(exc)})


def self_test() -> int:
    """契约自测：只测协议层（解析/响应/归一/翻译），不触发引擎副作用。"""
    ok = 0
    fail = 0

    def check(name, cond, detail=""):
        nonlocal ok, fail
        if cond:
            ok += 1
            print("  [PASS] " + name)
        else:
            fail += 1
            print("  [FAIL] " + name + (" | " + detail if detail else ""))

    print("=== DGEN Contract v1 Self-Test ===")

    # 1. 信封解析
    env = parse_envelope('{"event":"tool_pre","tool":{"name":"Bash","input":{"command":"Get-ChildItem"}}}')
    check("parse envelope: event/tool", env["event"] == "tool_pre" and env["tool"]["name"] == "Bash")
    check("parse envelope: platform default", env["context"]["platform"] == "codex")
    check("parse envelope: session_id generated", env["session_id"].startswith("sess-"))
    check("parse envelope: ts generated", bool(env["ts"]))

    # 2. 非法事件拒绝
    try:
        parse_envelope('{"event":"bogus"}')
        check("parse envelope: invalid event rejected", False)
    except ValueError:
        check("parse envelope: invalid event rejected", True)

    # 3. 三态归一
    check("normalize block", _normalize_decision("iron_wall_block") == DECISION_BLOCK)
    check("normalize audit", _normalize_decision("audit") == DECISION_AUDIT)
    check("normalize allow", _normalize_decision("ALLOW") == DECISION_ALLOW)
    check("normalize empty", _normalize_decision("") == DECISION_ALLOW)

    # 4. 统一响应结构
    resp = build_response("tool_pre", decision=DECISION_BLOCK, reason="test",
                          matched_count=2, winning_rule="r1",
                          suggestions=[{"id": "p1"}])
    check("response: contract 1.0", resp["contract"] == CONTRACT_VERSION)
    check("response: decision block", resp["decision"] == DECISION_BLOCK)
    check("response: inject null by default", resp["inject"] is None)
    check("response: suggestions passthrough", resp["suggestions"] == [{"id": "p1"}])
    check("response: event echo", resp["event"] == "tool_pre")

    # 5. 5 事件枚举完整
    check("events cover 5 standard", set(EVENTS) == {"session_start", "prompt_pre", "tool_pre", "tool_post", "stop"})

    print("---")
    print("  Result: %d/%d passed (%d failed)" % (ok, ok + fail, fail))
    return 0 if fail == 0 else 1


def main() -> int:
    if len(sys.argv) > 1 and sys.argv[1] == "--self-test":
        return self_test()
    try:
        b = sys.stdin.buffer.read()
        text = _decode_stdin_bytes(b)
        env = parse_envelope(text)
        resp = dispatch(env)
        print(json.dumps(resp, ensure_ascii=False))
        return 0
    except ValueError as ve:
        print(json.dumps({"contract": CONTRACT_VERSION, "decision": "allow",
                          "reason": "contract parse error: %s" % ve,
                          "event": "unknown"}, ensure_ascii=False))
        return 0
    except Exception as exc:  # noqa: BLE001
        print(json.dumps({"contract": CONTRACT_VERSION, "decision": "allow",
                          "reason": "contract error: %s" % exc,
                          "event": "unknown"}, ensure_ascii=False))
        return 0


if __name__ == "__main__":
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass
    sys.exit(main())
