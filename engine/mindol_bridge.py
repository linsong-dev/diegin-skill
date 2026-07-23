#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Mindol 桥接器 - PowerShell hooks 通过此脚本写入 Mindol"""
import sys, os, json
sys.stdout.reconfigure(encoding="utf-8")

# 路径
CODEX_HOME = os.environ.get("CODEX_HOME", "")
if not CODEX_HOME:
    base = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    CODEX_HOME = base if base.endswith(".codex") else os.path.join(base, ".codex")

MINDOL_STORAGE = os.path.join(CODEX_HOME, "mindol")


def _get_mindol():
    """获取 Mindol 实例（懒加载）"""
    sys.path.insert(0, os.path.join(CODEX_HOME, "diegin", "engine"))
    from mindol import core
    m = core.Mindol(storage_path=MINDOL_STORAGE, persist=True)
    return m


def cmd_record(args):
    """记录一条上下文到 Mindol CODEX 空间
    用法: mindol_bridge.py record <source> <text> [space]
    """
    if len(args) < 2:
        print("ERROR: need source and text")
        return 1
    source = args[0]
    text = " ".join(args[1:])
    space = "codex"  # 默认
    # 检查末尾是否指定空间
    if text.endswith(")") and "(" in text:
        parts = text.rsplit("(", 1)
        sp = parts[1].rstrip(")").strip()
        if sp in ("codex", "rule", "pattern", "trade", "abstract", "state", "chat", "raw_chat", "raw_file"):
            space = sp
            text = parts[0].strip()
    
    try:
        m = _get_mindol()
        import datetime
        ts = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        uid = f"hook_{source}_{ts}"
        m.add_unit(text=text, source=f"hook_{source}", uid=uid, space=space)
        m.save()
        print(f"OK: {uid} -> {space}")
        m.close()
        return 0
    except Exception as e:
        print(f"ERROR: {e}")
        return 1


def cmd_search(args):
    """语义搜索
    用法: mindol_bridge.py search <query> [space] [top_k]
    """
    if len(args) < 1:
        print("ERROR: need query")
        return 1
    query = args[0]
    space = args[1] if len(args) > 1 else None
    top_k = int(args[2]) if len(args) > 2 else 5
    
    try:
        m = _get_mindol()
        spaces = [space] if space else None
        results = m.retrieve(query, top_k=top_k, spaces=spaces)
        out = []
        for u, s in results:
            out.append({"score": round(s, 3), "space": u.space, "text": u.text[:200]})
        print(json.dumps(out, ensure_ascii=False))
        m.close()
        return 0
    except Exception as e:
        print(f"ERROR: {e}")
        return 1


def cmd_stats(args):
    """查看 Mindol 状态"""
    try:
        m = _get_mindol()
        stats = m.space_stats()
        print(json.dumps(stats, ensure_ascii=False))
        m.close()
        return 0
    except Exception as e:
        print(f"ERROR: {e}")
        return 1


def cmd_close(args):
    """安全关闭 Mindol"""
    try:
        sys.path.insert(0, os.path.join(CODEX_HOME, "diegin", "engine"))
        from mindol import core
        m = core.Mindol(storage_path=MINDOL_STORAGE, persist=True)
        m.close()
        return 0
    except:
        return 0


def main():
    if len(sys.argv) < 2:
        print("Usage: mindol_bridge.py <record|search|stats|close> [args...]")
        sys.exit(1)
    
    command = sys.argv[1]
    args = sys.argv[2:]
    
    commands = {
        "record": cmd_record,
        "search": cmd_search,
        "stats": cmd_stats,
        "close": cmd_close,
    }
    
    handler = commands.get(command)
    if not handler:
        print(f"Unknown command: {command}")
        sys.exit(1)
    
    result = handler(args)
    sys.exit(result if result is not None else 0)


if __name__ == "__main__":
    main()