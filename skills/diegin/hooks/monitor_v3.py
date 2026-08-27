"""
monitor_v3.py - 轮询监控框架参考实现
======================================
用途：外部系统轮询监控的示例框架。
注意：这是一个通用参考实现，不绑定任何具体业务。
      - get_resource_state() 需替换为你的实际数据源
      - 状态机逻辑可作为模板复用
"""
#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
任务监控轮询 v3 — 2026-07-05更新
- 通过API查询外部状态
- 检查状态阈值/异常/超时
- 忙季加强监控
- 更新context.json
"""

import json, os, sys, requests
from datetime import datetime

WORKSPACE = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "workspace")
TRADE_STATE = os.path.join(WORKSPACE, "state.json")
CTX_FILE = os.path.join(WORKSPACE, "context.json")
LOG_FILE = os.path.join(WORKSPACE, "monitor_log.txt")

def get_resource_state():
    if not os.path.exists(TRADE_STATE):
        return [], 0
    with open(TRADE_STATE, "r", encoding="utf-8") as f:
        data = json.load(f)
    return data.get("resources", []), data.get("capacity", 0)

def get_gtimg_quote(code):
    prefix = "sh" if code.startswith("6") else "sz"
    url = f"http://qt.gtimg.cn/q={prefix}{code}"
    try:
        r = requests.get(url, timeout=10)
        parts = r.text.split("~")
        if len(parts) > 40:
            return {
                "ok": True, "name": parts[1],
                "now": float(parts[3]) if parts[3] else 0,
                "high": float(parts[33]) if parts[33] else 0,
                "low": float(parts[34]) if parts[34] else 0,
                "open": float(parts[5]) if parts[5] else 0,
                "pre_close": float(parts[4]) if parts[4] else 0,
                "volume": float(parts[6]) if parts[6] else 0,
                "amount": float(parts[37]) if parts[37] else 0,
                "chg_pct": float(parts[32]) if parts[32] else 0
            }
        return {"ok": False, "error": "parse_failed"}
    except Exception as e:
        return {"ok": False, "error": str(e)}

def run_check():
    resources, capacity = get_resource_state()
    if not resources:
        print("NO_POSITIONS")
        return
    
    alerts = []
    pos_snapshots = []
    market_summary = []
    
    for res in resources:
        code = res["code"]
        name = res["name"]
        avg = res["avgPrice"]
        sl = res.get("stopLoss", avg * 0.93)
        shares = res.get("shares", 0)
        
        data = get_gtimg_quote(code)
        if not data.get("ok"):
            market_summary.append(f"{name}({code}) 数据失败")
            continue
        
        current = data["now"]
        high = data["high"]
        
        if current <= 0:
            continue
        
        pnl_pct = (current - avg) / avg * 100
        pnl_amt = (current - avg) * shares
        
        # 阈值检查
        sl_flag = current <= sl
        
        # 盘中回撤阈值触发（当日最高×0.97）
        retrace_flag = False
        if high > 0 and current < high * 0.97 and pnl_pct > 3:
            retrace_flag = True
        
        # 收盘追踪阈值触发
        pre_close = data["pre_close"]
        tp_close_flag = False
        if pre_close > 0 and current < pre_close * 0.96 and pnl_pct > 5:
            tp_close_flag = True
        
        # 中报季警示（7月中报季期间）
        earn_season = True  # 7月6日起开启
        earn_warn = False
        if earn_season and pnl_pct > 15:
            earn_warn = True  # 数值过高，注意锁定
        
        status = "持有"
        if sl_flag:
            alerts.append(f"STOP_LOSS|{code}|{name}|{current}|{sl}")
            status = "STOP_LOSS"
        elif retrace_flag:
            alerts.append(f"RETRACE|{code}|{name}|{current}|{high}")
            status = "RETRACE"
        elif tp_close_flag:
            alerts.append(f"TP_CLOSE|{code}|{name}|{current}|{pre_close}")
            status = "TP_CLOSE"
        
        pos_snapshots.append({
            "code": code, "name": name, "shares": shares,
            "avgPrice": avg, "currentPrice": current,
            "high": high, "pnlPct": round(pnl_pct, 2),
            "pnlAmt": round(pnl_amt, 2),
            "stopLoss": sl, "status": status,
            "earnSeasonWarn": earn_warn
        })
        
        c = data['chg_pct']
        if status == "STOP_LOSS":
            market_summary.append(f"{name} {current:.2f}({c:+.2f}%) ⛔阈值触发!")
        elif status == "RETRACE":
            market_summary.append(f"{name} {current:.2f}({c:+.2f}%) ⚠️回撤")
        elif status == "TP_CLOSE":
            market_summary.append(f"{name} {current:.2f}({c:+.2f}%) ⚠️阈值触发线跌破")
        elif pnl_pct > 0:
            market_summary.append(f"{name} {current:.2f}({c:+.2f}%) +{pnl_pct:.1f}%")
        else:
            market_summary.append(f"{name} {current:.2f}({c:+.2f}%) {pnl_pct:.1f}%")
    
    now = datetime.now().strftime("%H:%M")
    
    ctx = {
        "updatedAt": datetime.now().isoformat(),
        "resources": pos_snapshots,
        "alerts": alerts,
        "summary": " | ".join(market_summary)
    }
    with open(CTX_FILE, "w", encoding="utf-8") as f:
        json.dump(ctx, f, ensure_ascii=False, indent=2)
    
    sys.stdout.reconfigure(encoding='utf-8')
    print(json.dumps(ctx, ensure_ascii=False))
    
    with open(LOG_FILE, "a", encoding="utf-8") as f:
        f.write(f"{datetime.now().isoformat()} | {ctx['summary']}\n")
        for a in alerts:
            f.write(f"{datetime.now().isoformat()} | {a}\n")

if __name__ == "__main__":
    run_check()
