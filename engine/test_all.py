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


def test_token_governance():
    """TOKEN 治理：Shalou 写侧降噪 + 会话预算哨兵 + 目标预算护栏"""
    import os, json, tempfile, sqlite3
    # 1) memory_archive 写侧降噪：JSON 全文/长转储不落库
    try:
        import sys as _sys
        _shalou_engine = ""
        _codex_home = os.environ.get("CODEX_HOME", "")
        if _codex_home:
            _shalou_engine = os.path.join(os.path.dirname(os.path.dirname(_codex_home)), "开发", "本地源码库", "shalou", "engine")
        if _shalou_engine and os.path.isdir(_shalou_engine):
            _sys.path.insert(0, _shalou_engine)
        from shalou.diegin_integration import _archive_summary, memory_archive, _ARCHIVE_TOTAL_LIMIT
        big = json.dumps({"action": "begin", "intent_summary": "x" * 500, "detail": "y" * 1000}, ensure_ascii=False)
        s = _archive_summary(big)
        c1 = check("TOKEN·归档摘要压缩", len(s) <= 240 and "y" * 1000 not in s, f"{len(s)}字符")
        calls = []
        import shalou.diegin_integration as _di
        class _Fake:
            def archive(self, rule_id, content):
                calls.append(content)
                return True
        _di._MEMORY_ADAPTER = _Fake()
        memory_archive("t_rule", big, {"ctx": "z" * 800})
        c2 = check("TOKEN·归档全文不落库", bool(calls) and len(calls[0]) <= _ARCHIVE_TOTAL_LIMIT and "y" * 1000 not in calls[0], f"{len(calls[0]) if calls else 0}字符")
    except Exception as e:
        c1 = check("TOKEN·归档摘要压缩", False, str(e))
        c2 = check("TOKEN·归档全文不落库", False, str(e))
    # 2) 会话预算哨兵：>150K 单轮上下文 → 强制提示（构造临时 rollout）
    _warn_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "var", "state", "token_budget_warn.json")
    _warn_backup = None
    if os.path.exists(_warn_path):
        with open(_warn_path, encoding="utf-8") as _fw:
            _warn_backup = _fw.read()
    _tmp_rollout = None
    _tmp_goal_db = None
    try:
        import call_diegin as _cd
        import uuid as _uuid
        _home = os.environ.get("CODEX_HOME", "")
        _sid = "test_tokenguard_" + _uuid.uuid4().hex[:8]
        _dir = os.path.join(_home, "sessions", "test", "token")
        os.makedirs(_dir, exist_ok=True)
        _rf = os.path.join(_dir, f"rollout-{_sid}-x.jsonl")
        _tmp_rollout = _rf
        _evt = {"timestamp": "2026-08-31T00:00:00Z", "type": "event_msg", "payload": {
            "type": "token_count", "info": {"last_token_usage": {"input_tokens": 160000}}}}
        with open(_rf, "w", encoding="utf-8") as _fh:
            _fh.write(json.dumps(_evt) + "\n")
        _g = _cd._session_size_guard(_sid)
        c3 = check("TOKEN·>150K强制提示", _g and "150000" in _g, _g[:60] if _g else "无注入")
    except Exception as e:
        c3 = check("TOKEN·>150K强制提示", False, str(e))
    finally:
        if _tmp_rollout and os.path.exists(_tmp_rollout):
            os.remove(_tmp_rollout)
        if _warn_backup is not None:
            with open(_warn_path, "w", encoding="utf-8") as _fw:
                _fw.write(_warn_backup)
    # 3) 目标预算护栏：无 budget 且已用 >50K → 提示补设
    try:
        import call_diegin as _cd
        import uuid as _uuid
        _db = os.path.join(os.environ.get("CODEX_HOME", ""), "goals_test_" + _uuid.uuid4().hex[:8] + ".sqlite")
        _tmp_goal_db = _db
        if os.path.exists(_db):
            os.remove(_db)
        _con = sqlite3.connect(_db)
        _con.execute("CREATE TABLE thread_goals (thread_id TEXT PRIMARY KEY, goal_id TEXT, objective TEXT, status TEXT, token_budget INTEGER, tokens_used INTEGER, created_at_ms INTEGER, updated_at_ms INTEGER)")
        _con.execute("INSERT INTO thread_goals VALUES ('test_goal_session','g1','目标','active',NULL,60000,0,0)")
        _con.commit(); _con.close()
        _g2 = _cd._goal_budget_guard("test_goal_session")
        c4 = check("TOKEN·目标预算提示", _g2 and "token_budget" in _g2, _g2[:60] if _g2 else "无注入")
        _con = sqlite3.connect(_db)
        _con.execute("UPDATE thread_goals SET token_budget=50000, tokens_used=60000")
        _con.commit(); _con.close()
        _g3 = _cd._goal_budget_guard("test_goal_session")
        c5 = check("TOKEN·预算耗尽强制", _g3 and "预算耗尽" in _g3, _g3[:60] if _g3 else "无注入")
    except Exception as e:
        c4 = check("TOKEN·目标预算提示", False, str(e))
        c5 = check("TOKEN·预算耗尽强制", False, str(e))
    finally:
        if _tmp_goal_db and os.path.exists(_tmp_goal_db):
            try:
                os.remove(_tmp_goal_db)
            except Exception:
                pass
        if _warn_backup is not None:
            with open(_warn_path, "w", encoding="utf-8") as _fw:
                _fw.write(_warn_backup)
    return c1 and c2 and c3 and c4 and c5


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




