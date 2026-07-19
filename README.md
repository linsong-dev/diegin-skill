# diegin·DGEN — AI 全域常驻自我迭代进化系统

> 守三攻七 + 一二不过三 + 举一反三 + 去伪存真 — 让 AI 从每次交互中自我进化

---

## 核心原理

**让每个 AI Agent 都具备自我纠错、自我强化、自我记忆、自我进化的能力。**
不绑定任何模型、平台或业务场景，通过系统级规则使 AI 在每次回复前自动执行迭进预检。

---

## 核心特性

| 原则 | 含义 | 触发条件 | 执行方式 |
|:---|:---|:---|:---|
| 守三（负向纠错） | 拆解自己→找出不足→对比提炼→总结改进 | 每次回复前 | 写入固化→触发执行 |
| 攻七（正向强化） | 识别优势→复盘成功→提炼模式→主动写入 | 成功案例后 | 验证→迭代微调 |
| 一二不过三（兜底线） | 第1次→建规则；第2次→加固；第3次→通知用户 | 同类错误 | 自动升级处理 |
| 举一反三（跨域泛化） | 从单条规则推导跨场景通用候选规则 | 新规则入库时 | 自动推导泛化 |

---

## 接入方式

### 方式 A：纯 Markdown（推荐 · 零依赖 · 30 秒生效）

告诉你的 AI：

```
你已启用 迭进·DGEN 系统。请阅读 SKILL.md 中全部规则，每次回复前执行[DGEN]预检。
```

适用于 **Codex / Claude / ChatGPT / 任何 AI Agent**。

### 方式 B：Python 引擎（完整功能）

```bash
cd engine && uv run python call_diegin.py activate
uv run python call_diegin.py check   # 测试规则匹配
```

### 方式 C：自动进化循环（推荐）

```bash
python scripts/dgen_evolve.py   # 创建健康度基线，开始自动闭环
```

---

## 进化工作流

遵循**"观察 → 建议 → 确认 → 写入 → 追踪"**闭环：

```
dgen_evolve.py → 自动观察 → 自动提议 → 用户确认 → 写入规则 → trail 追踪
```

启动方式：
```bash
python scripts/dgen_evolve.py
```

---

## 领域规则

在 `engine/evo/rules/domain_rules/` 下创建 JSON 文件，引擎自动发现加载。

---

## 项目结构

```
diegin-skill/
├── SKILL.md                核心技能定义
├── README.md               本文档
├── engine/                 Python 迭进引擎
│   └── evo/rules/
│       ├── interception_rules.json  83 条系统级拦截规则（含5条种子+50条系统+28条泛化候选）
│       ├── success_patterns.json     9 条系统级成功模式（含攻七自动化记录）
│       └── domain_rules/            你的领域规则包
├── scripts/                自动化脚本
├── workspace/              运行时模板
├── plugin/                 Codex 插件
└── config/                 配置文件
```

---

## 许可

Apache 2.0 — 自由使用、修改、分发（保留版权声明）。

## 安装

### 方式 A：作为 Codex Skill 安装

```powershell
# 克隆仓库
git clone https://github.com/linsong-dev/diegin-skill.git
# 或直接复制到 skills 目录
copy-item -Path S:\diegin-skill -Destination $env:USERPROFILE\.codex\skills\diegin-skill -Recurse -Force
```

### 方式 B：作为 Codex Plugin 安装

在 Codex 设置 → 插件 → 个人市场 → 安装迭进·DGEN 插件。

### 依赖

Python 3.12+，需要以下包：
- requests (GitHub API)
- websocket-client (CDP 桥接)

```powershell
pip install -r requirements.txt
```


