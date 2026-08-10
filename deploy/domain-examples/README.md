# 领域规则包示例（Domain Rule Packs）

> 迭进（Diegin）的**领域规则是即插即用**的：每包一个 `rules.json`，复制进
> `engine/evo/rules/domain_rules/` 即可生效，无需改引擎代码。
> 本目录是 3 个对外示例包（与引擎内置规则同源，`example_` 前缀避免 ID 冲突）。

## 包一览

| 包 | 规则数 | 解决什么 | 典型规则 |
|:--|:--:|:--|:--|
| [coding](coding/) | 6 | 代码质量门：坏代码不入库 | 提交前语法检查 / UTF-8 NoBOM 强制 / 批量操作 dry-run |
| [writing](writing/) | 4 | 文档质量：引用可验证、术语一致 | 术语一致性 / 链接可访问性验证 / 章节层级规范 |
| [data-analysis](data-analysis/) | 4 | 数据诚信：结论可溯源、计算可复现 | 数据来源标注 / 异常值说明 / 计算公式可复现 |

## 安装（任选其一）

### A. 直接启用（推荐，最简单）

把 `rules.json` 内容合并进迭进实例的领域规则目录：

```powershell
# 示例：启用 coding 包
Copy-Item deploy/domain-examples/coding/rules.json <迭进根>\engine\evo\rules\domain_rules\domain_example_coding.json
```

重启迭进引擎（或下轮 `迭进状态` 自动加载），验证：

```powershell
python engine/diegin_self_check.py   # 预期：无 bareword 恒真、无乱码
python engine/test_all.py            # 32/32 回归通过
```

### B. 只借用规则（不装引擎）

直接打开各包的 `rules.json`，把规则结构（`trigger_condition` / `action` / `severity` / `tags`）
作为你自己 Agent 的护栏设计参考——字段即契约。

## 定制指南

- **调强度**：改 `severity`（`low` / `medium` / `high` / `critical`）；`critical` 会走硬阻断。
- **调触发**：`trigger_condition` 是布尔表达式，支持 `op ==` / `ext IN (...)` / `reply_contains(...)` 等，
  可参考内置规则写法扩展。
- **调处置**：`action` 支持 `block_execution` / `warn_and_confirm` / `auto_fix_*` / `require_*`。
- **加字段**：`logic.detect` / `logic.expected` 会被迭进审计日志引用，建议保留。
- **规则 ID**：保持 `example_` 前缀避免与内置 `domain_` / 自动学习规则冲突；改了 ID 记得同步 `source`。

## 与引擎内置规则的关系

- 本目录规则与 `engine/evo/rules/domain_rules/` 同源（2026-07-19 领域基线）。
- 差异：ID 前缀（`example_` vs `domain_`）+ `source` 标注（`example:*`）。
- 内置规则已随迭进引擎发布并持续演进；示例包用于对外分发、教学与独立复用。