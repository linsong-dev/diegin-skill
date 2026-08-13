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
