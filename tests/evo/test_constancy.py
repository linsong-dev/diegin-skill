"""Tests for evo.constancy —— 持存·恒常门（任务续接）
四态生命周期 / 嵌套≤3 溢出保护 / 30天快照 / 恢复确认≤50字 / 终态不可恢复
"""
import os, sys, json
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "engine"))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "engine", "evo"))
from evo import constancy
from evo.constancy import TaskRegistry, MAX_NEST_DEPTH, USER_SUMMARY_MAX_CHARS


def _make_registry(tmp_path, monkeypatch):
    target = os.path.join(str(tmp_path), "constancy_tasks.json")
    monkeypatch.setattr(constancy, "_get_tasks_path", lambda: target)
    return TaskRegistry()


def test_begin_creates_task(tmp_path, monkeypatch):
    reg = _make_registry(tmp_path, monkeypatch)
    r = reg.begin("完成白皮书九章化", "九章表+预策P0-P6")
    assert r["ok"] is True
    assert r["task_id"].startswith("task_")
    assert r["task"]["intent_summary"] == "完成白皮书九章化"
    assert r["task"]["status"] in ("paused", "active")


def test_lifecycle_four_statuses(tmp_path, monkeypatch):
    reg = _make_registry(tmp_path, monkeypatch)
    r = reg.begin("任务A")
    tid = r["task_id"]
    assert reg.suspend(tid) is True
    assert reg._tasks[tid]["status"] == "paused"
    assert reg.complete(tid) is True
    assert reg._tasks[tid]["status"] == "completed"
    r2 = reg.begin("任务B")
    tid2 = r2["task_id"]
    assert reg.block(tid2, "依赖缺失") is True
    assert reg._tasks[tid2]["status"] == "blocked"
    assert reg.abandon(tid2, "无意义") is True
    assert reg._tasks[tid2]["status"] == "abandoned"


def test_nested_overflow_protection(tmp_path, monkeypatch):
    reg = _make_registry(tmp_path, monkeypatch)
    r0 = reg.begin("根任务")
    r1 = reg.begin("子1", parent_task_id=r0["task_id"])
    r2 = reg.begin("子2", parent_task_id=r1["task_id"])
    assert reg.nest_depth(r0["task_id"]) == 1
    assert reg.nest_depth(r2["task_id"]) == 3
    r3 = reg.begin("子3", parent_task_id=r2["task_id"])
    assert r3["ok"] is False
    assert r3["error"] == "nested_overflow"


def test_find_recoverable_filters(tmp_path, monkeypatch):
    reg = _make_registry(tmp_path, monkeypatch)
    a = reg.begin("可恢复A")
    reg.suspend(a["task_id"])
    b = reg.begin("已完成B")
    reg.complete(b["task_id"])
    c = reg.begin("已放弃C")
    reg.abandon(c["task_id"])
    rec = reg.find_recoverable()
    ids = {t["task_id"] for t in rec}
    assert a["task_id"] in ids
    assert b["task_id"] not in ids
    assert c["task_id"] not in ids


def test_terminal_status_cannot_resume(tmp_path, monkeypatch):
    reg = _make_registry(tmp_path, monkeypatch)
    a = reg.begin("终态A")
    reg.complete(a["task_id"])
    assert reg.resume(a["task_id"]) is False
    b = reg.begin("终态B")
    reg.abandon(b["task_id"])
    assert reg.resume(b["task_id"]) is False


def test_user_summary_within_50_chars(tmp_path, monkeypatch):
    reg = _make_registry(tmp_path, monkeypatch)
    long_intent = "这是一段非常长的任务意图描述，用于验证用户可见摘要必须被截断到五十个字以内并且加上状态前缀" * 2
    r = reg.begin(long_intent)
    s = reg.user_summary(r["task_id"])
    assert len(s) <= USER_SUMMARY_MAX_CHARS
    assert s.startswith("[")


def test_cleanup_expired_removes_stale(tmp_path, monkeypatch):
    import datetime
    reg = _make_registry(tmp_path, monkeypatch)
    a = reg.begin("过期暂停A")
    reg.suspend(a["task_id"])
    reg._tasks[a["task_id"]]["updated_at"] = (datetime.datetime.now() - datetime.timedelta(days=31)).isoformat()
    b = reg.begin("保留已完成B")
    reg.complete(b["task_id"])
    removed = reg.cleanup_expired(max_days=30)
    assert removed == 1
    assert a["task_id"] not in reg._tasks
    assert b["task_id"] in reg._tasks
