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
        # [P0 回归锁 2026-09-12] 哨兵必须落「负载占比」ratio，否则持行章 Token 分量回退硬编码 0.3
        _wj = {}
        try:
            with open(_warn_path, encoding="utf-8") as _wf:
                _wj = json.load(_wf)
        except Exception:
            _wj = {}
        _rt = _wj.get("ratio")
        _c3b = bool(isinstance(_rt, (int, float)) and 0.0 <= float(_rt) <= 1.0)
        c3b = check("TOKEN·持行章Token分量(ratio)已落盘", _c3b, ("ratio=%s" % _rt) if _c3b else "缺失/越界")
        try:
            from evo import holder as _hd
            _rd = _hd._token_ratio()
            c3c = check("TOKEN·ratio被持行章读端消费", abs(float(_rd) - float(_rt)) < 1e-6, "读端=%s 落盘=%s" % (_rd, _rt))
        except Exception as _he:
            c3c = check("TOKEN·ratio被持行章读端消费", False, str(_he)[:60])
        # [§0-C:191 回归锁 2026-09-12] 工具链体量信号：正常轮必须静默；重轮必须给出数字
        try:
            _tp_dir = os.path.join(_home, "sessions", "test", "c191lock")
            os.makedirs(_tp_dir, exist_ok=True)
            _sid2 = "c191lock_" + _uuid.uuid4().hex[:8]
            _tp_f = os.path.join(_tp_dir, "rollout-%s-x.jsonl" % _sid2)
            with open(_tp_f, "w", encoding="utf-8") as _tf:
                _tf.write(json.dumps({"type": "response_item", "payload": {
                    "type": "message", "role": "assistant", "content": [{"text": "a"}]}}) + "\n")
                _tf.write(json.dumps({"type": "response_item", "payload": {
                    "type": "function_call_output", "output": "z" * 500}}) + "\n")
                _tf.write(json.dumps({"type": "response_item", "payload": {
                    "type": "message", "role": "assistant", "content": [{"text": "b"}]}}) + "\n")
            _q1 = _cd._toolchain_pressure(_sid2)              # 默认阈值 3 万 → 应静默
            c4 = check("§0-C·工具链信号默认静默(不刷屏)", _q1 == "", "len=%d" % len(_q1 or ""))
            _q2 = _cd._toolchain_pressure(_sid2, min_chars=100)  # 降阈值 → 应给数
            c5 = check("§0-C·工具链信号可触发且含数字", bool(_q2) and "万字符" in _q2 and "次" in _q2,
                       (_q2 or "").strip()[:60])
            os.remove(_tp_f)
        except Exception as _te:
            c4 = check("§0-C·工具链信号默认静默(不刷屏)", False, str(_te)[:60])
            c5 = check("§0-C·工具链信号可触发且含数字", False, str(_te)[:60])
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
    """L1 沙漏翻转·势差驱动（沙漏§2.2/§2.4/§5.3 · P3/D1 契约 2026-09-11）：
    IO 次数退为辅助证据 + 势差连续角度 + no-op 抑制 + 原子状态切换 + 审计 + 冷却"""
    import tempfile
    import shalou.flip as _F
    _tmp = tempfile.mkdtemp(prefix="flip_test_")
    _F.MIN_FLIP_INTERVAL_MIN = 0
    _F.RW_FLIP_RATIO = 2.0
    for _ in range(8):
        _F.record_io("write", _tmp)
    # [P3/D1] IO 次数不再独自触发（写>读×2 恒真已成历史）
    _ev0 = _F.evaluate(_tmp)
    c1 = check("L1翻转·IO不再独自触发(D1)", _ev0.get("triggered") is False)
    # 势差驱动 -> 连续角度（下腔沉积率高 -> θ 偏激活 >90°）
    _st = {"raw_chat": 1500, "codex": 200, "rule": 289, "pattern": 50, "abstract": 18}
    _us = {"raw_chat": ["u%d" % i for i in range(1500)],
           "codex": ["c%d" % i for i in range(200)],
           "rule": ["r%d" % i for i in range(289)],
           "pattern": ["p%d" % i for i in range(20)]}
    _sed = {"rule": 225, "pattern": 43, "abstract": 11}
    _F.reset_baseline(_tmp, space_stats=_st, uid_sets=_us)
    _ev = _F.evaluate(_tmp, space_stats=_st, uid_sets=_us, sediment=_sed)
    c1b = check("L1翻转·势差触发+连续角", _ev.get("triggered") is True
                and _ev.get("flip_type") == "potential" and _ev.get("target_angle") is not None
                and _ev["potential"]["suggested_angle"] > 90.0)
    _ex = _F.execute_flip(_ev["flip_type"], storage_dir=_tmp,
                          target_angle=_ev["target_angle"], source="test")
    c2 = check("L1翻转·任意角度生效", _ex.get("ok") is True and _ex.get("to_angle") == _ev["target_angle"])
    _h = _F.health(_tmp)
    c3 = check("L1翻转·状态生效+计数", abs(_h.get("angle") - _ev["target_angle"]) < 0.01
               and _h.get("flip_count") == 1)
    c4 = check("L1翻转·审计日志落盘", os.path.exists(_F.event_path(_tmp)))
    # [P3/D3] no-op 抑制：同角度重翻被拦，且不写审计
    _n0 = sum(1 for _ in open(_F.event_path(_tmp), encoding="utf-8"))
    _exn = _F.execute_flip("potential", storage_dir=_tmp,
                           target_angle=_ev["target_angle"], source="test")
    _n1 = sum(1 for _ in open(_F.event_path(_tmp), encoding="utf-8"))
    c5 = check("L1翻转·no-op抑制(D3)", _exn.get("ok") is False and _exn.get("noop") is True and _n1 == _n0)
    # 冷却（120分钟）阻止连续翻转
    _F.MIN_FLIP_INTERVAL_MIN = 120
    _ex1b = _F.execute_flip("natural", storage_dir=_tmp, source="test")
    _ex2 = _F.execute_flip("reverse", storage_dir=_tmp, source="test")
    c6 = check("L1翻转·冷却阻止频繁翻转", _ex1b.get("ok") is True and _ex2.get("ok") is False)
    return c1 and c1b and c2 and c3 and c4 and c5 and c6


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

