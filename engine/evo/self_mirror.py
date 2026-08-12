# -*- coding: utf-8 -*-
"""self_mirror.py - 自照镜·方向之镜（自我审视）
回望所行 → 静照本心 → 拨云见路 → 辨繁识简 → 笃定前行
职责：收集各原则执行轨迹生成自照报告、勇气信号（半衰期×0.6）、方向校准、归档 Mindol、
     通过 P6 语义记忆静默影响下一轮裁决（不凌驾 P0-P3）
定稿依据：律令九章 第九章 自照镜·方向之镜（2026-08-12 最终定稿）
"""
from __future__ import annotations

import datetime
import json
import os
from typing import Any, Dict, List, Optional

_STATE_PATH = None


def _get_state_path() -> str:
    global _STATE_PATH
    if _STATE_PATH is None:
        _STATE_PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))),
                                   "var", "state", "self_mirror.json")
    return _STATE_PATH


COURAGE_DECAY = 0.6        # 勇气信号半衰期式衰减：每轮剩余值 × 0.6
MIRROR_EVERY_ROUNDS = 10   # 跟随守三深度复盘频率：每10轮或每日
MIRROR_EVERY_DAYS = 1
COURAGE_DEFAULT = 0.5      # 单次勇气信号默认强度
COURAGE_MAX = 0.8          # P6 采信上限（score≥0.8 才采信；勇气信号封顶 0.8 保证进入 P6）


