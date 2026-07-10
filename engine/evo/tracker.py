#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
diegin-evo 隐性偏好追踪器
迭进自主生成和维护
"""

from datetime import datetime
from typing import Dict, Optional, Any

from rule_engine import InterceptionRule, SuccessPattern, RuleEngine


class BehaviorTracker:
    """隐性偏好追踪器"""

    def __init__(self, rule_engine: RuleEngine):
        self.rule_engine = rule_engine
        self.soft_elimination_threshold = 0.8
        self.decay_factor = 0.9

    def _resolve_rule(self, rule_id: str):
        """查找规则（拦截规则优先，成功模式兜底）"""
        rule = self.rule_engine.get_interception_by_id(rule_id)
        if rule:
            return rule, "interception"
        pattern = self.rule_engine.get_pattern_by_id(rule_id)
        if pattern:
            return pattern, "pattern"
        return None, None

    def _save_rule(self, rule, rule_type: str, **kwargs):
        """根据规则类型调用对应的 update 方法"""
        if rule_type == "interception":
            self.rule_engine.update_interception(rule.id, **kwargs)
        else:
            self.rule_engine.update_pattern(rule.id, **kwargs)

    def record_ignore(self, rule_id: str) -> Dict:
        """
        记录规则被无视
        返回: {"action": "updated" | "soft_eliminated", "new_confidence": float}
        """
        rule, rule_type = self._resolve_rule(rule_id)
        if not rule:
            return {"action": "not_found"}

        rule.ignored_count += 1
        rule.last_ignored = datetime.now().isoformat()

        total = rule.triggered_count + rule.ignored_count
        if total > 0:
            ignore_rate = rule.ignored_count / total
            if ignore_rate > self.soft_elimination_threshold:
                old_conf = rule.confidence
                rule.confidence = rule.confidence * self.decay_factor
                if rule.lifecycle_status == "active":
                    rule.lifecycle_status = "deprecating"

                self._save_rule(rule, rule_type,
                                ignored_count=rule.ignored_count,
                                last_ignored=rule.last_ignored,
                                confidence=rule.confidence,
                                lifecycle_status=rule.lifecycle_status
                                )

                return {
                    "action": "soft_eliminated",
                    "new_confidence": rule.confidence,
                    "old_confidence": old_conf,
                    "ignore_rate": ignore_rate
                }

        self._save_rule(rule, rule_type,
                        ignored_count=rule.ignored_count,
                        last_ignored=rule.last_ignored
                        )
        return {"action": "updated", "ignore_count": rule.ignored_count}

    def record_override(self, rule_id: str) -> Dict:
        """记录规则被手动覆盖"""
        rule, rule_type = self._resolve_rule(rule_id)
        if not rule:
            return {"action": "not_found"}

        rule.override_count += 1
        self._save_rule(rule, rule_type, override_count=rule.override_count)
        return {"action": "updated", "override_count": rule.override_count}

    def record_triggered(self, rule_id: str) -> Dict:
        """记录规则被触发"""
        rule, rule_type = self._resolve_rule(rule_id)
        if not rule:
            return {"action": "not_found"}

        rule.triggered_count += 1
        rule.last_triggered = datetime.now().isoformat()

        self._save_rule(rule, rule_type,
                        triggered_count=rule.triggered_count,
                        last_triggered=rule.last_triggered
                        )
        return {"action": "updated", "triggered_count": rule.triggered_count}

    def record_self_error(self, error_type: str, detail: str, task_context: Dict = None) -> Dict:
        """
        一二不过三：记录自身同类错误
        第1次→创建拦截规则
        第2次→加固（置信度+1）
        第3次→通知用户干预
        """
        if task_context is None:
            task_context = {}
        
        key = f"self_error_{error_type}"
        
        # 检查是否已有此类型错误的拦截规则
        rule = self.rule_engine.get_interception_by_id(key)
        
        if rule is None:
            # 第1次：创建拦截规则
            new_rule = InterceptionRule(
                id=key,
                trigger_condition=error_type,
                action="self_check_and_avoid",
                severity="high",
                tags=["self_error", "一二不过三"],
                logic_score=4.0,
                outcome_score=3.0,
                confidence=4.0,
                source="auto_self_error",
                lifecycle_status="active",
                created_at=datetime.now().isoformat(),
                triggered_count=1,
                ignored_count=0,
                override_count=0
            )
            self.rule_engine.add_interception(new_rule)
            self.rule_engine.save_all()
            return {"action": "first_error_rule_created", "rule_id": key, "warning": f"第1次犯{error_type}，已创建拦截规则"}
        
        # 第2次及以后
        rule.triggered_count += 1
        rule.last_triggered = datetime.now().isoformat()
        
        if rule.triggered_count == 2:
            # 第2次：加固
            rule.confidence = min(5.0, rule.confidence + 1.0)
            self.rule_engine.update_interception(rule.id,
                triggered_count=rule.triggered_count,
                last_triggered=rule.last_triggered,
                confidence=rule.confidence)
            self.rule_engine.save_all()
            return {"action": "second_error_reinforce", "rule_id": key,
                    "warning": f"第2次犯{error_type}，规则已加固到conf={rule.confidence}"}
        
        if rule.triggered_count >= 3:
            # 第3次：通知用户
            rule.lifecycle_status = "alerting"
            self.rule_engine.update_interception(rule.id,
                triggered_count=rule.triggered_count,
                last_triggered=rule.last_triggered,
                lifecycle_status="alerting")
            self.rule_engine.save_all()
            return {"action": "third_error_alert", "rule_id": key,
                    "alert": f"一二不过三触发：{error_type}已犯第{rule.triggered_count}次，需要你介入"}
        
        return {"action": "counted", "triggered": rule.triggered_count}

    def record_user_feedback(self, rule_id: str, feedback: str, user_action: Optional[str] = None) -> Dict[str, Any]:
        """
        用户反馈三态模型 + 沉默+一二不过三完整决策树
        
        feedback: 'agree' | 'veto' | 'silent'
        user_action: 'consistent' | 'inconsistent' | None
          - consistent: 用户行为与规则方向一致
          - inconsistent: 用户行为与规则方向相反
          - None: 无行为可观测
        
        决策逻辑（定稿版）：
        你说 → 以你为准
        你沉默 → 看你怎么做
        你没说没做 → 一二不过三兜底
        """
        rule, rule_type = self._resolve_rule(rule_id)
        if not rule:
            return {"action": "not_found"}
        
        # ── 分支一：用户明确表态 ──
        if feedback == "agree":
            rule.confidence = min(5.0, rule.confidence + 0.5)
            rule.triggered_count += 1
            rule.last_triggered = datetime.now().isoformat()
            rule.lifecycle_status = "active"
            self._save_rule(rule, rule_type,
                confidence=rule.confidence,
                triggered_count=rule.triggered_count,
                last_triggered=rule.last_triggered,
                lifecycle_status="active")
            self.rule_engine.save_all()
            return {"action": "confirmed", "rule_id": rule_id,
                    "new_confidence": rule.confidence,
                    "source": "用户明确表态", "signal": "agree"}
        
        if feedback == "veto":
            # 一次否决即生效
            old_conf = rule.confidence
            rule.confidence = rule.confidence * 0.7
            rule.override_count += 1
            rule.last_triggered = datetime.now().isoformat()
            self._save_rule(rule, rule_type,
                confidence=rule.confidence,
                override_count=rule.override_count,
                last_triggered=rule.last_triggered)
            self.rule_engine.save_all()
            return {"action": "vetoed", "rule_id": rule_id,
                    "new_confidence": rule.confidence,
                    "old_confidence": old_conf,
                    "source": "用户明确表态", "signal": "veto"}
        
        # ── 分支二：用户沉默（反馈==silent）─ 看你做的 ──
        
        # ① 有行为可观测
        if user_action == "consistent":
            rule.confidence = min(5.0, rule.confidence + 0.3)
            rule.triggered_count += 1
            rule.last_triggered = datetime.now().isoformat()
            self._save_rule(rule, rule_type,
                confidence=rule.confidence,
                triggered_count=rule.triggered_count,
                last_triggered=rule.last_triggered)
            self.rule_engine.save_all()
            return {"action": "inferred_agree", "rule_id": rule_id,
                    "new_confidence": rule.confidence,
                    "source": "沉默+行为推定", "signal": "agree_from_consistent_action"}
        
        if user_action == "inconsistent":
            old_conf = rule.confidence
            rule.confidence = rule.confidence * 0.8
            rule.override_count += 1
            rule.last_triggered = datetime.now().isoformat()
            self._save_rule(rule, rule_type,
                confidence=rule.confidence,
                override_count=rule.override_count,
                last_triggered=rule.last_triggered)
            self.rule_engine.save_all()
            return {"action": "inferred_veto", "rule_id": rule_id,
                    "new_confidence": rule.confidence,
                    "old_confidence": old_conf,
                    "source": "沉默+行为推定", "signal": "veto_from_inconsistent_action"}
        
        # ② 无行为可观测（既没说也没做）→ 一二不过三兜底
        #  复用 ignored_count 追踪沉默次数
        rule.ignored_count += 1
        rule.last_ignored = datetime.now().isoformat()
        
        if rule.ignored_count == 1:
            # 第1次：挂起标记
            self._save_rule(rule, rule_type,
                ignored_count=rule.ignored_count,
                last_ignored=rule.last_ignored)
            self.rule_engine.save_all()
            return {"action": "silent_pending", "rule_id": rule_id,
                    "message": "用户沉默且无行为，规则挂起待定。下次同场景触发时再问。",
                    "silent_hits": rule.ignored_count}
        
        elif rule.ignored_count == 2:
            # 第2次：衰减
            old_conf = rule.confidence
            rule.confidence = rule.confidence * 0.95
            if rule.lifecycle_status == "active":
                rule.lifecycle_status = "cold_standby"
            self._save_rule(rule, rule_type,
                ignored_count=rule.ignored_count,
                last_ignored=rule.last_ignored,
                confidence=rule.confidence,
                lifecycle_status=rule.lifecycle_status)
            self.rule_engine.save_all()
            return {"action": "silent_decayed", "rule_id": rule_id,
                    "new_confidence": rule.confidence,
                    "old_confidence": old_conf,
                    "message": f"沉默无行为x2，置信度衰减至{rule.confidence:.2f}，标记cold_standby",
                    "silent_hits": rule.ignored_count}
        
        else:
            # 第3次及以上：通知用户
            self._save_rule(rule, rule_type,
                ignored_count=rule.ignored_count,
                last_ignored=rule.last_ignored)
            self.rule_engine.save_all()
            return {"action": "silent_alert", "rule_id": rule_id,
                    "message": f"一二不过三：规则{rule_id}已沉默被忽略{rule.ignored_count}次，请确认保留或删除。",
                    "silent_hits": rule.ignored_count}

    def get_ignored_rules(self, threshold: float = None) -> list:
        """获取被无视的规则列表"""
        if threshold is None:
            threshold = self.soft_elimination_threshold

        ignored_list = []
        all_rules = (self.rule_engine.get_interceptions(active_only=False) +
                     self.rule_engine.get_patterns(active_only=False))

        for rule in all_rules:
            total = rule.triggered_count + rule.ignored_count
            if total > 0:
                ignore_rate = rule.ignored_count / total
                if ignore_rate > threshold:
                    ignored_list.append({
                        "id": rule.id,
                        "name": getattr(rule, "pattern_name", rule.trigger_condition),
                        "type": "interception" if hasattr(rule, "severity") else "pattern",
                        "ignore_rate": ignore_rate,
                        "ignored_count": rule.ignored_count,
                        "triggered_count": rule.triggered_count
                    })

        return sorted(ignored_list, key=lambda x: x["ignore_rate"], reverse=True)
