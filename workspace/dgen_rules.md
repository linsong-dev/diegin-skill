# DGEN 规则文档（规则库索引）

> 生成时间：2026-08-06 08:50:28
> 生成方式：扫描引擎规则库自动生成（读取 `engine/evo/rules/interception_rules.json`）
> 权威源：`engine/evo/rules/interception_rules.json`（运行时同步 Mindol 语义记忆）。
> 本文件是规则库的可读索引/文档，供人工审阅与 SKILL 引用；规则的增删改以引擎维护流程（`run_maintenance` / 各原则模块）为准，不要直接编辑本文件。

## 总览

| 生命周期 | 数量 |
|:---|:---|
| critical | 2 |
| blocking | 3 |
| alerting | 7 |
| active | 33 |
| staging | 6 |
| deprecating | 7 |
| archived | 206 |
| **合计** | **264** |

## §规则（critical 2 条）

| 规则ID | 严重度 | 触发条件 | 动作 | 置信度 | 触发 |
|:---|:---|:---|:---|:---|:---|
| `self_error_encoding_write_corruption` | high | `error_type=='encoding_write_corruption'` | `self_check_and_avoid` | 4.5 | 0 |
| `self_error_test_error` | high | `error_type=='test_error'` | `self_check_and_avoid` | 4.5 | 0 |

## §规则（blocking 3 条）

| 规则ID | 严重度 | 触发条件 | 动作 | 置信度 | 触发 |
|:---|:---|:---|:---|:---|:---|
| `self_error_hooks_ps1_bom` | high | `error_type=='hooks_ps1_bom'` | `self_check_and_avoid` | 5.0 | 2 |
| `self_error_protocol_b_marker` | high | `error_type=='protocol_b_marker'` | `self_check_and_avoid` | 4.5 | 0 |
| `self_error_verify_test_b2ad68eb` | high | `error_type=='verify_test_b2ad68eb'` | `self_check_and_avoid` | 4.5 | 0 |

## §规则（alerting 7 条）

| 规则ID | 严重度 | 触发条件 | 动作 | 置信度 | 触发 |
|:---|:---|:---|:---|:---|:---|
| `self_error_atomic_tmp_residue` | high | `error_type=='atomic_tmp_residue'` | `self_check_and_avoid` | 4.5 | 0 |
| `self_error_command_failure` | medium | `error_type=='command_failure'` | `self_check_and_avoid` | 0.0 | 3 |
| `self_error_image_url` | high | `error_type=='image_url'` | `self_check_and_avoid` | 4.0 | 0 |
| `self_error_stdin_bom_guard` | high | `error_type=='stdin_bom_guard'` | `self_check_and_avoid` | 5.0 | 0 |
| `self_error_test_cmd_fail` | high | `error_type=='test_cmd_fail'` | `self_check_and_avoid` | 4.0 | 0 |
| `self_error_tool_error_Bash` | high | `error_type=='tool_error_Bash'` | `self_check_and_avoid` | 0.0 | 3 |
| `self_error_unknown` | high | `error_type=='unknown'` | `self_check_and_avoid` | 4.0 | 0 |

## §规则（active 33 条）

| 规则ID | 严重度 | 触发条件 | 动作 | 置信度 | 触发 |
|:---|:---|:---|:---|:---|:---|
| `pat_rule_pat_ps_stdin_bom_flow` | medium | `'stdin' in context and 'json' in context` | `suggest_from_pattern; 先验字节再解码：sys.stdin.buffer.rea` | 5.0 | 19 |
| `rule_check_before_conclude` | medium | `'mismatch' in context or 'inconsistency' in context or 'conf` | `audit_only; cross_validate_multi_source_before_con` | 3.8 | 34 |
| `rule_clean_verify_layered` | high | `task_type == 'clean' or task_type == 'remove' or task_type =` | `block; enforce_3_layer_verify` | 5.0 | 22 |
| `rule_config_hash_sync` | critical | `(('config.toml' in command or 'hooks.json' in command or 'tr` | `block; enforce_hash_sync_before_restart` | 5.0 | 13 |
| `rule_deploy_ps1_avoid_set_content` | critical | `'Set-Content' in command or 'set-content' in command` | `block; use_writealltext_not_set_content_nonewline` | 5.0 | 224 |
| `rule_dgen_marker_every_reply` | low | `task_type == 'user_prompt'` | `audit_only; inject_display_line` | 5.0 | 132 |
| `rule_dual_defense_state_relay` | critical | `'dgen_last_reply' in context or 'dgen_override' in context o` | `state_relay_between_hooks; write_state_in_reply_re` | 5.0 | 153 |
| `rule_encoding_no_bom_utf8` | critical | `task_type == 'user_prompt' and ('encoding' in text or '编码' i` | `block_execution; require_utf8_nobom` | 5.0 | 4 |
| `rule_encoding_pre_check` | high | `'-Encoding' in command or '-encoding' in command` | `block; specify_utf8_or_detect_bom` | 4.3 | 867 |
| `rule_engine_bareword_guard` | medium | `'trigger_condition' in context or 'rule_engine' in context` | `audit_only; verify_field_exists_in_context` | 4.5 | 247 |
| `rule_engine_ops_contains_fix` | medium | `'rule_engine' in context or 'trigger_condition' in context` | `audit_only; use_dot_contains_instead_of_bare_conta` | 5.0 | 247 |
| `rule_fix_scan_same_class` | low | `'bom' in context and '修复' in context` | `suggest; 修复一处 BOM/编码类漏洞后必须全库扫描同类 stdin/管道读取模式（本次 1` | 4.5 | 1 |
| `rule_hook_prepend_log` | medium | `'audit_log' in context or 'diegin_audit' in context or 'log'` | `use_prepend_write; not_append` | 4.0 | 292 |
| `rule_json_escape_check` | critical | `('hooks.json' in command and ('Set-Content' in command or 's` | `check_escape_before_write; use_json_dumps` | 5.0 | 11 |
| `rule_json_no_bom` | critical | `'json' in command and ('Set-Content' in command or 'set-cont` | `block; require_bom_free_json_output` | 5.0 | 104 |
| `rule_marker_tool_block` | low | `task_type == 'pre_tool'` | `audit_only; record_tool_marker_audit` | 5.0 | 2041 |
| `rule_powershell_set_content_bom` | critical | `'Set-Content' in command or 'set-content' in command` | `block; use [System.IO.File]::WriteAllText() instea` | 5.0 | 224 |
| `rule_pre_deploy_encoding_audit` | critical | `'deploy' in command or 'sync' in command or 'push' in comman` | `block; require_encoding_scan_before_deploy` | 4.8 | 107 |
| `rule_protect_diegin_engine_rules` | critical | `(('engine\\evo\\rules\\' in command or 'engine\\evo\\rule_en` | `block_execution; notify_protected_file` | 5.0 | 257 |
| `rule_protect_diegin_hook_scripts` | critical | `(('diegin_pre_tool.ps1' in command or 'diegin_post_tool.ps1'` | `block_execution; notify_protected_file` | 5.0 | 101 |
| `rule_protect_diegin_hooks_json` | critical | `('hooks.json' in command and ('Set-Content' in command or 's` | `block_execution; notify_protected_file` | 5.0 | 7 |
| `rule_ps_stdin_bom_guard` | medium | `'stdin' in context and 'json' in context` | `suggest; Python 从 PS 管道读 stdin JSON 前必须字节级去 BOM: b` | 5.0 | 19 |
| `rule_reply_hook_retro_first` | medium | `'reply' in context and 'rule' in context` | `retrospect_key_rules_before_reply` | 3.5 | 8 |
| `rule_seed_idempotent` | medium | `'seed' in context and 'init' in context` | `suggest; seed/初始化命令必须幂等：目标文件已存在时跳过或提示，禁止无条件覆盖已有数据` | 4.2 | 0 |
| `rule_session_image_protection` | medium | `tool_name == 'view_image'` | `suggest; 当前模型 deepseek-v4-flash 不支持图片输入，view_image` | 5.0 | 0 |
| `rule_state_expire_60s` | medium | `'state_file' in context or 'dgen_last_reply' in context or '` | `check_timestamp_before_relay; expire_after_60s` | 3.8 | 9 |
| `rule_test_no_pollution` | medium | `'测试' in context and 'strikes' in context` | `suggest; 测试不得污染生产状态文件(strikes_db/evidence_trail)，测` | 4.0 | 0 |
| `rule_windows_bom_audit` | high | `('bom' in command or 'BOM' in command or 'encoding' in comma` | `block; check_first_3_bytes_for_bom_before_deploy` | 4.3 | 617 |
| `shousan_review_command_failure_20260805_145423` | high | `op == cmd AND NOT cmd_prechecked` | `dry_run_before_exec; verify_exit_code` | 4.0 | 0 |
| `shousan_review_command_failure_20260805_165257` | high | `op == cmd AND NOT cmd_prechecked` | `dry_run_before_exec; verify_exit_code` | 4.0 | 0 |
| `shousan_review_hooks_ps1_bom_20260805_124836` | high | `op_contains(hooks_ps1_bom) AND NOT prechecked` | `pre_check_before_hooks_ps1_bom; verify_result` | 4.0 | 0 |
| `shousan_review_tool_error_Bash_20260805_145424` | high | `op_contains(tool_error_Bash) AND NOT prechecked` | `pre_check_before_tool_error_Bash; verify_result` | 4.0 | 2 |
| `shousan_review_tool_error_Bash_20260805_165258` | high | `op_contains(tool_error_Bash) AND NOT prechecked` | `pre_check_before_tool_error_Bash; verify_result` | 4.0 | 2 |

