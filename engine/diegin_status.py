#!/usr/bin/env python3
"""迭进工作台 - 一键查看五元框架运行状态"""
import sys, os, json
sys.stdout.reconfigure(encoding="utf-8")
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "evo"))

def check_rules():
    rules_file = os.path.join(os.path.dirname(__file__), "evo", "rules", "interception_rules.json")
    if os.path.exists(rules_file):
        with open(rules_file, "r", encoding="utf-8") as f:
            rules = json.load(f)
        total = len(rules)
        active = sum(1 for r in rules if r.get("lifecycle_status") == "active")
        staging = sum(1 for r in rules if r.get("lifecycle_status") == "staging")
        deprecating = sum(1 for r in rules if r.get("lifecycle_status") == "deprecating")
        self_errors = [r for r in rules if r.get("id","").startswith("self_error_")]
        return total, active, staging, deprecating, self_errors
    return 0, 0, 0, 0, []

def check_patterns():
    pf = os.path.join(os.path.dirname(__file__), "evo", "rules", "success_patterns.json")
    if os.path.exists(pf):
        with open(pf, "r", encoding="utf-8") as f:
            patterns = json.load(f)
        return len(patterns)
    return 0

def check_strikes():
    # 查找 strikes_db.json
    for p in [
        os.path.join(os.path.dirname(__file__), "..", "var", "state", "strikes_db.json"),
    ]:
        if os.path.exists(p):
            with open(p, "r", encoding="utf-8") as f:
                return json.load(f)
    return {}

def check_audit():
    log = os.path.join(os.path.dirname(__file__), "..", "var", "logs", "diegin_audit.log")
    if os.path.exists(log):
        with open(log, "r", encoding="utf-8") as f:
            lines = f.readlines()
        return len(lines), lines[0] if lines else ""
    return 0, ""

def check_last_verify():
    lv = os.path.join(os.path.dirname(__file__), "..", "var", "state", "last_check_result.json")
    if os.path.exists(lv):
        with open(lv, "r", encoding="utf-8") as f:
            return json.load(f)
    return {}

def main():
    total, active, staging, deprecating, self_errors = check_rules()
    patterns = check_patterns()
    strikes = check_strikes()
    log_lines, last_log = check_audit()
    last_verify = check_last_verify()
    
    print("=" * 55)
    print("  [DG] 迭进工作台 · 五元框架运行状态")
    print("=" * 55)
    
    # 1. 守三
    s1 = "[OK]" if active > 0 else "[!!]"
    print(f"\n  {s1} 守三（拦截规则）")
    print(f"     活跃: {active} | staging: {staging} | 降权: {deprecating} | 总计: {total}")
    
    # 2. 攻七
    s2 = "[OK]" if patterns > 0 else "[!!]"
    print(f"\n  {s2} 攻七（成功模式）")
    print(f"     成功模式: {patterns}")
    
    # 3. 一二不过三
    strike_count = len(strikes)
    s3 = "[OK]" if strike_count > 0 else "[!!]"
    print(f"\n  {s3} 一二不过三（错误追踪）")
    if strikes:
        for k, v in strikes.items():
            marker = "!" if v["count"] >= 3 else ">"
            print(f"     {marker} {k}: {v['count']}次 (最后: {v.get('last_detail','')[:40]})")
    else:
        print(f"     无记录")
    
    # 4. 举一反三
    cross_rules = [r for r in (self_errors or []) if "xdomain" in r.get("id","")]
    s4 = "[OK]" if staging > 0 or cross_rules else "[i]"
    print(f"\n  {s4} 举一反三（跨域泛化）")
    print(f"     staging 规则: {staging}")
    
    # 6. 缓急律
    s6 = "[OK]" if True else "[i]"
    print(f"\n  {s6} 缓急律（节奏门）")
    try:
        from evo.pacemaker import get_pacemaker
        pm = get_pacemaker()
        ps = pm.get_status()
        dt = ps["downtime"]
        print(f"     宕机时段: {dt['start']}-{dt['end']} (当前{'在' if dt['active_now'] else '不在'}宕机时段)")
        print(f"     已分类: {ps['total_classifications']} 次")
    except Exception:
        print(f"     未加载")

    # 7. 止观门
    s7 = "[OK]" if True else "[i]"
    print(f"\n  {s7} 止观门（完形律）")
    try:
        from evo.closure import get_closure
        cg = get_closure()
        cs = cg.get_status()
        print(f"     已封存: {cs['closed_items']} 项")
        print(f"     进行中: {cs['open_items']} 项")
    except Exception:
        print(f"     未加载")

    # 5. 去伪存真
    has_arbiter_log = "ARBITER" in last_log if last_log else False
    s5 = "[OK]" if has_arbiter_log else "[i]"
    print(f"\n  {s5} 去伪存真（仲裁+验证）")
    if last_verify:
        print(f"     上次验证: {last_verify.get('consistency','?')} (决策={last_verify.get('current_decision','?')})")
    print(f"     审计日志: {log_lines} 行")
    if last_log:
        print(f"     最新: {last_log[:80].strip()}")
    
    try:
        from evo.main import get_vault
        v = get_vault()
        vs = v.get_stats()
        print(f"     证据裁决: {vs['total_verdicts']} 条 (通过:{vs['by_verdict'].get('pass',0)} 跳过:{vs['by_verdict'].get('skip',0)})")
    except Exception:
        pass

    # 引擎健康
    print(f"\n" + "-" * 55)
    try:
        from evo.main import health_check
        health = health_check()
        print(f"  引擎: {health.get('active_rules', '?')}活跃/{health.get('total_rules', '?')}总规则")
        print(f"  熵: {health.get('cognitive_entropy', '?')} ({health.get('entropy_status', '?')})")
    except Exception:
        print(f"  引擎: 无法连接")
    
    print("=" * 55)

if __name__ == "__main__":
    main()

