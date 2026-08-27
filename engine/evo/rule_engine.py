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

import io
import json
import os
import re
import ast
import copy
import functools
from datetime import datetime, timedelta

@functools.lru_cache(maxsize=512)
def _compile_trigger_ast(expr: str):
    """标准化后的 trigger 表达式 → 安全 AST 树（lru_cache：高频匹配避免重复 parse）"""
    try:
        return ast.parse(expr, mode="eval")
    except SyntaxError:
        return None

from typing import List, Dict, Optional, Any
from dataclasses import dataclass, asdict, field
from pathlib import Path


# ============================================================
# 数据结构定义
# ============================================================

def _noise_reason(text: str) -> str:
    """[P4-20260806] 自动提取质量门（去伪存真·证必可验）：
    自动提炼成功模式/派生规则前必须通过本门；返回空字符串=通过，非空=拒绝原因。
    """
    if not text or not text.strip():
        return "空决策逻辑"
    if "\ufffd" in text:
        return "含替换字符 U+FFFD"
    # 乱码路径特征: E:\??\ 或任意段 \??\（用 chr(63) 构造问号，避免检测代码本身触发连续问号启发式）
    _q2 = chr(63) * 2
    # [2026-08-09] 修复：?? 未转义时被正则引擎解析为惰性量词，导致任意单条 / 或 \ 均误判为乱码路径
    _q2_esc = re.escape(_q2)
    if re.search(r"[\\/]" + _q2_esc + r"[\\/]", text) or "\\" + _q2 + "\\" in text or _q2 + "\\" in text:
        return "含乱码路径 " + _q2 + "（证据不可验证）"
    low = text.lower()
    # 疑似测试/临时样本（非真实成功经验）
    for h in ("x.txt", "test.txt", "_p0_", "_b1_", "_test", "test_", "\\temp\\", "\\tmp\\", "_bh_review", "_probe", "_verify", "probe.txt", "tmp.txt", "echo perf-test", "perf-test"):
        if h in low:
            return "疑似测试/临时样本: " + h
    # 只读查询命令（无写语义、无决策可学）作首行判定
    first = low.strip().splitlines()[0][:120] if low.strip().splitlines() else ""
    for c in ("get-content", "get-childitem", "select-string", "get-item", "test-path", "test-netconnection", "get-filehash", "dir ", "ls ", "cat ", "type "):
        if first.startswith(c):
            return "只读查询命令不作为攻七模式: " + c.strip()
    # git 只读子命令（-C 参数后仍判只读）
    if first.startswith("git ") and any(_s in first for _s in (" status", " log", " diff", " ls-files", " remote", " branch", " rev-parse", " config", " show", " blame")):
        return "git 只读查询不作为攻七模式"
    return ""


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


def build_gongqi_suggestions(patterns: list, top_n: int = 5, context: dict = None) -> list:
    """攻七推荐纯函数（v3.x 提取自 pre_check 内联逻辑，便于独立回归测试）

    训练/测试分离：本函数只做只读计算，不写规则库、不写 Mindol、不触发学习，
    回归测试可注入固定种子模式验证推荐行为，防"测试集泄漏进训练集"。
    规则：
      - 工具名级噪音（trigger 仅为 tool_name=='X'，任何工具调用都触发）→ 整体剔除
      - priority: confidence>=4.5 且 decision_logic 长度>=6
      - 排序：priority 优先，组内按 confidence 降序，同分按 created_at 新优先；总量截断 top_n
    """
    import json as _json
    _suggestions = []
    import re as _re
    # 纯工具名级触发（形如 tool_name == 'Bash'，无场景/操作区分）→ 推荐无信息量
    _tool_noise_re = _re.compile(r"^tool_name\s*==\s*['\"][^'\"]+['\"]$")
    try:
        _priority_sug = []
        _normal_sug = []
        for p in patterns:
            # [P0-20260825] 上下文相关性过滤：攻七建议只推与当前任务相关的经验
            # （此前全局取最高置信度模式，导致发布任务时推荐 git push 预检等无关建议，模型全部忽略）
            if context is not None:
                if not _pattern_relevant(p, context):
                    continue
            _s = {
                "id": getattr(p, "id", ""),
                "scenario": getattr(p, "trigger_scenario", ""),
                "decision": getattr(p, "decision_logic", ""),
                "confidence": getattr(p, "confidence", 0),
                "created_at": getattr(p, "created_at", ""),
            }
            _logic = str(getattr(p, "decision_logic", "") or "").strip()
            _conf = float(getattr(p, "confidence", 0) or 0)
            _trig = str(getattr(p, "trigger_condition", "") or "").strip()
            # 工具名级噪音过滤（P2a 防伪模式污染）：trigger 为 tool_name=='X' 的模式
            # 任何工具调用都触发，无场景区分，推荐无信息量 → 整体剔除，不进推荐列表
            if _tool_noise_re.match(_trig):
                continue
            # 高置信度 + 实质决策逻辑 → 优先采用（复用验证过的正确做法）
            _is_priority = _conf >= 4.5 and len(_logic) >= 6
            _s["priority"] = _is_priority
            if _is_priority:
                _priority_sug.append(_s)
            else:
                _normal_sug.append(_s)
        # 按置信度降序；同分按创建时间新优先（让新沉淀的经验更快浮出）
        def _sort_key(x):
            _conf = -float(x["confidence"])
            _ts = 0.0
            try:
                from datetime import datetime as _dt
                _raw = str(x.get("created_at", "") or "")
                if _raw:
                    _ts = _dt.fromisoformat(_raw.replace("Z", "+00:00")).timestamp()
            except Exception:
                _ts = 0.0
            return (_conf, -_ts)
        _priority_sug.sort(key=_sort_key)
        _normal_sug.sort(key=_sort_key)
        _suggestions = (_priority_sug + _normal_sug)[:top_n]
    except Exception:
        _suggestions = []
    return _suggestions


