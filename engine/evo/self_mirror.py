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
WARM_START_SKIPS = 5        # 温启动：连续跳过≥5次 → 下次强制轻量校准模式
WARM_START_DAYS = 3         # 或距上次运行≥3天


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
            "pending_courage": 0.0,
            "pending_courage_round": 0,
            "same_dir_streak": 0,
            "consecutive_skips": 0,
            "last_dir_kind": "",
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

    def add_courage(self, amount: float = COURAGE_DEFAULT, reason: str = "", pending: bool = False) -> float:
        """勇气信号（定稿第九章）：主动冒险获得超额收益 → 记入待确认（pending），
        须在下一轮用户交互中确认方可生效；无确认自动归零。pending=False 直接生效（向后兼容）。"""
        _amt = float(amount)
        self._state["total_courage_events"] = int(self._state.get("total_courage_events", 0) or 0) + 1
        if pending:
            _pc = float(self._state.get("pending_courage", 0.0) or 0.0)
            self._state["pending_courage"] = round(min(COURAGE_MAX, _pc + _amt), 4)
            self._state["pending_courage_round"] = self._state.get("round", 0)
        else:
            _c = float(self._state.get("courage", 0.0) or 0.0)
            self._state["courage"] = round(min(COURAGE_MAX, _c + _amt), 4)
        if reason:
            self._state.setdefault("courage_log", []).append(
                {"round": self._state.get("round", 0), "amount": _amt,
                 "pending": pending, "reason": str(reason)[:200], "ts": datetime.datetime.now().isoformat()}
            )
        self._save()
        return self.active_courage()

    def confirm_courage(self, confirmed: bool) -> float:
        """勇气信号外部确认（定稿第九章）：下一轮用户交互确认——未负面反馈且任务目标达成 → 生效；
        否则自动归零，不进入 P6 调权。"""
        _pc = float(self._state.get("pending_courage", 0.0) or 0.0)
        if _pc > 0:
            if confirmed:
                _c = float(self._state.get("courage", 0.0) or 0.0)
                self._state["courage"] = round(min(COURAGE_MAX, _c + _pc), 4)
                self._state.setdefault("courage_log", []).append(
                    {"round": self._state.get("round", 0), "amount": _pc, "confirmed": True,
                     "reason": "用户下一轮确认生效", "ts": datetime.datetime.now().isoformat()}
                )
            else:
                self._state.setdefault("courage_log", []).append(
                    {"round": self._state.get("round", 0), "amount": _pc, "confirmed": False,
                     "reason": "用户负面反馈/未确认，自动归零", "ts": datetime.datetime.now().isoformat()}
                )
            self._state["pending_courage"] = 0.0
            self._state["pending_courage_round"] = 0
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
                _tasks = getattr(_cg, "_tasks", {}) or {}
                _n = len(_tasks)
                _completed = sum(1 for t in _tasks.values() if t.get("status") == "completed")
                _abandoned = sum(1 for t in _tasks.values() if t.get("status") == "abandoned")
                _paused = sum(1 for t in _tasks.values() if t.get("status") == "paused")
                _blocked = sum(1 for t in _tasks.values() if t.get("status") == "blocked")
                _resumes = sum(int((t.get("resume_count") or 0)) for t in _tasks.values())
                _block_reports = sum(1 for t in _tasks.values() if (t.get("blocker_report") or "").strip())
                _dur_h = 0.0
                import datetime as _dtm
                for t in _tasks.values():
                    if t.get("status") == "completed" and t.get("created_at") and t.get("updated_at"):
                        try:
                            _dur_h += (_dtm.datetime.fromisoformat(t["updated_at"])
                                       - _dtm.datetime.fromisoformat(t["created_at"])).total_seconds() / 3600
                        except Exception:
                            pass
                report["持存"] = {
                    "总任务数": _n,
                    "可恢复任务数": _cs.get("recoverable", 0),
                    "完成率": round(_completed / _n, 3) if _n else 0,
                    "中断率": round((_paused + _blocked) / _n, 3) if _n else 0,
                    "恢复率": round(_resumes / _n, 3) if _n else 0,
                    "平均任务时长(h)": round(_dur_h / _completed, 2) if _completed else 0,
                    "阻塞上报次数": _block_reports,
                }
            except Exception:
                pass
        except Exception:
            pass
        try:
            _sd = os.path.join(os.path.dirname(self._path), "strikes_db.json")
            if os.path.exists(_sd):
                with open(_sd, "r", encoding="utf-8") as f:
                    _st = json.load(f)
                if isinstance(_st, dict):
                    _entries = [v for v in _st.values() if isinstance(v, dict)]
                    _by_prefix = {}
                    for _k, _v in _st.items():
                        if isinstance(_v, dict):
                            _p = str(_k).split("_")[0]
                            _by_prefix[_p] = _by_prefix.get(_p, 0) + 1
                    report["一二不过三"] = {
                        "阻断类型数": len(_entries),
                        "累计触发次数": sum(int(_e.get("count", 0) or 0) for _e in _entries),
                        "根因分布": _by_prefix,
                    }
        except Exception:
            pass
        _ov_n = 0
        try:
            _ov = os.path.join(os.path.dirname(self._path), "dgen_overrides.json")
            if os.path.exists(_ov):
                with open(_ov, "r", encoding="utf-8") as f:
                    _raw = f.read().strip()
                if _raw:
                    _od = json.loads(_raw)
                    if isinstance(_od, list):
                        _ov_n = len(_od)
                    elif isinstance(_od, dict):
                        _ov_n = sum(1 for v in _od.values() if isinstance(v, dict) and v.get("blocked_error_type"))
        except Exception:
            pass
        report["预策"] = {"升级阻断数": _ov_n,
                          "冲突裁决近似": _ov_n}  # override 条目数≈升级阻断/冲突裁决面
        try:
            _sd = os.path.join(os.path.dirname(self._path), "strikes_db.json")
            if os.path.exists(_sd):
                with open(_sd, "r", encoding="utf-8") as f:
                    _st = json.load(f)
                if isinstance(_st, dict):
                    _entries = [v for v in _st.values() if isinstance(v, dict)]
                    report["守三"] = {"strike数": len(_entries),
                                      "根因分类数": len({str(_e.get("error_type", "?")).split("_")[0] for _e in _entries})}
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
                report["去伪存真"] = {"验证请求数": len(_tr) if isinstance(_tr, list) else 0,
                                     "验证分布": _dist,
                                     "误判/伪记录": int(_dist.get("假", 0)) + int(_dist.get("misattributed", 0))}
        except Exception:
            pass
        report["自照镜"] = {"勇气信号剩余": self.active_courage(),
                           "累计勇气事件": self._state.get("total_courage_events", 0)}
        report["direction_calibration"] = self._build_direction_calibration(report)
        return report

    def _build_direction_calibration(self, report: Dict[str, Any]) -> List[str]:
        """方向校准信号（定稿第九章步骤③）：冗余/偏离信号，仅建议不产生规则。
        信号写 Mindol 供预策 P6 / 攻七 / 守三 / 举一反三检索参考；不直接调规则库。"""
        _sig = []
        try:
            _gq = report.get("攻七") or {}
            if int(_gq.get("入库模式数", 0) or 0) >= 30 and float(_gq.get("平均置信度", 5.0) or 5.0) < 4.5:
                _sig.append("攻七: 模式库膨胀（%d 条, 均信 %.1f），建议收敛空壳/低置信模式" % (
                    int(_gq.get("入库模式数", 0)), float(_gq.get("平均置信度", 0))))
        except Exception:
            pass
        try:
            _cs = report.get("持存") or {}
            _rate = float(_cs.get("中断率", 0) or 0)
            if _rate > 0.5:
                _sig.append("恒常门: 中断率 %.0f%%，任务易断，建议优先恢复未完成任务" % (_rate * 100))
        except Exception:
            pass
        try:
            _sm = report.get("自照镜") or {}
            _jy = report.get("举一反三") or {}
            if int(_sm.get("累计勇气事件", 0) or 0) == 0 and int(_jy.get("staging池大小", 0) or 0) == 0:
                _sig.append("方向偏保守: 无冒险事件且无泛化候选在验，建议适度主动验证")
        except Exception:
            pass
        return _sig

    def note_skip(self) -> int:
        """温启动（运维手册 2.1）：记录一次未触发的跳过"""
        self._state["consecutive_skips"] = int(self._state.get("consecutive_skips", 0) or 0) + 1
        self._save()
        return self._state["consecutive_skips"]

    def reset_skip(self) -> None:
        """触发运行后清零跳过计数"""
        if self._state.get("consecutive_skips"):
            self._state["consecutive_skips"] = 0
            self._save()

    def warm_start_due(self) -> bool:
        """连续跳过≥WARM_START_SKIPS 或距上次≥WARM_START_DAYS → 强制轻量校准"""
        if int(self._state.get("consecutive_skips", 0) or 0) >= WARM_START_SKIPS:
            return True
        _last = self._state.get("last_mirror_at", "")
        if _last:
            try:
                if (datetime.datetime.now() - datetime.datetime.fromisoformat(_last)).days >= WARM_START_DAYS:
                    return True
            except Exception:
                pass
        return False

    def should_mirror(self) -> bool:
        """跟随守三深度复盘频率：每10轮或每日触发；且距上次运行至少≥3轮或≥1小时（定稿第九章最小间隔），未触发静默跳过"""
        _r = int(self._state.get("round", 0) or 0)
        _last = int(self._state.get("last_mirror_round", 0) or 0)
        _last_at = self._state.get("last_mirror_at", "")
        if _last_at:
            try:
                _gap_h = (datetime.datetime.now() - datetime.datetime.fromisoformat(_last_at)).total_seconds() / 3600
                if (_r - _last) < 3 and _gap_h < 1:
                    return False
            except Exception:
                pass
        if _r - _last >= MIRROR_EVERY_ROUNDS:
            return True
        if _last_at:
            try:
                if (datetime.datetime.now() - datetime.datetime.fromisoformat(_last_at)).total_seconds() >= MIRROR_EVERY_DAYS * 86400:
                    return True
            except Exception:
                pass
        return False

    def _signal_kind(self, report: Dict[str, Any]) -> str:
        """方向信号类型：down（收敛/降权）/ up（激活/促进）/ mixed / none"""
        _sig = report.get("direction_calibration") or []
        _down = sum(1 for s in _sig if any(w in str(s) for w in ("收敛", "降权", "膨胀")))
        _up = len(_sig) - _down
        if _down and _up:
            return "mixed"
        if _down:
            return "down"
        if _up:
            return "up"
        return "none"

    def mirror(self, emergency: bool = False, light: bool = False) -> Dict[str, Any]:
        """执行自照：生成报告 → 归档 Mindol → 更新轮次（静默跳过逻辑由调用方判断）
        emergency=True（守三应急复盘触发）：仅记录照镜素材，不产出 P6 调权信号（定稿第九章约束）。
        同向熔断：连续两次对同一方向（下调/上调）干扰 → 本次静默，中断递归循环。"""
        report = self.generate_report()
        _kind = self._signal_kind(report)
        _prev = str(self._state.get("last_dir_kind", "") or "")
        if _kind == _prev and _kind in ("down", "up"):
            _streak = int(self._state.get("same_dir_streak", 0) or 0) + 1
        else:
            _streak = 1 if _kind in ("down", "up") else 0
        self._state["same_dir_streak"] = _streak
        self._state["last_dir_kind"] = _kind
        _silent = _streak >= 2
        _suppress = bool(emergency) or _silent or bool(light)
        if light:
            # 温启动·轻量校准模式：仅统计报告，不产出 P6 调权（运维手册 2.1）
            report["warm_start"] = True
            report["wakeup_report"] = "系统长期未自照，已进入轻量校准模式：仅对任务完成率/中断率做统计对比，不产出P6调权"
        if _suppress:
            report["direction_calibration"] = []
            report["emergency_suppressed"] = bool(emergency)
            report["same_dir_silenced"] = bool(_silent)
            if _silent:
                self._state["same_dir_streak"] = 0
        try:
            from mindol.diegin_integration import memory_archive
            _txt = "自照报告 r%d: %s" % (report.get("round", 0),
                                        json.dumps(report, ensure_ascii=False)[:800])
            memory_archive("self_mirror", _txt)
            _dir = report.get("direction_calibration") or []
            if _dir:
                memory_archive("direction_calibration", "r%d %s" % (
                    report.get("round", 0), " | ".join(str(x) for x in _dir)[:500]))
        except Exception:
            pass
        self._state["last_mirror_round"] = self._state.get("round", 0)
        self._state["last_mirror_at"] = datetime.datetime.now().isoformat()
        self._state.setdefault("reports", []).append(report)
        self._state["reports"] = self._state["reports"][-10:]
        self._save()
        self._write_report_files(report)
        return report

    def _write_report_files(self, report):
        try:
            _rep_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))),
                                    "var", "reports")
            os.makedirs(_rep_dir, exist_ok=True)
            _r = int(report.get("round", 0) or 0)
            _base = os.path.join(_rep_dir, "self_mirror_r%d" % _r)
            with open(_base + ".json", "w", encoding="utf-8") as _f:
                json.dump(report, _f, ensure_ascii=False, indent=2)
            _lines = []
            _lines.append("# 自照镜报告 r%d · %s" % (_r, report.get("ts", "")))
            _lines.append("")
            _lines.append("## 九章素材")
            _lines.append("| 原则 | 关键指标 |")
            _lines.append("|:--|:--|")
            for _k, _v in report.items():
                if isinstance(_v, dict):
                    _s = "; ".join("%s=%s" % (kk, vv) for kk, vv in _v.items())
                    _lines.append("| %s | %s |" % (_k, _s[:200]))
            _sig = report.get("direction_calibration") or []
            _lines.append("")
            _lines.append("## 方向校准信号")
            _lines.append("- " + (" | ".join(str(x) for x in _sig) if _sig else "无"))
            _lines.append("")
            _lines.append("## 状态")
            _lines.append("- 同向熔断静默: %s" % report.get("same_dir_silenced", False))
            _lines.append("- 应急抑制: %s" % report.get("emergency_suppressed", False))
            _lines.append("- 温启动: %s" % report.get("warm_start", False))
            _lines.append("")
            _lines.append("## L1 挂载点（待人工确认）")
            _lines.append("- 2.11 真理跌落听证: （空）")
            _lines.append("- 2.12 影子基线池漂移: （空）")
            _lines.append("- 2.14 新鲜度指数: （空）")
            _lines.append("- 2.16 宪法解释请求: （空）")
            with open(_base + ".md", "w", encoding="utf-8") as _f:
                _f.write("\n".join(_lines) + "\n")
            _mds = sorted([f for f in os.listdir(_rep_dir) if f.startswith("self_mirror_r") and f.endswith(".md")])
            while len(_mds) > 30:
                _old = _mds.pop(0)
                _r_old = _old.replace("self_mirror_r", "").replace(".md", "")
                for _suf in (".md", ".json"):
                    _fp = os.path.join(_rep_dir, "self_mirror_r" + _r_old + _suf)
                    if os.path.exists(_fp):
                        os.remove(_fp)
        except Exception:
            pass

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
