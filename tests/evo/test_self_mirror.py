"""Tests for evo.self_mirror —— 自照镜·方向之镜
勇气信号 ×0.6 半衰期 / 封顶 0.8 / 每10轮触发 / 报告归档
"""
import os, sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "engine"))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "engine", "evo"))
from evo import self_mirror
from evo.self_mirror import SelfMirror, COURAGE_DECAY, COURAGE_MAX, MIRROR_EVERY_ROUNDS


def _make_mirror(tmp_path, monkeypatch):
    target = os.path.join(str(tmp_path), "self_mirror.json")
    monkeypatch.setattr(self_mirror, "_get_state_path", lambda: target)
    return SelfMirror()


def test_courage_decay_half_life(tmp_path, monkeypatch):
    m = _make_mirror(tmp_path, monkeypatch)
    m.add_courage(1.0)
    assert m.active_courage() == COURAGE_MAX  # 封顶 0.8
    m._state["courage"] = 1.0
    m.tick()
    assert abs(m.active_courage() - 0.6) < 1e-6  # ×0.6
    m.tick()
    assert abs(m.active_courage() - 0.36) < 1e-6  # ×0.6 再衰减


def test_courage_cap_at_max(tmp_path, monkeypatch):
    m = _make_mirror(tmp_path, monkeypatch)
    m.add_courage(2.0)
    assert m.active_courage() == COURAGE_MAX
    m.add_courage(0.5)
    assert m.active_courage() == COURAGE_MAX  # 不越上限


def test_should_mirror_every_10_rounds(tmp_path, monkeypatch):
    m = _make_mirror(tmp_path, monkeypatch)
    assert m.should_mirror() is False
    m._state["round"] = MIRROR_EVERY_ROUNDS
    assert m.should_mirror() is True
    m._state["last_mirror_round"] = MIRROR_EVERY_ROUNDS
    assert m.should_mirror() is False


def test_should_mirror_daily(tmp_path, monkeypatch):
    import datetime
    m = _make_mirror(tmp_path, monkeypatch)
    m._state["last_mirror_at"] = (datetime.datetime.now() - datetime.timedelta(days=2)).isoformat()
    assert m.should_mirror() is True


def test_mirror_generates_report_and_archives(tmp_path, monkeypatch):
    m = _make_mirror(tmp_path, monkeypatch)
    m._state["round"] = 10
    report = m.mirror()
    assert report["round"] == 10
    assert "自照镜" in report
    assert m._state["last_mirror_round"] == 10
    assert len(m._state["reports"]) == 1
