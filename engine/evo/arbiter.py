#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
diegin-evo 冲突仲裁器（对齐 AGENTS.md §二 裁决定义）
迭进自主生成和维护

裁决类型映射：
  IRON_WALL_BLOCK → "iron_wall_block"  铁律：只输出拦截信息，不生成业务内容
  BLOCK           → "block"            拦截：回复开头输出拦截信息+原因
  ESCALATE        → "escalate"         升级：改为提问确认模式
  ALLOW           → "allow"            放行：[DGEN] ✅ 通过
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
    ALLOW           = "allow"             # 放行：[DGEN] ✅ 通过
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
            line = f"[DGEN] 🛑 铁律阻断 | 裁决: iron_wall_block | 原因: {result.reason[:200]}"
        elif display_decision == "block":
            line = f"[DGEN] 🛑 拦截 | 裁决: block | 原因: {result.reason[:200]}"
        elif display_decision == "escalate":
            line = f"[DGEN] ⚠️ 需确认 | 裁决: escalate | 原因: {result.reason[:200]}"
        else:
            line = "[DGEN] ✅ 通过"

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
        5层裁决（对齐 AGENTS.md §二）：
        第1层：铁律检查（high/critical+irreversible）
        第2层：critical/high 严重度→block
        第3层：medium/low触发 + 成功模式 → 置信度冲突检测
        第4层：medium/low触发 无模式 → 严重度决定
        第5层：默认放行（allow）
        """
        # ⭐⭐⭐ 第1层：铁律阻断 ⭐⭐⭐
        for rule in interceptions:
            severity = getattr(rule, 'severity', 'low')
            tags = getattr(rule, 'tags', []) or []
            if severity in ("critical", "high") and "irreversible" in tags:
                return ArbitrationResult(
                    decision=ResolutionType.IRON_WALL_BLOCK,
                    winning_rule=rule,
                    reason=f"触及安全铁律：{getattr(rule, 'id', '?')} | 不可逆操作或合规红线"
                )

        # ⭐⭐⭐ 第2层：严重度检查（安全优先，模式不可穿透）⭐⭐⭐
        if interceptions:
            severities = [getattr(r, 'severity', 'low') for r in interceptions]
            # critical/high → 直接 BLOCK，不论有无成功模式
            if "critical" in severities:
                crit_rules = [r for r in interceptions if getattr(r, 'severity', '') == "critical"]
                return ArbitrationResult(
                    decision=ResolutionType.BLOCK,
                    winning_rule=crit_rules[0],
                    reason=f"触及关键规则（critical）：{crit_rules[0].id}"
                )

            if "high" in severities:
                high_rules = [r for r in interceptions if getattr(r, 'severity', '') == "high"]
                return ArbitrationResult(
                    decision=ResolutionType.BLOCK,
                    winning_rule=high_rules[0],
                    reason=f"匹配高严重度规则：{high_rules[0].id}"
                )

            # ⭐⭐⭐ 第3层：攻守冲突检测（仅 medium/low + 成功模式）⭐⭐⭐
            if patterns:
                best_interception = max(interceptions, key=lambda x: getattr(x, 'confidence', 0) or 0)
                best_pattern = max(patterns, key=lambda x: getattr(x, 'confidence', 0) or 0)
                int_conf = getattr(best_interception, 'confidence', 0) or 0
                pat_conf = getattr(best_pattern, 'confidence', 0) or 0
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
                        reason=f"攻守规则置信度接近（delta={confidence_delta:.3f}），需询问用户"
                    )
                elif pat_conf > int_conf:
                    return ArbitrationResult(
                        decision=ResolutionType.ALLOW,
                        winning_rule=best_pattern,
                        reason=f"成功模式 {best_pattern.id} 置信度（{pat_conf}）高于拦截规则，放行"
                    )

            # ⭐⭐⭐ 第4层：严重度决定（无成功模式 / 拦截置信度更高）⭐⭐⭐
            if "medium" in severities:
                med_rules = [r for r in interceptions if getattr(r, 'severity', '') == "medium"]
                return ArbitrationResult(
                    decision=ResolutionType.ESCALATE,
                    winning_rule=med_rules[0],
                    reason=f"匹配中严重度规则：{med_rules[0].id}，需确认后执行"
                )

            # low → 放行但通知
            return ArbitrationResult(
                decision=ResolutionType.ALLOW,
                winning_rule=interceptions[0],
                reason=f"低严重度规则触发：{interceptions[0].id}，不影响执行"
            )

        # ⭐⭐⭐ 第5层：默认放行 ⭐⭐⭐
        return ArbitrationResult(
            decision=ResolutionType.ALLOW,
            winning_rule=None,
            reason="无规则触发或全部放行"
        )
    # ──────────────────────────────────────────────────
    # 自动降级（熔断保护）
    # ──────────────────────────────────────────────────

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
