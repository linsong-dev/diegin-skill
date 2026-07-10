# 迭进·DGEN Notify 钩子（简化版）
$pluginRoot = Split-Path -Parent (Split-Path -Parent $PSCommandPath)
$dieginHome = if ($env:CODEX_HOME) { $env:CODEX_HOME } else { Join-Path $env:USERPROFILE ".codex" }
$auditLog = Join-Path $dieginHome "diegin_audit.log"
$time = Get-Date -Format "yyyy-MM-dd HH:mm:ss.fff"
try { "$time [HOOK:Notify] FIRED" | Add-Content -Path $auditLog -ErrorAction SilentlyContinue } catch {}
exit 0
