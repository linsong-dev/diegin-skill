# 迭进守护协议（Guardrail Protocol）— 分析 · 审查 · 验证三环保障

> 版本: v1.0 | 日期: 2026-08-04
> 定位: 迭进引擎自身运行质量的自举保障机制。解决"规则写入了却没生效 / 问题反复出现 / 迭进像假的"这一系统性缺陷。

## 0. 为什么需要本协议（真实案例）

2026-08-04 审计发现：规则库 215 条 active 规则中 **202 条从未触发**（triggered_count=0），
其中 7 条 BOM/编码规则（confidence 4.3~5.0）全部为死规则，导致 Set-Content 写文件产生 UTF-8 BOM 的问题
在 7/10、7/11、7/12、8/03 四次复发、四次重写规则均未生效。

**根因**：规则 trigger 引用了钩子上下文不存在的字段（`shell_type`、`op`、`file_write`、`task_is_deploy_or_sync_or_upgrade` 等），
安全求值器把这些裸词转成字符串常量，表达式恒为 False → 规则永远不命中，且写入时无任何验证。
迭进缺的不是"写规则"，而是 **写规则后证明它能被触发** + **持续揪出没触发的死规则**。

## 1. 三环框架总览

```
┌─────────────────────────────────────────────────────────────┐
│                    迭进守护协议（三环六步）                      │
├───────────────┬──────────────────┬──────────────────────────┤
│  环1 分析       │   环2 审查         │   环3 验证                │
│  Analyze       │   Review          │   Verify                 │
├───────────────┼──────────────────┼──────────────────────────┤
│ A1 数据采集     │ R1 写入门禁        │ V1 触发验证               │
│ A2 规则体检     │ R2 周期审查        │ V2 行为回环               │
│ A3 健康基线     │ R3 分级处置        │ V3 防再生接线             │
└───────────────┴──────────────────┴──────────────────────────┘
                    ↑ 闭环：每环产出进入下一环，验证失败回流分析
```

## 2. 环1 分析（Analyze）— 弄清"现状是什么"

| 步骤 | 内容 | 数据源 | 产出 |
|:----|:-----|:-------|:-----|
| A1 数据采集 | 规则触发计数、阻断记录、strike、健康度 | `interception_rules.json`、`rule_counter_deltas.json`、`diegin_audit.log`、`rule_health.json` | 触发矩阵 |
| A2 规则体检 | 死规则（active 超 7 天触发=0）、恒真规则、裸词字段、双存储一致性 | 自检输出 `diegin_self_check.json` | 问题清单 |
| A3 健康基线 | 熵/信噪比/容量/满意度 | `health_check()` | 健康报告 |

**判定标准（去伪存真）**：
- `triggered_count > 0` = 规则真实进入过匹配流程
- `triggered_count = 0` 且创建超 7 天 = 死规则候选，进入环2 处置
- 审计日志存在 `[HOOK:DGEN-BLOCK]` 且规则 id 对应 = 行为证据

## 3. 环2 审查（Review）— 决定"该不该留/怎么写"

### R1 写入门禁（已实现：`rule_engine.py` 触发验证门）
每条新规则/更新规则写入时强制验证，三级分级：

| 级别 | 判定 | 动作 |
|:----|:-----|:-----|
| **P0** | trigger 引用上下文不存在的字段（`shell_type`/`op`/`task_type == file_write` 等裸词） | **拒绝写入**（raise ValueError），确定性死规则 |
| **P1** | 引用 `domain` 等仅语义字段（表达式永不命中，只靠 Shalou 检索） | 告警放行 |
| **P2** | 字段合法但在全部真实钩子上下文模板下均未命中 | 告警放行（提示作者复核） |

钩子真实字段白名单（模板）：`task_type`、`tool_name`、`command`、`text`、`prompt`、
`hook_event_name`、`marker_missing`、`blocked_error_type`；内置：`context`、`error_type`、`domain` 等。

