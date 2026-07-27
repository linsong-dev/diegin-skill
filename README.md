# 迭进 (Diegin) — AI 全域常驻自我迭代进化系统

> 版本: v3.4.0 | 最后更新: 2026-07-22

## 概述

迭进是一个基于八元原则网络的 AI 自我进化系统。它使用八条元原则（守三、攻七、一二不过三、举一反三、去伪存真、裁决律、缓急律、止观门）构成互联网络，使 AI 具备自主纠错、自主强化、自主记忆、自主进化的能力。

## 架构

```
┌─────────────────────────────────────────────────────────┐
│                    迭进引擎 (Diegin)                       │
├─────────────────────────────────────────────────────────┤
│  ┌─────────┐  ┌─────────┐  ┌──────────┐  ┌──────────┐  │
│  │ 守三     │  │ 攻七     │  │一二不过三│  │举一反三   │  │
│  │(负向纠错)│  │(正向强化)│  │(三错锁)  │  │(跨域泛化) │  │
│  └────┬────┘  └────┬────┘  └────┬─────┘  └────┬─────┘  │
│       │            │            │             │         │
│  ┌────▼────────────▼────────────▼─────────────▼─────┐  │
│  │              仲裁器 (Arbiter)                      │  │
│  │  裁决律(P0) > 一二不过三(P1) > 止观门(P2) > ...    │  │
│  └────────────────────┬──────────────────────────────┘  │
│                       │                                 │
│  ┌────────────────────▼──────────────────────────────┐  │
│  │         去伪存真 (EvidenceVault)                    │  │
│  │         验证门 · 季度证伪                           │  │
│  └────────────────────┬──────────────────────────────┘  │
│                       │                                 │
│  ┌────────────────────▼──────────────────────────────┐  │
│  │         缓急律 (PaceMaker) · 止观门 (Closure)      │  │
│  │         宕机时段 · 生命周期管理                     │  │
│  └───────────────────────────────────────────────────┘  │
├─────────────────────────────────────────────────────────┤
│  记忆层: Mindol (内存+SQLite 权威) ←→ JSON (人类可读副本)  │
├─────────────────────────────────────────────────────────┤
│  配置: engine/config/config.toml                          │
└─────────────────────────────────────────────────────────┘
```

## 核心文件

| 文件 | 作用 |
|:-----|:------|
| `engine/evo/main.py` | 统一入口 + run_maintenance 定期维护 |
| `engine/evo/rule_engine.py` | 规则引擎（CRUD + 匹配） |
| `engine/evo/tracker.py` | 行为追踪器（守三/攻七循环、一二不过三连锁） |
| `engine/evo/arbiter.py` | 仲裁器（P0-P5 优先级裁决） |
| `engine/evo/pacemaker.py` | 缓急律调度器（宕机时段） |
| `engine/evo/closure.py` | 止观门（认知封存） |
| `engine/evo/evidence_vault.py` | 去伪存真证据库 + 季度证伪 |
| `engine/evo/error_detector.py` | 错误检测 + 一二不过三阻断 |
| `engine/evo/dashboard.py` | 健康度仪表盘 |
| `engine/mindol/` | Mindol 语义记忆引擎 |

## 配置

参见 `engine/config/config.toml`:

```toml
[pacemaker]
downtime_start = "23:00"
downtime_end   = "06:00"

[maintenance]
cached_max_age_days = 30

[evidence_vault]
quarterly_falsification_enabled = true
```

## 测试

```bash
python engine/test_all.py
```

## 八元原则