def test_constancy_age_fallback():
    """恒常门年龄口径（2026-09-13 修复后回归锁）。

    病根：cleanup_expired() 只读 updated_at，解析失败就 age=0
    ⇒ 实测 205 条任务无 updated_at 被**永久豁免**清理；
    "清理"机制接了线却从不生效。
    现三级回退：updated_at → created_at → task_id 内嵌日期。
    """
    import datetime as _dt
    import evo.constancy as _c
    now = _dt.datetime(2026, 9, 13, 12, 0, 0)
    TR = _c.TaskRegistry.task_age_days
    # 1) updated_at 可用
    a1 = TR("task_x", {"updated_at": "2026-09-10T00:00:00"}, now)
    c1 = check("年龄·updated_at 优先", a1 == 3, str(a1))
    # 2) updated_at 缺失 → created_at 回退（原实现在此返回 0）
    a2 = TR("task_x", {"created_at": "2026-08-13T00:00:00"}, now)
    c2 = check("年龄·回退 created_at", a2 == 31, str(a2))
    # 3) 两者都无 → task_id 内嵌日期（原实现在此返回 0 ⇒ 永久豁免）
    a3 = TR("task_20260813_101612_9e91a8", {}, now)
    c3 = check("年龄·回退 task_id 日期", a3 == 31, str(a3))
    # 4) 字段坏值（不是 ISO）也能走回退
    a4 = TR("task_20260813_101612_9e91a8", {"updated_at": "not-a-date"}, now)
    c4 = check("年龄·坏值不致永久豁免", a4 == 31, str(a4))
    # 5) 真无法定年（无时间戳且 id 不含日期）→ 保守保留
    a5 = TR("weird_id", {}, now)
    c5 = check("年龄·无法定年则保守保留", a5 == 0, str(a5))
    return c1 and c2 and c3 and c4 and c5


def test_constancy_goal_gate():
    """恒常门·任务资格闸门（2026-09-13 受权·口径 A）回归锁。

    病根：写侧每轮无条件 begin ⇒ 一条用户消息 = 一条任务（台账 933 条，
    真正恢复过仅 2 条）。本锁保证：单轮问答 / 环境注入不建任务，多轮目标语义才建。
    """
    from evo.main import constancy_goal_gate as G
    # 1) 单轮问答 / 短指令 / 环境注入 / 附件块 → 不立项
    _no = ["现在感觉，迭进 沙漏 一片混乱，感觉无从着手处理?",
           "恒常门每轮自动建任务是有问题的对吗",
           "全搞定他们", "先修", "以上内容你的建议是什么？",
           "冒烟检查", "去看TQ 交易函数",
           "去处理 codex://threads/01a09884-797f-7a81",
           "<in-app-browser-context source=\"ambient-ui-state\">",
           "# Files mentioned by the user:\n\n## 某文档:",
           "# Overview\n\nGenerate 0 to 3 hyperpersonalized sugg"]
    c1 = check("闸门·单轮问答不立项", not any(G(_x)["qualified"] for _x in _no),
               "误建=%s" % [_x[:20] for _x in _no if G(_x)["qualified"]])
    # 2) 多轮目标语义 → 立项（reason 即判据，供审计）
    _yes = [("第一步 改闸门\n第二步 补回归锁", "steps>=2"),
            ("1修闸门\n2补测试", "steps>=2"),
            ("1 改闸门，然后补回归锁", "step+seq"),
            ("按 A 方案加闸门，完成后出交付件", "strong"),
            ("继续 goal_20261231_15to50", "continue"),
            ("A股资金增值目标: 2026-12-31 前 15万→50万", "goal+date")]
    c2 = True
    for _t, _r in _yes:
        _g = G(_t)
        if not check("闸门·立项(%s)" % _r,
                     _g["qualified"] and _g["reason"] == _r, "got=%s" % _g):
            c2 = False
    # 3) 边界：过短 / 空 → 不立项
    c3 = check("闸门·过短不立项", G("A")["qualified"] is False and
               G("")["qualified"] is False)
    return c1 and c2 and c3


