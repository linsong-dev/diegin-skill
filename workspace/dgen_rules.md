# DGEN 规则文档（规则库索引）

> 生成时间：2026-08-04 18:06:58
> 生成方式：扫描引擎规则库自动生成（读取 `engine/evo/rules/interception_rules.json`）
> 权威源：`engine/evo/rules/interception_rules.json`（运行时同步 Mindol 语义记忆）。
> 本文件是规则库的可读索引/文档，供人工审阅与 SKILL 引用；规则的增删改以引擎维护流程（`run_maintenance` / 各原则模块）为准，不要直接编辑本文件。

## 总览

| 生命周期 | 数量 |
|:---|:---|
| staging | 26 |
| deprecating | 7 |
| critical | 2 |
| blocking | 2 |
| alerting | 7 |
| active | 29 |
| archived | 180 |
| **合计** | **253** |

## §规则（生效规则明细）

### critical（2 条）

| 规则ID | 严重度 | 触发条件 | 动作 | 置信度 | 触发 |
|:---|:---|:---|:---|:---:|:---:|
| `self_error_encoding_write_corruption` | high | `error_type=='encoding_write_corruption'` | self_check_and_avoid | 4.5 | 0 |
| `self_error_test_error` | high | `error_type=='test_error'` | self_check_and_avoid | 4.5 | 0 |

### blocking（2 条）

| 规则ID | 严重度 | 触发条件 | 动作 | 置信度 | 触发 |
|:---|:---|:---|:---|:---:|:---:|
| `self_error_verify_test_b2ad68eb` | high | `error_type=='verify_test_b2ad68eb'` | self_check_and_avoid | 4.5 | 0 |
| `self_error_protocol_b_marker` | high | `error_type=='protocol_b_marker'` | self_check_and_avoid | 4.5 | 0 |

### active（29 条）

