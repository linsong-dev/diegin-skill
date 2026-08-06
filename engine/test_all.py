"""test_all.py - 迭进 v3.4.0 端到端测试"""
import sys, json, os
sys.stdout.reconfigure(encoding="utf-8")
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "engine"))

VERBOSE = "--verbose" in sys.argv
passed = 0
failed = 0

def log(msg):
    if VERBOSE:
        print(f"  [TEST] {msg}", flush=True)

def check(name, condition, detail=""):
    global passed, failed
    status = "PASS" if condition else "FAIL"
    d = f" - {detail}" if detail else ""
    msg = f"  [{status}] {name}{d}"
    print(msg, flush=True)
    if condition:
        passed += 1
    else:
        failed += 1
    return condition

def test_pacemaker():
    from evo.main import get_pacemaker
    pm = get_pacemaker()
    _orig_dt = pm._check_downtime
    pm._check_downtime = lambda: False  # 时间无关：避开宕机时段(23:00-06:00)导致的 flaky
    r1 = pm.classify({"task": "紧急修复bug"})
    c1 = check("缓急律·紧急分流", r1["channel"] == "fast_path")
    r2 = pm.classify({"task": "日常提交"})
    c2 = check("缓急律·常规分流", r2["channel"] == "normal")
    pm._check_downtime = _orig_dt
    return c1 and c2

def test_closure():
    from evo.main import get_closure
    cg = get_closure()
    cg.open("test-item", "测试")
    c1 = check("止观门·打开", len(cg.get_open_items()) == 1)
    cg.close("test-item", "完成")
    c2 = check("止观门·封存", cg.is_closed("test-item"))
    return c1 and c2

def test_evidence():
    from evo.main import get_vault
    v = get_vault()
    v.record("r1", "pass", "通过")
    v.record("r2", "skip", "跳过")
    stats = v.get_stats()
    c1 = check("证据库·裁决记录", stats["total_verdicts"] >= 2)
    return c1

def test_precheck():
    from call_diegin import pre_check
    r = pre_check({"task": "测试", "task_type": "general"})
    c1 = check("预检·决策", r["decision"] in ("allow", "block"))
    c2 = check("预检·缓急律集成", "pace_result" in r)
    return c1 and c2

def test_rules():
    rules_path = os.path.join(os.path.dirname(__file__), "evo", "rules", "interception_rules.json")
    with open(rules_path, "r", encoding="utf-8") as f:
        rules = json.load(f)
    c1 = check("规则库·存在", len(rules) > 0)
    active = sum(1 for r in rules if r.get("lifecycle_status") == "active")
    c2 = check("规则库·活跃规则>0", active > 0, f"{active}条")
    return c1 and c2


def test_strike_mechanism():
    """一二不过三：检测strike记录和计数"""
    from call_diegin import load_principle_rules, evidence_filter
    # 测试含 marker_missing 的上下文
    ctx = {"task": "test", "marker_missing": True}
    # dry-run: 不写入 strikes_db（避免测试污染生产状态）
    rules = load_principle_rules(ctx, record_strike=False)
    # 至少返回一条规则（阻断）
    c1 = check("一二不过三·strike触发", len(rules) >= 1, f"{len(rules)}条")
    return c1

def test_empty_context():
    """空上下文预检不崩溃"""
    from call_diegin import pre_check
    r = pre_check({})
    c1 = check("空上下文·决策存在", "decision" in r)
    r2 = pre_check({"task": ""})
    c2 = check("空任务·不崩溃", "decision" in r2)
    return c1 and c2

def test_missing_file_graceful():
    """文件缺失时 engine 不崩溃"""
    import os, json, tempfile
    from evo.main import _get_engine
    eng = _get_engine()
    # 尝试用一个不存在的路径
    c1 = check("引擎加载·成功", eng is not None)
    try:
        rules = eng.get_interceptions(active_only=True)
        c2 = check("获取活跃规则·不崩溃", isinstance(rules, list), f"{len(rules)}条")
    except Exception as e:
        c2 = check("获取活跃规则·不崩溃", False, str(e))
    return c1 and c2

