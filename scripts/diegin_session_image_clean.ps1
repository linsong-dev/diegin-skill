# 迭进·DGEN 会话图片保护脚本
# 由 PostToolUse 钩子触发，自动清理 Keysync 不兼容的 input_image 格式
# 不依赖代理，独立运行

param()
$dieginHome = if ($env:CODEX_HOME) { $env:CODEX_HOME } else { "$env:USERPROFILE\.codex" }
$python = "$dieginHome\skills\diegin-skill\python\python.exe"
$fixScript = "$env:USERPROFILE\Documents\Codex\2026-07-09\failed-to-deserialize-the-json-body\outputs\fix_codex_sessions.py"
$auditLog = "$dieginHome\diegin_audit.log"
$time = Get-Date -Format "yyyy-MM-dd HH:mm:ss.fff"

if (-not (Test-Path $python)) { exit 0 }
if (-not (Test-Path $fixScript)) { exit 0 }

# 运行会话图片清理脚本
$result = & $python $fixScript 2>&1 | Out-String

if ($result -match "Fixed") {
    "$time [IMAGE-PROTECT] $($result.Trim())" | Add-Content -Path $auditLog
}

exit 0
