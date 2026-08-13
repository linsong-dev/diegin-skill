"""Tests for evo.closure readonly_snapshot —— 止观·完形律 执行轨迹只读快照（定稿第八章）
封存携带快照 / export 只读访问 / 深拷贝不污染 / 无快照返回 None
"""
import os, sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "engine"))
from evo import closure
from evo.closure import ClosureGate


def _make_gate(tmp_path, monkeypatch):
    monkeypatch.setattr(closure, "_get_closure_dir", lambda: str(tmp_path))
    monkeypatch.setattr(closure, "_inst", None)
    return ClosureGate()


def test_close_writes_readonly_snapshot(tmp_path, monkeypatch):
    g = _make_gate(tmp_path, monkeypatch)
    snap = {"block_records": ["block: x exit=1"], "tool_call_sequence": ["Bash: ls"],
            "arbitration_log": "exit=1 decision=block"}
    item = g.close("snap_1", "快照测试", snapshot=snap)
    assert item["readonly_snapshot"]["block_records"] == ["block: x exit=1"]
    assert item["readonly_snapshot"]["tool_call_sequence"] == ["Bash: ls"]


def test_export_readonly_snapshot_deepcopy(tmp_path, monkeypatch):
    g = _make_gate(tmp_path, monkeypatch)
    g.close("snap_2", "快照测试", snapshot={"tool_call_sequence": ["Bash: ls"]})
    out = g.export_readonly_snapshot("snap_2")
    out["tool_call_sequence"].append("mutated")
    assert g.export_readonly_snapshot("snap_2")["tool_call_sequence"] == ["Bash: ls"]


def test_export_none_for_missing(tmp_path, monkeypatch):
    g = _make_gate(tmp_path, monkeypatch)
    assert g.export_readonly_snapshot("not_exist") is None


def test_close_without_snapshot_has_no_key(tmp_path, monkeypatch):
    g = _make_gate(tmp_path, monkeypatch)
    item = g.close("snap_3", "无快照封存")
    assert "readonly_snapshot" not in item
