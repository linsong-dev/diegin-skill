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
def test_find_by_intent_fuzzy_match(tmp_path, monkeypatch):
    """v3.9.1 模糊恢复：自然语言按意图检索可恢复任务（无 task_id）"""
    reg = _make_registry(tmp_path, monkeypatch)
    a = reg.begin("A股资金增值模拟盘：15万到50万年度目标")
    reg.suspend(a["task_id"])
    b = reg.begin("三角洲行动游戏优化与ROG散热配置")
    reg.suspend(b["task_id"])
    c = reg.begin("已完成任务不参与匹配")
    reg.complete(c["task_id"])

    r1 = reg.find_by_intent("恢复 A股模拟盘那个任务")
    assert r1 and r1[0]["task_id"] == a["task_id"]
    assert r1[0]["score"] > 0
    assert len(r1[0]["summary"]) <= USER_SUMMARY_MAX_CHARS

    r2 = reg.find_by_intent("继续三角洲游戏优化")
    assert r2 and r2[0]["task_id"] == b["task_id"]

    r3 = reg.find_by_intent("已完成任务")
    assert all(t["task_id"] != c["task_id"] for t in r3)

    assert reg.find_by_intent("") == []
    assert reg.find_by_intent("   ") == []


def test_find_by_intent_score_order_and_topk(tmp_path, monkeypatch):
    """v3.9.1 模糊恢复：分数降序 + top_k 截断 + 最相似排前"""
    reg = _make_registry(tmp_path, monkeypatch)
    t1 = reg.begin("交易系统开发与首板回测验证")
    reg.suspend(t1["task_id"])
    t2 = reg.begin("交易纪律与仓位管理规则梳理")
    reg.suspend(t2["task_id"])
    t3 = reg.begin("开发文档整理与知识层对齐")
    reg.suspend(t3["task_id"])

    r = reg.find_by_intent("交易 系统 开发", top_k=2)
    assert len(r) <= 2
    assert r[0]["score"] >= r[-1]["score"]
    assert r[0]["task_id"] == t1["task_id"]
    assert r[0]["task_id"] in (t1["task_id"], t2["task_id"])

