# engine/evo 权威边界（模块专属指令）

> 作用域：`engine/evo/` 全部源码与规则资产。本文件就近约束核心进化引擎；根 AGENTS.md 仍是全域预检规则，两者不冲突，冲突时以根 AGENTS.md 的裁决律/去伪存真为准。

## 1. 规则库 / Mindol 一致性（不可破坏）

- 规则与模式写入后必须保持**双库一致**：`engine/evo/rules/*.json` 与 Mindol 记忆库（264=264 基线）同步，禁止只写一边。
- 全量同步（`_mindol_sync_all`）为**单向归档保护**：旧进程内存覆盖不得复活已归档单元；只允许新增/修改 active 与 staging。
- 归档（archived）单元默认不再注入 pre_check 上下文；如需复活必须走 `_force_reopen` 人工入口（见 §3）。
- 每次规则/模式变更后运行 `diegin_self_check.py`（13 项）确认 `dual_store_consistent` 与 `mindol_rule_units == json_rules`。

## 2. 触发器表达式约束（安全求值器）

- 裸字段引用会被 BareWordToConstant 转字符串常量导致恒 False → 禁止使用上下文不存在的字段名（如 `shell_type`、`op`、`file_write`）。
- `op_contains` 参数是**字面 token**（非字段引用），字段白名单为：`domain`、`error_type`、`op_contains`、`prechecked`；字段名撞名禁止。
- NOT 标准化：触发器一律写 `NOT IN` / `NOT`，求值器自动归一为 `not in` / `not`，不得混用大小写变体。
- 提交规则前必须用 `test_all.py` 的 op_contains 用例（命中/不命中/短 token 拒绝/空参数拒绝/撞名拒绝）验证。

## 3. 人工入口与审计留痕

- `_force_reopen` 是复活 archived 规则/模式的**唯一人工入口**，调用必须写审计日志（`[RULE_ENGINE][AUDIT] _force_reopen pattern=<id> <from_status>-><to_status>`），禁止绕过。
- 一二不过三升级/熔断/override 属于运行态自保护：override 中对应错误类型若在 `strikes_db.json` 已 `fix_status=verified`，自动跳过（72h TTL 残留闭环），不得人为恢复过期 override 阻断。

## 4. 归档护栏

- 删除/归档规则必须保留证据轨迹（pre_ 备份文件或归档记录），禁止静默删除后无痕。
- 死规则（active 超期零触发）应归档而非删除，归档后重生成索引并同步 Mindol。

## 5. 变更流程

- 修改 `engine/evo/` 任何文件后：`test_all.py`（23 项）→ `diegin_self_check.py`（13 项）→ 全绿后才算完成。
- 运行版为权威，改动先落运行版，再经 `sync.ps1` 同步源码库，最后走 checkpush 审推。