| 原则 | 方向 | 机制 |
|:---|:---:|:---|
| 0:裁决律 | 仲裁 | 真伪至上→生存优先→完形封存 |
| 1:守三 | 防守 | 观不足→省其因→正其行 |
| 2:攻七 | 进攻 | 识长处→炼精华→固其用 |
| 3:一二不过三 | 安全阀 | 错立改·改毕验·不过三 |
| 4:举一反三 | 扩展 | 举一→反三→通百→回归校验 |
| 5:去伪存真 | 硬地板 | 言必有证→证必可验→验证为真 + 季度证伪 |
| 6:缓急律 | 节奏 | 急务求效→缓务求真→张弛有度 + config.toml 宕机时段 |
| 7:止观门 | 封存 | 事毕封存→投入清零→不恋战 |


## 安装指南

### 前置依赖
- **Python 3.12+**（引擎运行必需）
- **PowerShell 5.1+**（钩子脚本必需）
- **Codex** （桌面版，v2.0+）

### 快速安装

1. 确保 `%CODEX_HOME%` 环境变量已设置（通常为 `.codex` 目录）
2. 将 `diegin/` 文件夹放入 `%CODEX_HOME%/` 下
3. 执行同步脚本：
   ```powershell
   cd %CODEX_HOME%/diegin
   .\sync.ps1 check    # 检查差异
   .\sync.ps1 sync-all # 同步全部
   ```
4. 将 `config/hooks.json` 注册到 Codex 的 hooks 系统：
   - 把文件中 `%CODEX_HOME%` 替换为实际路径
   - 内容合并到 `%CODEX_HOME%/hooks.json`
5. 重启 Codex，迭进引擎将随会话自动启动

### 环境变量

| 变量 | 说明 | 示例 |
|:---|:---|:---|
| `CODEX_HOME` | Codex 安装根目录 | `%CODEX_HOME%\.codex` |

### 验证安装

```powershell
cd %CODEX_HOME%/diegin/engine
python call_diegin.py health
python test_all.py --verbose
```

---

## 快速使用

| 命令 | 效果 |
|:---|:---|
| `接入迭进` 或 `dgen on` | 激活迭进引擎 |
| `迭进状态` | 查看规则库/置信度/健康度 |
| `守三攻七复盘` | 执行负向纠错 + 正向强化 |
| `@迭进` | 触发预检，输出原始 JSON |
| `dgen feedback <ID> <agree/veto/silent>` | 对规则反馈，调整置信度 |

---

## 项目结构

```
diegin/
├── engine/               # Python 引擎
│   ├── call_diegin.py    # CLI 入口（审查/审计/健康检查）
│   ├── test_all.py       # 端到端测试
│   ├── evo/              # 八元原则引擎
│   │   ├── main.py       # 统一入口
│   │   ├── rule_engine.py# 规则引擎
│   │   ├── arbiter.py    # 仲裁器
│   │   ├── tracker.py    # 行为追踪
│   │   ├── pacemaker.py  # 缓急律
│   │   └── closure.py    # 止观门
│   └── mindol/           # 语义记忆引擎
├── hooks/                # PowerShell 钩子脚本
├── config/               # 路由配置
├── var/                  # 运行时状态
│   ├── state/            # strikes_db, override 等
│   └── logs/             # 审计日志
├── bin/.venv/            # Python 虚拟环境
├── sync.ps1              # 同步脚本
├── README.md             # 本文档
└── LICENSE               # MIT 协议
```

## 交付物清单

| 文件/目录 | 说明 | 必须 |
|:---|:---|:---:|
| `engine/` | Python 引擎代码 | ✅ |
| `hooks/` | PowerShell 钩子脚本 | ✅ |
| `config/hooks.json` | 路由模板（部署时替换 %CODEX_HOME%） | ✅ |
| `var/state/` | 运行时状态（首次运行自动生成） | ✅ |
| `bin/.venv/` | Python 虚拟环境（含依赖） | ✅ |
| `sync.ps1` | 同步脚本 | ✅ |
| `SKILL.md` | Codex 技能描述 | ✅ |
| `README.md` | 文档 | ✅ |
| `LICENSE` | MIT 协议 | ✅ |
| `.codex-plugin/plugin.json` | 插件清单 | ✅ |
