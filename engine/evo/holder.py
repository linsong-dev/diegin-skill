# -*- coding: utf-8 -*-
"""holder.py - 持行章(第十章·律令章)最小信号源 + 沙漏侧压系数（2026-09-05 终稿落地）

第十章是迭进运行过程的固有监控视角：附着在九章运行之上，贯穿所有环节，持续检视
九章的执行是否到位。持行章作为信号源生成三类信号（强制激活→预策律 / 阻断盲区→守三 /
规则沉积→举一反三），注入 pre_check 入口；作为资源感知层在侧放状态下计算侧压系数。

落地范围（2026-09-05 核验后最小批）：
- 只读规则库/阻断记录/激活统计，产出 JSON 信号与状态文件；
- 不自动改规则、不参与实时仲裁（staging + 人工确认门禁沿用）；
- 侧压系数只在侧放状态生效；P3 恢复期间挂起；深侧放(>0.75)只记录不强制降级动作。
"""
from __future__ import annotations

import datetime
import json
import os
import sqlite3

_VAR_DIR = None
_STATE_DIR = None


def _var_dir() -> str:
    global _VAR_DIR
    if _VAR_DIR is None:
        _VAR_DIR = os.path.join(
            os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
            "var")
    return _VAR_DIR


def _state_dir() -> str:
    global _STATE_DIR
    if _STATE_DIR is None:
        _STATE_DIR = os.path.join(_var_dir(), "state")
    return _STATE_DIR


def _load_json(path, default):
    try:
        if os.path.exists(path):
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
            if data is not None:
                return data
    except Exception:
        pass
    return default


def _save_json(path, data) -> bool:
    try:
        os.makedirs(os.path.dirname(path), exist_ok=True)
        tmp = path + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        os.replace(tmp, path)
        return True
    except Exception:
        return False


def _audit(event: str, payload: dict) -> None:
    try:
        log_dir = os.path.join(_var_dir(), "logs")
        os.makedirs(log_dir, exist_ok=True)
        with open(os.path.join(log_dir, "holder_audit.jsonl"), "a", encoding="utf-8") as f:
            f.write(json.dumps({"ts": datetime.datetime.now().isoformat(),
                                "event": event, **payload}, ensure_ascii=False) + "\n")
    except Exception:
        pass


def _round_now() -> int:
    sm = _load_json(os.path.join(_state_dir(), "self_mirror.json"), {})
    if isinstance(sm, dict):
        return int(sm.get("round", 0) or 0)
    return 0


def _holder_state() -> dict:
    st = _load_json(os.path.join(_state_dir(), "holder_state.json"), {})
    return st if isinstance(st, dict) else {}


def _save_holder_state(st: dict) -> None:
    _save_json(os.path.join(_state_dir(), "holder_state.json"), st)


# ────────────────────────────────────────────────
# ① 该用则用：激活统计 + 强制激活信号
# ────────────────────────────────────────────────
def record_activation(matched_ids, decision: str = "", win_id: str = "") -> None:
    """每轮 pre_check 记录：命中规则 ID、裁决方向、胜出规则 ID（仅计数，不调权重）"""
    try:
        if not matched_ids:
            return
        st = _holder_state()
        ring = st.get("activation_ring", [])
        rnd = _round_now()
        ring.append({"round": rnd,
                     "matched": [str(x) for x in matched_ids][:40],
                     "decision": str(decision)[:16],
                     "win_id": str(win_id or "")[:80]})
        st["activation_ring"] = ring[-100:]
        _save_holder_state(st)
    except Exception:
        pass


def force_activate_candidates(top: int = 10) -> list:
    """守三规则 5 轮内命中>=3 次但从未胜出 → '强制激活'候选（P4+ 权重，仅信号）"""
    st = _holder_state()
    ring = st.get("activation_ring", []) or []
    rnd = _round_now()
    recent = [r for r in ring if int(r.get("round", 0) or 0) >= rnd - 5]
    if not recent:
        return []
    hit = {}
    won = {}
    for r in recent:
        for rid in r.get("matched", []) or []:
            hit[rid] = hit.get(rid, 0) + 1
        w = r.get("win_id", "")
        if w:
            won[w] = won.get(w, 0) + 1
    out = []
    for rid, cnt in hit.items():
        if cnt >= 3 and won.get(rid, 0) == 0:
            out.append({"rule_id": rid, "hit_5rounds": cnt, "won": 0})
    out.sort(key=lambda x: -x["hit_5rounds"])
    return out[:top]


