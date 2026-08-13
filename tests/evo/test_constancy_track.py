"""Tests for evo.main.constancy_track_prompt —— 恒常门·写侧接线
新意图→begin / 同意图去重 / 切换→suspend旧+begin新 / 空输入跳过 / 异常安全
"""
import os, sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "engine"))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "engine", "evo"))
from evo import constancy
from evo.constancy import _inst as _CONSTANCY_INST
import evo.main as main


def _setup(monkeypatch, tmp_path):
    """重置单例并指向临时任务文件"""
    monkeypatch.setattr(constancy, "_get_tasks_path", lambda: os.path.join(str(tmp_path), "constancy_tasks.json"))
    monkeypatch.setattr(constancy, "_inst", None)
    monkeypatch.setattr(main, "_get_constancy_inst", constancy.get_constancy)


def test_new_intent_begins(monkeypatch, tmp_path):
    _setup(monkeypatch, tmp_path)
    r = main.constancy_track_prompt("实现长任务持久化")
    assert r["ok"] is True and r["action"] == "begin" and r["task_id"]
    assert len(constancy.get_constancy()._tasks) == 1


def test_same_intent_dedup(monkeypatch, tmp_path):
    _setup(monkeypatch, tmp_path)
    main.constancy_track_prompt("实现长任务持久化")
    r = main.constancy_track_prompt("实现长任务持久化")
    assert r["action"] == "extend"
    assert len(constancy.get_constancy()._tasks) == 1


def test_switch_suspends_old(monkeypatch, tmp_path):
    _setup(monkeypatch, tmp_path)
    main.constancy_track_prompt("推进任务A的实现进度")
    r = main.constancy_track_prompt("推进任务B的实现进度")
    assert r["action"] == "begin"
    reg = constancy.get_constancy()
    assert len(reg._tasks) == 2
    a = reg._tasks[list(reg._tasks)[0]]
    assert a["status"] == "paused"


def test_short_prompt_none(monkeypatch, tmp_path):
    _setup(monkeypatch, tmp_path)
    assert main.constancy_track_prompt("")["action"] == "none"
    assert main.constancy_track_prompt("   ")["action"] == "none"
    assert main.constancy_track_prompt("短")["action"] == "none"


def test_exception_safe(monkeypatch, tmp_path):
    _setup(monkeypatch, tmp_path)
    def _boom(*a, **k):
        raise RuntimeError("boom")
    monkeypatch.setattr(main, "constancy_recoverable", _boom)
    r = main.constancy_track_prompt("异常安全测试任务")
    assert r["ok"] is False


def test_system_marker_filtered(monkeypatch, tmp_path):
    """P2: Memory Writing Agent 等系统输入不落库"""
    _setup(monkeypatch, tmp_path)
    r = main.constancy_track_prompt("## Memory Writing Agent: Phase 2\r\n\r\nYou are a Memory Writing Agent.\r\nconsolidate raw memories")
    assert r["action"] == "none"
    assert len(constancy.get_constancy()._tasks) == 0


def test_resume_current_task_extend(monkeypatch, tmp_path):
    """恢复续接：current_task_id 传入 → extend 不新建、不切换"""
    _setup(monkeypatch, tmp_path)
    r1 = main.constancy_track_prompt("长任务持久化实现")
    tid = r1["task_id"]
    r2 = main.constancy_track_prompt("继续之前的长任务", current_task_id=tid)
    assert r2["action"] == "extend"
    assert r2["task_id"] == tid
    assert len(constancy.get_constancy()._tasks) == 1


def test_criteria_derivation(monkeypatch, tmp_path):
    """P1-3: completion_criteria/pending_items 轻量推导"""
    _setup(monkeypatch, tmp_path)
    prompt = "实现长任务持久化，确保跨会话可恢复。\n1. 设计任务登记表\n2. 落库接线\n最后验收"
    r = main.constancy_track_prompt(prompt)
    reg = constancy.get_constancy()
    t = reg._tasks[r["task_id"]]
    assert "实现长任务持久化" in t["completion_criteria"]
    assert any("设计任务登记表" in x for x in t["pending_items"])
    assert any("落库接线" in x for x in t["pending_items"])


def test_complete_signal_status(monkeypatch, tmp_path):
    """完成自动信号：complete 后任务不再可恢复"""
    _setup(monkeypatch, tmp_path)
    r = main.constancy_track_prompt("一个待完成任务")
    tid = r["task_id"]
    assert main.constancy_complete(tid) is True
    assert main.constancy_recoverable() == []
    assert constancy.get_constancy()._tasks[tid]["status"] == "completed"


def test_precheck_order_excludes_current(monkeypatch, tmp_path):
    """P0-2: 恢复检查排除当前轮任务（pre_reply 顺序语义）"""
    _setup(monkeypatch, tmp_path)
    # 先有遗留任务
    main.constancy_track_prompt("遗留任务甲")
    # 用户新输入 → 落库当前任务
    cur = main.constancy_track_prompt("新任务乙")
    rec = main.constancy_recoverable()
    assert len(rec) == 2  # 遗留 + 当前
    # pre_check 排除当前轮任务后 → 只剩遗留
    rec2 = [t for t in rec if t.get("task_id") != cur["task_id"]]
    assert [t["intent_summary"] for t in rec2] == ["遗留任务甲"]
