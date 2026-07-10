#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
diegin-evo 沙盘推演引擎
迭进自主生成和维护
"""

import re
from datetime import datetime, timedelta
from typing import List, Dict, Optional, Any
from uuid import uuid4

from rule_engine import RuleEngine, SuccessPattern


class WarGameEngine:
    """沙盘推演引擎"""

    def __init__(self, rule_engine: RuleEngine):
        self.rule_engine = rule_engine
        self.ttl_hours = 24
        self.min_backtest_score = 3.5

    def run_scenarios(self, portfolio: Dict, macro_data: Dict) -> List[Dict]:
        """
        运行沙盘推演
        由 AI 在对话中生成场景逻辑，此方法负责验证和打包
        """
        scenarios = [
            {"name": "黑天鹅", "condition": "大盘单日跌幅超5%"},
            {"name": "政策急转弯", "condition": "核心项目突发重大风险政策"},
            {"name": "流动性枯竭", "condition": "成交量萎缩至20日均量30%以下"}
        ]

        results = []
        for scenario in scenarios:
            skeleton = self._generate_skeleton(scenario, portfolio, macro_data)
            validation_score = self._validate_with_history(skeleton)

            if validation_score >= self.min_backtest_score:
                template = self._package_template(skeleton, scenario)
                self._cache_template(template)
                results.append(template)
            else:
                results.append({
                    "scenario": scenario["name"],
                    "status": "rejected",
                    "reason": f"历史验证分数 {validation_score} < {self.min_backtest_score}"
                })

        return results

    def _generate_skeleton(self, scenario: Dict, portfolio: Dict, macro_data: Dict) -> Dict:
        """生成逻辑骨架（由 AI 在 Prompt 中生成）"""
        return {
            "scenario": scenario["name"],
            "logic": f"当{scenario['condition']}发生时，执行以下步骤：1.检查项目集中度 2.评估流动性 3.分批决策",
            "stripped_emotion": True
        }

    def _validate_with_history(self, skeleton: Dict) -> float:
        """用历史经验验证推演逻辑"""
        keywords = self._extract_keywords(skeleton.get("logic", ""))

        scores = []
        for rule in self.rule_engine.get_interceptions(active_only=True):
            rule_keywords = self._extract_keywords(rule.trigger_condition)
            overlap = set(keywords) & set(rule_keywords)
            if len(overlap) >= 2:
                scores.append(rule.confidence)

        for pattern in self.rule_engine.get_patterns(active_only=True):
            pattern_keywords = self._extract_keywords(pattern.trigger_scenario)
            overlap = set(keywords) & set(pattern_keywords)
            if len(overlap) >= 2:
                scores.append(pattern.confidence)

        if not scores:
            return 2.5
        return sum(scores) / len(scores)

    def _extract_keywords(self, text: str) -> List[str]:
        """提取中文关键词"""
        stopwords = ["的", "了", "是", "在", "和", "与", "或", "当", "时", "如果", "那么", "则"]
        words = re.findall(r'[\u4e00-\u9fa5]{2,}', text)
        return [w for w in words if w not in stopwords]

    def _package_template(self, skeleton: Dict, scenario: Dict) -> Dict:
        """打包为临时模板"""
        return {
            "type": "contingency_pattern",
            "id": f"cont_{datetime.now().strftime('%Y%m%d_%H%M%S')}_{uuid4().hex[:8]}",
            "pattern_name": f"应急-{scenario['name']}",
            "trigger_scenario": scenario["condition"],
            "decision_logic": skeleton.get("logic", ""),
            "micro_template": skeleton.get("logic", "")[:50],
            "source": "war_game",
            "auto_promoted": False,
            "ttl_hours": self.ttl_hours,
            "expires_at": (datetime.now() + timedelta(hours=self.ttl_hours)).isoformat(),
            "extracted_context": {
                "original_scenario": scenario["name"],
                "stripped_emotion": skeleton.get("stripped_emotion", False),
                "remaining_logic_only": True
            },
            "lifecycle_status": "cached",
            "logic_score": 4.0,
            "outcome_score": 3.5,
            "confidence": 3.8,
            "created_at": datetime.now().isoformat(),
            "valid_until": (datetime.now() + timedelta(hours=self.ttl_hours)).isoformat()
        }

    def _cache_template(self, template: Dict):
        """缓存临时模板（写入规则库的 cached 状态）"""
        pattern = SuccessPattern(
            id=template["id"],
            pattern_name=template["pattern_name"],
            trigger_scenario=template["trigger_scenario"],
            decision_logic=template["decision_logic"],
            micro_template=template["micro_template"],
            source=template["source"],
            auto_promoted=False,
            logic_score=template["logic_score"],
            outcome_score=template["outcome_score"],
            confidence=template["confidence"],
            lifecycle_status="cached",
            created_at=template["created_at"],
            valid_until=template["valid_until"]
        )
        self.rule_engine.add_pattern(pattern)
