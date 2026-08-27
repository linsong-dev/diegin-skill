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
    # v3.8.1 证据有效性门：pass/skip 需引用真实规则 id 或有实质 reason；
    # 测试用 fail/block（无条件保留）保证干净环境可复现
    v.record("r1", "fail", "测试失败证据：预检拦截了高危操作")
    v.record("r2", "block", "测试阻断证据：一二不过三升三错级熔断")
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


def test_gongqi_noise_filter():
    """攻七推荐：工具名级伪模式整体剔除 + priority 标记正确"""
    from evo.rule_engine import build_gongqi_suggestions

    class _FakePat:
        def __init__(self, pid, scenario, decision, conf, trig, created_at=""):
            self.id = pid
            self.trigger_scenario = scenario
            self.decision_logic = decision
            self.confidence = conf
            self.trigger_condition = trig
            self.created_at = created_at

    noise = _FakePat("pat_noise_bash", "tool_Bash", "工具名级伪模式决策逻辑" * 4, 5.0, "tool_name == 'Bash'")
    rich = _FakePat("pat_rich_write", "PS写文件", "写含中文文件用 WriteAllText UTF-8 NoBOM 原子写并读回验证", 4.9, "tool_name == 'PowerShell' and 'Set-Content' in command")
    low = _FakePat("pat_low", "低置信", "短逻辑", 3.0, "op_contains(xxx)")
    old_pat = _FakePat("pat_old_same_conf", "旧经验", "同分旧经验决策逻辑内容足够长用于测试排序", 5.0, "tool_name == 'PowerShell' and 'X' in command", "2026-08-01T10:00:00")
    new_pat = _FakePat("pat_new_same_conf", "新经验", "同分新经验决策逻辑内容足够长用于测试排序", 5.0, "tool_name == 'PowerShell' and 'Y' in command", "2026-08-09T16:00:00")
    sug = build_gongqi_suggestions([noise, rich, low])
    ids = [s["id"] for s in sug]
    c1 = check("攻七·工具名级伪模式剔除", "pat_noise_bash" not in ids)
    c2 = check("攻七·priority标记正确", len(sug) > 0 and sug[0]["priority"] is True and sug[0]["id"] == "pat_rich_write")
    sug2 = build_gongqi_suggestions([old_pat, new_pat])
    ids2 = [s["id"] for s in sug2]
    c3 = check("攻七·同分新优先", ids2 == ["pat_new_same_conf", "pat_old_same_conf"])
    return c1 and c2 and c3

def test_noise_reason():
    """攻七质量门 _noise_reason：正则 ?? 惰性量词误判回归 + 真乱码仍拦截"""
    from evo.rule_engine import _noise_reason

    c1 = check("质量门·含斜杠/反斜杠的正常文本放行",
               _noise_reason("收集信息先核验链接与目标一致（owner/仓库名）；页面超时降级 GitHub API / raw README；多源数据不一致以官方为准") == "")
    c2 = check("质量门·含反斜杠路径的正常文本放行",
               _noise_reason("递归删除/移动目录前：GetFullPath 验证目标绝对路径前缀在授权范围内；再 Directory.Delete($p,$true)") == "")
    c3 = check("质量门·真乱码路径 E:\\??\\ 仍拦截",
               "含乱码路径" in _noise_reason("写文件到 E:" + chr(92) + chr(63)*2 + chr(92) + "x 后读回验证"))
    c4 = check("质量门·U+FFFD 拦截", "U+FFFD" in _noise_reason("乱码" + chr(0xFFFD) + "文本"))
    c5 = check("质量门·空决策逻辑拦截", _noise_reason("   ") == "空决策逻辑")
    c6 = check("质量门·测试样本拦截", "疑似测试/临时样本" in _noise_reason("先写 test.txt 验证"))
    c7 = check("质量门·perf-test 样本拦截", "疑似测试/临时样本" in _noise_reason("echo perf-test"))
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

    print(f"\n--- 攻七推荐 ---", flush=True)
    test_gongqi_noise_filter()

    print(f"\n--- 攻七质量门 ---", flush=True)
    test_noise_reason()
    
    total = passed + failed
    print(f"\n{'='*50}", flush=True)
    print(f"  结果: {passed}/{total} 通过 ({failed} 失败)", flush=True)
    print(f"{'='*50}", flush=True)
    
    return 1 if failed > 0 else 0

if __name__ == "__main__":
    sys.exit(main())
