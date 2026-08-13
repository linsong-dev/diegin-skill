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


def test_direction_calibration_conservative(tmp_path, monkeypatch):
    """方向校准：无勇气事件 + 无 staging 候选 → 保守信号"""
    m = _make_mirror(tmp_path, monkeypatch)
    r = m.generate_report()
    sig = r.get("direction_calibration", [])
    assert any("保守" in s for s in sig)


def test_direction_calibration_high_interrupt(tmp_path, monkeypatch):
    """方向校准：中断率高 → 恢复优先信号"""
    m = _make_mirror(tmp_path, monkeypatch)
    report = {"攻七": {"入库模式数": 10, "平均置信度": 5.0},
              "持存": {"中断率": 0.9},
              "举一反三": {"staging池大小": 3},
              "自照镜": {"累计勇气事件": 1}}
    sig = m._build_direction_calibration(report)
    assert any("中断率" in s for s in sig)
    assert not any("保守" in s for s in sig)


def test_report_has_all_principles(tmp_path, monkeypatch):
    """自照报告素材：一二不过三/预策/持存/守三/去伪存真/自照镜 六块齐（注入状态文件）"""
    import json
    _sd = os.path.join(str(tmp_path), "strikes_db.json")
    with open(_sd, "w", encoding="utf-8") as f:
        json.dump({"image_url": {"count": 2}, "command_failure": {"count": 1}}, f)
    _vt = os.path.join(str(tmp_path), "evidence_trail.json")
    with open(_vt, "w", encoding="utf-8") as f:
        json.dump([{"verdict": "真"}, {"verdict": "假"}, {"verdict": "暂存"}], f)
    m = _make_mirror(tmp_path, monkeypatch)
    r = m.generate_report()
    for k in ("一二不过三", "预策", "持存", "守三", "去伪存真", "自照镜"):
        assert k in r, f"缺少素材块: {k}"
    assert "完成率" in r["持存"]
    assert "升级阻断数" in r["预策"]
    assert "累计触发次数" in r["一二不过三"]
    assert r["一二不过三"]["累计触发次数"] == 3
    assert r["去伪存真"]["验证请求数"] == 3


def test_mirror_archives_direction_signal(tmp_path, monkeypatch):
    """自照归档：方向信号非空时写 direction_calibration Mindol 条目"""
    import sys, types
    calls = []
    _mod = types.ModuleType("mindol")
    _di = types.ModuleType("mindol.diegin_integration")
    _di.memory_archive = lambda space, text, *a, **k: calls.append((space, text))
    _mod.diegin_integration = _di
    sys.modules["mindol"] = _mod
    sys.modules["mindol.diegin_integration"] = _di
    m = _make_mirror(tmp_path, monkeypatch)
    m._state["round"] = 10
    m.mirror()
    assert any(sp == "self_mirror" for sp, _ in calls)
    # 保守环境应产生方向信号归档
    assert any(sp == "direction_calibration" for sp, _ in calls)
