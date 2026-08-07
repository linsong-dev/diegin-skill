# -*- coding: utf-8 -*-
"""迭进引擎自检脚本（防复发机制 P0）
检查: 1) Mindol 可加载  2) 双存储一致性  3) 无恒真规则  4) 关键规则存在  5) 会话无图片残留
输出: JSON 结果 + 追加审计日志。异常写 WARN/ERROR 标记（不再静默）。
"""
import io, sys, json, os, re, datetime, glob, traceback

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
ENGINE_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, ENGINE_DIR)

AUDIT_LOG = os.path.join(os.path.dirname(ENGINE_DIR), "var", "logs", "diegin_audit.log")
STATE_DIR = os.path.join(os.path.dirname(ENGINE_DIR), "var", "state")
RESULT_FILE = os.path.join(STATE_DIR, "diegin_self_check.json")

def log(msg):
    ts = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]
    line = f"{ts} [SELF-CHECK] {msg}\n"
    try:
        os.makedirs(os.path.dirname(AUDIT_LOG), exist_ok=True)
        with io.open(AUDIT_LOG, "r", encoding="utf-8", errors="replace") as f:
            old = f.read()
        with io.open(AUDIT_LOG, "w", encoding="utf-8") as f:
            f.write(line + old)
    except Exception as e:
        print(f"SELF-CHECK log fail: {e}", file=sys.stderr)

