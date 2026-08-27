#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""diegin_cron.py - P3-12 cron 批处理调度器（宕机时段维护 + 深度复盘 + 健康刷新）
用法:
  python diegin_cron.py due        # 检查并运行到期任务（供 Windows 计划任务调用）
  python diegin_cron.py run <job>  # 强制运行指定任务
  python diegin_cron.py status     # 查看 cron 状态
"""
import io, sys, os, json, datetime

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
STATE = os.path.join(BASE, "var", "state")
CRON_STATE = os.path.join(STATE, "cron_state.json")
HEALTH = os.path.join(BASE, "workspace", "rule_health.json")
AUDIT = os.path.join(BASE, "var", "logs", "diegin_audit.log")


def _append_audit(msg):
    try:
        os.makedirs(os.path.dirname(AUDIT), exist_ok=True)
        try:
            from _audit_rotate import rotate_audit_log
            rotate_audit_log(AUDIT)
        except Exception:
            pass
        _line = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")[:-3] + " " + msg + "\n"
        with open(AUDIT, "a", encoding="utf-8") as f:
            f.write(_line)
    except Exception:
        pass


def _load_state():
    if os.path.exists(CRON_STATE):
        try:
            with open(CRON_STATE, "r", encoding="utf-8-sig") as f:
                return json.load(f)
        except Exception:
            pass
    return {"last_run": {}, "failures": {}, "runs": {}, "history": []}


def _save_state(st):
    os.makedirs(STATE, exist_ok=True)
    with open(CRON_STATE, "w", encoding="utf-8") as f:
        json.dump(st, f, ensure_ascii=False, indent=2)


def _read_config():
    cfg = {}
    _cp = os.path.join(BASE, "config", "config.toml")
    if os.path.isfile(_cp):
        try:
            import tomllib
            with open(_cp, "rb") as f:
                cfg = tomllib.load(f)
        except Exception:
            pass
    cron_cfg = cfg.get("cron", {})
    return {
        "downtime_start": cron_cfg.get("downtime_start", "23:00"),
        "downtime_end": cron_cfg.get("downtime_end", "06:00"),
        "maintenance_interval_h": int(cron_cfg.get("maintenance_interval_h", 24) or 24),
        "deep_review_interval_h": int(cron_cfg.get("deep_review_interval_h", 24) or 24),
        "health_interval_h": int(cron_cfg.get("health_interval_h", 6) or 6),
    }


def _in_window(start, end, now=None):
    now = now or datetime.datetime.now()
    cur = now.hour * 60 + now.minute
    s = int(start.split(":")[0]) * 60 + int(start.split(":")[1])
    e = int(end.split(":")[0]) * 60 + int(end.split(":")[1])
    if s <= e:
        return s <= cur < e
    return cur >= s or cur < e  # 跨午夜


def _due(last_run, interval_h, window, now=None):
    now = now or datetime.datetime.now()
    if window:
        if not _in_window(window[0], window[1], now):
            return False
    if not last_run:
        return True
    try:
        last = datetime.datetime.fromisoformat(last_run)
        if last.tzinfo is not None:
            last = last.replace(tzinfo=None)
    except Exception:
        return True
    return (now - last).total_seconds() >= interval_h * 3600


def _job_downtime_maintenance(cfg):
    """宕机时段维护：规则 TTL/淘汰/复审 + 全量维护（run_maintenance）"""
    sys.path.insert(0, os.path.join(BASE, "engine"))
    sys.path.insert(0, os.path.join(BASE, "engine", "evo"))
    from evo.main import run_maintenance
    run_maintenance()
    return {"ok": True, "note": "宕机时段维护完成"}


def _job_deep_review(cfg):
    """深度复盘：对 strikes_db 失败教训做负向深挖，产出复盘报告（不新建规则）"""
    _st = {}
    _sp = os.path.join(STATE, "strikes_db.json")
    if os.path.exists(_sp):
        try:
            with open(_sp, "r", encoding="utf-8-sig") as f:
                _st = json.load(f)
        except Exception:
            pass
    sys.path.insert(0, os.path.join(BASE, "engine"))
    sys.path.insert(0, os.path.join(BASE, "engine", "evo"))
    from evo.reviewer import Reviewer
    from evo.main import _get_engine
    _rv = Reviewer(_get_engine())
    report = []
    for _etype, _info in _st.items():
        if not isinstance(_info, dict):
            continue
        _detail = str(_info.get("last_detail") or "")[:200]
        _signals = _rv._negative_deep_review({"status": "failed", "error_type": _etype, "detail": _detail, "error": _detail})
        report.append({"error_type": _etype, "count": _info.get("count", 0),
                       "detail": _detail, "signals": len(_signals)})
    _rp = os.path.join(STATE, "deep_review_report.json")
    _out = {"ts": datetime.datetime.now().isoformat(), "reviewed": report}
    with open(_rp, "w", encoding="utf-8") as f:
        json.dump(_out, f, ensure_ascii=False, indent=2)
    _append_audit(f"[CRON] deep_review 完成: {len(report)} 项失败教训复盘")
    return {"ok": True, "reviewed": len(report)}


def _job_health_report(cfg):
    """健康刷新：cronFailureRate 由硬编码改为真实统计"""
    st = _load_state()
    runs = sum(st.get("runs", {}).values())
    fails = sum(st.get("failures", {}).values())
    rate = round(100.0 * fails / max(runs, 1))
    if os.path.exists(HEALTH):
        try:
            with open(HEALTH, "r", encoding="utf-8-sig") as f:
                health = json.load(f)
            health.setdefault("metrics", {})["cronFailureRate"] = {
                "value": rate, "count": runs,
                "desc": "cron定时任务失败率(真实统计: 失败%d/总%d)" % (fails, runs),
            }
            health["lastUpdated"] = datetime.datetime.now().strftime("%Y-%m-%d %H:%M")
            with open(HEALTH, "w", encoding="utf-8") as f:
                json.dump(health, f, ensure_ascii=False, indent=2)
        except Exception:
            pass
    return {"ok": True, "cronFailureRate": rate, "runs": runs, "failures": fails}




def _deep_review_interval_h(cfg):
    """P1b（2026-08-25）：深度复盘间隔随错误态势自适应（缓急律·该省则省该用则用）。
    错误率高（活跃未修复错误>=2，或24h内有复发）→ 6h 密集复盘；
    平稳 → 默认24h。避免高频使用下错误反复出现却等不到每日复盘。"""
    try:
        _sp = os.path.join(STATE, "strikes_db.json")
        if not os.path.isfile(_sp):
            return cfg["deep_review_interval_h"]
        with open(_sp, "r", encoding="utf-8") as _f:
            _strikes = json.load(_f)
        _active = 0
        _recent = 0
        _now = datetime.datetime.now()
        for _k, _v in _strikes.items():
            if not isinstance(_v, dict):
                continue
            if _v.get("status") == "dormant":
                continue
            _cnt = _v.get("count", 0) or 0
            if _cnt >= 2:
                _active += 1
            _ls = _v.get("last_seen", "")
            if _ls:
                try:
                    _last = datetime.datetime.fromisoformat(_ls)
                    if (_now - _last).total_seconds() < 24 * 3600:
                        _recent += 1
                except Exception:
                    pass
        # 高错误态势 → 6h；否则默认 24h
        if _active >= 2 or _recent >= 1:
            return 6
        return cfg["deep_review_interval_h"]
    except Exception:
        return cfg["deep_review_interval_h"]

JOBS = {
    "downtime_maintenance": {"interval_h": lambda c: c["maintenance_interval_h"],
                             "window": lambda c: (c["downtime_start"], c["downtime_end"]),
                             "fn": _job_downtime_maintenance},
    "deep_review": {"interval_h": lambda c: _deep_review_interval_h(c),
                    "window": lambda c: (c["downtime_start"], c["downtime_end"]),
                    "fn": _job_deep_review},
    "health_report": {"interval_h": lambda c: c["health_interval_h"],
                      "window": lambda c: None,
                      "fn": _job_health_report},
}


def run_job(name, cfg, force=False):
    st = _load_state()
    job = JOBS[name]
    if not force and not _due(st["last_run"].get(name), job["interval_h"](cfg), job["window"](cfg)):
        return {"job": name, "ran": False, "reason": "not_due"}
    st["runs"][name] = st["runs"].get(name, 0) + 1
    try:
        result = job["fn"](cfg)
        st["last_run"][name] = datetime.datetime.now().isoformat()
        st["history"].append({"job": name, "ts": datetime.datetime.now().isoformat(), "ok": True})
        st["history"] = st["history"][-200:]
        _save_state(st)
        _append_audit(f"[CRON] {name} 成功")
        print(f"[CRON] {name} 完成: {json.dumps(result, ensure_ascii=False)[:200]}")
        return {"job": name, "ran": True, "ok": True, "result": result}
    except Exception as e:
        st["failures"][name] = st["failures"].get(name, 0) + 1
        st["history"].append({"job": name, "ts": datetime.datetime.now().isoformat(), "ok": False, "error": str(e)[:200]})
        st["history"] = st["history"][-200:]
        _save_state(st)
        _append_audit(f"[CRON] {name} 失败: {e}")
        print(f"[CRON] {name} 失败: {e}")
        return {"job": name, "ran": True, "ok": False, "error": str(e)[:200]}


def main():
    cfg = _read_config()
    mode = sys.argv[1] if len(sys.argv) > 1 else "due"
    if mode == "due":
        ran = []
        for name in JOBS:
            r = run_job(name, cfg)
            if r["ran"]:
                ran.append(name)
        if not ran:
            print("[CRON] 无到期任务（宕机时段外或未到间隔）")
        _job_health_report(cfg)  # 每次执行后刷新健康指标
    elif mode == "run":
        name = sys.argv[2] if len(sys.argv) > 2 else ""
        if name not in JOBS:
            print(f"[CRON] 未知任务: {name}，可选: {list(JOBS.keys())}")
            sys.exit(2)
        run_job(name, cfg, force=True)
        _job_health_report(cfg)
    elif mode == "status":
        st = _load_state()
        print(json.dumps({"last_run": st.get("last_run", {}), "failures": st.get("failures", {}),
                          "runs": st.get("runs", {})}, ensure_ascii=False, indent=2))
    else:
        print(__doc__)
        sys.exit(1)


if __name__ == "__main__":
    main()