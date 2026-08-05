# DGEN 开发运维 SOP（防再生铁律）

> 依据守三（负向纠错→写入固化）固化本次实战踩坑教训。
> 适用范围：任何修改 diegin 运行版（.codex\diegin）的钩子/引擎/规则文件。

## 1. 编码铁律（Windows PS5.1 + 中文环境）

| # | 规则 | 教训来源 |
|---|---|---|
| E1 | **所有 hooks/*.ps1 必须 UTF-8 带 BOM**（前 3 字节 EF BB BF）。PS5.1 无 BOM 按 GBK 解析中文 → 乱码 → 钩子静默失败 | git 3e14aac + 本次实战 |
| E2 | **写 ps1 用 `WriteAllLines/WriteAllText` + UTF8Encoding($true)**（BOM），禁用 NoBOM 写 ps1 | 本次实战（A1 曾 NoBOM 写回致乱码） |
| E3 | **call_diegin.py 的 stdin 必须字节级去 BOM**：`sys.stdin.buffer.read()` → 去 `b"\xef\xbb\xbf"` → `decode("utf-8")`。PS 管道会自动注入 UTF-8 BOM 字节，`json.loads` 直接崩溃 | 本次实战（A1 根因） |
| E4 | PowerShell 命令行传中文路径/中文内容会被转义破坏 → **改用补丁脚本文件**（写 .ps1/.py 到 TEMP 再执行） | 本次实战（多次命令被转义/拦截） |

## 2. 修改流程铁律

| # | 规则 |
|---|---|
| M1 | 修改前必须备份：`xxx.bak_<步骤>_<日期>`（保留 BOM） |
| M2 | 用 `ParseInput`（读文件+UTF8 显式编码）验证 PS 语法，**不要用 ParseFile**（按 GBK 读无 BOM 文件误报错误） |
| M3 | Python 用 `py_compile` 验证 |
| M4 | 行数组编辑用 `List[string]` + 锚点校验（改前确认锚点行内容），避免行号漂移 |
| M5 | 测试钩子必须**完整复制 engine/ + hooks/ + var/**（缺 engine 会让坏 python 与真 bug 混淆） |

## 3. 测试铁律

| # | 规则 |
|---|---|
| T1 | 钩子测试用 `cmd /c "powershell -File <hook> < in.json"`（文件重定向），**不要用 PS 嵌套管道**（外层 stdin 被 ReadToEnd 消费后内层 python 收到 EOF） |
| T2 | 故障路径测试用 `$env:DGEN_PYTHON = "C:\nonexistent\python.exe"` 覆盖（钩子已支持该 env） |
| T3 | 每轮修改后检查：语法 0 错误 + BOM 正确 + 无 `.tmp_*` 残留 + stdout 无污染（函数返回值泄漏会进 Codex 裁决流） |

## 4. 原子写铁律

| # | 规则 |
|---|---|
| A1 | `Write-AtomicFile` 必须：tmp+`File.Replace(tmp, dst, realBackupPath)`；**`$null` 备份路径会抛 "path is not of a legal form"**（PowerShell $null→空串） |
| A2 | 任何路径必须 try/catch 兜底（Delete+Move）+ finally 清理 tmp，防残留 |
| A3 | 函数不要 `return $ok`（返回值会泄漏到 stdout 污染 Codex 裁决流），用 `[void]` 或直接无返回 |

## 5. 防再生自检（SessionStart 机械执行）

`diegin_self_check.py` 已内置：hooks_ps1_bom / no_tmp_residue / stdin_bom_guard / dual_store_consistent / key_rules_present。
任何修改后运行：`python engine\diegin_self_check.py`，必须 status=ok 才视为完成。

## 6. 修改范围铁律

| # | 规则 |
|---|---|
| R1 | 运行版（.codex\diegin）为唯一权威落点；源码库（本地源码库\Diegin）从运行版同步 |
| R2 | 不在 hooks.json/config.toml 信任哈希之外改配置；改 hooks.json 需同步 config.toml 哈希 |
| R3 | 每步骤修改-测试-检查-验证-清理，清理含 TEMP 补丁脚本与测试目录 |

## 7. 攻七强化与质量审计（v3.8）

| # | 规则 |
|---|---|
| G1 | 攻七模式写入门槛：decision_logic 必须 ≥6 实质字符（无工具名/状态词填充），否则不入库 |
| G2 | 每次规则库/模式库变更后运行 `python engine\call_diegin.py audit_patterns`（空壳自动归档，幂等） |
| G3 | staging 积压检查：`python engine\call_diegin.py audit_staging`（死亡→归档 / 触发≥2→active） |
| G4 | 证据库去假：`python engine\call_diegin.py audit_evidence`（evidence_filter 批量 pass 标记 skip） |
| G5 | 攻七反馈闭环：post_tool 自动调用 `feedback_adopt`（工具成功+priority 推荐 → 置信度+0.5）；测试用 `adopted=false` 验证 veto 路径后必须清理 |
| G6 | 修改攻七相关代码后：验证 4 场景——同场景加权 allow / 异场景守三不误伤 / 持平守三优先 / 空 context 默认放行 |
| G7 | 自检必须含 `no_hollow_patterns` / `no_stale_staging` / `no_fake_evidence` 三项为 true（防再生） |
| G8 | ps1 改动用 UTF-8 带 BOM 写回（`UTF8Encoding($true)`）；若误用 NoBOM 写回，自检 `hooks_ps1_bom` 会 FAIL 并记 strike，需恢复 BOM 后清理 strike |

## 8. 文档同步铁律

| # | 规则 |
|---|---|
| D1 | 引擎/钩子行为变更后必须同步更新：SKILL.md（协议+指令表）、README.md（版本+特性）、workspace\dgen_rules.md（重新生成）、dev_ops_sop.md（SOP）、AGENTS.md（规则数） |
| D2 | workspace\dgen_rules.md 为自动生成索引，用脚本从 interception_rules.json 重新生成，禁止手改 |
| D3 | 每次工作轮次新建 workspace\trail_<日期>.md 记录变更与验证实证 |
| D4 | 文档更新后运行 checkpush pre-check，通过后再 push |
