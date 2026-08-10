# Coding · 编码质量门规则包（6 条）

> 目标：**坏代码不入库**。覆盖提交、编码、批量操作、审查、部署五个高风险动作。
> 安装与定制见 [总入口](../README.md)。

## 规则明细

| # | 规则 | 严重度 | 触发 | 处置 |
|:-:|:--|:--:|:--|:--|
| 1 | 提交前语法检查 | high | `git commit` / `git push` | 阻断并要求先跑语法检查 |
| 2 | 全文件编码强制 | critical | 写入 py/js/ts/json/md/ps1/toml/yaml | 自动转 UTF-8 NoBOM |
| 3 | 代码审查注释规范 | medium | 生成 code-comment 缺 priority/body | 要求补全字段 |
| 4 | 批量操作前预演 | high | 删除/移动/重命名/批量替换 >3 个文件 | 阻断并要求 dry-run |
| 5 | 禁止 TODO 未解决入库 | medium | commit 含 TODO/FIXME/HACK | 警告并确认 |
| 6 | 部署前测试通过 | critical | 生产部署且测试未跑 | 阻断并强制测试 |

## 为什么是这 6 条

- **入口把关**（1/6）：语法错误与未测代码是「入库即债」的两大来源。
- **编码基线**（2）：UTF-8 NoBOM 是跨平台协作的隐形契约，错误编码会引发中文乱码类连锁故障。
- **安全阀**（4）：批量操作（删除/移动）是 AI 代理最容易造成不可逆破坏的动作。
- **质量信号**（3/5）：审查注释与 TODO 是代码可维护性的最小可测代理。

## 快速试用

```powershell
Copy-Item deploy/domain-examples/coding/rules.json <迭进根>\engine\evo\rules\domain_rules\domain_example_coding.json
```

然后在 Codex 中尝试 `git commit` 未测试代码——迭进预检应命中「部署前测试通过」或「提交前语法检查」并提示。