| 规则ID | 严重度 | 触发条件 | 动作 | 置信度 | 触发 |
|:---|:---|:---|:---|:---:|:---:|
| `rule_session_image_protection` | medium | `tool_name == 'view_image'` | suggest; 当前模型 deepseek-v4-flash 不支持图片输入，view_image 会把 image_ | 5.0 | 0 |
| `rule_reply_hook_retro_first` | medium | `'reply' in context and 'rule' in context` | retrospect_key_rules_before_reply | 3.5 | 8 |
| `rule_check_before_conclude` | medium | `'mismatch' in context or 'inconsistency' in context or 'conflict' in context` | audit_only; cross_validate_multi_source_before_conclusion | 3.8 | 17 |
| `rule_dgen_marker_every_reply` | low | `task_type == 'user_prompt'` | audit_only; inject_display_line | 5.0 | 25 |
| `rule_dual_defense_state_relay` | critical | `'dgen_last_reply' in context or 'dgen_override' in context or 'phase_state' in c` | state_relay_between_hooks; write_state_in_reply_read_in_tool | 5.0 | 26 |
| `rule_hook_prepend_log` | medium | `'audit_log' in context or 'diegin_audit' in context or 'log' in context` | use_prepend_write; not_append | 4.0 | 178 |
| `rule_engine_bareword_guard` | medium | `'trigger_condition' in context or 'rule_engine' in context` | audit_only; verify_field_exists_in_context | 4.5 | 87 |
| `rule_engine_ops_contains_fix` | medium | `'rule_engine' in context or 'trigger_condition' in context` | audit_only; use_dot_contains_instead_of_bare_contains | 5.0 | 87 |
| `rule_marker_tool_block` | low | `task_type == 'pre_tool'` | audit_only; record_tool_marker_audit | 5.0 | 1162 |
| `rule_fix_scan_same_class` | low | `'bom' in context and '修复' in context` | suggest; 修复一处 BOM/编码类漏洞后必须全库扫描同类 stdin/管道读取模式（本次 1 处发现 7 处同类 | 4.5 | 0 |
| `rule_test_no_pollution` | medium | `'测试' in context and 'strikes' in context` | suggest; 测试不得污染生产状态文件(strikes_db/evidence_trail)，测试前后必须清理或隔离 | 4.0 | 0 |
| `rule_seed_idempotent` | medium | `'seed' in context and 'init' in context` | suggest; seed/初始化命令必须幂等：目标文件已存在时跳过或提示，禁止无条件覆盖已有数据 | 4.2 | 0 |
| `pat_rule_pat_ps_stdin_bom_flow` | medium | `'stdin' in context and 'json' in context` | suggest_from_pattern; 先验字节再解码：sys.stdin.buffer.read() 检查 b'\ | 5.0 | 16 |
| `rule_windows_bom_audit` | high | `('bom' in command or 'BOM' in command or 'encoding' in command) and ('-Encoding'` | block; check_first_3_bytes_for_bom_before_deploy | 4.3 | 384 |
| `rule_pre_deploy_encoding_audit` | critical | `'deploy' in command or 'sync' in command or 'push' in command` | block; require_encoding_scan_before_deploy | 4.8 | 59 |
| `rule_encoding_pre_check` | high | `'-Encoding' in command or '-encoding' in command` | block; specify_utf8_or_detect_bom | 4.3 | 454 |
| `rule_verification_gate_hard_floor` | critical | `phase == 'stop_verification' OR 'stop_verification' in str(context)` | verify_phase_state; report_if_stalled | 5.0 | 0 |
| `rule_state_expire_60s` | medium | `'state_file' in context or 'dgen_last_reply' in context or 'dgen_override' in co` | check_timestamp_before_relay; expire_after_60s | 3.8 | 8 |
| `rule_clean_verify_layered` | high | `task_type == 'clean' or task_type == 'remove' or task_type == 'purge' or 'Remove` | block; enforce_3_layer_verify | 5.0 | 8 |
| `rule_json_no_bom` | critical | `'json' in command and ('Set-Content' in command or 'set-content' in command)` | block; require_bom_free_json_output | 5.0 | 36 |
| `rule_powershell_set_content_bom` | critical | `'Set-Content' in command or 'set-content' in command` | block; use [System.IO.File]::WriteAllText() instead of Set-C | 5.0 | 84 |
| `rule_deploy_ps1_avoid_set_content` | critical | `'Set-Content' in command or 'set-content' in command` | block; use_writealltext_not_set_content_nonewline | 5.0 | 84 |
| `rule_encoding_no_bom_utf8` | critical | `task_type == 'user_prompt' and ('encoding' in text or '编码' in text or 'bom' in t` | block_execution; require_utf8_nobom | 5.0 | 1 |
| `rule_ps_stdin_bom_guard` | medium | `'stdin' in context and 'json' in context` | suggest; Python 从 PS 管道读 stdin JSON 前必须字节级去 BOM: b=b[3:] if  | 5.0 | 16 |
| `rule_protect_diegin_hook_scripts` | critical | `(('diegin_pre_tool.ps1' in command or 'diegin_post_tool.ps1' in command or 'dieg` | block_execution; notify_protected_file | 5.0 | 53 |
| `rule_protect_diegin_engine_rules` | critical | `(('engine\\evo\\rules\\' in command or 'engine\\evo\\rule_engine' in command or ` | block_execution; notify_protected_file | 5.0 | 129 |
| `rule_protect_diegin_hooks_json` | critical | `('hooks.json' in command and ('Set-Content' in command or 'set-content' in comma` | block_execution; notify_protected_file | 5.0 | 2 |
| `rule_json_escape_check` | critical | `('hooks.json' in command and ('Set-Content' in command or 'set-content' in comma` | check_escape_before_write; use_json_dumps | 5.0 | 7 |
| `rule_config_hash_sync` | critical | `(('config.toml' in command or 'hooks.json' in command or 'trusted_hash' in comma` | block; enforce_hash_sync_before_restart | 5.0 | 7 |

### alerting（7 条）

| 规则ID | 严重度 | 触发条件 | 动作 | 置信度 | 触发 |
|:---|:---|:---|:---|:---:|:---:|
| `self_error_image_url` | high | `error_type=='image_url'` | self_check_and_avoid | 4.0 | 0 |
| `self_error_test_cmd_fail` | high | `error_type=='test_cmd_fail'` | self_check_and_avoid | 4.0 | 0 |
| `self_error_atomic_tmp_residue` | high | `error_type=='atomic_tmp_residue'` | self_check_and_avoid | 4.5 | 0 |
| `self_error_stdin_bom_guard` | high | `error_type=='stdin_bom_guard'` | self_check_and_avoid | 5.0 | 0 |
| `self_error_hooks_ps1_bom` | high | `error_type=='hooks_ps1_bom'` | self_check_and_avoid | 4.5 | 0 |
| `self_error_unknown` | high | `error_type=='unknown'` | self_check_and_avoid | 4.0 | 0 |
| `self_error_command_failure` | medium | `error_type=='command_failure'` | self_check_and_avoid | 4.0 | 3 |

### deprecating（7 条）

