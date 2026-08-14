# -*- coding: utf-8 -*-
"""守三·应急写侧验证门（定稿第二章「立即强制」→ 写侧改「自动生成 staging + 人工一步确认」）：
stage_deep_review_candidates 幂等生成候选（不写 override）；
apply_deep_review_staging 无 --confirm 只读、有 --confirm 才转 active（写 override + legacy + 清空 staging）；
pre_check 应急触发时自动 stage（端到端冒烟，快照恢复）。
"""
import json
import os
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "engine"))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "engine", "evo"))

import call_diegin
from evo import self_mirror

_SRC_STATE = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(call_diegin.__file__))),
    "var", "state")
_SRC_LOG = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(call_diegin.__file__))),
    "var", "logs", "diegin_audit.log")
_SNAP_FILES = ["strikes_db.json", "dgen_overrides.json", "dgen_override.json",
               "deep_review_staging.json", "emergency_track.json", "constancy_proactive.json",
               "self_mirror.json", "rule_counter_deltas.json", "dgen_marker_pending.json",
               "dgen_last_reply.json", "dgen_verify_result.json", "param_adjustments.json",
               "last_check_result.json"]


@pytest.fixture()
def snap_restore():
    snap = {}
    for n in _SNAP_FILES:
        p = os.path.join(_SRC_STATE, n)
        snap[n] = open(p, "rb").read() if os.path.exists(p) else None
    log_tail = None
    if os.path.exists(_SRC_LOG):
        with open(_SRC_LOG, "rb") as f:
            f.seek(0, 2)
            size = f.tell()
            f.seek(max(0, size - 8192))
            log_tail = (size, f.read())
    yield
    for n, b in snap.items():
        p = os.path.join(_SRC_STATE, n)
        if b is None:
            if os.path.exists(p):
                os.remove(p)
        else:
            with open(p, "wb") as f:
                f.write(b)
    if log_tail is not None:
        size, _tail = log_tail
        with open(_SRC_LOG, "rb+") as f:
            f.truncate(size)


def _write(tmp_path, name, data):
    p = os.path.join(str(tmp_path), name)
    os.makedirs(os.path.dirname(p), exist_ok=True)
    with open(p, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False)
    return p


def _read(tmp_path, name):
    p = os.path.join(str(tmp_path), name)
    if not os.path.exists(p):
        return None
    with open(p, "r", encoding="utf-8") as f:
        return json.load(f)


# ─────────── 候选计算（纯函数）───────────

def test_candidates_filter_count_and_blocked():
    strikes = {
        "err_a": {"count": 3, "severity": "high", "last_seen": "T1", "last_detail": "d1"},
        "err_b": {"count": 1, "severity": "low", "last_seen": "", "last_detail": ""},
        "err_c": {"count": 2, "severity": "medium", "last_seen": "", "last_detail": ""},
    }
    overrides = [{"blocked_error_type": "err_c"}]
    cands = call_diegin._deep_review_candidates(strikes, overrides)
    assert [c["error_type"] for c in cands] == ["err_a"]  # count>=2 且未阻断


def test_candidates_sort_by_count_desc():
    strikes = {"a": {"count": 2}, "b": {"count": 5}, "c": {"count": 3}}
    cands = call_diegin._deep_review_candidates(strikes, [])
    assert [c["error_type"] for c in cands] == ["b", "c", "a"]


# ─────────── stage（自动生成，幂等，不写 override）───────────

def test_stage_writes_staging_not_override(tmp_path):
    _write(tmp_path, "strikes_db.json", {"err_a": {"count": 3}})
    r = call_diegin.stage_deep_review_candidates(state_dir=str(tmp_path))
    assert r["ok"] is True and r["new_staged"] == 1 and r["total_staged"] == 1
    assert _read(tmp_path, "deep_review_staging.json") is not None
    assert _read(tmp_path, "dgen_overrides.json") is None  # 未生效


def test_stage_idempotent_and_refresh(tmp_path):
    _write(tmp_path, "strikes_db.json", {"err_a": {"count": 3}})
    r1 = call_diegin.stage_deep_review_candidates(state_dir=str(tmp_path))
    r2 = call_diegin.stage_deep_review_candidates(state_dir=str(tmp_path))
    assert r1["new_staged"] == 1 and r2["new_staged"] == 0
    assert r2["total_staged"] == 1
    # 更新 count 刷新
    _write(tmp_path, "strikes_db.json", {"err_a": {"count": 5}})
    r3 = call_diegin.stage_deep_review_candidates(state_dir=str(tmp_path))
    assert r3["new_staged"] == 0 and r3["total_staged"] == 1
    assert r3["candidates"][0]["count"] == 5


