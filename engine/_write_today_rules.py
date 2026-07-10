import sys
from pathlib import Path
from datetime import datetime

sys.path.insert(0, str(Path(__file__).resolve().parent))
from evo.main import _get_engine
from evo.rule_engine import InterceptionRule, SuccessPattern

engine = _get_engine()
now = datetime.now().isoformat()

# ── 新增 7 条拦截规则 ──
new_rules = [
    InterceptionRule(
        id="rule_custom_001",
        trigger_condition="outbound_message and not outbound_message.startswith('[DGEN')",
        action="block_reply; re_activate_diegin",
        severity="high",
        tags=["global", "marker_enforcement"],
        logic_score=5.0, outcome_score=5.0, confidence=5.0,
        source="learned", source_review="2026-06-20-global-test",
        created_at=now, lifecycle_status="active",
        boundary_conditions=["空消息不判定拦截"],
        invalid_conditions=["消息已含[DGEN]标记时放行"]
    ),
    InterceptionRule(
        id="rule_no_binary_hack_001",
        trigger_condition="task_type == 'binary_modify' AND target == 'app.asar'",
        action="block_execution; suggest_plugin_alternative",
        severity="high",
        tags=["global", "system_safety"],
        logic_score=5.0, outcome_score=5.0, confidence=5.0,
        source="learned", source_review="2026-06-20-asar-crash",
        created_at=now, lifecycle_status="active"
    ),
    InterceptionRule(
        id="rule_subagent_marker_001",
        trigger_condition="session_type == 'subagent' AND not has_diegin_rule",
        action="block_reply; inject_diegin_task",
        severity="medium",
        tags=["global", "subagent_coverage"],
        logic_score=4.5, outcome_score=4.5, confidence=4.5,
        source="learned", source_review="2026-06-20-test8-fail",
        created_at=now, lifecycle_status="active"
    ),
    InterceptionRule(
        id="rule_iron_wall_loop_001",
        trigger_condition="diegin_consecutive_blocks >= 3",
        action="escalate; notify_user_engine_check",
        severity="high",
        tags=["global", "safety_valve"],
        logic_score=5.0, outcome_score=4.5, confidence=4.8,
        source="learned", source_review="2026-06-20-iron-wall-deadlock",
        created_at=now, lifecycle_status="active"
    ),
    InterceptionRule(
        id="rule_empty_context_001",
        trigger_condition="diegin_context == {} OR diegin_task_type == ''",
        action="mark_not_applicable; do_not_block",
        severity="low",
        tags=["global", "context_guard"],
        logic_score=4.5, outcome_score=4.5, confidence=4.5,
        source="learned", source_review="2026-06-20-empty-context",
        created_at=now, lifecycle_status="active"
    ),
    InterceptionRule(
        id="rule_gateway_client_coverage_001",
        trigger_condition="message_source == 'gateway_client' AND not message.content.startswith('[DGEN')",
        action="inject_marker; escalate_if_persistent",
        severity="medium",
        tags=["global", "routing_coverage"],
        logic_score=4.5, outcome_score=4.0, confidence=4.3,
        source="learned", source_review="2026-06-20-gateway-client-miss",
        created_at=now, lifecycle_status="active"
    ),
    InterceptionRule(
        id="rule_decorative_marker_001",
        trigger_condition="matched_interceptions > 0 AND reply_unaffected",
        action="block_normal_reply; enforce_arbitration_table",
        severity="high",
        tags=["global", "decision_enforcement"],
        logic_score=5.0, outcome_score=5.0, confidence=5.0,
        source="learned", source_review="2026-06-20-empty-marker-discovered",
        created_at=now, lifecycle_status="active"
    ),
]

for r in new_rules:
    existing = engine.get_interception_by_id(r.id)
    if existing:
        engine.update_interception(r.id, severity=r.severity, logic_score=r.logic_score, outcome_score=r.outcome_score, confidence=r.confidence)
    else:
        engine.add_interception(r)

print(f"Interception rules added/updated: {len(new_rules)}")
print(f"Total interceptions now: {len(engine.get_interceptions())}")

# ── 新增 4 条成功模式 ──
new_patterns = [
    SuccessPattern(
        id="pat_global_full_matrix_001",
        pattern_name="全局全域全量测试覆盖",
        trigger_scenario="迭进部署验证",
        decision_logic="按8×N矩阵逐项验证每个消息入口、每种消息类型，确保迭进全通路覆盖",
        micro_template="全量测试矩阵覆盖→逐项确认→彻底闭环",
        logic_score=5.0, outcome_score=5.0, confidence=5.0,
        source="learned", created_at=now, lifecycle_status="active"
    ),
    SuccessPattern(
        id="pat_all_path_coverage_001",
        pattern_name="全出站路径8hook闭环",
        trigger_scenario="迭进出站注入设计",
        decision_logic="8个hook覆盖所有消息路由路径: message_sending, before_dispatch, tool_result_persist, before_agent_finalize, reply_dispatch, agent_end, before_prompt_build, subagent_spawning",
        micro_template="多hook冗余覆盖→全出站路径→零遗漏",
        logic_score=5.0, outcome_score=5.0, confidence=5.0,
        source="learned", created_at=now, lifecycle_status="active"
    ),
    SuccessPattern(
        id="pat_engine_domain_separation_001",
        pattern_name="引擎不要处理编码隔离问题",
        trigger_scenario="引擎输入层设计",
        decision_logic="引擎只接收字典/JSON对象，编码、转义、引号等问题在调用层解决。引擎核心逻辑永远不处理字符串转义",
        micro_template="引擎语义层与调用编码层彻底分离",
        logic_score=5.0, outcome_score=5.0, confidence=5.0,
        source="learned", created_at=now, lifecycle_status="active"
    ),
    SuccessPattern(
        id="pat_self_repair_loop_001",
        pattern_name="迭进3次收敛自愈循环",
        trigger_scenario="迭进迭代修复",
        decision_logic="第1次: 发现误触发 → 修复_match_condition异常处理; 第2次: 发现死锁 → 增加安全阀; 第3次: 发现空壳 → 注入真实裁决",
        micro_template="发现问题→不改顶层→修根本→验证→收敛",
        logic_score=5.0, outcome_score=5.0, confidence=5.0,
        source="learned", created_at=now, lifecycle_status="active"
    ),
]

for p in new_patterns:
    existing = engine.get_pattern_by_id(p.id)
    if existing:
        engine.update_pattern(p.id, confidence=p.confidence)
    else:
        engine.add_pattern(p)

print(f"Patterns added/updated: {len(new_patterns)}")
print(f"Total patterns now: {len(engine.get_patterns())}")