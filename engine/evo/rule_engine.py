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
    decision_logic: str                        # 决策逻辑
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

        self._load_all()

    # ─── 存储与加载 ───

    def _load_all(self):
        """加载所有规则文件"""
        self._interceptions = self._load_json("interception_rules.json", InterceptionRule)
        self._patterns = self._load_json("success_patterns.json", SuccessPattern)
        self._metas = self._load_json("meta_experiences.json", MetaExperience)
        self._precedents = self._load_json("precedents.json", Precedent)

    def _load_json(self, filename: str, cls):
        """加载 JSON 文件"""
        filepath = self.rules_dir / filename
        if not filepath.exists():
            return []
        try:
            with open(filepath, 'r', encoding='utf-8') as f:
                data = json.load(f)
            return [cls(**item) for item in data]
        except (json.JSONDecodeError, TypeError, KeyError):
            return []

    def _save_json(self, filename: str, data: List):
        """保存 JSON 文件"""
        filepath = self.rules_dir / filename
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump([asdict(item) for item in data], f, ensure_ascii=False, indent=2)

    def save_all(self):
        """保存所有规则"""
        self._save_json("interception_rules.json", self._interceptions)
        self._save_json("success_patterns.json", self._patterns)
        self._save_json("meta_experiences.json", self._metas)
        self._save_json("precedents.json", self._precedents)

    # ─── 拦截规则 CRUD ───

    def add_interception(self, rule: InterceptionRule) -> str:
        """添加拦截规则"""
        if not rule.id:
            rule.id = f"rule_{datetime.now().strftime('%Y%m%d_%H%M%S')}_{hash(rule.trigger_condition) % 10000:04d}"
        if not rule.created_at:
            rule.created_at = datetime.now().isoformat()
        self._interceptions.append(rule)
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
        """更新拦截规则"""
        rule = self.get_interception_by_id(rule_id)
        if not rule:
            return False
        for key, value in kwargs.items():
            if hasattr(rule, key):
                setattr(rule, key, value)
        self._save_json("interception_rules.json", self._interceptions)
        return True

    def delete_interception(self, rule_id: str) -> bool:
        """删除拦截规则"""
        for i, r in enumerate(self._interceptions):
            if r.id == rule_id:
                del self._interceptions[i]
                self._save_json("interception_rules.json", self._interceptions)
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
            if self._match_condition(pattern.trigger_scenario, task_context):
                matched_patterns.append(pattern)

        return {
            "interceptions": matched_interceptions,
            "patterns": matched_patterns
        }

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

        # ── 回退：模糊关键词匹配 ──
        try:
            ctx_str = str(context).lower()
            cond_lower = cond.lower()
            for op_word in ['and', 'or', 'not']:
                cond_lower = cond_lower.replace(f' {op_word} ', ' ')
            for word in cond_lower.split():
                word = word.strip().strip("'").strip('"').strip("(").strip(")").strip(",")
                if len(word) > 3 and word in ctx_str:
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
    """如果规则库为空，注入种子规则"""
    if len(rule_engine.get_interceptions(active_only=False)) == 0:
        for rule in get_seed_interceptions():
            rule_engine.add_interception(rule)
        rule_engine.save_all()
        print("[OK] 种子规则注入完成，智能体已具备基础生存能力")



