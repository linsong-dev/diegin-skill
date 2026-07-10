#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
diegin-evo 三明治复盘引擎
迭进自主生成和维护
"""

import json
import re
from datetime import datetime
from typing import List, Dict, Optional, Any, Tuple
from dataclasses import dataclass, field

from rule_engine import (
    RuleEngine, InterceptionRule, SuccessPattern,
    MetaExperience, Precedent
)


@dataclass
class ReviewSignal:
    """复盘信号"""
    description: str
    type: str                                 # positive | negative
    linked_rules: List[str] = field(default_factory=list)
    allowed_output_types: List[str] = field(default_factory=list)
    forced_type: str = ""
    require_state_check: bool = False
    attribution: Dict = field(default_factory=dict)


@dataclass
class ReviewResult:
    """复盘结果"""
    positive_signals: List[ReviewSignal]
    negative_signals: List[ReviewSignal]
    clean_signals: List[ReviewSignal]
    filtered_signals: List[Dict]
    fused_outputs: List[Dict]
    meta_insights: List[MetaExperience]
    anomaly_observations: List[Dict]


class Reviewer:
    """三明治复盘引擎"""

    def __init__(self, rule_engine: RuleEngine):
        self.rule_engine = rule_engine
        self.luck_keywords = [
            "运气", "没想到会", "意外", "突然", "巧合",
            "碰巧", "刚好", "偶然", "不可预测"
        ]
        self.emotion_keywords = [
            "害怕", "贪婪", "冲动", "焦虑", "恐慌",
            "兴奋", "着急", "不耐烦", "情绪化"
        ]

    def full_review(self, task_context: Dict, result: Dict) -> ReviewResult:
        """
        完整三明治复盘
        步骤：正向轻回顾 → 负向深挖 → 归因过滤 → 融合提炼 → 元认知
        """
        # 阶段1：正向轻回顾（20% 逻辑，由 AI 生成信号列表）
        positive_signals = self._positive_light_review(result)

        # 阶段2：负向深挖（50% 逻辑）
        negative_signals = self._negative_deep_review(result)

        # 阶段3：归因过滤
        historical = self.rule_engine.get_interceptions(active_only=True)[:20]
        filter_result = self._attribution_filter(
            positive_signals, negative_signals, historical
        )

        # 阶段4：融合提炼
        fused_outputs = self._fusion_refine(
            filter_result["clean_signals"],
            negative_signals,
            task_context
        )

        # 阶段5：元认知反思
        meta_insights = self._meta_cognition_review()

        # 阶段6：写入规则库
        for output in fused_outputs:
            if output["type"] == "interception_rule":
                rule = InterceptionRule(**output)
                self.rule_engine.add_interception(rule)
            elif output["type"] == "success_pattern":
                pattern = SuccessPattern(**output)
                self.rule_engine.add_pattern(pattern)

        for f in filter_result["filtered_signals"]:
            if f["disposition"] == "downgrade_to_anomaly_observation":
                self._write_anomaly(f["signal"])

        self.rule_engine.save_all()

        return ReviewResult(
            positive_signals=positive_signals,
            negative_signals=negative_signals,
            clean_signals=filter_result["clean_signals"],
            filtered_signals=filter_result["filtered_signals"],
            fused_outputs=fused_outputs,
            meta_insights=meta_insights,
            anomaly_observations=filter_result.get("anomalies", [])
        )

    # ─── 各阶段实现 ───

    def _positive_light_review(self, result: Dict) -> List[ReviewSignal]:
        """
        正向轻回顾
        注意：实际信号提取由 AI 在 Prompt 中完成
        """
        return []

    def _negative_deep_review(self, result: Dict) -> List[ReviewSignal]:
        """负向深挖"""
        return []

    def _attribution_filter(self, positive_signals: List[ReviewSignal],
                             negative_signals: List[ReviewSignal],
                             historical_rules: List[InterceptionRule]) -> Dict:
        """
        归因过滤器
        三道过滤：反事实追问、归因一致性、标签限权
        """
        clean_signals = []
        filtered_signals = []
        anomalies = []

        for signal in positive_signals:
            luck_score = self._assess_luck(signal.description)
            emotion_score = self._assess_emotion(signal.description)
            consistency_issue = self._check_attribution_consistency(
                signal, historical_rules
            )

            if luck_score == "high":
                filtered_signals.append({
                    "signal": signal,
                    "reason": "运气主导",
                    "disposition": "downgrade_to_anomaly_observation"
                })
                signal.forced_type = "anomaly_observation"
                signal.allowed_output_types = ["note"]
                anomalies.append({"signal": signal, "reason": "运气主导"})

            elif emotion_score == "high":
                filtered_signals.append({
                    "signal": signal,
                    "reason": "情绪驱动",
                    "disposition": "bind_state_check_rule"
                })
                signal.require_state_check = True

            elif consistency_issue:
                filtered_signals.append({
                    "signal": signal,
                    "reason": f"归因不一致：上次评价为「{consistency_issue}」",
                    "disposition": "flag_for_review"
                })
            else:
                clean_signals.append(signal)

        return {
            "clean_signals": clean_signals,
            "filtered_signals": filtered_signals,
            "anomalies": anomalies,
            "filter_count": len(filtered_signals)
        }

    def _assess_luck(self, text: str) -> str:
        """评估运气成分"""
        desc = text.lower()
        luck_count = sum(1 for kw in self.luck_keywords if kw in desc)
        if luck_count >= 2:
            return "high"
        elif luck_count == 1:
            return "medium"
        return "low"

    def _assess_emotion(self, text: str) -> str:
        """评估情绪驱动程度"""
        desc = text.lower()
        emotion_count = sum(1 for kw in self.emotion_keywords if kw in desc)
        if emotion_count >= 2:
            return "high"
        elif emotion_count == 1:
            return "medium"
        return "low"

    def _check_attribution_consistency(self, signal: ReviewSignal,
                                        historical_rules: List[InterceptionRule]) -> Optional[str]:
        """检查归因一致性"""
        if not signal.linked_rules:
            return None

        for rule_id in signal.linked_rules:
            for rule in historical_rules:
                if rule.id == rule_id and rule.ignored_count > 0:
                    return f"规则 {rule_id} 曾被无视 {rule.ignored_count} 次"
        return None

    def _fusion_refine(self, clean_signals: List[ReviewSignal],
                        negative_signals: List[ReviewSignal],
                        task_context: Dict) -> List[Dict]:
        """
        融合提炼：正负向关联，生成带边界条件的复用模式
        """
        outputs = []

        for signal in clean_signals:
            pattern = {
                "id": "",
                "pattern_name": f"从任务 {task_context.get('task_id', 'unknown')} 提炼",
                "trigger_scenario": task_context.get("task_type", ""),
                "decision_logic": signal.description,
                "micro_template": signal.description[:50],
                "preconditions": task_context.get("preconditions", []),
                "boundary_conditions": [],
                "luck_factor": "low",
                "emotion_factor": "low",
                "core_capability": self._extract_capability(signal.description),
                "logic_score": 4.5,
                "outcome_score": 4.0,
                "confidence": 4.3,
                "source": "learned",
                "auto_promoted": False,
                "created_at": datetime.now().isoformat(),
                "lifecycle_status": "active",
                "triggered_count": 0
            }
            outputs.append({"type": "success_pattern", **pattern})

        return outputs

    def _extract_capability(self, text: str) -> str:
        """提取核心能力关键词"""
        capabilities = ["数据分析", "风险识别", "宏观判断", "技术分析",
                        "基本面分析", "市场情绪", "策略制定", "执行纪律"]
        for cap in capabilities:
            if cap in text:
                return cap
        return "通用决策能力"

    def _meta_cognition_review(self) -> List[MetaExperience]:
        """元认知反思（由 AI 在 Prompt 中生成）"""
        return []

    def _write_anomaly(self, signal: ReviewSignal):
        """写入异常观察（由 AI 在对话中写入）"""
        pass


# ============================================================
# ROI 分级复盘
# ============================================================

class ROIReviewer:
    """ROI 分级复盘管理器"""

    TIERS = {
        "high": {"trigger": ["config_change", "release", "high_risk_action"], "depth": "full"},
        "medium": {"trigger": ["report", "portfolio_review"], "depth": "simplified"},
        "low": {"trigger": ["query", "info", "daily_check"], "depth": "minimal"}
    }

    @classmethod
    def get_tier(cls, task_type: str) -> str:
        """获取任务的价值层级"""
        for tier, config in cls.TIERS.items():
            if any(t in task_type for t in config["trigger"]):
                return tier
        return "medium"

    @classmethod
    def get_review_prompt(cls, tier: str) -> Dict:
        """获取对应层级的复盘 Prompt 模板"""
        prompts = {
            "full": {
                "description": "完整三明治复盘 + 归因过滤 + 元认知",
                "questions": [
                    "1. 正向轻回顾（20%）：做对了什么？核心决策点是什么？",
                    "2. 负向深挖（50%）：哪里不够好？是能力不足还是认知偏差？边界条件是什么？",
                    "3. 归因过滤：反事实追问——如果去掉运气因素，决策还成立吗？",
                    "4. 融合提炼（30%）：正负向关联，提炼最小化微模板",
                    "5. 元认知反思：本次复盘本身有什么问题？"
                ]
            },
            "simplified": {
                "description": "简化复盘（40% Token）",
                "questions": [
                    "1. 这次有没有致命错误？如果有，是什么？",
                    "2. 有没有一个可以复用的 1 句话微模板？"
                ]
            },
            "minimal": {
                "description": "极简复盘（10% Token）",
                "questions": [
                    "1. 用 1 句话总结这次任务的结论"
                ]
            }
        }
        return prompts.get(tier, prompts["medium"])
