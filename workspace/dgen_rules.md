# 迭进规则库（单文件 - 由 dgen_evolve.py 自动维护）
> 生效: 2026-07-07 | v3.0 通用版

---

## 附录A：上下文分层管理

**三层管理：**

| 层级 | 内容 | 裁剪策略 | 存放位置 |
|:---|:---|:---|:---|
| L1 永久 | 规则/模式/关键决策 | 不可裁剪 | 此文件(dgen_rules.md) |
| L2 摘要 | 运行参数/简报 | 可摘要化 | SYSTEM_CONFIG.md |
| L3 临时 | 原始数据/快照 | 可丢弃 | 重新读取即可 |

---

## 附录G：迭进自动化引擎

引擎: `scripts/dgen_evolve.py` | 健康度: `workspace/rule_health.json`

触发→自动观察→自动提议→验证门控→确认生效

**已生效的自动提议：**
1. rule_prioritize — 规则互斥时按严重度自动裁决

---

## ⚡ 从本次工作衍生的迭进规则（2026-07-07）

### 1. 先搞清楚用户说什么再做 — 词义确认规则

**场景：** 用户说 "剥离"，我理解为 "删除并分离" → 用户纠正为 "提取，原项目保留"

| 字段 | 值 |
|:---|:---|
| 规则ID | `rule_word_meaning_confirm` |
| 严重度 | high |
| 触发条件 | 用户使用歧义词（剥离/清除/迁移/整理）时，先确认具体含义再执行 |
| 行为 | 执行前反问用户具体意图，或同时给出两种方案 |
| 来源 | 2026-07-07 提取迭进工作 |

### 2. 先查全貌再行动 — 范围确认规则

**场景：** 用户说 "检查迭进内容"，我只搜了主目录 → 用户纠正为"从三个实际目录找"

| 字段 | 值 |
|:---|:---|
| 规则ID | `rule_scope_full_check` |
| 严重度 | high |
| 触发条件 | 接到"检查/搜索/提取/分析"任务时，先确认搜索范围（所有关联路径）再开始 |
| 行为 | 先列出所有可能路径，确认后再执行搜索 |
| 来源 | 2026-07-07 迭进搜索路径事件 |

### 3. 少下结论多验证 — 在确凿证据前不下定论

**场景：** 我说 "JSON有10条规则不对，文档说13条" → 实际是两套体系，需要合并而非替换

| 字段 | 值 |
|:---|:---|
| 规则ID | `rule_check_before_conclude` |
| 严重度 | medium |
| 触发条件 | 发现数字/数量/内容不一致时，先排查是否存在多套来源/两套体系/版本差异，再下"不一致"结论 |
| 行为 | 先列出所有来源的数据，交叉验证后再输出结论 |
| 来源 | 2026-07-07 规则数量误判事件 |

### 4. 提取完整再报告 — 确认完整范围原则

**场景：** 用户说 "全盘自动化"，我第一次提取时遗漏了 dgen_evolve.py / rule_health.json / trail

| 字段 | 值 |
|:---|:---|
| 规则ID | `rule_extract_full_scope` |
| 严重度 | high |
| 触发条件 | 执行"提取/迁移/复制"任务时，先确认全貌再动手 |
| 行为 | 先遍历所有相关文件路径，列出完整清单，覆盖确认后再执行复制 |
| 来源 | 2026-07-07 迭进提取遗漏事件 |

### 5. 清洗必须逐层确认 — 多层清洗验证规则

**场景：** 用户说"清洗残留"，前3次我依赖自动扫描说"干净了"，但用户指正还有大量残留。最终用 .Contains() 逐文件才确认干净

| 字段 | 值 |
|:---|:---|
| 规则ID | `rule_clean_verify_layered` |
| 严重度 | critical |
| 触发条件 | 执行"清洗/删除/替换"内容时，必须做到3层验证 |
| 行为 | ① 自动扫描（regex/关键词）→ ② 逐文件内容审查 → ③ 最终用精确方法.Contains()再确认一次。3层都通过才算干净 |
| 来源 | 2026-07-07 迭进清洗事件 |

### 6. 发布的交付物必须完整可验证

**场景：** 最终交付时我报"干干净净"但实际 workspace 下还有大量未处理的内容

