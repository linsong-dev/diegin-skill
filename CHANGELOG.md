# Changelog · Diegin 迭进

## 3.8.1 (2026-08-10)

- feat: 迭进钩子契约 M2——Claude Code 适配器（deploy/adapters/claude-code/）：5 事件映射（SessionStart/UserPromptSubmit/PreToolUse/PostToolUse/Stop+PreCompact）、PreToolUse permissionDecision deny 阻断、additionalContext 注入、settings.json.template、模拟验证 22/22
- docs: VERIFY.md 验证手册（安装/合并 settings/验证点/故障排查）；适配器只进源码库，端到端待真实 Claude 环境
- chore: plugin.json 3.8.1+codex.20260810160952
## 3.8.1 (2026-08-10)

- feat: 迭进钩子契约 M2——Claude Code 适配器（deploy/adapters/claude-code/）：5 事件映射（SessionStart/UserPromptSubmit/PreToolUse/PostToolUse/Stop+PreCompact）、PreToolUse permissionDecision deny 阻断、additionalContext 注入、settings.json.template、模拟验证 22/22
- docs: VERIFY.md 验证手册（安装/合并 settings/验证点/故障排查）；适配器只进源码库，端到端待真实 Claude 环境
- chore: plugin.json 3.8.1+codex.20260810160952
- docs: 产品化 P1——README 实战案例章节 + README.en.md + 版本徽章 3.8.1
- feat: 产品化 P2——领域规则包示例 3 个（deploy/domain-examples/: coding/writing/data-analysis，即插即用 rules.json + 推广级 README）
- docs: AI 自我进化系统白皮书 v1.0（references/whitepaper.md，八元原则方法论 + 真实证据）
- docs: 产品化 P2——社区技术文 2 篇（references/articles/: 《AI 为什么总重复犯错》《迭进 vs LOOP vs 目标模式》+ 索引）
- fix(health): 统一健康口径——total_rules/active_rules 只数拦截规则（新增 success_patterns/total_assets 保留模式视角），与 self_check 对齐（235/41）
## 3.8.0 (2026-08-10)

- feat: 规则增量发布——守三 +4（image_url critical 复活 / 举一反三 ×2 / staging 派生），攻七 +7（六条 manual + image_url 泛化）
- feat: 迭进钩子契约 v1（M1）——新增 engine/contract.py 契约层（5 标准事件统一信封 + 三态决策 + inject/suggestions），Codex PS1 钩子全部接入契约通道（向后兼容）
- docs: README 产品化数据刷新（3.8.0 / 235 规则 active 41 / 32 测试）
- refactor: 运行版 session_start.ps1 硬编码路径回归修复（$env:USERPROFILE 统一）

## 3.6.6 (2026-08-01)

- 初始产品化版本：八元原则网络 + 引擎 + hooks + Mindol 记忆后端