| 规则ID | 严重度 | 触发条件 | 动作 | 置信度 | 触发 |
|:---|:---|:---|:---|:---:|:---:|
| `rule_empty_context_001` | low | `diegin_context == {} OR diegin_task_type == ''` | mark_not_applicable; do_not_block | 4.5 | 0 |
| `rule_gateway_client_coverage_001` | medium | `message_source == 'gateway_client' AND not message.content.startswith('[DGEN')` | inject_marker; escalate_if_persistent | 4.3 | 0 |
| `rule_iron_wall_loop_001` | high | `diegin_consecutive_blocks >= 3` | escalate; notify_user_engine_check | 4.8 | 0 |
| `rule_no_binary_hack_001` | high | `task_type == 'binary_modify' AND target == 'app.asar'` | block_execution; suggest_plugin_alternative | 5.0 | 0 |
| `rule_subagent_marker_001` | medium | `task_type == 'subagent' and 'diegin' not in context` | block_reply; inject_diegin_task | 4.5 | 0 |
| `rule_marker_001` | low | `task_type == 'user_prompt'` | audit_only; check_marker_in_display | 5.0 | 0 |
| `rule_decorative_marker_001` | high | `matched_interceptions > 0 AND 'reply_unaffected' in context` | block_normal_reply; enforce_arbitration_table | 5.0 | 0 |

### archived（180 条）

已归档规则保留 Mindol 语义记忆，退出表达式匹配。归档明细见规则库 JSON。

## §附录（staging 待校验队列）

staging 规则全部为 0 触发（hold 状态），由 `run_maintenance` 的 staging 校验队列按 TTL（`staging_max_age_days=14`）自动消化。

| 规则ID | 置信度 | 创建时间 | 触发 |
|:---|:---:|:---|:---:|
| `pat_rule_pat_auto_tool_mcp__node_repl__js_1` | 5.0 | 2026-07-23T17:07:47.563179 | 0 |
| `pat_rule_pat_auto_tool_codex_appload_workspace_dependencies_1` | 3.8 | 2026-07-23T17:07:47.571681 | 0 |
| `pat_rule_pat_auto_tool_codex_applist_threads_1` | 5.0 | 2026-07-30T14:23:22.363764 | 0 |
| `pat_rule_pat_auto_tool_codex_appread_thread_1` | 5.0 | 2026-07-30T14:23:22.382674 | 0 |
| `pat_rule_pat_auto_tool_view_image_1` | 4.1 | 2026-07-30T14:23:22.387692 | 0 |
| `pat_rule_pat_auto_tool_codex_appsend_message_to_thread_1` | 5.0 | 2026-07-30T14:23:22.397599 | 0 |
| `pat_rule_pat_auto_tool_codex_applist_projects_1` | 3.8 | 2026-07-30T14:23:22.402632 | 0 |
| `pat_rule_pat_auto_tool_collaborationspawn_agent_1` | 3.8 | 2026-07-30T14:23:22.409794 | 0 |
| `pat_rule_pat_auto_tool_collaborationwait_agent_1` | 4.1 | 2026-07-30T14:23:22.417809 | 0 |
| `pat_rule_pat_auto_tool_collaborationlist_agents_1` | 3.8 | 2026-07-30T14:23:22.424818 | 0 |
| `pat_rule_pat_auto_tool_collaborationfollowup_task_1` | 3.8 | 2026-07-30T14:23:22.431890 | 0 |
| `pat_rule_pat_auto_tool_collaborationinterrupt_agent_1` | 3.8 | 2026-07-30T14:23:22.438180 | 0 |
| `pat_rule_pat_auto_tool_apply_patch_1` | 5.0 | 2026-07-30T14:23:22.443470 | 0 |
| `pat_rule_pat_auto_tool_test_1` | 4.1 | 2026-07-30T14:23:22.452954 | 0 |
| `pat_rule_pat_auto_tool_git_push_1` | 3.8 | 2026-07-30T14:23:22.456576 | 0 |
| `pat_rule_pat_auto_tool_deploy_1` | 3.8 | 2026-07-30T14:23:22.462989 | 0 |
| `pat_rule_pat_auto_tool_file_write_1` | 3.8 | 2026-07-30T14:23:22.468300 | 0 |
| `pat_rule_p1` | 5.0 | 2026-07-30T14:23:22.473319 | 0 |
| `pat_rule_pat_auto_tool_mcp__node_repl__js_reset_1` | 3.8 | 2026-07-30T14:23:22.478658 | 0 |
| `pat_rule_pat_auto_tool_list_mcp_resources_1` | 3.8 | 2026-07-31T11:50:04.124652 | 0 |
| `pat_rule_pat_auto_tool_create_goal_1` | 3.8 | 2026-07-31T12:11:35.918094 | 0 |
| `pat_rule_pat_auto_tool_update_goal_1` | 3.8 | 2026-07-31T14:23:10.246478 | 0 |
| `pat_rule_pat_auto_tool_get_goal_1` | 4.1 | 2026-08-01T00:29:12.797365 | 0 |
| `pat_rule_pat_auto_tool_TestTool_1` | 4.1 | 2026-08-01T18:38:59.730484 | 0 |
| `pat_rule_pat_auto_tool_unknown_1` | 4.1 | 2026-08-03T11:38:47.307059 | 0 |
| `pat_rule_gongqi_verified_image_url_20260804_080935` | 5.0 | 2026-08-04T08:10:41.050568 | 0 |
