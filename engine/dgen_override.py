#!/usr/bin/env python3
"""迭进覆写入口：AI在回复前调此脚本写入覆盖裁决"""
import json, sys, os
from pathlib import Path
from datetime import datetime, timezone, timedelta

TZ = timezone(timedelta(hours=8))

def write_override(decision: str, reason: str, rule_id: str = "", matched: int = 0):
    # 确定运行时路径（优先 CODEX_HOME）
    codex_home = os.environ.get("CODEX_HOME", str(Path.home() / ".codex"))
    state_dir = Path(codex_home) / "diegin" / "var" / "state"
    state_dir.mkdir(parents=True, exist_ok=True)
    
    state = {
        "ts": datetime.now(TZ).isoformat(),
        "decision": decision,
        "reason": reason,
        "winning_rule": rule_id,
        "matched_count": matched,
        "source": "ai_override"
    }
    
    path = state_dir / "dgen_override.json"
    with open(path, "w", encoding="utf-8") as f:
        json.dump(state, f, ensure_ascii=False)
    
    print(json.dumps({"ok": True, "path": str(path), "decision": decision}, ensure_ascii=False))
    return True

if __name__ == "__main__":
    if len(sys.argv) < 3:
        print("用法: python dgen_override.py block|allow <reason> [rule_id] [matched_count]", file=sys.stderr)
        sys.exit(1)
    
    decision = sys.argv[1]
    reason = sys.argv[2]
    rule_id = sys.argv[3] if len(sys.argv) > 3 else ""
    matched = int(sys.argv[4]) if len(sys.argv) > 4 else 0
    
    write_override(decision, reason, rule_id, matched)