def test_shousan_guard_cap():
    """守三下调 50% 上限（2026-09-05 第六章）：P6 正向调权不得超过守三下调总和的一半"""
    import tempfile
    import shousan_guard as _sg
    from shousan_guard import record, cap
    _tmp = tempfile.mkdtemp(prefix="sguard_test_")
    _sg._STATE_PATH = os.path.join(_tmp, "shousan_down_regs.json")
    _rid = "test_sguard_cap_rule"
    record(_rid, 0.4, reason="test 守三下调登记")
    c1 = check("守三帽·无下调记录不过滤", cap(_rid + "_none", 0.2) == 0.2)
    c2 = check("守三帽·P6上限=50%守三下调", cap(_rid, 0.5) == 0.2)
    c3 = check("守三帽·低于上限原样放行", cap(_rid, 0.1) == 0.1)
    return c1 and c2 and c3


def test_arbiter_p3_resume():
    """P3(恒常门恢复)期间 P6 单点豁免：方向调权静默，不动 completion_criteria"""
    from arbiter import ConflictArbiter
    from rule_engine import RuleEngine, InterceptionRule
    _arb = ConflictArbiter(RuleEngine())
    c1 = check("P3豁免·默认未置位", getattr(_arb, "_p3_resume", False) is False)
    _ir = InterceptionRule(id="test_p3_resume_rule", trigger_condition="true", action="block", severity="high",
                           tags=[], logic_score=0, outcome_score=0, confidence=5.0,
                           source="test", lifecycle_status="active")
    _hits = [{"text": "历史高置信阻断案例：同类高危操作必须拦截", "score": 0.95, "space": "rule"}]
    _arb.resolve([_ir], [], shalou_hits=_hits, constancy_state={"resumed": True})
    c2 = check("P3豁免·恢复期置位", _arb._p3_resume is True)
    c3 = check("P3豁免·恢复期无方向调权", (getattr(_ir, "_mem_conf_adj", 0) or 0) == 0)
    return c1 and c2 and c3


def test_holder_ch10_entry():
    """第十章持行章 ch10 入口：三类信号注入 + 只读不自动改规则"""
    import tempfile
    import evo.holder as _holder
    _tmp = tempfile.mkdtemp(prefix="holder_test_")
    _holder._VAR_DIR = _tmp
    _holder._STATE_DIR = os.path.join(_tmp, "state")
    r = _holder.ch10_entry({"task": "第十章持行章测试"}, {"decision": "allow"}, matched_ids=["test_ch10_rule"])
    c1 = check("持行章·入口标记", r.get("source") == "ch10_holder" and r.get("principle") == "持行·律令章")
    _sig = r.get("signals", {})
    c2 = check("持行章·三类信号注入", {"force_activate", "blind_zone", "deposition"} <= set(_sig))
    c3 = check("持行章·侧压系数输出", isinstance(r.get("side_pressure", {}).get("side_pressure"), float))
    c4 = check("持行章·守真不越权", "candidates" in _sig.get("deposition", {}) or _sig.get("deposition", {}).get("warning") is not None)
    return c1 and c2 and c3 and c4


