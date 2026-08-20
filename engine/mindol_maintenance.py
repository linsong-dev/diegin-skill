# -*- coding: utf-8 -*-
"""Mindol 每日维护（[PERF-C 2026-08-20] P3）
分档保留期 dormant 化 + 记忆衰减（decay_and_dormancy）+ 主动统计。

保留期分档（按「该用的用，该省的省」）：
  - 工具中间日志 hook_pre_tool/hook_post_tool/dgen_archive/hook_stop → 1 天
  - 半对话 post_tool/chat_post_tool → 3 天
  - 对话上下文 hook_raw_chat/raw_chat → 7 天
  - rule/trade/pattern/user/abstract/state 永不清理

幂等：已 dormant 的记录不再处理；软删除可恢复（status=dormant）。
用法: python mindol_maintenance.py [--apply]
默认 --dry-run 只输出统计；--apply 才实际 dormant 化。
"""
import sys, os, sqlite3, time, datetime, json

def log(msg):
    ts = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]
    print(f"{ts} {msg}")
    try:
        with open(os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "var", "logs", "diegin_audit.log"), "a", encoding="utf-8") as f:
            f.write(f"{ts} [MINDOL-MAINT] {msg}\n")
    except Exception:
        pass

RETENTION = {
    "hook_pre_tool": 1, "hook_post_tool": 1, "dgen_archive": 1, "hook_stop": 1,
    "post_tool": 3, "chat_post_tool": 3,
    "hook_raw_chat": 7, "raw_chat": 7,
}
# 永不清理
PROTECTED = {"rule", "trade", "pattern", "abstract", "state", "user", "chat_user", "diegin_rule", "diegin_pattern", "diegin_meta", "diegin_strike", "hook_trade"}
# 其它未知 source 一律视为工具日志（默认 1 天），防漏网
DEFAULT_DAYS = 1

def main():
    apply = "--apply" in sys.argv
    db_path = os.path.join(os.environ.get("CODEX_HOME", ""), "mindol", "memory.db")
    if not os.path.exists(db_path):
        # 兜底：便携版相对路径
        db_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "..", "mindol", "memory.db")
    if not os.path.exists(db_path):
        log(f"ERROR memory.db not found: {db_path}")
        return 1
    db = sqlite3.connect(db_path)
    cur = db.cursor()
    now = time.time()
    # 统计各 source 分布
    rows = cur.execute("SELECT source, status, COUNT(*) FROM memory_units GROUP BY source, status").fetchall()
    src_total = {}
    src_active = {}
    for s, st, n in rows:
        src_total[s] = src_total.get(s, 0) + n
        if st == "active":
            src_active[s] = src_active.get(s, 0) + n
    plan = []  # (source, cutoff_days, count)
    for s, total in src_total.items():
        if s in PROTECTED:
            continue
        days = RETENTION.get(s, DEFAULT_DAYS)
        cut = now - days * 86400
        n = cur.execute("SELECT COUNT(*) FROM memory_units WHERE source=? AND status='active' AND timestamp<?", (s, cut)).fetchone()[0]
        if n > 0:
            plan.append((s, days, n))
    plan.sort(key=lambda x: -x[2])
    active_total = sum(src_active.values())
    log(f"active_total={active_total} apply={apply}")
    for s, days, n in plan:
        log(f"  will_dormant source={s} days={days} count={n}")
    if not apply:
        log("DRY-RUN: 加 --apply 实际执行")
        db.close()
        return 0
    # 执行
    for s, days, n in plan:
        cut = now - days * 86400
        cur.execute("UPDATE memory_units SET status='dormant' WHERE source=? AND status='active' AND timestamp<?", (s, cut))
    # 记忆衰减（decay_and_dormancy 语义等价：经验空间强度衰减 + 低阈值休眠）
    try:
        sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
        from mindol.diegin_integration import memory_decay
        decay = memory_decay()
        log(f"decay={decay}")
    except Exception as e:
        log(f"decay_skip: {e}")
    db.commit()
    after = cur.execute("SELECT COUNT(*) FROM memory_units WHERE status='active'").fetchone()[0]
    log(f"done active_before={active_total} active_after={after} dormant_plan={sum(x[2] for x in plan)}")
    db.close()
    return 0

if __name__ == "__main__":
    sys.exit(main())