<p align="center">
  <img src="assets/logo.svg" width="200" alt="DGEN">
</p>

<h1 align="center">迭进 · DGEN</h1>

<p align="center">
  <b>AI 全域常驻自我迭代进化系统</b><br>
  让 AI 像人一样从错误中学习，越用越聪明
</p>

<p align="center">
  [![EN](https://img.shields.io/badge/EN-README-blue)](README.en.md) | [![中文](https://img.shields.io/badge/中文-README-red)](README.md) | <a href="https://github.com/linsong-dev/diegin-skill/blob/main/LICENSE">
    <img src="https://img.shields.io/badge/license-Apache%202.0-blue" alt="License">
  </a>
  <img src="https://img.shields.io/badge/version-3.9.2-brightgreen" alt="Version">
  <img src="https://img.shields.io/badge/python-3.12+-orange" alt="Python">
  <img src="https://img.shields.io/badge/Codex-ready-purple" alt="Codex">
</p>

---

## 30 秒看懂迭进

迭进是一个 **AI 操作系统级进化层**。不调任何外部 API，不依赖 GPU，纯 Python 运行。

> 普通 AI：犯过的错下次还可能再犯
>
> 带迭进的 AI：错误自动检测 → 立改加固 → 举一反三 → 不再重犯

## 架构

`
用户操作 → [恒常门·持存] 入口恢复检查（恢复前用户确认）
         → [预策·汇] 汇集输出 + task_id
         → [去伪存真] 验证信息真实性（P0 无条件优先）
         → [守三·轻量] 扫描失败模式（锚定 success_patterns≥4.0）
         → [一二不过三] alerting 警觉落动作（不阻断）
         → [预策·衡] P0-P6 统摄权衡（P3 恒常门恢复优先）
         → 执行操作
            ├─ 成功 → [攻七·行知律] 提炼成功模式 → [举一反三] 语义阈值<0.7 泛化
            └─ 失败 → [一二不过三·三错锁] 立改→加固→升级
         → [止观·完形律] 封存本轮（四态 + 只读快照）
         → [守三·深度] 离线复盘（连续3轮≥2阻断→应急）
         → [自照镜·方向之镜] 自照报告→勇气信号×0.6→P6 静默影响
`

## 核心文件

| 文件 | 作用 |
|:-----|:------|
| engine/evo/main.py | 统一入口 + 定期维护 |
| engine/evo/rule_engine.py | 规则引擎（64 条活跃拦截规则：active 53 + critical 2 + blocking 1 + deprecating 7 + staging 1，另有 archived 183；CRUD + 匹配 + RULE-GUARD 触发写入门） |
| engine/evo/tracker.py | 行为追踪（一二不过三连锁、守三攻七循环） |
| engine/evo/arbiter.py | 预策仲裁器（P0-P6 优先级裁决；P6 调权±0.3/单轮±0.1） |
| engine/evo/pacemaker.py | 缓急律·节奏工具（九章已移除，保留宕机分流/cron） |
| engine/evo/closure.py | 止观·完形律（四态封存 + 只读快照 + 豁免权） |
| engine/evo/evidence_vault.py | 去伪存真证据库 + 季度证伪 + 暂存 50轮/7天 淘汰 |
| engine/evo/error_detector.py | 错误检测 + 一二不过三阻断（警觉落动作 -0.2） |
| engine/evo/constancy.py | 恒常门·持存（task_id 生命周期/嵌套≤3/30天快照） |
| engine/evo/self_mirror.py | 自照镜·方向之镜（勇气信号×0.6/P6 静默影响） |
| engine/evo/dashboard.py | 健康度仪表盘 |
| engine/mindol/ | Mindol 语义记忆引擎 |
| references/whitepaper.md | AI 自我进化系统白皮书 v1.0（律令九章方法论） |

## 律令九章（四律三门一锁一镜）

| 章 | 原则 | 别名 | 方向 | 机制 |
|:-:|:----|:----|:---:|:-----|
| 一 | 攻七 | 行知律 | 进攻 | 试之以行 → 成则炼之 → 通则固之 → 泛而验之 → 废则舍之 |
| 二 | 守三 | 省知律 | 防守 | 失则拆之 → 拆则溯之 → 溯则炼之 → 炼则铭之 → 铭则复战 |
| 三 | 一二不过三 | 三错锁 | 安全阀 | 初犯立改验 → 再犯锁其途 → 三犯剑落下 |
| 四 | 举一反三 | 通变门 | 扩展 | 一法通 → 三法生 → 百法衍 → 验而归真 |
| 五 | 去伪存真 | 真伪门 | 硬地板 | 言必有证 → 证必可验 → 验证为真 |
| 六 | 预策 | 裁决律 | 宪法 | 汇而衡之 → 预而策之 → 决而行之 → 复而平之 |
| 七 | 持存 | 恒常门 | 续接 | 启而探之 → 行而记之 → 断而存之 → 续而接之 |
| 八 | 止观 | 完形律 | 封存 | 事毕则封 → 功过即舍 → 心如明镜 |
| 九 | 自照镜 | 方向之镜 | 照见 | 回望所行 → 静照本心 → 拨云见路 → 笃定前行 |

> **编号为认知顺序；执行优先级以预策律 P0-P6 为准，不受编号顺序影响。**

**运行时主导映射：**

| 预策律分级 | 运行时主导原则 |
|:---|:---|
| P0 真伪 | 去伪存真（假信息不入任何流程） |
| P1 安全 | 一二不过三（阻断优先于强化/泛化；alerting 警觉落动作不阻断） |
| P2 完形 | 止观·完形律（事毕清零，不追加纠错） |
| P3 任务恢复 | 恒常门·持存（恢复信号统一在"衡"中决策，恢复前用户确认） |
| P4 置信 | 攻七 / 守三（置信度高者胜出；警觉落动作对相关模式 -0.2） |
| P5 staging | 举一反三（先经去伪存真验证再激活） |
| P6 语义记忆 | Mindol（调权±0.3/单轮±0.1，含自照镜勇气信号静默影响） |

> **认知顺序用于学习与叙事；运行时主导权由预策律 P0-P6 决定。两个维度不同，互不冲突。**
> **缓急律已从九章移除，降级为宕机时段/批处理的节奏工具（不入 P3）。**

## 攻七强化（v3.8）

验证过的正确做法 → **及时推荐 → 优先选用 → 快速泛化 → 采纳反馈**：

- **及时使用**：`pre_check` 高置信度模式标 priority，工具调用前直接推荐采用
- **优先选用**：仲裁器 P4 同场景加权 +0.5（同工具复用验证过的方法优先于负向纠错）
- **泛化提速**：复用≥2 次或 conf≥4.5 即触发跨域泛化
- **反馈闭环**：工具成功自动采纳（置信度+0.5）；否决 ×0.7
- **质量护栏**：`audit_patterns` / `audit_staging` / `audit_evidence` 防空壳与假数据再生

## 实战案例

- **跨对话任务恢复破冰（2026-08-18 实测）**：恒常门恢复率从 0 完成首次实证——用户一句「恢复 A股模拟盘那个任务」经意图匹配唯一高置信命中（0.760，领先次名 0.286）并自动恢复；v3.9.1 模糊恢复（无 task_id、自然语言恢复）同步上线。
- **跨域实战同日四连（2026-08-18）**：交易模拟盘任务续接、迭进推广立项、微信/Edge 启动崩溃修复（junction 误转内存盘）、ps1 乱码修复——迭进覆盖交易/开发/运维多场景。
- **举一反三 ×2 当日 71/74 次命中、零误伤**：08-09 入库的 2 条跨域泛化规则（`pat_rule_pat_manual_ps1_chinese_bom` / `pat_rule_pat_manual_backup_before_remove`）08-10 即在实战中触发 71/74 次，人工复核 boundary 明确、无误伤，按裁决保留并正式发布。
- **image_url 守三 11 次审计**：同一会话内 view_image 连发触发「一二不过三」，`self_error_image_url` 从 archived 升级 critical 复活，当日 11 次命中全部走 audit（熔断期行为），按计划 ≈08-17 复查，无复发可人工 reset。
- **乱码根因修复**：PS5.1 ↔ Python 管道中文乱码（`$OutputEncoding` 默认 US-ASCII、`[Console]::OutputEncoding` 默认 GBK）导致 prompt 入库变 `?`、pre_reply JSON 解析失败 → 强制 UTF-8 + 质量门正则惰性量词修复；7 个被拒的攻七模式恢复提升，经验沉淀管线卡死闭环。
- **攻七规则当日 auto_adopt**：08-09 入库的攻七规则（`pat_manual_doc_writeback_verify` ×4、`pat_manual_new_tool_smoke` ×1）08-10 实战当日自动采纳（置信度 +0.5），「入库 → 实战 → 采纳」闭环 24 小时内跑通。

## 快速开始
### 环境要求
- Python 3.12+
- Codex 桌面版（v3.0+，26.x 已内置迭进钩子支持）
- PowerShell 5.1+

### 安装
**方式一：一键部署（推荐）**
`powershell
git clone https://github.com/linsong-dev/diegin-skill.git
cd Diegin
powershell -ExecutionPolicy Bypass -File deploy/deploy.ps1
`
一键部署会自动：部署引擎与钩子到 `%USERPROFILE%\.codex\diegin\`、合并钩子配置到 `%USERPROFILE%\.codex\hooks.json`、注册插件。
依赖（numpy）请手动安装：`pip install numpy`。

**方式二：手动安装**
`powershell
git clone https://github.com/linsong-dev/diegin-skill.git
cd Diegin
pip install numpy
`

### 注册钩子（手动方式）
将 `deploy/hooks-template.json` 合并到 `%USERPROFILE%/.codex/hooks.json`（钩子脚本会自动从 `%USERPROFILE%/.codex/diegin/hooks/` 加载），重启 Codex。

### 激活
在 Codex 对话中输入 接入迭进 或 dgen on。

### 验证
`powershell
cd engine
python test_all.py --verbose
`
预期输出：结果: 32/32 通过 (0 失败)

## 快速使用

| 命令 | 效果 |
|:-----|:------|
| 接入迭进 或 dgen on | 激活迭进引擎 |
| 迭进状态 | 查看规则库 / 置信度 / 健康度 |
| 守三攻七复盘 | 负向纠错 + 正向强化 |
| @迭进 | 触发预检，输出原始 JSON |
| dgen feedback <ID> <agree/veto/silent> | 对规则反馈，调整置信度 |

## 配置

`	oml
[pacemaker]
downtime_start = "23:00"
downtime_end   = "06:00"

[evidence_vault]
quarterly_falsification_enabled = true
`

## 项目结构

`
diegin/
├── engine/           Python 引擎
│   ├── call_diegin.py    CLI 入口
│   ├── test_all.py       32 个端到端测试
│   ├── evo/              律令九章引擎（含恒常门/自照镜）
│   └── mindol/           Mindol 语义记忆引擎
├── hooks/             PowerShell 钩子（全域常驻）
├── config/            路由配置
├── assets/            Logo 等资源
├── tests/             测试套件
├── sync.ps1           同步脚本
├── deploy/            部署脚本
└── LICENSE            Apache 2.0
