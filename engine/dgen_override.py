# ============================================
# 迭进路DGEN 核心引擎
# 元原则框架(全域常驻不可绕过):
#   守三(负向纠错): 观不足->省其因->正其行
#   攻七(正向强化): 识长处->炼精华->固其用
#   一二不过三(三错阀): 初错立规->再错固规->三错请裁决
#   举一反三(跨域泛化): 举一->反三->通百
#   去伪存真(真伪门): 言必有证->证必可验->验证为真
# ============================================

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