| 字段 | 值 |
|:---|:---|
| 规则ID | `rule_delivery_full_audit` |
| 严重度 | critical |
| 触发条件 | 输出/交付/报告最终版本前，执行全清单审查：每文件逐项确认 |
| 行为 | 列出交付物中每个文件 → 每文件检查是否在作用范围内 → 不在的一律排除或标注 |
| 来源 | 2026-07-07 迭进交付审计事件 |

---

## 速查

| 规则ID | 严重度 | 一句话 |
|:---|:---:|:---|
| `rule_word_meaning_confirm` | high | 歧义词先确认再执行 |
| `rule_scope_full_check` | high | 搜索前确认完范围 |
| `rule_check_before_conclude` | medium | 不一致先多源交叉验证 |
| `rule_extract_full_scope` | high | 提取前确认完整文件清单 |
| `rule_clean_verify_layered` | critical | 清洗必须3层验证 |
| `rule_delivery_full_audit` | critical | 交付前逐文件审查 |
## [NEW] PowerShell 转义 — shell命令构造规则

### 7. PowerShell 转义三层锁 — 命令参数构造保护规则

**场景：** 本次工作中多次遇到 PowerShell 转义问题但未被显式记录。
典型问题模式：
1. Get-ChildItem -Path $path — 反引号转义 $ 变量
2. Select-String -Pattern "转义|escape" — 双引号内竖线 | 被解释为管道
3. JSON 中包含 $ 或 " 时直接在 PowerShell 字符串中传递 → 语法错误
4. '-match' vs 正则的 Unicode 误报 — 不同比较运算符的语义差异
5. $variable 在单引号 vs 双引号中的行为差异（展开 vs 不展开）
6. 路径中有空格或括号时缺少 & 调用运算符

