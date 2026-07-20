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

        total = rule.triggered_count + getattr(rule, 'ignored_count', 0)
        if total > 0:
            ignore_rate = getattr(rule, 'ignored_count', 0) / total
            if ignore_rate > self.soft_elimination_threshold:
                old_conf = rule.confidence
                rule.confidence = rule.confidence * self.decay_factor
                if rule.lifecycle_status == "active":
                    rule.lifecycle_status = "deprecating"

                self._save_rule(rule, rule_type,
                                ignored_count=getattr(rule, 'ignored_count', 0),
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
                        ignored_count=getattr(rule, 'ignored_count', 0),
                        last_ignored=rule.last_ignored
                        )
        return {"action": "updated", "ignore_count": getattr(rule, 'ignored_count', 0)}

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

    
    def _strikes_db_path(self):
        import os
        return os.path.join(os.path.dirname(os.path.dirname(__file__)), "var", "state", "strikes_db.json")

    def _load_strikes_db(self):
        import os,json
        path = self._strikes_db_path()
        if not os.path.exists(path):
            return {}
        try:
            with open(path, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return {}

    def _save_strikes_db(self, db):
        import os,json
        path = self._strikes_db_path()
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            json.dump(db, f, ensure_ascii=False, indent=2)

    def record_self_error(self, error_type, detail='', task_context=None):
        import datetime as _dt
        if task_context is None:
            task_context = {}
        key = 'self_error_' + error_type
        now = _dt.datetime.now().isoformat()

        db = self._load_strikes_db()
        if error_type not in db:
            db[error_type] = {'count': 0, 'first_seen': now, 'last_seen': now,
                              'last_detail': detail,
                              'severity': task_context.get('severity', 'high'),
                              'details': []}
        entry = db[error_type]
        entry['count'] += 1
        entry['last_seen'] = now
        entry['last_detail'] = detail
        if len(entry.get('details', [])) < 10:
            entry.setdefault('details', []).append({'ts': now, 'detail': detail[:60]})
        self._save_strikes_db(db)
        sn = entry['count']

        rule = self.rule_engine.get_interception_by_id(key) if hasattr(self, 'rule_engine') else None
        if rule is None and sn == 1:
            from rule_engine import InterceptionRule
            nr = InterceptionRule(id=key, trigger_condition='error_type=='+repr(error_type),
                action='self_check_and_avoid', severity=task_context.get('severity','high'),
                tags=['self_error','一二不过三'], logic_score=4.0, outcome_score=3.0, confidence=4.0,
                source='auto_self_error', lifecycle_status='active', created_at=now,
                triggered_count=sn, ignored_count=0, override_count=0)
            self.rule_engine.add_interception(nr)
            self.rule_engine.save_all()
            return {'action':'first_error_rule_created','rule_id':key,'strike':sn,
                    'warning':('[一二不过三] 第{}次犯{}，已创建拦截规则'.format(sn, error_type))}

        if rule:
            rule.triggered_count = sn
            rule.last_triggered = now
            if sn == 2:
                rule.confidence = min(5.0, (rule.confidence or 4.0) + 1.0)
                self.rule_engine.update_interception(rule.id, triggered_count=sn,
                    last_triggered=now, confidence=rule.confidence)
                self.rule_engine.save_all()
                return {'action':'second_error_reinforce','rule_id':key,'strike':sn,
                        'warning':('[一二不过三] 第{}次犯{}，规则已加固'.format(sn, error_type))}

            if sn >= 3:
                rule.lifecycle_status = 'alerting'
                op = self._strikes_db_path().replace('strikes_db.json','dgen_override.json')
                od = {'blocked_error_type':error_type,'strike_count':sn,
                      'blocked_at':now,'last_detail':detail,
                      'reason':'一二不过三: '+error_type+' 已触发'+str(sn)+'次，自动阻止'}
                try:
                    with open(op,'w',encoding='utf-8') as f:
                        json.dump(od,f,ensure_ascii=False,indent=2)
                except Exception:
                    pass
                self.rule_engine.update_interception(rule.id, triggered_count=sn,
                    last_triggered=now, lifecycle_status='alerting')
                self.rule_engine.save_all()
                return {'action':'third_error_force_stop','rule_id':key,'strike':sn,
                        'warning':('[一二不过三] 第{}次犯{}！强制停止，需手动确认'.format(sn, error_type))}

        return {'action':'error_incremented','rule_id':key,'strike':sn}

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
        你没说没做 → 三错阀兜底
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
        
        # ② 无行为可观测（既没说也没做）→ 三错阀兜底
        #  复用 ignored_count 追踪沉默次数
        rule.ignored_count += 1
        rule.last_ignored = datetime.now().isoformat()
        
        if getattr(rule, 'ignored_count', 0) == 1:
            # 第1次：挂起标记
            self._save_rule(rule, rule_type,
                ignored_count=getattr(rule, 'ignored_count', 0),
                last_ignored=rule.last_ignored)
            self.rule_engine.save_all()
            return {"action": "silent_pending", "rule_id": rule_id,
                    "message": "用户沉默且无行为，规则挂起待定。下次同场景触发时再问。",
                    "silent_hits": getattr(rule, 'ignored_count', 0)}
        
        elif getattr(rule, 'ignored_count', 0) == 2:
            # 第2次：衰减
            old_conf = rule.confidence
            rule.confidence = rule.confidence * 0.95
            if rule.lifecycle_status == "active":
                rule.lifecycle_status = "cold_standby"
            self._save_rule(rule, rule_type,
                ignored_count=getattr(rule, 'ignored_count', 0),
                last_ignored=rule.last_ignored,
                confidence=rule.confidence,
                lifecycle_status=rule.lifecycle_status)
            self.rule_engine.save_all()
            return {"action": "silent_decayed", "rule_id": rule_id,
                    "new_confidence": rule.confidence,
                    "old_confidence": old_conf,
                    "message": f"沉默无行为x2，置信度衰减至{rule.confidence:.2f}，标记cold_standby",
                    "silent_hits": getattr(rule, 'ignored_count', 0)}
        
        else:
            # 第3次及以上：通知用户
            self._save_rule(rule, rule_type,
                ignored_count=getattr(rule, 'ignored_count', 0),
                last_ignored=rule.last_ignored)
            self.rule_engine.save_all()
            return {"action": "silent_alert", "rule_id": rule_id,
                    "message": f"一二不过三：规则{rule_id}已沉默被忽略{getattr(rule, 'ignored_count', 0)}次，请确认保留或删除。",
                    "silent_hits": getattr(rule, 'ignored_count', 0)}

    def get_ignored_rules(self, threshold: float = None) -> list:
        """获取被无视的规则列表"""
        if threshold is None:
            threshold = self.soft_elimination_threshold

        ignored_list = []
        all_rules = self.rule_engine.get_interceptions(active_only=False)

        for rule in all_rules:
            total = getattr(rule, 'triggered_count', 0) + getattr(rule, 'ignored_count', 0)
            if total > 0:
                ignore_rate = getattr(rule, 'ignored_count', 0) / total
                if ignore_rate > threshold:
                    ignored_list.append({
                        "id": rule.id,
                        "name": getattr(rule, "pattern_name", rule.trigger_condition),
                        "type": "interception" if hasattr(rule, "severity") else "pattern",
                        "ignore_rate": ignore_rate,
                        "ignored_count": getattr(rule, 'ignored_count', 0),
                        "triggered_count": rule.triggered_count
                    })

        return sorted(ignored_list, key=lambda x: x["ignore_rate"], reverse=True)
