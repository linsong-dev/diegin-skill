# 迭进DGEN 引擎入口(去伪存真真伪门: 言必有证->证必可验->验证为真)

"""

迭进 · DGEN 实战调用入口

迭进引擎入口

"""

import sys, json, os, re

import io
from datetime import datetime

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

from pathlib import Path
from mindol.diegin_integration import memory_format_context, memory_archive



sys.path.insert(0, str(Path(__file__).parent))
from mindol.diegin_integration import memory_format_context, memory_archive

from evo.rule_engine import build_gongqi_suggestions

from evo.main import (get_rules_for_task, arbitrate, full_review, record_behavior,
                      health_check, run_maintenance, dgen_archive, mempalace_search,
                      auto_sandwich, record_user_feedback, auto_sandwich_trigger,
                      generalize_rule, generalize_from_patterns, generalize_cross_domain,
                      ensure_three_strikes, get_strike_status,
                      pace_classify, should_skip_deep_review,
                      get_pacemaker, get_closure,
                      closure_open, closure_close, closure_is_closed,
                      _get_engine, _get_tracker)
from evo.error_detector import ErrorDetector


def _append_audit(msg: str) -> None:
    """追加审计日志（与 hooks 共用 diegin_audit.log）"""
    try:
        _audit_log = os.path.join(os.path.dirname(__file__), "..", "var", "logs", "diegin_audit.log")
        _d = os.path.dirname(_audit_log)
        if _d and not os.path.exists(_d):
            os.makedirs(_d, exist_ok=True)
        _ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]
        with open(_audit_log, "a", encoding="utf-8") as _f:
            _f.write(f"{_ts} {_ts} {msg}\n")
    except Exception:
        pass








def load_principle_rules(context: dict, record_strike: bool = True) -> list:
    """Load strike (一二不过三) + staging (举一反三) rules into arbitration pipeline"""
    engine = _get_engine()
    extra = []
    seen_ids = set()

    # 1. Get non-active but arbitration-relevant rules from engine
    all_rules = engine.get_interceptions(active_only=False)
    for rule in all_rules:
        lifecycle = getattr(rule, "lifecycle_status", "")
        if lifecycle in ("alerting", "staging", "critical", "blocking"):
            tags = getattr(rule, "tags", []) or []
            trigger = getattr(rule, "trigger_condition", "") or ""
            if trigger:
                if not engine._rule_applies_to_context(tags, context):
                    continue
                if not engine._match_condition(trigger, context):
                    continue
                extra.append(rule)
                seen_ids.add(rule.id)
            else:
                if engine._rule_applies_to_context(tags, context):
                    extra.append(rule)
                    seen_ids.add(rule.id)

    # 2. Load from tracker strikes_db for any missed strike records
    try:
        tracker = _get_tracker()
        db_path = tracker._strikes_db_path()
        if os.path.exists(db_path):
            with open(db_path, "r", encoding="utf-8") as f:
                strikes_db = json.load(f)
            # 防御：strikes_db 可能被外部清空为 [] 或 null，需兼容 dict 格式
            if not isinstance(strikes_db, dict):
                strikes_db = {}
            for error_type, entry in strikes_db.items():
                count = entry.get("count", 0)
                if count < 2:
                    continue
                rule_id = "self_error_" + error_type
                if rule_id in seen_ids:
                    continue
                active_rules = engine.get_interceptions(active_only=True)
                if any(r.id == rule_id for r in active_rules):
                    continue
                temp_trigger = "error_type==" + repr(error_type)
                if not engine._match_condition(temp_trigger, context):
                    continue
                from evo.rule_engine import InterceptionRule as _IR
                nr = _IR(
                    id=rule_id,
                    trigger_condition=temp_trigger,
                    action="block_operation",
                    severity="high",
                    tags=["self_error", "one-two-no-three", "auto_block"],
                    logic_score=4.5,
                    outcome_score=3.5,
                    confidence=4.5,
                    source="auto_self_error_tracker",
                    lifecycle_status="active",
                    created_at=entry.get("first_seen", ""),
                    triggered_count=count
                )
                extra.append(nr)
                seen_ids.add(rule_id)
    except Exception as e:
        import sys as _sys
        print("[DG] load_principle_rules error: " + str(e), file=_sys.stderr)

    # 3. Protocol B: marker_missing 规则 — 一二不过三闭环
    marker_missing = context.get("marker_missing", False)
    if marker_missing and marker_missing is True:
        marker_rule_id = "rule_protocol_b_marker_missing"

        # ① 错立改+改毕验：记录 strike，走引擎裁决
        try:
            if record_strike:
                ensure_three_strikes("protocol_b_marker",
                    f"工具命令缺失[DGEN]标记: {str(context.get('command',''))[:80]}")
        except Exception:
            pass

        # 查当前 strike 计数
        strike_count = 0
        try:
            _ss = get_strike_status("protocol_b_marker")
            strike_count = _ss.get("protocol_b_marker", {}).get("count", 0) if isinstance(_ss, dict) else 0
        except Exception:
            pass

        # 根据 strike 次数执行一二不过三策略
        if strike_count >= 3:
            # ③ 三错升级处理：推翻原阻断方案，切换为 audit_only
            from evo.rule_engine import InterceptionRule as _MR3
            mr = _MR3(
                id=marker_rule_id,
                trigger_condition="marker_missing == true",
                action="audit_only; protocol_b_escalated",
                severity="medium",
                tags=["escalated", "protocol_b"],
                logic_score=0.0,
                outcome_score=0.0,
                confidence=0.0,
                source="principle",
                lifecycle_status="active",
                created_at=datetime.now().isoformat(),
            )
        elif strike_count >= 2:
            # ② 再错加固阻断：去伪存真归因过滤
            _detail = str(context.get("command", ""))
            try:
                from evo.evidence_vault import EvidenceVault
                _ev = EvidenceVault()
                _verdict = _ev.classify_failure("protocol_b_marker", _detail)
            except Exception:
                _verdict = "uncertain"

            if _verdict == "internal":
                # 内生惯性：系统自身问题 → 写入硬阻断，切换策略
                _action = "block_operation; internal_inertia_override"
            else:
                # 外生变量/不确定 → 调整策略
                _action = "block_operation; external_variable_adjust"

            from evo.rule_engine import InterceptionRule as _MR2
            mr = _MR2(
                id=marker_rule_id,
                trigger_condition="marker_missing == true",
                action=_action,
                severity="high",
                tags=["strike_2", "protocol_b"],
                logic_score=5.0,
                outcome_score=5.0,
                confidence=5.0,
                source="principle",
                lifecycle_status="active",
                created_at=datetime.now().isoformat(),
            )
        else:
            # ① 初错：标准阻断
            if marker_rule_id not in seen_ids:
                from evo.rule_engine import InterceptionRule as _MR1
                mr = _MR1(
                    id=marker_rule_id,
                    trigger_condition="marker_missing == true",
                    action="block_operation; audit_only",
                    severity="high",
                    tags=["strike_1", "protocol_b"],
                    logic_score=5.0,
                    outcome_score=5.0,
                    confidence=5.0,
                    source="principle",
                    lifecycle_status="active",
                    created_at=datetime.now().isoformat(),
                )
                extra.append(mr)
                seen_ids.add(marker_rule_id)

    return extra

def evidence_filter(interceptions: list, context: dict) -> list:
    """去伪存真：过滤无证据支持的规则（带证据链记录）"""
    filtered = []
    try:
        from evo.main import evidence_record
    except ImportError:
        evidence_record = None

    for rule in interceptions:
        rid = getattr(rule, 'id', '?')
        lifecycle = getattr(rule, 'lifecycle_status', '')

        if lifecycle == 'active':
            # v3.8 去假阳性：active 规则放行不写证据（存在≠验证，避免证据库被假 pass 灌满）
            filtered.append(rule)
            continue

        if lifecycle == 'staging':
            triggered = getattr(rule, 'triggered_count', 0) or 0
            confidence = getattr(rule, 'confidence', 0) or 0
            # [FIX v3.8.1] staging 验证死锁: staging 规则需进入匹配集才会被 record_triggered 计数,
            # 原条件(tc>=2/conf>=4.5)导致新建规则永远无法自然命中 → 放宽为 conf>=3.8 或新建 7 天内放行
            created_at = getattr(rule, 'created_at', '') or ''
            is_new = False
            if created_at:
                try:
                    from datetime import datetime as _dt8
                    is_new = (_dt8.now() - _dt8.fromisoformat(created_at)).days <= 7
                except Exception:
                    pass
            if triggered >= 2 or confidence >= 4.5 or confidence >= 3.8 or is_new:
                filtered.append(rule)
                if evidence_record:
                    evidence_record(rid, 'skip', f'staging阈值达标(触发={triggered},置信度={confidence}), evidence_filter批量非验证', source='evidence_filter')
                continue
            if evidence_record:
                evidence_record(rid, 'skip', f'staging规则证据不足(触发={triggered},置信度={confidence})', source='evidence_filter')
            continue

        filtered.append(rule)

    return filtered