def _pattern_relevant(pattern, context: dict) -> bool:
    """攻七建议相关性判定：pattern 的 trigger/场景关键词是否出现在当前上下文文本中。
    context 为 None 时视为全相关（保持旧行为，测试兼容）。"""
    if not context:
        return True
    import re as _re
    ctx_str = ""
    try:
        ctx_str = _json_dumps_context(context).lower()
    except Exception:
        ctx_str = str(context).lower()
    trig = str(getattr(pattern, "trigger_condition", "") or "").lower()
    scene = str(getattr(pattern, "trigger_scenario", "") or "").lower()
    logic = str(getattr(pattern, "decision_logic", "") or "").lower()
    # 1) trigger/scenario/logic 中的关键词直接出现在上下文 → 相关
    toks = set()
    for _txt in (trig, scene):
        for _m in _re.finditer(r"[a-z][a-z_0-9]{2,}", _txt):
            _t = _m.group(0)
            if _t in ("auto", "fix", "the", "for", "and", "or", "not", "in",
                      "op_contains", "blocked_error_type", "tool_name", "task_type",
                      "command", "text", "prompt", "cmd", "hook_event_name",
                      "marker_missing", "true", "false", "none", "context",
                      "bash", "powershell", "shell", "pwsh", "cmd", "codex",
                      "tool", "name", "value", "check", "use", "with", "new",
                      "state", "path", "file", "data", "result", "status"):
                continue
            if len(_t) >= 4:
                toks.add(_t)
    if toks:
        for _t in toks:
            if _t in ctx_str:
                return True
    # 2) 错误类型关键词（command_failure/tool_error/git_push/encoding/timeout/write）显式比对
    for _kw in ("command_failure", "tool_error", "git_push", "encoding", "timeout",
                "file_write", "publish", "post", "editor", "browser", "chrome"):
        if _kw in trig or _kw in scene or _kw in logic:
            if _kw in ctx_str:
                return True
    # 3) 上下文带 blocked_error_type（一二不过三 override 阻断中）→ 错误类型相关模式命中
    _bet = str((context or {}).get("blocked_error_type", "") or "").lower()
    if _bet and (_bet in trig or _bet in scene):
        return True
    return False


