# -*- coding: utf-8 -*-
# error_detector.py - 全局操作监控器
# 自动检测操作失败模式并触发一二不过三

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
    
    def __init__(self, tracker=None):
        self._tracker = tracker
        self._log = []
    
    def _get_tracker(self):
        if self._tracker is None:
            try:
                from tracker import BehaviorTracker
                from rule_engine import RuleEngine
                re = RuleEngine()
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
            if "third" in a: tag = " (第3次!)"
            elif "second" in a: tag = " (第2次)"
            elif "first" in a: tag = " (第1次)"
            print("[DETECT] " + detection["error"] + tag)
        except Exception as e:
            print("[DETECT] err: " + str(e))
    
    def wrap_write(self, path, data):
        os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
        with open(path, "wb") as f:
            f.write(data)
        return self.detect_and_record({"op":"file_write","path":path,"data":data}) is not None


_inst = None

def get(tracker=None):
    global _inst
    if _inst is None:
        _inst = ErrorDetector(tracker)
    return _inst
