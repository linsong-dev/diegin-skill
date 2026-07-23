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
            for kw in FAIL_GIT + FAIL_CMD:
                if kw.lower() in combined:
                    etype = "git_push_failure" if kw in FAIL_GIT else "command_failure"
                    return {"error":etype,"severity":"high",
                            "detail":"exit=" + str(exit_code) + " cmd=" + cmd[:40],
                            "matched":kw}
            return {"error":"command_failure","severity":"medium",
                    "detail":"exit=" + str(exit_code) + " cmd=" + cmd[:40],"matched":""}
        if dur > 120000:
            return {"error":"command_timeout","severity":"medium",
                    "detail":"timeout=" + str(dur) + "ms cmd=" + cmd[:40],"matched":"timeout"}
        return None
    
    def detect_and_record(self, ctx):
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
            self._trigger(result)
        # 正常检测（修复：移到 return 之前）
        if result is None:
            if op == "file_write":
                result = self.check_file(ctx.get("path",""), ctx.get("data",b""))
            elif op in ("cmd","git_push"):
                result = self.check_cmd(ctx.get("cmd",""), ctx.get("exit",0),
                                       ctx.get("out",""), ctx.get("err",""), ctx.get("dur",0))
                if result and op == "git_push":
                    result["error"] = "git_push_failure"
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
            r = tracker.record_self_error(
                error_type=detection["error"],
                detail=detection.get("detail",""),
                task_context={"auto_detected":True,"severity":detection.get("severity","")}
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
            
            # 一二不过三·立改: 首次错误自动修复
            if "first" in a or "warning" in a:
                self.disarm(detection)
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

