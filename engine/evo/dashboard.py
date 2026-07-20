#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
diegin-evo 宏观健康度仪表盘
迭进自主生成和维护
"""

import re
from datetime import datetime
from typing import List, Dict, Any
from rule_engine import RuleEngine, InterceptionRule, SuccessPattern


class HealthDashboard:
    """健康度仪表盘"""

    def __init__(self, rule_engine: RuleEngine):
        self.rule_engine = rule_engine
        self._scenario_keywords = [
            "宏观", "行业", "项目", "政策", "数据", "资源", "情绪",
            "稳定性", "波动率", "可用性", "估值", "状态", "风险"
        ]

    def generate_report(self) -> Dict:
        """生成健康度报告"""
        interceptions = self.rule_engine.get_interceptions(active_only=False)
        patterns = self.rule_engine.get_patterns(active_only=False)
        all_rules = interceptions + patterns

        conflict_count = self._count_conflicts()
        entropy = round((len(all_rules) + conflict_count) / max(len(set(r.id for r in all_rules)), 1), 3)

        snr = self._calculate_snr(interceptions)
        capacity = self._count_scenarios(all_rules)
        satisfaction = self._calculate_satisfaction(all_rules)
        redundancy = self._calculate_redundancy(all_rules)

        report = {
            "generated_at": datetime.now().isoformat(),
            "total_rules": len(all_rules),
            "active_rules": len([r for r in all_rules if r.lifecycle_status == "active"]),
            "deprecating_rules": len([r for r in all_rules if r.lifecycle_status == "deprecating"]),
            "archived_rules": len([r for r in all_rules if r.lifecycle_status == "archived"]),
            "cached_rules": len([r for r in all_rules if r.lifecycle_status == "cached"]),
            "cognitive_entropy": round(entropy, 3),
            "entropy_status": self._status_entropy(entropy),
            "decision_snr": round(snr, 3),
            "snr_status": self._status_snr(snr),
            "strategy_capacity": capacity,
            "capacity_status": self._status_capacity(capacity),
            "satisfaction": round(satisfaction, 3),
            "satisfaction_status": self._status_satisfaction(satisfaction),
            "redundancy": round(redundancy, 3),
            "recommendations": self._generate_recommendations(
                entropy, snr, capacity, satisfaction, redundancy
            )
        }

        return report

    def _count_conflicts(self) -> int:
        """统计冲突次数（从判例库中）"""
        precedents = self.rule_engine.get_precedents()
        return len([p for p in precedents if p.resolution == "auto_degraded"])

    def _calculate_snr(self, interceptions: List[InterceptionRule]) -> float:
        """计算决策信噪比"""
        total_triggers = sum(r.triggered_count for r in interceptions)
        if total_triggers == 0:
            return 1.0
        effective = sum(r.triggered_count - r.ignored_count - r.override_count
                        for r in interceptions)
        return max(0, effective / total_triggers)

    def _count_scenarios(self, rules: list) -> int:
        """统计规则覆盖的场景种类"""
        scenarios = set()
        for r in rules:
            text = getattr(r, "trigger_scenario", None)
            if text is None:
                text = getattr(r, "trigger_condition", "")
            found = [kw for kw in self._scenario_keywords if kw in text]
            scenarios.update(found if found else ["通用"])
        return len(scenarios)

    def _calculate_satisfaction(self, rules: list) -> float:
        """计算隐性偏好满意度（仅统计拦截规则，成功模式无ignored_count）"""
        total_ignored = sum(getattr(r, 'ignored_count', 0) for r in rules)
        total_triggered = sum(getattr(r, 'triggered_count', 0) for r in rules)
        if total_triggered == 0:
            return 1.0
        return 1 - (total_ignored / total_triggered)

    def _calculate_redundancy(self, rules: list) -> float:
        """计算规则库冗余度（仅统计拦截规则，成功模式无ignored_count）"""
        if not rules:
            return 0
        interceptions = [r for r in rules if hasattr(r, 'ignored_count')]
        if not interceptions:
            return 0
        ignored_rules = [r for r in interceptions if r.ignored_count > 0]
        return len(ignored_rules) / len(interceptions)

    def _status_entropy(self, entropy: float) -> str:
        if entropy > 10:
            return "[WARN] 过高（规则冲突频繁，建议剪枝）"
        elif entropy > 5:
            return "[WARN] 偏高（建议关注规则质量）"
        return "[OK] 健康"

    def _status_snr(self, snr: float) -> str:
        if snr < 0.3:
            return "[WARN] 过低（大量规则未被采纳，建议审查）"
        elif snr < 0.5:
            return "[WARN] 偏低（建议优化规则质量）"
        return "[OK] 健康"

    def _status_capacity(self, capacity: int) -> str:
        if capacity < 3:
            return "[WARN] 不足（规则覆盖场景过少）"
        elif capacity < 5:
            return "[WARN] 一般（建议增加场景覆盖）"
        return "[OK] 充足"

    def _status_satisfaction(self, satisfaction: float) -> str:
        if satisfaction < 0.2:
            return "[WARN] 极低（用户基本不采纳规则，建议全量审查）"
        elif satisfaction < 0.5:
            return "[WARN] 偏低（用户采纳率不足一半）"
        return "[OK] 良好"



    def read_phase_gate(self):
        import os
        fpath = os.path.join(os.path.dirname(os.path.dirname(__file__)), "var", "state", "phase_state.json")
        if not os.path.exists(fpath):
            return {"status": "no_session", "phases": {}}
        try:
            with open(fpath, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return {"status": "error", "phases": {}}

    def phase_gate_display(self):
        data = self.read_phase_gate()
        phases = data.get("phases", {})
        chain = ["session_start", "pre_reply", "pre_tool", "post_tool", "stop_verification"]
        sym_map = {"passed": "+", "completed": "+", "verified": "+",
                   "stalled": "X", "error": "X", "hard_floor_blocked": "!"}
        rows = []
        rows.append("-" * 36)
        rows.append("  Phase Gate Chain")
        rows.append("-" * 36)
        ok = True
        for p in chain:
            info = phases.get(p, {})
            st = info.get("status", "missing") if info else "missing"
            ts = info.get("ts", "")[:19] if info else ""
            sym = sym_map.get(st, "o")
            if st == "missing":
                ok = False
                rows.append("  " + sym + " " + p + " (pending)")
            elif st in ("stalled", "error", "hard_floor_blocked"):
                ok = False
                rows.append("  " + sym + " " + p + " [" + st.upper() + "] " + ts)
            else:
                rows.append("  " + sym + " " + p + " [" + st + "] " + ts)
        rows.append("-" * 36)
        rows.append("  " + ("OK" if ok else "WARN") + " Chain " + ("complete" if ok else "incomplete, check above"))
        rows.append("-" * 36)
        return '\n'.join(rows)

    def _generate_recommendations(self, entropy: float, snr: float,
                                   capacity: int, satisfaction: float,
                                   redundancy: float) -> List[str]:
        recommendations = []
        if entropy > 5:
            recommendations.append("[TOOL] 认知熵值偏高，建议执行全局规则剪枝")
        if snr < 0.3:
            recommendations.append("[TOOL] 决策信噪比过低，建议审查被频繁无视的规则")
        if capacity < 3:
            recommendations.append("[CHART] 策略容量不足，建议通过沙盘推演生成更多场景模板")
        if satisfaction < 0.2:
            recommendations.append("[TOOL] 隐性偏好满意度极低，建议重置或全量审查规则库")
        if redundancy > 0.3:
            recommendations.append("[TOOL] 规则库冗余度偏高，建议合并相似规则")
        if not recommendations:
            recommendations.append("[OK] 所有指标正常，系统健康运行")
        return recommendations


def run_health_check(rule_engine: RuleEngine) -> Dict:
    """执行健康度检查（外部调用接口）"""
    dashboard = HealthDashboard(rule_engine)
    report = dashboard.generate_report()

    print("\n" + "=" * 50)
    print("[DATA] 智能体健康度报告")
    print("=" * 50)
    print(f"生成时间: {report['generated_at']}")
    print(f"规则总数: {report['total_rules']} (活跃: {report['active_rules']}, 缓存: {report['cached_rules']})")
    print(f"认知熵值: {report['cognitive_entropy']} {report['entropy_status']}")
    print(f"决策信噪比: {report['decision_snr']} {report['snr_status']}")
    print(f"策略容量: {report['strategy_capacity']} {report['capacity_status']}")
    print(f"隐性满意度: {report['satisfaction']:.1%} {report['satisfaction_status']}")
    print("\n[LIST] 建议:")
    for rec in report['recommendations']:
        print(f"  {rec}")
    print("=" * 50)

    return report
