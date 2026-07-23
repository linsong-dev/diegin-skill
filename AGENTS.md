# 迭进 (Diegin) — Agent 使用指南

> 适用于 Codex Agent / 子代理 使用迭进引擎时的指引

## 快速启动

1. 确保迭进引擎已安装（`engine/` 目录完整）
2. 运行 `python engine/test_all.py` 确认引擎正常工作
3. 首次使用时会自动创建种子规则

## 关键接口

### `run_maintenance()`
- **位置**: `engine/evo/main.py`
- **触发**: 定期维护（降权/归档/生命周期/季度证伪）
- **调用示例**:
  ```python
  from main import run_maintenance
  run_maintenance()
  ```

### `auto_sandwich_trigger(task_type, positive, negative)`
- **位置**: `engine/evo/main.py`
- **作用**: 工作完成后自动触发守三攻七复盘
- **调用**: 由 `call_diegin.py` 或外部工具在关键操作完成后调用

### `pace_classify(ctx)` / `should_skip_deep_review(ctx)`
- **位置**: `engine/evo/main.py`
- **作用**: 缓急律任务分类
- **ctx 参数**: `{"task": "...", "task_type": "..."}`

### `closure_open()` / `closure_close()` / `closure_is_closed()`
- **位置**: `engine/evo/main.py`
- **作用**: 止观门认知封存

### `get_vault()` / `evidence_record()`
- **位置**: `engine/evo/main.py`
- **作用**: 去伪存真证据记录

## 配置

配置文件 `engine/config/config.toml` 控制:
- 宕机时段
- 生命周期参数
- 季度证伪开关

## 状态查看

```bash
python engine/diegin_status.py
```

## 测试验证

```bash
python engine/test_all.py
```