def main():
    result = {
        "ts": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        "checks": {},
        "status": "ok",
        "issues": [],
    }
    # 1) Mindol 可加载
    try:
        from evo.rule_engine import RuleEngine
        engine = RuleEngine()
        m = engine._mindol
        mindol_ok = m is not None
        result["checks"]["mindol_loadable"] = mindol_ok
        if not mindol_ok:
            result["issues"].append("Mindol 不可加载（_mindol is None）")
        else:
            space = m.get_space(m.SPACE_RULE)
            mid_count = len(space.memory_units)
            result["mindol_rule_units"] = mid_count
    except Exception as e:
        result["checks"]["mindol_loadable"] = False
        result["issues"].append(f"Mindol 加载异常: {e}")
        mindol_ok = False
        mid_count = 0
        engine = None

    # 2) 双存储一致性
    try:
        rj = os.path.join(ENGINE_DIR, "evo", "rules", "interception_rules.json")
        with io.open(rj, "r", encoding="utf-8") as f:
            jrules = json.load(f)
        rja = os.path.join(ENGINE_DIR, "evo", "rules", "interception_rules_archive.json")
        if os.path.exists(rja):
            with io.open(rja, "r", encoding="utf-8") as f:
                jrules = jrules + json.load(f)
        jid_set = {r.get("id") for r in jrules}
        mids = set()
        if engine is not None and engine._mindol is not None:
            for u in engine._mindol.get_space(engine._mindol.SPACE_RULE).memory_units:
                try:
                    d = json.loads(u.text)
                    mids.add(d.get("id"))
                except Exception:
                    pass
        consistent = (jid_set == mids) and len(jid_set) > 0
        result["checks"]["dual_store_consistent"] = consistent
        result["json_rules"] = len(jid_set)
        result["mindol_rules"] = len(mids)
        if not consistent:
            result["issues"].append(f"双存储不一致: JSON={len(jid_set)} Mindol={len(mids)} onlyJSON={len(jid_set-mids)} onlyMindol={len(mids-jid_set)}")
    except Exception as e:
        result["checks"]["dual_store_consistent"] = False
        result["issues"].append(f"双存储检查异常: {e}")

    # 3) 无恒真规则（逻辑运算符+裸词）
    try:
        bad = []
        if engine is not None:
            for r in engine.get_interceptions(active_only=True):
                t = r.trigger_condition or ""
                if not re.search(r"\b(and|or|AND|OR)\b", t):
                    continue
                for part in re.split(r"\b(?:and|or|AND|OR)\b", t):
                    part = part.strip().strip("()")
                    if re.match(r"^[A-Za-z_][A-Za-z0-9_]*$", part):
                        bad.append((r.id, t))
        result["checks"]["no_bareword_true_rules"] = len(bad) == 0
        result["bareword_true_rules"] = [b[0] for b in bad]
        if bad:
            result["issues"].append(f"发现恒真规则 {len(bad)} 条: {[b[0] for b in bad]}")
    except Exception as e:
        result["checks"]["no_bareword_true_rules"] = False
        result["issues"].append(f"恒真规则检查异常: {e}")

    # 4) 关键规则存在
    try:
        key_rules = ["rule_session_image_protection", "rule_marker_tool_block", "rule_clean_verify_layered"]
        if engine is None:
            engine = RuleEngine()
        ids = {r.id for r in engine.get_interceptions(active_only=False)}
        missing = [k for k in key_rules if k not in ids]
        result["checks"]["key_rules_present"] = len(missing) == 0
        result["missing_key_rules"] = missing
        if missing:
            result["issues"].append(f"缺失关键规则: {missing}")
    except Exception as e:
        result["checks"]["key_rules_present"] = False
        result["issues"].append(f"关键规则检查异常: {e}")

    # 5) 会话无图片残留
    try:
        home = os.environ.get("CODEX_HOME", "")
        sess_root = os.path.join(home, "sessions") if home else ""
        img_files = []
        if sess_root and os.path.isdir(sess_root):
            for f in glob.glob(os.path.join(sess_root, "**", "*.jsonl"), recursive=True):
                b = os.path.basename(f)
                if ".bak" in b or ".patched" in b or "snapshot" in b:
                    continue
                try:
                    with io.open(f, "r", encoding="utf-8", errors="replace") as fh:
                        d = fh.read()
                    if '"input_image"' in d or '"image_url"' in d:
                        img_files.append(b)
                except Exception:
                    pass
        result["checks"]["no_image_residue"] = len(img_files) == 0
        result["image_residue_files"] = img_files
        if img_files:
            result["issues"].append(f"会话图片残留 {len(img_files)} 个: {img_files}")
    except Exception as e:
        result["checks"]["no_image_residue"] = False
        result["issues"].append(f"图片残留检查异常: {e}")

    # 6) domain_rules 无恒真陷阱
    try:
        domain_dir = os.path.join(ENGINE_DIR, "evo", "rules", "domain_rules")
        bad_dom = []
        archived_dom = []
        if os.path.isdir(domain_dir):
            for fn in sorted(os.listdir(domain_dir)):
                if not fn.endswith(".json"):
                    continue
                fp = os.path.join(domain_dir, fn)
                try:
                    with io.open(fp, "r", encoding="utf-8") as f:
                        dr = json.load(f)
                except Exception:
                    continue
                items = dr if isinstance(dr, list) else [dr]
                for it in items:
                    tc = str(it.get("trigger_condition", "") or "")
                    st = str(it.get("lifecycle_status", "") or "")
                    if st == "archived" or it.get("deprecated"):
                        archived_dom.append(fn)
                    if tc.strip().lower() in ("true", "1"):
                        bad_dom.append((fn, it.get("id", "?"), tc))
                    elif re.search(r"\b(and|or)\b", tc, re.I):
                        for part in re.split(r"\b(?:and|or)\b", tc):
                            part = part.strip().strip("()")
                            if re.match(r"^[A-Za-z_][A-Za-z0-9_]*$", part):
                                bad_dom.append((fn, it.get("id", "?"), tc))
                                break
        result["checks"]["no_domain_bareword_true"] = len(bad_dom) == 0
        result["domain_archived_files"] = archived_dom
        result["domain_bareword_true_rules"] = bad_dom
        if bad_dom:
            result["issues"].append("domain_rules 恒真陷阱 %d 条: %s" % (len(bad_dom), bad_dom))
    except Exception as e:
        result["checks"]["no_domain_bareword_true"] = False
        result["issues"].append("domain_rules 扫描异常: %s" % e)


    # 7) 钩子 ps1 编码铁律（防再生：PS5.1 无 BOM 按 GBK 解析中文乱码）
    try:
        hook_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "hooks")
        hook_files = ["diegin_pre_tool.ps1", "diegin_pre_reply.ps1", "diegin_post_tool.ps1",
                      "diegin_session_start.ps1", "diegin_stop.ps1"]
        bad_bom = []
        for hf in hook_files:
            hp = os.path.join(hook_dir, hf)
            if not os.path.exists(hp):
                bad_bom.append(hf + "(missing)")
                continue
            with open(hp, "rb") as h:
                head = h.read(3)
            if head != b"\xef\xbb\xbf":
                bad_bom.append(hf)
        result["checks"]["hooks_ps1_bom"] = len(bad_bom) == 0
        if bad_bom:
            result["issues"].append("ps1 缺 UTF-8 BOM: %s" % ", ".join(bad_bom))
    except Exception as e:
        result["checks"]["hooks_ps1_bom"] = False
        result["issues"].append("ps1 BOM 检查异常: %s" % e)

    # 8) 状态目录 tmp 残留（防再生：原子写异常终止残留）
    try:
        tmp_left = [n for n in os.listdir(STATE_DIR) if ".tmp_" in n] if os.path.isdir(STATE_DIR) else []
        result["checks"]["no_tmp_residue"] = len(tmp_left) == 0
        if tmp_left:
            result["issues"].append("状态目录存在 tmp 残留: %s" % ", ".join(tmp_left[:5]))
    except Exception as e:
        result["checks"]["no_tmp_residue"] = False
        result["issues"].append("tmp 残留检查异常: %s" % e)

    # 9) stdin 字节级去 BOM 防御（防再生：PS 管道注入 BOM 致 json.loads 崩溃）
    try:
        engine_py = os.path.join(ENGINE_DIR, "call_diegin.py")
        with io.open(engine_py, "r", encoding="utf-8") as fh2:
            esrc = fh2.read()
        has_guard = "sys.stdin.buffer.read()" in esrc and "startswith(b" in esrc
        result["checks"]["stdin_bom_guard"] = has_guard
        if not has_guard:
            result["issues"].append("call_diegin.py 缺少 stdin 字节级去 BOM 防御")
    except Exception as e:
        result["checks"]["stdin_bom_guard"] = False
        result["issues"].append("stdin BOM 防御检查异常: %s" % e)

    # 10) 死规则检测（去伪存真）：active 且创建超 7 天且从未触发 → 显性暴露
    # 说明：仅报告不置 failed，避免存量死规则每次自检触发 strike 误伤正常流程。
    try:
        rj = os.path.join(ENGINE_DIR, "evo", "rules", "interception_rules.json")
        dead = []
        with io.open(rj, "r", encoding="utf-8") as f:
            jrules = json.load(f)
        now = datetime.datetime.now(datetime.timezone.utc)
        for r in jrules:
            if r.get("lifecycle_status") != "active":
                continue
            if (r.get("triggered_count") or 0) > 0:
                continue
            ca = r.get("created_at", "")
            if not ca:
                continue
            try:
                if ca.endswith("Z"):
                    ca = ca[:-1] + "+00:00"
                dt = datetime.datetime.fromisoformat(ca)
                if dt.tzinfo is None:
                    dt = dt.replace(tzinfo=datetime.timezone.utc)
                age_days = (now - dt).total_seconds() / 86400
            except Exception:
                continue
            if age_days > 7:
                dead.append({"id": r.get("id"), "created": ca, "triggered": 0,
                             "trigger": (r.get("trigger_condition") or "")[:80]})
        result["dead_rules"] = dead
        result["dead_rule_count"] = len(dead)
        if dead:
            result["issues"].append("死规则 %d 条（active 超7天从未触发）: %s"
                                    % (len(dead), ", ".join(d["id"] for d in dead[:10])))
    except Exception as e:
        result["dead_rules"] = []
        result["dead_rule_count"] = -1
        result["issues"].append("死规则检测异常: %s" % e)

    # 11b) 攻七空壳模式检查（防再生）：decision_logic 空/无价值 → 报出
    try:
        spj = os.path.join(ENGINE_DIR, "evo", "rules", "success_patterns.json")
        with io.open(spj, "r", encoding="utf-8") as f:
            spatterns = json.load(f)
        hollow = []
        hollow_words = ("成功完成exit=0", "completedexit=0", "工具成功完成", "unknown")
        for _p in spatterns:
            if _p.get("lifecycle_status") == "archived":
                continue
            _logic = str(_p.get("decision_logic", "") or "").strip()
            _compact = _logic.replace(" ", "").replace("　", "").lower()
            _scene = str(_p.get("trigger_scenario", "") or "").strip()
            _cond = str(_p.get("trigger_condition", "") or "").strip()
            if (len(_compact) < 6) or any(_w in _compact for _w in hollow_words):
                hollow.append(_p.get("id", "?"))
            elif not _cond and not _scene:
                hollow.append(_p.get("id", "?"))
        result["hollow_pattern_count"] = len(hollow)
        result["hollow_patterns"] = hollow
        if hollow:
            result["checks"]["no_hollow_patterns"] = False
            result["issues"].append("空壳成功模式 %d 条（未归档，建议 audit_patterns 清理）: %s"
                                    % (len(hollow), ", ".join(hollow[:10])))
        else:
            result["checks"]["no_hollow_patterns"] = True
    except Exception as e:
        result["hollow_pattern_count"] = -1
        result["checks"]["no_hollow_patterns"] = False
        result["issues"].append("空壳模式检查异常: %s" % e)

    # 11c) staging 积压预警（防再生）：超14天未触发或数量超标 → 建议 audit_staging
    try:
        rj2 = os.path.join(ENGINE_DIR, "evo", "rules", "interception_rules.json")
        with io.open(rj2, "r", encoding="utf-8") as f:
            jrules2 = json.load(f)
        staging_all = [r for r in jrules2 if r.get("lifecycle_status") == "staging"]
        now2 = datetime.datetime.now(datetime.timezone.utc)
        stale_staging = []
        for r in staging_all:
            if (r.get("triggered_count") or 0) > 0:
                continue
            ca2 = r.get("created_at", "")
            if not ca2:
                continue
            try:
                if ca2.endswith("Z"):
                    ca2 = ca2[:-1] + "+00:00"
                dt2 = datetime.datetime.fromisoformat(ca2)
                if dt2.tzinfo is None:
                    dt2 = dt2.replace(tzinfo=datetime.timezone.utc)
                age_days = (now2 - dt2).total_seconds() / 86400
            except Exception:
                continue
            if age_days > 14:
                stale_staging.append({"id": r.get("id"), "age_days": round(age_days, 1)})
        result["staging_count"] = len(staging_all)
        result["stale_staging_count"] = len(stale_staging)
        result["stale_staging"] = stale_staging
        if stale_staging:
            result["checks"]["no_stale_staging"] = False
            result["issues"].append("staging 积压 %d 条（超14天未触发，建议 audit_staging 清理）: %s"
                                    % (len(stale_staging), ", ".join(s["id"] for s in stale_staging[:10])))
        else:
            result["checks"]["no_stale_staging"] = True
    except Exception as e:
        result["staging_count"] = -1
        result["stale_staging_count"] = -1
        result["checks"]["no_stale_staging"] = False
        result["issues"].append("staging 积压检查异常: %s" % e)

    # 11d) 假证据检查（防再生）：evidence_filter 来源的 pass 记录应为 0
    try:
        et_path = os.path.join(ENGINE_DIR, "var", "state", "evidence_trail.json")
        with io.open(et_path, "r", encoding="utf-8") as f:
            etrail = json.load(f)
        fake_pass = [e for e in etrail
                     if e.get("source") == "evidence_filter" and e.get("verdict") == "pass"]
        result["fake_evidence_count"] = len(fake_pass)
        if fake_pass:
            result["checks"]["no_fake_evidence"] = False
            result["issues"].append("假证据 %d 条（evidence_filter 批量 pass，建议 audit_evidence 清理）"
                                    % len(fake_pass))
        else:
            result["checks"]["no_fake_evidence"] = True
    except Exception as e:
        result["fake_evidence_count"] = -1
        result["checks"]["no_fake_evidence"] = False
        result["issues"].append("假证据检查异常: %s" % e)


    # 11) 基线对比（P4-15 L4 启动清理）：关键指标 vs 冻结基线，回归即报警
    try:
        base_file = os.path.join(STATE_DIR, "system_baseline.json")
        baseline = {}
        try:
            with io.open(base_file, "r", encoding="utf-8") as f:
                baseline = json.load(f)
        except Exception:
            baseline = {}
        regressions = []
        rj2 = os.path.join(ENGINE_DIR, "evo", "rules", "interception_rules.json")
        cur_counts = {}
        try:
            with io.open(rj2, "r", encoding="utf-8") as f:
                jr = json.load(f)
            rj2a = os.path.join(ENGINE_DIR, "evo", "rules", "interception_rules_archive.json")
            if os.path.exists(rj2a):
                with io.open(rj2a, "r", encoding="utf-8") as f:
                    jr = jr + json.load(f)
            for r in jr:
                st = r.get("lifecycle_status", "")
                cur_counts[st] = cur_counts.get(st, 0) + 1
            regen = [str(r.get("id", "")) for r in jr
                     if str(r.get("id", "")).startswith("xdomain_merged_")
                     or str(r.get("id", "")) == "pat_rule_pat_auto_auto_fix_command_failure_1"]
            if regen and baseline.get("no_regenerated_rules", True):
                regressions.append("泛化再生规则出现: %s" % ", ".join(regen[:3]))
            if baseline.get("rules_active") is not None and abs(cur_counts.get("active", 0) - baseline["rules_active"]) > baseline.get("rules_active_tol", 2):
                regressions.append("active 规则数偏离基线: cur=%d base=%d" % (cur_counts.get("active", 0), baseline["rules_active"]))
            if baseline.get("rules_total") and abs(sum(cur_counts.values()) - baseline["rules_total"]) > baseline.get("rules_total_tol", 8):
                regressions.append("规则总数偏离基线: cur=%d base=%d" % (sum(cur_counts.values()), baseline["rules_total"]))
        except Exception as e:
            regressions.append("规则库读取异常: %s" % e)
        pj = os.path.join(ENGINE_DIR, "evo", "rules", "success_patterns.json")
        try:
            with io.open(pj, "r", encoding="utf-8") as f:
                pats = json.load(f)
            empty = sum(1 for x in pats if not str(x.get("decision_logic", "") or "").strip())
            if baseline.get("empty_shell_max") is not None and empty > baseline["empty_shell_max"]:
                regressions.append("空壳模式增长: cur=%d max=%d" % (empty, baseline["empty_shell_max"]))
        except Exception as e:
            regressions.append("模式库读取异常: %s" % e)
        try:
            with io.open(os.path.join(STATE_DIR, "strikes_db.json"), "r", encoding="utf-8") as f:
                st2 = json.load(f)
            n_strikes = len(st2) if isinstance(st2, (dict, list)) else 0
            if baseline.get("strikes_max") and n_strikes > baseline["strikes_max"]:
                regressions.append("strikes 超限: cur=%d max=%d" % (n_strikes, baseline["strikes_max"]))
        except Exception:
            pass
        root = os.path.dirname(ENGINE_DIR)
        if baseline.get("dgen_rules_md_exists") and not os.path.exists(os.path.join(root, "workspace", "dgen_rules.md")):
            regressions.append("dgen_rules.md 缺失")
        if baseline.get("hooks_dual_consistent"):
            c1 = os.path.join(root, "config", "hooks.json")
            c2 = os.path.join(root, "hooks", "hooks.json")
            try:
                same = os.path.exists(c1) and os.path.exists(c2) and open(c1, "rb").read() == open(c2, "rb").read()
                if not same:
                    regressions.append("hooks.json 双源不一致")
            except Exception:
                regressions.append("hooks.json 读取异常")
        result["checks"]["baseline_no_regression"] = len(regressions) == 0
        result["baseline_counts"] = cur_counts
        result["baseline_regressions"] = regressions
        if regressions:
            result["issues"].append("基线回归 %d 项: %s" % (len(regressions), "; ".join(regressions)))
    except Exception as e:
        result["checks"]["baseline_no_regression"] = False
        result["issues"].append("基线对比异常: %s" % e)

    # 汇总
    failed = [k for k, v in result["checks"].items() if v is False]
    result["status"] = "FAIL" if failed else "ok"
    result["failed_checks"] = failed

    # 防再生 L1 规则接线：自检失败 → 一二不过三 strike（1警→2阻→3升级，封顶3）
    PREVENTION_STRIKE_MAP = {
        "hooks_ps1_bom": "hooks_ps1_bom",
        "no_tmp_residue": "atomic_tmp_residue",
        "stdin_bom_guard": "stdin_bom_guard",
    }
    for check_key, error_type in PREVENTION_STRIKE_MAP.items():
        if result["checks"].get(check_key) is False:
            try:
                from evo.main import _get_tracker
                _get_tracker().record_self_error(
                    error_type,
                    "自检失败: " + check_key,
                    task_context={"severity": "high", "auto_detected": True, "source": "self_check"},
                )
                result["issues"].append("已记一二不过三 strike: " + error_type)
            except Exception as _se:
                result["issues"].append("strike 记录失败 %s: %s" % (error_type, _se))

    # 写状态文件
    try:
        os.makedirs(STATE_DIR, exist_ok=True)
        tmp = RESULT_FILE + ".tmp"
        with io.open(tmp, "w", encoding="utf-8") as f:
            json.dump(result, f, ensure_ascii=False, indent=2)
        os.replace(tmp, RESULT_FILE)
    except Exception as e:
        result["issues"].append(f"写状态文件异常: {e}")

    log(f"status={result['status']} checks={json.dumps(result['checks'], ensure_ascii=False)} issues={len(result['issues'])}")
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result["status"] == "ok" else 1

if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception:
        traceback.print_exc()
        sys.exit(2)