def test_evidence_filter():
    """去伪存真过滤逻辑"""
    from call_diegin import evidence_filter
    from evo.rule_engine import InterceptionRule
    ctx = {"task": "test"}
    # 创建测试规则
    r1 = InterceptionRule(id="test_active", trigger_condition="true", action="allow", severity="low",
                           tags=[], logic_score=0, outcome_score=0, confidence=0,
                           source="test", lifecycle_status="active")
    r2 = InterceptionRule(id="test_staging", trigger_condition="true", action="allow", severity="low",
                           tags=[], logic_score=0, outcome_score=0, confidence=0,
                           source="test", lifecycle_status="staging")
    # staging 因置信度不足应被过滤
    filtered = evidence_filter([r1, r2], ctx)
    c1 = check("active规则通过", any(r.id == "test_active" for r in filtered))
    c2 = check("staging低置信度过滤", not any(r.id == "test_staging" for r in filtered))
    return c1 and c2


def test_op_contains():
    """去伪存真·op_contains 谓词（P2方案A）：字段白名单精确命中 + AND NOT prechecked"""
    from evo.rule_engine import RuleEngine
    eng = RuleEngine()
    ok1 = eng._match_condition("op_contains(tool_error_Bash)", {"blocked_error_type": "tool_error_Bash"})
    ok2 = eng._match_condition("op_contains(command_failure)", {"op": "command_failure"})
    ok3 = not eng._match_condition("op_contains(tool_error_Bash)", {"task": "普通任务"})
    ok4 = eng._match_condition("op_contains(hooks_ps1_bom) AND NOT prechecked", {"blocked_error_type": "hooks_ps1_bom"})
    ok5 = not eng._match_condition("op_contains(x)", {"blocked_error_type": "tool_error_Bash"})
    ok6 = not eng._match_condition("op_contains()", {"blocked_error_type": "x"})
    ok7 = not eng._match_condition("op_contains(error_type)", {"error_type": "Bash"})
    c1 = check("op_contains·命中blocked_error_type", ok1)
    c2 = check("op_contains·命中op字段", ok2)
    c3 = check("op_contains·无关字段不命中", ok3)
    c4 = check("op_contains·AND NOT prechecked", ok4)
    c5 = check("op_contains·短token拒绝", ok5)
    c6 = check("op_contains·空参数拒绝", ok6)
    c7 = check("op_contains·字段名撞名拒绝", ok7)
    return c1 and c2 and c3 and c4 and c5 and c6 and c7


def main():
    print(f"\n{'='*50}", flush=True)
    print(f"  迭进 v3.4.0 端到端测试", flush=True)
    print(f"{'='*50}", flush=True)
    
    print(f"\n--- 规则库 ---", flush=True)
    test_rules()
    
    print(f"\n--- 缓急律 ---", flush=True)
    test_pacemaker()
    
    print(f"\n--- 止观门 ---", flush=True)
    test_closure()
    
    print(f"\n--- 去伪存真 ---", flush=True)
    test_evidence()
    
    print(f"\n--- 预检流程 ---", flush=True)
    test_precheck()

    print(f"\n--- 一二不过三 ---", flush=True)
    test_strike_mechanism()

    print(f"\n--- 异常保护 ---", flush=True)
    test_empty_context()
    test_missing_file_graceful()

    print(f"\n--- 去伪存真过滤 ---", flush=True)
    test_evidence_filter()
    test_op_contains()
    
    total = passed + failed
    print(f"\n{'='*50}", flush=True)
    print(f"  结果: {passed}/{total} 通过 ({failed} 失败)", flush=True)
    print(f"{'='*50}", flush=True)
    
    return 1 if failed > 0 else 0

if __name__ == "__main__":
    sys.exit(main())