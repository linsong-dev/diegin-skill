"""mindol.diegin_integration — 迭进引擎桥接（mindol ↔ diegin）"""
from __future__ import annotations
import json, os
from datetime import datetime
from typing import Any, Dict, List, Optional
from .codex_adapter import CodexMemoryAdapter

_MEMORY_ADAPTER: Optional[CodexMemoryAdapter] = None
_MEMORY_V2_AVAILABLE = True

def _get_adapter() -> CodexMemoryAdapter:
    global _MEMORY_ADAPTER
    if _MEMORY_ADAPTER is None:
        _MEMORY_ADAPTER = CodexMemoryAdapter()
    return _MEMORY_ADAPTER

def memory_search(query: str, max_results: int = 5) -> List[Dict]:
    try: return _get_adapter().search(query, top_k=max_results)
    except Exception: return []

def memory_archive(rule_id: str, decision: str, context: Dict = None) -> bool:
    try:
        content = f"[{rule_id}] {decision}"
        if context: content += f" | ctx: {json.dumps(context, ensure_ascii=False)[:200]}"
        return _get_adapter().archive(rule_id, content)
    except Exception: return False

def memory_format_context(query: str = "", top_k: int = 3) -> str:
    try:
        a = _get_adapter()
        r = a.search(query, top_k=top_k) if query else []
        return a.format_context(r)
    except Exception: return ""

def get_memory_stats() -> Dict[str, int]:
    try: return _get_adapter().stats()
    except Exception: return {}

def close_memory():
    global _MEMORY_ADAPTER
    if _MEMORY_ADAPTER: _MEMORY_ADAPTER.close(); _MEMORY_ADAPTER = None