### R2 周期审查（已实现：自检检查 #10）
- **每次自检**（会话触发）：扫描 active 且创建超 7 天且触发=0 的规则 → 写入 `dead_rules` 列表
- **每周专项**：对死规则批量分级处置
- 死规则仅报告不置 failed（避免存量问题每次自检触发 strike 误伤正常流程）

### R3 分级处置（死规则四选一）
| 处置 | 条件 | 操作 |
|:----|:-----|:-----|
| 修复 | trigger 写错字段/值（如 BOM 规则） | `update_interception` 改真实字段，过验证门 |
| 保留 | 触发窗口极窄但合理（如 critical 兜底） | 标记 `source_review` 注明保留理由 |
| 归档 | 3 轮审查仍 0 触发且无保留理由 | `lifecycle_status=archived` |
| 删除 | 已证实无效/被替代 | `delete_interception` |

## 4. 环3 验证（Verify）— 证明"真的生效"

| 步骤 | 内容 | 判定 |
|:----|:-----|:-----|
| V1 触发验证 | 用真实钩子上下文模板跑 `_match_condition`，要求命中 | 命中=通过；否则回到 R1/P2 告警 |
| V2 行为回环 | 规则写入后观察审计日志：`[HOOK:DGEN-BLOCK] rule=<id>` 出现 | 3 天内无记录 → 回 A2 标记死规则候选 |
| V3 防再生接线 | 自检失败项映射到 `PREVENTION_STRIKE_MAP` → 一二不过三 strike | 1警→2阻→3升级，封顶3 |

**关键原则：验证必须用"运行证据"，不用"代码存在"代替。**
- 代码存在 ≠ 生效；`triggered_count>0` + 审计 BLOCK 记录 = 生效
- 每次验证写 trail（`workspace/trail_*.md`），形成可追溯链条

## 5. 落地机制映射（全部已接线）

| 机制 | 位置 | 状态 |
|:----|:-----|:-----|
| 触发验证门（P0 拒绝 / P1/P2 告警） | `engine/evo/rule_engine.py` | ✅ 已实现 |
| 钩子上下文模板 + 字段审计 | `rule_engine.py: HOOK_CONTEXT_TEMPLATES` | ✅ 已实现 |
| 死规则检测（7 天未触发） | `engine/diegin_self_check.py` 检查 #10 | ✅ 已实现 |
| 自检失败 → strike 接线 | `diegin_self_check.py PREVENTION_STRIKE_MAP` | ✅ 已有 |
| 健康基线 | `workspace/rule_health.json` | ✅ 已有 |
| 执行轨迹 | `workspace/trail_*.md` | ✅ 已有 |

## 6. 执行节奏

| 时机 | 动作 |
|:----|:-----|
| 每次会话启动 | 自检全量跑（含死规则检测） |
| 每次写规则/改 trigger | 触发验证门自动执行 |
| 每次工具调用/回复 | 预检+记忆注入（引擎常驻） |
| 每周 | 死规则专项审查 + 分级处置 |
| 发布前（checkpush） | 编码审计门禁（BOM/乱码） |

## 7. 本次修复落地记录（2026-08-04）

1. **激活 7 条 BOM 死规则**：`rule_json_no_bom`、`rule_encoding_no_bom_utf8`、`rule_windows_bom_audit`、
   `rule_powershell_set_content_bom`、`rule_deploy_ps1_avoid_set_content`、`rule_pre_deploy_encoding_audit`、
   `rule_encoding_pre_check` —— trigger 全部改为钩子真实字段（command/text/task_type 关键词），
   三场景验证命中（Set-Content 写 json / deploy 同步 / 用户编码要求）。
2. **触发验证门上线**：P0 拒绝"引用不存在字段"（实测 `shell_type == powershell` 被拒），
   杜绝未来新死规则。
3. **死规则检测上线**：自检暴露存量 193 条死规则（多为 xdomain/seed 历史规则），
   进入每周专项处置队列。