## §规则（staging 6 条）

| 规则ID | 严重度 | 触发条件 | 动作 | 置信度 | 触发 |
|:---|:---|:---|:---|:---|:---|
| `pat_rule_gongqi_fix_command_failure_20260805_165257` | medium | `op_contains(command_failure)` | `suggest_from_pattern; 执行命令前先dry-run或验证参数正确性` | 5.0 | 1 |
| `pat_rule_gongqi_fix_hooks_ps1_bom_20260805_124836` | medium | `op_contains(hooks_ps1_bom)` | `suggest_from_pattern; hooks_ps1_bom操作前预检，避免同类错误` | 5.0 | 0 |
| `pat_rule_gongqi_fix_tool_error_Bash_20260805_165258` | medium | `op_contains(tool_error_Bash)` | `suggest_from_pattern; tool_error_Bash操作前预检，避免同类错误` | 5.0 | 1 |
| `pat_rule_gongqi_verified_command_failure_20260805_145423` | medium | `op_contains(command_failure)` | `suggest_from_pattern; 执行命令前先dry-run或验证参数正确性` | 5.0 | 1 |
| `pat_rule_gongqi_verified_image_url_20260804_080935` | medium | `op_contains(image_url)` | `suggest_from_pattern; image_url操作已修复并验证通过，固化该路径` | 5.0 | 0 |
| `pat_rule_gongqi_verified_tool_error_Bash_20260805_145424` | medium | `op_contains(tool_error_Bash)` | `suggest_from_pattern; tool_error_Bash操作已修复并验证通过，固化` | 5.0 | 2 |

## §规则（deprecating 7 条）

| 规则ID | 严重度 | 触发条件 | 动作 | 置信度 | 触发 |
|:---|:---|:---|:---|:---|:---|
| `rule_decorative_marker_001` | high | `matched_interceptions > 0 AND 'reply_unaffected' in context` | `block_normal_reply; enforce_arbitration_table` | 5.0 | 0 |
| `rule_empty_context_001` | low | `diegin_context == {} OR diegin_task_type == ''` | `mark_not_applicable; do_not_block` | 4.5 | 0 |
| `rule_gateway_client_coverage_001` | medium | `message_source == 'gateway_client' AND not message.content.s` | `inject_marker; escalate_if_persistent` | 4.3 | 0 |
| `rule_iron_wall_loop_001` | high | `diegin_consecutive_blocks >= 3` | `escalate; notify_user_engine_check` | 4.8 | 0 |
| `rule_marker_001` | low | `task_type == 'user_prompt'` | `audit_only; check_marker_in_display` | 5.0 | 0 |
| `rule_no_binary_hack_001` | high | `task_type == 'binary_modify' AND target == 'app.asar'` | `block_execution; suggest_plugin_alternative` | 5.0 | 0 |
| `rule_subagent_marker_001` | medium | `task_type == 'subagent' and 'diegin' not in context` | `block_reply; inject_diegin_task` | 4.5 | 0 |

## §规则（archived 206 条）