def test_stage_excludes_existing_override(tmp_path):
    _write(tmp_path, "strikes_db.json", {"err_a": {"count": 3}, "err_c": {"count": 2}})
    _write(tmp_path, "dgen_overrides.json", [{"blocked_error_type": "err_c"}])
    r = call_diegin.stage_deep_review_candidates(state_dir=str(tmp_path))
    assert [c["error_type"] for c in r["candidates"]] == ["err_a"]


# ─────────── apply（人工一步确认）───────────

def test_apply_requires_confirm_readonly(tmp_path):
    _write(tmp_path, "strikes_db.json", {"err_a": {"count": 3}})
    call_diegin.stage_deep_review_candidates(state_dir=str(tmp_path))
    r = call_diegin.apply_deep_review_staging(state_dir=str(tmp_path), confirm=False)
    assert r["action"] == "requires_confirm"
    assert r["pending_count"] == 1
    assert "--confirm" in r["hint"]
    assert _read(tmp_path, "dgen_overrides.json") is None  # 只读未写


def test_apply_confirm_writes_override_and_clears_staging(tmp_path):
    _write(tmp_path, "strikes_db.json", {"err_a": {"count": 3}, "err_b": {"count": 2}})
    call_diegin.stage_deep_review_candidates(state_dir=str(tmp_path))
    r = call_diegin.apply_deep_review_staging(state_dir=str(tmp_path), confirm=True)
    assert r["action"] == "applied"
    assert r["new_blocks_created"] == 2
    ov = _read(tmp_path, "dgen_overrides.json")
    assert len(ov) == 2
    assert ov[0]["blocked_error_type"] == "err_a"
    assert ov[0]["strike_count"] == 3
    assert "confidence_decay" in ov[0]
    assert _read(tmp_path, "dgen_override.json") is not None  # legacy 同步
    assert _read(tmp_path, "deep_review_staging.json") == []  # 清空


def test_apply_confirm_skips_already_blocked(tmp_path):
    _write(tmp_path, "strikes_db.json", {"err_a": {"count": 3}})
    _write(tmp_path, "dgen_overrides.json", [{"blocked_error_type": "err_a"}])
    call_diegin.stage_deep_review_candidates(state_dir=str(tmp_path))
    r = call_diegin.apply_deep_review_staging(state_dir=str(tmp_path), confirm=True)
    assert r["new_blocks_created"] == 0  # 已阻断不重复


# ─────────── pre_check 应急触发自动 stage（端到端）───────────

def test_precheck_emergency_auto_stage(monkeypatch, tmp_path, snap_restore):
    """应急触发（连续3轮内≥2次阻断）→ pre_check 自动生成 staging 候选，不写 override"""
    monkeypatch.setattr(self_mirror, "_get_state_path",
                        lambda: os.path.join(str(tmp_path), "self_mirror.json"))
    import evo.main as evo_main_mod
    monkeypatch.setattr(evo_main_mod, "constancy_recoverable", lambda: [])
    from evo import tracker as _trk
    monkeypatch.setattr(_trk, "check_emergency_deep_review", lambda d: True)
    stg_path = os.path.join(_SRC_STATE, "deep_review_staging.json")
    if os.path.exists(stg_path):
        os.remove(stg_path)
    ov_path = os.path.join(_SRC_STATE, "dgen_overrides.json")
    ov_before = open(ov_path, "rb").read() if os.path.exists(ov_path) else None
    out = call_diegin.pre_check({"task": "应急自动stage测试"})
    assert out.get("deep_review_required") is True
    assert out.get("deep_review_report") is not None
    assert os.path.exists(stg_path), "pre_check 应急未自动生成 staging"
    with open(stg_path, "r", encoding="utf-8") as f:
        stg = json.load(f)
    assert isinstance(stg, list)
    # override 未被自动写（写侧保持人工确认）：内容与调用前逐字节一致
    ov_after = open(ov_path, "rb").read() if os.path.exists(ov_path) else None
    assert ov_after == ov_before, "应急自动执行不应直接写 override"
