# ============================================
# 迭进(Diegin) 核心引擎 - 检测模块
# 全域常驻自我迭代进化系统
# 包含: detect_failure / detect_success / ensure_three_strikes / get_strike_status
# ============================================

import os
import sys
import json
import datetime
from pathlib import Path

# ------------------------------------------------------------
# 错误检测器单例
# ------------------------------------------------------------
try:
    from error_detector import ErrorDetector, get as get_detector
    _detector = ErrorDetector()
    try:
        _tk = None
        _detector._tracker = _tk
    except Exception:
        pass
    _detector_active = True
except Exception:
    _detector = None
    _detector_active = False

# ------------------------------------------------------------
# 成功日志持久化
# ------------------------------------------------------------
_SUCCESS_LOG_FILE = os.path.join(
    os.path.dirname(os.path.dirname(__file__)),
    "workspace", "success_log.json"
)

def _load_success_log():
    try:
        if os.path.exists(_SUCCESS_LOG_FILE):
            with open(_SUCCESS_LOG_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
    except Exception:
        pass
    return []

def _save_success_log(log):
    try:
        os.makedirs(os.path.dirname(_SUCCESS_LOG_FILE), exist_ok=True)
        with open(_SUCCESS_LOG_FILE, "w", encoding="utf-8") as f:
            json.dump(log, f, ensure_ascii=False, indent=2)
    except Exception:
        pass

_success_log = _load_success_log()

# ------------------------------------------------------------
# detect_failure: 全局操作失败检测
# ------------------------------------------------------------
def detect_failure(ctx: dict) -> dict:
    if not _detector_active or _detector is None:
        return {}
    return _detector.detect_and_record(ctx) or {}

# ------------------------------------------------------------
# detect_success: 检测操作成功并持久化到 success_patterns.json
# ------------------------------------------------------------
def detect_success(ctx: dict) -> dict:
    global _success_log
    if not _detector_active:
        return {}
    score = 0
    reasons = []
    dur = ctx.get("duration_ms", 0)
    if dur > 0 and dur < 10000:
        score += 1
        reasons.append("fast")
    retry = ctx.get("retry_count", 0)
    if retry == 0:
        score += 1
        reasons.append("no_retry")
    op = ctx.get("op", "")
    if op in ("git_push", "release", "file_write"):
        if retry == 0 and dur < 60000:
            score += 2
            reasons.append("complex_ops_success")
    if score >= 2:
        entry = {
            "time": datetime.datetime.now().isoformat(),
            "op": op,
            "detail": ctx.get("detail", "")[:80],
            "score": score,
            "reasons": reasons
        }
        _success_log.append(entry)
        _save_success_log(_success_log)
        if score >= 3:
            try:
                from evo.main import _get_engine
                from mindol.diegin_integration import memory_archive as dgen_archive
                from rule_engine import RuleEngine, SuccessPattern
                import datetime as dt
                engine = _get_engine()
                pattern_id = f"auto_success_{op}_{len(_success_log)}"
                existing_pattern = engine.get_pattern_by_id(pattern_id)
                if existing_pattern:
                    engine.update_pattern(pattern_id,
                        confidence=min(5.0, existing_pattern.confidence + 0.5),
                        triggered_count=existing_pattern.triggered_count + 1)
                else:
                    new_pattern = SuccessPattern(
                        id=pattern_id,
                        pattern_name=f"自动提取: {op} 成功模式",
                        trigger_scenario=f"{op} 操作成功",
                        decision_logic=f"op={op} score={score} reasons={','.join(reasons)}",
                        micro_template=f"{op}成功: {','.join(reasons)}",
                        logic_score=4.0, outcome_score=4.0,
                        confidence=min(5.0, score + 1.0),
                        source="auto_detect", lifecycle_status="active",
                        created_at=dt.datetime.now().isoformat(), triggered_count=1)
                    engine.add_pattern(new_pattern)
                engine.save_all()
            except Exception:
                pass
        return {"detected": True, "score": score, "reasons": reasons}
    return {"detected": False}

# ------------------------------------------------------------
# ensure_three_strikes: 一二不过三 · 错误跟踪入口
# ------------------------------------------------------------
def ensure_three_strikes(error_type: str, detail: str = "", severity: str = "high") -> dict:
    if not _detector_active or _detector is None:
        return {}
    return _detector.detect_and_record({
        "op": "file_write", "path": "", "data": b"",
        "force_error": error_type, "force_detail": detail,
        "force_severity": severity
    }) or {}

# ------------------------------------------------------------
# get_strike_status: 获取错误触发状态
# ------------------------------------------------------------
def get_strike_status(error_type: str = None) -> dict:
    try:
        from evo.main import _get_tracker as _gt
        tracker = _gt()
    except Exception:
        tracker = None
    if tracker is None:
        return {"status": "tracker_not_available"}
    try:
        if error_type:
            rule = tracker.rule_engine.get_interception_by_id(f"self_error_{error_type}")
            if rule:
                return {
                    "error_type": error_type,
                    "triggered_count": getattr(rule, "triggered_count", 0),
                    "severity": getattr(rule, "severity", "unknown"),
                    "confidence": getattr(rule, "confidence", 0),
                    "lifecycle": getattr(rule, "lifecycle_status", "unknown")
                }
            return {"error_type": error_type, "status": "never_triggered"}
        rules = tracker.rule_engine.get_interceptions(active_only=False)
        strikes = []
        for r in rules:
            if getattr(r, "triggered_count", 0) > 0:
                strikes.append({
                    "id": getattr(r, "id", ""),
                    "triggered": getattr(r, "triggered_count", 0),
                    "severity": getattr(r, "severity", ""),
                    "lifecycle": getattr(r, "lifecycle_status", "")
                })
        return {"status": "ok", "strike_rules": strikes}
    except Exception as e:
        return {"status": "error", "detail": str(e)}
