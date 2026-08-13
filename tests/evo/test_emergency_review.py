"""Tests for evo.tracker.check_emergency_deep_review —— 守三·应急触发（定稿第二章）
连续3轮内≥2次阻断 → 强制深度复盘；间隔超3轮不触发；allow 不累计
"""
import os, sys, json
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "engine"))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "engine", "evo"))
from evo.tracker import check_emergency_deep_review


def _state_file(tmp_path):
    return os.path.join(str(tmp_path), "emergency_track.json")


def test_two_blocks_in_span_triggers(tmp_path):
    f = _state_file(tmp_path)
    assert check_emergency_deep_review("block", f) is False   # 第1次阻断
    assert check_emergency_deep_review("block", f) is True    # 3轮内第2次 → 触发


def test_blocks_spaced_beyond_span_not_trigger(tmp_path):
    f = _state_file(tmp_path)
    check_emergency_deep_review("block", f)                   # 轮1
    check_emergency_deep_review("allow", f)                   # 轮2
    check_emergency_deep_review("allow", f)                   # 轮3（隔开）
    assert check_emergency_deep_review("block", f) is False   # 轮4，轮1已超3轮窗口


def test_allow_does_not_accumulate(tmp_path):
    f = _state_file(tmp_path)
    check_emergency_deep_review("allow", f)
    check_emergency_deep_review("allow", f)
    check_emergency_deep_review("allow", f)
    assert check_emergency_deep_review("allow", f) is False


def test_iron_wall_block_counts(tmp_path):
    f = _state_file(tmp_path)
    assert check_emergency_deep_review("allow", f) is False
    assert check_emergency_deep_review("iron_wall_block", f) is False  # 第1次
    assert check_emergency_deep_review("iron_wall_block", f) is True   # 第2次


def test_round_counter_persists(tmp_path):
    f = _state_file(tmp_path)
    check_emergency_deep_review("allow", f)
    with open(f, "r", encoding="utf-8") as fh:
        et = json.load(fh)
    assert et["round"] == 1
    check_emergency_deep_review("allow", f)
    with open(f, "r", encoding="utf-8") as fh:
        et = json.load(fh)
    assert et["round"] == 2


def test_exception_returns_false(tmp_path, monkeypatch):
    f = _state_file(tmp_path)
    monkeypatch.setattr(os, "makedirs", lambda *a, **k: (_ for _ in ()).throw(PermissionError("denied")))
    assert check_emergency_deep_review("block", f) is False
