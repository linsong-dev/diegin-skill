#!/usr/bin/env python3
"""
迭进自动化核心引擎 - self_evolve.py
每次关键决策后调用，自动写入观察→生成提议→验证门控
"""

import json, os, sys
from datetime import datetime

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
HEALTH_FILE = os.path.join(BASE, "workspace", "rule_health.json")
TRAIL_DIR = os.path.join(BASE, "workspace")
FAILURES_FILE = os.path.join(BASE, "workspace", "failures.json")

def seed():
    """首次初始化健康度基线"""
    health = {
        "schemaVersion": "1.0",
        "lastUpdated": datetime.now().strftime("%Y-%m-%d %H:%M"),
        "metrics": {
            "stopLossHitRate": {"value": 0, "count": 0, "desc": "错误触发次数/总操作天数"},
            "takeProfitExecRate": {"value": 0, "count": 0, "desc": "成功模式匹配/总触发信号"},
            "ruleConflictRate": {"value": 0, "count": 0, "desc": "规则互斥引起执行延迟/总操作"},
            "contextLossRate": {"value": 0, "count": 0, "desc": "上下文裁剪导致信息丢失/总请求"},
            "cronFailureRate": {"value": 100, "count": 7, "desc": "cron定时任务失败率(当前所有7个cron均不可用)"}
        },
        "observations": [],
        "proposals": [],
        "history": []
    }
    with open(HEALTH_FILE, "w", encoding="utf-8") as f:
        json.dump(health, f, ensure_ascii=False, indent=2)
    print(f"[DGEN-EVOLVE] 健康度基线已初始化: {HEALTH_FILE}")

def add_observation(obs_type, content, severity="info"):
    """添加一条自动观察"""
    if not os.path.exists(HEALTH_FILE):
        seed()
    with open(HEALTH_FILE, "r", encoding="utf-8") as f:
        health = json.load(f)
    health["observations"].append({
        "ts": datetime.now().isoformat(),
        "type": obs_type,
        "severity": severity,
        "content": content
    })
    # 自动触发提议生成
    proposal = auto_propose(obs_type, content)
    if proposal:
        health["proposals"].append(proposal)
    health["lastUpdated"] = datetime.now().strftime("%Y-%m-%d %H:%M")
    with open(HEALTH_FILE, "w", encoding="utf-8") as f:
        json.dump(health, f, ensure_ascii=False, indent=2)
    print(f"[DGEN-EVOLVE] 观察已记录: {obs_type} | {content[:60]}...")
    return proposal

def auto_propose(obs_type, content):
    """根据观察自动生成规则修改提议"""
    proposals = {
        "cron_timeout": {
            "rule": "cron_failover",
            "action": "add",
            "target": "dgen_rules.md §规则",
            "suggestion": "cron AI推送不可用时，自动切换到降级报告模式+手动问询",
            "priority": "high"
        },
        "error_hit": {
            "rule": "error_adjust",
            "action": "review",
            "target": "dgen_rules.md §规则",
            "suggestion": "错误频发，检查当前流程参数是否过紧或工作质量下降",
            "priority": "medium"
        },
        "context_loss": {
            "rule": "context_persist",
            "action": "add",
            "target": "dgen_rules.md §附录",
            "suggestion": "上下文裁剪后自动从memory/trail_*.md恢复关键状态",
            "priority": "high"
        },
        "rule_conflict": {
            "rule": "rule_prioritize",
            "action": "add",
            "target": "dgen_rules.md §规则",
            "suggestion": "检测到规则互斥时，启用优先级排序自动裁决",
            "priority": "high"
        }
    }
    for key, prop in proposals.items():
        if key in obs_type:
            prop["ts"] = datetime.now().isoformat()
            prop["status"] = "pending_review"
            return prop
    return None

def record_decision(decision_type, summary):
    """记录关键决策到trail文件"""
    today = datetime.now().strftime("%Y-%m-%d")
    trail_file = os.path.join(TRAIL_DIR, f"trail_{today}.md")
    entry = f"""
## [{datetime.now().strftime('%H:%M')}] {decision_type}
- {summary}
"""
    with open(trail_file, "a", encoding="utf-8") as f:
        f.write(entry)
    print(f"[DGEN-EVOLVE] 决策已记录: {decision_type}")

def maintenance_report(stats: dict):
    """B2 最小接入：run_maintenance 将真实维护统计写入健康度基线（防孤儿脚本空转）"""
    if not os.path.exists(HEALTH_FILE):
        seed()
    try:
        with open(HEALTH_FILE, "r", encoding="utf-8") as f:
            health = json.load(f)
    except Exception:
        return False
    if "metrics" not in health:
        health["metrics"] = {}
    health["metrics"]["ruleCount"] = {"value": stats.get("rules", 0), "count": 1, "desc": "拦截规则总数"}
    health["metrics"]["stagingCount"] = {"value": stats.get("staging", 0), "count": 1, "desc": "staging 待验证规则数"}
    health["metrics"]["deprecationCount"] = {"value": stats.get("deprecated", 0), "count": 1, "desc": "本次弃用数"}
    health["metrics"]["strikeTypeCount"] = {"value": stats.get("strikes", 0), "count": 1, "desc": "一二不过三 strike 类型数"}
    health.setdefault("observations", []).append({
        "ts": datetime.now().isoformat(),
        "type": "maintenance_done",
        "severity": "info",
        "content": "维护完成: rules=%d staging=%d deprecated=%d strikes=%d" % (
            stats.get("rules", 0), stats.get("staging", 0),
            stats.get("deprecated", 0), stats.get("strikes", 0))
    })
    # 观察/提议防膨胀：只保留最近 100 条
    for key in ("observations", "proposals"):
        if len(health.get(key, [])) > 100:
            health[key] = health[key][-100:]
    health["lastUpdated"] = datetime.now().strftime("%Y-%m-%d %H:%M")
    with open(HEALTH_FILE, "w", encoding="utf-8") as f:
        json.dump(health, f, ensure_ascii=False, indent=2)
    return True

if __name__ == "__main__":
    if not os.path.exists(HEALTH_FILE):
        seed()
    else:
        print(f'[DGEN-EVOLVE] 健康度基线已存在: {HEALTH_FILE}，如需重建请先删除该文件')
