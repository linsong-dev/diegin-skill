# 迭进验收注册表（Acceptance Register）

> 版本: v1.0 | 日期: 2026-08-06
> 定位: 规划/验收编号化 —— 把「意图、稳定验收编号、非目标、实现任务、验证证据」绑定到单一可评审文档，替代散落无编号的 trail 描述。

## 编号规则

- 格式：`ACC-<域>-<序号>`，域取 2 位（如 `SYS` 系统自保护、`QRY` 质量加固、`OPS` 运维）。
- 状态机：`open`（已立项）→ `in-progress`（实施中）→ `done`（验证全绿）→ `verified`（证据归档）。
- 每条必须登记：意图 / 验收标准 / 非目标 / 实现任务 / 验证证据。缺任一项不得标 `verified`（去伪存真硬地板）。

## 登记

### ACC-SYS-001 — P0 假阳性阻断闭环（2026-08-06 done）
- 意图：解除 8-05 残留 override 升级阻断（修复已 verified 却因 72h TTL 继续误挡所有 PreToolUse）。
- 验收标准：override 对应错误类型在 strikes_db 中 fix_status=verified 时自动跳过并清空归档；非 verified 仍阻断；恢复 enforce 后引擎 allow。
- 非目标：不修改一二不过三升级逻辑本身；不改引擎判定。
- 实现任务：① 清残留 override+熔断复位+enforce 复位 ② pre_tool.ps1 Test-DieginOverride 加 verified 跳过前置（含 blocked_at 无时区 ParseExact 异常规避）③ 双向验证（verified 跳过 / 非 verified 阻断）④ 同步源码库。
- 验证证据：模拟 PreToolUse allow×2；SKIP+CLEANED 日志；自检 13/13；test_all 23/23；源码版 git diff 1 文件待审推。

### ACC-QRY-002 — 核心模块就近指令（2026-08-06 done）
- 意图：engine/evo（16 文件、churn 最高）获得就近可检索的权威边界，消除「约束依赖散落规则」。
- 验收标准：`engine/evo/AGENTS.md` 存在；better-harness agents-md-review nestedInstructionCount=1、documents 含 engine/evo/AGENTS.md；与根 AGENTS.md 无规则冲突（warning 仅多入口提示）。
- 非目标：不新增/修改 engine/evo 源码行为；不改根 AGENTS.md。
- 实现任务：撰写模块专属指令（规则库/Mindol 一致性、op_contains 白名单+NOT 标准化、_force_reopen 审计留痕、归档护栏、变更流程）。
- 验证证据：lint 复现 nestedInstructionCount 0→1；docs 列表含 engine/evo/AGENTS.md；multi-entrypoint 为可接受提示（非重复/冲突）。

### ACC-QRY-003 — 规划/验收编号化（2026-08-06 open）
- 意图：让规划文档承载可评审的验收编号，替代散落 HANDOVER/trail 的无编号描述。
- 验收标准：本注册表存在且至少一条规划路径引用稳定验收编号；后续实现任务在开始前打开对应 ACC 条目。
- 非目标：不为历史 trail 补编号（止观门：不追旧账）；不改更业务功能。
- 实现任务：创建本注册表；归属链接进 references/diegin_promotion_plan.md；后续 B-1 变更-验证绑定立项为 ACC-QRY-004。
- 验证证据：注册表文件存在；promotion_plan 含链接；lint references 计数增加。

## 后续立项（B-1 变更-验证绑定）

### ACC-QRY-004 — 编辑后最小验证绑定（2026-08-06 done）
- 意图：任一源码变更后运行与变更最小对应的验证（self_check 13 / test_all 23），命令+修订+结果写入可审计记录。
- 验收标准：变更事件可关联到同一目标的最小验证结果；无验证变更不流入发布。
- 非目标：不扩大变更范围；不重写既有验证命令。
- 实现任务（已实施）：post_tool.ps1 新增 B1 块 —— Test-DieginChangeEvent（apply_patch/edit/写文件语义，排除只读查询）+ Write-DieginChangeRecord（self_check 最小验证 + dgen_change_log.json 追加审计，cap 200）；发布门禁联动 sync.ps1（见 ACC-QRY-006）。
- 验证证据：三场景测试通过（apply_patch 记录✓ / 写 shell 记录✓ / 只读排除✓，self_check=passed）；sync.ps1 门禁三场景（无日志放行/全 passed 放行/含 failed 拦截）。
### ACC-QRY-005 — 自动提取质量门（2026-08-06 done）
- 意图：解决「自动提取无质量门」——攻七 record_success / 举一反三 generalize / 自动提升 promote 链路不得把乱码、测试样本、只读查询噪音自动固化为模式或规则。
- 验收标准：`_noise_reason` 质量门拒绝：乱码路径 ??/U+FFFD、疑似测试样本（x.txt/test/_p0_/_b1_/tmp 等）、只读查询命令（Get-Content/git status 等）；真实部署/构建命令通过。
- 非目标：不禁止自动提取本身（攻七正向强化保留）；不改人工评审路径。
- 实现任务：rule_engine.py 新增 `_noise_reason`（共享质量门）并接入 3 处：auto_sandwich 建模式、generalize_from_patterns 派生规则、promote_pattern 提升；归档 2 条已入库噪音（pat_auto_tool_shell_command_1 模式 + pat_rule_pat_auto_tool_shell_command_1 规则）。
- 验证证据：质量门 11/11 正反向测试通过；噪音模式/规则已归档（lifecycle_status=archived，Mindol 同步）；规则库 265 条（含归档）。
- 边界与人工复核路径（去伪存真·个案复核）：黑名单为启发式，若真实成功经验被误伤（如真实部署脚本恰含 `x.txt`/`test`），按「人工复核」流程处理——人工确认后显式降级该模式/规则为人工来源（source=manual / lifecycle_status=active），并更新 `_noise_reason` 白名单或精确化判定；不静默放行，不静默归档。

### ACC-QRY-006 — 发布门禁联动（2026-08-06 done）
- 意图：无验证变更不得流入发布——同步/推送前检查 dgen_change_log.json 无 failed/error 验证记录。
- 验收标准：sync.ps1 sync-rules/sync-all 执行前调用 Test-PublishGate；含 failed 记录时中止（exit 1）；无日志或全 passed 放行。
- 非目标：不侵入 checkpush 本体（独立工具）；不改既有验证命令。
- 实现任务：sync.ps1 新增 Test-PublishGate 函数并接入 sync-rules/sync-all；修复 PS 5.1 无 BOM UTF-8 中文解码坑（给 sync.ps1 加 UTF-8 BOM，与 hooks/*.ps1 约定一致）。
- 验证证据：门禁三场景测试通过（无日志→true / 全 passed→true / 含 failed→false）；sync.ps1 语法 0 错误。