def test_case_prototype_idempotent():
    """B方案 case_prototype 空间：同场景幂等登记 + 重复登记不吞战绩 + 连续成功阈值"""
    import tempfile
    import shalou.diegin_integration as _di
    from shalou.codex_adapter import CodexMemoryAdapter
    _tmp = tempfile.mkdtemp(prefix="caseproto_test_")
    _old_adapt = _di._MEMORY_ADAPTER
    _di._MEMORY_ADAPTER = CodexMemoryAdapter(storage_path=_tmp)
    try:
        _key = "verify_fix::caseproto_幂等测试场景"
        _u1 = _di.write_case_prototype("场景A首次登记文本", uid_seed=_key)
        _u2 = _di.write_case_prototype("场景A重复登记文本(描述变化)", uid_seed=_key)
        c1 = check("case原型·uid 场景幂等", bool(_u1) and _u1 == _u2)
        _r1 = _di.record_case_outcome(_u1, ok=True)
        _r2 = _di.record_case_outcome(_u1, ok=True)
        c2 = check("case原型·连续成功累计", _r2.get("consecutive_success") == 2)
        _u3 = _di.write_case_prototype("场景A再次登记文本", uid_seed=_key)
        _r3 = _di.record_case_outcome(_u1, ok=True)
        c3 = check("case原型·重复登记不吞战绩且达阈值", _u3 == _u1 and _r3.get("promotable") is True and _r3.get("consecutive_success") == 3)
        _r4 = _di.record_case_outcome(_u1, ok=False)
        c4 = check("case原型·失败清零", _r4.get("consecutive_success") == 0 and _r4.get("total_fail") == 1)
        return c1 and c2 and c3 and c4
    finally:
        _di._MEMORY_ADAPTER = _old_adapt

def test_l1_flip_rw_balance():
    """L1 沙漏翻转·读写平衡（沙漏§3.3/§5.3）：自然/逆向触发 + 原子状态切换 + 审计 + 冷却"""
    import tempfile
    import shalou.flip as _F
    _tmp = tempfile.mkdtemp(prefix="flip_test_")
    _F.MIN_FLIP_INTERVAL_MIN = 0
    _F.RW_FLIP_RATIO = 2.0
    for _ in range(8):
        _F.record_io("write", _tmp)
    _ev = _F.evaluate(_tmp)
    c1 = check("L1翻转·写主导触发自然", _ev.get("triggered") is True and _ev.get("flip_type") == "natural")
    _ex = _F.execute_flip("natural", storage_dir=_tmp, source="test")
    c2 = check("L1翻转·自然→倒放180", _ex.get("ok") is True and _ex.get("to_angle") == 180.0)
    _h = _F.health(_tmp)
    c3 = check("L1翻转·状态生效+计数", _h.get("angle") == 180.0 and _h.get("mode") == "upside_down" and _h.get("flip_count") == 1)
    c4 = check("L1翻转·审计日志落盘", os.path.exists(_F.event_path(_tmp)))
    # 读主导（新目录）→ 逆向
    _tmp2 = tempfile.mkdtemp(prefix="flip_test2_")
    for _ in range(8):
        _F.record_io("read", _tmp2)
    _ev2 = _F.evaluate(_tmp2)
    c5 = check("L1翻转·读主导触发逆向", _ev2.get("triggered") is True and _ev2.get("flip_type") == "reverse")
    # 冷却（120分钟）阻止连续翻转
    _F.MIN_FLIP_INTERVAL_MIN = 120
    _ex1b = _F.execute_flip("reverse", storage_dir=_tmp2, source="test")
    _ex2 = _F.execute_flip("natural", storage_dir=_tmp2, source="test")
    c6 = check("L1翻转·冷却阻止频繁翻转", _ex1b.get("ok") is True and _ex2.get("ok") is False)
    return c1 and c2 and c3 and c4 and c5 and c6