# ────────────────────────────────────────────────
# ② 该总结则总结：阻断盲区信号（→守三）
# ────────────────────────────────────────────────
def _aggregate_blind_zones(breach) -> list:
    """阻断盲区聚合（纯函数可测）：支持 dict{error_type:count} 与 list[{error_type,...}] 两种历史格式。
    同 error_type 计数累计>=2 → 提示守三复查同类判定条件。"""
    out = {}
    if isinstance(breach, list):
        for e in breach:
            if not isinstance(e, dict):
                continue
            et = str(e.get("error_type", ""))
            if not et:
                continue
            ent = out.setdefault(et, {"error_type": et, "breach_count": 0, "detail": ""})
            ent["breach_count"] += 1
            if not ent["detail"] and (e.get("detail") or e.get("last_detail")):
                ent["detail"] = str(e.get("detail") or e.get("last_detail"))[:120]
    elif isinstance(breach, dict):
        for k, v in breach.items():
            if isinstance(v, dict):
                cnt = int(v.get("count", 0) or 0)
                detail = str(v.get("detail") or v.get("last_detail") or "")[:120]
            elif isinstance(v, list):
                cnt = len(v)
                detail = ""
            else:
                cnt = int(v or 0)
                detail = ""
            if cnt >= 1:
                ent = out.setdefault(k, {"error_type": k, "breach_count": 0, "detail": detail})
                ent["breach_count"] += cnt
    return [v for v in out.values() if v["breach_count"] >= 2]


def blind_zone_candidates(top: int = 10) -> list:
    """一二不过三阻断记录中同类重复>=2 的条目 → 提示守三复查同类判定条件（→守三/复盘参考）"""
    breach = _load_json(os.path.join(_state_dir(), "dgen_breach_log.json"), None)
    if breach is None:
        return []
    out = _aggregate_blind_zones(breach)
    out.sort(key=lambda x: -x["breach_count"])
    return out[:top]



def _active_rules() -> list:
    """守三(拦截)规则源：读 engine/evo/rules/interception_rules.json 中非归档规则（兼容数组与 {rules:[]} 形态）。
    供规则沉积/阻断等信号统计；读取失败返回空（只读信号不阻断主链路）。"""
    try:
        _p = os.path.join(os.path.dirname(os.path.abspath(__file__)), "rules", "interception_rules.json")
        if not os.path.exists(_p):
            return []
        with open(_p, "r", encoding="utf-8") as _f:
            _data = json.load(_f)
        if isinstance(_data, list):
            _arr = _data
        elif isinstance(_data, dict):
            _arr = _data.get("rules") or _data.get("interceptions") or []
        else:
            _arr = []
        return [r for r in _arr if isinstance(r, dict)
                and str(r.get("lifecycle_status", "") or "").lower() not in ("archived", "")]
    except Exception:
        return []


def deposition_signal() -> dict:
    """守三规则激活率统计：激活率<20% 生成'规则沉积警告'，触发举一反三批处理优先处理"""
    rules = _active_rules()
    if not rules:
        return {"warning": False, "activation_rate": None, "candidates": []}
    now = datetime.datetime.now()
    cutoff = (now - datetime.timedelta(days=14)).isoformat()
    mature = [r for r in rules if str(r.get("created_at", "")) < cutoff]
    if not mature:
        return {"warning": False, "activation_rate": None, "candidates": [], "note": "成熟规则<14天窗口不足"}
    activated = [r for r in mature if int(r.get("triggered_count", 0) or 0) > 0]
    rate = round(len(activated) / len(mature), 3)
    cands = []
    if rate < 0.2:
        never = [r for r in mature if int(r.get("triggered_count", 0) or 0) == 0]
        never.sort(key=lambda r: str(r.get("created_at", "")))
        cands = [{"rule_id": r.get("id", ""),
                  "created_at": r.get("created_at", "")[:10],
                  "severity": r.get("severity", "")} for r in never[:15]]
    return {"warning": rate < 0.2, "activation_rate": rate,
            "active_total": len(mature), "activated": len(activated),
            "candidates": cands}