| 字段 | 值 |
|:---|:---|
| 规则ID | 
ule_powershell_escape_triple_lock |
| 严重度 | **critical** |
| 触发条件 | 在 PowerShell 环境中构造命令行参数时 |
| 行为 | 执行前检查三层：① 变量引用是否用对引号类型 ② 特殊字符（\|&\$\"()）是否转义 ③ JSON/对象参数是否通过 stdin 而非命令行传 |
| 子规则 | |
| | 
7a_quote_type_aware — medium | 单引号(')内所有字符字面量；双引号(")内 $ 需反引号转义 |
| | 
7b_pipe_in_quotes — high | 竖线 \| 在双引号字符串中仍是管道，需用 --% 或转义 |
| | 
7c_args_via_stdin — high | 复杂 JSON/嵌套对象 → 绝不拼命令行，改 stdin 传参 |
| | 
7d_path_safe_delimiter — medium | 路径含空格/括号/Unicode → 用 --% 或 -LiteralPath 而非 -Path |
| | 
7e_comparison_semantics — low | -match 是正则匹配，.Contains() 是子串匹配，不可混用 |
| 来源 | 2026-07-07 迭进提取清洗全程 + 历史多次 exec_command 翻车 |

### 8. 命令行先试后跑 — 命令构造安全验证规则

**场景：** 直接在 exec_command 中写入未测试的复杂管道/转义序列。

| 字段 | 值 |
|:---|:---|
| 规则ID | 
ule_cmd_test_before_run |
| 严重度 | **high** |
| 触发条件 | 构造长度超过 200 字符的命令行，或包含 2 层以上管道/引号嵌套 |
| 行为 | 先输出裸露命令字符串审查 → 确保肉眼可读且语法正确 → 再执行 |
| 来源 | 2026-07-07 多次命令行错误后修正的经验 |

---

## [NEW] 补充发现的缺失规则（2026-07-07 第二批次）

### 9. Python 路径可靠检测规则 — 已知可用工具链优先

**场景：** where.exe python 能找到但 python -c 不可用（Windows App Store 沙箱限制），浪费多次尝试。

| 字段 | 值 |
|:---|:---|
| 规则ID | 
ule_toolchain_path_verify |
| 严重度 | **high** |
| 触发条件 | 调用外部解释器（python/node/dotnet）前 |
| 行为 | 先运行简单测试（python -c "print(1)"）确认可用，而不只看 where.exe 或 Get-Command |
| 子规则 | |
| | 
9a_verify_before_use — high | 任何解释器调用前先 Hello World 测试，不可用时立即切换降级链 |
| | 
9b_fallback_chain — medium | 降级顺序：js tool > PowerShell native > cmd > 通知用户切换环境 |
| 来源 | 2026-07-07 迭进清洗阶段 |

### 10. 文件编码确认规则 — 读之前检查编码

**场景：** 	rail_2026-07-07.md 读出来全乱码（UTF-8 文件被 GBK 终端读取）；precedents.json 中已有 learned_gbk_emoji_001 历史教训却未泛化。

| 字段 | 值 |
|:---|:---|
| 规则ID | 
ule_encoding_pre_check |
| 严重度 | **high** |
| 触发条件 | 读取或写入文本文件时 |
| 行为 | ① 优先指定 encoding='utf-8' ② 读文件前检查 BOM 标记 ③ 中文内容先确认编码再展示 ④ 从 precedent 泛化：有相同症状的 precedent 就自动注入防护 |
| 来源 | 2026-07-07 trail 读取 + precedent 未泛化 |

### 11. 命令结果验证规则 — 不假设成功

**场景：** 多次 exec_command 返回空输出时默认假设成功，实际静默失败（Python/python3/node 都翻过）。

| 字段 | 值 |
|:---|:---|
| 规则ID | 
ule_verify_command_exitcode |
| 严重度 | **critical** |
| 触发条件 | 任何 exec_command 或外部工具调用后 |
| 行为 | ① 输出为空 → 不假设成功，检查 stderr 或 exit code ② 有 ErrorRecord / 异常 / Fail → 标记失败 ③ 连续空输出 2 次 → 切换方法 |
| 来源 | 2026-07-07 多次工具调用未反馈 |

### 12. 批量操作前 dry-run 规则

**场景：** 清理 workspace 时直接 Remove-Item，风险不可控。

| 字段 | 值 |
|:---|:---|
| 规则ID | 
ule_dry_run_before_batch |
| 严重度 | **high** |
| 触发条件 | 执行批量删除/移动/重命名操作（超过 3 个文件） |
| 行为 | ① 先输出完整文件列表 + 大小统计 ② 用 -WhatIf 或等效模拟模式 ③ 用户确认后再执行 ④ 删除后验证数量一致 |
| 来源 | 2026-07-07 workspace 清理事件 |

### 13. 工具选择决策规则 — 简单任务用最快的工具

**场景：** 每次需要读文件内容时，在 Get-Content / python / 
ode / js tool 之间反复试错。

| 字段 | 值 |
|:---|:---|
| 规则ID | 
ule_tool_selection_fastest |
| 严重度 | medium |
| 触发条件 | 需要选择文件读取/处理的工具时 |
| 行为 | 优先级：① PowerShell built-in（Get-Content / Select-String）→ ② js tool（Node REPL）→ ③ Python → ④ 第三方工具。不需要安装/路径检测的先上。 |
| 来源 | 2026-07-07 多工具链试错 |

---


## 速查总表（全部 13 条规则 + 同步状态）

| 规则ID | 严重度 | 一句话 | 入库地点 | 同步状态 |
|:---|:---:|:---|:---|:---:|
| rule_word_meaning_confirm | high | 歧义词先确认再执行 | interception_rules.json | [已同步] |
| rule_scope_full_check | high | 搜索前确认完范围 | interception_rules.json | [已同步] |
| rule_check_before_conclude | medium | 不一致先多源交叉验证 | interception_rules.json | [已同步] |
| rule_extract_full_scope | high | 提取前确认完整文件清单 | 留 dgen_rules.md | 场景特定 |
| rule_clean_verify_layered | critical | 清洗必须3层验证 | interception_rules.json | [已同步] |
| rule_delivery_full_audit | critical | 交付前逐文件审查 | interception_rules.json | [已同步] |
| rule_powershell_escape_triple_lock | critical | PowerShell 转义三层锁 | interception_rules.json | [已同步] |
| rule_cmd_test_before_run | high | 命令行先试后跑 | interception_rules.json | [已同步] |
| rule_toolchain_path_verify | high | 工具链路径先验证再使用 | interception_rules.json | [已同步] |
| rule_encoding_pre_check | high | 文件编码先确认再读 | interception_rules.json | [已同步] |
| rule_verify_command_exitcode | critical | 命令结果不假设成功 | interception_rules.json | [已同步] |
| rule_dry_run_before_batch | high | 批量操作前 dry-run | interception_rules.json | [已同步] |
| rule_tool_selection_fastest | medium | 选最快工具 | success_patterns.json | [已同步] |

汇总: 13条中 11条通用规则 -> interception_rules.json（引擎自动拦截）
1条成功模式 -> success_patterns.json
1条场景特定 -> 保留在 dgen_rules.md


## [NEW] 补充发现的缺失规则（2026-07-07 第二批次）

### 9. Python 路径可靠检测规则 - 已知可用工具链优先

场景： where.exe python 能找到但 python -c 不可用（Windows App Store 沙箱限制）

| 字段 | 值 |
|:---|:---|
| 规则ID | rule_toolchain_path_verify |
| 严重度 | high |
| 触发条件 | 调用外部解释器（python/node/dotnet）前 |
| 行为 | 先运行简单测试确认可用，不可用时立即切换降级链 |
| 来源 | 2026-07-07 迭进清洗阶段 |

### 10. 文件编码确认规则 - 读之前检查编码

场景： trail 文件读出来全乱码（UTF-8 被 GBK 终端读取）

| 字段 | 值 |
|:---|:---|
| 规则ID | rule_encoding_pre_check |
| 严重度 | high |
| 触发条件 | 读取或写入文本文件时 |
| 行为 | 优先指定 encoding=utf-8；读前检查 BOM；中文内容先确认编码再展示 |
| 来源 | 2026-07-07 trail 读取 |

### 11. 命令结果验证规则 - 不假设成功

场景： 多次 exec_command 返回空输出时默认假设成功，实际静默失败

| 字段 | 值 |
|:---|:---|
| 规则ID | rule_verify_command_exitcode |
| 严重度 | critical |
| 触发条件 | 任何 exec_command 或外部工具调用后 |
| 行为 | 输出为空则检查 stderr/exit code；有异常/ErrorRecord 标记失败；连续空输出2次切换方法 |
| 来源 | 2026-07-07 多次工具调用未反馈 |

### 12. 批量操作前 dry-run 规则

场景： 清理 workspace 时直接 Remove-Item，风险不可控

| 字段 | 值 |
|:---|:---|
| 规则ID | rule_dry_run_before_batch |
| 严重度 | high |
| 触发条件 | 执行批量删除/移动/重命名操作（超过3个文件） |
| 行为 | 先输出完整文件列表+大小；用 -WhatIf 模拟；确认后执行；删除后验证数量 |
| 来源 | 2026-07-07 workspace 清理 |

### 13. 工具选择决策规则 - 简单任务用最快的工具

场景： 每次读文件在 Get-Content / python / node / js tool 之间反复试错

| 字段 | 值 |
|:---|:---|
| 规则ID | rule_tool_selection_fastest |
| 严重度 | medium |
| 触发条件 | 需要选择文件读取/处理的工具时 |
| 行为 | 优先级：PowerShell built-in > js tool (Node REPL) > Python > 第三方 |
| 来源 | 2026-07-07 多工具链试错 |

---

## 速查总表（全部 13 条规则）

| 规则ID | 严重度 | 一句话 | 入库批次 |
|:---|:---:|:---|:---:|
| rule_word_meaning_confirm | high | 歧义词先确认再执行 | 第一批 |
| rule_scope_full_check | high | 搜索前确认完范围 | 第一批 |
| rule_check_before_conclude | medium | 不一致先多源交叉验证 | 第一批 |
| rule_extract_full_scope | high | 提取前确认完整文件清单 | 第一批 |
| rule_clean_verify_layered | critical | 清洗必须3层验证 | 第一批 |
| rule_delivery_full_audit | critical | 交付前逐文件审查 | 第一批 |
| rule_powershell_escape_triple_lock | critical | PowerShell 转义三层锁 | 第二批 |
| rule_cmd_test_before_run | high | 命令行先试后跑 | 第二批 |
| rule_toolchain_path_verify | high | 工具链路径先验证再使用 | 第三批 |
| rule_encoding_pre_check | high | 文件编码先确认再读 | 第三批 |
| rule_verify_command_exitcode | critical | 命令结果不假设成功 | 第三批 |
| rule_dry_run_before_batch | high | 批量操作前 dry-run | 第三批 |
| rule_tool_selection_fastest | medium | 选最快工具 | 第三批 |

---

## [NEW] 2026-07-10 ???????????

### 14. JSON BOM ???? ? ?JSON???Codex???BOM

**???** hooks.json ? PowerShell Set-Content ?? UTF-8 BOM?Codex Rust JSON ?????????

| ?? | ? |
|:---|:---|
| ??ID | `rule_json_no_bom` |
| ??? | critical |
| ???? | ? JSON ???? .NET ?????Codex/hooks/marketplace? |
| ?? | ??? PowerShell `Set-Content -Encoding UTF8` ? JSON??? Python `json.dump()` |
| ?? | 2026-07-10 hooks.json ???? |

### 15. ?? UI ???? ? ?????? + ????

**???** ??????? UI ??? ? ?? marketplace ????????plugins ?????

| ?? | ? |
|:---|:---|
| ??ID | `rule_plugin_ui_display_requirements` |
| ??? | high |
| ???? | ?????? UI ??? |
| ?? | ??????? `~/.agents/plugins/marketplace.json` ? plugins ???**??** ? `config.toml` ???? `[marketplaces.personal]` |
| ?? | 2026-07-10 ???? UI ??? |

### 16. Windows BOM ???? ? ???????? BOM

**???** 3 ??? .py ???? BOM??? PowerShell ????????????

| ?? | ? |
|:---|:---|
| ??ID | `rule_windows_bom_audit` |
| ??? | high |
| ???? | Windows ?????/?? .py/.json/.ps1 ??? |
| ?? | ??? 3 ????? EF BB BF?????? |
| ?? | 2026-07-10 BOM ???? |

### 17. ??????????? plugin-creator ??

**???** ?? marketplace ????????????????

| ?? | ? |
|:---|:---|
| ??ID | `pat_use_plugin_creator_first_001`?????? |
| ???? | ????/??? |
| ???? | ???? plugin-creator ?????? |
| ?? | 2026-07-10 |

---

## ??????? 17 ??? ? 18 ??? + 6 ??????

| ??ID | ??? | ??? | ???? |
|:---|:---:|:---|:---:|
| rule_word_meaning_confirm | high | ????????? | ??? |
| rule_scope_full_check | high | ???????? | ??? |
| rule_check_before_conclude | high | ?????????? | ??? |
| rule_extract_full_scope | high | ??????????? | ??? |
| rule_clean_verify_layered | critical | ????3??? | ??? |
| rule_delivery_full_audit | critical | ???????? | ??? |
| rule_powershell_escape_triple_lock | critical | PowerShell ????? | ??? |
| rule_cmd_test_before_run | high | ??????? | ??? |
| rule_toolchain_path_verify | high | ??????????? | ??? |
| rule_encoding_pre_check | high | ????????? | ??? |
| rule_verify_command_exitcode | critical | ????????? | ??? |
| rule_dry_run_before_batch | high | ????? dry-run | ??? |
| rule_tool_selection_fastest | medium | ??????????? | ??? |
| rule_json_no_bom | critical | JSON ? Codex ??? BOM | 2026-07-10 |
| rule_plugin_ui_display_requirements | high | ?? UI ? marketplace ?? + ???? | 2026-07-10 |
| rule_windows_bom_audit | high | ????????3?? | 2026-07-10 |
| pat_use_plugin_creator_first_001 | ?? | ????????? | 2026-07-10 |

## [NEW] 2026-07-10 编码安全规则

### 18. 全文件 UTF8 NoBOM 编码规则

**场景：** PowerShell Set-Content / Out-File 默认写入 UTF16-LE 或 UTF8 BOM，
导致 Python/JSON 解析器崩溃、AI 上下文注入乱码、hooks 中文变 ???。
该问题已在 diegin 中发生 **无数次**，涉及 hooks 脚本、config 文件、skills 等全部模块。

| 字段 | 值 |
|:---|:---|
| 规则ID | ule_encoding_no_bom_utf8 |
| 严重度 | critical |
| 触发条件 | 任何文件写入操作（.ps1/.py/.json/.md/.toml） |
| 行为 | 必须用 [System.IO.File]::WriteAllText(path, content, [System.Text.UTF8Encoding]::new(False)) 或 -Encoding UTF8NoBOM；禁止使用 Out-File / Set-Content 无编码参数 |
| 来源 | 2026-07-10 无数次编码损坏事件 |

### 19. 部署前编码三遍审计

**场景：** 每次部署/升级前必须验证所有文本文件编码

| 字段 | 值 |
|:---|:---|
| 规则ID | ule_pre_deploy_encoding_audit |
| 严重度 | critical |
| 触发条件 | 部署/同步/升级前 |
| 行为 | ① 扫描所有 .ps1/.py/.json/.md/.toml → ② 检查 BOM（前3字节 EF BB BF）→ ③ 检查 U+FFFD 替换字符 → ④ 有问题的写入失败清单，全部修复后才能部署 |
| 来源 | 2026-07-10 迭进部署审计"