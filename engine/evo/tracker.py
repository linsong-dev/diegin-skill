#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
diegin-evo 隐性偏好追踪器
迭进自主生成和维护
"""

from datetime import datetime
from typing import Dict, Optional, Any

from rule_engine import InterceptionRule, SuccessPattern, RuleEngine
import os, json


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
        return os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "var", "state", "strikes_db.json")

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


    def _overrides_path(self):
        """Path to multi-entry override file (array format)"""
        import os
        return self._strikes_db_path().replace("strikes_db.json", "dgen_overrides.json")

    def _load_overrides(self):
        """Load overrides array from dgen_overrides.json"""
        import os, json
        path = self._overrides_path()
        if not os.path.exists(path):
            return []
        try:
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
                return data if isinstance(data, list) else []
        except Exception:
            return []

    def _save_overrides(self, overrides):
        """Save overrides array to dgen_overrides.json (also sync legacy dgen_override.json)"""
        import os, json
        path = self._overrides_path()
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            json.dump(overrides, f, ensure_ascii=False, indent=2)
        # Also write legacy single-file for backward compat (first non-escalated, else first escalated)
        if overrides:
            # Pick active block (prefer escalated for backward compat safety)
            legacy = overrides[0]
            for entry in overrides:
                if entry.get("escalated"):
                    legacy = entry
                    break
            legacy_path = path.replace("dgen_overrides.json", "dgen_override.json")
            with open(legacy_path, "w", encoding="utf-8") as f:
                json.dump(legacy, f, ensure_ascii=False, indent=2)

    def _analyze_cause(self, error_type, detail):
        """归因过滤：判断错误是内生惯性还是外生变量"""
        ex_keywords = [
            "network","timeout","connection refused","permission denied",
            "rate limit","not found","no such file","disk full",
            "too many open files","authentication","unauthorized",
            "git clone","git fetch","pip install","npm install",
            "429","502","503","econnrefused","etimedout",
        ]
        in_keywords = [
            "encoding","write error","syntax","compile",
            "indentation","typeerror","valueerror","keyerror",
            "self_error","image_url","test_","import",
        ]
        dl = (detail or "").lower()
        el = (error_type or "").lower()
        for kw in ex_keywords:
            if kw in el or kw in dl:
                return {"verdict":"external","kw":kw,"reason":"环境/外因问题"}
        for kw in in_keywords:
            if kw in el or kw in dl:
                return {"verdict":"internal","kw":kw,"reason":"AI自身行为惯性"}
        return {"verdict":"internal","kw":None,"reason":"默认保守视为内生惯性"}


    def notify_shousan(self, error_type: str, detail: str, cause: dict) -> dict:
        """一二不过三(strike) -> 守三(复盘触发)
        在第2次strike阻断后自动触发守三复盘，生成一条预防性规则写入规则库。"""
        from rule_engine import InterceptionRule
        import datetime as _dt
        now = _dt.datetime.now()
        
        # 止观门检查: 如果该error_type已被close，跳过守三复盘
        try:
            from closure import get_closure
            cl = get_closure()
            if cl.is_closed("self_error_" + error_type):
                print(f"  [CLOSURE] 止观门: {error_type} 已封存，守三跳过")
                return {"rule_id": "", "trigger": "", "action": "", "skipped": "closed"}
        except Exception:
            pass
        
        # 守三-攻七时间隔离: 检查攻七是否正在运行
        if getattr(self.rule_engine, "_phase_lock_gongqi", False):
            print("  [PHASE_LOCK] 攻七正在运行，守三跳过本轮")
            return {"boosted": 0, "decayed": 0, "archived": 0, "skipped": "gongqi_running"}
        
        # 缓急律调度: 紧急事务跳过守三深度复盘
        try:
            from pacemaker import get_pacemaker
            pm = get_pacemaker()
            pace = pm.classify({"task_type": "maintenance", "cmd": "shousan_cycle"})
            ch = pace.get("channel", "")
            if ch in ("fast_path", "downtime"):
                print(f"  [PACE] 缓急律: {ch} -> 守三跳过本轮")
                return {"boosted": 0, "decayed": 0, "archived": 0, "skipped": ch}
        except Exception:
            now = _dt.datetime.now()
        
        trigger_map = {
            'encoding_write_corruption': ('op == file_write AND NOT encoding_verified', 'verify_encoding_before_write; if_fail_fix_it'),
            'encoding_error': ('op == file_write AND NOT encoding_verified', 'verify_encoding_before_write; if_fail_fix_it'),
            'git_push_failure': ('op == git_push AND NOT pre_push_verified', 'pre_push_validation; check_git_state'),
            'command_failure': ('op == cmd AND NOT cmd_prechecked', 'dry_run_before_exec; verify_exit_code'),
            'command_timeout': ('op == cmd AND duration > timeout_threshold AND NOT timeout_handled', 'set_timeout; handle_timeout_gracefully'),
        }
        
        matched = False
        trigger = None
        action = None
        for key in trigger_map:
            if key in error_type:
                trigger, action = trigger_map[key]
                matched = True
                break
        
        if not matched:
            clean_type = error_type.replace('self_error_', '').replace('silent_', '')
            if len(clean_type) > 40:
                clean_type = clean_type[:40]
            trigger = f'op_contains({clean_type}) AND NOT prechecked'
            action = f'pre_check_before_{clean_type}; verify_result'
        
        rule_id = f'shousan_review_{error_type}_{_dt.datetime.now().strftime("%Y%m%d_%H%M%S")}'
        
        sev_map = {'internal': 'high', 'external': 'medium'}
        severity = cause.get('verdict', 'internal')
        
        new_rule = InterceptionRule(
            id=rule_id,
            trigger_condition=trigger,
            action=action,
            severity=sev_map.get(severity, 'high'),
            tags=['shousan', 'auto_generated', 'yierbuguosao->shousan', error_type[:30]],
            logic_score=4.0,
            outcome_score=3.5,
            confidence=4.0,
            source='learned',
            source_review=f'auto_generated_by_shousan: {error_type}',
            lifecycle_status='active',
            created_at=now,
        )
        self.rule_engine.add_interception(new_rule, auto_save=True)
        print(f'[SHOUSAN] 守三复盘: 已生成规则 {rule_id} 防止 {error_type}')
        return {'rule_id': rule_id, 'trigger': trigger, 'action': action}

    def notify_gongqi(self, error_type: str, detail: str, fix_rule_id: str = '') -> dict:
        """一二不过三(修复成功) -> 攻七(写入模式)
        在strike阻断并生成预防规则后，自动创建成功模式记录修复经验。
        使修复成果被固化到攻七成功模式库。"""
        from rule_engine import SuccessPattern
        import datetime as _dt
        now = _dt.datetime.now()
        
        # 止观门检查: 如果已封存，跳过攻七写入
        try:
            from closure import get_closure
            cl = get_closure()
            if cl.is_closed("self_error_" + error_type):
                print(f"  [CLOSURE] 止观门: {error_type} 已封存，攻七跳过")
                return {"pattern_id": "", "pattern_name": "", "logic": "", "skipped": "closed"}
        except Exception:
            pass
        
        # 守三-攻七时间隔离: 检查攻七是否正在运行
        if getattr(self.rule_engine, "_phase_lock_gongqi", False):
            print("  [PHASE_LOCK] 攻七正在运行，守三跳过本轮")
            return {"boosted": 0, "decayed": 0, "archived": 0, "skipped": "gongqi_running"}
        
        # 缓急律调度: 紧急事务跳过守三深度复盘
        try:
            from pacemaker import get_pacemaker
            pm = get_pacemaker()
            pace = pm.classify({"task_type": "maintenance", "cmd": "shousan_cycle"})
            ch = pace.get("channel", "")
            if ch in ("fast_path", "downtime"):
                print(f"  [PACE] 缓急律: {ch} -> 守三跳过本轮")
                return {"boosted": 0, "decayed": 0, "archived": 0, "skipped": ch}
        except Exception:
            now = _dt.datetime.now()
        
        pattern_map = {
            'encoding_write_corruption': ('编码写入前验证', 'file_write前检查encoding，确认UTF-8 NoBOM再写入'),
            'encoding_error': ('编码错误预防', '文件操作前验证编码，避免乱码写入'),
            'git_push_failure': ('Git推送前验证', 'git push前先验证仓库状态和网络连接'),
            'command_failure': ('命令执行前预检', '执行命令前先dry-run或验证参数正确性'),
            'command_timeout': ('命令超时处理', '设置超时机制，超时后优雅降级'),
        }
        
        matched = False
        for key in pattern_map:
            if key in error_type:
                pname, logic = pattern_map[key]
                matched = True
                break
        
        if not matched:
            clean_type = error_type.replace('self_error_', '').replace('silent_', '')
            if len(clean_type) > 30:
                clean_type = clean_type[:30]
            pname = f'预防{clean_type}'
            logic = f'{clean_type}操作前预检，避免同类错误'
        
        pattern_id = f'gongqi_fix_{error_type}_{_dt.datetime.now().strftime("%Y%m%d_%H%M%S")}'
        
        new_pattern = SuccessPattern(
            id=pattern_id,
            pattern_name=pname,
            trigger_scenario=f'auto: 修复 {error_type} 成功后的行为模式',
            decision_logic=logic,
            trigger_condition=f'op_contains({error_type.replace("self_error_","").replace("silent_","")})',
            micro_template=f'检查{clean_type if not matched else error_type[:20]}状态，确认无误后执行',
            logic_score=3.5,
            outcome_score=3.5,
            source='learned',
            core_capability=f'auto_generated_by_gongqi: {error_type} via fix_rule={fix_rule_id}',
            lifecycle_status='active',
            created_at=now,
        )
        self.rule_engine.add_pattern(new_pattern)
        print(f'[GONGQI] 攻七强化: 已写入成功模式 {pattern_id} - {pname}')
        return {'pattern_id': pattern_id, 'pattern_name': pname, 'logic': logic}
    def record_self_error(self, error_type, detail='', task_context=None):
        """
        一二不过三·三错阀
        第1次：警告+警觉 → 写 dgen_warning.json，规则标记 alerting
        第2次：阻断 → 写 dgen_override.json，AI 不再执行这类操作
        第3次：不应发生 → 如果发生说明阻断机制出 bug，记录到 strikes_db
        """
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

        # ========== 第1次：警告 + 警觉 ==========
        if sn == 1:
            from rule_engine import InterceptionRule
            if rule is None:
                nr = InterceptionRule(id=key, trigger_condition='error_type=='+repr(error_type),
                    action='self_check_and_avoid', severity=task_context.get('severity','high'),
                    tags=['self_error','一二不过三','warning'], logic_score=4.0, outcome_score=3.0, confidence=4.0,
                    source='auto_self_error', lifecycle_status='alerting', created_at=now,
                    triggered_count=sn, ignored_count=0, override_count=0)
                self.rule_engine.add_interception(nr)
            # 写 warning 标记：告知 AI "这个错误已被记录，下次要警惕"
            op = self._strikes_db_path().replace('strikes_db.json','dgen_warning.json')
            od = {'warned_error_type':error_type,'strike_count':sn,
                  'warned_at':now,'last_detail':detail,
                  'message':'一二不过三: '+error_type+' 已出现第1次，请注意防止再犯'}
            try:
                os.makedirs(os.path.dirname(op), exist_ok=True)
                with open(op,'w',encoding='utf-8') as f:
                    json.dump(od,f,ensure_ascii=False,indent=2)
            except Exception:
                pass
            self.rule_engine.save_all()
            return {'action':'first_warning','rule_id':key,'strike':sn,
                    'warning':'⚠️ 一二不过三: '+error_type+' 已出现第1次，系统已警觉，注意防止再犯'}

        # ========== 第2次：阻断 ==========
        # ========== 第2次：阻断（先去伪存真·归因过滤）==========
        if sn == 2:
            cause = self._analyze_cause(error_type, detail)
            is_internal = cause["verdict"] == "internal"
            if not is_internal:
                print("[TRACKER] external cause, skip block: " + error_type)
                return {"action":"external_skip","rule_id":key,"strike":sn,
                        "cause":cause,
                        "message":"一二不过三: "+error_type+" 第2次触发但判定为外生变量，不做阻断"}
            if rule:
                rule.triggered_count = sn
                rule.last_triggered = now
                rule.lifecycle_status = 'blocking'
                conf = getattr(rule, 'confidence', 4.0) or 4.0
                rule.confidence = min(5.0, conf + 0.5)
                self.rule_engine.update_interception(rule.id,
                    triggered_count=sn, last_triggered=now,
                    confidence=rule.confidence, lifecycle_status='blocking')
            # 写入 dgen_overrides.json (数组格式，支持多类型同时阻断)
            overrides = self._load_overrides()
            existing_idx = None
            for idx, entry in enumerate(overrides):
                if entry.get("blocked_error_type") == error_type:
                    existing_idx = idx
                    break
            new_entry = {
                "blocked_error_type": error_type,
                "strike_count": sn,
                "blocked_at": now,
                "last_detail": detail,
                "cause": cause,
                "escalated": False,
                "reason": "一二不过三: " + error_type + " 已触发2次，归因为内生惯性，自动阻断",
            }
            if existing_idx is not None:
                overrides[existing_idx] = new_entry
            else:
                overrides.append(new_entry)
            self._save_overrides(overrides)
            self.rule_engine.save_all()
            # 一二不过三->守三：strike第2次阻断后自动触发守三复盘
            shousan_result = self.notify_shousan(error_type, detail, cause)
            fix_rule_id = shousan_result.get("rule_id", "")
            self.notify_gongqi(error_type, detail, fix_rule_id)
            return {"action":"second_block","rule_id":key,"strike":sn,
                    "cause":cause,
                    "warning":"一二不过三: "+error_type+" 第2次触发！归因为内生惯性，强制阻断"}

        # ========== 第3次及以上：阻断失效处理 ==========
        # 第2次写了 override.json 但第3次仍然发生 → 阻断机制未生效
        # 原因可能是：override.json 未被钩子脚本及时读取
        # 处理方式：升级阻断措施 + 记录阻断失效原因
        if rule:
            rule.triggered_count = sn
            rule.last_triggered = now
            rule.lifecycle_status = 'critical'
            self.rule_engine.update_interception(rule.id, triggered_count=sn,
                last_triggered=now, lifecycle_status='critical')
            self.rule_engine.save_all()
        # 升级阻断：更新 dgen_overrides.json 中的条目为 escalated
        overrides = self._load_overrides()
        existing_idx = None
        for idx, entry in enumerate(overrides):
            if entry.get("blocked_error_type") == error_type:
                existing_idx = idx
                break
        escalated_entry = {
            "blocked_error_type": error_type,
            "strike_count": sn,
            "blocked_at": now,
            "last_detail": detail,
            "escalated": True,
            "reason": f"一二不过三阻断失效: {error_type} 第{sn}次触发，已升级为最高优先级阻断",
        }
        if existing_idx is not None:
            overrides[existing_idx] = escalated_entry
        else:
            overrides.append(escalated_entry)
        self._save_overrides(overrides)
        # 记录阻断失效日志（供工作台和审计追踪）
        op = self._strikes_db_path().replace("strikes_db.json", "dgen_warning.json")
        op = self._strikes_db_path().replace("strikes_db.json", "dgen_warning.json")
        breach_log = os.path.join(os.path.dirname(op), "dgen_breach_log.json")
        breaches = []
        try:
            if os.path.exists(breach_log):
                with open(breach_log, "r", encoding="utf-8") as f:
                    breaches = json.load(f)
        except Exception:
            pass
        breaches.append({"error_type": error_type, "strike": sn,
                         "first_seen": self._load_strikes_db().get(error_type, {}).get("first_seen", ""),
                         "blocked_at": now,
                         "detail": detail})
        with open(breach_log, "w", encoding="utf-8") as f:
            json.dump(breaches, f, ensure_ascii=False, indent=2)
        return {"action": "third_breach", "rule_id": key, "strike": sn,
                "escalated": True,
                "warning": "一二不过三阻断失效: " + error_type + " 在阻断后仍出现第" + str(sn) + "次。已升级阻断优先级，阻断失效原因已记录至 dgen_breach_log.json"}

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

    def cycle_shousan_rules(self) -> dict:
        """守三循环闭环: 检查shousan规则的触发效果
        已触发(有用) -> boost confidence
        未触发且超期 -> decay confidence
        """
        import datetime as _dt
        now = _dt.datetime.now()
        
        # 守三-攻七时间隔离: 检查攻七是否正在运行
        if getattr(self.rule_engine, "_phase_lock_gongqi", False):
            print("  [PHASE_LOCK] 攻七正在运行，守三跳过本轮")
            return {"boosted": 0, "decayed": 0, "archived": 0, "skipped": "gongqi_running"}
        
        # 缓急律调度: 紧急事务跳过守三深度复盘
        try:
            from pacemaker import get_pacemaker
            pm = get_pacemaker()
            pace = pm.classify({"task_type": "maintenance", "cmd": "shousan_cycle"})
            ch = pace.get("channel", "")
            if ch in ("fast_path", "downtime"):
                print(f"  [PACE] 缓急律: {ch} -> 守三跳过本轮")
                return {"boosted": 0, "decayed": 0, "archived": 0, "skipped": ch}
        except Exception:
            pass
        
        shousan_rules = [r for r in self.rule_engine.get_interceptions(active_only=False)
                           if "shousan_" in r.id or "shousan_review" in r.id]
        
        boosted = 0
        decayed = 0
        archived = 0
        
        for r in shousan_rules:
            created = r.created_at
            if created:
                try:
                    created_dt = _dt.datetime.fromisoformat(created)
                    age_hours = (now - created_dt).total_seconds() / 3600
                except:
                    age_hours = 0
            else:
                age_hours = 0
            
            triggered = getattr(r, 'triggered_count', 0) or 0
            ignored = getattr(r, 'ignored_count', 0) or 0
            
            if triggered > 0:
                old_conf = getattr(r, 'confidence', 3.0) or 3.0
                new_conf = min(5.0, old_conf + 0.3 * triggered)
                self.rule_engine.update_interception(r.id,
                    confidence=new_conf,
                    lifecycle_status="active")
                boosted += 1
                print(f"  [SHOUSAN_CYCLE] boost: {r.id} (old={old_conf:.1f}->new={new_conf:.1f}, trigs={triggered})")
            elif age_hours > 72 and triggered == 0:
                old_conf = getattr(r, 'confidence', 3.0) or 3.0
                new_conf = max(1.0, old_conf - 0.5)
                if new_conf <= 1.5:
                    self.rule_engine.update_interception(r.id,
                        lifecycle_status="archived",
                        confidence=new_conf)
                    archived += 1
                    print(f"  [SHOUSAN_CYCLE] archive: {r.id} (never trig in {age_hours:.0f}h)")
                else:
                    self.rule_engine.update_interception(r.id,
                        confidence=new_conf)
                    decayed += 1
                    print(f"  [SHOUSAN_CYCLE] decay: {r.id} (old={old_conf:.1f}->new={new_conf:.1f})")
            elif age_hours > 24 and triggered == 0 and ignored > 3:
                self.rule_engine.update_interception(r.id,
                    lifecycle_status="archived")
                archived += 1
                print(f"  [SHOUSAN_CYCLE] archive: {r.id} (ignored={ignored}, no trig)")
        
        if boosted > 0 or decayed > 0 or archived > 0:
            self.rule_engine.save_all()
        
        return {"boosted": boosted, "decayed": decayed, "archived": archived}
    def cycle_gongqi_patterns(self) -> dict:
        """攻七强化闭环: 验证gongqi模式的有效性
        已触发(有用) -> solidify
        未触发且超期 -> archive
        """
        import datetime as _dt
        now = _dt.datetime.now()
        
        # 守三-攻七时间隔离: 标记攻七正在运行
        self.rule_engine._phase_lock_gongqi = True
        try:
            # 缓急律调度: 紧急事务跳过攻七
            try:
                from pacemaker import get_pacemaker
                pm = get_pacemaker()
                pace = pm.classify({"task_type": "maintenance", "cmd": "gongqi_cycle"})
                ch = pace.get("channel", "")
                if ch in ("fast_path", "downtime"):
                    print(f"  [PACE] 缓急律: {ch} -> 攻七跳过本轮")
                    return {"solidified": 0, "decayed": 0, "archived": 0, "skipped": ch}
            except Exception:
                pass
            
            gongqi_patterns = [p for p in self.rule_engine.get_patterns(active_only=False)
                                  if "gongqi_" in p.id]
            
            solidified = 0
            decayed = 0
            archived = 0
            
            for p in gongqi_patterns:
                created = p.created_at
                if created:
                    try:
                        created_dt = _dt.datetime.fromisoformat(created)
                        age_hours = (now - created_dt).total_seconds() / 3600
                    except:
                        age_hours = 0
                else:
                    age_hours = 0
                
                triggered = getattr(p, 'triggered_count', 0) or 0
                
                if triggered > 0:
                    old_conf = getattr(p, 'confidence', 3.0) or 3.0
                    new_conf = min(5.0, old_conf + 0.3 * triggered)
                    self.rule_engine.update_pattern(p.id,
                        confidence=new_conf,
                        lifecycle_status="active")
                    solidified += 1
                    print(f"  [GONGQI_CYCLE] solidify: {p.id} (old={old_conf:.1f}->new={new_conf:.1f}, trigs={triggered})")
                elif age_hours > 72 and triggered == 0:
                    old_conf = getattr(p, 'confidence', 3.0) or 3.0
                    new_conf = max(1.0, old_conf - 0.5)
                    if new_conf <= 1.5:
                        self.rule_engine.update_pattern(p.id,
                            lifecycle_status="archived",
                            confidence=new_conf)
                        archived += 1
                        print(f"  [GONGQI_CYCLE] archive: {p.id} (never trig in {age_hours:.0f}h)")
                    else:
                        self.rule_engine.update_pattern(p.id,
                            confidence=new_conf)
                        decayed += 1
                        print(f"  [GONGQI_CYCLE] decay: {p.id} (old={old_conf:.1f}->new={new_conf:.1f})")
            
            if solidified > 0 or decayed > 0 or archived > 0:
                self.rule_engine.save_all()
            
            return {"solidified": solidified, "decayed": decayed, "archived": archived}
        finally:
            self.rule_engine._phase_lock_gongqi = False
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
