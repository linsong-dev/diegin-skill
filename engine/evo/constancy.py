# -*- coding: utf-8 -*-
"""constancy.py - 持存·恒常门（任务续接）
启而探之 → 行而记之 → 断而存之 → 续而接之
职责：task_id 生命周期、状态摘要、暂停/恢复、阻塞上报、嵌套保护、溢出保护、30天快照
定稿依据：律令九章 第七章 持存·恒常门（2026-08-12 最终定稿）
"""
from __future__ import annotations

import datetime
import difflib
import json
import os
import uuid
from typing import Any, Dict, List, Optional

_TASKS_PATH = None


def _get_tasks_path() -> str:
    global _TASKS_PATH
    if _TASKS_PATH is None:
        _TASKS_PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))),
                                   "var", "state", "constancy_tasks.json")
    return _TASKS_PATH


MAX_NEST_DEPTH = 3          # 嵌套深度不超过3层
SNAPSHOT_RETENTION_DAYS = 30  # 封存包保留30天
USER_SUMMARY_MAX_CHARS = 50   # 用户可见摘要≤50字
SNAPSHOT_TOKEN_LIMIT = 16000      # 活跃恢复快照 Token 上限（可配置）
SNAPSHOT_FULL_KEEP = 30         # 快照全集保留 30 个任务，更早归档冷存储

_RECOVERABLE_STATUSES = ("paused", "blocked")
_TERMINAL_STATUSES = ("completed", "abandoned")