def hyperparam_review_needed() -> dict:
    """规则沉积/阻断频繁 连续 3 次评估触发 → 生成超参数审视报告(仅报告, 不自动调参)"""
    st = _holder_state()
    streak = int(st.get("deposition_streak", 0) or 0)
    sig = deposition_signal()
    if sig.get("warning"):
        streak += 1
    else:
        streak = 0
    st["deposition_streak"] = streak
    _save_holder_state(st)
    if streak >= 3:
        return {"needed": True, "streak": streak,
                "note": "连续3次规则沉积/阻断频繁评估触发，生成超参数审视报告供人工审阅（不自动调整阈值）"}
    return {"needed": False, "streak": streak}


# ────────────────────────────────────────────────
# ④ 该省则省：沙漏侧压系数（五项输入，仅侧放状态生效）
# ────────────────────────────────────────────────
# 权重(运维手册参数表 2026-09-05 权威)：延迟0.3 + 快照0.25 + Token0.25 + 积压0.2
SIDE_P_W_DELAY = 0.30
SIDE_P_W_SNAP = 0.25
SIDE_P_W_TOKEN = 0.25
SIDE_P_W_BACKLOG = 0.20
SIDE_P_TRIGGER = 0.75        # >0.75 深侧放
SNAP_THRESHOLD = 30          # 活跃快照阈值(个)
TOKEN_THRESHOLD = 0.70       # Token 占用阈值
BACKLOG_THRESHOLD = 3        # 自照镜报告积压阈值(份)
MALIGNANT_IDLE_ROUNDS = 5    # 恶性空闲：连续 5 轮无输入


def _snapshot_ratio() -> float:
    tasks = _load_json(os.path.join(_state_dir(), "constancy_tasks.json"), {})
    active = 0
    if isinstance(tasks, dict):
        for t in tasks.values():
            if isinstance(t, dict) and t.get("status") not in ("completed", "abandoned", "blocked"):
                active += 1
    elif isinstance(tasks, list):
        for t in tasks:
            if isinstance(t, dict) and t.get("status") not in ("completed", "abandoned", "blocked"):
                active += 1
    return round(min(1.0, active / SNAP_THRESHOLD), 3)


def _token_ratio() -> float:
    warn = _load_json(os.path.join(_state_dir(), "token_budget_warn.json"), {})
    if isinstance(warn, dict):
        for k in ("ratio", "token_ratio", "occupancy"):
            v = warn.get(k)
            try:
                fv = float(v)
                if 0 <= fv <= 1:
                    return round(fv, 3)
            except Exception:
                pass
    return 0.3


def _backlog_ratio() -> float:
    sm = _load_json(os.path.join(_state_dir(), "self_mirror.json"), {})
    n = 0
    if isinstance(sm, dict):
        reps = sm.get("reports", [])
        n = len(reps) if isinstance(reps, list) else 0
    return round(min(1.0, n / BACKLOG_THRESHOLD), 3)


def _latency_ratio() -> float:
    st = _holder_state()
    last = st.get("latency_sample", {})
    age = 999
    try:
        if last and last.get("ts"):
            age = (datetime.datetime.now() - datetime.datetime.fromisoformat(last["ts"])).total_seconds()
    except Exception:
        pass
    if age < 60:
        return float(last.get("score", 0.2) or 0.2)
    # 每 60 秒实测一次 Shalou(Shalou) 检索延迟（只读探测，失败回落默认 0.2）
    score = 0.2
    try:
        import time as _t
        from shalou import core as _core
        _t0 = _t.time()
        try:
            _core.search("迭进", top_k=1)
        except Exception:
            pass
        ms = (_t.time() - _t0) * 1000
        score = round(min(1.0, ms / 500.0), 3)
    except Exception:
        pass
    st["latency_sample"] = {"ts": datetime.datetime.now().isoformat(), "score": score}
    _save_holder_state(st)
    return score