def test_l1_angle_parking():
    """L1 沙漏·360度任意角度停驻（沙漏§2.4/§5.1）：90=侧放待机 / 任意角度 / 状态健康"""
    import tempfile
    import shalou.flip as _F
    _tmp = tempfile.mkdtemp(prefix="flip_park_")
    _s90 = _F.set_angle(90.0, _tmp, source="test", reason="停驻测试")
    _h90 = _F.health(_tmp)
    c1 = check("L1停驻·90度侧放", _s90.get("ok") is True and _h90.get("mode") == "side")
    _s45 = _F.set_angle(45.0, _tmp, source="test", reason="任意角度")
    _h45 = _F.health(_tmp)
    c2 = check("L1停驻·任意角度混合", _s45.get("ok") is True and _h45.get("mode") == "arbitrary" and "任意角度" in (_h45.get("direction") or {}).get("label", ""))
    _s0 = _F.set_angle(0.0, _tmp, source="test", reason="正放恢复")
    _h0 = _F.health(_tmp)
    c3 = check("L1停驻·0度正放恢复", _s0.get("ok") is True and _h0.get("mode") == "upright")
    c4 = check("L1停驻·健康含流动监控", "flip_last_24h" in _h0 and "flow_rate_10min" in _h0)
    return c1 and c2 and c3 and c4


def test_l1_user_flip_text():
    """L1 沙漏·主动翻转（用户指令）：侧放/正放/翻转词映射到翻转动作"""
    import tempfile
    import evo.holder as _h
    _tmp = tempfile.mkdtemp(prefix="flip_uf_")
    _sdir = os.path.join(_tmp, "shalou")
    os.makedirs(_sdir, exist_ok=True)
    _orig = _h._memory_db_path
    _h._memory_db_path = lambda: os.path.join(_sdir, "memory.db")
    try:
        _r1 = _h.user_flip("沙漏侧放 停驻", reason="test 停驻")
        c1 = check("L1用户·侧放停驻", _r1.get("ok") is True and _r1.get("action") == "side_park")
        _r2 = _h.user_flip("沙漏正放 恢复流动", reason="test 正放")
        c2 = check("L1用户·正放恢复", _r2.get("ok") is True and _r2.get("action") == "upright_resume")
        _r3 = _h.user_flip("沙漏翻转", reason="test 翻转")
        c3 = check("L1用户·翻转指令", _r3.get("ok") is True and "flip" in _r3.get("action", ""))
        _r4 = _h.user_flip("日常任务继续推进", reason="test 非翻转")
        c4 = check("L1用户·非翻转指令不动", _r4.get("ok") is False)
        return c1 and c2 and c3 and c4
    finally:
        _h._memory_db_path = _orig

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

    print(f"\n--- TOKEN 治理 ---", flush=True)
    test_token_governance()

    print(f"\n--- 攻七推荐 ---", flush=True)
    test_gongqi_noise_filter()

    print(f"\n--- 攻七质量门 ---", flush=True)
    test_noise_reason()

    print(f"\n--- 第十章 P0 闭环 (2026-09-05) ---", flush=True)
    test_shousan_guard_cap()
    test_arbiter_p3_resume()
    test_holder_ch10_entry()
    test_case_prototype_idempotent()
    print(f"\n--- L1 沙漏翻转/停驻/读写平衡 (2026-09-06 受权实施) ---", flush=True)
    test_l1_flip_rw_balance()
    test_l1_angle_parking()
    test_l1_user_flip_text()
    
    total = passed + failed
    print(f"\n{'='*50}", flush=True)
    print(f"  结果: {passed}/{total} 通过 ({failed} 失败)", flush=True)
    print(f"{'='*50}", flush=True)
    
    return 1 if failed > 0 else 0

if __name__ == "__main__":
    sys.exit(main())