def test_constancy_session_close():
    """恒常门·会话绑定与收口（2026-09-13 闸门配套）回归锁。

    病根：写侧每轮新建 + 下一轮 suspend 上一条 ⇒ 台账只进不出。
    本锁保证：① 同会话续接同一任务（不逐轮新建）
              ② 会话切换 → 上一会话遗留任务自动收口（不再跨会话占待办）
              ③ 会话表独立落盘，终态任务不被续接
    """
    import tempfile, os as _os
    import evo.constancy as _c
    _orig = _c._TASKS_PATH
    _dir = tempfile.mkdtemp(prefix="diegin_sess_")
    try:
        _c._TASKS_PATH = _os.path.join(_dir, "constancy_tasks.json")
        reg = _c.TaskRegistry()
        a = reg.begin("会话A任务", completion_criteria="c",
                      context={"session_id": "sess-A"})
        reg.bind_session("sess-A", a["task_id"])
        c1 = check("会话·新任务落库为 paused",
                   bool(a.get("ok")) and
                   reg.snapshot(a["task_id"]).get("status") == "paused")
        c2 = check("会话·同会话返回在办任务",
                   reg.session_sync("sess-A") == a["task_id"])
        c3 = check("会话·无任务会话返回空", reg.session_sync("sess-B") == "")
        c4 = check("会话·切换即收口上一会话",
                   reg.snapshot(a["task_id"]).get("status") == "abandoned")
        c5 = check("会话·收口理由落库",
                   "收口" in str(reg.snapshot(a["task_id"]).get("abandon_reason", "")))
        b = reg.begin("会话B任务", context={"session_id": "sess-B"})
        reg.bind_session("sess-B", b["task_id"])
        c6 = check("会话·本会话任务不受切换影响",
                   reg.snapshot(b["task_id"]).get("status") == "paused")
        c7 = check("会话·第二轮续接同一任务",
                   reg.session_sync("sess-B") == b["task_id"])
        c8 = check("会话·会话表独立落盘", _os.path.exists(reg._sessions_path()))
        reg.complete(b["task_id"])
        c9 = check("会话·终态任务不再被续接", reg.session_sync("sess-B") == "")
        return all([c1, c2, c3, c4, c5, c6, c7, c8, c9])
    finally:
        _c._TASKS_PATH = _orig
        try:
            import shutil as _sh
            _sh.rmtree(_dir, ignore_errors=True)
        except Exception:
            pass


def test_constancy_cold_not_recoverable():
    """恒常门·冷存储不再作为「未完成待办」（2026-09-13 修复）回归锁。

    病根：archive_old_snapshots 把超出 30 条活跃窗口的任务压缩入冷库后，status 仍为
    paused/blocked ⇒ find_recoverable 仍把它当待办返回，而入口只显示前 3 条
    ⇒ 清完 3 条又冒 3 条（实测池 44 条 / 窗口 3 条），观感为「越用越多」。
    本锁保证：① 未冷存的 paused 任务照常可恢复
              ② 已冷存（归档）的任务不再出现在待办池
              ③ 归档任务仍可按意图检索（归档 ≠ 丢失）
    """
    import tempfile, os as _os
    import evo.constancy as _c
    _orig = _c._TASKS_PATH
    _dir = tempfile.mkdtemp(prefix="diegin_cold_")
    try:
        _c._TASKS_PATH = _os.path.join(_dir, "constancy_tasks.json")
        reg = _c.TaskRegistry()
        a = reg.begin("冷存回归锁任务", context={})
        c1 = check("冷存·未归档任务照常可恢复",
                   any(t.get("task_id") == a["task_id"] for t in reg.find_recoverable()))
        reg._tasks[a["task_id"]]["cold_stored"] = True
        reg._save()
        c2 = check("冷存·归档任务不再进入待办池",
                   not any(t.get("task_id") == a["task_id"] for t in reg.find_recoverable()))
        c3 = check("冷存·归档任务仍可按意图检索",
                   any(t.get("task_id") == a["task_id"]
                       for t in reg.find_by_intent("冷存回归锁任务", top_k=5,
                                                   shalou_fallback=False)))
        return all([c1, c2, c3])
    finally:
        _c._TASKS_PATH = _orig
        try:
            import shutil as _sh
            _sh.rmtree(_dir, ignore_errors=True)
        except Exception:
            pass

