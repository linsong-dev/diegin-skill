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
        # C1 计数旁路：同进程合并 + 降频落盘（防 Mindol/JSON 全量重写）
        self._counter_queue = {}
        self._counter_events = 0
        self._reconcile_counts_from_json()
        self._apply_counter_sidecar()

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
            # v3.6: 计数立即落盘（原实现只标 dirty，进程退出计数丢失 → 统计恒为0）
            try:
                self.rule_engine._save_json("interception_rules.json", self.rule_engine._interceptions)
            except Exception:
                pass
        else:
            self.rule_engine.update_pattern(rule.id, **kwargs)

    # ─── C1 计数旁路（脏标记增量写 + 同进程合并 + 降频双存储比对）───
    C1_FLUSH_THRESHOLD = 20

    def _counter_sidecar_path(self):
        """旁路计数小文件（进程间计数连续性，崩溃不丢）"""
        return os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))),
                            "var", "state", "rule_counter_deltas.json")

    def _load_counter_sidecar(self):
        path = self._counter_sidecar_path()
        if not os.path.exists(path):
            return {}
        try:
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
            return data if isinstance(data, dict) else {}
        except Exception:
            return {}

    def _save_counter_sidecar(self, data):
        path = self._counter_sidecar_path()
        try:
            os.makedirs(os.path.dirname(path), exist_ok=True)
            tmp = path + ".c1tmp" + str(os.getpid())
            with open(tmp, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=1)
            os.replace(tmp, path)
        except Exception:
            pass

    _COUNTER_FIELDS = ("triggered_count", "ignored_count", "override_count", "block_count",
                       "last_triggered", "last_ignored", "confidence", "lifecycle_status")

    def _reconcile_counts_from_json(self):
        """降频双存储比对：Mindol 权威单元不携带计数，加载时用 JSON 计数补齐内存
        （修复 v3.6 计数落盘 JSON 但加载走 Mindol 导致重启归零的问题）"""
        try:
            rd = self.rule_engine.rules_dir
            for fname, rules in (("interception_rules.json", self.rule_engine._interceptions),
                                 ("success_patterns.json", self.rule_engine._patterns)):
                path = os.path.join(str(rd), fname)
                if not os.path.exists(path):
                    continue
                with open(path, "r", encoding="utf-8") as f:
                    jitems = json.load(f)
                by_id = {it.get("id"): it for it in jitems if isinstance(it, dict)}
                for r in rules:
                    jr = by_id.get(r.id)
                    if not jr:
                        continue
                    for k in ("triggered_count", "ignored_count", "override_count", "block_count"):
                        jv = jr.get(k) or 0
                        if jv > (getattr(r, k, 0) or 0):
                            setattr(r, k, jv)
                    for k, jk in (("last_triggered", "last_triggered"), ("last_ignored", "last_ignored")):
                        jv = jr.get(jk) or ""
                        mv = getattr(r, k, "") or ""
                        if jv and (not mv or jv > mv):
                            setattr(r, k, jv)
        except Exception:
            pass

    def _apply_counter_sidecar(self):
        """加载旁路计数增量到内存（跨进程计数连续性；权威落盘由 flush 降频执行）"""
        data = self._load_counter_sidecar()
        if not data:
            return
        for rid, entry in data.items():
            rule, _ = self._resolve_rule(rid)
            if not rule:
                continue
            for dk, ck in (("triggered_delta", "triggered_count"),
                           ("ignored_delta", "ignored_count"),
                           ("override_delta", "override_count"),
                           ("block_delta", "block_count")):
                d = entry.get(dk, 0) or 0
                if d:
                    setattr(rule, ck, (getattr(rule, ck, 0) or 0) + d)
            for k in ("last_triggered", "last_ignored"):
                if entry.get(k):
                    setattr(rule, k, entry[k])
        self._counter_queue = {k: dict(v) for k, v in data.items()}
        self._counter_events = len(data)

    def _queue_counter(self, rule_id, rule_type, **delta_fields):
        """同进程合并计数增量；按阈值降频冲刷权威存储"""
        entry = self._counter_queue.setdefault(rule_id, {"type": rule_type})
        for k, v in delta_fields.items():
            if k.endswith("_delta"):
                entry[k] = (entry.get(k, 0) or 0) + v
            else:
                entry[k] = v
        self._counter_events += 1
        self._save_counter_sidecar(self._counter_queue)
        if self._counter_events >= self.C1_FLUSH_THRESHOLD:
            self.flush_counter_deltas()

    def flush_counter_deltas(self):
        """把旁路计数合并进权威 JSON（每类文件一次全量写），并清空旁路"""
        if not self._counter_queue:
            return 0
        ids = list(self._counter_queue.keys())
        try:
            has_inter = has_pat = False
            for rid in ids:
                rule, rule_type = self._resolve_rule(rid)
                if not rule:
                    continue
                if rule_type == "interception":
                    has_inter = True
                else:
                    has_pat = True
            # 内存已含全部增量（record 时 + 加载 sidecar 时），直接落盘当前值
            if has_inter:
                self.rule_engine._save_json("interception_rules.json", self.rule_engine._interceptions)
            if has_pat:
                self.rule_engine._save_json("success_patterns.json", self.rule_engine._patterns)
            self._counter_queue = {}
            self._counter_events = 0
            self._save_counter_sidecar({})
            print("[TRACKER] C1 计数合并落盘: %d 条" % len(ids))
            return len(ids)
        except Exception as _e:
            print("[TRACKER] flush_counter_deltas failed: %s" % _e)
            return 0

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

        self._queue_counter(rule_id, rule_type,
                            ignored_delta=1,
                            last_ignored=rule.last_ignored)
        return {"action": "updated", "ignore_count": getattr(rule, 'ignored_count', 0)}

    def record_override(self, rule_id: str) -> Dict:
        """记录规则被手动覆盖"""
        rule, rule_type = self._resolve_rule(rule_id)
        if not rule:
            return {"action": "not_found"}

        rule.override_count += 1
        self._queue_counter(rule_id, rule_type, override_delta=1)
        return {"action": "updated", "override_count": rule.override_count}

    def record_triggered(self, rule_id: str) -> Dict:
        """记录规则被触发"""
        rule, rule_type = self._resolve_rule(rule_id)
        if not rule:
            return {"action": "not_found"}

        rule.triggered_count += 1
        rule.last_triggered = datetime.now().isoformat()

        self._queue_counter(rule_id, rule_type,
                            triggered_delta=1,
                            last_triggered=rule.last_triggered)
        return {"action": "updated", "triggered_count": rule.triggered_count}

    def record_block(self, rule_id: str, blocked_rule: str = "") -> Dict:
        # v3.8.3: 守三真实阻断计数（block_count 回写，曾恒为 0）
        rule, rule_type = self._resolve_rule(rule_id)
        if not rule:
            return {"action": "not_found"}
        if not hasattr(rule, "block_count"):
            return {"action": "not_supported"}  # 成功模式无阻断字段

        rule.block_count += 1
        if blocked_rule and hasattr(rule, "blocked_rules"):
            if blocked_rule not in rule.blocked_rules:
                rule.blocked_rules.append(blocked_rule)

        self._queue_counter(rule_id, rule_type, block_delta=1)
        return {"action": "updated", "block_count": rule.block_count}


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
        """归因过滤：委托去伪存真 EvidenceVault 分类"""
        try:
            from evidence_vault import EvidenceVault
            _v = EvidenceVault()
            _verdict = _v.classify_failure(error_type or "", detail or "")
            if _verdict == "external":
                return {"verdict": "external", "kw": "classified", "reason": "环境/外因问题（去伪存真）"}
            elif _verdict == "internal":
                return {"verdict": "internal", "kw": "classified", "reason": "AI自身行为惯性（去伪存真）"}
            else:
                return {"verdict": "internal", "kw": None, "reason": "不确定，默认保守视为内生惯性（去伪存真）"}
        except Exception:
            # 降级：内置关键词匹配
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
                    return {"verdict":"external","kw":kw,"reason":"环境/外因问题（内置降级）"}
            for kw in in_keywords:
                if kw in el or kw in dl:
                    return {"verdict":"internal","kw":kw,"reason":"AI自身行为惯性（内置降级）"}
            return {"verdict":"internal","kw":None,"reason":"默认保守视为内生惯性（内置降级）"}


    def notify_shousan(self, error_type: str, detail: str, cause: dict) -> dict:
        """一二不过三(strike) -> 守三(复盘触发)
        在第2次strike阻断后自动触发守三复盘，生成一条预防性规则写入规则库。"""
        from rule_engine import InterceptionRule
        import datetime as _dt
        now = _dt.datetime.now().isoformat()
        
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
            now = _dt.datetime.now().isoformat()
        
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

    def notify_gongqi(self, error_type: str, detail: str, fix_rule_id: str = '', mode: str = 'prevention') -> dict:
        """一二不过三 -> 攻七(写入模式)
        mode='prevention'  ：第2次阻断后生成预防模式（原行为）
        mode='verified_fix'：①立改"改毕验"通过后，固化修复成功经验（文档①语义落地）"""
        from rule_engine import SuccessPattern
        import datetime as _dt
        now = _dt.datetime.now().isoformat()
        
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
            now = _dt.datetime.now().isoformat()
        
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
                if mode == "verified_fix":
                    pname = pname + "（修复成功经验）"
                matched = True
                break
        
        if not matched:
            clean_type = error_type.replace('self_error_', '').replace('silent_', '')
            if len(clean_type) > 30:
                clean_type = clean_type[:30]
            if mode == "verified_fix":
                pname = f'修复{clean_type}经验'
                logic = f'{clean_type}操作已修复并验证通过，固化该路径'
            else:
                pname = f'预防{clean_type}'
                logic = f'{clean_type}操作前预检，避免同类错误'
        
        pattern_id = f'gongqi_{"verified" if mode == "verified_fix" else "fix"}_{error_type}_{_dt.datetime.now().strftime("%Y%m%d_%H%M%S")}'
        
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
    @staticmethod
    def _normalize_type(t: str) -> str:
        return "".join(ch for ch in (t or "").lower() if ch.isalnum())

    @staticmethod
    def _types_similar(a: str, b: str) -> bool:
        """语义相似判定：词元重叠 >= 50% 视为同类错误（v3.7）"""
        na = BehaviorTracker._normalize_type(a)
        nb = BehaviorTracker._normalize_type(b)
        if not na or not nb:
            return False
        if na == nb:
            return True
        shorter, longer = (na, nb) if len(na) <= len(nb) else (nb, na)
        if shorter in longer and len(shorter) >= 3:
            return True
        ta = set(x for x in (a or "").lower().replace("-", "_").split("_") if x)
        tb = set(x for x in (b or "").lower().replace("-", "_").split("_") if x)
        if ta and tb:
            inter = len(ta & tb)
            if inter >= 1 and (inter / min(len(ta), len(tb))) >= 0.5:
                return True
        return False


    def record_self_error(self, error_type, detail='', task_context=None):
        """
        一二不过三·三错阀（v3.4.1 增强）
        第1次：警告+警觉+立改 → 写 dgen_warning.json + dgen_fix_plan.json（修复方案），规则标记 alerting
               → 修复后由 verify_fix() / _auto_verify_pending_fixes() 完成"改毕验"，成功则输出攻七修复经验
        第2次：去伪存真归因过滤 → 内生惯性 → dgen_overrides.json 硬阻断 + 守三预防规则 + 攻七预防模式
               外生变量 → 记录 dgen_external_adjust.json 策略调整，不阻断
        第3次：推翻原阻断方案 → enforce→audit 模式切换 → 根因分析 + 修复 + 复检提醒
        """
        import datetime as _dt
        if task_context is None:
            task_context = {}
        now = _dt.datetime.now().isoformat()

        db = self._load_strikes_db()
        # v3.7 语义相似判定：同类错误归并（error_type 词元重叠 >= 50% 视为同类）
        if error_type not in db:
            for _et in list(db.keys()):
                if _et != error_type and self._types_similar(error_type, _et):
                    error_type = _et
                    break
        if error_type not in db:
            db[error_type] = {'count': 0, 'first_seen': now, 'last_seen': now,
                              'last_detail': detail,
                              'severity': task_context.get('severity', 'high'),
                              'details': []}
        key = 'self_error_' + error_type
        entry = db[error_type]
        # 一二不过三·封顶：超过3次不再继续累加（1改→2验→3升级，之后停止）
        if entry['count'] >= 3:
            # 已达到封顶，不再累加，但更新上次时间
            entry['last_seen'] = now
            entry['last_detail'] = detail
            self._save_strikes_db(db)
            return {"action":"capped_at_3","rule_id":key,"strike":entry['count'],
                    "warning":"一二不过三封顶: "+error_type+" 已达3次上限，不再计数"}
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
            else:
                # 防再生 L1: 预置规则下第1次 strike 同步计数/时间（1警→2阻→3升级状态准确）
                self.rule_engine.update_interception(rule.id, triggered_count=sn, last_triggered=now)
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
            # ①立改：生成修复方案，进入"改毕验"待验证状态
            try:
                self._generate_fix_plan(error_type, detail)
            except Exception:
                pass
            return {'action':'first_warning','rule_id':key,'strike':sn,
                    'warning':'⚠️ 一二不过三: '+error_type+' 已出现第1次，系统已警觉，已生成修复方案（立改），等待改毕验'}

        # ========== 第2次：阻断 ==========
        # ========== 第2次：阻断（先去伪存真·归因过滤）==========
        if sn == 2:
            cause = self._analyze_cause(error_type, detail)
            is_internal = cause["verdict"] == "internal"
            if not is_internal:
                print("[TRACKER] external cause, skip block: " + error_type)
                # ②外生变量：记录策略调整（不阻断，但调整应对策略供后续参考）
                try:
                    self._record_external_adjustment(error_type, detail, cause)
                except Exception:
                    pass
                return {"action":"external_skip","rule_id":key,"strike":sn,
                        "cause":cause,
                        "adjustment":"已记录外生变量策略调整（dgen_external_adjust.json）",
                        "message":"一二不过三: "+error_type+" 第2次触发但判定为外生变量，不做阻断，已调整应对策略"}
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
        # v3.7 升级熔断：连续同类错误第3次 → 熔断状态 open（pre_tool 读到 escalated+circuit 强制阻断）
        try:
            _cb_path = os.path.join(os.path.dirname(self._strikes_db_path()), "dgen_circuit_breaker.json")
            _cb = {
                "error_type": error_type,
                "strike_count": sn,
                "circuit": "open",
                "triggered_at": now,
                "escalated": True,
                "note": "一二不过三升级熔断：连续同类错误达到3次，强制 audit_only + 最高优先级阻断"
            }
            with open(_cb_path, "w", encoding="utf-8") as _f:
                json.dump(_cb, _f, ensure_ascii=False, indent=2)
        except Exception:
            pass
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

        # 三错升级：推翻原阻断方案 + 切换执行模式 + 通知用户
        try:
            # 1. 删除阻断文件（推翻原方案）
            _ov_path = self._strikes_db_path().replace("strikes_db.json", "dgen_override.json")
            if os.path.exists(_ov_path):
                _null_ov = {"blocked_error_type":"","strike_count":0,"blocked_at":None,"last_detail":"","decision":"allow"}
                with open(_ov_path, "w", encoding="utf-8") as _f:
                    json.dump(_null_ov, _f, ensure_ascii=False, indent=2)
            # 2. 降级规则生命周期（阻断失败 → 降为 alerting，走其他策略）
            if rule:
                self.rule_engine.update_interception(rule.id, lifecycle_status="alerting")
            # 3. 写入模式切换文件（钩子据此切换执行策略）
            _base_dir = os.path.dirname(self._strikes_db_path())
            _mode_file = os.path.join(_base_dir, "dgen_enforcement_mode.json")
            _mode = {
                "mode": "audit",
                "previous_mode": "enforce",
                "trigger": error_type,
                "reason": f"一二不过三: {error_type} 第{sn}次触发，已升三错级，从enforce切换为audit",
                "switched_at": now,
                "available_modes": ["enforce", "audit", "bypass"]
            }
            try:
                os.makedirs(os.path.dirname(_mode_file), exist_ok=True)
                with open(_mode_file, "w", encoding="utf-8") as _f:
                    json.dump(_mode, _f, ensure_ascii=False, indent=2)
            except Exception:
                pass
            # 4. 写状态文件通知用户
            _st = os.path.join(_base_dir, "dgen_status.txt")
            _msg = ("=== DGEN STATUS ===\nSTATUS: ESCALATED\nRULES: ?\n"
                    "DECISION: escalate\nMATCHED: 0\n"
                    "TS: " + now + "\n"
                    "MODE: enforce → audit\n"
                    "NOTE: 一二不过三失效: " + error_type + " 已在阻断后仍出现第" + str(sn) + "次，已推翻原阻断方案\n"
                    "  执行模式已从 enforce 切换为 audit（记录但不阻断）\n")
            try:
                with open(_st, "w", encoding="utf-8") as _f:
                    _f.write(_msg)
            except Exception:
                pass
            print("\n[DGEN] ⚠️ 一二不过三升级: " + error_type + " 第" + str(sn) + "次触发")
            print("  原阻断方案已推翻，规则已降级为 alerting")
            print("  执行模式切换: enforce → audit")
            print("  系统升级建议: 检查 " + error_type + " 的根因并调整拦截策略\n")
        except Exception as _ee:
            pass

        # 封顶：升级后下次不再处理
        if rule:
            self.rule_engine.update_interception(rule.id, lifecycle_status="alerting", confidence=0.0)

        # ③三错根因分析 + 修复 + 复检提醒（v3.4.1 增强；位于封顶之后，修复结果不被封顶覆盖）
        root_causes = []
        try:
            root_causes = self._root_cause_analysis(error_type, rule)
            self._apply_strike_treatment(error_type, rule, root_causes)
        except Exception:
            pass
        return {"action": "third_breach", "rule_id": key, "strike": sn,
                "escalated": True,
                "root_causes": root_causes,
                "warning": "一二不过三阻断失效: " + error_type + " 在阻断后仍出现第" + str(sn) + "次。已推翻原阻断方案并降低规则优先级"}

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
            rule.override_count = getattr(rule, "override_count", 0) + 1  # 修复：SuccessPattern 无 override_count 字段
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


    # ============================================================
    # v3.4.1 增强：①立改+改毕验 ②外生调整 ③三错根因分析
    # ============================================================

    def _state_dir(self):
        """var/state 目录（与 strikes_db 同目录）"""
        return os.path.dirname(self._strikes_db_path())

    def _fix_plan_path(self):
        return os.path.join(self._state_dir(), "dgen_fix_plan.json")

    def _external_adjust_path(self):
        return os.path.join(self._state_dir(), "dgen_external_adjust.json")

    def _generate_fix_plan(self, error_type, detail="", cause=None):
        """①立改：第1次错误后自动生成修复方案，进入"改毕验"待验证状态。
        修复方案写入 dgen_fix_plan.json；strikes_db 条目标记 fix_status=pending_verify。
        """
        import datetime as _dt
        now = _dt.datetime.now().isoformat()
        if cause is None:
            try:
                cause = self._analyze_cause(error_type, detail)
            except Exception:
                cause = {"verdict": "internal", "reason": "unknown"}
        fix_map = {
            'encoding_write_corruption': ["用 UTF-8 NoBOM 重新写入文件", "写入前校验编码", "避免 BOM/替换符"],
            'encoding_error': ["用 UTF-8 NoBOM 重新写入文件", "写入前校验编码", "避免 BOM/替换符"],
            'git_push_failure': ["检查网络连接", "git status 确认工作区状态", "git pull 同步后重试", "确认认证有效"],
            'command_failure': ["先 dry-run 或 --help 验证参数", "检查命令路径与权限", "确认退出码与错误信息"],
            'command_timeout': ["设置显式超时", "拆分为更小步骤", "超时后优雅降级"],
        }
        steps = None
        for key, s in fix_map.items():
            if key in error_type:
                steps = s
                break
        if steps is None:
            clean = error_type.replace("self_error_", "").replace("silent_", "")[:40]
            steps = [f"执行前预检 {clean}", "验证结果", "确认无误后继续"]
        plan = {
            "error_type": error_type,
            "cause": cause,
            "fix_steps": steps,
            "fix_status": "pending_verify",
            "created_at": now,
            "verify_rule": "24小时内同类错误未再出现 或 显式调用 verify_fix 确认成功",
        }
        try:
            os.makedirs(self._state_dir(), exist_ok=True)
            with open(self._fix_plan_path(), "w", encoding="utf-8") as f:
                json.dump(plan, f, ensure_ascii=False, indent=2)
        except Exception:
            pass
        try:
            db = self._load_strikes_db()
            if error_type in db:
                db[error_type]["fix_status"] = "pending_verify"
                db[error_type]["fix_plan_at"] = now
                self._save_strikes_db(db)
        except Exception:
            pass
        return plan

    def verify_fix(self, error_type, success=True, detail=""):
        """①改毕验：确认修复结果。
        success=True  → 修复成功：标记 verified，输出攻七成功模式（修复经验固化）+ 守三预防规则
        success=False → 修复失败：标记 failed，同类错误再出现将触发第2次流程
        """
        import datetime as _dt
        now = _dt.datetime.now().isoformat()
        db = self._load_strikes_db()
        entry = db.get(error_type, {})
        entry["fix_status"] = "verified" if success else "failed"
        entry["fix_verified_at"] = now
        entry["fix_verify_detail"] = str(detail)[:120]
        db[error_type] = entry
        self._save_strikes_db(db)
        if success:
            try:
                self.notify_gongqi(error_type, detail, fix_rule_id="", mode="verified_fix")
            except Exception:
                pass
            try:
                cause = self._analyze_cause(error_type, detail)
                self.notify_shousan(error_type, detail, cause)
            except Exception:
                pass
            return {"action": "fix_verified", "error_type": error_type,
                    "message": "改毕验通过：修复成功，经验已固化到攻七模式库"}
        return {"action": "fix_failed", "error_type": error_type,
                "message": "改毕验未通过：修复无效，同类错误再出现将触发第2次阻断"}

    def _auto_verify_pending_fixes(self, max_age_hours=24):
        """①改毕验·自动版：检查所有 pending_verify 修复。
        超过阈值时间且仍为第1次（未再犯）→ 自动判定修复成功并固化攻七经验。
        """
        import datetime as _dt
        now = _dt.datetime.now()
        db = self._load_strikes_db()
        results = []
        for error_type, entry in db.items():
            if entry.get("fix_status") != "pending_verify":
                continue
            plan_at = entry.get("fix_plan_at", "")
            if not plan_at:
                continue
            try:
                plan_dt = _dt.datetime.fromisoformat(plan_at)
            except Exception:
                continue
            age_hours = (now - plan_dt).total_seconds() / 3600
            count = entry.get("count", 0)
            if age_hours >= max_age_hours and count <= 1:
                entry["fix_status"] = "verified"
                entry["fix_verified_at"] = now.isoformat()
                entry["fix_auto"] = True
                self._save_strikes_db(db)
                try:
                    self.notify_gongqi(error_type, entry.get("last_detail", ""), mode="verified_fix")
                except Exception:
                    pass
                results.append({"error_type": error_type, "action": "auto_verified",
                                "age_hours": round(age_hours, 1)})
        return results

    def _record_external_adjustment(self, error_type, detail="", cause=None):
        """②外生变量调整策略：不阻断，但记录外部归因与应对策略，供后续同类事件参考。"""
        import datetime as _dt
        now = _dt.datetime.now().isoformat()
        adj = {
            "error_type": error_type,
            "cause": cause or {"verdict": "external", "reason": "外部变量"},
            "strategy": "重试/等待/更换来源/降级处理（外生变量不做硬阻断）",
            "recorded_at": now,
            "last_detail": str(detail)[:120],
        }
        path = self._external_adjust_path()
        arr = []
        try:
            if os.path.exists(path):
                with open(path, "r", encoding="utf-8") as f:
                    arr = json.load(f) if isinstance(json.load(f), list) else []
        except Exception:
            arr = []
        arr = [a for a in arr if a.get("error_type") != error_type]
        arr.append(adj)
        arr = arr[-50:]
        try:
            os.makedirs(self._state_dir(), exist_ok=True)
            with open(path, "w", encoding="utf-8") as f:
                json.dump(arr, f, ensure_ascii=False, indent=2)
        except Exception:
            pass
        try:
            db = self._load_strikes_db()
            if error_type in db:
                db[error_type]["external_adjusted"] = True
                db[error_type]["external_adjusted_at"] = now
                self._save_strikes_db(db)
        except Exception:
            pass
        return adj

    def _root_cause_analysis(self, error_type, rule):
        """③三错根因分析：阻断失效后，为什么失效？"""
        causes = []
        source = getattr(rule, "source", "") if rule else ""
        trigger = (getattr(rule, "trigger_condition", "") or "") if rule else ""
        if source == "auto_generalized":
            causes.append({"type": "generalization_gap", "confidence": 0.8,
                           "treatment": "该规则为举一反三泛化产物，未经充分验证，标记 deprecating 淘汰",
                           "evidence": f"source={source}"})
        if trigger:
            broad = (" OR " in trigger) or (" IN (" in trigger) or len(trigger) > 120
            if broad:
                causes.append({"type": "condition_too_broad", "confidence": 0.6,
                               "treatment": "收窄触发条件或拆分规则",
                               "evidence": f"trigger_len={len(trigger)} contains_OR={' OR ' in trigger}"})
        try:
            db = self._load_strikes_db()
            if db.get(error_type, {}).get("external_adjusted"):
                causes.append({"type": "external_persistent", "confidence": 0.7,
                               "treatment": "不降级规则；通知用户外部环境持续异常，升级人工处理",
                               "evidence": "第2次已判定外生变量，第3次仍出现"})
        except Exception:
            pass
        try:
            trail_path = os.path.join(self._state_dir(), "evidence_trail.json")
            if os.path.exists(trail_path):
                with open(trail_path, "r", encoding="utf-8") as f:
                    trail = json.load(f)
                rid = getattr(rule, "id", error_type)
                rule_ev = [e for e in trail if e.get("rule_id") == rid]
                fails = [e for e in rule_ev if e.get("verdict") in ("fail", "block")]
                if len(rule_ev) >= 3 and len(fails) / len(rule_ev) > 0.5:
                    causes.append({"type": "confidence_mismatch", "confidence": 0.6,
                                   "treatment": "置信度已归零，建议人工复审或归档",
                                   "evidence": f"evidence_trail fail_rate={len(fails)}/{len(rule_ev)}"})
        except Exception:
            pass
        if not causes:
            causes.append({"type": "unknown", "confidence": 0.3,
                           "treatment": "记录 breach 并保持 audit 模式观察，必要时人工介入",
                           "evidence": "未匹配已知根因模式"})
        causes.sort(key=lambda x: -x["confidence"])
        return causes

    def _apply_strike_treatment(self, error_type, rule, root_causes):
        """③三错修复：根据根因执行修复 + 写入追踪记录 + 创建复检提醒（止观门）。"""
        import datetime as _dt
        now = _dt.datetime.now().isoformat()
        result = {"error_type": error_type, "applied": [], "followup": None}
        if rule is None:
            return result
        for rc in root_causes:
            t = rc.get("type")
            if t == "generalization_gap":
                try:
                    self.rule_engine.update_interception(rule.id, lifecycle_status="deprecating")
                    result["applied"].append("auto_generalized 规则 → deprecating")
                except Exception:
                    pass
            elif t == "condition_too_broad":
                try:
                    new_cond = rule.trigger_condition.split(" OR ")[0] if " OR " in (rule.trigger_condition or "") else rule.trigger_condition
                    self.rule_engine.update_interception(rule.id, trigger_condition=new_cond,
                                                         lifecycle_status="staging")
                    result["applied"].append("触发条件收窄 → staging 重验")
                except Exception:
                    pass
            elif t == "external_persistent":
                result["applied"].append("外生持续问题 → 保持规则现状，升级人工处理")
            elif t == "confidence_mismatch":
                try:
                    self.rule_engine.update_interception(rule.id, lifecycle_status="deprecating", confidence=0.0)
                    result["applied"].append("置信度失配 → deprecating")
                except Exception:
                    pass
            elif t == "unknown":
                result["applied"].append("未知根因 → 保持 audit 观察")
        try:
            from closure import get_closure
            cl = get_closure()
            cl.open(f"strike_followup_{rule.id}",
                    f"三错根因修复复检: {error_type} ({rule.id})",
                    {"check_after_days": 7, "rule_id": rule.id,
                     "root_causes": [c["type"] for c in root_causes]})
            result["followup"] = f"strike_followup_{rule.id}"
        except Exception:
            pass
        # 复检提醒持久化（进程重启不丢失）
        followups = []
        _fp = os.path.join(self._state_dir(), "dgen_strike_followups.json")
        try:
            if os.path.exists(_fp):
                with open(_fp, "r", encoding="utf-8") as f:
                    followups = json.load(f) if isinstance(json.load(f), list) else []
        except Exception:
            pass
        followups.append({"rule_id": rule.id, "error_type": error_type,
                          "check_after_days": 7, "created_at": now,
                          "root_causes": [c["type"] for c in root_causes]})
        try:
            with open(_fp, "w", encoding="utf-8") as f:
                json.dump(followups[-100:], f, ensure_ascii=False, indent=2)
        except Exception:
            pass
        record = {
            "error_type": error_type,
            "rule_id": rule.id,
            "root_causes": root_causes,
            "applied": result["applied"],
            "followup": result["followup"],
            "recorded_at": now,
        }
        try:
            rp = os.path.join(self._state_dir(), "dgen_strike_rootcause.json")
            arr = []
            if os.path.exists(rp):
                with open(rp, "r", encoding="utf-8") as f:
                    arr = json.load(f) if isinstance(json.load(f), list) else []
            arr.append(record)
            arr = arr[-100:]
            with open(rp, "w", encoding="utf-8") as f:
                json.dump(arr, f, ensure_ascii=False, indent=2)
        except Exception:
            pass
        return result
