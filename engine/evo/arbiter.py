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
# -*- coding: utf-8 -*-
"""
diegin-evo 冲突仲裁器（对齐 AGENTS.md §二 裁决定义）
迭进自主生成和维护

裁决类型映射：
  IRON_WALL_BLOCK → "iron_wall_block"  铁律：只输出拦截信息，不生成业务内容
  BLOCK           → "block"            拦截：回复开头输出拦截信息+原因
  ESCALATE        → "escalate"         升级：改为提问确认模式
  ALLOW           → "allow"            放行：[DGEN] PASS
  保留内部类型（CONFIDENCE_WIN / HUMAN_REQUIRED / AUTO_DEGRADED）用于引擎内部流转
"""

import time
from typing import List, Dict, Optional, Any, Union
from dataclasses import dataclass, field
from enum import Enum

from rule_engine import InterceptionRule, SuccessPattern, RuleEngine


class ResolutionType(Enum):
    """对齐 AGENTS.md §二 裁决执行表的4种外部+3种内部"""
    # ── 外部可见（AI 回复用）──
    IRON_WALL_BLOCK = "iron_wall_block"   # 铁律阻断：只输出拦截信息
    BLOCK           = "block"             # 阻断：回复开头拦截信息+原因
    ESCALATE        = "escalate"          # 升级：改为提问确认模式
    ALLOW           = "allow"             # 放行：[DGEN] PASS
    # ── 内部流转（引擎内部）──
    CONFIDENCE_WIN  = "confidence_win"    # 置信度胜出（内部映射为 ALLOW）
    HUMAN_REQUIRED  = "human_required"    # 需人工裁决（映射为 ESCALATE）
    AUTO_DEGRADED   = "auto_degraded"     # 自动降级（映射为 BLOCK）


@dataclass
class ArbitrationResult:
    """仲裁结果"""
    decision: ResolutionType
    winning_rule: Optional[object] = None
    reason: str = ""
    conflict_set: List = field(default_factory=list)
    degradation_type: str = ""
    requires_precedent: bool = False


