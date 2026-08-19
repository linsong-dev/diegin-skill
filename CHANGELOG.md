# Changelog · Diegin 迭进

## 3.9.3 (2026-08-19)

- fix: 桌面版钩子注入——UserPromptSubmit 输出 hookSpecificOutput.additionalContext JSON 信封，注入实测生效（A）
- feat: 恒常门恢复提示三件套——find_by_intent 多候选 + 完成标准/待办前 2 条随恢复提示返回（A2）
- docs: SKILL.md 新增规则 0-1a「任务恢复纪律」+ 版本声明对齐完整终版 v3.9.3（B）
- chore: 版本一致性补全——plugin.json/README 徽章/CHANGELOG 统一 3.9.3；hooks.json 模板化去除个人绝对路径

## 3.9.2 (2026-08-18)

- feat: 恒常门模糊恢复增强——Mindol 语义检索兜底通道（意图匹配 + 多候选）
- docs: 推广 v2 恢复实证——README 实战案例刷新 + 计划书三端状态更新

## 3.9.1 (2026-08-18)

- feat: 恒常门模糊恢复——task_id 缺失时按意图召回候选，恢复率 0 场景兜底

## 3.9.0 (2026-08-12)

- feat: 律令九章全量实施——八元结构重组为九章（四律三门一锁一镜）：
  - 新增持存·恒常门（engine/evo/constancy.py）：task_id 生命周期、四态状态摘要、嵌套≤3层溢出保护（nested_overflow）、30天快照清理、恢复前用户确认（pre_check 入口恢复检查最先执行）
  - 新增自照镜·方向之镜（engine/evo/self_mirror.py）：九原则轨迹自照报告、勇气信号×0.6 半衰期衰减（封顶0.8）、每10轮/每日触发、归档 Mindol codex、P6 静默影响（受±0.1单轮限幅约束）
  - 预策·裁决律升级（engine/evo/arbiter.py）：P6 调权限幅±0.3/单轮±0.1；P3 由缓急律紧急优先改为恒常门任务恢复优先；pre_check 新增「汇」（task_id 生成/复用）与「预」（主动推进检查：连续3轮无输入+无待恢复+staging非空才触发，只读建议不制造伪任务）
  - 止观·完形律升级（engine/evo/closure.py）：状态摘要四态（paused/completed/abandoned/blocked）、执行轨迹只读快照、封存后只读豁免权（export_readonly_snapshot）
  - 守三·省知律：锚定优先级（同场景 success_patterns≥4.0，否则回退 intent_summary）；应急触发（连续3轮内≥2次阻断→强制深度复盘）
  - 一二不过三·三错锁：警觉落动作落地（alerting 不阻断，预策权衡阶段相关模式置信度-0.2）
  - 举一反三·通变门：语义距离阈值（候选与既有 staging 候选余弦相似度≥0.7 判伪泛化，不入 staging）
  - 去伪存真·真伪门：暂存区保留期 50轮/7天（先到者）自动淘汰，外部新证据重置计时器一次
  - 缓急律从九章移除，降级为宕机时段/cron 批处理的节奏工具（不入 P3）
- docs: SKILL.md 九章化（v3.9.0，§一 原则网络 + §二 执行流程）；README/README.en 九章化；plugin.json 3.9.0+codex.20260812124100
- docs: CHANGELOG 3.9.0（本条目）

## 3.8.1 (2026-08-10)

- feat: 迭进钩子契约 M2——Claude Code 适配器（deploy/adapters/claude-code/）：5 事件映射（SessionStart/UserPromptSubmit/PreToolUse/PostToolUse/Stop+PreCompact）、PreToolUse permissionDecision deny 阻断、additionalContext 注入、settings.json.template、模拟验证 22/22
- docs: VERIFY.md 验证手册（安装/合并 settings/验证点/故障排查）；适配器只进源码库，端到端待真实 Claude 环境
- chore: plugin.json 3.8.1+codex.20260810160952
- docs: 产品化 P1——README 实战案例章节 + README.en.md + 版本徽章 3.8.1
- feat: 产品化 P2——领域规则包示例 3 个（deploy/domain-examples/: coding/writing/data-analysis，即插即用 rules.json + 推广级 README）
- docs: AI 自我进化系统白皮书 v1.0（references/whitepaper.md，八元原则方法论 + 真实证据）
- docs: 产品化 P2——社区技术文 2 篇（references/articles/: 《AI 为什么总重复犯错》《迭进 vs LOOP vs 目标模式》+ 索引）
- fix(health): 统一健康口径——total_rules/active_rules 只数拦截规则（新增 success_patterns/total_assets 保留模式视角），与 self_check 对齐（235/41）
- fix(engine): 运行版回灌——攻七建议排序同分按 created_at 新优先（让新沉淀经验更快浮出）
- docs: SKILL.md 版本一致性刷新——v3.8.1/日期、规则口径（235/20/系统级34）、Hooks 契约事件列+Stop、裁决律 P6、路径脱敏 %DEV_ROOT%

## 3.8.0 (2026-08-10)

- feat: 规则增量发布——守三 +4（image_url critical 复活 / 举一反三 ×2 / staging 派生），攻七 +7（六条 manual + image_url 泛化）
- feat: 迭进钩子契约 v1（M1）——新增 engine/contract.py 契约层（5 标准事件统一信封 + 三态决策 + inject/suggestions），Codex PS1 钩子全部接入契约通道（向后兼容）
- docs: README 产品化数据刷新（3.8.0 / 235 规则 active 41 / 32 测试）
- refactor: 运行版 session_start.ps1 硬编码路径回归修复（$env:USERPROFILE 统一）

## 3.6.6 (2026-08-01)

- 初始产品化版本：八元原则网络 + 引擎 + hooks + Mindol 记忆后端