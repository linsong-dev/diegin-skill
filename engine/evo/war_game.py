#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""diegin-evo sandbox war game engine (enhanced)"""

import re
from datetime import datetime, timedelta
from typing import List, Dict, Any
from uuid import uuid4

from rule_engine import RuleEngine, InterceptionRule, SuccessPattern


class WarGameEngine:
    """Sandbox war game engine for generating coding-relevant rules"""

    def __init__(self, rule_engine: RuleEngine):
        self.rule_engine = rule_engine
        self.min_backtest_score = 2.5

    def run_scenarios(self, portfolio, macro_data):
        scenarios = self._generate_scenarios(portfolio, macro_data)
        results = []
        for scenario in scenarios:
            skeleton = self._generate_skeleton(scenario, portfolio, macro_data)
            score = self._validate_with_history(skeleton)
            if score >= self.min_backtest_score:
                template = self._package_template(skeleton, scenario)
                self._cache_template(template)
                results.append(template)
            else:
                results.append({
                    "scenario": scenario["name"],
                    "status": "rejected",
                    "reason": "score " + str(score) + " < " + str(self.min_backtest_score)
                })
        return results

    def _generate_scenarios(self, portfolio, macro_data):
        scenarios = []

        scenarios.append({
            "name": "destructive_file_op",
            "type": "interception",
            "condition": "op in ('delete', 'move', 'rename') AND recursive == true",
            "severity": "critical",
            "tags": ["global", "irreversible", "file_safety"],
            "action": "block_execution; require_explicit_approval",
            "logic_score": 5.0, "outcome_score": 4.5
        })

        scenarios.append({
            "name": "env_var_exposure",
            "type": "interception",
            "condition": "'env:' in prompt",
            "severity": "high",
            "tags": ["global", "security", "secret"],
            "action": "warn_and_confirm",
            "logic_score": 4.5, "outcome_score": 4.0
        })

        scenarios.append({
            "name": "mass_parallel_ops",
            "type": "interception",
            "condition": "op == shell AND 'for' in cmd AND 'in' in cmd",
            "severity": "high",
            "tags": ["global", "resource"],
            "action": "chunk_and_confirm",
            "logic_score": 4.0, "outcome_score": 4.0
        })

        scenarios.append({
            "name": "data_overwrite",
            "type": "interception",
            "condition": "op == file_write AND exists == true",
            "severity": "medium",
            "tags": ["global", "data_integrity"],
            "action": "confirm_overwrite",
            "logic_score": 4.0, "outcome_score": 3.5
        })

        scenarios.append({
            "name": "external_network_call",
            "type": "interception",
            "condition": "op == network AND target != 'localhost'",
            "severity": "medium",
            "tags": ["global", "network"],
            "action": "permission_check; confirm_before_send",
            "logic_score": 4.0, "outcome_score": 3.5
        })

        scenarios.append({
            "name": "git_destructive",
            "type": "interception",
            "condition": "op == git AND ' --force' in cmd",
            "severity": "high",
            "tags": ["global", "git", "irreversible"],
            "action": "block_execution; require_explicit_approval",
            "logic_score": 5.0, "outcome_score": 4.5
        })

        scenarios.append({
            "name": "file_read_sensitive",
            "type": "interception",
            "condition": "op == file_read AND ('.env' in path OR 'secret' in path OR 'password' in path)",
            "severity": "high",
            "tags": ["global", "security", "secret"],
            "action": "warn_and_confirm",
            "logic_score": 4.5, "outcome_score": 4.0
        })

        scenarios.append({
            "name": "cmd_line_unusual",
            "type": "interception",
            "condition": "op == shell AND ('rm -rf' in cmd OR 'rd /s' in cmd OR 'del /f' in cmd)",
            "severity": "critical",
            "tags": ["global", "irreversible", "shell"],
            "action": "block_execution; require_explicit_approval",
            "logic_score": 5.0, "outcome_score": 5.0
        })

        scenarios.append({
            "name": "large_scale_install",
            "type": "interception",
            "condition": "cmd contains 'install'",
            "severity": "medium",
            "tags": ["global", "dependency"],
            "action": "confirm_and_log",
            "logic_score": 3.5, "outcome_score": 3.5
        })

        # Success patterns
        scenarios.append({
            "name": "pip_install_workflow",
            "type": "pattern",
            "condition": "pip install",
            "severity": "low",
            "tags": ["workflow", "python"],
            "action": "suggest_venv_check",
            "logic_score": 3.0, "outcome_score": 4.0,
            "pattern_name": "pip_install_best_practice"
        })

        scenarios.append({
            "name": "git_commit_workflow",
            "type": "pattern",
            "condition": "git commit",
            "severity": "low",
            "tags": ["workflow", "git"],
            "action": "suggest_review_before_commit",
            "logic_score": 3.0, "outcome_score": 4.0,
            "pattern_name": "git_commit_review"
        })

        scenarios.append({
            "name": "file_write_review",
            "type": "pattern",
            "condition": "op == file_write AND length > 1000",
            "severity": "low",
            "tags": ["workflow", "quality"],
            "action": "suggest_post_review",
            "logic_score": 3.0, "outcome_score": 3.5,
            "pattern_name": "post_write_review"
        })

        scenarios.append({
            "name": "test_before_push",
            "type": "pattern",
            "condition": "git push",
            "severity": "low",
            "tags": ["workflow", "git", "quality"],
            "action": "suggest_run_tests",
            "logic_score": 3.5, "outcome_score": 3.5,
            "pattern_name": "test_before_push"
        })

        return scenarios

    def _generate_skeleton(self, scenario, portfolio, macro_data):
        return {
            "scenario": scenario["name"],
            "type": scenario["type"],
            "condition": scenario["condition"],
            "severity": scenario["severity"],
            "tags": scenario["tags"],
            "action": scenario["action"],
            "logic_score": scenario["logic_score"],
            "outcome_score": scenario["outcome_score"],
            "pattern_name": scenario.get("pattern_name", ""),
        }

    def _validate_with_history(self, skeleton):
        kws = self._extract_keywords(skeleton.get("condition", ""))
        scores = []
        for r in self.rule_engine.get_interceptions(active_only=True):
            rk = self._extract_keywords(r.trigger_condition)
            if set(kws) & set(rk):
                scores.append(r.confidence)
        return sum(scores) / len(scores) if scores else 3.0

    def _extract_keywords(self, text):
        ws = re.findall(r"[\w_]{2,}", text)
        sw = {"the","and","or","in","for","is","to","of","a","an",
              "this","that","with","from","by","at","on","not","are",
              "was","be","has","have","do","does","true","false"}
        return [w.lower() for w in ws if w.lower() not in sw and len(w) >= 2]

    def _package_template(self, skeleton, scenario):
        now = datetime.now().isoformat()
        bid = "wargame_" + scenario["name"] + "_" + uuid4().hex[:6]
        conf = skeleton["logic_score"] * 0.6 + skeleton["outcome_score"] * 0.4
        if scenario["type"] == "interception":
            return {
                "type": "interception", "id": bid,
                "trigger_condition": skeleton["condition"], "action": skeleton["action"],
                "severity": skeleton["severity"], "tags": skeleton["tags"],
                "logic_score": skeleton["logic_score"], "outcome_score": skeleton["outcome_score"],
                "confidence": conf, "source": "war_game", "lifecycle_status": "active", "created_at": now
            }
        return {
            "type": "pattern", "id": bid,
            "pattern_name": skeleton.get("pattern_name", scenario["name"]),
            "trigger_scenario": skeleton["condition"], "decision_logic": skeleton["action"],
            "micro_template": skeleton["action"][:50], "source": "war_game",
            "lifecycle_status": "active", "logic_score": skeleton["logic_score"],
            "outcome_score": skeleton["outcome_score"], "confidence": conf, "created_at": now
        }

    def _cache_template(self, template):
        if template["type"] == "interception":
            for r in self.rule_engine.get_interceptions(active_only=False):
                if r.trigger_condition == template["trigger_condition"]:
                    return
            self.rule_engine.add_interception(InterceptionRule(
                id=template["id"],
                trigger_condition=template["trigger_condition"],
                action=template["action"], severity=template["severity"],
                tags=template["tags"], logic_score=template["logic_score"],
                outcome_score=template["outcome_score"],
                confidence=template["confidence"], source=template["source"],
                lifecycle_status=template["lifecycle_status"],
                created_at=template["created_at"]))
        else:
            for p in self.rule_engine.get_patterns(active_only=False):
                if p.trigger_scenario == template["trigger_scenario"]:
                    return
            self.rule_engine.add_pattern(SuccessPattern(
                id=template["id"],
                pattern_name=template["pattern_name"],
                trigger_scenario=template["trigger_scenario"],
                decision_logic=template["decision_logic"],
                micro_template=template["micro_template"],
                source=template["source"], logic_score=template["logic_score"],
                outcome_score=template["outcome_score"],
                confidence=template["confidence"],
                lifecycle_status=template["lifecycle_status"],
                created_at=template["created_at"]))