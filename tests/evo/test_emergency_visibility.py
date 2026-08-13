"""守三·应急触发 AI 可见性（定稿第二章）：emergency_review_notice 纯函数
——触发时 display_line 追加应急复盘提示；不重复追加；未触发原样返回。
组合链路：check_emergency_deep_review（连续3轮≥2次阻断触发）→ notice 可见。
"""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "engine", "evo"))

from evo.tracker import emergency_review_notice, EMERGENCY_REVIEW_FLAG, check_emergency_deep_review


def test_not_triggered_returns_unchanged():
    assert emergency_review_notice(False, "abc") == "abc"
    assert emergency_review_notice(False, "") == ""


def test_triggered_appends_flag():
    out = emergency_review_notice(True, "abc")
    assert out == "abc | " + EMERGENCY_REVIEW_FLAG
    assert "守三应急" in out


def test_triggered_empty_display_line():
    assert emergency_review_notice(True, "") == EMERGENCY_REVIEW_FLAG


def test_triggered_no_duplicate():
    dl = "abc | " + EMERGENCY_REVIEW_FLAG
    assert emergency_review_notice(True, dl) == dl


def test_triggered_preserves_prior_prefix():
    dl = "[DGEN] PASS"
    out = emergency_review_notice(True, dl)
    assert out.startswith("[DGEN] PASS | ")
    assert out.endswith(EMERGENCY_REVIEW_FLAG)


def test_trigger_to_visibility_link(tmp_path):
    """链路：连续2次阻断触发应急 → notice 升级 display_line（模拟 pre_check 接线）。"""
    f = os.path.join(str(tmp_path), "emergency_track.json")
    assert check_emergency_deep_review("block", f) is False
    assert check_emergency_deep_review("block", f) is True
    dl = emergency_review_notice(True, "放行")
    assert "守三应急" in dl
    assert "deep_review" in dl