def side_pressure(suspended: bool = False) -> dict:
    """侧压系数 = 延迟×0.3 + 快照×0.25 + Token×0.25 + 积压×0.2（恶性空闲时权重翻倍加速）"""
    if suspended:
        return {"suspended": True,
                "note": "P3(恒常门任务恢复)执行期间侧压系数挂起，恢复完成后恢复监测"}
    st = _holder_state()
    idle = int(st.get("idle_rounds", 0) or 0)
    d = _latency_ratio()
    s = _snapshot_ratio()
    t = _token_ratio()
    b = _backlog_ratio()
    malignant = idle >= MALIGNANT_IDLE_ROUNDS and s <= 0 and True  # 活跃任务=0 由 s<=0 近似 + strike 门下方
    strikes = _load_json(os.path.join(_state_dir(), "strikes_db.json"), {})
    strike_hits_3 = 0
    if isinstance(strikes, dict):
        for v in strikes.values():
            if isinstance(v, dict) and int(v.get("count", 0) or 0) > 0:
                strike_hits_3 += 1
    malignant = malignant and strike_hits_3 == 0
    mult = 2.0 if malignant else 1.0
    raw = d * SIDE_P_W_DELAY + s * SIDE_P_W_SNAP + t * SIDE_P_W_TOKEN + b * SIDE_P_W_BACKLOG
    coeff = min(1.0, raw * mult)
    return {
        "side_pressure": round(coeff, 3),
        "raw": round(raw, 3),
        "components": {"latency": d, "snapshot": s, "token": t, "backlog": b},
        "malignant_idle": malignant,
        "idle_rounds": idle,
        "deep_side": coeff > SIDE_P_TRIGGER,
        "note": "深侧放: 自照镜顺延/降级事件记录(卸载CoT、未验证staging、未命中strike轻量日志)；绝对保留P6基准+goal快照+活跃task指纹" if coeff > SIDE_P_TRIGGER else "",
    }


# ────────────────────────────────────────────────
# 模式驻留超时检测（攻七/守三状态标志 >3 轮复位）
# ────────────────────────────────────────────────
def _active_modes_from_state() -> list:
    """从真实状态文件识别当前激活的攻七/守三模式标志（替代仅 deep_review 标志）：
    - dgen_enforcement_mode.json mode=audit       → 守三·audit 模式
    - dgen_fatal_errors.json 非空                  → 守三·fatal 处置
    - dgen_human_escalation.json awaiting/locked   → 守三·人工等待/静默锁
    """
    out = []
    try:
        em = _load_json(os.path.join(_state_dir(), "dgen_enforcement_mode.json"), {})
        if isinstance(em, dict) and str(em.get("mode", "")) == "audit":
            out.append("shousan_audit_mode")
    except Exception:
        pass
    try:
        fatal = _load_json(os.path.join(_state_dir(), "dgen_fatal_errors.json"), {})
        if isinstance(fatal, dict) and fatal:
            out.append("shousan_fatal")
    except Exception:
        pass
    try:
        esc = _load_json(os.path.join(_state_dir(), "dgen_human_escalation.json"), {})
        if isinstance(esc, dict):
            _pending = [v for v in esc.values() if isinstance(v, dict)
                        and v.get("status") in ("awaiting_human", "silent_locked")]
            if _pending:
                out.append("shousan_human_wait")
    except Exception:
        pass
    return out


