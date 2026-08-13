# -*- coding: utf-8 -*-
"""定稿第七章·恒常门：Token 上限 16k + 冷存储指针 + 快照全集 30 + 原子写
2026-08-13 完整终版细则
"""
import os, sys, json
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "engine"))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "engine", "evo"))
from evo import constancy
from evo.constancy import (TaskRegistry, SNAPSHOT_TOKEN_LIMIT, SNAPSHOT_FULL_KEEP)


def _make_registry(tmp_path, monkeypatch):
    target = os.path.join(str(tmp_path), "constancy_tasks.json")
    monkeypatch.setattr(constancy, "_get_tasks_path", lambda: target)
    return TaskRegistry()


def _big_task(reg, rid="big", cjk=0, en=0):
    t = {
        "task_id": rid,
        "intent_summary": "任务" + "大" * cjk,
        "completion_criteria": "标准" + "x" * en,
        "status": "paused",
        "pending_items": [],
        "blocker_report": "",
        "created_at": "2026-08-13T00:00:00",
        "updated_at": "2026-08-13T00:00:00",
        "resume_count": 0,
    }
    reg._tasks[rid] = t
    return t


# ── Token 估算 ──

def test_estimate_tokens_cjk_and_ascii():
    assert TaskRegistry._estimate_tokens("") == 0
    assert TaskRegistry._estimate_tokens("中文") == 2
    assert TaskRegistry._estimate_tokens("abcd") == 1
    assert TaskRegistry._estimate_tokens("中abcd") == 2  # 1 中文 + 4 ascii/4


def test_snapshot_token_count_basic(tmp_path, monkeypatch):
    reg = _make_registry(tmp_path, monkeypatch)
    _big_task(reg, rid="t1", cjk=10, en=0)
    assert reg.snapshot_token_count("t1") >= 10


def test_snapshot_token_count_over_limit(tmp_path, monkeypatch):
    reg = _make_registry(tmp_path, monkeypatch)
    _big_task(reg, rid="huge", cjk=SNAPSHOT_TOKEN_LIMIT + 100)
    assert reg.snapshot_token_count("huge") > SNAPSHOT_TOKEN_LIMIT


# ── 冷存储指针（Token 超限 → 仅加载摘要）──

def test_recoverable_over_limit_returns_pointer(tmp_path, monkeypatch):
    reg = _make_registry(tmp_path, monkeypatch)
    _big_task(reg, rid="huge", cjk=SNAPSHOT_TOKEN_LIMIT + 100)
    rec = reg.find_recoverable()
    assert len(rec) == 1
    p = rec[0]
    assert p.get("cold_stored") is True
    assert p.get("bulk_hint") == "任务信息量较大，恢复后可能需要分批加载"
    assert len(p.get("intent_summary", "")) <= 50
    assert p.get("token_count", 0) > SNAPSHOT_TOKEN_LIMIT


def test_recoverable_normal_returns_full(tmp_path, monkeypatch):
    reg = _make_registry(tmp_path, monkeypatch)
    r = reg.begin("普通任务", "标准A")
    rec = reg.find_recoverable()
    assert len(rec) == 1
    assert rec[0].get("cold_stored") is None
    assert rec[0]["task_id"] == r["task_id"]
    assert rec[0].get("intent_summary") == "普通任务"


# ── 快照全集 30 + 冷存储归档 ──

def test_archive_old_snapshots_keeps_recent_30(tmp_path, monkeypatch):
    reg = _make_registry(tmp_path, monkeypatch)
    for i in range(40):
        reg.begin("任务%d" % i, "标准%d" % i)
    archived = reg.archive_old_snapshots()
    assert archived == 10
    active = [t for t in reg._tasks.values() if not t.get("cold_stored")]
    assert len(active) == SNAPSHOT_FULL_KEEP
    old = [t for t in reg._tasks.values() if t.get("cold_stored")]
    assert len(old) == 10
    for t in old:
        assert set(t.keys()) >= {"task_id", "intent_summary", "status", "completion_criteria", "cold_stored"}
        assert len(t.get("intent_summary", "")) <= 50


def test_archive_old_snapshots_cold_store_full(tmp_path, monkeypatch):
    reg = _make_registry(tmp_path, monkeypatch)
    for i in range(35):
        reg.begin("任务%d" % i, "标准%d" % i)
    reg.archive_old_snapshots()
    cold = reg._load_cold_store()
    assert len(cold) == 5
    tid = list(cold.keys())[0]
    assert cold[tid].get("intent_summary", "") != ""
    assert "cold_stored" not in cold[tid]  # 冷存储保留完整快照


def test_archive_idempotent(tmp_path, monkeypatch):
    reg = _make_registry(tmp_path, monkeypatch)
    for i in range(35):
        reg.begin("任务%d" % i)
    assert reg.archive_old_snapshots() == 5
    assert reg.archive_old_snapshots() == 0  # 二次执行不再归档


# ── 原子写 ──

def test_save_atomic_no_tmp_residue(tmp_path, monkeypatch):
    reg = _make_registry(tmp_path, monkeypatch)
    reg.begin("任务A", "标准A")
    reg._save()
    assert not os.path.exists(reg._path + ".tmp")
    assert os.path.exists(reg._path)