class SelfMirror:
    """自照镜执行器"""

    def __init__(self):
        self._path = _get_state_path()
        self._state: Dict[str, Any] = {
            "courage": 0.0,
            "round": 0,
            "last_decay_round": 0,
            "last_mirror_round": 0,
            "last_mirror_at": "",
            "total_courage_events": 0,
            "reports": [],
        }
        self._load()

    def _load(self) -> None:
        try:
            if os.path.exists(self._path):
                with open(self._path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                if isinstance(data, dict):
                    self._state.update({k: v for k, v in data.items() if k in self._state})
        except Exception:
            pass

    def _save(self) -> None:
        try:
            os.makedirs(os.path.dirname(self._path), exist_ok=True)
            with open(self._path, "w", encoding="utf-8") as f:
                json.dump(self._state, f, ensure_ascii=False, indent=2)
        except Exception:
            pass

    # ── 轮次与衰减 ─────────────────────────────────────────
    def tick(self) -> float:
        """每轮调用：轮次+1，勇气信号 ×0.6 半衰期衰减（每轮仅一次）"""
        self._state["round"] = int(self._state.get("round", 0) or 0) + 1
        _r = self._state["round"]
        if int(self._state.get("last_decay_round", 0) or 0) < _r:
            _c = float(self._state.get("courage", 0.0) or 0.0)
            if _c > 0:
                _c = _c * COURAGE_DECAY
                self._state["courage"] = round(_c, 4)
            self._state["last_decay_round"] = _r
        self._save()
        return float(self._state.get("courage", 0.0) or 0.0)

    def active_courage(self) -> float:
        return float(self._state.get("courage", 0.0) or 0.0)

    def add_courage(self, amount: float = COURAGE_DEFAULT, reason: str = "") -> float:
        """勇气信号：主动冒险获得超额收益 → P6 正面加权（对冲纠偏偏好）"""
        _c = float(self._state.get("courage", 0.0) or 0.0)
        _c = min(COURAGE_MAX, _c + float(amount))
        self._state["courage"] = round(_c, 4)
        self._state["total_courage_events"] = int(self._state.get("total_courage_events", 0) or 0) + 1
        if reason:
            self._state.setdefault("courage_log", []).append(
                {"round": self._state.get("round", 0), "amount": float(amount),
                 "reason": str(reason)[:200], "ts": datetime.datetime.now().isoformat()}
            )
        self._save()
        return self.active_courage()

    # ── 自照报告 ───────────────────────────────────────────
    def generate_report(self) -> Dict[str, Any]:
        """收集各原则执行轨迹（定稿第九章 互联素材）"""
        report: Dict[str, Any] = {"ts": datetime.datetime.now().isoformat(),
                                  "round": self._state.get("round", 0)}
        try:
            from evo.main import _get_engine, _get_closure_inst, _get_constancy_inst, _get_tracker
            eng = _get_engine()
            patterns = eng.get_patterns(active_only=True)
            report["攻七"] = {
                "入库模式数": len(patterns),
                "平均置信度": round(sum((getattr(p, "confidence", 0) or 0) for p in patterns) / max(1, len(patterns)), 2),
                "最高置信度": max(((getattr(p, "confidence", 0) or 0) for p in patterns), default=0),
            }
            staging = [r for r in eng.get_interceptions(active_only=False)
                       if getattr(r, "lifecycle_status", "") == "staging"]
            report["举一反三"] = {"staging池大小": len(staging)}
            cg = _get_closure_inst()
            report["止观"] = {"封存轮次数": cg.get_closed_count()}
            try:
                _cg = _get_constancy_inst()
                _cs = _cg.get_status()
                report["持存"] = {"总任务数": _cs.get("total_tasks", 0),
                                  "可恢复任务数": _cs.get("recoverable", 0)}
            except Exception:
                pass
        except Exception:
            pass
        try:
            _sd = os.path.join(os.path.dirname(self._path), "strikes_db.json")
            if os.path.exists(_sd):
                with open(_sd, "r", encoding="utf-8") as f:
                    _st = json.load(f)
                report["守三"] = {"strike数": len(_st) if isinstance(_st, dict) else 0}
        except Exception:
            pass
        try:
            _vt = os.path.join(os.path.dirname(self._path), "evidence_trail.json")
            if os.path.exists(_vt):
                with open(_vt, "r", encoding="utf-8") as f:
                    _tr = json.load(f)
                _dist = {}
                for _e in _tr:
                    _v = _e.get("verdict", "?")
                    _dist[_v] = _dist.get(_v, 0) + 1
                report["去伪存真"] = {"验证分布": _dist}
        except Exception:
            pass
        report["自照镜"] = {"勇气信号剩余": self.active_courage(),
                           "累计勇气事件": self._state.get("total_courage_events", 0)}
        return report

    def should_mirror(self) -> bool:
        """跟随守三深度复盘频率：每10轮或每日触发，未触发静默跳过"""
        _r = int(self._state.get("round", 0) or 0)
        _last = int(self._state.get("last_mirror_round", 0) or 0)
        if _r - _last >= MIRROR_EVERY_ROUNDS:
            return True
        _last_at = self._state.get("last_mirror_at", "")
        if _last_at:
            try:
                if (datetime.datetime.now() - datetime.datetime.fromisoformat(_last_at)).total_seconds() >= MIRROR_EVERY_DAYS * 86400:
                    return True
            except Exception:
                pass
        return False

    def mirror(self) -> Dict[str, Any]:
        """执行自照：生成报告 → 归档 Mindol → 更新轮次（静默跳过逻辑由调用方判断）"""
        report = self.generate_report()
        try:
            from mindol.diegin_integration import memory_archive
            _txt = "自照报告 r%d: %s" % (report.get("round", 0),
                                        json.dumps(report, ensure_ascii=False)[:800])
            memory_archive("self_mirror", _txt)
        except Exception:
            pass
        self._state["last_mirror_round"] = self._state.get("round", 0)
        self._state["last_mirror_at"] = datetime.datetime.now().isoformat()
        self._state.setdefault("reports", []).append(report)
        self._state["reports"] = self._state["reports"][-10:]
        self._save()
        return report

    def get_status(self) -> Dict[str, Any]:
        return {
            "principle": "自照镜·方向之镜",
            "round": self._state.get("round", 0),
            "courage": self.active_courage(),
            "total_courage_events": self._state.get("total_courage_events", 0),
            "last_mirror_round": self._state.get("last_mirror_round", 0),
            "last_mirror_at": self._state.get("last_mirror_at", ""),
            "should_mirror": self.should_mirror(),
        }


_inst: Optional[SelfMirror] = None


def get_self_mirror() -> SelfMirror:
    global _inst
    if _inst is None:
        _inst = SelfMirror()
    return _inst
