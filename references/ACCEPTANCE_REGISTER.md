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
- 实现任务：撰写模块专属指令（规则库/Shalou 一致性、op_contains 白名单+NOT 标准化、_force_reopen 审计留痕、归档护栏、变更流程）。
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
- 验证证据：质量门 11/11 正反向测试通过；噪音模式/规则已归档（lifecycle_status=archived，Shalou 同步）；规则库 265 条（含归档）。
- 边界与人工复核路径（去伪存真·个案复核）：黑名单为启发式，若真实成功经验被误伤（如真实部署脚本恰含 `x.txt`/`test`），按「人工复核」流程处理——人工确认后显式降级该模式/规则为人工来源（source=manual / lifecycle_status=active），并更新 `_noise_reason` 白名单或精确化判定；不静默放行，不静默归档。

### ACC-QRY-006 — 发布门禁联动（2026-08-06 done）
- 意图：无验证变更不得流入发布——同步/推送前检查 dgen_change_log.json 无 failed/error 验证记录。
- 验收标准：sync.ps1 sync-rules/sync-all 执行前调用 Test-PublishGate；含 failed 记录时中止（exit 1）；无日志或全 passed 放行。
- 非目标：不侵入 checkpush 本体（独立工具）；不改既有验证命令。
- 实现任务：sync.ps1 新增 Test-PublishGate 函数并接入 sync-rules/sync-all；修复 PS 5.1 无 BOM UTF-8 中文解码坑（给 sync.ps1 加 UTF-8 BOM，与 hooks/*.ps1 约定一致）。
- 验证证据：门禁三场景测试通过（无日志→true / 全 passed→true / 含 failed→false）；sync.ps1 语法 0 错误。

### ACC-OPS-007 — 运行态审计与三端对齐（2026-09-13 done）
- 意图：收敛「运行中的迭进/沙漏一片混乱」的真实病灶——三端副本漂移（AI 反复读到旧引擎）、交付目录指向废弃目录、每夜维护停摆 10 天、恒常门待办只进不出；并补上会长期复发的守卫，避免下次再漂。
- 验收标准：① 模型加载的技能目录 `plugins\cache\personal\diegin\<ver>\skills\diegin` 与运行版在 engine/hooks/config/references/SKILL.md 上一致（rules 允许仅即时字段不同）；② 会话 cwd 下 `outputs` 可解析、交付环境自愈门 exit=0；③ `find_recoverable()` 不再把已冷存（归档）任务当未完成待办返回；④ 每夜批处理有承载且实测成功；⑤ 运行版无 `.pre_/.bak` 残留；引擎自检 status=ok、failed_checks=[]；test_all 全过。
- 非目标：不改规则数据面（`engine/evo/rules` 运行版独有条目仍走 SR-Sync 既有合并设计）；不破坏源码库镜像的脱敏约束；**不推送含个人绝对路径的提交**（见下「遗留」）。
- 实现任务：① `sync.ps1` 补盲区——`Get-DieginRoots` 纳入插件缓存内嵌 `skills\diegin`，并新增 `sync-cache` 动作（运行版 → 插件缓存根 + skill 镜像，含 rules/references）；② 重指会话 `outputs` 目录联接到 `%DEV_ROOT%\文档`（原指向 2026-08-14 legacy 僵尸目录）；③ `constancy.py`：`find_recoverable` 跳过**原始** `cold_stored`（归档 ≠ 待办；超长快照经 `_cold_pointer` 的不受影响），并补 3 条回归锁；④ 重建 `DGEN-Cron-Batch` 计划任务（本地工具脚本 `diegin_cron_batch.ps1`，含计划任务上下文控制台编码修正）；⑤ 清理运行版 102 个 `.pre_/.bak`（9.3MB）与沙漏旧库备份（释放 32.5MB，保留最新回滚点）。
- 验证证据：
  - 五副本哈希一致 —— `engine/evo/constancy.py` = `44FDB069`、`engine/test_all.py` = `2F1DE82E`、`sync.ps1` = `E7DD89EC`（runtime = src-repo = src(skills) = cache(root) = cache(skills)）。
  - `outputs` → `%DEV_ROOT%\文档`；相对路径实测可解析；`确保交付件可打开.ps1` 返回 exit=0（幂等）。
  - `find_recoverable()` 44 条 → 0 条；`test_all.py` 102/102 通过（含新增冷存回归锁 3 条：未归档可恢复 / 归档不进待办池 / 归档仍可意图检索）。
  - `Get-ScheduledTask DGEN-Cron-Batch` State=Ready、每日 23:30、`Start-ScheduledTask` 实测 LastTaskResult=0；`diegin_cron` 三项作业（downtime_maintenance / deep_review / health_report）当日补跑成功，failures={}。
  - 运行版 `.pre_/.bak` 残留=0；`diegin_self_check` status=ok、failed_checks=[]、dead_rule_count=0、fake_evidence_count=0、baseline_regressions=[]。
- 遗留处置（同日按「运行期路径外置」方案收敛，`checkpush audit` 由 10 处阻断 → **0**）：

  - `hooks/diegin_pre_tool.ps1`（交付环境自愈门 A-1H）：脚本路径外置为 `$env:DGEN_DELIVER_HEAL_SCRIPT` → `$env:DGEN_DEV_ROOT`/`$env:DEV_ROOT` 推导 → 均未设则跳过（仅记录不阻断）。
  - `bin/dgen-hook-verify.ps1`：删除与上一行 `Join-Path` 推导**完全重复**的硬编码回退（语义等价）。
  - `sync.ps1` / `config/requirements.toml` / `engine/evo/rules/interception_rules.json` / `references/钩子事件契约与注入位置矩阵_2026-09-13.md`：改为 `%DEV_ROOT%` / `$env:USERPROFILE` 占位，或改用 `Join-Path (Split-Path $env:CODEX_HOME -Parent) ...` 等**可解析写法**。
  - 本机用户级环境变量 `DGEN_DEV_ROOT`、`DEV_ROOT`、`DGEN_DELIVER_HEAL_SCRIPT` 已设置，保证运行期行为与原硬编码等价。
  - 说明：`OpenAI.Codex`/`KeySync-Bridge` 位于便携版**根目录**下（而非 `.codex` 自身），故未套用 `%CODEX_HOME%`——那会把 `<便携版根>` 展开成错误的双重 `.codex` 层级
- 推送结果（2026-09-13 完成）：提交 `528510e`，`origin/main` 已同步 **0/0**；远端 `hooks/diegin_pre_tool.ps1` 实测含 `DGEN_DELIVER_HEAL_SCRIPT`、**不含**个人路径。首次推送遇 `curl 55 Connection was reset`（直连抖动，本机无可用代理）；设 `http.postBuffer=500MB` + `http.version=HTTP/1.1` 后重试成功。- 待办（非本次范围）：源码库 `pytest` 有 **15 项既有失败**（与 `git stash` 后的 HEAD 基线逐条比对**完全一致**，非本次引入），集中在 `tests/evo/test_constancy_track.py`（旧行为断言，与 2026-09-13「任务资格闸门」新契约不符）、`test_self_mirror`、`test_nine_chapters_integration`、`tests/shalou/test_core.py`；另有 3 条 `GIT-HISTORY` 敏感串警告（需重写历史 + force push，人工决策）。。

### ACC-OPS-008 — 15 项既有测试失败清零 + pre_reply 意图上下文落盘修复（2026-09-13 done）
- 意图：收口 ACC-OPS-007「待办①」——源码库 `pytest` 15 项既有失败逐项定因并清零；期间暴露并修复一个**自 2026-08-14 起一直被静默吞掉**的真实缺陷。
- 验收标准：① `pytest tests` 0 failed；② 15 项逐项给出根因归类（真实缺陷 / 契约变更 / 时间脆弱 / 数据源耦合 / 口径对齐），不得用 skip/xfail 掩盖；③ 真实缺陷修复后 `pre_reply` 端到端落盘 `current_intent.json` 且钩子可读；④ `test_all.py` 102/102、引擎自检 ok、engine/config 四副本一致。
- 非目标：不改任务资格闸门口径（口径 A 已冻结）；不动规则数据面；不 bump 插件版本（留待下次审推统一）；不重写 git 历史（3 条 `GIT-HISTORY` 警告仍属人工决策）。
- 实现任务：① `engine/call_diegin.py`：`pre_reply` 的 `write_current_intent` 实参 `_user_negative` → `None`（该名在该分支从未定义，NameError 被裸 except 吞掉）；② 六个测试文件按根因对齐（显式任务声明 / 多步 prompt + 状态快照 / 相对时间戳 / 持存趋势口径 + 固定报告注入 / 空间数 12）；③ `sync.ps1 sync-eng` 推 engine+config 至 runtime / skills-mirror / plugin-cache 两处；④ CHANGELOG v3.10.7+ 与本报告登记。
- 验证证据：
  - `pytest tests` = **283 passed / 0 failed**（改前 15 failed / 268 passed）；逐项归因见 `%DEV_ROOT%\文档\迭进_15项既有测试失败清零_2026-09-13.md` 第二节。
  - 真实缺陷端到端实证：`pre_reply` 子进程 rc=0 → `var/state/current_intent.json` 落盘，含 `intent_summary` + `task_id` + `ts`（60 分钟内可被 `hooks/diegin_post_tool.ps1` 读取）；验证后已清理探针任务与探针文件。
  - `test_all.py` **102/102**（源码库与运行版各跑一次）；运行版 `diegin_self_check` status=ok、failed_checks=[]、dead_rule_count=0、fake_evidence_count=0、baseline_regressions=[]；源码库自检的 `no_stale_staging`/`baseline_no_regression` 经 `git stash` 基线比对为**既有**差异（逐条一致，非本次引入）。
  - 副本守卫：`sync.ps1 check` → engine/config 四副本（runtime / skills-mirror / plugin-cache / plugin-cache-skills）全绿；`engine/call_diegin.py` SHA256 前缀 `129D7D6E9F77C01C` 五处一致。
  - 行尾卫生：改动文件「混合行尾」=0；`engine/call_diegin.py` CRLF=3882 / LF=0；六个测试文件维持 LF；均无 BOM。
- 推送结果（2026-09-13 完成）：提交 f33a44（9 文件 / +108 −26），188755..ff33a44  main -> main；origin/main 核对 **0/0**（已同步）。audit ALL CLEAN（0 issues；3 条既有 GIT-HISTORY 非阻断）、verify PASSED（pytest 283 passed）。审推工具走直连（本地代理不可用）。