def pre_check(context: dict) -> dict:

    """任务前预检 - 检索规则 + 仲裁（对齐 AGENTS.md 裁决格式）
    集成：缓急律（优先分流）→ 止观门（去重封存）→ 去伪存真 → 裁决律
    """
    # [FIX v3.6.7] 入参防御：非 dict 上下文（如 CLI 误传 JSON 字符串）不再崩溃，避免 fail-open 状态注水
    if not isinstance(context, dict):
        context = {}

    # ========== P0: raw_chat 写入 Mindol ==========
    try:
        _chat_text = context.get("context", context.get("task", context.get("message", context.get("cmd", ""))))
        if _chat_text and len(str(_chat_text)) > 5:
            from mindol.diegin_integration import save_chat
            import threading
            _ = threading.Thread(target=save_chat, args=(str(_chat_text)[:2000],), daemon=True).start()
    except Exception:
        pass

    # ========== P3: 缓急律·优先分流 ==========
    from evo.main import pace_classify, should_skip_deep_review
    pace_result = pace_classify(context)
    skip_deep = should_skip_deep_review(context)
    # v3.8 缓急律可观测：分流结果落审计日志 [PACE]
    try:
        _append_audit("[PACE] channel=%s action=%s reason=%s"
                      % (pace_result.get("channel", "?"), pace_result.get("action", "?"),
                         str(pace_result.get("reason", ""))[:60]))
    except Exception:
        pass

    # ========== P2: 止观门·去重封存 ==========
    from evo.main import closure_is_closed
    task_id = context.get("task_id", context.get("cmd", context.get("message", "")))
    if task_id and closure_is_closed(task_id):
        # v3.8 止观门可观测：封存命中落审计日志 [PHASE_LOCK]
        try:
            _append_audit("[PHASE_LOCK] skip_closed task_id=%s" % str(task_id)[:80])
        except Exception:
            pass
        return {
            "matched_interceptions": 0,
            "matched_patterns": 0,
            "decision": "allow",
            "display_line": "[DGEN] PASS (止观门: 已封存事项，跳过)",
            "reason": "止观门: 该任务已封存，不再重复处理",
            "pace_result": pace_result,
            "closure_skip": True
        }

    rules = get_rules_for_task(context)

    # Five principle network: inject strike + staging rules
    extra_rules = load_principle_rules(context)
    if extra_rules:
        rules["interceptions"].extend(extra_rules)

    # 去伪存真：过滤无证据支持的规则
    rules["interceptions"] = evidence_filter(rules["interceptions"], context)

    # 缓急律：紧急任务跳过深度复盘标记
    if skip_deep:
        for r in rules["interceptions"]:
            if getattr(r, "lifecycle_status", "") == "active":
                pass  # 基础规则仍有效

    # ========== 去伪存真·Mindol语义上下文注入 ==========
    # v3.6: 单次检索复用（format + hits），带超时熔断，不再重复检索
    mindol_context = ""
    mindol_hits = []
    try:
        from mindol.diegin_integration import memory_search, memory_format_context
        ctx_str = json.dumps(context, ensure_ascii=False)[:300]
        mindol_hits = memory_search(ctx_str, max_results=3) or []
        mindol_context = memory_format_context(query=ctx_str, top_k=3)
    except Exception:
        pass

    # ========== 裁决律真实输入：P2 止观门状态 + P3 缓急律通道 ==========
    closure_state = {"status": "open", "task_id": task_id}
    try:
        if task_id and closure_is_closed(task_id):
            closure_state["status"] = "closed"
    except Exception:
        pass
    result = arbitrate(rules["interceptions"], rules["patterns"], mindol_hits=mindol_hits,
                       closure_state=closure_state, pace_channel=pace_result, context=context)

    # ========== v3.6: 命中计数打通（守三/攻七真实统计，供一二不过三升级与 auto_promote） ==========
    try:
        from evo.main import _get_tracker
        _trk = _get_tracker()
        for _r in rules["interceptions"]:
            _trk.record_triggered(getattr(_r, "id", ""))
        for _p in rules["patterns"]:
            _trk.record_triggered(getattr(_p, "id", ""))
    except Exception:
        pass

    # ========== v3.6: 一二不过三·失败教训注入（AI 每轮可见历史教训） ==========
    strike_context = ""
    try:
        import os as _os3
        _sp = _os3.path.join(_os3.path.dirname(_os3.path.abspath(__file__)), "..", "var", "state", "strikes_db.json")
        if _os3.path.exists(_sp):
            with open(_sp, "r", encoding="utf-8") as _f3:
                _strikes = json.load(_f3)
            _entries = []
            if isinstance(_strikes, dict):
                for _k, _v in _strikes.items():
                    _cnt = _v.get("count", 0) if isinstance(_v, dict) else 0
                    if _cnt >= 1:
                        _v = _v if isinstance(_v, dict) else {}
                        _detail = (_v.get("last_detail") or _v.get("detail") or "") or ""
                        _entries.append((_k, _cnt, str(_detail)[:80]))
            _entries.sort(key=lambda x: -x[1])
            if _entries:
                _lines = ["历史教训(一二不过三):"]
                for _k, _cnt, _d in _entries[:3]:
                    _lines.append(f"- {_k} x{_cnt}: {_d}")
                strike_context = "\n".join(_lines)
    except Exception:
        pass

    # ========== 攻七强化 Q1: 及时使用 - 高置信度模式优先推荐 ==========
    _suggestions = build_gongqi_suggestions(rules["patterns"])
    # display_line 升级：放行且有高置信度模式 → 显式推荐优先采用
    _display_line = result.get("display_line", "")
    if result.get("decision") == "allow" and _suggestions and _suggestions[0].get("priority"):
        _top = _suggestions[0]
        _rec = str(_top.get("decision", ""))[:80]
        if _rec and "攻七" not in _display_line:
            _display_line = (_display_line + " | ✅ 攻七优先采用: " + _rec).strip()

    return {
        "matched_interceptions": len(rules["interceptions"]),
        "matched_patterns": len(rules["patterns"]),
        "decision": result["decision"],
        "display_line": _display_line,
        "reason": result["reason"],
        "winning_rule_id": result.get("winning_rule_id"),
        "pace_result": pace_result,
        "mindol_context": mindol_context if mindol_context else "",
        "mindol_hits": len(mindol_hits),
        "suggestions": _suggestions,
        "strike_context": strike_context,
    }

def post_review(task_context: dict, task_result: dict) -> dict:

    """任务后复盘"""

    result = full_review(task_context, task_result)

    # ========== Mindol 语义归档 ==========
    try:
        ctx_str = json.dumps(task_context, ensure_ascii=False)[:200]
        res_str = json.dumps(task_result, ensure_ascii=False)[:200]
        memory_archive("post_review", f"{result.get('decision','?')} | ctx={ctx_str} | res={res_str}")
    except Exception:
        pass

    # ========== v3.5: 复盘结论回流规则置信度（双向反馈闭环） ==========
    try:
        from evo.main import adjust_rule_confidence
        _pos = getattr(result, "positive_signals", []) or []
        _neg = getattr(result, "negative_signals", []) or []
        for _sig in _pos:
            for _rid in (getattr(_sig, "linked_rules", []) or []):
                adjust_rule_confidence(_rid, +0.2, reason=str(getattr(_sig, "description", ""))[:60], source="post_review_positive")
        for _sig in _neg:
            for _rid in (getattr(_sig, "linked_rules", []) or []):
                adjust_rule_confidence(_rid, -0.2, reason=str(getattr(_sig, "description", ""))[:60], source="post_review_negative")
    except Exception:
        pass

    # ========== v3.5: 输出实质验证（去伪存真·claim_checker，去静默化: 记录审计日志） ==========
    try:
        from evo.claim_checker import get_checker
        _out_text = str(task_result.get("output", task_result.get("text", task_result.get("message", ""))))[:2000]
        if _out_text:
            _vc = get_checker().verify_output(_out_text, task_context)
            _append_audit(f"[CLAIM-CHECK] verdict={_vc.get('verdict', '?')} claims={_vc.get('total_claims', 0)} contradicted={_vc.get('contradicted', 0)}")
            if _vc.get("verdict") == "FAIL":
                print(f"[CLAIM-CHECK] 输出含 {_vc.get('contradicted', 0)} 条矛盾声明，已记录待修正")
    except Exception as _ce:
        _append_audit(f"[CLAIM-CHECK] ERROR {_ce}")

    # 自动维护：检查距上次维护是否超过24h
    _maint_file = os.path.join(os.path.dirname(__file__), 'var', 'state', 'last_maintenance.txt')
    _run_maint = False
    if os.path.isfile(_maint_file):
        try:
            with open(_maint_file, 'r') as _mf:
                _last_maint = datetime.fromisoformat(_mf.read().strip())
            if (datetime.now() - _last_maint).total_seconds() > 86400:
                _run_maint = True
        except:
            _run_maint = True
    else:
        _run_maint = True
    if _run_maint:
        try:
            run_maintenance()
            with open(_maint_file, 'w') as _mf:
                _mf.write(datetime.now().isoformat())
        except Exception as _me:
            pass

    return result





def system_health() -> dict:

    """系统健康度"""

    return health_check()





