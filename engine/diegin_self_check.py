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
