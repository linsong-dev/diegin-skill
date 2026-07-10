$dieginHome = "$env:USERPROFILE\.codex"
$auditLog = Join-Path $dieginHome "diegin_audit.log"
$time = Get-Date -Format "yyyy-MM-dd HH:mm:ss.fff"
try { "$time [HOOK:PreToolUse] ACTIVE" | Add-Content -Path $auditLog -ErrorAction SilentlyContinue } catch {}
exit 0
