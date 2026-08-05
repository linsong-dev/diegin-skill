# DGEN 规则文档（规则库索引）

> 生成时间：2026-08-05 16:16:11
> 生成方式：扫描引擎规则库自动生成（读取 `engine/evo/rules/interception_rules.json`）
> 权威源：`engine/evo/rules/interception_rules.json`（运行时同步 Mindol 语义记忆）。
> 本文件是规则库的可读索引/文档，供人工审阅与 SKILL 引用；规则的增删改以引擎维护流程（`run_maintenance` / 各原则模块）为准，不要直接编辑本文件。

## 总览

| 生命周期 | 数量 |
|:---|:---|
| staging | 6 |
| deprecating | 7 |
| critical | 2 |
| blocking | 3 |
| alerting | 7 |
| active | 31 |
| archived | 204 |
| **合计** | **260** |

## §规则（生效规则明细）

### critical（2 条）

| 规则ID | 严重度 | 触发条件 | 动作 | 置信度 | 触发 |
|:---|:---|:---|:---|:---:|:---:|
| `self_error_encoding_write_corruption` | high | `error_type=='encoding_write_corruption'` | self_check_and_avoid | 4.5 | 0 |
| `self_error_test_error` | high | `error_type=='test_error'` | self_check_and_avoid | 4.5 | 0 |

### blocking（3 条）

| 规则ID | 严重度 | 触发条件 | 动作 | 置信度 | 触发 |
|:---|:---|:---|:---|:---:|:---:|
| `self_error_hooks_ps1_bom` | high | `error_type=='hooks_ps1_bom'` | self_check_and_avoid | 5.0 | 2 |
| `self_error_protocol_b_marker` | high | `error_type=='protocol_b_marker'` | self_check_and_avoid | 4.5 | 0 |
| `self_error_verify_test_b2ad68eb` | high | `error_type=='verify_test_b2ad68eb'` | self_check_and_avoid | 4.5 | 0 |

### active（31 条）