def mode_residency_check(active_modes: list, has_user_input: bool,
                         produced: bool = False, report_round: int = 0) -> list:
    """每轮入口调用：模式驻留超时检测（攻七/守三状态标志 >3 轮无产出且无用户输入 → 复位）。
    修复 v3.10 伪逻辑：模式不在本轮激活不再直接清理——只有 ①有用户输入（上下文切换）自然结束
    或 ②本模式已有产出（deep_review_report 生成）自然完成 或 ③超过3轮无产出无输入 才退出/复位。
    """
    st = _holder_state()
    modes = st.get("modes", {}) or {}
    rnd = report_round or _round_now()
    resets = []
    if produced:
        # 模式已产出结果（如应急复盘报告已生成）→ 视为自然完成，清理
        for m in list(modes.keys()):
            if m in (active_modes or []):
                modes.pop(m, None)
                _audit("mode_residency_completed", {"mode": m, "round": rnd})
        active_modes = []
    for m in list(modes.keys()):
        info = modes[m] or {}
        start = int(info.get("start_round", 0) or 0)
        last_act = int(info.get("last_activity_round", 0) or 0)
        if m in (active_modes or []):
            modes[m]["last_activity_round"] = rnd
            continue
        if has_user_input:
            # 新用户输入 = 模式上下文切换，自然结束（不视为卡死）
            modes.pop(m, None)
            continue
        if (rnd - max(start, last_act)) > 3:
            modes.pop(m, None)
            resets.append({"mode": m, "stuck_rounds": rnd - max(start, last_act),
                           "reason": "模式状态标志超过3轮连续运行无产出且无用户输入，自动复位"})
            _audit("mode_residency_reset", {"mode": m, "stuck_rounds": rnd - max(start, last_act)})
    for m in (active_modes or []):
        if m not in modes:
            modes[m] = {"start_round": rnd, "last_activity_round": rnd}
        else:
            modes[m]["last_activity_round"] = rnd
    st["modes"] = modes
    _save_holder_state(st)
    return resets



def note_round(has_user_input: bool) -> None:
    """记录空闲轮次（恶性空闲判定输入）"""
    st = _holder_state()
    idle = int(st.get("idle_rounds", 0) or 0)
    st["idle_rounds"] = 0 if has_user_input else min(100, idle + 1)
    _save_holder_state(st)


# ────────────────────────────────────────────────
# ⑤ 该保留则保留：case_prototype 空间扫描（守三深度复盘 → 举一反三迁移申请）
# ────────────────────────────────────────────────
def _memory_db_path() -> str:
    return os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(
        os.path.dirname(os.path.abspath(__file__))))), "shalou", "memory.db")


def scan_case_prototypes() -> dict:
    """扫描 Shalou(Shalou) case_prototype 空间：连续3次相似场景成功 → 向举一反三发'原型转规则'申请
    申请仅写入状态文件，迁移进 staging 仍需去伪存真 + 人工确认门禁。"""
    db_path = _memory_db_path()
    if not os.path.exists(db_path):
        return {"found": 0, "promotions": [], "note": "memory.db 不存在"}
    try:
        con = sqlite3.connect(db_path)
        cur = con.cursor()
        rows = cur.execute(
            "SELECT uid, text, metadata FROM memory_units WHERE space='case_prototype' AND status='active'"
        ).fetchall()
        con.close()
    except Exception:
        return {"found": 0, "promotions": [], "note": "读取失败"}
    promotions = []
    for uid, text, meta in rows:
        try:
            m = json.loads(meta) if meta else {}
        except Exception:
            m = {}
        succ = int(m.get("consecutive_success", 0) or 0)
        if succ >= 3:
            promotions.append({"uid": uid, "text": str(text)[:120],
                               "consecutive_success": succ,
                               "request": "原型转规则申请：举一反三按标准流程迁移为候选规则写入 staging"})
    path = os.path.join(_state_dir(), "case_prototype_promotions.json")
    if promotions:
        _save_json(path, {"ts": datetime.datetime.now().isoformat(), "promotions": promotions})
    return {"found": len(rows), "promotions": promotions, "note": ""}


