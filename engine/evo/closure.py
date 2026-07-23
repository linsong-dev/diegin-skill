"""closure.py - 止观门（完形律）
事毕则封存 -> 投入即清零 -> 不恋战，不内耗
职责：任务完成检测、认知封存、归档管理
"""

import datetime
import json
import os
from typing import Dict, List, Optional

_CLOSURE_DIR = None

def _get_closure_dir():
    global _CLOSURE_DIR
    if _CLOSURE_DIR is None:
        _CLOSURE_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)),
                                    "var", "state")
    return _CLOSURE_DIR

class ClosureGate:
    """止观门 - 完形律执行器"""

    def __init__(self):
        self._archive_path = os.path.join(_get_closure_dir(), "dgen_archive.json")
        self._session_path = os.path.join(_get_closure_dir(), "dgen_session.json")
        self._open_items = []
        self._closed_items = []
        self._load_state()

    def _load_state(self):
        if os.path.exists(self._archive_path):
            try:
                with open(self._archive_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    self._closed_items = data if isinstance(data, list) else []
            except Exception:
                self._closed_items = []

    def _save_archive(self):
        os.makedirs(os.path.dirname(self._archive_path), exist_ok=True)
        with open(self._archive_path, "w", encoding="utf-8") as f:
            json.dump(self._closed_items, f, ensure_ascii=False, indent=2)

    def open(self, item_id, description, context=None):
        now = datetime.datetime.now().isoformat()
        entry = {
            "id": item_id,
            "description": description[:100],
            "opened_at": now,
            "status": "open",
            "context": context or {}
        }
        self._open_items = [i for i in self._open_items if i["id"] != item_id]
        self._open_items.append(entry)
        return entry

    def close(self, item_id, summary="", result="completed"):
        now = datetime.datetime.now().isoformat()
        item = None
        self._open_items = [i for i in self._open_items if i["id"] != item_id]
        for i in self._closed_items:
            if i["id"] == item_id:
                item = i
                break
        if item is None:
            item = {"id": item_id, "description": summary[:100], "opened_at": now}
        item["closed_at"] = now
        item["status"] = "closed"
        item["result"] = result
        item["summary"] = summary[:200] if summary else ""
        self._closed_items = [i for i in self._closed_items if i["id"] != item_id]
        self._closed_items.append(item)
        self._save_archive()
        return item

    def is_closed(self, item_id):
        for i in self._closed_items:
            if i["id"] == item_id:
                return True
        return False

    def get_open_items(self):
        return list(self._open_items)

    def get_closed_count(self):
        return len(self._closed_items)

    def cleanup_old(self, max_age_days=30):
        now = datetime.datetime.now()
        before = len(self._closed_items)
        cutoff = (now - datetime.timedelta(days=max_age_days)).isoformat()
        self._closed_items = [
            i for i in self._closed_items
            if i.get("closed_at", "") >= cutoff
        ]
        after = len(self._closed_items)
        if before != after:
            self._save_archive()
        return before - after

    def get_status(self):
        return {
            "principle": "止观门·完形律",
            "open_items": len(self._open_items),
            "closed_items": len(self._closed_items),
            "recent_closed": self._closed_items[-5:] if self._closed_items else []
        }

_inst = None

def get_closure():
    global _inst
    if _inst is None:
        _inst = ClosureGate()
    return _inst