def _json_dumps_context(context: dict) -> str:
    """上下文序列化（容错：含不可序列化字段时降级 str）"""
    try:
        return json.dumps(context, ensure_ascii=False, default=str)
    except Exception:
        return str(context)


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


    def _mindol_warn(self, ctx: str, exc: Exception):
        """记录 Mindol 同步失败（消除静默失败，防复发：失败必须可见）"""
        try:
            # 不再向 stderr 输出：PowerShell 钩子 2>&1 合并会污染引擎 JSON 输出
            try:
                _logp = os.path.join(os.path.dirname(__file__), "..", "..", "var", "logs", "diegin_audit.log")
                _logp = os.path.abspath(_logp)
                if os.path.isdir(os.path.dirname(_logp)):
                    _line = __import__("datetime").datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")[:-3] + f" [RULE_ENGINE][WARN] Mindol {ctx} failed: {exc}\n"
                    _old = ""
                    try:
                        with io.open(_logp, "r", encoding="utf-8", errors="replace") as _f:
                            _old = _f.read()
                    except Exception:
                        pass
                    with io.open(_logp, "w", encoding="utf-8") as _f:
                        _f.write(_line + _old)
            except Exception:
                pass
        except Exception:
            pass


    def _audit_reopen(self, pattern_id: str, from_status: str, to_status: str):
        """人工裁决审计：_force_reopen 复活 archived 模式必须留痕（防再生可追溯）"""
        try:
            _logp = os.path.join(os.path.dirname(__file__), "..", "..", "var", "logs", "diegin_audit.log")
            _logp = os.path.abspath(_logp)
            if os.path.isdir(os.path.dirname(_logp)):
                try:
                    from _audit_rotate import rotate_audit_log
                    rotate_audit_log(_logp)
                except Exception:
                    pass
                _line = __import__("datetime").datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")[:-3] + \
                    f" [RULE_ENGINE][AUDIT] _force_reopen pattern={pattern_id} {from_status}->{to_status}\n"
                _old = ""
                try:
                    with io.open(_logp, "r", encoding="utf-8", errors="replace") as _f:
                        _old = _f.read()
                except Exception:
                    pass
                with io.open(_logp, "w", encoding="utf-8") as _f:
                    _f.write(_line + _old)
        except Exception:
            pass


    def _validate_trigger(self, trigger: str) -> list:
        """恒真规则守卫（防复发 P2）：检测 trigger 是否可能在空/无关上下文下恒真
        返回问题列表（空 = 通过）。发现恒真只告警，不阻断写入（历史规则兼容）。
        """
        issues = []
        try:
            if not trigger or not trigger.strip():
                issues.append("trigger 为空（永远命中）")
                return issues
            t = trigger.strip()
            # 空条件（纯关键词）是合法设计（子串匹配），跳过
            ops = ['==', '!=', '>', '<', '>=', '<=', ' and ', ' or ', ' AND ', ' OR ',
                   '.startswith(', '.contains(', ' in ', ' not ', 'in ', 'not ']
            if not any(op in t for op in ops):
                return issues
            # 逻辑表达式中的裸词 → AST 会转字符串常量 → 恒真
            import re as _re
            for part in _re.split(r"\b(?:and|or|AND|OR)\b", t):
                part = part.strip().strip("()")
                if _re.match(r"^[A-Za-z_][A-Za-z0-9_]*$", part):
                    issues.append(f"逻辑表达式含裸词 '{part}'（AST 会转为字符串常量导致恒真）")
        except Exception as _e:
            issues.append(f"trigger 校验异常: {_e}")
        return issues

    # ─── 触发验证门（防死规则 P0）：真实钩子上下文模板 + 字段引用审计 ───
    # 钩子真实传入的上下文字段（与 diegin_pre_tool.ps1 / call_diegin.py pre_reply 一致）
    HOOK_CONTEXT_TEMPLATES = [
        {"task_type": "pre_tool", "tool_name": "Bash", "blocked_error_type": "",
         "marker_missing": False, "command": "Set-Content -Path a.py -Value x -NoNewline",
         "text": "Set-Content -Path a.py -Value x -NoNewline", "hook_event_name": "PreToolUse"},
        {"task_type": "pre_tool", "tool_name": "Bash", "blocked_error_type": "tool_error_Bash",
         "marker_missing": False, "command": "Get-ChildItem 不存在的路径", "text": "Get-ChildItem 不存在的路径",
         "hook_event_name": "PreToolUse"},
        {"task_type": "pre_tool", "tool_name": "Bash", "blocked_error_type": "command_failure",
         "marker_missing": False, "command": "& 'E:\\app\\python.exe' run.py", "text": "& 'E:\\app\\python.exe' run.py",
         "hook_event_name": "PreToolUse"},
        {"task_type": "user_prompt", "text": "用 WriteAllText 写文件", "prompt": "用 WriteAllText 写文件",
         "hook_event_name": "UserPromptSubmit"},
    ]
    # 内置/引擎级字段（安全求值器提供默认值或上下文映射）
    _BUILTIN_FIELDS = {"context", "True", "False", "None", "has_diegin_rule", "reply_unaffected",
                       "domain", "error_type", "op_contains", "prechecked"}

    def _trigger_known_fields(self) -> set:
        fields = set(self._BUILTIN_FIELDS)
        for tpl in self.HOOK_CONTEXT_TEMPLATES:
            fields.update(tpl.keys())
        return fields

    def _analyze_trigger_fields(self, trigger: str) -> tuple:
        """静态提取 trigger 引用的裸字段名（Name 节点），排除关键字/方法调用。
        返回 (引用字段集合, 未知字段集合)"""
        import ast as _ast
        import re as _re
        if not trigger or not trigger.strip():
            return set(), set()
        expr = trigger.strip()
        expr = _re.sub(r'\bAND\b', 'and', expr, flags=_re.IGNORECASE)
        expr = _re.sub(r'\bOR\b', 'or', expr, flags=_re.IGNORECASE)
        expr = _re.sub(r'\bNOT\s+IN\b', 'not in', expr, flags=_re.IGNORECASE)
        expr = _re.sub(r'\bNOT\b', 'not', expr, flags=_re.IGNORECASE)
        expr = _re.sub(r'\bIN\b', 'in', expr, flags=_re.IGNORECASE)
        try:
            tree = _ast.parse(expr, mode="eval")
        except SyntaxError:
            return set(), set()
        # op_contains 的参数是字面 token（BareWordToConstant 会转字符串常量），非字段引用，排除
        _opc_arg_ids = set()
        for node in _ast.walk(tree):
            if isinstance(node, _ast.Call) and isinstance(node.func, _ast.Name) \
                    and node.func.id == "op_contains":
                for _a in node.args:
                    if isinstance(_a, _ast.Name):
                        _opc_arg_ids.add(id(_a))
        names = set()
        for node in _ast.walk(tree):
            if isinstance(node, _ast.Name) and id(node) not in _opc_arg_ids:
                names.add(node.id)
        known = self._trigger_known_fields()
        return names, names - known

    def validate_trigger_live(self, trigger: str) -> list:
        """真实触发验证：字段引用审计 + 钩子模板命中测试
        返回 issues（P0=确定性死规则应拒绝；P1=仅语义字段；P2=模板未命中告警）
        空 trigger / 纯关键词 = 合法（子串匹配），跳过。"""
        issues = list(self._validate_trigger(trigger))
        if not trigger or not trigger.strip():
            return issues
        t = trigger.strip()
        ops = ['==', '!=', '>', '<', '>=', '<=', ' and ', ' or ', ' AND ', ' OR ',
               '.startswith(', '.contains(', ' in ', ' not ', 'in ', 'not ', 'op_contains(']
        if not any(op in t for op in ops):
            return issues  # 纯关键词（子串匹配）跳过
        # [P0-20260826] blocked_error_type 精确匹配：钩子真实字段（override 阻断上下文），
        # 任意错误类型值都可能出现（command_failure/tool_error_Bash/image_url/...），无需模板枚举
        import re as _re_bet
        if _re_bet.fullmatch(r'blocked_error_type\s*==\s*["\'][^"\']+["\']', t):
            return issues
        names, unknown = self._analyze_trigger_fields(t)
        for f in sorted(unknown):
            issues.append(f"[P0] trigger 引用上下文不存在的字段 '{f}'（钩子真实字段: task_type/tool_name/command/text/prompt/hook_event_name/marker_missing/blocked_error_type），该规则永远无法命中")
        if "domain" in names:
            issues.append("[P1] trigger 引用 'domain' 字段（钩子上下文无此字段，仅能靠 Mindol 语义检索召回，表达式匹配永不命中）")
        if not any(i.startswith("[P0]") for i in issues) and "context" not in names:
            hit_any = False
            for tpl in self.HOOK_CONTEXT_TEMPLATES:
                try:
                    if self._match_condition(t, tpl):
                        hit_any = True
                        break
                except Exception:
                    continue
            if not hit_any:
                issues.append("[P2] trigger 在全部真实钩子上下文模板下均未命中（写入了但可能永不触发，请用 command/text 关键词或 task_type 组合）")
        return issues

    def _guard_trigger(self, rule_id: str, trigger: str, kind: str) -> list:
        """写入/更新门：P0 抛错拒绝；P1/P2 打印告警。返回问题列表。"""
        issues = self.validate_trigger_live(trigger)
        p0 = [i for i in issues if i.startswith("[P0]")]
        if p0:
            raise ValueError("触发验证门拒绝写入 %s %s: %s" % (kind, rule_id, "; ".join(p0)))
        for i in issues:
            if i.startswith("[P1]") or i.startswith("[P2]"):
                print("[RULE-GUARD] %s %s: %s" % (kind, rule_id, i))
        return issues

    def _init_mindol(self):
        """懒加载 Mindol 实例"""
        if self._mindol is None:
            try:
                from mindol import core as _mindol_core
                storage = str(Path(os.environ.get("CODEX_HOME", str(Path(__file__).parent.parent.parent)), "mindol"))
                self._mindol = _mindol_core.Mindol(storage_path=storage, persist=True)
            except Exception as _e:
                self._mindol = None

    def _mindol_sync_all(self, force_status: bool = False):
        """将所有迭进数据同步到 Mindol 语义记忆引擎"""
        if self._mindol is None:
            self._init_mindol()
        if self._mindol is None:
            return
        import json, datetime
        now = datetime.datetime.now().isoformat()
        m = self._mindol
        # [L4-防再生] 权威状态快照：全量同步不得用内存陈旧状态覆盖 Mindol 权威 archived（旧进程覆盖防护）
        _auth_status = {}
        if not force_status:
            try:
                for _spn in (m.SPACE_RULE, m.SPACE_PATTERN):
                    _sp = m.get_space(_spn)
                    if _sp is None:
                        continue
                    for _u in _sp.memory_units:
                        try:
                            _d = json.loads(_u.text)
                            _auth_status[_u.uid] = _d.get("status", "")
                        except Exception:
                            pass
            except Exception:
                pass

        # 1. 规则 → SPACE_RULE
        for r in self._interceptions:
            uid = f"rule_{r.id}"
            text = json.dumps({
                "id": r.id, "trigger": r.trigger_condition,
                "action": r.action, "severity": r.severity,
                "confidence": r.confidence, "status": ("archived" if _auth_status.get("rule_" + r.id) == "archived" and r.lifecycle_status in ("active", "staging") else r.lifecycle_status),
                "source": r.source, "created": r.created_at,
                "tags": getattr(r, "tags", []),
                "boundary_conditions": getattr(r, "boundary_conditions", []) or []
            }, ensure_ascii=False)
            m.add_unit(text=text, source="diegin_rule", uid=uid, space=m.SPACE_RULE)
        # [统一存储] 全量同步后立即提交权威库
        if hasattr(m, "flush"):
            m.flush()
        else:
            m.save()

        # 2. 成功模式 → SPACE_PATTERN
        for p in self._patterns:
            uid = f"pat_{p.id}"
            text = json.dumps({
                "id": p.id, "name": p.pattern_name, "scene": p.trigger_scenario,
                "confidence": p.confidence, "status": ("archived" if _auth_status.get("pat_" + p.id) == "archived" and p.lifecycle_status in ("active", "staging") else p.lifecycle_status),
                "source": p.source,
                "decision_logic": p.decision_logic or "",
                "micro_template": p.micro_template or "",
                "trigger_condition": p.trigger_condition or "",
                "logic_score": p.logic_score, "outcome_score": p.outcome_score,
                "triggered_count": p.triggered_count, "auto_promoted": p.auto_promoted,
                "created_at": p.created_at or "", "last_triggered": p.last_triggered or "",
                "valid_until": p.valid_until or ""
            }, ensure_ascii=False)
            m.add_unit(text=text, source="diegin_pattern", uid=uid, space=m.SPACE_PATTERN)


        # [JSON 权威] 孤儿清理：Mindol 中已不在 JSON 的规则/模式单元删除（防删除项复活）
        if force_status:
            try:
                _rule_uids = {f"rule_{r.id}" for r in self._interceptions}
                _pat_uids = {f"pat_{p.id}" for p in self._patterns}
                for _spn, _valid in ((m.SPACE_RULE, _rule_uids), (m.SPACE_PATTERN, _pat_uids)):
                    _sp = m.get_space(_spn)
                    if _sp is None:
                        continue
                    for _u in list(_sp.memory_units):
                        if _u.uid not in _valid:
                            m.remove_unit(_u.uid)
            except Exception as _e:
                self._mindol_warn("mindol-orphan-cleanup", _e)

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
        # C1: 轻量提交（add_unit/add_relation 已落 SQL 未提交，flush 即提交）
        if hasattr(m, "flush"):
            m.flush()
        else:
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
        # C1: 轻量提交
        if hasattr(m, "flush"):
            m.flush()
        else:
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
            "tags": getattr(rule, "tags", []),
            "boundary_conditions": getattr(rule, "boundary_conditions", []) or []
        }, ensure_ascii=False)
        self._mindol.add_unit(text=text, source="diegin_rule", uid=uid, space=self._mindol.SPACE_RULE)
        # [统一存储] Mindol 为权威：写后立即 commit，防止进程退出丢数据（JSON 仅为单向镜像）
        if hasattr(self._mindol, "flush"):
            self._mindol.flush()
        else:
            self._mindol.save()

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
                            created_at=data.get("created", ""),
                            boundary_conditions=data.get("boundary_conditions", []) or []
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
                            source=data.get("source", "mindol"),
                            decision_logic=data.get("decision_logic", ""),
                            micro_template=data.get("micro_template", ""),
                            trigger_condition=data.get("trigger_condition", ""),
                            logic_score=data.get("logic_score", 5.0),
                            outcome_score=data.get("outcome_score", 5.0),
                            triggered_count=data.get("triggered_count", 0),
                            auto_promoted=data.get("auto_promoted", False),
                            created_at=data.get("created_at", ""),
                            last_triggered=data.get("last_triggered", ""),
                            valid_until=data.get("valid_until", "")
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
        """废弃：JSON 为权威后不再从 Mindol 重建 JSON（保留仅为向后兼容，无调用点）"""
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
            _arch_path = self.rules_dir / "interception_rules_archive.json"
            if _arch_path.exists():
                with open(_arch_path, "r", encoding="utf-8") as _af:
                    json_rules += _j.load(_af)
            json_ids = {it["id"] for it in json_rules}
            mindol_ids = set()
            if self._mindol:
                _sp = self._mindol.get_space(self._mindol.SPACE_RULE)
                if _sp:
                    mindol_ids = {u.uid.removeprefix("rule_") for u in _sp.memory_units}
            return json_ids == mindol_ids
        except Exception:
            return False

    # ─── 存储与加载 ───

    def _merge_dedup_by_id(self, items):
        """主+archive 合并去重（v3.8.1）：同 id 条目以后加载者（archive）为准，
        archived 终态覆盖主文件同 id active 副本，防归档模式/规则复活。"""
        _seen = {}
        for _it in items:
            _iid = getattr(_it, "id", None) or ""
            _seen[_iid] = _it
        return list(_seen.values())

    def _load_all(self):
        """加载所有规则数据 - JSON（完整权威）优先，Mindol 仅为检索镜像。

        历史缺陷修复（v3.6.6→）：Mindol 单元只存字段子集（规则 10/22 字段），
        以 Mindol 为权威加载后回写 JSON 会丢失 logic_score/outcome_score/
        valid_until/invalid_conditions/block_count 等 12 个字段（覆盖问题）。
        现改为 JSON 优先加载；JSON 缺失/全空时回退 Mindol（旧环境升级路径）。"""
        # [FIX v3.8.1] 主+archive 合并去重：同 id 以 archive（后加载）为准，
        # 防 archived 终态条目被主文件同 id active 副本复活
        self._interceptions = self._merge_dedup_by_id(
            self._load_json("interception_rules.json", InterceptionRule)
            + self._load_json("interception_rules_archive.json", InterceptionRule)
        )
        self._patterns = self._merge_dedup_by_id(
            self._load_json("success_patterns.json", SuccessPattern)
            + self._load_json("success_patterns_archive.json", SuccessPattern)
        )
        self._metas = self._load_json("meta_experiences.json", MetaExperience)
        self._precedents = self._load_json("precedents.json", Precedent)

        if not self._mindol:
            return
        # JSON 权威判定：核心规则文件存在且解析非空（规则库以 JSON 为唯一权威）
        _json_authoritative = (self.rules_dir / "interception_rules.json").exists() and bool(self._interceptions)
        if _json_authoritative:
            try:
                if self._verify_json_consistency():
                    # 增量：JSON 与 Mindol ID 集合一致 → 镜像无需重建（启动零写放大）
                    pass
                else:
                    # ID 不一致 → 全量重建检索镜像（单向，含孤儿清理）
                    self._mindol_sync_all(force_status=True)
            except Exception as _e:
                self._mindol_warn("load_all-sync-mindol", _e)
        elif self._load_from_mindol():
            # JSON 缺失/全空 → 从 Mindol 恢复（防误清空历史数据）
            pass

        # [治理] active 死规则自动归档（P0 字段审计：引用不存在字段=永不命中）
        if _json_authoritative:
            try:
                _archived_any = False
                for _r in list(self._interceptions):
                    if _r.lifecycle_status != "active":
                        continue
                    _p0 = [i for i in self.validate_trigger_live(_r.trigger_condition) if i.startswith("[P0]")]
                    if _p0:
                        _r.lifecycle_status = "archived"
                        self._sync_one_rule_to_mindol(_r)
                        _archived_any = True
                        print("[RULE_ENGINE][GOVERN] 死规则自动归档 %s: %s" % (_r.id, "; ".join(_p0)[:120]))
                if _archived_any:
                    self.save_all(force=True)
            except Exception as _e:
                self._mindol_warn("dead-rule-governance", _e)

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

    def _write_archive_file(self, filename: str, items: List):
        """写归档文件（原子写 + 读回验证）：归档为静态历史，精确反映内存归档集合，
        删除即消失（git 历史仍保留已删记录）。"""
        filepath = self.rules_dir / filename
        out = []
        for it in items:
            d = asdict(it) if not isinstance(it, dict) else it
            out.append(d)
        out.sort(key=lambda x: x.get("id", ""))
        tmp_path = filepath.parent / f"{filename}.tmp"
        with open(tmp_path, "w", encoding="utf-8") as f:
            json.dump(out, f, ensure_ascii=False, indent=2)
        os.replace(str(tmp_path), str(filepath))
        with open(filepath, "r", encoding="utf-8") as f:
            saved_arch = json.load(f)
        if len(saved_arch) != len(out):
            raise RuntimeError(f"_write_archive_file verify failed: {filename} {len(saved_arch)} != {len(out)}")

    def _save_json(self, filename: str, data: List):
        """保存 JSON 文件（写前备份 + 原子写入 + 写后验证 + 阈值保护）"""
        import shutil, datetime as dt
        filepath = self.rules_dir / filename

        # [L4-防再生] 计数保全：Mindol 权威单元不携带 triggered_count，
        # 任何全量重写(save_all/_rebuild_from_mindol)前从现有 JSON 合并最大计数，防清零
        if filename == "interception_rules.json":
            try:
                _existing = {}
                if filepath.exists():
                    with open(filepath, "r", encoding="utf-8") as _ef:
                        _old = json.load(_ef)
                    _existing = {it.get("id"): it for it in _old if isinstance(it, dict)}
                _arch_path = self.rules_dir / "interception_rules_archive.json"
                if _arch_path.exists():
                    with open(_arch_path, "r", encoding="utf-8") as _af:
                        _old_arch = json.load(_af)
                    for _it in _old_arch:
                        _existing.setdefault(_it.get("id"), _it)
                for _item in data:
                    _oid = _item.get("id") if isinstance(_item, dict) else getattr(_item, "id", None)
                    _o = _existing.get(_oid) or {}
                    for _k in ("triggered_count", "ignored_count", "override_count"):
                        _ov = _o.get(_k) or 0
                        _nv = (_item.get(_k) if isinstance(_item, dict) else getattr(_item, _k, 0)) or 0
                        if _ov > _nv:
                            if isinstance(_item, dict):
                                _item[_k] = _ov
                            else:
                                setattr(_item, _k, _ov)
                    for _k in ("last_triggered", "last_ignored"):
                        _ov = _o.get(_k) or ""
                        _nv = (_item.get(_k) if isinstance(_item, dict) else getattr(_item, _k, "")) or ""
                        if _ov and (not _nv or _ov > _nv):
                            if isinstance(_item, dict):
                                _item[_k] = _ov
                            else:
                                setattr(_item, _k, _ov)
            except Exception as _e:
                print(f"[RULE_ENGINE] count-preserve merge failed: {_e}")

        # [归档分区] archived → *_archive.json，非 archived → 主文件（主文件精简，git 可读）
        if filename in ("interception_rules.json", "success_patterns.json"):
            _arch_name = filename.replace(".json", "_archive.json")
            _archived = [x for x in data if getattr(x, "lifecycle_status", "") == "archived"]
            _main = [x for x in data if getattr(x, "lifecycle_status", "") != "archived"]
            if _archived:
                self._write_archive_file(_arch_name, _archived)
            data = _main

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

        # Step 5: 双存储一致性校验（防复发 P3）— JSON 镜像必须与 Mindol 权威一致
        if filename == "interception_rules.json":
            try:
                if self._mindol is None:
                    self._init_mindol()
                if self._mindol is not None:
                    _space = self._mindol.get_space(self._mindol.SPACE_RULE)
                    _mid_ids = set()
                    for _u in _space.memory_units:
                        try:
                            _d = json.loads(_u.text)
                            _mid_ids.add(_d.get("id"))
                        except Exception:
                            pass
                    _jid_ids = {item.get("id") for item in saved}
                    _arch_path = self.rules_dir / "interception_rules_archive.json"
                    if _arch_path.exists():
                        with open(_arch_path, "r", encoding="utf-8") as _af:
                            for _ait in json.load(_af):
                                _jid_ids.add(_ait.get("id"))
                    if _mid_ids != _jid_ids and len(_mid_ids) > 0:
                        _only_j = _jid_ids - _mid_ids
                        _only_m = _mid_ids - _jid_ids
                        self._mindol_warn(
                            "dual-store-consistency",
                            Exception(f"JSON 与 Mindol 不一致: onlyJSON={len(_only_j)} onlyMindol={len(_only_m)}")
                        )
            except Exception as _e:
                self._mindol_warn("dual-store-check", _e)

        # Step 6: 清理旧备份
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
        # C1 防再生：脏标记增量写——规则/模式单元已由 CRUD 逐条维护，
        # 仅当数量不一致才全量同步；常规路径只同步 strikes/state（flush 轻量提交）。
        try:
            self._init_mindol()
            if self._mindol:
                _rule_units = len(self._mindol.get_space(self._mindol.SPACE_RULE).memory_units)
                if _rule_units != len(self._interceptions):
                    print("[MINDOL] 规则数量不一致(memory=%d mindol=%d)，执行全量同步"
                          % (len(self._interceptions), _rule_units))
                    self._mindol_sync_all()
                else:
                    import os as _os
                    _sp = str(Path(__file__).parent.parent.parent / "var" / "state" / "strikes_db.json")
                    if _os.path.exists(_sp):
                        try:
                            with open(_sp, "r", encoding="utf-8") as _sf:
                                _sd = json.load(_sf)
                            if _sd:
                                self._mindol_sync_strikes(_sd)
                        except Exception:
                            pass
                    try:
                        _sd = {
                            "active_rules": len(self._interceptions),
                            "active_patterns": len(self._patterns),
                            "staging_rules": sum(1 for r in self._interceptions if r.lifecycle_status == "staging"),
                            "last_sync": datetime.now().isoformat()
                        }
                        self._mindol_sync_state(_sd)
                    except Exception:
                        pass
        except Exception as _e:
            print(f"[MINDOL] primary sync failed: {_e}")

        # Step 2: 写 JSON（人类可读同步副本）
        for fname in to_save:
            self._save_json(fname, filenames[fname])
        self._dirty.clear()

    # ─── 拦截规则 CRUD ───

    def add_interception(self, rule: InterceptionRule, auto_save: bool = False) -> str:
        """添加拦截规则 - 同步写入 Mindol（权威）"""
        _issues = self._validate_trigger(rule.trigger_condition)
        for _iss in _issues:
            self._mindol_warn(f"add_interception trigger-check [{rule.id}]", Exception(_iss))
        # 触发验证门：P0 拒绝（引用不存在字段=确定性死规则），P1/P2 告警
        self._guard_trigger(rule.id, rule.trigger_condition, "interception")
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
        except Exception as _e:
            self._mindol_warn("add_interception", _e)
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
        if "trigger_condition" in kwargs:
            _issues = self._validate_trigger(kwargs["trigger_condition"])
            for _iss in _issues:
                self._mindol_warn(f"update_interception trigger-check [{rule_id}]", Exception(_iss))
            self._guard_trigger(rule_id, kwargs["trigger_condition"], "interception")
        for key, value in kwargs.items():
            if hasattr(rule, key):
                setattr(rule, key, value)
        self._dirty.add("interception_rules.json")
        # 同步到 Mindol
        try:
            if self._mindol:
                self._sync_one_rule_to_mindol(rule)
        except Exception as _e:
            self._mindol_warn("update_interception", _e)
        return True

    def delete_interception(self, rule_id: str) -> bool:
        """删除拦截规则 - 从 Mindol（权威）同步删除（v3.6.3 补懒加载）"""
        for i, r in enumerate(self._interceptions):
            if r.id == rule_id:
                del self._interceptions[i]
                self._dirty.add("interception_rules.json")
                # 从 Mindol 删除
                try:
                    if self._mindol is None:
                        self._init_mindol()
                    if self._mindol:
                        self._mindol.remove_unit(f"rule_{rule_id}")
                        if hasattr(self._mindol, "flush"):
                            self._mindol.flush()
                        else:
                            self._mindol.save()
                except Exception as _e:
                    self._mindol_warn("delete_interception", _e)
                return True
        return False

    # ─── 成功模式 CRUD ───

    def add_pattern(self, pattern: SuccessPattern) -> str:
        """添加成功模式（同步写 Mindol 权威源，与 update_pattern 一致）"""
        if getattr(pattern, "trigger_condition", ""):
            self._guard_trigger(pattern.id, pattern.trigger_condition, "pattern")
        if not pattern.id:
            pattern.id = f"pattern_{datetime.now().strftime('%Y%m%d_%H%M%S')}_{hash(pattern.pattern_name) % 10000:04d}"
        # [L4-防再生] 幂等去重：同 id 已存在 → 不重复入库，返回现有 id（防重复模式堆积）
        _dup = self.get_pattern_by_id(pattern.id)
        if _dup is not None:
            self._mindol_warn(
                "add_pattern-dup-guard",
                Exception(f"模式 {pattern.id} 已存在，跳过重复添加（保留现有状态={_dup.lifecycle_status}）")
            )
            return _dup.id
        if not pattern.created_at:
            pattern.created_at = datetime.now().isoformat()
        if not pattern.last_triggered and pattern.triggered_count and pattern.triggered_count > 0:
            pattern.last_triggered = datetime.now().isoformat()
        self._patterns.append(pattern)
        self._save_json("success_patterns.json", self._patterns)
        # 同步 Mindol 权威单元（幂等 uid；失败必须可见，防再生）
        try:
            if self._mindol is None:
                self._init_mindol()
            if self._mindol:
                import json as _j
                _m = self._mindol
                _uid = f"pat_{pattern.id}"
                _text = _j.dumps({
                    "id": pattern.id, "name": pattern.pattern_name, "scene": pattern.trigger_scenario,
                    "confidence": pattern.confidence, "status": pattern.lifecycle_status,
                    "source": pattern.source,
                    "decision_logic": pattern.decision_logic or "",
                    "micro_template": pattern.micro_template or "",
                    "trigger_condition": pattern.trigger_condition or "",
                    "logic_score": pattern.logic_score, "outcome_score": pattern.outcome_score,
                    "triggered_count": pattern.triggered_count, "auto_promoted": pattern.auto_promoted,
                    "created_at": pattern.created_at or "", "last_triggered": pattern.last_triggered or "",
                    "valid_until": pattern.valid_until or ""
                }, ensure_ascii=False)
                _m.add_unit(text=_text, source="diegin_pattern", uid=_uid, space=_m.SPACE_PATTERN)
                # 写后立即 commit，防止进程退出丢数据（与 _sync_one_rule_to_mindol 一致）
                if hasattr(_m, "flush"):
                    _m.flush()
                else:
                    _m.save()
        except Exception as _e:
            self._mindol_warn("add_pattern", _e)
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
        """更新成功模式（v3.6.1 同步写 Mindol 权威源）"""
        if kwargs.get("trigger_condition"):
            self._guard_trigger(pattern_id, kwargs["trigger_condition"], "pattern")
        pattern = self.get_pattern_by_id(pattern_id)
        if not pattern:
            return False
        # [L4-防再生] 状态转换护栏：archived 是终态，仅显式 _force_reopen=True 才可复活
        _cur_status = getattr(pattern, "lifecycle_status", "") or ""
        _new_status = kwargs.get("lifecycle_status")
        if _new_status and _new_status in ("active", "staging") and _cur_status == "archived":
            _force = kwargs.pop("_force_reopen", False)
            if not _force:
                self._mindol_warn(
                    "update_pattern-reopen-guard",
                    Exception(f"拒绝复活 archived 模式 {pattern_id} -> {_new_status}（需显式 _force_reopen=True）")
                )
                return False
            self._audit_reopen(pattern_id, _cur_status, _new_status)
        # [L4-防再生] 旧进程内存覆盖防护：kwargs 未显式改状态时，
        # 以 Mindol(SQLite) 权威状态纠正内存陈旧值，防止 active 旧缓存写回 JSON/Mindol
        if not kwargs.get("lifecycle_status"):
            _auth_status = None
            try:
                if self._mindol is None:
                    self._init_mindol()
                if self._mindol is not None:
                    _db = getattr(self._mindol, "_db", None)
                    if _db is not None:
                        _uid = f"pat_{pattern_id}"
                        _row = _db.execute("SELECT text FROM memory_units WHERE uid=?", (_uid,)).fetchone()
                        if _row:
                            import json as _aj
                            _auth_status = _aj.loads(_row[0]).get("status")
            except Exception:
                _auth_status = None
            if _auth_status and _auth_status != _cur_status:
                # 内存陈旧（旧进程缓存 active）→ 以权威 archived 纠正，防止全量覆盖复活
                pattern.lifecycle_status = _auth_status
        for key, value in kwargs.items():
            if hasattr(pattern, key):
                setattr(pattern, key, value)
        self._save_json("success_patterns.json", self._patterns)
        # 同步 Mindol 权威单元（幂等 uid）
        try:
            if self._mindol is None:
                self._init_mindol()
            if self._mindol:
                import json as _j
                _m = self._mindol
                _uid = f"pat_{pattern.id}"
                _status_out = kwargs.get("lifecycle_status")
                if not _status_out:
                    # 权威状态保护：未显式改状态 → 保留 Mindol 现有权威状态（防旧进程内存覆盖）
                    try:
                        _db = getattr(_m, "_db", None)
                        if _db is not None:
                            _row = _db.execute("SELECT text FROM memory_units WHERE uid=?", (_uid,)).fetchone()
                            if _row:
                                _status_out = _j.loads(_row[0]).get("status", pattern.lifecycle_status)
                    except Exception:
                        _status_out = pattern.lifecycle_status
                _text = _j.dumps({
                    "id": pattern.id, "name": pattern.pattern_name, "scene": pattern.trigger_scenario,
                    "confidence": pattern.confidence, "status": _status_out or pattern.lifecycle_status,
                    "source": pattern.source,
                    "decision_logic": pattern.decision_logic or "",
                    "micro_template": pattern.micro_template or "",
                    "trigger_condition": pattern.trigger_condition or "",
                    "logic_score": pattern.logic_score, "outcome_score": pattern.outcome_score,
                    "triggered_count": pattern.triggered_count, "auto_promoted": pattern.auto_promoted,
                    "created_at": pattern.created_at or "", "last_triggered": pattern.last_triggered or "",
                    "valid_until": pattern.valid_until or ""
                }, ensure_ascii=False)
                _m.add_unit(text=_text, source="diegin_pattern", uid=_uid, space=_m.SPACE_PATTERN)
                # 写后立即 commit，防止进程退出丢数据
                if hasattr(_m, "flush"):
                    _m.flush()
                else:
                    _m.save()
        except Exception:
            pass
        return True

    def delete_pattern(self, pattern_id: str) -> bool:
        """删除成功模式（v3.6.1 同步删除 Mindol 权威单元）"""
        for i, p in enumerate(self._patterns):
            if p.id == pattern_id:
                del self._patterns[i]
                self._save_json("success_patterns.json", self._patterns)
                try:
                    if self._mindol is None:
                        self._init_mindol()
                    if self._mindol:
                        self._mindol.remove_unit(f"pat_{pattern_id}")
                except Exception:
                    pass
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
            # v3.6: 增强匹配（修复 tool_xxx 空壳模式错位）
            if self._match_pattern_context(pattern, task_context):
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
                                    # v3.6.5: 语义回退必须二次表达式确认，防止语义误匹配拉入不相关规则
                                    try:
                                        if self._match_condition(_r.trigger_condition, task_context):
                                            if _r not in matched_interceptions:
                                                matched_interceptions.append(_r)
                                    except Exception:
                                        pass
                                    break
            except Exception:
                pass  # Mindol 不可用时静默降级

        return {
            "interceptions": matched_interceptions,
            "patterns": matched_patterns
        }

    # ─── 攻七专用匹配 ───

    def _match_pattern_context(self, pattern, context: dict) -> bool:
        """模式增强匹配（v3.6）：修复 tool_xxx 空壳模式匹配错位
        1) 标准条件匹配（原 _match_condition 逻辑）
        2) tool_xxx 场景：与 tool_name/tool/op/cmd 字段比对（去前缀、去分隔符）
        """
        scenario = getattr(pattern, 'trigger_scenario', '') or ''
        condition = getattr(pattern, 'trigger_condition', '') or scenario
        if condition and condition.strip():
            if self._match_condition(condition, context):
                return True
        # tool_xxx 场景增强匹配
        if scenario.startswith('tool_'):
            tool_key = scenario[len('tool_'):].strip().lower()
            if not tool_key:
                return False
            ctx_str = str(context).lower()
            if scenario.lower() in ctx_str:
                return True
            for field in ('tool_name', 'tool', 'op'):
                val = str(context.get(field, '') or '').lower()
                if val and (tool_key in val or val in tool_key):
                    return True
            norm_key = tool_key.replace('_', '').replace('-', '')
            for field in ('cmd', 'command', 'text', 'prompt'):
                val = str(context.get(field, '') or '').lower()
                if val:
                    norm_val = val.replace('_', '').replace('-', '').replace(' ', '')
                    if norm_key and norm_key in norm_val:
                        return True
        return False

    def match_patterns(self, context: dict, top_k: int = 5) -> list:
        """攻七：返回与上下文匹配的成功模式（v3.6 增强 tool_xxx 匹配）"""
        scored = []
        for pattern in self.get_patterns(active_only=True):
            if not self._match_pattern_context(pattern, context):
                continue
            conf = getattr(pattern, 'confidence', 3.0) or 3.0
            auto_bonus = 2.0 if getattr(pattern, 'auto_promoted', False) else 1.0
            scored.append((conf * auto_bonus, pattern))
        scored.sort(key=lambda x: -x[0])
        return [s[1] for s in scored[:top_k]]

    def promote_pattern(self, pattern_id: str) -> bool:
        """自动提升（v3.6.3 验证门）：
        staging 模式第2次成功触发（tc>=2）= 可复用验证通过 → 转 active
        active 模式 tc>=3 且 outcome_score>=4.0 → auto_promoted 强化
        """
        pattern = self.get_pattern_by_id(pattern_id)
        if not pattern:
            return False
        # [P4-20260806] 自动提取质量门：噪音模式不得提升（去伪存真·证必可验）
        try:
            _why = _noise_reason(getattr(pattern, "decision_logic", "") or "")
            if _why:
                self._mindol_warn("promote_pattern-quality-gate", Exception(f"{pattern_id} 拒绝提升: {_why}"))
                return False
        except Exception:
            pass
        import datetime
        now = datetime.datetime.now().isoformat()
        tc = getattr(pattern, 'triggered_count', 0) or 0
        os_val = getattr(pattern, 'outcome_score', 0) or 0
        status = getattr(pattern, 'lifecycle_status', '') or ''
        if status == "staging" and tc >= 2:
            # 验证门：第2次成功 = 可复用性验证通过
            self.update_pattern(pattern_id,
                                lifecycle_status="active",
                                promoted_from="verified",
                                promoted_at=now)
            return True
        if status == "active" and tc >= 3 and os_val >= 4.0:
            self.update_pattern(pattern_id,
                                auto_promoted=True,
                                promoted_from="auto",
                                promoted_at=now)
            return True
        return False

    def auto_promote_all(self) -> int:
        """扫描所有成功模式，自动提升符合条件的（v3.6.3 含 staging 验证转正）"""
        count = 0
        for p in self.get_patterns(active_only=False):
            if not getattr(p, 'auto_promoted', False):
                if self.promote_pattern(p.id):
                    count += 1
        return count

    def demote_patterns(self) -> int:
        """无效淘汰（v3.6.3）：高频触发但低效果的模式降级或归档（防误杀高成功模式）
        - triggered_count>=8 且 outcome_score<3.0 → archived（高频但效果平庸，淘汰）
        - triggered_count>=5 且 outcome_score<2.0 → archived（效果极差，淘汰）
        - active 且 triggered_count>=5 且 confidence<2.5 → staging（降级再观察）
        注意：高 outcome_score 的高频模式（如 outcome>=4.0）不淘汰，只淘汰"高频但无效果"模式。
        """
        count = 0
        for p in self.get_patterns(active_only=False):
            status = getattr(p, 'lifecycle_status', '') or ''
            if status not in ("active", "staging"):
                continue
            tc = getattr(p, 'triggered_count', 0) or 0
            conf = getattr(p, 'confidence', 0) or 0
            os_val = getattr(p, 'outcome_score', 0) or 0
            if (tc >= 8 and os_val < 3.0) or (tc >= 5 and os_val < 2.0):
                self.update_pattern(p.id, lifecycle_status="archived")
                count += 1
            elif status == "active" and tc >= 5 and conf < 2.5:
                self.update_pattern(p.id, lifecycle_status="staging")
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
               '.startswith(', '.contains(', ' in ', ' not ', 'in ', 'not ', 'op_contains(']
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

        # 标准化逻辑运算符（大小写不敏感：AND/And/OR/Or 均可）
        import re as _re
        expr = _re.sub(r'\bAND\b', 'and', expr, flags=_re.IGNORECASE)
        expr = _re.sub(r'\bOR\b', 'or', expr, flags=_re.IGNORECASE)
        expr = _re.sub(r'\bNOT\s+IN\b', 'not in', expr, flags=_re.IGNORECASE)
        expr = _re.sub(r'\bNOT\b', 'not', expr, flags=_re.IGNORECASE)
        expr = _re.sub(r'\bIN\b', 'in', expr, flags=_re.IGNORECASE)

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

        # op_contains 谓词（去伪存真约束：字段白名单 + 字符串常量参数，禁止任意表达式）
        _op_fields = ("blocked_error_type", "op", "error_type", "type", "cmd", "text")
        def _op_contains(_token) -> bool:
            if not isinstance(_token, str) or len(_token.strip()) < 3:
                return False
            _t = _token.strip().lower()
            for _f in _op_fields:
                _v = str(context.get(_f, "") or "").lower()
                if _v and _t in _v:
                    return True
            return False
        scope['op_contains'] = _op_contains
        # tracker 生成规则标志：prechecked（已预检）默认 False（未预检 → NOT prechecked 为真）
        scope.setdefault('prechecked', False)

        # 裸词转换：将不在作用域中的 Name 节点转为 Constant（字符串）
        # 避免 NameError 的同时保证安全（AST级操作，无需字符串替换）
        PYTHON_KEYWORDS = frozenset({'True', 'False', 'None'})
        scope_keys = set(scope.keys())

        # 小写布尔归一：true/false -> True/False（在 AST 转换前，用词边界替换避免误伤字符串）
        expr = _re.sub(r'\btrue\b', 'True', expr)
        expr = _re.sub(r'\bfalse\b', 'False', expr)
        # 解析 AST（lru_cache 缓存标准化后的语法树，避免每次匹配重复 parse；
        # 返回副本供 BareWordToConstant 就地变换，防共享缓存树被污染）
        tree = _compile_trigger_ast(expr)
        if tree is None:
            return False
        tree = copy.deepcopy(tree)

        class BareWordToConstant(ast.NodeTransformer):
            def visit_Name(self, node):
                if node.id not in PYTHON_KEYWORDS and node.id not in scope_keys:
                    return ast.Constant(value=node.id)
                return node

            def visit_Attribute(self, node):
                # 处理 .py / .json 等属性节点（如 file_extension IN [.py, .json]）
                return ast.Constant(value=node.attr)

            def visit_BinOp(self, node):
                # 先处理子节点（保证 Name/Attribute 已转为 Constant）
                self.generic_visit(node)
                # 处理连字符裸词: Set-Content -> 'Set-Content'（AST 解析为 Set - Content 减法）
                if isinstance(node.op, ast.Sub):
                    left = node.left
                    right = node.right
                    if isinstance(left, ast.Constant) and isinstance(right, ast.Constant) \
                            and isinstance(left.value, str) and isinstance(right.value, str):
                        return ast.Constant(value=f"{left.value}-{right.value}")
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
                # op_contains('token') / op_contains(token)：单字符串常量参数白名单
                if isinstance(node.func, ast.Name) and node.func.id == "op_contains":
                    if len(node.args) != 1 or not isinstance(node.args[0], ast.Constant) \
                            or not isinstance(node.args[0].value, str):
                        return False
                    continue
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
            trigger_condition="task_type == 'pre_tool' AND command.contains('production')",
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
            trigger_condition="task_type == 'pre_tool' AND command.contains('Remove-Item') AND command.contains('-Recurse')",
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
            trigger_condition="task_type == 'pre_tool' AND (command.contains('Invoke-WebRequest') OR command.contains('curl'))",
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
