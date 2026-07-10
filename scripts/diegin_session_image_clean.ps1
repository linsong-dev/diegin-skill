# 迭进·DGEN 会话图片保护脚本
# 由 PostToolUse 钩子触发，自动清理 Keysync 不兼容的 input_image 格式
# 不依赖代理，独立运行
param()
$pluginRoot = Split-Path -Parent (Split-Path -Parent $PSCommandPath)
$dieginHome = if ($env:CODEX_HOME) { $env:CODEX_HOME } else { Join-Path $env:USERPROFILE ".codex" }
$auditLog = Join-Path $dieginHome "diegin_audit.log"
$time = Get-Date -Format "yyyy-MM-dd HH:mm:ss.fff"

# 尝试查找会话图片清理脚本（与插件同目录）
$fixScript = Join-Path $pluginRoot "scripts\fix_codex_sessions.py"
if (-not (Test-Path $fixScript)) {
    # 后备：从工作区查找最近的 fix 脚本
    $found = Get-ChildItem -Path $dieginHome -Recurse -Filter "fix_codex_sessions.py" -ErrorAction SilentlyContinue | Select-Object -First 1
    if ($found) { $fixScript = $found.FullName }
}
if (-not (Test-Path $fixScript)) { exit 0 }

# 查找 python
$python = Join-Path $pluginRoot ".venv\Scripts\python.exe"
if (-not (Test-Path $python)) {
    $python = Get-Command python -ErrorAction SilentlyContinue | Select-Object -ExpandProperty Source
    if (-not $python) { exit 0 }
}

# 运行会话图片清理脚本
$result = & $python $fixScript 2>&1 | Out-String
if ($result -match "Fixed") {
    "$time [IMAGE-PROTECT] $($result.Trim())" | Add-Content -Path $auditLog
}
exit 0
