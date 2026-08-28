# -*- coding: utf-8 -*-
"""p6_audit.py - P6 影响审计日志（运维手册 2.4）
追加写 var/logs/p6_audit.jsonl，环形 1000 条；纯记录不参与裁决；失败静默。"""
import json, os, time

def audit_p6(rule_id, delta, hit, rule_obj):
    try:
        _log = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                            "..", "var", "logs", "p6_audit.jsonl")
        _log = os.path.normpath(_log)
        _d = os.path.dirname(_log)
        if _d and not os.path.exists(_d):
            os.makedirs(_d, exist_ok=True)
        _rec = {
            "ts": time.strftime("%Y-%m-%dT%H:%M:%S"),
            "rule_id": rule_id,
            "kind": "pattern" if "SuccessPattern" in str(type(rule_obj)) else "rule",
            "delta": round(float(delta), 3),
            "direction": "up" if delta > 0 else "down",
            "source": str((hit or {}).get("space", "")) + ":" + str((hit or {}).get("uid", ""))[:40],
            "score": round(float((hit or {}).get("score", 0) or 0), 3),
        }
        _line = json.dumps(_rec, ensure_ascii=False)
        _lines = []
        if os.path.exists(_log):
            try:
                with open(_log, "r", encoding="utf-8") as _f:
                    _lines = [l for l in _f.read().splitlines() if l.strip()]
            except Exception:
                _lines = []
        _lines.append(_line)
        if len(_lines) > 1000:
            _lines = _lines[-1000:]
        with open(_log, "w", encoding="utf-8") as _f:
            _f.write("\n".join(_lines) + "\n")
    except Exception:
        pass