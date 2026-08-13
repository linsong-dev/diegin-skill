"""自照镜·终稿细则（2026-08-13）：勇气信号外部确认 / 同向干扰熔断 / 最小运行间隔 / 应急抑制
定稿依据：律令九章 第九章 自照镜（2026-08-13 完整终版）
"""
import os
import sys
import datetime

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "engine"))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "engine", "evo"))

from evo import self_mirror as sm
from evo.self_mirror import SelfMirror, COURAGE_MAX


def _make(tmp_path, monkeypatch):
    target = os.path.join(str(tmp_path), "self_mirror.json")
    monkeypatch.setattr(sm, "_get_state_path", lambda: target)
    return SelfMirror()


def test_courage_pending_does_not_apply(tmp_path, monkeypatch):
    """pending=True：勇气信号先记待确认，不直接进入 courage（P6 不调权）。"""
    m = _make(tmp_path, monkeypatch)
    m.add_courage(0.5, pending=True)
    assert m.active_courage() == 0.0
    assert abs(m._state["pending_courage"] - 0.5) < 1e-6


def test_courage_confirm_applies(tmp_path, monkeypatch):
    """下一轮用户交互确认（无负面反馈）→ 生效进 courage。"""
    m = _make(tmp_path, monkeypatch)
    m.add_courage(0.5, pending=True)
    m.confirm_courage(True)
    assert abs(m.active_courage() - 0.5) < 1e-6
    assert m._state["pending_courage"] == 0.0


def test_courage_no_confirm_zeroed(tmp_path, monkeypatch):
    """用户负面反馈/未确认 → 自动归零，不进入 P6 调权。"""
    m = _make(tmp_path, monkeypatch)
    m.add_courage(0.5, pending=True)
    m.confirm_courage(False)
    assert m.active_courage() == 0.0
    assert m._state["pending_courage"] == 0.0


def test_courage_confirm_cap(tmp_path, monkeypatch):
    """确认生效仍受 COURAGE_MAX 封顶。"""
    m = _make(tmp_path, monkeypatch)
    m.add_courage(0.5, pending=True)
    m._state["courage"] = 0.7
    m.confirm_courage(True)
    assert m.active_courage() == COURAGE_MAX


def test_min_interval_blocks_frequent(tmp_path, monkeypatch):
    """与前次运行间隔 <3轮 且 <1小时 → 不触发（最小运行间隔）。"""
    m = _make(tmp_path, monkeypatch)
    m._state["round"] = 10
    m._state["last_mirror_round"] = 10  # 同一轮刚照过
    m._state["last_mirror_at"] = datetime.datetime.now().isoformat()
    assert m.should_mirror() is False


def test_min_interval_not_blocking_normal_frequency(tmp_path, monkeypatch):
    """最小间隔是护栏：10轮频率已到且轮差≥3 → 正常触发（不被最小间隔拦截）。"""
    m = _make(tmp_path, monkeypatch)
    m._state["round"] = 20
    m._state["last_mirror_round"] = 10  # 差 10 轮（跟随频率到点）
    m._state["last_mirror_at"] = datetime.datetime.now().isoformat()  # 时差<1h，但轮差≥3 已满足最小间隔
    assert m.should_mirror() is True


def test_same_dir_fuse_third_silent(tmp_path, monkeypatch):
    """连续两次同向干扰 → 第三次静默（direction_calibration 清空 + 标记）。"""
    m = _make(tmp_path, monkeypatch)
    fake = {"round": 11, "direction_calibration": ["攻七: 模式库膨胀(35 条, 均信 4.0)，建议收敛空壳/低置信模式"]}
    monkeypatch.setattr(m, "generate_report", lambda: dict(fake))
    r1 = m.mirror()
    assert not r1.get("same_dir_silenced")
    assert len(r1.get("direction_calibration")) == 1
    r2 = m.mirror()
    assert r2.get("same_dir_silenced") is True
    assert r2.get("direction_calibration") == []
    # 静默后 streak 已重置：第三次恢复正常（方向信号重新产出）
    r3 = m.mirror()
    assert not r3.get("same_dir_silenced")
    assert len(r3.get("direction_calibration")) == 1


def test_emergency_suppresses_p6(tmp_path, monkeypatch):
    """守三应急复盘触发时：仅记录素材，不产出 P6 调权（方向信号清空 + 标记）。"""
    m = _make(tmp_path, monkeypatch)
    fake = {"round": 12, "direction_calibration": ["方向偏保守: 无冒险事件且无泛化候选在验，建议适度主动验证"]}
    monkeypatch.setattr(m, "generate_report", lambda: dict(fake))
    r = m.mirror(emergency=True)
    assert r.get("emergency_suppressed") is True
    assert r.get("direction_calibration") == []
