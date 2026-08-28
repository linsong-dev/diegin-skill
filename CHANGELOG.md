# Changelog · Diegin 迭进

## 3.9.11+ 自照镜报告机制 · L1 前置地基 (2026-08-28)

- feat: 第一批 L1 前置地基落地——自照镜报告落盘（`var/reports/self_mirror_r<round>.md/.json`，保留 30 份，含九章素材/方向校准/状态/L1 挂载点）；P6 影响审计日志（`var/logs/p6_audit.jsonl`，环形 1000 条，记录来源/幅度/方向/后续裁决，运维手册 2.4）
- files: `engine/evo/p6_audit.py`（新增）+ `engine/evo/arbiter.py`（_apply_delta 挂接）+ `engine/evo/self_mirror.py`（_write_report_files）
- 验证: py_compile 通过，test_all.py 33/33 通过；手动验证报告落盘 + p6_audit 追加；四副本同步
- 边界: 仅追加记录，不改变裁决行为；2.7/2.12/2.14 等 L1 机制仍为「待人工确认」，仅预留 l1_pending 挂载点

## 3.9.11+ L2 决策超时熔断 (2026-08-28)

- feat: 运维手册 2.3 决策超时熔断落地——`engine/evo/arbiter.py` resolve() 增加 fast_path 参数（跳过 P6/P4 微调，仅 P0-P3 + 严重度兜底）；`engine/evo/main.py` arbitrate() 增加 fast_path 透传；`engine/call_diegin.py` 衡步骤耗时 >2s 强制 fast_path 重算并覆盖裁决，失败回退沿用完整裁决，审计记录降级与重算结果
- docs: `references/迭进复核报告_2026-08-28.md` 更新 2.3 状态 ⚠️部分 → ✅ 已落地（L2 锚点 22/22）；审计日志追加落地记录
- 范围: L2 数字锚点微调，不涉及 L1；边界声明：L1 九项机制仍为「待人工确认」，未触碰引擎
- 验证: py_compile 通过，test_all.py 33/33 通过

## 3.9.11 (2026-08-27)

- fix: 一二不过三误报链收口——post_tool 错误判定两处修复（P0-20260827）：① stderr/error 字段不再无条件触发 analyze，仅 exit≠0 认定（与 08-25 truncated 豁免同口径，exit 缺失且 stderr 非空仍兼容）；② analyze 结果匹配改精确 `"error":`，消除正常 JSON 输出（含 error_type 字段名）误判
- chore: 系统基线刷新 270/71 → 280/81（含 08-26/27 守三复盘 + 攻七配对合法演化）；模式 22/20 → 47/45
- docs: CHANGELOG 补齐 3.9.7~3.9.10 断档 + 3.9.10+（08-22~08-25 攻七配对/周期治理/审计轮转）历史条目

## 3.9.10+ (2026-08-22 ~ 08-25，未升版)


- feat: 一二不过三教训休眠—唤醒治理——verify_fix 成功后 strike 置 dormant（省 token，不再注入运行上下文）；record_self_error 命中休眠项自动唤醒（复发=新证据）；恒常门教训注入过滤 dormant 项；止观门 deep_review 仍读全量
- feat: 周期治理 P1/P2——一二不过三唤醒重置计数（修复验证后复发=新第 1 次，累计入 lifetime_count）；deep_review 间隔随错误态势自适应（高错误率 6h / 平稳 24h）；攻七成功模式生命周期（active 30 天未触发→deprecating）；裁决律 high 级休眠需人工确认（confirm_dormant 支持确认/驳回）
- feat: P0 攻七先败后成配对闭环——record_error 记录 30 分钟窗口内失败（命令族 + 脱敏）；post_tool_batch 成功时检测同族失败自动生成攻七 staging 模式（auto_pair）；staging 触发计数 tc>=2 自动转 active；入库脱敏（URL 内嵌凭据/gho_ token → <redacted>）
- fix: 审计日志统一轮转治理（8MB/保留 3 份）+ call_diegin 时间戳重复写入（新增 engine/_audit_rotate.py，接入五处写入入口）
- fix: 自述一致性+记忆卫生双防线（九章权威护栏 + 自检 15/16 项）
- docs: 篇三《迭进如何修复了它自己》/ 篇四《DeepSeek 读〈迭进·律令九章〉》三平台发布 + 推广计划书数据对齐 v3.9.10 + KPI 基线建档（2026-08-25）

