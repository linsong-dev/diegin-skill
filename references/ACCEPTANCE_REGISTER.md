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

### ACC-QRY-004 — 编辑后最小验证绑定（2026-08-06 in-progress）
- 意图：任一源码变更后运行与变更最小对应的验证（self_check 13 / test_all 23），命令+修订+结果写入可审计记录。
- 验收标准：变更事件可关联到同一目标的最小验证结果；无验证变更不流入发布。
- 非目标：不扩大变更范围；不重写既有验证命令。
- 实现任务（已实施）：post_tool.ps1 新增 B1 块 —— Test-DieginChangeEvent（apply_patch/edit/写文件语义，排除只读查询）+ Write-DieginChangeRecord（self_check 最小验证 + dgen_change_log.json 追加审计，cap 200）。
- 验证证据：三场景测试通过（apply_patch 记录✓ / 写 shell 记录✓ / 只读排除✓，self_check=passed）；待办：发布门禁联动（checkpush 前查未验证变更）。
