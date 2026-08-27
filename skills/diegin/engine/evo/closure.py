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
        _CLOSURE_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))),
                                    "var", "state")
    return _CLOSURE_DIR

class ClosureGate:
    """止观门 - 完形律执行器（2026-08-12 律令九章定稿：状态摘要四态 + 只读快照 + 封存后只读豁免权）"""

    # 定稿第八章：状态摘要四态
    VALID_STATUSES = ("completed", "abandoned", "paused", "blocked")

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

    def close(self, item_id, summary="", result="completed", learnings=None,
              status="completed", intent_summary="", completion_criteria="",
              pending_items=None, parent_task_id="", snapshot=None):
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
        # 定稿四态：completed/abandoned/paused/blocked；旧数据兼容保留原值
        item["status"] = status if status in self.VALID_STATUSES else item.get("status", "completed")
        item["result"] = result
        item["summary"] = summary[:200] if summary else ""
        # 定稿第八章：状态摘要（task_id/intent_summary/completion_criteria/status/pending_items/parent_task_id）
        item["task_id"] = str(item_id)[:120]
        if intent_summary:
            item["intent_summary"] = str(intent_summary)[:500]
        if completion_criteria:
            item["completion_criteria"] = str(completion_criteria)[:2000]
        _pi = [str(x)[:200] for x in (pending_items or [])][:20] if pending_items else []
        if _pi:
            item["pending_items"] = _pi
        if parent_task_id:
            item["parent_task_id"] = str(parent_task_id)[:120]
        # 定稿第八章：执行轨迹只读快照（阻断记录/工具调用序列/裁决日志摘要）
        if snapshot:
            item["readonly_snapshot"] = {
                "block_records": [str(x)[:500] for x in (snapshot.get("block_records") or [])][:20],
                "tool_call_sequence": [str(x)[:500] for x in (snapshot.get("tool_call_sequence") or [])][:50],
                "arbitration_log": str(snapshot.get("arbitration_log") or "")[:2000],
            }
        # v3.7 封存打包 key learnings（止观门完形：事毕提炼可复用经验）
        _lk = learnings or []
        if isinstance(_lk, str):
            _lk = [_lk]
        item["learnings"] = [str(x)[:200] for x in _lk][:5] if _lk else []
        self._closed_items = [i for i in self._closed_items if i["id"] != item_id]
        self._closed_items.append(item)
        self._save_archive()
        return item

    def export_readonly_snapshot(self, item_id):
        """封存后只读豁免权：供守三应急复盘只读访问执行轨迹快照。
        根因分析产出为独立新规则入库，不回溯修改已封存任务状态/完成标准。"""
        import copy
        for i in self._closed_items:
            if i["id"] == item_id:
                snap = i.get("readonly_snapshot")
                return copy.deepcopy(snap) if snap else None
        return None

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
