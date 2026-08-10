# -*- coding: utf-8 -*-
"""迭进 × Claude Code 适配器公共层（钩子契约 v1 / M2）

职责（平台适配器 = 本模块 + 平台薄翻译）：
  1. diegin_root       —— 定位迭进根（默认相对本文件上 3 级；DGEN_ROOT 可覆盖）
  2. make_envelope     —— 构造统一信封（contract 1.0 / 5 标准事件）
  3. call_contract     —— subprocess 调 engine/contract.py，返回统一响应
  4. read_stdin / ensure_utf8 —— Claude hooks stdin 读取与中文加固

纪律：引擎/契约异常一律 fail-open（返回 allow 响应并标注 error，不阻断业务）。
"""
import json
import os
import subprocess
import sys
import uuid
from datetime import datetime

CONTRACT_VERSION = "1.0"


def ensure_utf8() -> None:
    """Claude hooks 通道中文加固：stdout/stderr 强制 UTF-8。"""
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8", errors="replace")
        except Exception:
            pass


def diegin_root() -> str:
    """迭进根：DGEN_ROOT 环境变量优先；否则相对本文件上 3 级（deploy/adapters/claude-code -> 仓库根）。"""
    env_root = os.environ.get("DGEN_ROOT", "").strip()
    if env_root:
        return os.path.abspath(env_root)
    here = os.path.dirname(os.path.abspath(__file__))
    return os.path.abspath(os.path.join(here, "..", "..", ".."))


def make_envelope(event: str, session_id: str = "", ts: str = "",
                  tool: dict = None, context: dict = None) -> dict:
    """构造统一信封（与 Codex 适配器同一 schema）。"""
    ctx = dict(context or {})
    ctx.setdefault("platform", "claude")
    return {
        "contract": CONTRACT_VERSION,
        "event": event,
        "session_id": session_id or ("sess-" + uuid.uuid4().hex[:8]),
        "ts": ts or datetime.now().astimezone().isoformat(),
        "tool": tool or {},
        "context": ctx,
    }


def read_stdin() -> dict:
    """读 Claude hook stdin JSON；不可解析返回 {}（调用方按 fail-open 处理）。"""
    try:
        raw = sys.stdin.buffer.read()
    except Exception:
        return {}
    if raw.startswith(b"\xef\xbb\xbf"):
        raw = raw[3:]
    text = ""
    for enc in ("utf-8", "gbk"):
        try:
            s = raw.decode(enc)
            if "\ufffd" not in s:
                text = s.strip()
                break
        except (UnicodeDecodeError, LookupError):
            continue
    if not text:
        text = raw.decode("utf-8", errors="replace").strip()
    if not text:
        return {}
    try:
        data = json.loads(text)
    except json.JSONDecodeError:
        return {}
    return data if isinstance(data, dict) else {}


def call_contract(envelope: dict, timeout: int = 40) -> dict:
    """调 engine/contract.py；返回统一响应；任何异常 -> fail-open allow 并标注 error。"""
    root = diegin_root()
    contract_py = os.path.join(root, "engine", "contract.py")
    platform = envelope.get("context", {}).get("platform", "claude")
    event = envelope.get("event", "")
    fallback = {
        "contract": CONTRACT_VERSION,
        "event": event,
        "decision": "allow",
        "reason": "contract dispatch error",
        "matched_count": 0,
        "winning_rule": "",
        "inject": None,
        "suggestions": [],
        "platform": platform,
        "error": "",
    }
    try:
        p = subprocess.run(
            [sys.executable, contract_py],
            input=json.dumps(envelope, ensure_ascii=False),
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=timeout,
        )
        out = (p.stdout or "").strip()
        try:
            resp = json.loads(out)
        except json.JSONDecodeError:
            resp = dict(fallback)
            resp.update({"reason": "contract non-json output",
                         "engine_exit": p.returncode, "error": "non-json"})
            return resp
        if not isinstance(resp, dict):
            resp = dict(fallback)
            resp.update({"reason": "contract non-object output", "error": "non-object"})
            return resp
        return resp
    except Exception as exc:  # noqa: BLE001 契约层兜底：fail-open 放行并标注
        resp = dict(fallback)
        resp.update({"reason": "contract dispatch error: %s" % exc, "error": str(exc)})
        return resp