# ────────────────────────────────────────────────
# ────────────────────────────────────────────────
# 沙漏流动模型协调（L1：翻转/360度停驻/读写平衡）—— 供 pre_check ch10 每轮调用
# ────────────────────────────────────────────────
_FLIP_USER_WORDS = {
    "natural": ("自然翻转",),
    "reverse": ("逆向翻转", "倒放", "180度"),
    "direction": ("方向翻转",),
    "accumulate": ("蓄势翻转", "蓄势"),
    "side": ("侧放", "停驻", "待机停驻", "90度"),
    "upright": ("正放", "0度"),
}


def _flip_storage_dir() -> str:
    """Shalou 存储目录（flip_state.json 所在）：与 memory.db 同目录。"""
    _d = os.path.dirname(_memory_db_path())
    return _d if os.path.isdir(_d) else ""


def shalou_flow_tick(round_no: int, has_user_input: bool, out: dict, result: dict) -> dict:
    """沙漏流动模型每轮协调：心跳 + 健康快照 + 自动翻转（读写平衡/规则沉积/方向信号）。
    只更新方向/停驻状态与审计，不改 Shalou 存储与规则。"""
    try:
        from shalou import flip as _sflip
    except Exception:
        return {}
    _sd = _flip_storage_dir()
    if not _sd:
        return {}
    try:
        _sflip.heartbeat(round_no, _sd, has_user_input=bool(has_user_input))
        out["flow"] = _sflip.health(_sd)
        _sig = out.get("signals") or {}
        _dep = _sig.get("deposition") or {}
        _mrr = result.get("mirror_report") or {}
        _dev = bool(_mrr.get("direction_calibration"))
        _auto = _sflip.maybe_flip(_sd, signals={"deposition_warning": bool(_dep.get("warning")),
                                                "direction_deviation": _dev})
        if _auto and _auto.get("ok") and _auto.get("event"):
            out["flip"] = _auto
            _ev = _auto["event"]
            _audit("shalou_flip", {"type": _ev.get("type"), "from_angle": _ev.get("from_angle"),
                                     "to_angle": _ev.get("to_angle"), "count": _ev.get("count"),
                                     "reason": str(_ev.get("reason", ""))[:120]})
        return out.get("flip") or {}
    except Exception:
        return {}


def user_flip(text: str, reason: str = "") -> dict:
    """主动翻转（用户触发，沙漏§2.2/§2.4）：按命令词执行翻转或任意角度停驻。
    返回 {ok, action, angle|flip_type,...}；非翻转命令返回 {"ok": False}。"""
    try:
        from shalou import flip as _sflip
    except Exception:
        return {"ok": False, "error": "shalou 不可用"}
    _sd = _flip_storage_dir()
    if not _sd:
        return {"ok": False, "error": "存储目录不可用"}
    _t = str(text or "").strip()
    if not _t:
        return {"ok": False}
    _has_flip = ("翻转" in _t) or any(w in _t for w in ("倒放", "正放", "侧放", "停驻", "蓄势"))
    if not _has_flip:
        return {"ok": False}
    _src = reason[:200] or ("用户指令: " + _t[:80])
    for _kind, _words in _FLIP_USER_WORDS.items():
        if any(w in _t for w in _words):
            if _kind == "side":
                _r = _sflip.set_angle(90.0, _sd, source="user", reason=_src)
                return {"ok": bool(_r.get("ok")), "action": "side_park", "angle": 90.0, "result": _r}
            if _kind == "upright":
                _r = _sflip.set_angle(0.0, _sd, source="user", reason=_src)
                return {"ok": bool(_r.get("ok")), "action": "upright_resume", "angle": 0.0, "result": _r}
            _r = _sflip.execute_flip(_kind, storage_dir=_sd, source="user", reason=_src)
            return {"ok": bool(_r.get("ok")), "action": _kind + "_flip", "result": _r}
    # 仅"翻转"无明确方向 → 180度倒放（沉淀提炼方向），由下次平衡/显式命令复位
    _r = _sflip.execute_flip("natural", storage_dir=_sd, source="user", reason=_src)
    return {"ok": bool(_r.get("ok")), "action": "flip", "result": _r}


