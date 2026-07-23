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
diegin-evo 规则引擎
迭进自主生成和维护
"""

import json
import os
import re
from datetime import datetime, timedelta
from typing import List, Dict, Optional, Any
from dataclasses import dataclass, asdict, field
from pathlib import Path


# ============================================================
# 数据结构定义
# ============================================================

@dataclass
class InterceptionRule:
    """拦截规则（守）"""
    id: str
    trigger_condition: str                     # 触发条件表达式
    action: str                                # 执行动作
    severity: str                              # high | medium | low
    tags: List[str]                            # 标签（如 risk_control, irreversible）

    # 双因子评分
    logic_score: float = 5.0                   # 逻辑可解释性 (0-5)
    outcome_score: float = 5.0                 # 结果胜率 (0-5)
    confidence: float = 5.0                    # 加权总分

    # 来源
    source: str = "seed"                       # seed | learned | war_game | human_override
    source_review: str = ""                    # 来源任务ID

    # 生命周期
    lifecycle_status: str = "active"           # active | deprecating | archived | cached
    created_at: str = ""                       # 创建时间 ISO
    valid_until: str = ""                      # 有效期，空=永久
    last_triggered: str = ""                   # 最后触发时间

    # 边界条件
    boundary_conditions: List[str] = field(default_factory=list)
    invalid_conditions: List[str] = field(default_factory=list)

    # 隐性偏好追踪
    triggered_count: int = 0
    ignored_count: int = 0
    override_count: int = 0
    last_ignored: str = ""

    # 种子规则专用
    block_count: int = 0
    blocked_rules: List[str] = field(default_factory=list)


@dataclass
class SuccessPattern:
    """成功模式（攻）"""
    id: str
    pattern_name: str
    trigger_scenario: str                      # 触发场景描述
    decision_logic: str = ""                     # 决策逻辑
    trigger_condition: str = ""                # 结构化触发条件(同InterceptionRule), 空=回退
    micro_template: str = ""                   # 微模板（50字内）

    # 前置条件和边界
    preconditions: List[str] = field(default_factory=list)
    boundary_conditions: List[str] = field(default_factory=list)

    # 归因标签
    luck_factor: str = "low"                   # low | medium | high
    emotion_factor: str = "low"                # low | medium | high
    core_capability: str = ""                  # 核心可控能力

    # 双因子评分
    logic_score: float = 5.0
    outcome_score: float = 5.0
    confidence: float = 5.0

    # 来源
    source: str = "learned"                    # seed | learned | war_game
    auto_promoted: bool = False
    promoted_from: str = ""
    promoted_at: str = ""

    # 生命周期
    lifecycle_status: str = "active"
    created_at: str = ""
    valid_until: str = ""
    last_triggered: str = ""
    triggered_count: int = 0


@dataclass
class MetaExperience:
    """元经验"""
    id: str
    insight: str                               # 洞察内容
    applicable_contexts: List[str]             # 适用场景
    action_binding: str = ""                   # 绑定的行动
    source_review: str = ""
    created_at: str = ""
    confidence: float = 5.0


@dataclass
class Precedent:
    """判例（人工兜底/自动降级产出）"""
    id: str
    conflict_rules: List[str]
    resolution: str                            # human_resolved | auto_degraded
    degradation_reason: str = ""
    winning_rule: str = ""
    winning_rule_type: str = ""                # interception | success_pattern
    decision_logic: str = ""
    created_at: str = ""


# ============================================================
# 规则引擎核心
# ============================================================

class RuleEngine:
    """规则引擎：CRUD + 检索 + 匹配"""

    def __init__(self, rules_dir: str = None):
        if rules_dir is None:
            rules_dir = str(Path(__file__).parent / "rules")
        self.rules_dir = Path(rules_dir)
        self.rules_dir.mkdir(parents=True, exist_ok=True)

        self._interceptions: List[InterceptionRule] = []
        self._patterns: List[SuccessPattern] = []
        self._metas: List[MetaExperience] = []
        self._precedents: List[Precedent] = []

        self._dirty: set = set()                     # 脏文件跟踪（延迟批量写）
        self.MIN_RULES: dict = {"interception_rules.json": 10, "success_patterns.json": 1}  # 最小规则数阈值（写保护）
        self._mindol = None                          # Mindol 语义记忆引擎（权威存储）

        self._init_mindol()                          # 优先初始化 Mindol
        self._load_all()                             # 加载数据（Mindol优先）


    # ─── Mindol 语义记忆引擎集成（全局全域） ───

    def _init_mindol(self):
        """懒加载 Mindol 实例"""
        if self._mindol is None:
            try:
                import sys as _sys
                _sys.path.insert(0, str(Path(__file__).parent.parent))
                from mindol import core as _mindol_core
                storage = str(Path(os.environ.get("CODEX_HOME", str(Path(__file__).parent.parent.parent)), "mindol"))
                self._mindol = _mindol_core.Mindol(storage_path=storage, persist=True)
            except Exception as _e:
                self._mindol = None

    def _mindol_sync_all(self):
        """将所有迭进数据同步到 Mindol 语义记忆引擎"""
        if self._mindol is None:
            self._init_mindol()
        if self._mindol is None:
            return
        import json, datetime
        now = datetime.datetime.now().isoformat()
        m = self._mindol

        # 1. 规则 → SPACE_RULE
        for r in self._interceptions:
            uid = f"rule_{r.id}"
            text = json.dumps({
                "id": r.id, "trigger": r.trigger_condition,
                "action": r.action, "severity": r.severity,
                "confidence": r.confidence, "status": r.lifecycle_status,
                "source": r.source, "created": r.created_at,
                "tags": getattr(r, "tags", [])
            }, ensure_ascii=False)
            m.add_unit(text=text, source="diegin_rule", uid=uid, space=m.SPACE_RULE)

        # 2. 成功模式 → SPACE_PATTERN
        for p in self._patterns:
            uid = f"pat_{p.id}"
            text = json.dumps({
                "id": p.id, "name": p.pattern_name, "scene": p.trigger_scenario,
                "confidence": p.confidence, "status": p.lifecycle_status,
                "source": p.source
            }, ensure_ascii=False)
            m.add_unit(text=text, source="diegin_pattern", uid=uid, space=m.SPACE_PATTERN)

        # 3. 元经验 → SPACE_ABSTRACT
        for meta in self._metas:
            uid = f"meta_{meta.id}"
            if meta.insight:
                m.add_unit(text=meta.insight, source="diegin_meta", uid=uid, space=m.SPACE_ABSTRACT)

        # 4. 同步 strikes/override → SPACE_TRADE
        try:
            _sp = str(Path(__file__).parent.parent.parent / "var" / "state" / "strikes_db.json")
            if os.path.exists(_sp):
                    with open(_sp, "r", encoding="utf-8") as _sf:
                        _sd = json.load(_sf)
                    self._mindol_sync_strikes(_sd)
        except Exception:
            pass

        # 5. 同步阶段状态 → SPACE_STATE
        try:
            _sd = {
                "active_rules": len(self._interceptions),
                "active_patterns": len(self._patterns),
                "staging_rules": sum(1 for r in self._interceptions if r.lifecycle_status == "staging"),
                "last_sync": now
            }
            self._mindol_sync_state(_sd)
        except Exception:
            pass

        m.save()

    def _mindol_sync_strikes(self, strikes_data: dict = None):
        """同步 strike/override 记录到 SPACE_TRADE"""
        if self._mindol is None:
            self._init_mindol()
        if self._mindol is None:
            return
        if not strikes_data:
            return
        import json
        m = self._mindol
        for error_type, info in strikes_data.items():
            uid = f"strike_{error_type}"
            text = json.dumps(info, ensure_ascii=False)
            unit = m.add_unit(text=text, source="diegin_strike", uid=uid, space=m.SPACE_TRADE)
            if unit:
                _et_tokens = set(error_type.lower().split("_"))
                for r in self._interceptions:
                    _rid_lower = r.id.lower()
                    _cond_lower = r.trigger_condition.lower()
                    # 任一 token 匹配规则 ID 或触发条件即建立关系
                    if any(t in _rid_lower or t in _cond_lower for t in _et_tokens if len(t) > 2):
                        m.add_relation(uid, f"rule_{r.id}", "strike_affects")
        m.save()

    def _mindol_sync_state(self, state_data: dict):
        """同步阶段状态到 SPACE_STATE"""
        if self._mindol is None:
            self._init_mindol()
        if self._mindol is None:
            return
        import json
        m = self._mindol
        uid = "current_phase_state"
        m.add_unit(text=json.dumps(state_data, ensure_ascii=False),
                   source="diegin_state", uid=uid, space=m.SPACE_STATE)
        m.save()

    # ─── Mindol 权威：新增辅助方法 ───

    def _sync_one_rule_to_mindol(self, rule):
        """同步单条规则到 Mindol"""
        import json as _j
        if not self._mindol:
            return
        uid = f"rule_{rule.id}"
        text = _j.dumps({
            "id": rule.id, "trigger": rule.trigger_condition,
            "action": rule.action, "severity": rule.severity,
            "confidence": rule.confidence, "status": rule.lifecycle_status,
            "source": rule.source, "created": rule.created_at,
            "tags": getattr(rule, "tags", [])
        }, ensure_ascii=False)
        self._mindol.add_unit(text=text, source="diegin_rule", uid=uid, space=self._mindol.SPACE_RULE)

    def _load_from_mindol(self) -> bool:
        """从 Mindol 权威源加载所有规则数据"""
        if not self._mindol:
            return False
        import json as _j
        try:
            # 1. 加载拦截规则
            rule_space = self._mindol.get_space(self._mindol.SPACE_RULE)
            if rule_space and rule_space.size > 0:
                interceptions = []
                for unit in rule_space.memory_units:
                    try:
                        data = _j.loads(unit.text)
                        ir = InterceptionRule(
                            id=data.get("id", unit.uid.replace("rule_", "")),
                            trigger_condition=data.get("trigger", ""),
                            action=data.get("action", "warn"),
                            severity=data.get("severity", "medium"),
                            tags=data.get("tags", []),
                            confidence=data.get("confidence", 3.0),
                            logic_score=data.get("logic_score", 5.0),
                            outcome_score=data.get("outcome_score", 5.0),
                            lifecycle_status=data.get("status", "active"),
                            source=data.get("source", "mindol"),
                            created_at=data.get("created", "")
                        )
                        interceptions.append(ir)
                    except Exception:
                        continue
                if interceptions:
                    self._interceptions = interceptions
            else:
                return False

            # 2. 加载成功模式
            pat_space = self._mindol.get_space(self._mindol.SPACE_PATTERN)
            if pat_space and pat_space.size > 0:
                patterns = []
                for unit in pat_space.memory_units:
                    try:
                        data = _j.loads(unit.text)
                        sp = SuccessPattern(
                            id=data.get("id", unit.uid.replace("pat_", "")),
                            pattern_name=data.get("name", ""),
                            trigger_scenario=data.get("scene", ""),
                            confidence=data.get("confidence", 3.0),
                            lifecycle_status=data.get("status", "active"),
                            source=data.get("source", "mindol")
                        )
                        patterns.append(sp)
                    except Exception:
                        continue
                if patterns:
                    self._patterns = patterns

            return True
        except Exception:
            return False

    def _rebuild_json_from_mindol(self):
        """从 Mindol 重建所有 JSON 文件（Mindol 权威 → JSON 副本）"""
        if not self._mindol or not self._interceptions:
            return
        try:
            self._save_json("interception_rules.json", self._interceptions)
            self._save_json("success_patterns.json", self._patterns)
            self._save_json("meta_experiences.json", self._metas)
            self._save_json("precedents.json", self._precedents)
            print("[MINDOL] JSON 副本已从 Mindol 重建")
        except Exception as e:
            print(f"[MINDOL] JSON 重建失败: {e}")

    def _verify_json_consistency(self) -> bool:
        """验证 JSON 副本是否与 Mindol 一致（仅检查规则数量）"""
        rule_file = self.rules_dir / "interception_rules.json"
        if not rule_file.exists():
            return False
        try:
            import json as _j
            with open(rule_file, "r", encoding="utf-8") as f:
                json_rules = _j.load(f)
            return len(json_rules) == len(self._interceptions)
        except Exception:
            return False

    # ─── 存储与加载 ───

    def _load_all(self):
        """加载所有规则数据 - 优先从 Mindol（权威源），失败时回退 JSON"""
        if self._mindol:
            if self._load_from_mindol():
                # Mindol 加载成功，确认 JSON 副本一致性，不一致则重建
                if not self._verify_json_consistency():
                    self._rebuild_json_from_mindol()
                return
        
        # Fallback: 从 JSON 加载（文件系统备份）
        self._interceptions = self._load_json("interception_rules.json", InterceptionRule)
        self._patterns = self._load_json("success_patterns.json", SuccessPattern)
        self._metas = self._load_json("meta_experiences.json", MetaExperience)
        self._precedents = self._load_json("precedents.json", Precedent)
        # 重建 Mindol 索引
        if self._mindol:
            self._mindol_sync_all()

    def _load_json(self, filename: str, cls, retry: bool = False):
        """加载 JSON 文件（失败时自动从备份恢复）"""
        import shutil, datetime as dt
        filepath = self.rules_dir / filename
        if not filepath.exists():
            return []
        try:
            with open(filepath, 'r', encoding='utf-8') as f:
                data = json.load(f)
            return [cls(**item) for item in data]
        except (json.JSONDecodeError, TypeError, KeyError) as e:
            print(f"[RULE_ENGINE] 加载 {filename} 失败: {e}")
            # 自动恢复：从最近有效备份恢复
            if not retry:
                bak = self._find_nearest_backup(filename)
                if bak:
                    print(f"[RULE_ENGINE] 从备份恢复: {bak.name}")
                    shutil.copy2(str(bak), str(filepath))
                    return self._load_json(filename, cls, retry=True)
            # 最终手段：备份损坏文件
            if filepath.exists():
                bak_path = filepath.parent / f"{filename}.err_{dt.datetime.now().strftime('%Y%m%d_%H%M%S')}"
                shutil.copy2(str(filepath), str(bak_path))
                print(f"[RULE_ENGINE] 已备份损坏文件至 {bak_path.name}")
            return []

    def _save_json(self, filename: str, data: List):
        """保存 JSON 文件（写前备份 + 原子写入 + 写后验证 + 阈值保护）"""
        import shutil, datetime as dt
        filepath = self.rules_dir / filename

        # Step 1: 写前备份
        bak_path = None
        if filepath.exists():
            bak_name = f"{filename}.pre_{dt.datetime.now().strftime('%Y%m%d_%H%M%S')}"
            bak_path = filepath.parent / bak_name
            shutil.copy2(str(filepath), str(bak_path))

        # Step 2: 原子写入（先写临时文件再 rename）
        tmp_path = filepath.parent / f"{filename}.tmp"
        with open(tmp_path, 'w', encoding='utf-8') as f:
            json.dump([asdict(item) for item in data], f, ensure_ascii=False, indent=2)
        os.replace(str(tmp_path), str(filepath))

        # Step 3: 读回验证
        with open(filepath, 'r', encoding='utf-8') as f:
            saved = json.load(f)

        # Step 4: 最小阈值保护
        min_rules = self.MIN_RULES.get(filename, 0)
        if len(saved) < min_rules:
            if bak_path and bak_path.exists():
                shutil.copy2(str(bak_path), str(filepath))
                print(f"[RULE_ENGINE] X 写后验证失败({filename}仅{len(saved)}条, 阈值={min_rules}) 已回滚")
            raise RuntimeError(f"_save_json validation failed: {filename} only {len(saved)} rules (min={min_rules})")

        # Step 5: 清理旧备份
        self._clean_old_backups(filename, keep=5)

    def save_all(self, force: bool = False):
        """保存所有规则 - Mindol（权威）先写，JSON（人类可读副本）后写"""
        filenames = {
            "interception_rules.json": self._interceptions,
            "success_patterns.json": self._patterns,
            "meta_experiences.json": self._metas,
            "precedents.json": self._precedents,
        }
        if force:
            to_save = list(filenames.keys())
        else:
            to_save = [f for f in self._dirty if f in filenames]

        # Step 1: 同步到 Mindol（权威存储，ACID 事务保护）
        try:
            self._init_mindol()
            if self._mindol:
                self._mindol_sync_all()
        except Exception as _e:
            print(f"[MINDOL] primary sync failed: {_e}")

        # Step 2: 写 JSON（人类可读同步副本）
        for fname in to_save:
            self._save_json(fname, filenames[fname])
        self._dirty.clear()

    # ─── 拦截规则 CRUD ───

    def add_interception(self, rule: InterceptionRule, auto_save: bool = False) -> str:
        """添加拦截规则 - 同步写入 Mindol（权威）"""
        if not rule.id:
            rule.id = f"rule_{datetime.now().strftime('%Y%m%d_%H%M%S')}_{hash(rule.trigger_condition) % 10000:04d}"
        if not rule.created_at:
            rule.created_at = datetime.now().isoformat()
        self._interceptions.append(rule)
        self._dirty.add("interception_rules.json")
        # 同步到 Mindol（权威存储）
        try:
            self._init_mindol()
            if self._mindol:
                self._sync_one_rule_to_mindol(rule)
        except Exception:
            pass
        if auto_save:
            self._save_json("interception_rules.json", self._interceptions)
        return rule.id

    def get_interceptions(self, active_only: bool = True) -> List[InterceptionRule]:
        """获取拦截规则列表"""
        if active_only:
            return [r for r in self._interceptions if r.lifecycle_status == "active"]
        return self._interceptions

    def get_interception_by_id(self, rule_id: str) -> Optional[InterceptionRule]:
        """根据 ID 获取规则"""
        for r in self._interceptions:
            if r.id == rule_id:
                return r
        return None

    def update_interception(self, rule_id: str, **kwargs) -> bool:
        """更新拦截规则 - 同步到 Mindol（权威）"""
        rule = self.get_interception_by_id(rule_id)
        if not rule:
            return False
        for key, value in kwargs.items():
            if hasattr(rule, key):
                setattr(rule, key, value)
        self._dirty.add("interception_rules.json")
        # 同步到 Mindol
        try:
            if self._mindol:
                self._sync_one_rule_to_mindol(rule)
        except Exception:
            pass
        return True

    def delete_interception(self, rule_id: str) -> bool:
        """删除拦截规则 - 从 Mindol（权威）同步删除"""
        for i, r in enumerate(self._interceptions):
            if r.id == rule_id:
                del self._interceptions[i]
                self._dirty.add("interception_rules.json")
                # 从 Mindol 删除
                try:
                    if self._mindol:
                        self._mindol.remove_unit(f"rule_{rule_id}")
                except Exception:
                    pass
                return True
        return False

    # ─── 成功模式 CRUD ───

    def add_pattern(self, pattern: SuccessPattern) -> str:
        """添加成功模式"""
        if not pattern.id:
            pattern.id = f"pattern_{datetime.now().strftime('%Y%m%d_%H%M%S')}_{hash(pattern.pattern_name) % 10000:04d}"
        if not pattern.created_at:
            pattern.created_at = datetime.now().isoformat()
        self._patterns.append(pattern)
        self._save_json("success_patterns.json", self._patterns)
        return pattern.id

    def get_patterns(self, active_only: bool = True) -> List[SuccessPattern]:
        """获取成功模式列表"""
        if active_only:
            return [p for p in self._patterns if p.lifecycle_status == "active"]
        return self._patterns

    def get_pattern_by_id(self, pattern_id: str) -> Optional[SuccessPattern]:
        """根据 ID 获取模式"""
        for p in self._patterns:
            if p.id == pattern_id:
                return p
        return None

    def update_pattern(self, pattern_id: str, **kwargs) -> bool:
        """更新成功模式"""
        pattern = self.get_pattern_by_id(pattern_id)
        if not pattern:
            return False
        for key, value in kwargs.items():
            if hasattr(pattern, key):
                setattr(pattern, key, value)
        self._save_json("success_patterns.json", self._patterns)
        return True

    def delete_pattern(self, pattern_id: str) -> bool:
        """删除成功模式"""
        for i, p in enumerate(self._patterns):
            if p.id == pattern_id:
                del self._patterns[i]
                self._save_json("success_patterns.json", self._patterns)
                return True
        return False

    # ─── 元经验 CRUD ───

    def add_meta(self, meta: MetaExperience) -> str:
        """添加元经验"""
        if not meta.id:
            meta.id = f"meta_{datetime.now().strftime('%Y%m%d_%H%M%S')}_{hash(meta.insight) % 10000:04d}"
        if not meta.created_at:
            meta.created_at = datetime.now().isoformat()
        self._metas.append(meta)
        self._save_json("meta_experiences.json", self._metas)
        return meta.id

    def get_metas(self) -> List[MetaExperience]:
        """获取所有元经验"""
        return self._metas

    # ─── 判例 CRUD ───

    def add_precedent(self, precedent: Precedent) -> str:
        """添加判例"""
        if not precedent.id:
            precedent.id = f"prec_{datetime.now().strftime('%Y%m%d_%H%M%S')}_{hash(str(precedent.conflict_rules)) % 10000:04d}"
        if not precedent.created_at:
            precedent.created_at = datetime.now().isoformat()
        self._precedents.append(precedent)
        self._save_json("precedents.json", self._precedents)
        return precedent.id

    def get_precedents(self) -> List[Precedent]:
        """获取所有判例"""
        return self._precedents

    # ─── 检索与匹配 ───

    def _rule_applies_to_context(self, rule_tags: List[str], context: Dict[str, Any]) -> bool:
        """全局常开模式：所有规则不按场景过滤，规则引擎只靠条件匹配"""
        return True

    def retrieve_for_task(self, task_context: Dict[str, Any]) -> Dict[str, List]:
        """
        根据任务上下文检索相关规则
        支持场景域过滤（基于tags + channel/task_type）
        返回: {"interceptions": [...], "patterns": [...]}
        """
        matched_interceptions = []
        matched_patterns = []

        for rule in self.get_interceptions(active_only=True):
            if not self._rule_applies_to_context(rule.tags, task_context):
                continue
            if self._match_condition(rule.trigger_condition, task_context):
                matched_interceptions.append(rule)

        for pattern in self.get_patterns(active_only=True):
            if not self._rule_applies_to_context(pattern.tags if hasattr(pattern, 'tags') else [], task_context):
                continue
            # trigger_condition 优先，空时回退到 trigger_scenario
            condition = getattr(pattern, 'trigger_condition', '') or pattern.trigger_scenario
            if self._match_condition(condition, task_context):
                matched_patterns.append(pattern)

        # ========== Mindol 语义回退：表达式匹配不到时使用语义检索 ==========
        if not matched_interceptions:
            try:
                _ctx_str = json.dumps(task_context, ensure_ascii=False)
                if self._mindol is None:
                    self._init_mindol()
                if self._mindol:
                    _results = self._mindol.retrieve(_ctx_str, top_k=5, spaces=["rule"])
                    for _unit, _score in _results:
                        if _score < 0.25:
                            continue
                        _uid = _unit.uid if hasattr(_unit, 'uid') else ''
                        if _uid.startswith('rule_'):
                            _rid = _uid[5:]
                            for _r in self._interceptions:
                                if _r.id == _rid and _r.lifecycle_status == 'active':
                                    if _r not in matched_interceptions:
                                        matched_interceptions.append(_r)
                                        break
            except Exception:
                pass  # Mindol 不可用时静默降级

        return {
            "interceptions": matched_interceptions,
            "patterns": matched_patterns
        }

    # ─── 攻七专用匹配 ───

    def match_patterns(self, context: dict, top_k: int = 5) -> list:
        """攻七：返回与上下文匹配的成功模式，复用 _match_condition AST引擎"""
        scored = []
        for pattern in self.get_patterns(active_only=True):
            condition = getattr(pattern, 'trigger_condition', '') or pattern.trigger_scenario
            if self._match_condition(condition, context):
                conf = getattr(pattern, 'confidence', 3.0) or 3.0
                auto_bonus = 2.0 if getattr(pattern, 'auto_promoted', False) else 1.0
                scored.append((conf * auto_bonus, pattern))
        scored.sort(key=lambda x: -x[0])
        return [s[1] for s in scored[:top_k]]

    def promote_pattern(self, pattern_id: str) -> bool:
        """自动提升：当 triggered_count>=3 且 outcome_score>=4.0"""
        pattern = self.get_pattern_by_id(pattern_id)
        if not pattern:
            return False
        tc = getattr(pattern, 'triggered_count', 0) or 0
        os_val = getattr(pattern, 'outcome_score', 0) or 0
        if tc >= 3 and os_val >= 4.0:
            import datetime
            now = datetime.datetime.now().isoformat()
            self.update_pattern(pattern_id,
                                auto_promoted=True,
                                promoted_from="auto",
                                promoted_at=now)
            return True
        return False

    def auto_promote_all(self) -> int:
        """扫描所有成功模式，自动提升符合条件的"""
        count = 0
        for p in self.get_patterns(active_only=True):
            if not getattr(p, 'auto_promoted', False):
                if self.promote_pattern(p.id):
                    count += 1
        return count

    def _match_condition(self, condition: str, context: Dict[str, Any]) -> bool:
        """
        匹配条件表达式（安全版·无 eval）
        支持: field == value, field > value, field in [list], startswith(), etc.
        """
        if not condition or condition.strip() == "":
            return True

        cond = condition.strip()

        # ── 快速路径：纯关键词（无运算符、方法调用、逻辑连接词）──
        ops = ['==', '!=', '>', '<', '>=', '<=', ' and ', ' or ', ' AND ', ' OR ',
               '.startswith(', '.contains(', ' in ', ' not ', 'in ', 'not ']
        if not any(op in cond for op in ops):
            ctx_str = str(context).lower()
            kw = cond.lower().strip("'\"")
            return kw in ctx_str

        # ── 安全 AST 评估路径 ──
        try:
            return self._safe_evaluate(cond, context)
        except Exception:
            pass

        # ── 回退：'x' in context 精确检查 ──
        # AST 无法将 'context' 解析为 dict 变量，导致 'x' in context 永远 False
        # 解决方法：手动检查含有 "in context" 的表达式
        try:
            if "' in context" in cond or '" in context' in cond:
                ctx_str_lower = str(context).lower()
                quoted = re.findall(r"'([^']+)' in context", cond)
                for pair in quoted:
                    q = pair[0] if pair[0] else pair[1]
                    if q.lower() in ctx_str_lower:
                        return True
                return False
        except Exception:
            pass
        
        # ── 回退：关键词模糊匹配（仅用于纯关键词） ──
        try:
            ctx_str = str(context).lower()
            cond_lower = cond.lower().strip()
            ops_check = ['==', '!=', '>', '<', '>=', '<=', ' and ', ' or ', '.startswith(', '.contains(', ' in ', ' not ']
            has_ops = any(op in cond_lower for op in ops_check)
            if not has_ops:
                kw = cond_lower.strip("'\"")
                if len(kw) > 3 and kw in ctx_str:
                    return True
        except Exception:
            pass
        return False

    def _safe_evaluate(self, expr: str, context: Dict[str, Any]) -> bool:
        """基于 AST 的安全布尔表达式求值（完全替代 eval()）"""
        import ast

        # 标准化逻辑运算符
        expr = expr.replace(' AND ', ' and ').replace(' OR ', ' or ')

        # 构建变量作用域
        scope = {}
        for key, value in context.items():
            if isinstance(value, str):
                try:
                    scope[key] = int(value)
                except ValueError:
                    try:
                        scope[key] = float(value)
                    except ValueError:
                        scope[key] = value
            else:
                scope[key] = value

        # 为常见布尔标记提供默认值
        scope.setdefault('has_diegin_rule', False)
        scope.setdefault('reply_unaffected', False)

        # 映射 context 到字符串表示，支持 'x' in context 模式
        scope['context'] = str(context)

        # 解析 AST
        try:
            tree = ast.parse(expr, mode='eval')
        except SyntaxError:
            return False

        # 裸词转换：将不在作用域中的 Name 节点转为 Constant（字符串）
        # 避免 NameError 的同时保证安全（AST级操作，无需字符串替换）
        PYTHON_KEYWORDS = frozenset({'True', 'False', 'None'})
        scope_keys = set(scope.keys())

        class BareWordToConstant(ast.NodeTransformer):
            def visit_Name(self, node):
                if node.id not in PYTHON_KEYWORDS and node.id not in scope_keys:
                    return ast.Constant(value=node.id)
                return node

        tree = BareWordToConstant().visit(tree)
        ast.fix_missing_locations(tree)

        # 允许的安全 AST 节点类型
        ALLOWED = frozenset({
            ast.Expression, ast.BoolOp, ast.Compare, ast.Call,
            ast.Name, ast.Constant, ast.Attribute,
            ast.Load, ast.Store,
            ast.Eq, ast.NotEq, ast.Gt, ast.Lt, ast.GtE, ast.LtE,
            ast.And, ast.Or, ast.Not, ast.UnaryOp, ast.USub,
            ast.List, ast.Tuple, ast.In, ast.NotIn,
        })

        for node in ast.walk(tree):
            if type(node) not in ALLOWED:
                return False

            if isinstance(node, ast.Call):
                if not isinstance(node.func, ast.Attribute):
                    return False
                if node.func.attr not in {'startswith', 'endswith', 'contains',
                                            'find', 'count', 'lower', 'upper', 'strip'}:
                    return False

        # 受限内置函数（仅白名单）
        safe_builtins = {
            "True": True, "False": False, "None": None,
            "int": int, "float": float, "str": str, "bool": bool,
            "len": len, "isinstance": isinstance,
        }

        try:
            code = compile(tree, '<safe_eval>', 'eval')
            result = eval(code, {"__builtins__": safe_builtins}, scope)
            return bool(result)
        except Exception:
            return False

    def detect_conflicts(self, interceptions: List[InterceptionRule],
                         patterns: List[SuccessPattern]) -> List[Dict]:
        """
        检测攻守规则之间的冲突
        返回: [{"interception": rule, "pattern": pattern, "conflict_type": "..."}]
        """
        conflicts = []
        for ir in interceptions:
            for p in patterns:
                ir_keywords = self._extract_keywords(ir.trigger_condition)
                p_keywords = self._extract_keywords(p.trigger_scenario)

                overlap = set(ir_keywords) & set(p_keywords)
                if len(overlap) >= 2:
                    conflicts.append({
                        "interception": ir,
                        "pattern": p,
                        "conflict_type": "trigger_overlap",
                        "overlap_keywords": list(overlap)
                    })

        return conflicts

    def _extract_keywords(self, text: str) -> List[str]:
        """提取关键词"""
        pattern = r"([a-zA-Z_][a-zA-Z0-9_.]*)|'([^']*)'|\"([^\"]*)\""
        matches = re.findall(pattern, text)
        keywords = []
        for m in matches:
            for part in m:
                if part and len(part) > 1:
                    keywords.append(part)
        return keywords


    # 鈹€鈹€鈹€ 鍔╂墜鏂规硶锛氬浠芥仮澶嶄笌娓呯悊 鈹€鈹€鈹€

    def _find_nearest_backup(self, filename: str):
        """鎵惧埌鏈€杩戠殑鏈夋晥澶囦唤鏂囦欢锛堟帓闄ゅ綋鍓嶆枃浠跺拰err澶囦唤锛?"""
        pattern = f"{filename}.*"
        backups = sorted(self.rules_dir.glob(pattern), key=os.path.getmtime, reverse=True)
        valid = [b for b in backups
                 if b.name != filename and ".err_" not in b.name
                 and ".bak" not in b.name and ".pre_" in b.name]
        return valid[0] if valid else None

    def _clean_old_backups(self, filename: str, keep: int = 5):
        """淇濈暀鏈€杩?keep 涓浠斤紝鍒犻櫎杩囨湡澶囦唤"""
        pattern = f"{filename}.*"
        backups = sorted(self.rules_dir.glob(pattern), key=os.path.getmtime, reverse=True)
        count = 0
        for b in backups:
            if b.name == filename or ".err_" in b.name:
                continue
            if count >= keep:
                try:
                    b.unlink()
                except:
                    pass
            else:
                count += 1


# ============================================================
# 种子规则初始化
# ============================================================

def get_seed_interceptions() -> List[InterceptionRule]:
    """获取硬编码种子规则（通用场景）"""
    now = datetime.now().isoformat()
    return [
        InterceptionRule(
            id="seed_debug_critical_001",
            trigger_condition="task_type == debug AND target == production",
            action="block_execution; force_confirmation",
            severity="critical",
            tags=["global", "irreversible"],
            logic_score=5.0, outcome_score=5.0, confidence=5.0,
            source="seed", source_review="system_init",
            created_at=now, valid_until="", lifecycle_status="active",
            boundary_conditions=["确认是否为真正的生产环境"], invalid_conditions=[]
        ),
        InterceptionRule(
            id="seed_file_destructive_002",
            trigger_condition="op == delete AND recursive == true",
            action="block_execution; require_explicit_approval",
            severity="high",
            tags=["global", "irreversible"],
            logic_score=5.0, outcome_score=5.0, confidence=5.0,
            source="seed", source_review="system_init",
            created_at=now, valid_until="", lifecycle_status="active",
            boundary_conditions=["用户明确要求递归删除时放行"], invalid_conditions=[]
        ),
        InterceptionRule(
            id="seed_network_external_003",
            trigger_condition="op == network AND target != localhost",
            action="permission_check; confirm_before_send",
            severity="medium",
            tags=["global"],
            logic_score=5.0, outcome_score=5.0, confidence=5.0,
            source="seed", source_review="system_init",
            created_at=now, valid_until="", lifecycle_status="active",
            boundary_conditions=["已配置的网络调用例外不受影响"], invalid_conditions=[]
        )
    ]
def init_rules_if_empty(rule_engine: RuleEngine):
    """如果规则库为空，注入种子规则（双重验证+自动恢复）"""
    rules = rule_engine.get_interceptions(active_only=False)
    if len(rules) > 0:
        return
    rules_dir = rule_engine.rules_dir
    import shutil, datetime as dt
    rules_file = rules_dir / "interception_rules.json"
    if rules_file.exists():
        bak_name = f"interception_rules.json.auto_{dt.datetime.now().strftime('%Y%m%d_%H%M%S')}"
        shutil.copy2(str(rules_file), str(rules_dir / bak_name))
        print(f"[SAFETY] 已备份原规则文件至 {bak_name}")
        # 双重验证：直接读文件确认是否真的为空
        try:
            with open(rules_file, 'r', encoding='utf-8') as f_check:
                direct_data = json.load(f_check)
            if direct_data and len(direct_data) > 0:
                print(f"[SAFETY] 警告：JSON文件实际有 {len(direct_data)} 条规则，但引擎读到0条！")
                # 尝试重新加载引擎
                rule_engine._load_all()
                still_empty = len(rule_engine.get_interceptions(active_only=False)) == 0
                if not still_empty:
                    print(f"[SAFETY] 重新加载成功，跳过种子注入")
                    return
                # 仍为空 → 从备份恢复
                bak = rule_engine._find_nearest_backup("interception_rules.json")
                if bak:
                    print(f"[SAFETY] 从备份恢复: {bak.name}")
                    shutil.copy2(str(bak), str(rules_file))
                    rule_engine._load_all()
                    return
        except Exception as e:
            print(f"[SAFETY] 文件双重检查异常: {e}, 尝试恢复...")
            bak = rule_engine._find_nearest_backup("interception_rules.json")
            if bak:
                print(f"[SAFETY] 从备份恢复: {bak.name}")
                shutil.copy2(str(bak), str(rules_file))
                rule_engine._load_all()
                return
    for rule in get_seed_interceptions():
        rule_engine.add_interception(rule)
    rule_engine.save_all()
    print("[OK] 种子规则注入完成，智能体已具备基础生存能力")