| 规则ID | 严重度 | 触发条件 | 动作 | 置信度 | 触发 |
|:---|:---|:---|:---|:---|:---|
| `attack_complex_python_001` | medium | `(op == 'json_merge' OR op == 'data_transform' OR op == 'batc` | `suggest_python; prefer_python_over_shell_js_for_co` | 4.0 | 0 |
| `attack_js_tool_best_004` | low | `(tool == 'node_repl' OR tool == 'js') AND (op == 'browser' O` | `suggest_js; prefer_js_for_browser_npm_perf_compute` | 3.2 | 0 |
| `attack_python_scenario_002` | low | `op == 'regex_replace' OR op == 'encoding_detect' OR op == 'r` | `suggest_python; python_first_for_encoding_regex_re` | 3.8 | 0 |
| `attack_shell_best_003` | low | `op == 'file_read' OR op == 'grep' OR op == 'ls' OR op == 'gi` | `suggest_shell; keep_shell_for_simple_file_git_ops;` | 4.2 | 0 |
| `attack_tco_first_005` | medium | `op == 'tool_select' OR complexity == 'high' OR complexity ==` | `suggest_tco; prefer_total_cost_over_first_try_spee` | 4.2 | 0 |
| `gen_rule_empty_context_0_marker_coverage_1337277104` | critical | `marker_coverage_related_issue` | `check_and_auto_resolve` | 3.0 | 0 |
| `pat_rule_p1` | medium | `qa` | `suggest_from_pattern; ` | 5.0 | 0 |
| `pat_rule_pat_auto_tool_Bash_1` | medium | `tool_Bash` | `suggest_from_pattern; ` | 5.0 | 2 |
| `pat_rule_pat_auto_tool_TestTool_1` | medium | `tool_name == 'TestTool'` | `suggest_from_pattern; python -c 'print(1)' --verif` | 4.1 | 0 |
| `pat_rule_pat_auto_tool_apply_patch_1` | medium | `tool_apply_patch` | `suggest_from_pattern; ` | 5.0 | 0 |
| `pat_rule_pat_auto_tool_codex_applist_projects_1` | low | `tool_codex_applist_projects` | `suggest_from_pattern; ` | 3.8 | 0 |
| `pat_rule_pat_auto_tool_codex_applist_threads_1` | medium | `tool_codex_applist_threads` | `suggest_from_pattern; ` | 5.0 | 0 |
| `pat_rule_pat_auto_tool_codex_appload_workspace_dependencies_1` | low | `tool_codex_appload_workspace_dependencies` | `suggest_from_pattern; ` | 3.8 | 0 |
| `pat_rule_pat_auto_tool_codex_appread_thread_1` | medium | `tool_codex_appread_thread` | `suggest_from_pattern; ` | 5.0 | 0 |
| `pat_rule_pat_auto_tool_codex_appsend_message_to_thread_1` | medium | `tool_codex_appsend_message_to_thread` | `suggest_from_pattern; ` | 5.0 | 0 |
| `pat_rule_pat_auto_tool_collaborationfollowup_task_1` | low | `tool_collaborationfollowup_task` | `suggest_from_pattern; ` | 3.8 | 0 |
| `pat_rule_pat_auto_tool_collaborationinterrupt_agent_1` | low | `tool_collaborationinterrupt_agent` | `suggest_from_pattern; ` | 3.8 | 0 |
| `pat_rule_pat_auto_tool_collaborationlist_agents_1` | low | `tool_collaborationlist_agents` | `suggest_from_pattern; ` | 3.8 | 0 |
| `pat_rule_pat_auto_tool_collaborationspawn_agent_1` | low | `tool_collaborationspawn_agent` | `suggest_from_pattern; ` | 3.8 | 0 |
| `pat_rule_pat_auto_tool_collaborationwait_agent_1` | medium | `tool_collaborationwait_agent` | `suggest_from_pattern; ` | 4.1 | 0 |
| `pat_rule_pat_auto_tool_create_goal_1` | low | `tool_create_goal` | `suggest_from_pattern; ` | 3.8 | 0 |
| `pat_rule_pat_auto_tool_deploy_1` | low | `tool_deploy` | `suggest_from_pattern; ` | 3.8 | 0 |
| `pat_rule_pat_auto_tool_file_write_1` | low | `tool_file_write` | `suggest_from_pattern; ` | 3.8 | 0 |
| `pat_rule_pat_auto_tool_get_goal_1` | medium | `tool_get_goal` | `suggest_from_pattern; get_goal` | 4.1 | 0 |
| `pat_rule_pat_auto_tool_git_push_1` | low | `tool_git_push` | `suggest_from_pattern; ` | 3.8 | 0 |
| `pat_rule_pat_auto_tool_list_mcp_resources_1` | low | `tool_list_mcp_resources` | `suggest_from_pattern; ` | 3.8 | 0 |
| `pat_rule_pat_auto_tool_mcp__node_repl__js_1` | medium | `tool_mcp__node_repl__js` | `suggest_from_pattern; ` | 5.0 | 0 |
| `pat_rule_pat_auto_tool_mcp__node_repl__js_reset_1` | low | `tool_mcp__node_repl__js_reset` | `suggest_from_pattern; ` | 3.8 | 0 |
| `pat_rule_pat_auto_tool_test_1` | medium | `tool_test` | `suggest_from_pattern; ` | 4.1 | 0 |
| `pat_rule_pat_auto_tool_unknown_1` | medium | `tool_unknown` | `suggest_from_pattern; unknown` | 4.1 | 0 |
| `pat_rule_pat_auto_tool_update_goal_1` | low | `tool_update_goal` | `suggest_from_pattern; ` | 3.8 | 0 |
| `pat_rule_pat_auto_tool_update_plan_1` | medium | `tool_update_plan` | `suggest_from_pattern; ` | 5.0 | 2 |
| `pat_rule_pat_auto_tool_view_image_1` | medium | `tool_view_image` | `suggest_from_pattern; ` | 4.1 | 0 |
| `pat_rule_wargame_file_write_review_c70e18` | low | `op == file_write AND length > 1000` | `suggest_from_pattern; ` | 3.2 | 0 |
| `pat_rule_wargame_git_commit_workflow_b88fc3` | low | `git commit` | `suggest_from_pattern; ` | 3.4 | 0 |
| `pat_rule_wargame_pip_install_workflow_8f8f21` | low | `pip install` | `suggest_from_pattern; ` | 3.4 | 0 |
| `pat_rule_wargame_test_before_push_acf09c` | low | `git push` | `suggest_from_pattern; ` | 3.5 | 0 |
| `rule_ai_override_state` | critical | `('dgen_override.json' in command or 'overwrite dgen' in comm` | `write_override_block; ai_precheck_before_tool` | 5.0 | 0 |
| `rule_cmd_test_before_run` | high | `command_length > 200 OR pipe_nesting > 2` | `block; print_command_string_for_review` | 4.3 | 0 |
| `rule_delivery_full_audit` | critical | `task_type == 'delivery' or task_type == 'release' or task_ty` | `block; list_every_file_confirm_in_scope` | 5.0 | 0 |
| `rule_deploy_bom_self_check` | critical | `'deploy' in context and 'bom' in context` | `recursive_bom_audit_after_deploy` | 5.0 | 4 |
| `rule_deploy_direction` | critical | `('deploy.ps1' in command or 'deploy diegin' in command or 'd` | `block; enforce_source_to_runtime_direction` | 5.0 | 0 |
| `rule_deploy_git_push` | high | `'git push' in command and ('deploy' in command or '同步' in co` | `push_first_then_deploy; verify_deploy_script_synta` | 4.3 | 0 |
| `rule_deploy_verify_consistency` | critical | `('deploy' in command and 'verify' in command and ('git push'` | `deploy_consistency_check; block_on_mismatch` | 5.0 | 0 |
| `rule_dry_run_before_batch` | high | `batch_file_operation > 3` | `block; print_file_list_and_size; require_whatif` | 4.5 | 0 |
| `rule_extract_full_scope` | high | `task_type == 'extract_or_migrate' AND 'file_list_not_confirm` | `block; enumerate_full_file_set_before_extract` | 4.5 | 0 |
| `rule_hook_engine_parse_json` | critical | `'pre_reply.ps1' in context or 'pre_tool.ps1' in context or '` | `parse_engine_json_decision; not_rely_on_exitcode` | 5.0 | 0 |
| `rule_hook_scripts_location` | high | `('scripts' in context and ('hooks' in context or 'diegin_hoo` | `block; use_hooks_dir_instead_of_scripts` | 4.3 | 0 |
| `rule_modify_source_not_runtime` | critical | `('.codex' in context and 'diegin' in context and ('hooks.jso` | `block; redirect_to_source_directory` | 5.0 | 0 |
| `rule_plugin_ui_display_requirements` | high | `(task_type == 'plugin_deploy' OR task_type == 'plugin_debug'` | `block; check_marketplace_config_and_plugins_array_` | 4.5 | 0 |
| `rule_plugin_vs_local_hooks` | high | `'.codex' in context and 'hooks.json' in context AND task_typ` | `block; check_both_hook_locations` | 4.5 | 0 |
| `rule_powershell_escape_triple_lock` | critical | `shell_type == 'powershell' AND 'command_has_special_chars' i` | `block; check_3_layers_quote_special_stdin` | 5.0 | 0 |
| `rule_quwei_verification_gate` | low | `phase == 'verify' OR verify_dgen == True` | `verify_dgen_marker_in_reply; record_verification_r` | 5.0 | 0 |
| `rule_scope_full_check` | high | `task_type == 'search_or_extract' AND 'scope_not_confirmed' i` | `block; list_all_related_paths_before_proceed` | 4.3 | 0 |
| `rule_tool_selection_fastest` | medium | `multiple_tool_options_available` | `select_by_complexity; prefer_shell_for_simple_ops;` | 3.8 | 0 |
| `rule_toolchain_path_verify` | high | `invoke_external_interpreter` | `block; test_hello_world_or_fallback` | 3.8 | 0 |
| `rule_truth_gate_declaration` | high | `phase == 'truth_gate' OR phase_check == True OR verification` | `enforce_hard_floor; mark_verification_required` | 5.0 | 0 |
| `rule_verification_gate_hard_floor` | critical | `phase == 'stop_verification' OR 'stop_verification' in str(c` | `verify_phase_state; report_if_stalled` | 5.0 | 0 |
| `rule_verify_command_exitcode` | critical | `external_command_completed` | `block_if_empty_output_check_stderr` | 5.0 | 0 |
| `rule_word_meaning_confirm` | high | `user_input_contains_ambiguous_word(strip\|clear\|migrate\|cl` | `escalate; ask_clarification_before_execute` | 4.3 | 0 |
| `seed_file_destructive_002` | high | `op == delete AND recursive == true` | `block_execution; require_explicit_approval` | 5.0 | 0 |
| `seed_network_external_003` | medium | `op == network AND target != localhost` | `permission_check; confirm_before_send` | 5.0 | 0 |
| `wargame_cmd_line_unusual_132fa7` | critical | `op == shell AND ('rm -rf' in cmd OR 'rd /s' in cmd OR 'del /` | `block_execution; require_explicit_approval` | 5.0 | 0 |
| `wargame_data_overwrite_171a86` | medium | `op == file_write AND exists == true` | `confirm_overwrite` | 3.8 | 0 |
| `wargame_destructive_file_op_bdcf0a` | critical | `op in ('delete', 'move', 'rename') AND recursive == true` | `block_execution; require_explicit_approval` | 4.8 | 0 |
| `wargame_env_var_exposure_b7efec` | high | `'env:' in prompt` | `warn_and_confirm` | 4.3 | 0 |
| `wargame_external_network_call_86996d` | medium | `op == network AND target != 'localhost'` | `permission_check; confirm_before_send` | 3.8 | 0 |
| `wargame_file_read_sensitive_a548ee` | high | `op == file_read AND ('.env' in path OR 'secret' in path OR '` | `warn_and_confirm` | 4.3 | 0 |
| `wargame_git_destructive_9820d9` | high | `op == git AND ' --force' in cmd` | `block_execution; require_explicit_approval` | 4.8 | 0 |
| `wargame_large_scale_install_f67d31` | medium | `cmd contains 'install'` | `confirm_and_log` | 3.5 | 0 |
| `wargame_mass_parallel_ops_ef6bb5` | high | `op == shell AND 'for' in cmd AND 'in' in cmd` | `chunk_and_confirm` | 4.0 | 0 |
| `xdomain_code_dev_to_collaboration_domain_code_dry_run_` | low | `domain == 'collaboration'` | `suggest_cross_domain; collaboration: 对多个文件进行批量修改/删` | 3.0 | 0 |
| `xdomain_code_dev_to_collaboration_domain_code_encoding` | low | `domain == 'collaboration'` | `suggest_cross_domain; collaboration: 代码目录下所有新建/写入文` | 3.0 | 0 |
| `xdomain_code_dev_to_collaboration_domain_code_review_c` | low | `domain == 'collaboration'` | `suggest_cross_domain; collaboration: Review 时每处反馈必` | 3.0 | 0 |
| `xdomain_code_dev_to_collaboration_domain_code_syntax_b` | low | `domain == 'collaboration'` | `suggest_cross_domain; collaboration: 任何 git commit` | 3.0 | 0 |
| `xdomain_code_dev_to_collaboration_domain_code_test_bef` | low | `domain == 'collaboration'` | `suggest_cross_domain; collaboration: 部署到生产环境前必须确认测` | 3.0 | 0 |
| `xdomain_code_dev_to_collaboration_domain_code_todo_che` | low | `domain == 'collaboration'` | `suggest_cross_domain; collaboration: git commit 前检` | 3.0 | 0 |
| `xdomain_code_dev_to_data_analysis_domain_code_dry_run_` | low | `domain == 'data_analysis'` | `suggest_cross_domain; data analysis: 对多个文件进行批量修改/删` | 3.0 | 0 |
| `xdomain_code_dev_to_data_analysis_domain_code_encoding` | low | `domain == 'data_analysis'` | `suggest_cross_domain; data analysis: 代码目录下所有新建/写入文` | 3.0 | 0 |
| `xdomain_code_dev_to_data_analysis_domain_code_review_c` | low | `domain == 'data_analysis'` | `suggest_cross_domain; data analysis: Review 时每处反馈必` | 3.0 | 0 |
| `xdomain_code_dev_to_data_analysis_domain_code_syntax_b` | low | `domain == 'data_analysis'` | `suggest_cross_domain; data analysis: 任何 git commit` | 3.0 | 0 |
| `xdomain_code_dev_to_data_analysis_domain_code_test_bef` | low | `domain == 'data_analysis'` | `suggest_cross_domain; data analysis: 部署到生产环境前必须确认测` | 3.0 | 0 |
| `xdomain_code_dev_to_data_analysis_domain_code_todo_che` | low | `domain == 'data_analysis'` | `suggest_cross_domain; data analysis: git commit 前检` | 3.0 | 0 |
| `xdomain_code_dev_to_project_mgmt_domain_code_dry_run_` | low | `domain == 'project_mgmt'` | `suggest_cross_domain; project mgmt: 对多个文件进行批量修改/删除` | 3.0 | 0 |
| `xdomain_code_dev_to_project_mgmt_domain_code_encoding` | low | `domain == 'project_mgmt'` | `suggest_cross_domain; project mgmt: 代码目录下所有新建/写入文件` | 3.0 | 0 |
| `xdomain_code_dev_to_project_mgmt_domain_code_review_c` | low | `domain == 'project_mgmt'` | `suggest_cross_domain; project mgmt: Review 时每处反馈必须` | 3.0 | 0 |
| `xdomain_code_dev_to_project_mgmt_domain_code_syntax_b` | low | `domain == 'project_mgmt'` | `suggest_cross_domain; project mgmt: 任何 git commit ` | 3.0 | 0 |
| `xdomain_code_dev_to_project_mgmt_domain_code_test_bef` | low | `domain == 'project_mgmt'` | `suggest_cross_domain; project mgmt: 部署到生产环境前必须确认测试` | 3.0 | 0 |
| `xdomain_code_dev_to_project_mgmt_domain_code_todo_che` | low | `domain == 'project_mgmt'` | `suggest_cross_domain; project mgmt: git commit 前检查` | 3.0 | 0 |
| `xdomain_code_dev_to_security_audit_domain_code_dry_run_` | low | `domain == 'security_audit'` | `suggest_cross_domain; security audit: 对多个文件进行批量修改/` | 3.0 | 0 |
| `xdomain_code_dev_to_security_audit_domain_code_encoding` | low | `domain == 'security_audit'` | `suggest_cross_domain; security audit: 代码目录下所有新建/写入` | 3.0 | 0 |
| `xdomain_code_dev_to_security_audit_domain_code_review_c` | low | `domain == 'security_audit'` | `suggest_cross_domain; security audit: Review 时每处反馈` | 3.0 | 0 |
| `xdomain_code_dev_to_security_audit_domain_code_syntax_b` | low | `domain == 'security_audit'` | `suggest_cross_domain; security audit: 任何 git commi` | 3.0 | 0 |
| `xdomain_code_dev_to_security_audit_domain_code_test_bef` | low | `domain == 'security_audit'` | `suggest_cross_domain; security audit: 部署到生产环境前必须确认` | 3.0 | 0 |
| `xdomain_code_dev_to_security_audit_domain_code_todo_che` | low | `domain == 'security_audit'` | `suggest_cross_domain; security audit: git commit 前` | 3.0 | 0 |
| `xdomain_code_dev_to_writing_domain_code_dry_run_` | low | `domain == 'writing'` | `suggest_cross_domain; writing: 对多个文件进行批量修改/删除/移动前必` | 3.0 | 0 |
| `xdomain_code_dev_to_writing_domain_code_encoding` | low | `domain == 'writing'` | `suggest_cross_domain; writing: 代码目录下所有新建/写入文件必须用 U` | 3.0 | 0 |
| `xdomain_code_dev_to_writing_domain_code_review_c` | low | `domain == 'writing'` | `suggest_cross_domain; writing: Review 时每处反馈必须有明确的行` | 3.0 | 0 |
| `xdomain_code_dev_to_writing_domain_code_syntax_b` | low | `domain == 'writing'` | `suggest_cross_domain; writing: 任何 git commit 操作前必须` | 3.0 | 0 |
| `xdomain_code_dev_to_writing_domain_code_test_bef` | low | `domain == 'writing'` | `suggest_cross_domain; writing: 部署到生产环境前必须确认测试套件通过` | 3.0 | 0 |
| `xdomain_code_dev_to_writing_domain_code_todo_che` | low | `domain == 'writing'` | `suggest_cross_domain; writing: git commit 前检查代码中是否` | 3.0 | 0 |
| `xdomain_collaboration_to_code_dev_domain_collab_blocke` | low | `domain == 'code_dev'` | `suggest_cross_domain; code dev: 识别到阻塞项时必须在群组或任务系统中` | 3.0 | 0 |
| `xdomain_collaboration_to_code_dev_domain_collab_knowle` | low | `domain == 'code_dev'` | `suggest_cross_domain; code dev: 解决复杂问题后必须记录解决方案到知识` | 3.0 | 0 |
| `xdomain_collaboration_to_code_dev_domain_collab_review` | low | `domain == 'code_dev'` | `suggest_cross_domain; code dev: 代码 Review 请求必须在 72` | 3.0 | 0 |
| `xdomain_collaboration_to_data_analysis_domain_collab_blocke` | low | `domain == 'data_analysis'` | `suggest_cross_domain; data analysis: 识别到阻塞项时必须在群组或` | 3.0 | 0 |
| `xdomain_collaboration_to_data_analysis_domain_collab_knowle` | low | `domain == 'data_analysis'` | `suggest_cross_domain; data analysis: 解决复杂问题后必须记录解决` | 3.0 | 0 |
| `xdomain_collaboration_to_data_analysis_domain_collab_review` | low | `domain == 'data_analysis'` | `suggest_cross_domain; data analysis: 代码 Review 请求必` | 3.0 | 0 |
| `xdomain_collaboration_to_project_mgmt_domain_collab_blocke` | low | `domain == 'project_mgmt'` | `suggest_cross_domain; project mgmt: 识别到阻塞项时必须在群组或任` | 3.0 | 0 |
| `xdomain_collaboration_to_project_mgmt_domain_collab_knowle` | low | `domain == 'project_mgmt'` | `suggest_cross_domain; project mgmt: 解决复杂问题后必须记录解决方` | 3.0 | 0 |
| `xdomain_collaboration_to_project_mgmt_domain_collab_review` | low | `domain == 'project_mgmt'` | `suggest_cross_domain; project mgmt: 代码 Review 请求必须` | 3.0 | 0 |
| `xdomain_collaboration_to_security_audit_domain_collab_blocke` | low | `domain == 'security_audit'` | `suggest_cross_domain; security audit: 识别到阻塞项时必须在群组` | 3.0 | 0 |
| `xdomain_collaboration_to_security_audit_domain_collab_knowle` | low | `domain == 'security_audit'` | `suggest_cross_domain; security audit: 解决复杂问题后必须记录解` | 3.0 | 0 |
| `xdomain_collaboration_to_security_audit_domain_collab_review` | low | `domain == 'security_audit'` | `suggest_cross_domain; security audit: 代码 Review 请求` | 3.0 | 0 |
| `xdomain_collaboration_to_writing_domain_collab_blocke` | low | `domain == 'writing'` | `suggest_cross_domain; writing: 识别到阻塞项时必须在群组或任务系统中通` | 3.0 | 0 |
| `xdomain_collaboration_to_writing_domain_collab_knowle` | low | `domain == 'writing'` | `suggest_cross_domain; writing: 解决复杂问题后必须记录解决方案到知识库` | 3.0 | 0 |
| `xdomain_collaboration_to_writing_domain_collab_review` | low | `domain == 'writing'` | `suggest_cross_domain; writing: 代码 Review 请求必须在 72 ` | 3.0 | 0 |
| `xdomain_data_analysis_to_code_dev_domain_data_calculat` | low | `domain == 'code_dev'` | `suggest_cross_domain; code dev: 任何数值计算必须给出完整公式和中间值` | 3.0 | 0 |
| `xdomain_data_analysis_to_code_dev_domain_data_outlier_` | low | `domain == 'code_dev'` | `suggest_cross_domain; code dev: 分析结果中存在异常值时必须标注说明处` | 3.0 | 0 |
| `xdomain_data_analysis_to_code_dev_domain_data_source_c` | low | `domain == 'code_dev'` | `suggest_cross_domain; code dev: 所有统计数据、图表结论必须标注原始数` | 3.0 | 0 |
| `xdomain_data_analysis_to_code_dev_domain_data_visual_b` | low | `domain == 'code_dev'` | `suggest_cross_domain; code dev: 生成图表时必须同时输出原始数据（CS` | 3.0 | 0 |
| `xdomain_data_analysis_to_collaboration_domain_data_calculat` | low | `domain == 'collaboration'` | `suggest_cross_domain; collaboration: 任何数值计算必须给出完整公` | 3.0 | 0 |
| `xdomain_data_analysis_to_collaboration_domain_data_outlier_` | low | `domain == 'collaboration'` | `suggest_cross_domain; collaboration: 分析结果中存在异常值时必须` | 3.0 | 0 |
| `xdomain_data_analysis_to_collaboration_domain_data_source_c` | low | `domain == 'collaboration'` | `suggest_cross_domain; collaboration: 所有统计数据、图表结论必须` | 3.0 | 0 |
| `xdomain_data_analysis_to_collaboration_domain_data_visual_b` | low | `domain == 'collaboration'` | `suggest_cross_domain; collaboration: 生成图表时必须同时输出原始` | 3.0 | 0 |
| `xdomain_data_analysis_to_project_mgmt_domain_data_calculat` | low | `domain == 'project_mgmt'` | `suggest_cross_domain; project mgmt: 任何数值计算必须给出完整公式` | 3.0 | 0 |
| `xdomain_data_analysis_to_project_mgmt_domain_data_outlier_` | low | `domain == 'project_mgmt'` | `suggest_cross_domain; project mgmt: 分析结果中存在异常值时必须标` | 3.0 | 0 |
| `xdomain_data_analysis_to_project_mgmt_domain_data_source_c` | low | `domain == 'project_mgmt'` | `suggest_cross_domain; project mgmt: 所有统计数据、图表结论必须标` | 3.0 | 0 |
| `xdomain_data_analysis_to_project_mgmt_domain_data_visual_b` | low | `domain == 'project_mgmt'` | `suggest_cross_domain; project mgmt: 生成图表时必须同时输出原始数` | 3.0 | 0 |
| `xdomain_data_analysis_to_security_audit_domain_data_calculat` | low | `domain == 'security_audit'` | `suggest_cross_domain; security audit: 任何数值计算必须给出完整` | 3.0 | 0 |
| `xdomain_data_analysis_to_security_audit_domain_data_outlier_` | low | `domain == 'security_audit'` | `suggest_cross_domain; security audit: 分析结果中存在异常值时必` | 3.0 | 0 |
| `xdomain_data_analysis_to_security_audit_domain_data_source_c` | low | `domain == 'security_audit'` | `suggest_cross_domain; security audit: 所有统计数据、图表结论必` | 3.0 | 0 |
| `xdomain_data_analysis_to_security_audit_domain_data_visual_b` | low | `domain == 'security_audit'` | `suggest_cross_domain; security audit: 生成图表时必须同时输出原` | 3.0 | 0 |
| `xdomain_data_analysis_to_writing_domain_data_calculat` | low | `domain == 'writing'` | `suggest_cross_domain; writing: 任何数值计算必须给出完整公式和中间值，` | 3.0 | 0 |
| `xdomain_data_analysis_to_writing_domain_data_outlier_` | low | `domain == 'writing'` | `suggest_cross_domain; writing: 分析结果中存在异常值时必须标注说明处理` | 3.0 | 0 |
| `xdomain_data_analysis_to_writing_domain_data_source_c` | low | `domain == 'writing'` | `suggest_cross_domain; writing: 所有统计数据、图表结论必须标注原始数据` | 3.0 | 0 |
| `xdomain_data_analysis_to_writing_domain_data_visual_b` | low | `domain == 'writing'` | `suggest_cross_domain; writing: 生成图表时必须同时输出原始数据（CSV` | 3.0 | 0 |
| `xdomain_project_mgmt_to_code_dev_domain_pm_decision_r` | low | `domain == 'code_dev'` | `suggest_cross_domain; code dev: 做出关键决策时必须记录被否决的备选方` | 3.0 | 0 |
| `xdomain_project_mgmt_to_code_dev_domain_pm_delay_esca` | low | `domain == 'code_dev'` | `suggest_cross_domain; code dev: 同一任务连续延期 3 次时自动升级通` | 3.0 | 0 |
| `xdomain_project_mgmt_to_code_dev_domain_pm_scope_chec` | low | `domain == 'code_dev'` | `suggest_cross_domain; code dev: 接新需求前必须先确认范围，避免 sc` | 3.0 | 0 |
| `xdomain_project_mgmt_to_code_dev_domain_pm_status_rea` | low | `domain == 'code_dev'` | `suggest_cross_domain; code dev: 任务状态从进行中→完成/阻塞时必须记` | 3.0 | 0 |
| `xdomain_project_mgmt_to_collaboration_domain_pm_decision_r` | low | `domain == 'collaboration'` | `suggest_cross_domain; collaboration: 做出关键决策时必须记录被否` | 3.0 | 0 |
| `xdomain_project_mgmt_to_collaboration_domain_pm_delay_esca` | low | `domain == 'collaboration'` | `suggest_cross_domain; collaboration: 同一任务连续延期 3 次时` | 3.0 | 0 |
| `xdomain_project_mgmt_to_collaboration_domain_pm_scope_chec` | low | `domain == 'collaboration'` | `suggest_cross_domain; collaboration: 接新需求前必须先确认范围，` | 3.0 | 0 |
| `xdomain_project_mgmt_to_collaboration_domain_pm_status_rea` | low | `domain == 'collaboration'` | `suggest_cross_domain; collaboration: 任务状态从进行中→完成/阻` | 3.0 | 0 |
| `xdomain_project_mgmt_to_data_analysis_domain_pm_decision_r` | low | `domain == 'data_analysis'` | `suggest_cross_domain; data analysis: 做出关键决策时必须记录被否` | 3.0 | 0 |
| `xdomain_project_mgmt_to_data_analysis_domain_pm_delay_esca` | low | `domain == 'data_analysis'` | `suggest_cross_domain; data analysis: 同一任务连续延期 3 次时` | 3.0 | 0 |
| `xdomain_project_mgmt_to_data_analysis_domain_pm_scope_chec` | low | `domain == 'data_analysis'` | `suggest_cross_domain; data analysis: 接新需求前必须先确认范围，` | 3.0 | 0 |
| `xdomain_project_mgmt_to_data_analysis_domain_pm_status_rea` | low | `domain == 'data_analysis'` | `suggest_cross_domain; data analysis: 任务状态从进行中→完成/阻` | 3.0 | 0 |
| `xdomain_project_mgmt_to_security_audit_domain_pm_decision_r` | low | `domain == 'security_audit'` | `suggest_cross_domain; security audit: 做出关键决策时必须记录被` | 3.0 | 0 |
| `xdomain_project_mgmt_to_security_audit_domain_pm_delay_esca` | low | `domain == 'security_audit'` | `suggest_cross_domain; security audit: 同一任务连续延期 3 次` | 3.0 | 0 |
| `xdomain_project_mgmt_to_security_audit_domain_pm_scope_chec` | low | `domain == 'security_audit'` | `suggest_cross_domain; security audit: 接新需求前必须先确认范围` | 3.0 | 0 |
| `xdomain_project_mgmt_to_security_audit_domain_pm_status_rea` | low | `domain == 'security_audit'` | `suggest_cross_domain; security audit: 任务状态从进行中→完成/` | 3.0 | 0 |
| `xdomain_project_mgmt_to_writing_domain_pm_decision_r` | low | `domain == 'writing'` | `suggest_cross_domain; writing: 做出关键决策时必须记录被否决的备选方案` | 3.0 | 0 |
| `xdomain_project_mgmt_to_writing_domain_pm_delay_esca` | low | `domain == 'writing'` | `suggest_cross_domain; writing: 同一任务连续延期 3 次时自动升级通知` | 3.0 | 0 |
| `xdomain_project_mgmt_to_writing_domain_pm_scope_chec` | low | `domain == 'writing'` | `suggest_cross_domain; writing: 接新需求前必须先确认范围，避免 sco` | 3.0 | 0 |
| `xdomain_project_mgmt_to_writing_domain_pm_status_rea` | low | `domain == 'writing'` | `suggest_cross_domain; writing: 任务状态从进行中→完成/阻塞时必须记录` | 3.0 | 0 |
| `xdomain_security_audit_to_code_dev_domain_sec_command_i` | low | `domain == 'code_dev'` | `suggest_cross_domain; code dev: shell 命令中若包含外部输入，必` | 3.0 | 0 |
| `xdomain_security_audit_to_code_dev_domain_sec_env_crede` | low | `domain == 'code_dev'` | `suggest_cross_domain; code dev: 读取环境变量中的凭据后不得明文输出到` | 3.0 | 0 |
| `xdomain_security_audit_to_code_dev_domain_sec_file_perm` | low | `domain == 'code_dev'` | `suggest_cross_domain; code dev: 写入可执行文件或系统关键路径前确认权` | 3.0 | 0 |
| `xdomain_security_audit_to_code_dev_domain_sec_network_e` | low | `domain == 'code_dev'` | `suggest_cross_domain; code dev: 向外部网络发送数据前确认数据不包含敏` | 3.0 | 0 |
| `xdomain_security_audit_to_code_dev_domain_sec_path_trav` | low | `domain == 'code_dev'` | `suggest_cross_domain; code dev: 文件操作中避免路径注入，禁止用户输入` | 3.0 | 0 |
| `xdomain_security_audit_to_code_dev_domain_sec_secret_in` | low | `domain == 'code_dev'` | `suggest_cross_domain; code dev: 任何回复/输出中禁止出现 API K` | 3.0 | 0 |
| `xdomain_security_audit_to_collaboration_domain_sec_command_i` | low | `domain == 'collaboration'` | `suggest_cross_domain; collaboration: shell 命令中若包含外` | 3.0 | 0 |
| `xdomain_security_audit_to_collaboration_domain_sec_env_crede` | low | `domain == 'collaboration'` | `suggest_cross_domain; collaboration: 读取环境变量中的凭据后不得` | 3.0 | 0 |
| `xdomain_security_audit_to_collaboration_domain_sec_file_perm` | low | `domain == 'collaboration'` | `suggest_cross_domain; collaboration: 写入可执行文件或系统关键路` | 3.0 | 0 |
| `xdomain_security_audit_to_collaboration_domain_sec_network_e` | low | `domain == 'collaboration'` | `suggest_cross_domain; collaboration: 向外部网络发送数据前确认数` | 3.0 | 0 |
| `xdomain_security_audit_to_collaboration_domain_sec_path_trav` | low | `domain == 'collaboration'` | `suggest_cross_domain; collaboration: 文件操作中避免路径注入，禁` | 3.0 | 0 |
| `xdomain_security_audit_to_collaboration_domain_sec_secret_in` | low | `domain == 'collaboration'` | `suggest_cross_domain; collaboration: 任何回复/输出中禁止出现 ` | 3.0 | 0 |
| `xdomain_security_audit_to_data_analysis_domain_sec_command_i` | low | `domain == 'data_analysis'` | `suggest_cross_domain; data analysis: shell 命令中若包含外` | 3.0 | 0 |
| `xdomain_security_audit_to_data_analysis_domain_sec_env_crede` | low | `domain == 'data_analysis'` | `suggest_cross_domain; data analysis: 读取环境变量中的凭据后不得` | 3.0 | 0 |
| `xdomain_security_audit_to_data_analysis_domain_sec_file_perm` | low | `domain == 'data_analysis'` | `suggest_cross_domain; data analysis: 写入可执行文件或系统关键路` | 3.0 | 0 |
| `xdomain_security_audit_to_data_analysis_domain_sec_network_e` | low | `domain == 'data_analysis'` | `suggest_cross_domain; data analysis: 向外部网络发送数据前确认数` | 3.0 | 0 |
| `xdomain_security_audit_to_data_analysis_domain_sec_path_trav` | low | `domain == 'data_analysis'` | `suggest_cross_domain; data analysis: 文件操作中避免路径注入，禁` | 3.0 | 0 |
| `xdomain_security_audit_to_data_analysis_domain_sec_secret_in` | low | `domain == 'data_analysis'` | `suggest_cross_domain; data analysis: 任何回复/输出中禁止出现 ` | 3.0 | 0 |
| `xdomain_security_audit_to_project_mgmt_domain_sec_command_i` | low | `domain == 'project_mgmt'` | `suggest_cross_domain; project mgmt: shell 命令中若包含外部` | 3.0 | 0 |
| `xdomain_security_audit_to_project_mgmt_domain_sec_env_crede` | low | `domain == 'project_mgmt'` | `suggest_cross_domain; project mgmt: 读取环境变量中的凭据后不得明` | 3.0 | 0 |
| `xdomain_security_audit_to_project_mgmt_domain_sec_file_perm` | low | `domain == 'project_mgmt'` | `suggest_cross_domain; project mgmt: 写入可执行文件或系统关键路径` | 3.0 | 0 |
| `xdomain_security_audit_to_project_mgmt_domain_sec_network_e` | low | `domain == 'project_mgmt'` | `suggest_cross_domain; project mgmt: 向外部网络发送数据前确认数据` | 3.0 | 0 |
| `xdomain_security_audit_to_project_mgmt_domain_sec_path_trav` | low | `domain == 'project_mgmt'` | `suggest_cross_domain; project mgmt: 文件操作中避免路径注入，禁止` | 3.0 | 0 |
| `xdomain_security_audit_to_project_mgmt_domain_sec_secret_in` | low | `domain == 'project_mgmt'` | `suggest_cross_domain; project mgmt: 任何回复/输出中禁止出现 A` | 3.0 | 0 |
| `xdomain_security_audit_to_writing_domain_sec_command_i` | low | `domain == 'writing'` | `suggest_cross_domain; writing: shell 命令中若包含外部输入，必须` | 3.0 | 0 |
| `xdomain_security_audit_to_writing_domain_sec_env_crede` | low | `domain == 'writing'` | `suggest_cross_domain; writing: 读取环境变量中的凭据后不得明文输出到日` | 3.0 | 0 |
| `xdomain_security_audit_to_writing_domain_sec_file_perm` | low | `domain == 'writing'` | `suggest_cross_domain; writing: 写入可执行文件或系统关键路径前确认权限` | 3.0 | 0 |
| `xdomain_security_audit_to_writing_domain_sec_network_e` | low | `domain == 'writing'` | `suggest_cross_domain; writing: 向外部网络发送数据前确认数据不包含敏感` | 3.0 | 0 |
| `xdomain_security_audit_to_writing_domain_sec_path_trav` | low | `domain == 'writing'` | `suggest_cross_domain; writing: 文件操作中避免路径注入，禁止用户输入直` | 3.0 | 0 |
| `xdomain_security_audit_to_writing_domain_sec_secret_in` | low | `domain == 'writing'` | `suggest_cross_domain; writing: 任何回复/输出中禁止出现 API Ke` | 3.0 | 0 |
| `xdomain_writing_to_code_dev_domain_write_code_in` | low | `domain == 'code_dev'` | `suggest_cross_domain; code dev: 文档中提供的代码片段必须是完整可运行` | 3.0 | 0 |
| `xdomain_writing_to_code_dev_domain_write_link_ve` | low | `domain == 'code_dev'` | `suggest_cross_domain; code dev: 文档中的引用链接必须在回复前确认未被` | 3.0 | 0 |
| `xdomain_writing_to_code_dev_domain_write_structu` | low | `domain == 'code_dev'` | `suggest_cross_domain; code dev: 文档标题层级不能跳跃（H1→H3 必` | 3.0 | 0 |
| `xdomain_writing_to_code_dev_domain_write_term_co` | low | `domain == 'code_dev'` | `suggest_cross_domain; code dev: 文档中同一术语不得混用不同名称，首次` | 3.0 | 0 |
| `xdomain_writing_to_collaboration_domain_write_code_in` | low | `domain == 'collaboration'` | `suggest_cross_domain; collaboration: 文档中提供的代码片段必须是` | 3.0 | 0 |
| `xdomain_writing_to_collaboration_domain_write_link_ve` | low | `domain == 'collaboration'` | `suggest_cross_domain; collaboration: 文档中的引用链接必须在回复` | 3.0 | 0 |
| `xdomain_writing_to_collaboration_domain_write_structu` | low | `domain == 'collaboration'` | `suggest_cross_domain; collaboration: 文档标题层级不能跳跃（H1` | 3.0 | 0 |
| `xdomain_writing_to_collaboration_domain_write_term_co` | low | `domain == 'collaboration'` | `suggest_cross_domain; collaboration: 文档中同一术语不得混用不同` | 3.0 | 0 |
| `xdomain_writing_to_data_analysis_domain_write_code_in` | low | `domain == 'data_analysis'` | `suggest_cross_domain; data analysis: 文档中提供的代码片段必须是` | 3.0 | 0 |
| `xdomain_writing_to_data_analysis_domain_write_link_ve` | low | `domain == 'data_analysis'` | `suggest_cross_domain; data analysis: 文档中的引用链接必须在回复` | 3.0 | 0 |
| `xdomain_writing_to_data_analysis_domain_write_structu` | low | `domain == 'data_analysis'` | `suggest_cross_domain; data analysis: 文档标题层级不能跳跃（H1` | 3.0 | 0 |
| `xdomain_writing_to_data_analysis_domain_write_term_co` | low | `domain == 'data_analysis'` | `suggest_cross_domain; data analysis: 文档中同一术语不得混用不同` | 3.0 | 0 |
| `xdomain_writing_to_project_mgmt_domain_write_code_in` | low | `domain == 'project_mgmt'` | `suggest_cross_domain; project mgmt: 文档中提供的代码片段必须是完` | 3.0 | 0 |
| `xdomain_writing_to_project_mgmt_domain_write_link_ve` | low | `domain == 'project_mgmt'` | `suggest_cross_domain; project mgmt: 文档中的引用链接必须在回复前` | 3.0 | 0 |
| `xdomain_writing_to_project_mgmt_domain_write_structu` | low | `domain == 'project_mgmt'` | `suggest_cross_domain; project mgmt: 文档标题层级不能跳跃（H1→` | 3.0 | 0 |
| `xdomain_writing_to_project_mgmt_domain_write_term_co` | low | `domain == 'project_mgmt'` | `suggest_cross_domain; project mgmt: 文档中同一术语不得混用不同名` | 3.0 | 0 |
| `xdomain_writing_to_security_audit_domain_write_code_in` | low | `domain == 'security_audit'` | `suggest_cross_domain; security audit: 文档中提供的代码片段必须` | 3.0 | 0 |
| `xdomain_writing_to_security_audit_domain_write_link_ve` | low | `domain == 'security_audit'` | `suggest_cross_domain; security audit: 文档中的引用链接必须在回` | 3.0 | 0 |
| `xdomain_writing_to_security_audit_domain_write_structu` | low | `domain == 'security_audit'` | `suggest_cross_domain; security audit: 文档标题层级不能跳跃（H` | 3.0 | 0 |
| `xdomain_writing_to_security_audit_domain_write_term_co` | low | `domain == 'security_audit'` | `suggest_cross_domain; security audit: 文档中同一术语不得混用不` | 3.0 | 0 |