if __name__ == "__main__":

    import sys

    if len(sys.argv) < 2:

        print("用法: python call_diegin.py <check|review|health|maintain|archive|search> [args...]")

        sys.exit(1)



    mode = sys.argv[1]



    if mode == "check" or mode == "stdin":

        if len(sys.argv) > 2:

            raw = sys.argv[2]

        else:

            _b = sys.stdin.buffer.read(); _b = _b[3:] if _b.startswith(b"\xef\xbb\xbf") else _b; raw = _b.decode("utf-8", errors="replace").strip()  # [A1] PS管道BOM/GBK编码注入时json.loads崩溃，字节级去BOM+UTF8解码.lstrip("\ufeff")  # [A1] PS管道注入UTF-8 BOM时json.loads崩溃，去BOM

        ctx = json.loads(raw)

        result = pre_check(ctx)

        print(json.dumps(result, ensure_ascii=False, indent=2))



    elif mode == "check_file":

        fp = sys.argv[2]

        with open(fp, 'r', encoding='utf-8-sig') as f:

            ctx = json.loads(f.read())  # Handle BOM

        result = pre_check(ctx)

        print(json.dumps(result, ensure_ascii=False, indent=2))



    elif mode == "review":

        # v3.6.1: JSON 经 argv 在 Windows 会损坏（引号/换行/中文），优先临时文件 @path，其次 stdin 管道

        _payload = None

        if len(sys.argv) > 2 and sys.argv[2].startswith("@"):

            with open(sys.argv[2][1:], "r", encoding="utf-8") as _f:

                _payload = json.load(_f)

        if _payload is None and not sys.stdin.isatty():

            _raw = sys.stdin.read().strip()

            _parts = _raw.split("\n@@RESULT@@\n", 1)

            _payload = [_parts[0], _parts[1] if len(_parts) > 1 else ""]

        if _payload is None:

            _payload = [sys.argv[2] if len(sys.argv) > 2 else "", sys.argv[3] if len(sys.argv) > 3 else ""]

        def _load_json(x, default):

            if not x:

                return default

            if isinstance(x, str):

                try:

                    return json.loads(x)

                except Exception:

                    return default

            return x

        ctx = _load_json(_payload[0], {"task_id": "unknown"})

        result = _load_json(_payload[1] if len(_payload) > 1 else "", {"status": "completed"})

        result = post_review(ctx, result)

        print(json.dumps(result, ensure_ascii=False, indent=2))



    elif mode == "health":

        import io

        old_out = sys.stdout

        sys.stdout = io.StringIO()

        result = system_health()

        sys.stdout = old_out

        print(json.dumps(result, ensure_ascii=False, indent=2))



    elif mode == "maintain":

        run_maintenance()



    elif mode == "archive":

        content = sys.argv[2] if len(sys.argv) > 2 else sys.stdin.read()

        source = sys.argv[3] if len(sys.argv) > 3 else "dgen_cli"

        ok = dgen_archive(content, source)

        print(json.dumps({"ok": ok}, ensure_ascii=False))



    elif mode == "search":

        query = sys.argv[2] if len(sys.argv) > 2 else ""

        results = mempalace_search(query)

        print(json.dumps(results, ensure_ascii=False, indent=2))



    elif mode == "record_evidence":
        """记录一条证据到 EvidenceVault"""
        try:
            _b = sys.stdin.buffer.read()
            _b = _b[3:] if _b.startswith(b"\xef\xbb\xbf") else _b
            raw_input = _b.decode("utf-8", errors="replace").strip()
            ctx = json.loads(raw_input) if raw_input else {}
            from evo.evidence_vault import EvidenceVault
            ev = EvidenceVault()
            _entry = ev.record(
                rule_id=ctx.get("rule_id", "unknown"),
                verdict=ctx.get("verdict", "pass"),
                reason=ctx.get("reason", ""),
                source=ctx.get("source", "auto"),
                context={"detail": ctx.get("detail", ""), "tool": ctx.get("rule_id", "")}
            )
            if _entry.get("rejected"):
                print(json.dumps({"ok": False, "rejected": True,
                              "reason": _entry.get("reject_reason", "")}, ensure_ascii=False))
            else:
                print(json.dumps({"ok": True, "ts": _entry.get("ts", "")}, ensure_ascii=False))
        except Exception as e:
            print(json.dumps({"ok": False, "error": str(e)}, ensure_ascii=False))
    elif mode == "feedback":

        """用户反馈三态模型"""

        rule_id = sys.argv[2] if len(sys.argv) > 2 else ""

        feedback = sys.argv[3] if len(sys.argv) > 3 else "silent"

        user_action = sys.argv[4] if len(sys.argv) > 4 else None

        result = record_user_feedback(rule_id, feedback, user_action)

        print(json.dumps(result, ensure_ascii=False, indent=2, default=str))



    elif mode == "sandwich":

        """守三攻七复盘（自动钩子版）：python call_diegin.py sandwich <task_type> '<pos_json>' '<neg_json>'"""

        task_type = sys.argv[2] if len(sys.argv) > 2 else "general"

        positive = json.loads(sys.argv[3]) if len(sys.argv) > 3 else []

        negative = json.loads(sys.argv[4]) if len(sys.argv) > 4 else []

        result = auto_sandwich_trigger(task_type, positive, negative)

        print(json.dumps(result, ensure_ascii=False, indent=2))



    

    elif mode == "suggest":

        """攻七：返回与当前上下文匹配的成功模式建议（引擎级匹配）

        用法: python call_diegin.py suggest '<context_json>'

        支持:

          纯文本: 自动转为 {"prompt": "<text>"}

          JSON: 直接作为上下文，支持 tool/op/task_type 等字段

        """

        if not sys.stdin.isatty():
            _b = sys.stdin.buffer.read(); _b = _b[3:] if _b.startswith(b"\xef\xbb\xbf") else _b; raw = _b.decode("utf-8", errors="replace").strip()  # [A1] PS管道BOM/GBK编码注入时json.loads崩溃，字节级去BOM+UTF8解码.lstrip("\ufeff")  # [A1] PS管道注入UTF-8 BOM时json.loads崩溃，去BOM
        elif len(sys.argv) > 2:
            raw = sys.argv[2]
        else:
            raw = ""

        from evo.main import _get_engine, _get_arbiter

        engine = _get_engine()

        # 解析输入

        try:

            context = json.loads(raw)

        except json.JSONDecodeError:

            context = {"prompt": raw, "task_type": "general", "op": "unknown"}

        # 双通道仲裁：先检查守三是否有拦截

        interceptions = engine.get_interceptions(active_only=True)

        matched_inters = []

        for rule in interceptions:

            if engine._match_condition(rule.trigger_condition, context):

                matched_inters.append(rule)

        arbiter_obj = _get_arbiter()

        # 裁决律真实输入：P2 止观门状态 + P3 缓急律通道
        try:
            from evo.main import pace_classify, closure_is_closed
            _pace_c = pace_classify(context)
            _tid = context.get("task_id", context.get("cmd", context.get("message", "")))
            _cs = {"status": "closed" if (_tid and closure_is_closed(_tid)) else "open", "task_id": _tid}
        except Exception:
            _pace_c, _cs = None, None
        arb_result = arbiter_obj.resolve(matched_inters, [], closure_state=_cs, pace_channel=_pace_c)

        is_blocked = arb_result.decision.value in ("BLOCK", "IRON_WALL_BLOCK", "ESCALATE")

        # 用引擎匹配（复用 _match_condition AST解析器）

        matched = engine.match_patterns(context, top_k=5)

        suggestions = []

        for p in matched:

            suggestions.append({

                "id": p.id if hasattr(p, 'id') else '',

                "scenario": p.trigger_scenario if hasattr(p, 'trigger_scenario') else '',

                "decision": p.decision_logic if hasattr(p, 'decision_logic') else '',

                "confidence": getattr(p, 'confidence', 0),

                "auto_promoted": getattr(p, 'auto_promoted', False),

            })

        result = {

            "suggestions": [] if is_blocked else suggestions,

            "count": 0 if is_blocked else len(suggestions),

            "total_patterns": len(engine.get_patterns(active_only=True)),

            "matched_via": "engine_ast",

            "guard_decision": arb_result.decision.value if hasattr(arb_result, 'decision') else 'ALLOW',

            "guard_blocked": is_blocked,

            "guard_reason": arb_result.reason if is_blocked else "",

        }

        print(json.dumps(result, ensure_ascii=False, indent=2))

    elif mode == "pre_reply":
        """UserPromptSubmit 聚合模式：一次引擎加载完成所有预检工作
        用法: echo '<prompt_json>' | python call_diegin.py pre_reply
        合并 check + health + suggest + arbitrate_detail + verify + mindol record
        输出: JSON (含完整结果)
        退出码: 1=block, 0=allow
        """
        import sys as _sys
        try:
            if not _sys.stdin.isatty():
                _b = _sys.stdin.buffer.read()
                _b = _b[3:] if _b.startswith(b"\xef\xbb\xbf") else _b
                raw = _b.decode("utf-8", errors="replace").strip()
            else:
                raw = _sys.argv[2]
        except (IndexError, IOError):
            raw = "{}"
        input_data = json.loads(raw) if raw else {}
        prompt = input_data.get("prompt", input_data.get("text", ""))
        turn_id = input_data.get("turn_id", "")
        blocked_error_type = input_data.get("blocked_error_type", "")

        # 引擎级导入（一次加载）
        from evo.main import (
            _get_engine, _get_arbiter, get_rules_for_task, arbitrate,
            health_check as _health_check, get_vault, run_maintenance
        )
        from mindol.diegin_integration import memory_format_context, memory_archive as dgen_archive
        from evo.evidence_vault import EvidenceVault

        # 构建上下文
        ctx = {
            "task_type": "user_prompt",
            "text": prompt,
            "hook_event_name": "UserPromptSubmit",
            "prompt": prompt,
        }
        if blocked_error_type:
            ctx["blocked_error_type"] = blocked_error_type

        # 0. raw_chat 写入 Mindol（异步）
        try:
            if prompt and len(prompt) > 5:
                from mindol.diegin_integration import save_chat
                import threading
                _ = threading.Thread(target=save_chat, args=(prompt[:2000],), daemon=True).start()
        except Exception:
            pass

        # 1. 预检
        check_result = pre_check(ctx)
        decision = check_result.get("decision", "allow")
        matched_count = check_result.get("matched_interceptions", 0)
        winning_rule_id = check_result.get("winning_rule_id")
        reason = check_result.get("reason", "")
        display_line = check_result.get("display_line", "")
        mindol_ctx = check_result.get("mindol_context", "")
        strike_context = check_result.get("strike_context", "")

        if decision in ("block", "iron_wall_block"):
            # block 路径：输出阻断信息，退出 1
            enhanced = display_line
            if mindol_ctx:
                short_ctx = mindol_ctx.replace("\n", " ").replace("\r", "")
                if len(short_ctx) > 200:
                    short_ctx = short_ctx[:200] + "..."
                enhanced += " | mem:" + short_ctx
            print(enhanced)
            _sys.exit(1)

        # 2. allow 路径：继续执行全部操作
        engine = _get_engine()
        vault = get_vault()

        # 3. 健康度（捕获 stdout，避免健康报告污染 JSON 输出）
        import io as _io
        _old_stdout = sys.stdout
        sys.stdout = _io.StringIO()
        health_result = _health_check()
        sys.stdout = _old_stdout

        # 4. 攻七建议
        arbiter_obj = _get_arbiter()
        interceptions = engine.get_interceptions(active_only=True)
        matched_inters = []
        for rule in interceptions:
            if engine._match_condition(rule.trigger_condition, ctx):
                matched_inters.append(rule)
        # 裁决律真实输入：P2 止观门状态 + P3 缓急律通道
        try:
            from evo.main import pace_classify, closure_is_closed
            _pace_c = pace_classify(ctx)
            _tid = ctx.get("task_id", ctx.get("cmd", ctx.get("message", "")))
            _cs = {"status": "closed" if (_tid and closure_is_closed(_tid)) else "open", "task_id": _tid}
        except Exception:
            _pace_c, _cs = None, None
        arb_result = arbiter_obj.resolve(matched_inters, [], closure_state=_cs, pace_channel=_pace_c)
        is_blocked = getattr(arb_result, 'decision', None)
        is_blocked_val = is_blocked.value if is_blocked else "ALLOW"
        guard_blocked = is_blocked_val in ("BLOCK", "IRON_WALL_BLOCK", "ESCALATE")

        matched = engine.match_patterns(ctx, top_k=5)
        suggestions_list = []
        for p in matched:
            suggestions_list.append({
                "id": getattr(p, "id", ""),
                "scenario": getattr(p, "trigger_scenario", ""),
                "decision": getattr(p, "decision_logic", ""),
                "confidence": getattr(p, "confidence", 0),
            })

        # 格式化攻七输出文本
        sug_lines = []
        for s in suggestions_list:
            sug_lines.append("  - " + s["id"] + ": " + s["decision"])
        suggestions_text = ""
        if sug_lines:
            suggestions_text = "\n攻七·推荐路径\n" + "\n".join(sug_lines)

        # 5. 仲裁详情
        arb_detail_rules = get_rules_for_task(ctx)
        arb_detail_result = arbitrate(arb_detail_rules["interceptions"], arb_detail_rules["patterns"])
        conflict_rules_list = []
        for r in arb_detail_rules["interceptions"]:
            conflict_rules_list.append({
                "id": getattr(r, "id", "?"),
                "severity": getattr(r, "severity", "?"),
            })
        detail = {
            "matched_interceptions": len(arb_detail_rules["interceptions"]),
            "matched_patterns": len(arb_detail_rules["patterns"]),
            "decision": arb_detail_result["decision"],
            "reason": arb_detail_result["reason"],
            "winning_rule_id": arb_detail_result.get("winning_rule_id"),
            "conflict_rules": conflict_rules_list,
            "degradation": arb_detail_result.get("degradation_type", ""),
        }

        # 6. 一致性验证（读上次决策，写本次）
        import os as _os
        _last_check_file = _os.path.join(_os.path.dirname(__file__), "..", "var", "state", "last_check_result.json")
        verify_result = {"current_decision": decision, "consistency": "first_check", "flip_detected": False}
        if _os.path.exists(_last_check_file):
            try:
                with open(_last_check_file, "r", encoding="utf-8") as _f:
                    _last = json.load(_f)
                _prev = _last.get("decision", "unknown")
                if _prev != decision:
                    verify_result["consistency"] = "flipped"
                    verify_result["flip_detected"] = True
                    verify_result["previous_decision"] = _prev
                else:
                    verify_result["consistency"] = "consistent"
            except Exception:
                pass
        # 保存当前决策
        try:
            _os.makedirs(_os.path.dirname(_last_check_file), exist_ok=True)
            with open(_last_check_file, "w", encoding="utf-8") as _f:
                json.dump({"decision": decision, "ts": datetime.now().isoformat()}, _f, ensure_ascii=False)
        except Exception:
            pass

        # 7. 写入 Mindol 记忆（pre_reply 空间）
        try:
            dgen_archive("pre_reply", f"decision={decision} matched={matched_count} status=allow", {})
        except Exception:
            pass

        # 8. 构建输出文本
        marker_str = "[DGEN]"
        mindol_str = ""
        if mindol_ctx:
            short_ctx = mindol_ctx.replace("\n", " ").replace("\r", "")
            if len(short_ctx) > 150:
                short_ctx = short_ctx[:150] + "..."
            mindol_str = " mem:" + short_ctx
        strike_str = ""
        if strike_context:
            strike_str = "\n" + strike_context
        output_text = marker_str + " PASS" + mindol_str + suggestions_text + strike_str
        output_text += "\n\n=== PROTOCOL ==="
        output_text += "\nFirst tool command MUST contain: " + marker_str
        output_text += "\n=== END PROTOCOL ==="

        # 9. 审计日志
        try:
            _audit_log = _os.path.join(_os.path.dirname(__file__), "..", "var", "logs", "diegin_audit.log")
            _ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]
            _msg = f"{_ts} {_ts} [HOOK:DGEN-CHECK] OK decision={decision} matched={matched_count}"
            _d = _os.path.dirname(_audit_log)
            if _d and not _os.path.exists(_d):
                _os.makedirs(_d, exist_ok=True)
            with open(_audit_log, "a", encoding="utf-8") as _f:
                _f.write(f"{_msg}\n")
        except Exception:
            pass

        # 10. 输出完整结果
        output = {
            "decision": decision,
            "matched_count": matched_count,
            "winning_rule_id": winning_rule_id,
            "reason": reason,
            "health": health_result,
            "suggestions": suggestions_list,
            "arbitrate_detail": detail,
            "verify": verify_result,
            "display_text": output_text,
            "mindol_context": mindol_ctx,
            "strike_context": strike_context,
        }
        print(json.dumps(output, ensure_ascii=False))

    elif mode == "record_success":

        """攻七：记录一次成功的工具调用（带阈值过滤）
        用法: python call_diegin.py record_success <tool_name> [method]
        method: 本次成功做法的命令/描述（实质化模式库）
        阈值: 过滤简单查询、重复保存，只保留有学习价值的操作
        """

        tool_name = sys.argv[2] if len(sys.argv) > 2 else "unknown"
        method = sys.argv[3] if len(sys.argv) > 3 else ""
        # v3.6.6 修复：PowerShell 传参会拆分含引号/分号的命令 → 支持 stdin JSON 传 method（无损）
        if not method and not sys.stdin.isatty():
            try:
                _b = sys.stdin.buffer.read()
                _b = _b[3:] if _b.startswith(b"\xef\xbb\xbf") else _b
                _in = _b.decode("utf-8", errors="replace").strip()
                if _in:
                    _j = json.loads(_in)
                    if isinstance(_j, dict):
                        tool_name = _j.get("tool_name", tool_name) or tool_name
                        method = _j.get("method", "") or ""
            except Exception:
                pass
        _tn = tool_name.lower()

        # 阈值 1: 跳过简单只读操作
        _readonly = {"ls","dir","get-childitem","echo","write-output","cd","pwd",
                     "get-location","write-host","cat","type","find","select-string",
                     "get-content","get-process","get-service","get-date",
                     "get-item","get-help","get-command","get-alias","get-psdrive",
                     "measure","sort","where-object","format-table","format-list",
                     "out-string","write-progress","prompt"}
        import re as _re
        if _tn in _readonly or _re.match(r"^(ls|dir|echo|cd|pwd|get-|write-host)", _tn):
            _r = {"action": "skipped_readonly", "tool": tool_name, "reason": "查询类操作不保存成功模式"}
            print(json.dumps(_r, ensure_ascii=False, indent=2, default=str))
            sys.exit(0)

        # 阈值 2: 高频去重（同一工具 N 秒内不重复保存）
        import os as _os, json as _json, time as _time
        _counter_file = _os.path.join(_os.path.dirname(__file__), "..", "var", "state", ".record_success_counter.json")
        _cooldown = 300
        _now = _time.time()
        _counter = {}
        if _os.path.exists(_counter_file):
            try:
                with open(_counter_file, "r", encoding="utf-8") as _f:
                    _counter = _json.load(_f)
            except Exception:
                _counter = {}
        # v3.6.3 验证门兼容：staging 模式必须允许重复触发以完成验证（第2次转 active）
        _staging_skip = False
        try:
            from evo.main import _get_engine
            _pat = _get_engine().get_pattern_by_id("pat_auto_tool_" + tool_name.replace(".", "_") + "_1")
            if _pat and getattr(_pat, "lifecycle_status", "") == "staging":
                _staging_skip = True
        except Exception:
            pass
        _last = _counter.get(tool_name, 0)
        if not _staging_skip and _now - _last < _cooldown:
            _r = {"action": "skipped_dedup", "tool": tool_name, "reason": "5分钟内已保存过 " + tool_name + " 的模式"}
            print(json.dumps(_r, ensure_ascii=False, indent=2, default=str))
            sys.exit(0)
        _counter[tool_name] = _now
        try:
            _os.makedirs(_os.path.dirname(_counter_file), exist_ok=True)
            with open(_counter_file, "w", encoding="utf-8") as _f:
                _json.dump(_counter, _f, ensure_ascii=False, indent=2)
        except Exception:
            pass

        # 通过阈值：保存成功模式（v3.6.1 带方法内容实质化）
        from evo.main import auto_sandwich_trigger
        result = auto_sandwich_trigger("tool_" + tool_name.replace(".", "_"), positive=[tool_name], negative=[], method=method)
        print(json.dumps(result, ensure_ascii=False, indent=2, default=str))
    elif mode == "audit_patterns":
        """攻七质量审计（防再生）：扫描成功模式，空壳自动归档
        用法: python call_diegin.py audit_patterns
        空壳判定（与 record_success v3.7 门槛一致）：
          - decision_logic 为空 / 去空白后 <6 字符 / 含无学习价值词
          - 或 trigger_condition 与 trigger_scenario 均为空（无触发能力）
        归档为 archived 而非删除，保留可追溯；幂等，二次运行不重复归档。
        """
        try:
            from evo.main import _get_engine
            engine = _get_engine()
            _sp = os.path.join(os.path.dirname(__file__), "evo", "rules", "success_patterns.json")
            with open(_sp, "r", encoding="utf-8") as _f:
                patterns = json.load(_f)
        except Exception as _e:
            _r = {"action": "error", "error": str(_e)}
            print(json.dumps(_r, ensure_ascii=False, indent=2, default=str))
            sys.exit(1)

        _hollow_words = ("成功完成exit=0", "completedexit=0", "工具成功完成", "unknown")
        archived_ids = []
        kept_ids = []
        for _p in patterns:
            _pid = _p.get("id", "")
            _logic = str(_p.get("decision_logic", "") or "").strip()
            _scene = str(_p.get("trigger_scenario", "") or "").strip()
            _cond = str(_p.get("trigger_condition", "") or "").strip()
            _life = _p.get("lifecycle_status", "")
            _dl_compact = _logic.replace(" ", "").replace("\u3000", "").lower()
            is_hollow = (len(_dl_compact) < 6) or any(_w in _dl_compact for _w in _hollow_words)
            if not is_hollow and not _cond and not _scene:
                is_hollow = True
            # [L4-防再生] 工具名级伪模式：decision_logic 为纯工具名/标识符且无触发条件 → 视为空壳归档
            if not is_hollow and not _cond:
                import re as _are
                if _logic and len(_logic) <= 40 and not _are.search(r"[\s=;|&>^$()\[\]\{\}:]", _logic) and _logic.replace("_", "").isalnum():
                    is_hollow = True
            if not is_hollow:
                kept_ids.append(_pid)
                continue
            if _life == "archived":
                continue  # 幂等：已归档跳过
            try:
                engine.update_pattern(
                    _pid,
                    lifecycle_status="archived",
                    archive_reason="quality_gate_hollow",
                    archived_at=datetime.now().isoformat(),
                )
                archived_ids.append(_pid)
            except Exception as _e:
                _append_audit(f"[AUDIT-PATTERNS] 归档失败 {_pid}: {_e}")

        _total = len(patterns)
        _r = {
            "action": "audit_patterns",
            "total": _total,
            "archived": len(archived_ids),
            "kept": len(kept_ids),
            "archived_ids": archived_ids,
        }
        print(json.dumps(_r, ensure_ascii=False, indent=2, default=str))
        if archived_ids:
            _append_audit(f"[AUDIT-PATTERNS] 空壳模式归档 archived={len(archived_ids)} total={_total} ids={','.join(archived_ids[:20])}")
    elif mode == "audit_staging":
        """举一反三 staging 积压清理（防再生）
        死亡判定：
          - 源模式（pat_auto_tool_*）已归档或不存在 → 归档
          - 创建超 14 天且从未触发 → 归档
          - 测试残留（TestTool 等）→ 归档
        有效判定：triggered_count >= 2 → 转 active（回归校验通过）
        """
        try:
            from evo.main import _get_engine
            import datetime as _dt
            engine = _get_engine()
            rules = engine.get_interceptions(active_only=False)
            staging = [r for r in rules if getattr(r, "lifecycle_status", "") == "staging"]
            pats = engine.get_patterns(active_only=False)
            pat_map = {getattr(p, "id", ""): p for p in pats}
            now = _dt.datetime.now(_dt.timezone.utc)
            archived = []
            promoted = []
            kept = []
            for r in staging:
                rid = getattr(r, "id", "")
                if "testtool" in rid.lower():
                    engine.update_interception(rid, lifecycle_status="archived",
                                               archive_reason="staging_test_residue",
                                               archived_at=now.isoformat())
                    archived.append(rid)
                    continue
                if rid.startswith("pat_rule_pat_auto_tool_"):
                    src_id = rid[len("pat_rule_"):]
                    src_pat = pat_map.get(src_id)
                    if src_pat is None or getattr(src_pat, "lifecycle_status", "") == "archived":
                        engine.update_interception(rid, lifecycle_status="archived",
                                                   archive_reason="source_pattern_archived",
                                                   archived_at=now.isoformat())
                        archived.append(rid)
                        continue
                ca = str(getattr(r, "created_at", "") or "")
                try:
                    if ca.endswith("Z"):
                        ca = ca[:-1] + "+00:00"
                    created_dt = _dt.datetime.fromisoformat(ca)
                    if created_dt.tzinfo is None:
                        created_dt = created_dt.replace(tzinfo=_dt.timezone.utc)
                    age_days = (now - created_dt).total_seconds() / 86400
                except Exception:
                    age_days = 999
                tc = getattr(r, "triggered_count", 0) or 0
                if tc >= 2:
                    engine.update_interception(rid, lifecycle_status="active",
                                               verified_at=now.isoformat())
                    promoted.append(rid)
                elif age_days > 14:
                    engine.update_interception(rid, lifecycle_status="archived",
                                               archive_reason="staging_never_triggered_14d",
                                               archived_at=now.isoformat())
                    archived.append(rid)
                else:
                    kept.append(rid)
            engine.save_all()
            try:
                sq_path = os.path.join(os.path.dirname(__file__), "..", "var", "state", "staging_queue.json")
                with open(sq_path, "r", encoding="utf-8") as _f:
                    sq = json.load(_f)
                if isinstance(sq, list):
                    sq = [q for q in sq if q.get("id") not in archived]
                    with open(sq_path, "w", encoding="utf-8") as _f:
                        json.dump(sq, _f, ensure_ascii=False, indent=2)
            except Exception:
                pass
            _r = {
                "action": "audit_staging",
                "total": len(staging),
                "archived": len(archived),
                "promoted": len(promoted),
                "kept": len(kept),
                "archived_ids": archived[:30],
                "promoted_ids": promoted,
            }
            print(json.dumps(_r, ensure_ascii=False, indent=2, default=str))
            if archived:
                _append_audit("[AUDIT-STAGING] 死亡staging清理 archived=%d promoted=%d kept=%d ids=%s"
                              % (len(archived), len(promoted), len(kept), ",".join(archived[:20])))
        except Exception as _e:
            print(json.dumps({"action": "audit_staging", "error": str(_e)}, ensure_ascii=False, indent=2, default=str))
            sys.exit(1)
    elif mode == "audit_evidence":
        """去伪存真：证据库去假阳性（防再生）
        将 evidence_filter 批量产生的假 pass（存在≠验证）标记为 skip，
        保留可追溯（reason 前缀 [伪]），不删除记录。
        """
        try:
            _trail_path = os.path.join(os.path.dirname(__file__), "var", "state", "evidence_trail.json")
            with open(_trail_path, "r", encoding="utf-8") as _f:
                trail = json.load(_f)
            if not isinstance(trail, list):
                trail = []
            cleaned = 0
            for _e in trail:
                _src = str(_e.get("source", "") or "")
                _verdict = str(_e.get("verdict", "") or "")
                _reason = str(_e.get("reason", "") or "")
                if _src == "evidence_filter" and _verdict == "pass":
                    _e["verdict"] = "skip"
                    _e["reason"] = "[伪] 非验证动作（evidence_filter 批量产生），2026-08-05 清理: " + _reason[:120]
                    cleaned += 1
            with open(_trail_path, "w", encoding="utf-8") as _f:
                json.dump(trail, _f, ensure_ascii=False, indent=2)
            _pass = sum(1 for e in trail if e.get("verdict") == "pass")
            _skip = sum(1 for e in trail if e.get("verdict") == "skip")
            _r = {"action": "audit_evidence", "total": len(trail), "cleaned": cleaned,
                  "pass": _pass, "skip": _skip, "fail": sum(1 for e in trail if e.get("verdict") == "fail")}
            print(json.dumps(_r, ensure_ascii=False, indent=2, default=str))
            if cleaned:
                _append_audit("[AUDIT-EVIDENCE] 假证据清理 cleaned=%d total=%d pass=%d"
                              % (cleaned, len(trail), _pass))
        except Exception as _e:
            print(json.dumps({"action": "audit_evidence", "error": str(_e)}, ensure_ascii=False, indent=2, default=str))
            sys.exit(1)
    elif mode == "feedback_adopt":
        """攻七反馈闭环（Q4）：AI/用户对攻七建议的采纳或否决
        用法: python call_diegin.py feedback_adopt
        stdin JSON: {"pattern_id": "...", "adopted": true|false, "reason": "..."}
          adopted=true  → record_user_feedback(agree)  置信度+0.5
          adopted=false → record_user_feedback(veto)   置信度×0.7 + override_count
        由 post_tool 在工具成功时自动调用（推荐→采用→强化闭环）
        """
        try:
            _b = sys.stdin.buffer.read()
            _b = _b[3:] if _b.startswith(b"\xef\xbb\xbf") else _b
            _in = json.loads(_b.decode("utf-8", errors="replace").strip() or "{}")
            _pid = _in.get("pattern_id", "")
            _adopted = bool(_in.get("adopted", True))
            _reason = str(_in.get("reason", "") or "")[:120]
            if not _pid:
                print(json.dumps({"action": "feedback_adopt", "error": "pattern_id 缺失"}, ensure_ascii=False, indent=2))
                sys.exit(1)
            from evo.main import record_user_feedback
            _res = record_user_feedback(_pid, "agree" if _adopted else "veto")
            _r = {
                "action": "feedback_adopt",
                "pattern_id": _pid,
                "adopted": _adopted,
                "feedback_result": _res,
                "reason": _reason,
            }
            print(json.dumps(_r, ensure_ascii=False, indent=2, default=str))
            _append_audit("[FEEDBACK-ADOPT] %s pattern=%s result=%s %s"
                          % ("adopted" if _adopted else "vetoed", _pid,
                             str(_res.get("action", "?")), _reason))
        except Exception as _e:
            print(json.dumps({"action": "feedback_adopt", "error": str(_e)}, ensure_ascii=False, indent=2, default=str))
            sys.exit(1)
    elif mode == "record_error":
        """一二不过三：记录并追踪一次错误
        用法: python call_diegin.py record_error <error_type> [detail] [severity]
        第1次：自动创建拦截规则
        第2次：加固规则
        第3次：写 override.json 强制阻断
        """
        if len(sys.argv) > 2:
            error_type = sys.argv[2]
            detail = sys.argv[3] if len(sys.argv) > 3 else ""
            severity = sys.argv[4] if len(sys.argv) > 4 else "high"
        else:
            _b = sys.stdin.buffer.read()
            _b = _b[3:] if _b.startswith(b"\xef\xbb\xbf") else _b
            _in = json.loads(_b.decode("utf-8", errors="replace").strip() or "{}")
            error_type = _in.get("error_type", _in.get("type", "unknown"))
            detail = _in.get("detail", _in.get("error", ""))
            severity = _in.get("severity", "high")
        result = ensure_three_strikes(error_type, detail, severity)
        print(json.dumps(result, ensure_ascii=False, indent=2, default=str))
    elif mode == "arbitrate_detail":
        """去伪存真：完整冲突仲裁详情（带规则冲突分析）
        用法: echo '<context_json>' | python call_diegin.py arbitrate_detail
        或: python call_diegin.py arbitrate_detail '<context_json>'
        返回: 完整冲突集、胜出规则、降级信息、仲裁链路
        """
        if len(sys.argv) > 2:
            raw = sys.argv[2]
        else:
            _b = sys.stdin.buffer.read(); _b = _b[3:] if _b.startswith(b"\xef\xbb\xbf") else _b; raw = _b.decode("utf-8", errors="replace").strip()  # [A1] PS管道BOM/GBK编码注入时json.loads崩溃，字节级去BOM+UTF8解码.lstrip("\ufeff")  # [A1] PS管道注入UTF-8 BOM时json.loads崩溃，去BOM
        ctx = json.loads(raw)
        rules = get_rules_for_task(ctx)
        result = arbitrate(rules["interceptions"], rules["patterns"])
        output = {
            "matched_interceptions": len(rules["interceptions"]),
            "matched_patterns": len(rules["patterns"]),
            "decision": result["decision"],
            "reason": result["reason"],
            "winning_rule_id": result.get("winning_rule_id"),
            "conflict_rules": [
                {"id": r.id, "severity": getattr(r, "severity", "?"), "reason": getattr(r, "reason", "")}
                for r in rules["interceptions"]
            ] if rules["interceptions"] else [],
            "degradation": result.get("degradation_type", ""),
        }
        print(json.dumps(output, ensure_ascii=False, indent=2, default=str))


    elif mode == "verify":
        """去伪存真：一致性验证（跨检查对比）
        用法: python call_diegin.py verify '<current_check_json>' [last_check_file]
        比较当前检查结果与上一次检查，检测决策是否反转
        """
        import os as _os
        raw = sys.argv[2] if len(sys.argv) > 2 else sys.stdin.read().strip()
        current = json.loads(raw) if raw else {}
        last_file = sys.argv[3] if len(sys.argv) > 3 else _os.path.join(_os.path.dirname(__file__), "..", "var", "state", "last_check_result.json")
        result = {
            "current_decision": current.get("decision", "unknown"),
            "consistency": "first_check",
            "flip_detected": False,
        }
        if _os.path.exists(last_file):
            try:
                with open(last_file, "r", encoding="utf-8") as f:
                    last = json.load(f)
                prev = last.get("decision", "unknown")
                curr = current.get("decision", "unknown")
                if prev != curr:
                    result["consistency"] = "flipped"
                    result["flip_detected"] = True
                    result["previous_decision"] = prev
                    result["reason"] = f"决策反转: {prev} → {curr}, 需人工确认"
                else:
                    result["consistency"] = "consistent"
            except Exception:
                pass
        # 保存当前结果供下次对比
        try:
            _os.makedirs(_os.path.dirname(last_file), exist_ok=True)
            with open(last_file, "w", encoding="utf-8") as f:
                json.dump(current, f, ensure_ascii=False)
        except Exception:
            pass
        print(json.dumps(result, ensure_ascii=False, indent=2, default=str))








    elif mode == "verify_rules":
        """去伪存真·验证增强：批量验证规则库质量"""
        import os as _os_vr, json as _j_vr

        rules_path = _os_vr.path.join(_os_vr.path.dirname(__file__), "evo", "rules", "interception_rules.json")
        patterns_path = _os_vr.path.join(_os_vr.path.dirname(__file__), "evo", "rules", "success_patterns.json")

        rules = []
        if _os_vr.path.exists(rules_path):
            with open(rules_path, "r", encoding="utf-8") as f:
                rules = _j_vr.load(f)

        patterns = []
        if _os_vr.path.exists(patterns_path):
            with open(patterns_path, "r", encoding="utf-8") as f:
                patterns = _j_vr.load(f)

        checks = {"passed": 0, "warnings": 0, "errors": 0, "items": []}

        # 检查每条拦截规则
        for rule in rules:
            rid = rule.get("id", "?")
            items = []

            # 1. 必须有关键字段
            if not rule.get("trigger_condition"):
                items.append({"severity": "error", "msg": f"{rid}: 缺少 trigger_condition"})
            if not rule.get("action"):
                items.append({"severity": "error", "msg": f"{rid}: 缺少 action"})

            # 2. 必须有原则归属标签
            tags = rule.get("tags", [])
            tag_str = " ".join(tags)
            principle_tags = [t for t in tags if "principle:" in t]
            if not principle_tags:
                # 推断归属
                lifecycle = rule.get("lifecycle_status", "")
                source = rule.get("source", "")
                if lifecycle in ("blocking", "critical") or "self_error" in tag_str:
                    inferred = "principle:一二不过三"
                elif lifecycle in ("staging", "cached") or "举一反三" in tag_str:
                    inferred = "principle:举一反三"
                elif source == "war_game" or "pattern" in tag_str:
                    inferred = "principle:攻七"
                else:
                    inferred = "principle:守三"
                items.append({"severity": "warning", "msg": f"{rid}: 缺少principle标签，推断为 {inferred}"})

            # 3. 检查置信度合理性
            conf = rule.get("confidence", 0)
            if conf <= 0:
                items.append({"severity": "error", "msg": f"{rid}: 置信度为0，规则无效"})
            elif conf < 2.0:
                items.append({"severity": "warning", "msg": f"{rid}: 置信度过低({conf})，建议降权"})

            # 4. 严重度标签标准
            sev = rule.get("severity", "")
            if sev not in ("critical", "high", "medium", "low"):
                items.append({"severity": "warning", "msg": f"{rid}: 严重度'{sev}'非标准值(critical/high/medium/low)"})

            # 汇总
            for item in items:
                if item["severity"] == "error":
                    checks["errors"] += 1
                elif item["severity"] == "warning":
                    checks["warnings"] += 1
                if item not in checks["items"]:
                    checks["items"].append(item)
            if not items:
                checks["passed"] += 1

        # 检查规则间冲突
        for i, r1 in enumerate(rules):
            for r2 in rules[i+1:]:
                if r1.get("id") == r2.get("id"):
                    continue
                c1 = r1.get("trigger_condition", "")
                c2 = r2.get("trigger_condition", "")
                a1 = r1.get("action", "")
                a2 = r2.get("action", "")
                # 相同触发条件但不同动作 → 潜在冲突
                if c1 and c2 and c1 == c2 and a1 != a2:
                    checks["items"].append({
                        "severity": "warning",
                        "msg": f"规则冲突: {r1['id']}和{r2['id']} 触发条件相同但动作不同"
                    })
                    checks["warnings"] += 1

        result = {
            "principle": "去伪存真·规则验证",
            "total_rules": len(rules),
            "total_patterns": len(patterns),
            "checks": checks,
            "health": "good" if checks["errors"] == 0 else "needs_attention",
        }
        print(_j_vr.dumps(result, ensure_ascii=False, indent=2, default=str))

    elif mode == "generalize_cross_domain":

        """举一反三：跨域泛化"""

        result = generalize_cross_domain()

        print(json.dumps({"created": result}, ensure_ascii=False, indent=2))


    elif mode == "generalize_patterns":

        """举一反三：从成功模式泛化为拦截规则"""

        result = generalize_from_patterns()

        print(json.dumps({"created": result}, ensure_ascii=False, indent=2))


    elif mode == "pace_check":
        """缓急律：检查当前任务类型分类"""
        if len(sys.argv) > 2:
            ctx = json.loads(sys.argv[2])
        else:
            _b = sys.stdin.buffer.read()
            _b = _b[3:] if _b.startswith(b"\xef\xbb\xbf") else _b
            ctx = json.loads(_b.decode("utf-8", errors="replace").strip() or "{}")
        pm = get_pacemaker()
        result = pm.classify(ctx)
        print(json.dumps(result, ensure_ascii=False, indent=2, default=str))

    elif mode == "pace_status":
        """缓急律：查看调度器状态"""
        pm = get_pacemaker()
        result = pm.get_status()
        print(json.dumps(result, ensure_ascii=False, indent=2, default=str))

    elif mode == "pace_status":
        """缓急律：查看调度器状态"""
        pm = get_pacemaker()
        result = pm.get_status()
        print(json.dumps(result, ensure_ascii=False, indent=2, default=str))

    elif mode == "closure_open":
        """止观门：打开一个事项"""
        item_id = sys.argv[2]
        desc = sys.argv[3] if len(sys.argv) > 3 else ""
        cg = get_closure()
        result = cg.open(item_id, desc)
        print(json.dumps(result, ensure_ascii=False, indent=2))

    elif mode == "closure_close":
        """止观门：封存一个事项（v3.7 支持 stdin JSON 传 learnings）"""
        learnings = None
        if len(sys.argv) > 2:
            item_id = sys.argv[2]
            summary = sys.argv[3] if len(sys.argv) > 3 else ""
        else:
            _b = sys.stdin.buffer.read()
            _b = _b[3:] if _b.startswith(b"\xef\xbb\xbf") else _b
            _in = json.loads(_b.decode("utf-8", errors="replace").strip() or "{}")
            item_id = _in.get("item_id", _in.get("id", "unknown"))
            summary = _in.get("summary", _in.get("description", ""))
            learnings = _in.get("learnings", None)
        cg = get_closure()
        result = cg.close(item_id, summary, learnings=learnings)
        print(json.dumps(result, ensure_ascii=False, indent=2))

    elif mode == "closure_status":
        """止观门：查看封存状态"""
        cg = get_closure()
        result = cg.get_status()
        print(json.dumps(result, ensure_ascii=False, indent=2, default=str))

    elif mode == "evidence_status":
        """去伪存真：查看证据库状态"""
        try:
            from evo.main import get_vault
            v = get_vault()
            result = v.get_stats()
        except Exception as e:
            result = {"error": str(e), "principle": "去伪存真·证据库"}
        print(json.dumps(result, ensure_ascii=False, indent=2, default=str))

    elif mode == "evidence_trail":
        """去伪存真：查看最近证据链"""
        try:
            from evo.main import get_vault
            v = get_vault()
            result = {"principle": "去伪存真·证据链", "recent": v.get_recent(15)}
        except Exception as e:
            result = {"error": str(e)}
        print(json.dumps(result, ensure_ascii=False, indent=2, default=str))

    elif mode == "generalize":

        """举一反三：从单条或所有规则推导跨场景候选规则"""

        rule_id = sys.argv[2] if len(sys.argv) > 2 else None

        result = generalize_rule(rule_id)

        print(json.dumps(result, ensure_ascii=False, indent=2, default=str))



    elif mode == "verify_output":
        """去伪存真·实质验证: python call_diegin.py verify_output "<输出文本>" """
        from evo.claim_checker import get_checker
        _text = sys.argv[2] if len(sys.argv) > 2 else sys.stdin.read().strip()
        print(json.dumps(get_checker().verify_output(_text), ensure_ascii=False, indent=2))

    elif mode == "principle_health":
        """P2 八原则健康看板"""
        from evo.main import principle_health
        print(json.dumps(principle_health(), ensure_ascii=False, indent=2, default=str))

    elif mode == "verify_fix":
        """①改毕验：确认修复结果
        用法: python call_diegin.py verify_fix <error_type> <success=true|false> [detail]
        success=true → 修复成功，经验固化到攻七模式库
        """
        error_type = sys.argv[2] if len(sys.argv) > 2 else ""
        success = (sys.argv[3] if len(sys.argv) > 3 else "true").lower() in ("true", "1", "yes")
        detail = sys.argv[4] if len(sys.argv) > 4 else ""
        result = _get_tracker().verify_fix(error_type, success, detail)
        print(json.dumps(result, ensure_ascii=False, indent=2, default=str))

    elif mode == "sandwich_legacy":

        """守三攻七复盘（旧版无钩子）：python call_diegin.py sandwich_legacy <task_type> '<pos_json>' '<neg_json>'"""

        task_type = sys.argv[2] if len(sys.argv) > 2 else "general"

        positive = json.loads(sys.argv[3]) if len(sys.argv) > 3 else []

        negative = json.loads(sys.argv[4]) if len(sys.argv) > 4 else []

        result = auto_sandwich(positive, negative, task_type)

        print(json.dumps(result, ensure_ascii=False, indent=2))



    elif mode == "dgen_check":

        """全量预检：检索+仲裁+归档到MemPalace（一次性完整调用）"""

        ctx = json.loads(sys.argv[2]) if len(sys.argv) > 2 else {}

        result = pre_check(ctx)

        print(json.dumps(result, ensure_ascii=False, indent=2))



    elif mode == "activate":

        """

        统一接入入口：任何对话中执行此命令实现迭进接入。

        效果：加载规则库   健康检查   输出接入摘要

        """

        from evo.main import self_check

        from datetime import datetime

        

        # 加载并自检

        check_ok = self_check()

        import io

        _old_stdout, sys.stdout = sys.stdout, io.StringIO()

        health = system_health()

        sys.stdout = _old_stdout

        

        # 组装接入报告

        report = {

            "status": "activated" if check_ok else "failed",

            "activated_at": datetime.now().isoformat(),

            "engine": "迭进-diegin",

            "interception_rules": health.get("interception_rules", 0),

            "success_patterns": health.get("success_patterns", 0),

            "meta_experiences": health.get("meta_experiences", 0),

            "precedents": health.get("precedents", 0),

            "health_summary": health,

            "note": "迭进已就绪。使用规则: 守三攻七+一二不过三+三态反馈"

        }

        print(json.dumps(report, ensure_ascii=False, indent=2, default=str))
    elif mode == "analyze":
        """Analyze tool execution result and record strikes (post-tool analysis)"""
        if len(sys.argv) > 2:
            ctx = json.loads(sys.argv[2])
        else:
            _b = sys.stdin.buffer.read()
            _b = _b[3:] if _b.startswith(b"\xef\xbb\xbf") else _b
            ctx = json.loads(_b.decode("utf-8", errors="replace").strip() or "{}")
        tool_name = ctx.get("tool_name", ctx.get("tool", ""))
        exit_code = ctx.get("exit_code", ctx.get("exit", 0))
        cmd = ctx.get("cmd", ctx.get("command", ""))
        error_out = ctx.get("error", ctx.get("stderr", ctx.get("err", "")))
        stdout_out = ctx.get("stdout", ctx.get("out", ""))

        if tool_name in ("Bash", "PowerShell", "Shell", "cmd"):
            op = "cmd"
        elif "git" in tool_name.lower() or "git" in cmd.lower():
            op = "git_push"
        elif tool_name in ("FileWrite", "file_write", "write"):
            op = "file_write"
        else:
            op = "cmd"

        if exit_code == 0 and not error_out:
            result = {"action": "skip", "reason": "no error"}
            print(json.dumps(result, ensure_ascii=False, indent=2, default=str))
        else:
            detect_ctx = {
                "op": op, "cmd": cmd, "exit": exit_code,
                "out": stdout_out, "err": error_out,
                "dur": ctx.get("dur", ctx.get("duration", 0)),
                "path": ctx.get("path", ctx.get("file", "")),
            }
            detector = ErrorDetector()  # Uses singleton tracker
            result = detector.detect_and_record(detect_ctx)
            print(json.dumps(result or {}, ensure_ascii=False, indent=2, default=str))

    elif mode == "record_error":
        """Record a self-detected error for one-two-no-three tracking"""
        if len(sys.argv) > 2:
            ctx = json.loads(sys.argv[2])
        else:
            _b = sys.stdin.buffer.read()
            _b = _b[3:] if _b.startswith(b"\xef\xbb\xbf") else _b
            ctx = json.loads(_b.decode("utf-8", errors="replace").strip() or "{}")
        error_type = ctx.get("error_type", ctx.get("type", "unknown"))
        detail = ctx.get("detail", ctx.get("error", ""))
        severity = ctx.get("severity", "high")
        result = ensure_three_strikes(error_type, detail, severity)
        print(json.dumps(result or {}, ensure_ascii=False, indent=2, default=str))

    elif mode == "generate_fix":
        if len(sys.argv) > 2:
            ctx = json.loads(sys.argv[2])
        else:
            _b = sys.stdin.buffer.read()
            _b = _b[3:] if _b.startswith(b"\xef\xbb\xbf") else _b
            ctx = json.loads(_b.decode("utf-8", errors="replace").strip() or "{}")
        error_type = ctx.get("error_type", ctx.get("type", ctx.get("detected_type", "unknown")))
        detail = ctx.get("detail", ctx.get("error", ""))
        severity = ctx.get("severity", "high")
        cmd = ctx.get("cmd", ctx.get("command", ""))
        tool_name = ctx.get("tool_name", ctx.get("tool", ""))

        strike_result = ensure_three_strikes(error_type, detail, severity)

        fix_suggestion = {}
        fix_suggestion["error_type"] = error_type
        fix_suggestion["detail"] = detail
        fix_suggestion["severity"] = severity
        fix_suggestion["strike_action"] = strike_result.get("action", "recorded")
        fix_suggestion["fix_available"] = False

        if "encoding" in error_type.lower() or "encode" in detail.lower():
            fix_suggestion["fix_available"] = True
            fix_suggestion["fix_type"] = "encoding"
            fix_suggestion["fix_instruction"] = ('在文件写入操作中显式指定 encoding="utf-8" 参数, '
                                                  "避免系统默认编码导致的 UnicodeEncodeError")
            fix_suggestion["verify_steps"] = ["检查 exit_code=0", "检查输出无乱码"]

        elif "command" in error_type.lower() or "syntax" in detail.lower():
            fix_suggestion["fix_available"] = True
            fix_suggestion["fix_type"] = "command_syntax"
            if cmd:
                fix_suggestion["fix_instruction"] = "命令语法可能存在问题: " + cmd[:100]
            else:
                fix_suggestion["fix_instruction"] = "检查命令语法、参数路径、环境依赖是否正确"
            fix_suggestion["verify_steps"] = ["检查 exit_code=0", "验证输出符合预期"]

        elif "timeout" in error_type.lower() or "timeout" in detail.lower():
            fix_suggestion["fix_available"] = True
            fix_suggestion["fix_type"] = "timeout"
            fix_suggestion["fix_instruction"] = "操作超时，建议增加超时时间、分步骤执行或改用异步方式"
            fix_suggestion["verify_steps"] = ["重新执行并检查是否完成"]

        elif "git" in error_type.lower() or "git" in tool_name.lower():
            fix_suggestion["fix_available"] = True
            fix_suggestion["fix_type"] = "git"
            fix_suggestion["fix_instruction"] = "Git操作失败，建议检查网络连接、认证信息、远程仓库状态"
            fix_suggestion["verify_steps"] = ["检查 git remote -v", "检查认证状态", "重新尝试"]

        else:
            fix_suggestion["fix_instruction"] = "检测到错误: " + detail[:100] + "，建议检查操作参数和环境配置"
            fix_suggestion["verify_steps"] = ["分析错误日志", "修正参数后重试"]

        output = {
            "fix": fix_suggestion,
            "strike": strike_result,
            "principle": "一二不过三·立改",
            "note": "fix_instruction 包含建议的修复操作，执行后请调用 verify_fix 验证"
        }
        print(json.dumps(output, ensure_ascii=False, indent=2, default=str))

    elif mode == "verify_fix":
        if len(sys.argv) > 2:
            ctx = json.loads(sys.argv[2])
        else:
            _b = sys.stdin.buffer.read()
            _b = _b[3:] if _b.startswith(b"\xef\xbb\xbf") else _b
            ctx = json.loads(_b.decode("utf-8", errors="replace").strip() or "{}")
        error_type = ctx.get("error_type", "unknown")
        fix_exit_code = ctx.get("exit_code", ctx.get("exit", -1))
        fix_error = ctx.get("error", ctx.get("err", ""))

        verified = fix_exit_code == 0 and not fix_error
        result = {
            "error_type": error_type,
            "verified": verified,
            "exit_code": fix_exit_code,
            "detail": "修复验证通过" if verified else "修复验证失败: exit=" + str(fix_exit_code),
            "principle": "一二不过三·改毕验",
        }

        if verified:
            result["reset_strike"] = True
            result["success_pattern_eligible"] = True
            result["next_step"] = "修复成功，可纳入攻七成功模式"
        else:
            result["reset_strike"] = False
            result["next_step"] = "修复失败，请检查 fix_instruction 后重试，或进入第2次阻断流程"

        print(json.dumps(result, ensure_ascii=False, indent=2, default=str))
    elif mode == "deep_review":
        """守三·深度复盘：系统性回顾strike日志并生成改进建议"""
        import json as _j, os as _o
        import datetime as _dt

        strikes_path = _o.path.join(_o.path.dirname(_o.path.dirname(__file__)), "var", "state", "strikes_db.json")
        overrides_path = _o.path.join(_o.path.dirname(_o.path.dirname(__file__)), "var", "state", "dgen_overrides.json")

        strikes = {}
        if _o.path.exists(strikes_path):
            with open(strikes_path, "r", encoding="utf-8") as f:
                strikes = _j.load(f)

        overrides = []
        if _o.path.exists(overrides_path):
            with open(overrides_path, "r", encoding="utf-8") as f:
                overrides = _j.load(f)

        # 分析
        total_errors = len(strikes)
        total_strikes = sum(e.get("count", 0) for e in strikes.values())
        high_severity = sum(1 for e in strikes.values() if e.get("severity", "") in ("high", "critical"))
        blocked = len(overrides)

        # 按错误频率排序
        sorted_errors = sorted(strikes.items(), key=lambda x: -x[1].get("count", 0))

        # 生成改进建议
        suggestions = []
        for error_type, entry in sorted_errors:
            count = entry.get("count", 0)
            sev = entry.get("severity", "medium")
            if count >= 3:
                suggestions.append(f"[P0] {error_type}: 已触发{count}次(严重度:{sev})，建议: 推翻现有阻断方案，升级处理")
            elif count >= 2:
                suggestions.append(f"[P1] {error_type}: 已触发{count}次(严重度:{sev})，建议: 阻断已生效，持续监控")
            elif count >= 1:
                suggestions.append(f"[P2] {error_type}: 已触发{count}次(严重度:{sev})，建议: 保持警觉")

        # 未阻断的高频错误
        unblocked = []
        for error_type, entry in sorted_errors:
            count = entry.get("count", 0)
            if count >= 2:
                already_blocked = any(
                    o.get("blocked_error_type") == error_type for o in overrides
                )
                if not already_blocked:
                    unblocked.append(error_type)

        report = {
            "generated_at": _dt.datetime.now().isoformat(),
            "principle": "守三·深度复盘",
            "statistics": {
                "total_error_types": total_errors,
                "total_strikes": total_strikes,
                "high_severity_count": high_severity,
                "blocked_count": blocked,
                "unblocked_high_count": len(unblocked),
            },
            "error_ranking": [
                {"error_type": et, "count": e.get("count", 0), "severity": e.get("severity", "medium")}
                for et, e in sorted_errors[:10]
            ],
            "suggestions": suggestions,
            "unblocked_high_risk": unblocked,
            "next_step": "建议执行 deep_review_apply 应用本次复盘结果" if unblocked else "系统状态良好"
        }

        print(_j.dumps(report, ensure_ascii=False, indent=2, default=str))

    elif mode == "deep_review_apply":
        """守三·深度复盘：执行复盘结果——自动补全未阻断的高频错误"""
        import json as _j2, os as _o2

        strikes_path = _o2.path.join(_o2.path.dirname(_o2.path.dirname(__file__)), "var", "state", "strikes_db.json")
        overrides_path = _o2.path.join(_o2.path.dirname(_o2.path.dirname(__file__)), "var", "state", "dgen_overrides.json")
        legacy_path = _o2.path.join(_o2.path.dirname(_o2.path.dirname(__file__)), "var", "state", "dgen_override.json")

        strikes = {}
        if _o2.path.exists(strikes_path):
            with open(strikes_path, "r", encoding="utf-8") as f:
                strikes = _j2.load(f)

        overrides = []
        if _o2.path.exists(overrides_path):
            with open(overrides_path, "r", encoding="utf-8") as f:
                overrides = _j2.load(f)

        # 为所有count>=2但未阻断的错误新建阻断
        new_blocks = []
        for error_type, entry in strikes.items():
            count = entry.get("count", 0)
            if count >= 2:
                already_blocked = any(
                    o.get("blocked_error_type") == error_type for o in overrides
                )
                if not already_blocked:
                    new_entry = {
                        "blocked_error_type": error_type,
                        "strike_count": count,
                        "blocked_at": entry.get("last_seen", ""),
                        "last_detail": entry.get("last_detail", ""),
                        "cause": {"verdict": "internal", "reason": "守三·深度复盘自动补全"},
                        "escalated": True if count >= 3 else False,
                        "reason": f"守三·深度复盘: {error_type} 已触发{count}次，自动创建阻断"
                    }
                    overrides.append(new_entry)
                    new_blocks.append(error_type)

        if new_blocks:
            with open(overrides_path, "w", encoding="utf-8") as f:
                _j2.dump(overrides, f, ensure_ascii=False, indent=2)
            # 同步 legacy
            if overrides:
                legacy = overrides[0]
                for o in overrides:
                    if o.get("escalated"):
                        legacy = o
                        break
                with open(legacy_path, "w", encoding="utf-8") as f:
                    _j2.dump(legacy, f, ensure_ascii=False, indent=2)

        result = {
            "principle": "守三·深度复盘-应用",
            "new_blocks_created": len(new_blocks),
            "blocked_types": new_blocks,
            "total_overrides": len(overrides),
        }
        print(_j2.dumps(result, ensure_ascii=False, indent=2, default=str))

    elif mode == "audit":

        """迭进标准审核：一键执行全部检查
        用法: python call_diegin.py audit
        输出: 守三/攻七/一二不过三/举一反三/去伪存真 全维度状态
        """
        import os as _oa, json as _ja, datetime as _da
        _base = _oa.path.dirname(_oa.path.dirname(__file__))

        _s = lambda x: chr(0x2705) if x else chr(0x274C)
        _w = lambda x: chr(0x26A0) + " " + x if x else ""

        print("=" * 56)
        print("  迭进 (Diegin) 标准审核报告")
        print("  " + _da.datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
        print("=" * 56)

        # ── 1. 守三：规则库 ──
        _rf = _oa.path.join(_base, "engine", "evo", "rules", "interception_rules.json")
        _rules = []
        if _oa.path.exists(_rf):
            with open(_rf, "r", encoding="utf-8") as _f:
                _rules = _ja.load(_f)
        _total = len(_rules)
        _active = sum(1 for r in _rules if r.get("lifecycle_status") == "active")
        _critical = sum(1 for r in _rules if r.get("severity") == "critical" and r.get("lifecycle_status") == "active")
        _staging = sum(1 for r in _rules if r.get("lifecycle_status") == "staging")
        _deprecating = sum(1 for r in _rules if r.get("lifecycle_status") == "deprecating")
        _alerting = sum(1 for r in _rules if r.get("lifecycle_status") == "alerting")
        _blocking = sum(1 for r in _rules if r.get("lifecycle_status") == "blocking")
        print(f"\n{_s(_active > 0)} 守三（拦截规则）")
        print(f"    活跃: {_active} | critical: {_critical} | staging: {_staging}")
        print(f"    降权: {_deprecating} | 告警: {_alerting} | 阻断: {_blocking} | 总计: {_total}")

        # ── 2. 攻七：成功模式 ──
        _sf = _oa.path.join(_base, "var", "state", "success_patterns.json")
        if not _oa.path.exists(_sf):
            _sf = _oa.path.join(_base, "engine", "evo", "rules", "success_patterns.json")
        _patterns = []
        if _oa.path.exists(_sf):
            with open(_sf, "r", encoding="utf-8") as _f:
                _patterns = _ja.load(_f)
        _pat_auto = sum(1 for p in _patterns if isinstance(p, dict) and p.get('source') == 'auto_detect')
        _pat_active = sum(1 for p in _patterns if isinstance(p, dict) and p.get('lifecycle_status') == 'active')
        print(f"\n{_s(len(_patterns) > 0)} 攻七（成功模式）")
        print(f"    总数: {len(_patterns)} | 活跃: {_pat_active} | 自动: {_pat_auto}")

        # ── 3. 一二不过三：错误追踪 ──
        _stf = _oa.path.join(_base, "var", "state", "strikes_db.json")
        _strikes = {}
        if _oa.path.exists(_stf):
            with open(_stf, "r", encoding="utf-8") as _f:
                _strikes = _ja.load(_f)
        print(f"\n{_s(len(_strikes) == 0)} 一二不过三（错误追踪）")
        if _strikes:
            _high_risk = {k: v for k, v in _strikes.items() if v.get("count", 0) >= 3}
            _warn = {k: v for k, v in _strikes.items() if v.get("count", 0) == 2}
            _ok = {k: v for k, v in _strikes.items() if v.get("count", 0) == 1}
            if _high_risk:
                for k, v in _high_risk.items():
                    print(f"    {chr(0x274C)} {k}: {v['count']}次 {_w('已达阈值')}")
            if _warn:
                for k, v in _warn.items():
                    print(f"    {chr(0x26A0)} {k}: {v['count']}次（下一次将触发阻断）")
            if _ok:
                for k, v in _ok.items():
                    print(f"    {chr(0x1F514)} {k}: {v['count']}次")
        else:
            print(f"    {chr(0x2705)} 无错误记录")

        # breach 日志
        _blf = _oa.path.join(_base, "var", "state", "dgen_breach_log.json")
        if _oa.path.exists(_blf):
            with open(_blf, "r", encoding="utf-8") as _f:
                _breach = _ja.load(_f)
            if _breach:
                print(f"    {chr(0x26A0)} Breach 记录: {len(_breach)} 条")
                for _b in _breach[-3:]:
                    print(f"      {_b.get('error_type','?')} (strike={_b.get('strike','?')})")

        # 阻断文件
        _ovf = _oa.path.join(_base, "var", "state", "dgen_override.json")
        if _oa.path.exists(_ovf):
            with open(_ovf, "r", encoding="utf-8") as _f:
                _ov = _ja.load(_f)
            if _ov.get("blocked_error_type"):
                print(f"    {chr(0x26A0)} 当前阻断: {_ov['blocked_error_type']} ({_ov.get('strike_count',0)}次)")

        # ── 4. 举一反三 ──
        _xdomain = sum(1 for r in _rules if "xdomain_" in r.get("id", "") and r.get("lifecycle_status") == "active")
        _pat_rules = sum(1 for r in _rules if "pat_rule_" in r.get("id", "") and r.get("lifecycle_status") == "active")
        print(f"\n{_s(_xdomain > 0 or _staging > 0)} 举一反三（泛化）")
        print(f"    跨域规则: {_xdomain} | 模式派生规则: {_pat_rules} | staging: {_staging}")

        # ── 5. 引擎健康度 ──
        print(f"\n--- 引擎健康度 ---")
        try:
            from evo.main import _get_engine
            _eng = _get_engine()
            _all_r = _eng.get_interceptions(active_only=False)
            _all_p = _eng.get_patterns(active_only=False)
            print(f"    规则: {len(_all_r)} | 模式: {len(_all_p)}")
        except Exception as _ee:
            print(f"    引擎加载失败: {_ee}")

        # ── 6. 去伪存真 ──
        _etf = _oa.path.join(_base, "var", "state", "evidence_trail.json")
        _trail = []
        if _oa.path.exists(_etf):
            with open(_etf, "r", encoding="utf-8") as _f:
                _trail = _ja.load(_f)
        print(f"\n{_s(len(_trail) > 0)} 去伪存真（证据链）")
        print(f"    裁决记录: {len(_trail)} 条")
        if _trail:
            _recent = _trail[-5:]
            for _e in _recent:
                print(f"    {_e.get('ts','?')[:16]} | {_e.get('verdict','?'):8s} | {_e.get('reason','')[:50]}")

        # ── 7. 缓急律 ──
        print(f"\n--- 缓急律（节奏门）---")
        try:
            from evo.main import get_pacemaker
            _pm = get_pacemaker()
            _ps = _pm.get_status()
            print(f"    宕机时段: {_ps.get('downtime',{}).get('start','?')}-{_ps.get('downtime',{}).get('end','?')}")
            print(f"    当前{'在' if _ps.get('downtime',{}).get('active_now') else '不在'}宕机时段")
        except Exception:
            print(f"    未加载")

        # ── 8. 止观门 ──
        print(f"\n--- 止观门（完形律）---")
        try:
            from evo.main import get_closure
            _cg = get_closure()
            _cs = _cg.get_status()
            print(f"    已封存: {_cs.get('closed_items',0)} 项 | 进行中: {_cs.get('open_items',0)} 项")
        except Exception:
            print(f"    未加载")

        # ── 9. 会话阶段 ──
        _psf = _oa.path.join(_base, "var", "state", "phase_state.json")
        if _oa.path.exists(_psf):
            with open(_psf, "r", encoding="utf-8") as _f:
                _phase = _ja.load(_f)
            _phases = _phase.get("phases", {})
            print(f"\n--- 会话阶段 ---")
            for _pn, _ps2 in _phases.items():
                _st = _ps2.get("status", "?")
                _ts = _ps2.get("ts", "")[:19] if _ps2.get("ts") else ""
                _icon = chr(0x2705) if _st == "passed" or _st == "completed" else chr(0x26A0) if "block" in str(_st) else chr(0x1F7E1)
                print(f"    {_icon} {_pn}: {_st} ({_ts})")

        # ── 10. Mindol 记忆 ──
        _mdb = _oa.path.join(_oa.environ.get("CODEX_HOME", _oa.path.expanduser("~/.codex")), "mindol", "memory.db")
        print(f"\n--- Mindol 语义记忆 ---")
        if _oa.path.exists(_mdb):
            _mb = _oa.path.getsize(_mdb)
            print(f"    记忆库: {_mb / 1024:.0f} KB")
        else:
            print(f"    未找到记忆库")
        try:
            _mp = _oa.path.join(_base, "engine", "mindol_bridge.py")
            if _oa.path.exists(_mp):
                import subprocess as _sb
                _mr = _sb.run([sys.executable, _mp, "stats"], capture_output=True, text=True, timeout=5)
                if _mr.stdout.strip():
                    print(f"    空间: {_mr.stdout.strip()}")
        except Exception:
            pass

        # ── 总结 ──
        _issues = []
        if _high_risk:
            _issues.append(f"{len(_high_risk)} 个错误类型已达阈值")
        if _alerting > 0:
            _issues.append(f"{_alerting} 条告警规则")
        if _blocking > 0:
            _issues.append(f"{_blocking} 条阻断规则")
        if _breach:
            _issues.append(f"{len(_breach)} 条 breach 记录")
        print(f"\n{'=' * 56}")
        if _issues:
            print(f"  {chr(0x26A0)} 发现 {len(_issues)} 个问题:")
            for _iss in _issues:
                print(f"    - {_iss}")
        else:
            print(f"  {chr(0x2705)} 系统健康，无异常")
        print(f"{'=' * 56}")