class TaskRegistry:
    """恒常门任务登记处：task_id 生命周期 + 状态摘要 + 恢复检查"""

    def __init__(self):
        self._path = _get_tasks_path()
        self._tasks: Dict[str, Dict[str, Any]] = {}
        self._load()

    # ── 持久化 ──────────────────────────────────────────────
    def _load(self) -> None:
        try:
            if os.path.exists(self._path):
                with open(self._path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                if isinstance(data, dict):
                    self._tasks = data
        except Exception:
            self._tasks = {}

    def _save(self) -> None:
        try:
            os.makedirs(os.path.dirname(self._path), exist_ok=True)
            tmp = self._path + ".tmp"
            with open(tmp, "w", encoding="utf-8") as f:
                json.dump(self._tasks, f, ensure_ascii=False, indent=2)
            os.replace(tmp, self._path)  # 原子替换：并发读写一致性（定稿第七章·并发隔离）
        except Exception:
            pass

    # ── 工具 ────────────────────────────────────────────────
    @staticmethod
    def _now_iso() -> str:
        return datetime.datetime.now().isoformat()

    def _gen_task_id(self) -> str:
        ts = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        return f"task_{ts}_{uuid.uuid4().hex[:6]}"

    def nest_depth(self, task_id: str) -> int:
        """沿 parent_task_id 链计算嵌套深度（自身=1）"""
        depth = 0
        cur = task_id
        seen = set()
        while cur and cur in self._tasks and cur not in seen:
            depth += 1
            seen.add(cur)
            cur = self._tasks[cur].get("parent_task_id") or None
            if depth > 20:  # 防御环
                break
        return depth

    def user_summary(self, task_id: str) -> str:
        """用户可见摘要（≤50字），用于恢复前确认"""
        t = self._tasks.get(task_id)
        if not t:
            return ""
        intent = (t.get("intent_summary") or "").strip()
        status = t.get("status", "paused")
        prefix = f"[{status}] "
        max_intent = USER_SUMMARY_MAX_CHARS - len(prefix)
        if len(intent) > max_intent:
            intent = intent[:max_intent]
        return prefix + intent

    # ── 生命周期 ────────────────────────────────────────────
    def begin(self, intent_summary: str, completion_criteria: str = "",
              pending_items: Optional[List[str]] = None,
              parent_task_id: Optional[str] = None,
              context: Optional[Dict] = None) -> Dict[str, Any]:
        """启而探：创建新任务（含嵌套深度保护）"""
        intent_summary = (intent_summary or "").strip()
        if not intent_summary:
            intent_summary = "未命名任务"
        if parent_task_id:
            parent = self._tasks.get(parent_task_id)
            if not parent:
                return {"ok": False, "error": "parent_not_found",
                        "reason": f"父任务不存在: {parent_task_id}"}
            # 溢出保护：父任务深度达到第3层时，子任务将是第4层 → 拒绝
            if self.nest_depth(parent_task_id) >= MAX_NEST_DEPTH:
                return {"ok": False, "error": "nested_overflow",
                        "reason": "嵌套深度即将达到第4层，恒常门拒绝创建新子任务，由父任务自行消化或放弃该子目标",
                        "task_id": parent_task_id}
        task_id = self._gen_task_id()
        task = {
            "task_id": task_id,
            "intent_summary": intent_summary[:500],
            "completion_criteria": (completion_criteria or "")[:2000],
            "status": "paused",          # 新建即挂起，等待入口恢复确认
            "pending_items": [str(x)[:200] for x in (pending_items or [])][:20],
            "parent_task_id": parent_task_id or "",
            "blocker_report": "",
            "created_at": self._now_iso(),
            "updated_at": self._now_iso(),
            "context": {k: str(v)[:200] for k, v in (context or {}).items()},
            "resume_count": 0,
        }
        self._tasks[task_id] = task
        self._save()
        return {"ok": True, "task_id": task_id, "task": task}

    # ── 冷存储与快照分级（定稿第七章：Token 上限 16k + 快照全集 30 个 + 冷存储指针）──
    def _cold_store_path(self) -> str:
        return self._path.replace("constancy_tasks.json", "constancy_cold_store.json")

    def _load_cold_store(self) -> Dict[str, Dict[str, Any]]:
        try:
            if os.path.exists(self._cold_store_path()):
                with open(self._cold_store_path(), "r", encoding="utf-8") as f:
                    data = json.load(f)
                if isinstance(data, dict):
                    return data
        except Exception:
            pass
        return {}

    def _save_cold_store(self, store: Dict[str, Dict[str, Any]]) -> None:
        try:
            os.makedirs(os.path.dirname(self._cold_store_path()), exist_ok=True)
            tmp = self._cold_store_path() + ".tmp"
            with open(tmp, "w", encoding="utf-8") as f:
                json.dump(store, f, ensure_ascii=False, indent=2)
            os.replace(tmp, self._cold_store_path())
        except Exception:
            pass

    @staticmethod
    def _estimate_tokens(text: str) -> int:
        """中文 1 字 ≈ 1 token，英文按 4 字符 ≈ 1 token（16k 上限的可配置近似）"""
        if not text:
            return 0
        cjk = sum(1 for ch in text if "\u4e00" <= ch <= "\u9fff")
        other = len(text) - cjk
        return cjk + other // 4

    def snapshot_token_count(self, task_id: str) -> int:
        """活跃恢复快照 token 估算（intent + criteria + pending + blocker + context）"""
        t = self._tasks.get(task_id)
        if not t:
            return 0
        parts = [
            t.get("intent_summary", "") or "",
            t.get("completion_criteria", "") or "",
            " ".join(t.get("pending_items") or []),
            t.get("blocker_report", "") or "",
            json.dumps(t.get("context") or {}, ensure_ascii=False),
        ]
        return sum(self._estimate_tokens(x) for x in parts)

    def archive_old_snapshots(self, full_keep: int = SNAPSHOT_FULL_KEEP) -> int:
        """快照全集保留最近 full_keep 个任务；更早快照压缩为核心字段并归档冷存储。
        压缩保留 task_id / intent_summary(50字) / status / completion_criteria，完整快照存入冷存储。"""
        store = self._load_cold_store()
        ordered = sorted(self._tasks.items(),
                         key=lambda kv: kv[1].get("updated_at", kv[1].get("created_at", "")),
                         reverse=True)
        archived = 0
        for tid, t in ordered[full_keep:]:
            if t.get("cold_stored"):
                continue
            store[tid] = dict(t)
            self._tasks[tid] = {
                "task_id": tid,
                "intent_summary": (t.get("intent_summary") or "")[:50],
                "status": t.get("status", "paused"),
                "completion_criteria": (t.get("completion_criteria") or "")[:2000],
                "cold_stored": True,
                "archived_at": self._now_iso(),
            }
            archived += 1
        if archived:
            self._save_cold_store(store)
            self._save()
        return archived

    def _cold_pointer(self, task: Dict[str, Any]) -> Dict[str, Any]:
        """冷存储指针：仅加载核心字段（详细日志按需 RAG 检索）"""
        return {
            "task_id": task.get("task_id", ""),
            "intent_summary": (task.get("intent_summary") or "")[:50],
            "status": task.get("status", "paused"),
            "completion_criteria": (task.get("completion_criteria") or "")[:2000],
            "cold_stored": True,
            "token_count": self.snapshot_token_count(task.get("task_id", "")),
            "bulk_hint": "任务信息量较大，恢复后可能需要分批加载",
        }

    def find_recoverable(self) -> List[Dict[str, Any]]:
        """续而接：检索未完成且未超时的 task_id"""
        now = datetime.datetime.now()
        out = []
        for tid, t in self._tasks.items():
            if t.get("status") not in _RECOVERABLE_STATUSES:
                continue
            updated = t.get("updated_at", "")
            try:
                age = (now - datetime.datetime.fromisoformat(updated)).days
            except Exception:
                age = 0
            if age > SNAPSHOT_RETENTION_DAYS:
                continue
            t_copy = dict(t)
            # 定稿第七章：活跃恢复快照 Token 上限 → 超限自动转为冷存储指针（仅加载摘要）
            if self.snapshot_token_count(tid) > SNAPSHOT_TOKEN_LIMIT:
                t_copy = self._cold_pointer(t_copy)
            out.append(t_copy)
        out.sort(key=lambda x: x.get("updated_at", ""), reverse=True)
        return out

    _FUZZY_STOP_WORDS = ("恢复", "继续", "那个", "这个", "请", "帮我", "把", "去",
                       "一下", "任务", "然后", "再", "接着", "我们", "我", "要")

    @classmethod
    def _intent_score(cls, query: str, text: str) -> float:
        """轻量意图相似度（零依赖）：连续词块覆盖度 75% + 序列相似度 25%。

        覆盖度 = 查询中被目标文本以 ≥2 字符连续片段命中的字符占比；
        先剔除引导停用词（恢复/继续/那个/任务等），减少噪音稀释。
        """
        if not query or not text:
            return 0.0
        q = query.lower()
        t = text.lower()[:300]  # 截断防超长文本拖慢 O(n*m)
        for w in cls._FUZZY_STOP_WORDS:
            q = q.replace(w, " ")
        q = "".join(q.split())
        if not q:
            return 0.0
        n, m = len(q), len(t)
        covered = [False] * n
        for i in range(n):
            if covered[i]:
                continue
            best = 0
            for j in range(m):
                k = 0
                while i + k < n and j + k < m and q[i + k] == t[j + k]:
                    k += 1
                if k > best:
                    best = k
            if best >= 2:
                for x in range(best):
                    if i + x < n:
                        covered[i + x] = True
        cov = sum(covered) / n if n else 0.0
        seq = difflib.SequenceMatcher(None, q, t).ratio()
        return round(0.75 * cov + 0.25 * seq, 3)

    def find_by_intent(self, text: str, top_k: int = 3) -> List[Dict[str, Any]]:
        """续而接·模糊查找：按意图关键词/相似度检索可恢复任务（paused/blocked 未超时）。

        用于自然语言恢复（无 task_id 时）：用户说「恢复 A股模拟盘任务」，
        依 intent_summary 打分返回 top 候选；是否真正恢复由调用方按置信度+用户确认裁决。
        """
        if not text or not text.strip():
            return []
        now = datetime.datetime.now()
        scored = []
        for tid, t in self._tasks.items():
            if t.get("status") not in _RECOVERABLE_STATUSES:
                continue
            updated = t.get("updated_at", "")
            try:
                age = (now - datetime.datetime.fromisoformat(updated)).days
            except Exception:
                age = 0
            if age > SNAPSHOT_RETENTION_DAYS:
                continue
            summary = t.get("intent_summary", "") or ""
            criteria = t.get("completion_criteria", "") or ""
            match_text = (summary + " " + criteria).strip()
            score = self._intent_score(text, match_text)
            if score <= 0:
                continue
            scored.append({"task_id": tid,
                           "summary": summary[:USER_SUMMARY_MAX_CHARS],
                           "score": score})
        scored.sort(key=lambda x: (-x["score"], x["task_id"]))
        return scored[:top_k]

    def snapshot(self, task_id: str) -> Dict[str, Any]:
        """状态摘要（含完成标准、阻塞报告、待办清单）"""
        return dict(self._tasks.get(task_id) or {})

    def suspend(self, task_id: str, reason: str = "") -> bool:
        """断而存：任务中断/切换时挂起并生成状态摘要"""
        t = self._tasks.get(task_id)
        if not t:
            return False
        t["status"] = "paused"
        t["updated_at"] = self._now_iso()
        if reason:
            t["last_pause_reason"] = str(reason)[:500]
        self._save()
        return True

    def complete(self, task_id: str) -> bool:
        t = self._tasks.get(task_id)
        if not t:
            return False
        t["status"] = "completed"
        t["updated_at"] = self._now_iso()
        self._save()
        return True

    def abandon(self, task_id: str, reason: str = "") -> bool:
        t = self._tasks.get(task_id)
        if not t:
            return False
        t["status"] = "abandoned"
        t["updated_at"] = self._now_iso()
        if reason:
            t["abandon_reason"] = str(reason)[:500]
        self._save()
        return True

    def block(self, task_id: str, blocker_report: str) -> bool:
        """子任务受阻：status=blocked + blocker_report，上报父任务"""
        t = self._tasks.get(task_id)
        if not t:
            return False
        t["status"] = "blocked"
        t["blocker_report"] = str(blocker_report)[:2000]
        t["updated_at"] = self._now_iso()
        self._save()
        # 阻塞证据上报父任务
        parent = t.get("parent_task_id")
        if parent and parent in self._tasks:
            self._tasks[parent]["blocker_report"] = str(blocker_report)[:2000]
            self._tasks[parent]["updated_at"] = self._now_iso()
            self._save()
        return True

    def resume(self, task_id: str) -> bool:
        """续而接：用户确认后恢复任务（completed/abandoned 永不自动恢复）"""
        t = self._tasks.get(task_id)
        if not t:
            return False
        if t.get("status") in _TERMINAL_STATUSES:
            return False
        t["status"] = "paused"  # 恢复后进入执行态，仍以 paused 标记待执行
        t["resume_count"] = int(t.get("resume_count", 0) or 0) + 1
        t["updated_at"] = self._now_iso()
        self._save()
        return True

    def cleanup_expired(self, max_days: int = SNAPSHOT_RETENTION_DAYS) -> int:
        """封存包保留30天，超时自动清理（completed/abandoned 与超时的 paused/blocked）"""
        now = datetime.datetime.now()
        before = len(self._tasks)
        keep: Dict[str, Dict[str, Any]] = {}
        for tid, t in self._tasks.items():
            updated = t.get("updated_at", t.get("created_at", ""))
            try:
                age = (now - datetime.datetime.fromisoformat(updated)).days
            except Exception:
                age = 0
            if age <= max_days or t.get("status") in _TERMINAL_STATUSES:
                keep[tid] = t
        removed = before - len(keep)
        self._tasks = keep
        if removed:
            self._save()
        return removed

    def get_status(self) -> Dict[str, Any]:
        recoverable = self.find_recoverable()
        return {
            "principle": "持存·恒常门",
            "total_tasks": len(self._tasks),
            "recoverable": len(recoverable),
            "recoverable_tasks": [
                {"task_id": t["task_id"], "status": t.get("status"),
                 "summary": self.user_summary(t["task_id"]),
                 "updated_at": t.get("updated_at", "")}
                for t in recoverable
            ],
            "snapshot_retention_days": SNAPSHOT_RETENTION_DAYS,
            "max_nest_depth": MAX_NEST_DEPTH,
        }


_inst: Optional[TaskRegistry] = None


def get_constancy() -> TaskRegistry:
    global _inst
    if _inst is None:
        _inst = TaskRegistry()
    return _inst