class ConflictArbiter:
    """冲突仲裁器 — 对齐 AGENTS.md 裁决执行表"""

    def __init__(self, rule_engine: RuleEngine,
                 timeout_minutes: int = 5,
                 max_queue_size: int = 3):
        self.rule_engine = rule_engine
        self.timeout_seconds = timeout_minutes * 60
        self.max_queue_size = max_queue_size
        self.pending_conflicts: List[Dict] = []

    # ──────────────────────────────────────────────────
    # 映射：将内部类型转换为 AGENTS.md 外部类型 + 人类可读理由
    # ──────────────────────────────────────────────────

    def to_display(self, result: ArbitrationResult) -> Dict[str, Any]:
        """将仲裁结果转换为 AI 可直接输出的格式（对齐 AGENTS.md §二）"""
        mapping = {
            ResolutionType.IRON_WALL_BLOCK: "iron_wall_block",
            ResolutionType.BLOCK: "block",
            ResolutionType.ESCALATE: "escalate",
            ResolutionType.ALLOW: "allow",
            ResolutionType.CONFIDENCE_WIN: "allow",
            ResolutionType.HUMAN_REQUIRED: "escalate",
            ResolutionType.AUTO_DEGRADED: "block",
        }
        display_decision = mapping.get(result.decision, "allow")

        # 构建裁决行
        if display_decision == "iron_wall_block":
            line = f"[DGEN] IRON_BLOCK | decision: iron_wall_block | reason: {result.reason[:200]}"
        elif display_decision == "block":
            line = f"[DGEN] BLOCK | decision: block | reason: {result.reason[:200]}"
        elif display_decision == "escalate":
            line = f"[DGEN] ESCALATE | decision: escalate | reason: {result.reason[:200]}"
        else:
            line = "[DGEN] PASS"

        # 附加上下文
        if result.winning_rule:
            rule_id = getattr(result.winning_rule, 'id', str(result.winning_rule)[:40])
            rule_desc = getattr(result.winning_rule, 'trigger_condition', '') or getattr(result.winning_rule, 'pattern_name', '')
            line += f"\n  规则: {rule_id} | {rule_desc[:120]}"

        return {
            "decision": display_decision,
            "display_line": line,
            "reason": result.reason,
            "winning_rule_id": getattr(result.winning_rule, 'id', None) if result.winning_rule else None,
        }

    # ──────────────────────────────────────────────────
    # 核心仲裁逻辑（对齐 AGENTS.md）
    # ──────────────────────────────────────────────────

    def resolve(self, interceptions, patterns):
        """
        八元原则网络仲裁 · 按裁决律P0-P5优先级

        P0: 去伪存真无条件优先 → iron_wall_block
        P1: 一二不过三阻断指令优先 → block
        P2: 止观门事毕清零
        P3: 缓急律紧急分流
        P4: 守三改进规则 vs 攻七成功模式 → 置信度裁决
        P5: 举一反三 staging 规则不参与实时仲裁
        """
        if not interceptions:
            return ArbitrationResult(
                decision=ResolutionType.ALLOW,
                reason="无规则触发，默认放行"
            )

        # ── 辅助函数：检测规则归属原则 ──
        def _principle(rule):
            tags = getattr(rule, "tags", []) or []
            lifecycle = getattr(rule, "lifecycle_status", "")
            source = getattr(rule, "source", "")
            tags_str = " ".join(tags).lower()
            # 去伪存真: critical + irreversible
            if "irreversible" in tags_str and getattr(rule, "severity", "") in ("critical", "high"):
                return "去伪存真"
            # 一二不过三: self_error 或 blocking/critical lifecycle
            if "self_error" in tags_str or lifecycle in ("blocking", "critical"):
                return "一二不过三"
            if "一二不过三" in tags_str:
                return "一二不过三"
            # 举一反三: staging/cached
            if lifecycle in ("staging", "cached") or "举一反三" in tags_str:
                return "举一反三"
            # 止观门: closed/archived + 止观门tag
            if lifecycle in ("closed", "archived") or "止观门" in tags_str:
                return "止观门"
            # 缓急律: urgent tag + 缓急律tag
            if "urgent" in tags_str or "缓急律" in tags_str or "急务" in tags_str:
                return "缓急律"
            # 攻七: SuccessPattern 实例
            if "pattern" in tags_str and source in ("war_game", "learned"):
                return "攻七"
            # 守三: 默认拦截规则
            return "守三"

        # 按原则分组
        groups = {
            "去伪存真": [],
            "一二不过三": [],
            "止观门": [],
            "缓急律": [],
            "守三": [],
            "攻七": [],
            "举一反三": [],
        }
        for rule in interceptions:
            p = _principle(rule)
            if p in groups:
                groups[p].append(rule)
            else:
                groups["守三"].append(rule)

        # ⭐ P0: 去伪存真无条件优先 ⭐
        if groups["去伪存真"]:
            for rule in groups["去伪存真"]:
                if "irreversible" in " ".join(getattr(rule, "tags", []) or []):
                    return ArbitrationResult(
                        decision=ResolutionType.IRON_WALL_BLOCK,
                        winning_rule=rule,
                        reason=f"[裁决律P0] 去伪存真: {rule.id} | 触及不可逆操作铁律，强制阻断"
                    )
            return ArbitrationResult(
                decision=ResolutionType.BLOCK,
                winning_rule=groups["去伪存真"][0],
                reason=f"[裁决律P0] 去伪存真验证拒绝: {groups["去伪存真"][0].id}"
            )

        # ⭐ P1: 一二不过三阻断指令优先 ⭐
        if groups["一二不过三"]:
            for rule in groups["一二不过三"]:
                lifecycle = getattr(rule, "lifecycle_status", "")
                if lifecycle in ("blocking", "critical"):
                    return ArbitrationResult(
                        decision=ResolutionType.BLOCK,
                        winning_rule=rule,
                        reason=f"[裁决律P1] 一二不过三阻断: {rule.id} | 同类错误已达阈值，系统强制拦截"
                    )
            # alerting → escalate
            alerting = [r for r in groups["一二不过三"] if getattr(r, "lifecycle_status", "") == "alerting"]
            if alerting:
                return ArbitrationResult(
                    decision=ResolutionType.ESCALATE,
                    winning_rule=alerting[0],
                    reason=f"[裁决律P1] 一二不过三警告: {alerting[0].id} | 同类错误已出现第1次，请注意防范"
                )

        # ⭐ P2: 止观门事毕清零 ⭐
        if groups["止观门"]:
            closed_items = [r for r in groups["止观门"] if getattr(r, "lifecycle_status", "") == "closed"]
            if closed_items:
                return ArbitrationResult(
                    decision=ResolutionType.ALLOW,
                    winning_rule=closed_items[0],
                    reason=f"[裁决律P2] 止观门: {closed_items[0].id} 已完成封存，不追加纠错"
                )
            archived_items = [r for r in groups["止观门"] if getattr(r, "lifecycle_status", "") == "archived"]
            if archived_items:
                return ArbitrationResult(
                    decision=ResolutionType.ALLOW,
                    winning_rule=archived_items[0],
                    reason=f"[裁决律P2] 止观门: {archived_items[0].id} 已归档，放行"
                )

        # ⭐ P3: 缓急律紧急分流 ⭐
        if groups["缓急律"]:
            urgent_items = [r for r in groups["缓急律"] if "urgent" in " ".join(getattr(r, "tags", []) or [])]
            if urgent_items:
                return ArbitrationResult(
                    decision=ResolutionType.ALLOW,
                    winning_rule=urgent_items[0],
                    reason=f"[裁决律P3] 缓急律: {urgent_items[0].id} 紧急事务，走快速通道，跳过深度复盘"
                )

        # ⭐ P5: 举一反三 staging 不参与实时仲裁 ⭐
        active_interceptions = [r for r in interceptions if getattr(r, "lifecycle_status", "active") == "active"]
        if not active_interceptions:
            return ArbitrationResult(
                decision=ResolutionType.ALLOW,
                reason="[裁决律P5] 仅有staging规则触发，不参与实时仲裁，放行"
            )

        # ⭐ P4: 守三 vs 攻七 置信度裁决 ⭐
        patterns = patterns or []
        active_patterns = [p for p in patterns if getattr(p, "lifecycle_status", "active") == "active"]

        if active_patterns and groups["守三"]:
            best_interception = max(groups["守三"], key=lambda x: getattr(x, "confidence", 0) or 0)
            best_pattern = max(active_patterns, key=lambda x: getattr(x, "confidence", 0) or 0)
            int_conf = getattr(best_interception, "confidence", 0) or 0
            pat_conf = getattr(best_pattern, "confidence", 0) or 0
            confidence_delta = abs(int_conf - pat_conf)
            if confidence_delta < 0.5:
                self.pending_conflicts.append({
                    "timestamp": time.time(),
                    "interception": best_interception,
                    "pattern": best_pattern,
                    "delta": confidence_delta,
                    "resolved": False,
                })
                auto_decision = self._check_degradation()
                if auto_decision:
                    return auto_decision
                return ArbitrationResult(
                    decision=ResolutionType.ESCALATE,
                    conflict_set=[best_interception, best_pattern],
                    reason=f"[裁决律P4] 守三vs攻七置信度接近（delta={confidence_delta:.3f}），需用户确认"
                )
            elif pat_conf > int_conf:
                return ArbitrationResult(
                    decision=ResolutionType.ALLOW,
                    winning_rule=best_pattern,
                    reason=f"[裁决律P4] 攻七模式 {best_pattern.id} 置信度({pat_conf})高于守三规则，放行"
                )
            else:
                return ArbitrationResult(
                    decision=ResolutionType.BLOCK,
                    winning_rule=best_interception,
                    reason=f"[裁决律P4] 守三规则 {best_interception.id} 置信度({int_conf})高于攻七模式，拦截"
                )

        # ⭐ 严重度兜底 ⭐
        if active_interceptions:
            severities = [getattr(r, "severity", "low") for r in active_interceptions]
            if "high" in severities or "critical" in severities:
                high_rules = [r for r in active_interceptions if getattr(r, "severity", "") in ("high", "critical")]
                return ArbitrationResult(
                    decision=ResolutionType.BLOCK,
                    winning_rule=high_rules[0],
                    reason=f"高严重度规则触发: {high_rules[0].id}"
                )
            if "medium" in severities:
                med_rules = [r for r in active_interceptions if getattr(r, "severity", "") == "medium"]
                return ArbitrationResult(
                    decision=ResolutionType.ESCALATE,
                    winning_rule=med_rules[0],
                    reason=f"中严重度规则触发: {med_rules[0].id}，需确认后执行"
                )
            return ArbitrationResult(
                decision=ResolutionType.ALLOW,
                winning_rule=active_interceptions[0],
                reason=f"低严重度规则触发: {active_interceptions[0].id}，不影响执行"
            )

        return ArbitrationResult(
            decision=ResolutionType.ALLOW,
            reason="无活跃规则触发，放行"
        )
    def _check_degradation(self) -> Optional[ArbitrationResult]:
        """自动降级熔断检查"""
        now = time.time()

        unresolved_timeout = [
            c for c in self.pending_conflicts
            if not c.get("resolved") and (now - c["timestamp"]) > self.timeout_seconds
        ]

        should_degrade = (
            len(unresolved_timeout) > 0
            or len(self.pending_conflicts) >= self.max_queue_size
        )

        if should_degrade:
            latest = self.pending_conflicts[-1]
            latest["resolved"] = True

            # 安全优先：选择拦截方
            safety_first = sorted(
                [latest["interception"], latest["pattern"]],
                key=lambda r: (
                    (getattr(r, 'severity', 'low') in ("high", "critical")),
                    getattr(r, 'logic_score', 0) or 0
                ),
                reverse=True
            )[0]

            return ArbitrationResult(
                decision=ResolutionType.AUTO_DEGRADED,
                winning_rule=safety_first,
                reason=f"人工兜底超时/排队超限，自动降级为block",
                degradation_type="timeout" if unresolved_timeout else "queue_full",
                requires_precedent=True
            )

        return None

    # ──────────────────────────────────────────────────
    # 人工裁决接口
    # ──────────────────────────────────────────────────

    def human_resolve(self, conflict_index: int, chosen_rule) -> ArbitrationResult:
        """人工裁决接口"""
        if conflict_index < len(self.pending_conflicts):
            self.pending_conflicts[conflict_index]["resolved"] = True
            return ArbitrationResult(
                decision=ResolutionType.ALLOW,
                winning_rule=chosen_rule,
                reason="人工裁决已通过"
            )
        return ArbitrationResult(
            decision=ResolutionType.ESCALATE,
            winning_rule=None,
            reason="未找到对应冲突，请联系用户确认"
        )
