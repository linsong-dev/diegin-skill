# -*- coding: utf-8 -*-
# error_detector.py - 一二不过三·第一环：错误发现与记录
# 归属原则：一二不过三（三错锁）
#   第1步：检测错误（check_file / check_cmd）
#   第2步：记录strike（recording_self_error → strikes_db）
#   第3步：触发阻断（第2次strike后 → dgen_overrides.json）
#   (注：立改+改毕验 由 P1-3 实现)
# ============================================


import os, sys, json, datetime

# 编码乱码特征
MOJIBAKE_CHARS = set(range(0x0080, 0x00A0)) | set(range(0x2000, 0x2070))

# 失败关键词
FAIL_GIT = ["connection was reset","connection reset","connection timed out",
            "could not resolve host","fatal: unable to access","recv failure",
            "could not read from remote","authentication failed"]

FAIL_CMD = ["command not found","is not recognized","access is denied",
            "permission denied","cannot find","timed out","timeout"]


def _is_probe_command(cmd: str) -> bool:
    """探测类命令判定（[P0-20260825] 误伤豁免）：
    端口/连通性/HTTP状态码/健康检查类探测失败是"探测结果"而非 AI 错误。
    例如 curl 127.0.0.1:9222（浏览器未开时 exit=1）、curl -o NUL -w "%{http_code}"（代理未开时 exit=1）、
    Test-NetConnection 连通性测试。这类失败记 strike 会污染一二不过三并误升级熔断/override。
    """
    c = (cmd or "").lower()
    if not c or not c.strip():
        return False
    probe_markers = (
        "-o nul",                    # curl 静默输出到 NUL（只看状态码/连通性）
        "%{http_code}",              # curl 仅取 HTTP 状态码
        "--connect-timeout",         # 显式连接超时探测
        "-connecttimeout",
        "test-netconnection",        # PowerShell 连通性测试
        "test-connection",
        "get-process chrome",        # 进程存在性探测（发布流程常查）
        "--version",                 # 工具版本探测（环境检查，失败=未安装而非 AI 错误）
        "-version",
        "get-command",               # 命令存在性探测
        "where.exe",
        "where ",                    # where 命令探测
    )
    if any(m in c for m in probe_markers):
        return True
    # 纯环境探测命令：仅查询工具/解释器是否存在（node/python/codex/py 等）
    env_probe = (
        "python --version", "py --version", "node --version", "node -v",
        "codex --version", "git --version", "npm --version", "python -v",
        "py -", "py -0",
    )
    if any(e in c for e in env_probe):
        return True
    # 本机/回环地址探测：curl/请求类命令指向 localhost/127.0.0.1 属服务可用性探测
    local_marks = ("127.0.0.1", "localhost", "[::1]")
    if any(m in c for m in local_marks):
        if any(k in c for k in ("curl", "invoke-webrequest", "invoke-restmethod", "test-netconnection")):
            return True
        if "http://" in c or "https://" in c:
            return True
    return False



def build_success_baseline(success_log_path=None, patterns_path=None, evidence_path=None):
    """P3-11 守三期望行为来源：从 success_log / success_patterns / evidence_trail 提取成功基线。
    返回 {key: {"source","count","expectation","confidence"}}，key=op/tool/scenario"""
    import json as _json
    from collections import Counter as _Counter
    _base = os.path.dirname(os.path.abspath(__file__))
    baseline = {}
    # 源1: success_log.json（成功操作签名：op -> 成功理由）
    _sl = success_log_path or os.path.join(_base, "..", "workspace", "success_log.json")
    try:
        with open(_sl, "r", encoding="utf-8") as _f:
            _logs = _json.load(_f)
        _op_cnt = _Counter()
        _op_notes = {}
        for _x in _logs:
            if not isinstance(_x, dict):
                continue
            _op = str(_x.get("op", "") or "")
            if not _op:
                continue
            _op_cnt[_op] += 1
            _rs = _x.get("reasons") or []
            _note = ";".join(str(r) for r in _rs[:3])
            _op_notes[_op] = _note or _op_notes.get(_op, "")
        for _op, _c in _op_cnt.items():
            baseline[_op] = {"source": "success_log", "count": _c,
                             "expectation": _op_notes.get(_op, "") or "success",
                             "confidence": min(5.0, 3.0 + _c * 0.5)}
    except Exception:
        pass
    # 源2: success_patterns.json 非空 decision_logic（期望行为=决策逻辑）
    _sp = patterns_path or os.path.join(_base, "rules", "success_patterns.json")
    try:
        with open(_sp, "r", encoding="utf-8") as _f:
            _pats = _json.load(_f)
        for _p in _pats:
            _logic = str(_p.get("decision_logic", "") or "").strip()
            if not _logic:
                continue
            _scene = str(_p.get("trigger_scenario", "") or "")
            _key = _scene if _scene else str(_p.get("pattern_name", "") or "")
            if _key:
                baseline[_key] = {"source": "pattern", "count": _p.get("triggered_count", 0) or 0,
                                  "expectation": _logic, "confidence": _p.get("confidence", 0) or 0}
    except Exception:
        pass
    # 源3: evidence_trail pass 记录（工具级已验证成功基线）
    _ev = evidence_path or os.path.join(_base, "..", "..", "var", "state", "evidence_trail.json")
    try:
        with open(_ev, "r", encoding="utf-8") as _f:
            _evs = _json.load(_f)
        _tool_cnt = _Counter()
        for _x in _evs:
            if isinstance(_x, dict) and _x.get("verdict") == "pass":
                _ctx = _x.get("context", {}) or {}
                _tool = _ctx.get("tool") or _x.get("rule_id") or ""
                if _tool and _tool not in ("r1", "r2", "test_active", "test_staging"):
                    _tool_cnt[_tool] += 1
        for _tool, _c in _tool_cnt.items():
            if _c >= 3 and _tool not in baseline:
                baseline[_tool] = {"source": "evidence", "count": _c,
                                   "expectation": "exit_0", "confidence": 5.0}
    except Exception:
        pass
    return baseline


