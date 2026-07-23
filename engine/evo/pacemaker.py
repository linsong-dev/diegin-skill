"""pacemaker.py - 缓急律（节奏门）
急务求效 -> 缓务求真 -> 张弛有度
职责：任务类型分类、紧急分流、宕机时段管理
"""

import datetime
import os
from typing import Dict, Optional

class PaceMaker:
    """缓急律调度器"""

    URGENT_KEYWORDS = [
        "紧急", "urgent", "立即", "immediately", "asap", "fix now",
        "broken", "crash", "down", "失败", "error", "timeout"
    ]

    DEEP_KEYWORDS = [
        "设计", "方案", "分析", "review", "audit", "复盘",
        "优化", "重构", "策略", "规划", "plan", "strategy"
    ]

    def __init__(self, downtime_start=None, downtime_end=None):
        self.downtime_start = downtime_start or "23:00"
        self.downtime_end = downtime_end or "06:00"
        self._last_classify = None
        self._classify_log = []
        self._config_path = None
        # 尝试从配置文件加载
        self._load_config()

    def _load_config(self):
        """从 config/config.toml 加载配置（若存在）"""
        # 自动探测 config 路径
        candidates = [
            os.path.join(os.path.dirname(__file__), "..", "config", "config.toml"),
            os.path.join(os.path.dirname(__file__), "..", "..", "config", "config.toml"),
        ]
        for path in candidates:
            resolved = os.path.abspath(path)
            if os.path.isfile(resolved):
                self._config_path = resolved
                break

        if self._config_path is None:
            return  # 无配置文件，使用默认值

        try:
            import tomllib
            with open(self._config_path, "rb") as f:
                cfg = tomllib.load(f)

            pm_cfg = cfg.get("pacemaker", {})
            if pm_cfg:
                ds = pm_cfg.get("downtime_start")
                de = pm_cfg.get("downtime_end")
                if ds and self._validate_time(ds):
                    self.downtime_start = ds
                if de and self._validate_time(de):
                    self.downtime_end = de
        except Exception:
            pass  # 静默失败，使用默认值

    def _validate_time(self, t: str) -> bool:
        """验证时间格式 HH:MM"""
        try:
            parts = t.split(":")
            if len(parts) != 2:
                return False
            h, m = int(parts[0]), int(parts[1])
            return 0 <= h <= 23 and 0 <= m <= 59
        except (ValueError, IndexError):
            return False

    def classify(self, ctx):
        """判断任务类型：urgent | normal | deep | new_info"""
        task = ctx.get("task", ctx.get("cmd", ctx.get("message", "")))
        task_lower = task.lower() if task else ""
        task_type = ctx.get("task_type", "")

        is_urgent = False
        for kw in self.URGENT_KEYWORDS:
            if kw in task_lower or kw in task_type:
                is_urgent = True
                break

        is_deep = False
        for kw in self.DEEP_KEYWORDS:
            if kw in task_lower or kw in task_type:
                is_deep = True
                break

        is_downtime = self._check_downtime()

        if is_downtime:
            result = {
                "channel": "downtime",
                "action": "defer_or_minimal",
                "reason": "当前处于宕机时段，仅处理紧急事务"
            }
        elif is_urgent:
            result = {
                "channel": "fast_path",
                "action": "skip_deep_review",
                "reason": "紧急任务，走快速通道，跳过深度复盘"
            }
        elif is_deep:
            result = {
                "channel": "full_path",
                "action": "trigger_deep_review",
                "reason": "缓务，触发完整原则网络"
            }
        else:
            result = {
                "channel": "normal",
                "action": "standard",
                "reason": "常规任务，走标准流程"
            }

        self._classify_log.append({
            "t": datetime.datetime.now().isoformat(),
            "task": task[:50] if task else "",
            "result": result
        })
        self._last_classify = result
        return result

    def should_skip_deep_review(self, ctx):
        c = self.classify(ctx)
        return c["channel"] in ("fast_path", "downtime")

    def _check_downtime(self):
        now = datetime.datetime.now()
        current = now.hour * 60 + now.minute
        sp = self.downtime_start.split(":")
        ep = self.downtime_end.split(":")
        start_m = int(sp[0]) * 60 + int(sp[1])
        end_m = int(ep[0]) * 60 + int(ep[1])

        in_downtime = False
        if start_m <= end_m:
            in_downtime = start_m <= current <= end_m
        else:
            in_downtime = current >= start_m or current <= end_m
        
        # 止观门: 弛阶段自动触发认知封存扫描
        if in_downtime:
            try:
                from closure import get_closure
                cl = get_closure()
                old_count = cl.cleanup_old(max_age_days=30)
                if old_count > 0:
                    print(f"  [CLOSURE] 止观门: 宕机清理了 {old_count} 条过期归档")
                open_items = cl.get_open_items()
                for item in open_items:
                    opened = item.get("opened_at", "")
                    if opened:
                        try:
                            opened_dt = datetime.datetime.fromisoformat(opened)
                            age_days = (now - opened_dt).days
                            if age_days > 7:
                                cl.close(item["id"], "auto_closure: downtime cleanup", "auto_closed")
                                print(f"  [CLOSURE] 止观门自动封存: {item['id']} (开放{age_days}天)")
                        except:
                            pass
            except Exception:
                pass
        
        return in_downtime

    def get_status(self):
        now = datetime.datetime.now()
        in_downtime = self._check_downtime()
        last = self._last_classify
        last_short = None
        if last:
            last_short = {
                "channel": last.get("channel"),
                "action": last.get("action"),
                "reason": last.get("reason", "")[:40]
            }
        return {
            "principle": "缓急律·节奏门",
            "downtime": {
                "start": self.downtime_start,
                "end": self.downtime_end,
                "active_now": in_downtime,
                "config_source": "config.toml" if self._config_path else "default(hardcoded)"
            },
            "last_classify": last_short,
            "total_classifications": len(self._classify_log)
        }

_inst = None

def get_pacemaker():
    global _inst
    if _inst is None:
        _inst = PaceMaker()
    return _inst
