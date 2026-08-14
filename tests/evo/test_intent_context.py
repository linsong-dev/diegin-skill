# -*- coding: utf-8 -*-
"""预策·③：pre_reply 意图上下文接入三重判定（trail §45 待处理③）
链路：pre_reply 落盘 current_intent.json → post_tool 读取并传入 record_success
（intent_summary/result_text/user_negative/tool_ok）→ 攻七成功三重门。
"""
import json
import os
import subprocess
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "engine"))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "engine", "evo"))

import call_diegin

_SRC_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(call_diegin.__file__)))
_SRC_STATE = os.path.join(_SRC_ROOT, "var", "state")
_SNAP_FILES = ["current_intent.json", ".record_success_counter.json", "constancy_proactive.json",
               "self_mirror.json", "emergency_track.json", "rule_counter_deltas.json",
               "dgen_marker_pending.json", "dgen_last_reply.json", "dgen_verify_result.json",
               "last_check_result.json", "param_adjustments.json"]


@pytest.fixture()
def snap_restore():
    snap = {}
    for n in _SNAP_FILES:
        p = os.path.join(_SRC_STATE, n)
        snap[n] = open(p, "rb").read() if os.path.exists(p) else None
    yield
    for n, b in snap.items():
        p = os.path.join(_SRC_STATE, n)
        if b is None:
            if os.path.exists(p):
                os.remove(p)
        else:
            with open(p, "wb") as f:
                f.write(b)


def _read_intent():
    p = os.path.join(_SRC_STATE, "current_intent.json")
    if not os.path.exists(p):
        return None
    with open(p, "r", encoding="utf-8") as f:
        return json.load(f)


def test_write_current_intent_context(snap_restore):
    path = call_diegin.write_current_intent(
        "帮我清理开发目录的冗余文件并整理归档", "task_t3_0001", "turn_42", False)
    assert path and os.path.exists(path)
    ii = _read_intent()
    assert ii["intent_summary"] == "帮我清理开发目录的冗余文件并整理归档"
    assert ii["task_id"] == "task_t3_0001"
    assert ii["turn_id"] == "turn_42"
    assert ii["user_negative"] is False
    assert ii["prompt"]
    assert ii["ts"]


def test_write_current_intent_truncate_and_null(snap_restore):
    long_prompt = "长" * 500
    call_diegin.write_current_intent(long_prompt, "", "", None)
    ii = _read_intent()
    assert len(ii["intent_summary"]) <= 200
    assert len(ii["prompt"]) <= 400
    assert ii["user_negative"] is None  # 无观测 → null（post_tool 侧保持单重兼容）


def test_pre_reply_writes_intent_context(snap_restore, tmp_path):
    """pre_reply 模式端到端：用户 prompt 落盘 current_intent.json（无论 allow/block 均在预检前写入）"""
    env = dict(os.environ)
    env["CODEX_HOME"] = str(tmp_path)
    prompt = "测试意图上下文落盘：请列出当前目录文件"
    payload = json.dumps({"prompt": prompt, "turn_id": "turn_t3"})
    r = subprocess.run(
        [sys.executable, os.path.join(_SRC_ROOT, "engine", "call_diegin.py"), "pre_reply"],
        input=payload, capture_output=True, text=True, encoding="utf-8", timeout=60,
        cwd=os.path.join(_SRC_ROOT, "engine"), env=env)
    ii = _read_intent()
    assert ii is not None, "pre_reply 未落盘 current_intent.json (rc=%s)" % r.returncode
    assert ii["intent_summary"] == prompt
    assert ii["turn_id"] == "turn_t3"
    assert ii["task_id"]  # 恒常门已落库


def test_record_success_rejects_inconsistent_triple(snap_restore):
    """post_tool 带意图上下文 + 用户负面 + 一致性不足 → 三重门拒绝（不保存模式，无规则污染）"""
    payload = json.dumps({
        "tool_name": "dgen_t3_probe_unrelated",
        "method": "清理文件",
        "intent_summary": "帮我清理开发目录的冗余文件",
        "result_text": "tsla market trend up 3.2%",
        "user_negative": True,
        "tool_ok": True,
    })
    r = subprocess.run(
        [sys.executable, os.path.join(_SRC_ROOT, "engine", "call_diegin.py"), "record_success"],
        input=payload, capture_output=True, text=True, encoding="utf-8", timeout=60,
        cwd=os.path.join(_SRC_ROOT, "engine"))
    out = r.stdout.strip()
    assert "rejected_triple_anchor" in out
    data = json.loads(out)
    assert data.get("action") == "rejected_triple_anchor"
    assert data.get("consistency") is not None and data["consistency"] < 0.5