# ────────────────────────────────────────────────
# pre_check 入口集成（信号注入）—— 第十章 P0 闭环入口
# ────────────────────────────────────────────────
def ch10_entry(context: dict, result: dict, matched_ids=None,
               deep_review_required: bool = False,
               deep_review_report=None) -> dict:
    """持行章每轮入口动作：激活统计 → 模式驻留超时(真实状态) → 三类信号 → 侧压系数(深侧放每日≤1次降级日志) → 案例原型扫描。

    守真·不越权：全程只读/落 JSON 状态，不自动改规则；阻断盲区/强制激活仅作为提示信号注入结果供裁决层参考。
    """
    out = {"principle": "持行·律令章", "source": "ch10_holder"}
    text = str(context.get("context", context.get("prompt", context.get("cmd", context.get("task", "")))))
    has_input = bool(text and str(text).strip())
    rnd = _round_now()
    out["round"] = rnd
    note_round(has_input)
    if matched_ids:
        record_activation(list(matched_ids), result.get("decision", ""), result.get("winning_rule_id", ""))
    # 模式驻留超时复位：真实状态文件(强制/审计/人工等待) + 应急标记；本回合已产出(deep_review_report)视为自然完成
    active_modes = _active_modes_from_state()
    if deep_review_required and "shousan_emergency" not in active_modes:
        active_modes.append("shousan_emergency")
    produced = bool(deep_review_report)
    if produced:
        out["mode_produced"] = True
    resets = mode_residency_check(active_modes, has_input, produced=produced)
    if resets:
        out["mode_resets"] = resets
    # 三类信号 + 超参数审视（只读，供裁决层提示性消费；不做任何自动改规则动作）
    out["signals"] = {
        "force_activate": force_activate_candidates(),
        "blind_zone": blind_zone_candidates(),
        "deposition": deposition_signal(),
        "hyperparam_review": hyperparam_review_needed(),
    }
    # 该省则省：P3(恒常门恢复)期间侧压系数挂起；深侧放(>0.75)每日≤1次降级事件日志（只记录不强制动作）
    p3_active = bool(result.get("constancy_recovery") and
                     (result["constancy_recovery"].get("resumed") or
                      result["constancy_recovery"].get("resume_requested")))
    out["side_pressure"] = side_pressure(suspended=p3_active)
    _sp = out["side_pressure"]
    if _sp.get("deep_side") and not _sp.get("suspended"):
        _today = datetime.datetime.now().strftime("%Y-%m-%d")
        _st = _holder_state()
        _dse = _st.get("deep_side_events") or {}
        if not isinstance(_dse, dict) or _dse.get("date") != _today:
            _st["deep_side_events"] = {"date": _today, "count": 1,
                                         "coeff": _sp.get("side_pressure"),
                                         "round": rnd,
                                         "ts": datetime.datetime.now().isoformat()}
            _save_holder_state(_st)
            _audit("deep_side_demotion_log",
                   {"date": _today, "coeff": _sp.get("side_pressure"),
                    "daily_cap": 1, "round": rnd})
            out["deep_side_log"] = {"date": _today, "count": 1,
                                      "note": "深侧放(>0.75)：当日降级事件日志已记1次（上限每日1次）"}
        else:
            out["deep_side_log"] = {"date": _today, "count": int(_dse.get("count", 0) or 0),
                                      "skipped": True,
                                      "note": "深侧放(>0.75)：当日已达1次降级事件日志上限，本轮仅提示不重复记录"}
    # 案例原型扫描：守三深度复盘(应急)时执行 → 举一反三迁移申请
    if deep_review_required:
        out["case_prototypes"] = scan_case_prototypes()
    # 沙漏流动模型(L1)：心跳/健康/自动翻转协调（只更新方向状态，不改存储与规则）
    try:
        _flow = shalou_flow_tick(rnd, has_input, out, result)
        if _flow:
            out["flip_auto"] = _flow
    except Exception:
        pass
    # 主动翻转（用户指令：翻转/倒放/正放/侧放/停驻/蓄势）
    try:
        _uf = user_flip(text)
        if _uf.get("ok"):
            out["user_flip"] = _uf
            _audit("shalou_flip_user", {"action": _uf.get("action"), "ts": datetime.datetime.now().isoformat()})
    except Exception:
        pass
    _save_json(os.path.join(_state_dir(), "ch10_signals.json"), out)
    return out