| 规则ID | 严重度 | 触发条件 | 动作 | 置信度 | 触发 |
|:---|:---|:---|:---|:---:|:---:|
| `pat_rule_pat_ps_stdin_bom_flow` | medium | `'stdin' in context and 'json' in context` | suggest_from_pattern; 先验字节再解码：sys.stdin.buffer.read() 检查 b'\… | 5.0 | 18 |
| `rule_check_before_conclude` | medium | `'mismatch' in context or 'inconsistency' in context or 'conf…` | audit_only; cross_validate_multi_source_before_conclusion | 3.8 | 24 |
| `rule_clean_verify_layered` | high | `task_type == 'clean' or task_type == 'remove' or task_type =…` | block; enforce_3_layer_verify | 5 | 22 |
| `rule_config_hash_sync` | critical | `(('config.toml' in command or 'hooks.json' in command or 'tr…` | block; enforce_hash_sync_before_restart | 5.0 | 13 |
| `rule_deploy_ps1_avoid_set_content` | critical | `'Set-Content' in command or 'set-content' in command` | block; use_writealltext_not_set_content_nonewline | 5.0 | 224 |
| `rule_dgen_marker_every_reply` | low | `task_type == 'user_prompt'` | audit_only; inject_display_line | 5.0 | 47 |
| `rule_dual_defense_state_relay` | critical | `'dgen_last_reply' in context or 'dgen_override' in context o…` | state_relay_between_hooks; write_state_in_reply_read_in_tool | 5.0 | 99 |
| `rule_encoding_no_bom_utf8` | critical | `task_type == 'user_prompt' and ('encoding' in text or '编码' i…` | block_execution; require_utf8_nobom | 5.0 | 3 |
| `rule_encoding_pre_check` | high | `'-Encoding' in command or '-encoding' in command` | block; specify_utf8_or_detect_bom | 4.3 | 661 |
| `rule_engine_bareword_guard` | medium | `'trigger_condition' in context or 'rule_engine' in context` | audit_only; verify_field_exists_in_context | 4.5 | 147 |
| `rule_engine_ops_contains_fix` | medium | `'rule_engine' in context or 'trigger_condition' in context` | audit_only; use_dot_contains_instead_of_bare_contains | 5.0 | 147 |
| `rule_fix_scan_same_class` | low | `'bom' in context and '修复' in context` | suggest; 修复一处 BOM/编码类漏洞后必须全库扫描同类 stdin/管道读取模式（本次 1 处发现 7 处同类… | 4.5 | 0 |
| `rule_hook_prepend_log` | medium | `'audit_log' in context or 'diegin_audit' in context or 'log'…` | use_prepend_write; not_append | 4.0 | 263 |
| `rule_json_escape_check` | critical | `('hooks.json' in command and ('Set-Content' in command or 's…` | check_escape_before_write; use_json_dumps | 5.0 | 11 |
| `rule_json_no_bom` | critical | `'json' in command and ('Set-Content' in command or 'set-cont…` | block; require_bom_free_json_output | 5.0 | 104 |
| `rule_marker_tool_block` | low | `task_type == 'pre_tool'` | audit_only; record_tool_marker_audit | 5.0 | 1613 |
| `rule_powershell_set_content_bom` | critical | `'Set-Content' in command or 'set-content' in command` | block; use [System.IO.File]::WriteAllText() instead of Set-C… | 5.0 | 224 |
| `rule_pre_deploy_encoding_audit` | critical | `'deploy' in command or 'sync' in command or 'push' in comman…` | block; require_encoding_scan_before_deploy | 4.8 | 82 |
| `rule_protect_diegin_engine_rules` | critical | `(('engine\\evo\\rules\\' in command or 'engine\\evo\\rule_en…` | block_execution; notify_protected_file | 5.0 | 215 |
| `rule_protect_diegin_hook_scripts` | critical | `(('diegin_pre_tool.ps1' in command or 'diegin_post_tool.ps1'…` | block_execution; notify_protected_file | 5.0 | 100 |
| `rule_protect_diegin_hooks_json` | critical | `('hooks.json' in command and ('Set-Content' in command or 's…` | block_execution; notify_protected_file | 5.0 | 7 |
| `rule_ps_stdin_bom_guard` | medium | `'stdin' in context and 'json' in context` | suggest; Python 从 PS 管道读 stdin JSON 前必须字节级去 BOM: b=b[3:] if … | 5.0 | 18 |
| `rule_reply_hook_retro_first` | medium | `'reply' in context and 'rule' in context` | retrospect_key_rules_before_reply | 3.5 | 8 |
| `rule_seed_idempotent` | medium | `'seed' in context and 'init' in context` | suggest; seed/初始化命令必须幂等：目标文件已存在时跳过或提示，禁止无条件覆盖已有数据 | 4.2 | 0 |
| `rule_session_image_protection` | medium | `tool_name == 'view_image'` | suggest; 当前模型 deepseek-v4-flash 不支持图片输入，view_image 会把 image_… | 5.0 | 0 |
| `rule_state_expire_60s` | medium | `'state_file' in context or 'dgen_last_reply' in context or '…` | check_timestamp_before_relay; expire_after_60s | 3.8 | 8 |
| `rule_test_no_pollution` | medium | `'测试' in context and 'strikes' in context` | suggest; 测试不得污染生产状态文件(strikes_db/evidence_trail)，测试前后必须清理或隔离 | 4.0 | 0 |
| `rule_windows_bom_audit` | high | `('bom' in command or 'BOM' in command or 'encoding' in comma…` | block; check_first_3_bytes_for_bom_before_deploy | 4.3 | 576 |
| `shousan_review_command_failure_20260805_145423` | high | `op == cmd AND NOT cmd_prechecked` | dry_run_before_exec; verify_exit_code | 4.0 | 0 |
| `shousan_review_hooks_ps1_bom_20260805_124836` | high | `op_contains(hooks_ps1_bom) AND NOT prechecked` | pre_check_before_hooks_ps1_bom; verify_result | 4.0 | 0 |
| `shousan_review_tool_error_Bash_20260805_145424` | high | `op_contains(tool_error_Bash) AND NOT prechecked` | pre_check_before_tool_error_Bash; verify_result | 4.0 | 0 |