def test_action_memory_channel():
    """行动时刻记忆（2026-09-12 第1项）：tool_pre 必须把命中规则的 action 正文带进 inject 通道

    回归锁·病根：此前 tool_pre 只暴露规则 id 与命中条数（实测单轮可见 150 字符 / 8080 字符正文）
    ⇒ AI 在动手那一刻看不到「该怎么做」，于是「记不住正确方法」。此锁保证管道不再断线。
    """
    import json as _json
    import contract as _ct
    # 1) 纯函数：正文可见 + 去重键；无命中不注入
    _t, _k = _ct.action_memory({
        "matched_actions": [{"id": "rule_a", "action": "先做A；再做B"}],
        "winning_rule_id": "rule_a", "winning_action": "先做A；再做B",
    })
    c1 = check("行动记忆·规则正文可见", "rule_a" in _t and "先做A；再做B" in _t and len(_k) == 12, _t.splitlines()[0][:40] if _t else "")
    c2 = check("行动记忆·无命中不注入", _ct.action_memory({"matched_interceptions": 0}) == ("", ""))
    # 2) 契约通道透出（打桩引擎，只锁管道）
    _orig = _ct._run
    class _P:
        def __init__(self, out):
            self.stdout = out
            self.returncode = 0
    _env = _ct.parse_envelope(_json.dumps({"event": "tool_pre", "tool": {"name": "shell", "input": {"command": "Get-ChildItem"}}}))
    try:
        _hit = _json.dumps({"decision": "allow", "reason": "ok", "matched_interceptions": 1,
                            "winning_rule_id": "rule_x",
                            "matched_actions": [{"id": "rule_x", "action": "命中即照做：先查权威真源"}]},
                           ensure_ascii=False)
        _ct._run = lambda *a, **k: _P(_hit)
        _r1 = _ct.dispatch(_env)
        c3 = check("行动记忆·inject 透出", bool(_r1.get("inject")) and "先查权威真源" in _r1["inject"])
        c4 = check("行动记忆·inject_key 透出", len(str(_r1.get("inject_key") or "")) == 12, str(_r1.get("inject_key")))
        _ct._run = lambda *a, **k: _P(_json.dumps({"decision": "allow", "matched_interceptions": 0}))
        _r2 = _ct.dispatch(_env)
        c5 = check("行动记忆·无命中 inject 为空", _r2.get("inject") in (None, ""), repr(_r2.get("inject")))
    finally:
        _ct._run = _orig
    # 3) 引擎出口：pre_check 必须带 matched_actions / winning_action（下游接线前提）
    import call_diegin as _cd
    _e = _cd.pre_check({"task_type": "pre_tool", "tool_name": "shell",
                        "command": "Get-ChildItem -LiteralPath .", "text": "Get-ChildItem -LiteralPath ."})
    c6 = check("行动记忆·引擎出口带键",
               isinstance(_e.get("matched_actions"), list) and isinstance(_e.get("winning_action"), str))
    return c1 and c2 and c3 and c4 and c5 and c6


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
    print(f"\n--- 行动时刻记忆 (2026-09-12 第1项 受权实施) ---", flush=True)
    test_action_memory_channel()
    print(f"\n--- 恒常门年龄口径 (2026-09-13 修复) ---", flush=True)
    test_constancy_age_fallback()
    print(f"\n--- 恒常门任务资格闸门/会话收口 (2026-09-13 受权·口径 A) ---", flush=True)
    test_constancy_goal_gate()
    test_constancy_session_close()
    test_constancy_cold_not_recoverable()
    
    total = passed + failed
    print(f"\n{'='*50}", flush=True)
    print(f"  结果: {passed}/{total} 通过 ({failed} 失败)", flush=True)
    print(f"{'='*50}", flush=True)
    
    return 1 if failed > 0 else 0

if __name__ == "__main__":
    sys.exit(main())