## 3.9.10 (2026-08-21)

- fix: 归档规则——用户主动归档优先于 paused 保护
- chore: 数据回灌——7 条规则归档至 archive + 成功模式置信度快照 + 规则/模式运行时快照回灌（发布时点一致）
- docs: 质量基线 v3.9.10（249 规则三库一致 / 死规则 0 / 空壳模式 0 / 假证据 0 / 自检 failed_checks 全绿 / test_all 32/32）；篇一文章刷新至 v3.9.10 口径

## 3.9.9 (2026-08-21)

- fix: hooks python 统一优先 venv——修复 Mindol 断连 ModuleNotFoundError；清理 skills/mindol 残留

## 3.9.8 (2026-08-20)

- refactor: state 目录统一——engine/var/state 合并到根 var/state，修复证据链读取分裂（tracker/self_mirror/dashboard）

## 3.9.7 (2026-08-20)

- refactor: 迭进×Mindol 非自包含拆分——移除内置 mindol 副本、venv 独立包接入、checkpush 联动校验（与独立 mindol 插件版本前缀一致）

## 3.9.6 (2026-08-20)
## 3.9.6 (2026-08-20)

- feat: Mindol 情绪调制 + 跨空间联想（PERF-D，对应「带感觉权重、受情绪调制的状态动力学」最小路径）——
  - 情绪调制：Mindol 新增全局 mood 标量 [-1,+1]，pre_reply 入口自动注入自照镜 courage 信号；检索按 mood 调制空间权重（courage 高→trade/pattern/abstract 上调、rule 下调，幅度 ±15%）
  - 跨空间联想：`associate()` 将 trade×pattern×abstract top 候选重组为组合候选（零外部模型），并入预检注入文本
  - 会话级状态连续性：`_get_adapter()` 单例保留 mood（无守护进程，符合省 token 原则）
- test: test_core 新增 mood_modulation / associate 2 项（10/10 通过）

## 3.9.5 (2026-08-20)

- perf: Mindol 记忆治理 PERF-C（该用的用，该省的省）——
  - P1 存量清理：4.2 万 → 1.3 万 active（工具中间日志 dormant 化，可恢复；rule/trade/pattern/user 权威记忆零损失）
  - P2 写入去重：`save_chat` 去 codex 双写（retrieve 全空间覆盖，冗余）；post_tool_batch 两次写合并为单条摘要；pre_tool 裁决写入降频（每 5 次 1 条）——每工具调用新写入 ~5 条 → ~1.2 条
  - P3 每日维护：新增 `engine/mindol_maintenance.py`（分档保留期：工具日志 1 天 / 半对话 3 天 / raw_chat 7 天 / 权威记忆永久）+ Windows 计划任务每日 18:45 + pre_reply 入口阈值防线（active>2 万自动触发）
- fix: 入口防线与维护脚本 UTF-8 审计落盘

## 3.9.4 (2026-08-19)

- perf: 钩子性能 A+B——
  - A：8 钩子日志改 append 追加写 + 超 8MB 自动归档 `.1`（消除逐次整文件读改写，长期膨胀隐患消除）
  - B：post_tool 五段独立进程调用合并为单次 `post_tool_batch`（health / feedback_adopt / record_success / closure_close / mindol×2 / record_evidence），实测 post_tool 全链路 ~8.5s→3.8s（约 55% 提速），并消除 contract.py 双层 subprocess 浪费
  - fix: `health_check` / `auto_sandwich_trigger` 直接 print 污染 stdout（`redirect_stdout` 捕获）；`save_chat` 无 `space_hint` 参数兼容（改 `source="post_tool"`）
  - 保留不动：B1 self_check 变更验证、会话图片清理、generalize / analyze / review 原节奏

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
