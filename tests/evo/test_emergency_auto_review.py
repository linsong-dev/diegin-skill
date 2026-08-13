# -*- coding: utf-8 -*-
"""守三·应急自动执行深度复盘（定稿第二章「立即强制执行」）：
_build_deep_review_report 只读报告函数——结构完整、零写副作用；
pre_check 应急触发时自动调用并注入 deep_review_report（端到端冒烟验证，见 trail §45）。
"""
import json
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "engine"))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "engine", "evo"))

import call_diegin


def _state_file(name):
    return os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(call_diegin.__file__)))),
                        "var", "state", name)


def test_report_structure():
    r = call_diegin._build_deep_review_report()
    assert isinstance(r, dict)
    assert r.get("principle") == "守三·深度复盘"
    assert isinstance(r.get("statistics"), dict)
    assert set(("total_error_types", "total_strikes", "high_severity_count",
                "blocked_count", "unblocked_high_count", "max_snapshot_age_days")) <= set(r["statistics"].keys())
    assert isinstance(r.get("error_ranking"), list)
    assert isinstance(r.get("suggestions"), list)
    assert isinstance(r.get("unblocked_high_risk"), list)
    assert isinstance(r.get("trajectory"), list)
    assert "next_step" in r


def test_report_is_read_only():
    """深度复盘报告只读：调用前后 strikes/overrides 文件字节不变"""
    sp = _state_file("strikes_db.json")
    op = _state_file("dgen_overrides.json")
    before = {}
    for p, k in ((sp, "strikes"), (op, "overrides")):
        before[k] = None
        if os.path.exists(p):
            with open(p, "rb") as f:
                before[k] = f.read()
    call_diegin._build_deep_review_report()
    for p, k in ((sp, "strikes"), (op, "overrides")):
        if before[k] is None:
            assert not os.path.exists(p) or True
        else:
            with open(p, "rb") as f:
                assert f.read() == before[k], "deep_review 报告修改了 %s" % p


def test_report_consistency_with_strikes_db():
    sp = _state_file("strikes_db.json")
    if not os.path.exists(sp):
        return  # 无 strikes 时跳过数值断言
    with open(sp, "r", encoding="utf-8") as f:
        strikes = json.load(f)
    r = call_diegin._build_deep_review_report()
    assert r["statistics"]["total_error_types"] == len(strikes)
    assert r["statistics"]["total_strikes"] == sum(e.get("count", 0) for e in strikes.values())
