# Changelog · Diegin 迭进

## 3.8.0 (2026-08-10)

- feat: 规则增量发布——守三 +4（image_url critical 复活 / 举一反三 ×2 / staging 派生），攻七 +7（六条 manual + image_url 泛化）
- feat: 迭进钩子契约 v1（M1）——新增 engine/contract.py 契约层（5 标准事件统一信封 + 三态决策 + inject/suggestions），Codex PS1 钩子全部接入契约通道（向后兼容）
- docs: README 产品化数据刷新（3.8.0 / 235 规则 active 41 / 32 测试）
- refactor: 运行版 session_start.ps1 硬编码路径回归修复（$env:USERPROFILE 统一）

## 3.6.6 (2026-08-01)

- 初始产品化版本：八元原则网络 + 引擎 + hooks + Mindol 记忆后端