# ────────────────────────────────────────────────
# 该留则留：case_prototype 登记/战绩（verify_fix 改毕验 → 连续成功 → 举一反三迁移申请）
# ────────────────────────────────────────────────
def register_case_prototype(scenario_key: str, text: str = "", source: str = "case_prototype") -> dict:
    """case_prototype 幂等登记：uid 由场景键(scenario_key)派生，同场景重复登记只写一次（战绩保留不重置）。
    已存在 → 直接沿用；新增 → 写入 shalou.diegin_integration（沙漏权威存储）。"""
    try:
        from shalou import diegin_integration as _di
    except Exception:
        return {"uid": "", "created": False, "error": "shalou 不可用"}
    _key = str(scenario_key or "").strip()
    if not _key:
        return {"uid": "", "created": False, "error": "空场景键"}
    try:
        _uid = _di.case_uid(str(_key))
        _existing = _di._get_adapter()._ensure_core().get_unit(_uid)
        if _existing is not None:
            return {"uid": _uid, "created": False, "existing": True}
        _stored = str(text or _key)[:2000]
        _uid2 = _di.write_case_prototype(_stored, source=source, uid_seed=str(_key))
        return {"uid": _uid2 or _uid, "created": True}
    except Exception as _e:
        return {"uid": "", "created": False, "error": str(_e)[:120]}


def record_case_success(uid: str, ok: bool = True, note: str = "") -> dict:
    """case_prototype 战绩记录：成功 → consecutive_success+1；失败 → 清零。
    达阈值(promotable, >=3 连续成功) → 刷新 case_prototype_promotions.json 迁移申请（只写申请，门禁不变）。"""
    try:
        from shalou import diegin_integration as _di
    except Exception:
        return {"found": False, "error": "shalou 不可用"}
    if not uid:
        return {"found": False, "error": "空 uid"}
    try:
        _r = _di.record_case_outcome(uid, ok=bool(ok), note=str(note)[:120])
        if _r.get("found") and _r.get("promotable"):
            _append_promotion_candidate(uid, _r)
            _audit("case_prototype_promotable",
                   {"uid": uid, "consecutive_success": _r.get("consecutive_success", 0)})
        return _r
    except Exception as _e:
        return {"found": False, "uid": uid, "error": str(_e)[:120]}


def _append_promotion_candidate(uid: str, outcome: dict) -> None:
    """达晋升阈值的 case_prototype → 写入迁移申请文件（重复晋升刷新条目，不重复累积）。"""
    _path = os.path.join(_state_dir(), "case_prototype_promotions.json")
    _cur = _load_json(_path, {})
    if not isinstance(_cur, dict):
        _cur = {}
    _pros = _cur.get("promotions") if isinstance(_cur.get("promotions"), list) else []
    _pros = [x for x in _pros if x.get("uid") != uid]
    _pros.append({"uid": uid,
                  "text": _case_unit_text(uid),
                  "consecutive_success": int(outcome.get("consecutive_success", 0) or 0),
                  "total_success": int(outcome.get("total_success", 0) or 0),
                  "total_fail": int(outcome.get("total_fail", 0) or 0),
                  "request": "原型转规则申请：举一反三按标准流程迁移为候选规则写入 staging",
                  "ts": datetime.datetime.now().isoformat()})
    _cur["ts"] = datetime.datetime.now().isoformat()
    _cur["promotions"] = _pros[-50:]
    _save_json(_path, _cur)


def _case_unit_text(uid: str) -> str:
    try:
        from shalou import diegin_integration as _di
        _u = _di._get_adapter()._ensure_core().get_unit(uid)
        if _u is not None:
            return str(getattr(_u, "text", ""))[:200]
    except Exception:
        pass
    return ""