### alerting（7 条）

| 规则ID | 严重度 | 触发条件 | 动作 | 置信度 | 触发 |
|:---|:---|:---|:---|:---:|:---:|
| `self_error_atomic_tmp_residue` | high | `error_type=='atomic_tmp_residue'` | self_check_and_avoid | 4.5 | 0 |
| `self_error_command_failure` | medium | `error_type=='command_failure'` | self_check_and_avoid | 4.0 | 3 |
| `self_error_image_url` | high | `error_type=='image_url'` | self_check_and_avoid | 4.0 | 0 |
| `self_error_stdin_bom_guard` | high | `error_type=='stdin_bom_guard'` | self_check_and_avoid | 5.0 | 0 |
| `self_error_test_cmd_fail` | high | `error_type=='test_cmd_fail'` | self_check_and_avoid | 4.0 | 0 |
| `self_error_tool_error_Bash` | high | `error_type=='tool_error_Bash'` | self_check_and_avoid | 4.0 | 1 |
| `self_error_unknown` | high | `error_type=='unknown'` | self_check_and_avoid | 4.0 | 0 |

### deprecating（7 条）

| 规则ID | 严重度 | 触发条件 | 动作 | 置信度 | 触发 |
|:---|:---|:---|:---|:---:|:---:|
| `rule_decorative_marker_001` | high | `matched_interceptions > 0 AND 'reply_unaffected' in context` | block_normal_reply; enforce_arbitration_table | 5.0 | 0 |
| `rule_empty_context_001` | low | `diegin_context == {} OR diegin_task_type == ''` | mark_not_applicable; do_not_block | 4.5 | 0 |
| `rule_gateway_client_coverage_001` | medium | `message_source == 'gateway_client' AND not message.content.s…` | inject_marker; escalate_if_persistent | 4.3 | 0 |
| `rule_iron_wall_loop_001` | high | `diegin_consecutive_blocks >= 3` | escalate; notify_user_engine_check | 4.8 | 0 |
| `rule_marker_001` | low | `task_type == 'user_prompt'` | audit_only; check_marker_in_display | 5.0 | 0 |
| `rule_no_binary_hack_001` | high | `task_type == 'binary_modify' AND target == 'app.asar'` | block_execution; suggest_plugin_alternative | 5.0 | 0 |
| `rule_subagent_marker_001` | medium | `task_type == 'subagent' and 'diegin' not in context` | block_reply; inject_diegin_task | 4.5 | 0 |

### archived（204 条）

已归档规则保留 Mindol 语义记忆，退出表达式匹配。归档明细见规则库 JSON。

## §附录（staging 待校验队列）

staging 规则由 `audit_staging` / `run_maintenance` 校验队列消化：触发≥2 转 active（回归校验通过）；超 14 天未触发或源模式已归档 → 归档。

| 规则ID | 置信度 | 创建时间 | 触发 |
|:---|:---:|:---|:---:|
| `pat_rule_gongqi_fix_hooks_ps1_bom_20260805_124836` | 5.0 | 2026-08-05T12:49:05 | 0 |
| `pat_rule_gongqi_verified_command_failure_20260805_145423` | 5.0 | 2026-08-05T14:55:03 | 0 |
| `pat_rule_gongqi_verified_image_url_20260804_080935` | 5.0 | 2026-08-04T08:10:41 | 0 |
| `pat_rule_gongqi_verified_tool_error_Bash_20260805_145424` | 5.0 | 2026-08-05T14:55:03 | 0 |
| `pat_rule_p1` | 5.0 | 2026-07-30T14:23:22 | 0 |
| `pat_rule_pat_auto_tool_get_goal_1` | 4.1 | 2026-08-01T00:29:12 | 0 |