class ErrorDetector:
    """全局操作监控器。"""
    
    def __init__(self, tracker_or_engine=None):
        self._tracker = None
        if tracker_or_engine is not None:
            # Support passing either a BehaviorTracker or a RuleEngine
            from tracker import BehaviorTracker
            if isinstance(tracker_or_engine, BehaviorTracker):
                self._tracker = tracker_or_engine
            else:
                # Assume it's a RuleEngine, create tracker from it
                self._tracker = BehaviorTracker(tracker_or_engine)
        self._log = []
    
    def _get_tracker(self):
        if self._tracker is None:
            try:
                from evo.main import _get_tracker as _gt
                self._tracker = _gt()
            except ImportError:
                try:
                    from tracker import BehaviorTracker
                    from evo.main import _get_engine as _ge
                    re = _ge()
                    self._tracker = BehaviorTracker(re)
                except ImportError:
                    return None
        return self._tracker
    
    def check_file(self, path, data):
        """检测文件编码问题。"""
        issues = []
        if data[:3] == b"\xef\xbb\xbf":
            issues.append("BOM")
        try:
            text = data.decode("utf-8")
        except UnicodeDecodeError:
            issues.append("INVALID_UTF8")
            return {"error":"encoding_write_corruption","severity":"critical",
                    "detail":"非UTF-8: " + os.path.basename(path),"checks":issues}
        repl = text.count("\ufffd")
        if repl:
            issues.append("REPLACE_" + str(repl))
        na = [c for c in text if ord(c) > 127]
        if len(na) >= 5:
            cjk = sum(1 for c in na if 0x4E00 <= ord(c) <= 0x9FFF)
            moji = sum(1 for c in na if ord(c) in MOJIBAKE_CHARS)
            if moji > 0 and cjk == 0:
                issues.append("MOJIBAKE")
        if issues:
            sev = "critical" if any("BOM" in i or "REPLACE" in i or "MOJIBAKE" in i for i in issues) else "high"
            return {"error":"encoding_write_corruption","severity":sev,
                    "detail":os.path.basename(path) + ": " + ", ".join(issues), "checks":issues}
        return None
    
    def check_cmd(self, cmd, exit_code, out, err, dur):
        """检测命令失败。"""
        combined = (out + " " + err).lower()
        if exit_code != 0:
            # [P0-20260827] CLI 输出截断警告豁免：命令输出超长被 Codex CLI 截断（Warning: truncated output / original token count）时
            # exit 可能非 0，但属输出展示问题而非命令失败（8-25 豁免仅覆盖 resp 文本检测，此处覆盖 exit 判定链路）
            if 'warning: truncated output' in combined or 'original token count' in combined:
                print('[TRUNC-SKIP] CLI 输出截断警告豁免（非命令失败）: ' + str(cmd)[:80])
                return None
            # [P0-20260825] 探测类命令豁免：端口/连通性/状态码探测失败是预期结果，不记 strike
            if _is_probe_command(cmd):
                print("[PROBE-SKIP] 探测类命令失败豁免（非 AI 错误）: " + str(cmd)[:80])
                return None
            for kw in FAIL_GIT + FAIL_CMD:
                if kw.lower() in combined:
                    etype = "git_push_failure" if kw in FAIL_GIT else "command_failure"
                    # [P0-20260826] 命令不存在/环境损坏类失败 → 归因 external（外因），不升级熔断
                    if kw.lower() in ("is not recognized", "command not found",
                                      "not recognized as a name", "access is denied",
                                      "permission denied", "cannot find", "not found"):
                        return {"error": etype, "severity": "low", "external": True,
                                "detail": "exit=" + str(exit_code) + " cmd=" + cmd[:40],
                                "matched": kw}
                    return {"error":etype,"severity":"high",
                            "detail":"exit=" + str(exit_code) + " cmd=" + cmd[:40],
                            "matched":kw}
            return {"error":"command_failure","severity":"medium",
                    "detail":"exit=" + str(exit_code) + " cmd=" + cmd[:40],"matched":""}
        if dur > 120000:
            return {"error":"command_timeout","severity":"medium",
                    "detail":"timeout=" + str(dur) + "ms cmd=" + cmd[:40],"matched":"timeout"}
        return None
    
    def _check_success_deviation(self, ctx, baseline):
        """守三·期望行为偏离：成功基线强的可靠操作突发失败 → 标记 baseline_regression + 附期望行为"""
        op = ctx.get("op", "")
        if int(ctx.get("exit", 0) or 0) == 0 or op not in ("cmd", "git_push", "file_write"):
            return None
        entry = baseline.get(op)
        if not entry:
            tool = ctx.get("tool_name", ctx.get("tool", ""))
            entry = baseline.get(tool) if tool else None
        if not entry:
            return None
        count = int(entry.get("count", 0) or 0)
        source = str(entry.get("source", "") or "")
        # 基线强度门槛：pattern 任意 / success_log>=2 / evidence>=10
        strong = (source == "pattern") or (source == "success_log" and count >= 2) or (source == "evidence" and count >= 10)
        if not strong:
            return None
        return {
            "deviation": "baseline_regression",
            "expected_behavior": str(entry.get("expectation", "") or "")[:120],
            "baseline_source": source,
            "baseline_count": count,
        }

    def detect_and_record(self, ctx, baseline=None):
        """P3-11 守三检测：失败检测 + 成功基线偏离增强（期望行为喂给守三 strike 记录）"""
        op = ctx.get("op","")
        result = None
        # 如果有 force_error，直接触发一二不过三
        force_error = ctx.get("force_error", None)
        if force_error:
            result = {
                "error": force_error,
                "severity": ctx.get("force_severity", "high"),
                "detail": ctx.get("force_detail", "")
            }
        # 正常检测（修复：移到 return 之前）
        if result is None:
            if op == "file_write":
                result = self.check_file(ctx.get("path",""), ctx.get("data",b""))
            elif op in ("cmd","git_push"):
                result = self.check_cmd(ctx.get("cmd",""), ctx.get("exit",0),
                                       ctx.get("out",""), ctx.get("err",""), ctx.get("dur",0))
                if result and op == "git_push":
                    result["error"] = "git_push_failure"
        # P3-11 成功基线偏离增强（触发前附加期望行为，喂给守三）
        if result is not None and not force_error:
            try:
                if baseline is None:
                    baseline = build_success_baseline()
                _dev = self._check_success_deviation(ctx, baseline)
                if _dev:
                    result["deviation"] = _dev["deviation"]
                    result["expected_behavior"] = _dev["expected_behavior"]
                    result["baseline_source"] = _dev["baseline_source"]
                    result["baseline_count"] = _dev["baseline_count"]
            except Exception:
                pass
        if result:
            self._trigger(result)
            self._log.append({"t":datetime.datetime.now().isoformat(),"r":result})
        # 沉默失败检测：未匹配任何规则的调用也追踪
        if result is None and op:
            self._silent_fallback(op, ctx)
        return result
    
    def _trigger(self, detection):
        tracker = self._get_tracker()
        if tracker is None:
            return
        try:
            _task_ctx = {"auto_detected": True, "severity": detection.get("severity", "")}
            # [P0-20260826] 外因标记传递：命令不存在/环境损坏类失败 → 一二不过三按外因处理，不升级
            if detection.get("external"):
                _task_ctx["external_cause"] = True
            if detection.get("expected_behavior"):
                _task_ctx["expected_behavior"] = detection.get("expected_behavior")
                _task_ctx["baseline_deviation"] = detection.get("deviation", "")
            r = tracker.record_self_error(
                error_type=detection["error"],
                detail=detection.get("detail",""),
                task_context=_task_ctx
            )
            a = r.get("action","")
            tag = ""
            if "breach" in a: tag = " (阻断机制bug!)"
            elif "block" in a: tag = " (阻断!)"
            elif "warning" in a: tag = " (警告)"
            elif "third" in a: tag = " (第3次)"
            elif "second" in a: tag = " (第2次)"
            elif "first" in a: tag = " (第1次)"
            print("[DETECT] " + detection["error"] + tag)
            
            # 一二不过三·立改: 首次错误自动修复 + 输出到攻七
            if "first" in a or "warning" in a:
                _fix = self.disarm(detection)
                if _fix.get("disarmed"):
                    try:
                        from evo.main import auto_sandwich_trigger
                        auto_sandwich_trigger(
                            "auto_fix_" + detection.get("error", "unknown"),
                            positive=["disarm:" + _fix.get("fix_action", "?")],
                            negative=[]
                        )
                        print("[DETECT] -> 攻七: " + str(_fix.get("detail", ""))[:60])
                    except Exception as _fe:
                        print("[DETECT] -> 攻七 error: " + str(_fe))
        except Exception as e:
            print("[DETECT] err: " + str(e))
    

    def disarm(self, detection: dict) -> dict:
        """一二不过三·立改: 首次错误自动修复"""
        import datetime as _dt
        error = detection.get("error", "")
        detail = detection.get("detail", "")
        path = detection.get("path", "")
        
        fix_result = {"disarmed": False, "fix_action": "", "detail": ""}
        
        # case 1: 编码写入错误 -> 重写为UTF-8 NoBOM
        if "encoding" in error and path and os.path.exists(path):
            try:
                with open(path, "rb") as f:
                    raw = f.read()
                if raw[:3] == b"\xef\xbb\xbf":
                    raw = raw[3:]
                text = raw.decode("utf-8")
                with open(path, "w", encoding="utf-8") as f:
                    f.write(text)
                fix_result["disarmed"] = True
                fix_result["fix_action"] = "rewrite_as_utf8_nobom"
                fix_result["detail"] = f"auto_fix: {os.path.basename(path)} rewritten as UTF-8 NoBOM"
                print(f"[DISARM] {fix_result['detail']}")
            except Exception as e:
                fix_result["detail"] = f"auto_fix failed: {e}"
                print(f"[DISARM] fix failed: {e}")
        
        # case 2: git推送失败 -> 检查git状态
        elif "git" in error:
            import subprocess
            try:
                result = subprocess.run(["git", "remote", "-v"], capture_output=True, text=True, timeout=10)
                if result.returncode == 0:
                    fix_result["disarmed"] = True
                    fix_result["fix_action"] = "git_remote_check"
                    fix_result["detail"] = "git remote OK, suggest retry push"
                    print("[DISARM] git状态正常，可重试推送")
            except Exception as e:
                fix_result["detail"] = f"git check failed: {e}"
        
        # case 3: 命令失败 -> 记录建议
        elif "command" in error:
            fix_result["disarmed"] = True
            fix_result["fix_action"] = "suggest_precheck"
            fix_result["detail"] = "suggest: dry-run before exec"
            print("[DISARM] 命令失败建议: dry-run预检")
        
        return fix_result

    def wrap_write(self, path, data):
        os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
        with open(path, "wb") as f:
            f.write(data)
        return self.detect_and_record({"op":"file_write","path":path,"data":data}) is not None


    def _silent_fallback(self, op, ctx):
        """沉默失败：未匹配规则的错误操作追踪（三错阀兜底）"""
        import datetime as _dt
        key = "silent_" + op
        db = self._get_tracker()._load_strikes_db() if self._get_tracker() else {}
        now = _dt.datetime.now().isoformat()
        if key not in db:
            db[key] = {"count": 0, "first_seen": now, "last_seen": now, "last_detail": "", "severity": "low"}
        db[key]["count"] += 1
        db[key]["last_seen"] = now
        db[key]["last_detail"] = ctx.get("detail", op)[:60]
        try:
            import json, os
            p = self._get_tracker()._strikes_db_path() if self._get_tracker() else ""
            if p:
                os.makedirs(os.path.dirname(p), exist_ok=True)
                with open(p, "w", encoding="utf-8") as f:
                    json.dump(db, f, ensure_ascii=False, indent=2)
        except:
            pass
        print(f"[SILENT] unmatched op={op} strikes={db[key]['count']}")
        tracker = self._get_tracker()
        if tracker and db[key]["count"] >= 3:
            try:
                tracker.record_self_error(
                    error_type="silent_" + op,
                    detail=f"沉默失败x{db[key]['count']}: {op} 未匹配任何规则",
                    task_context={"auto_detected": True, "severity": "medium"}
                )
            except:
                pass
_inst = None

def get(tracker=None):
    global _inst
    if _inst is None:
        _inst = ErrorDetector(tracker)
    return _inst
