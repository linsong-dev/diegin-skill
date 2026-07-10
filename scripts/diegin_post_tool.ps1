# 迭进·DGEN PostToolUse 钩子 - 工具使用后处理
$pluginRoot = Split-Path -Parent (Split-Path -Parent $PSCommandPath)
$dieginHome = if ($env:CODEX_HOME) { $env:CODEX_HOME } else { Join-Path $env:USERPROFILE ".codex" }
$auditLog = Join-Path $dieginHome "diegin_audit.log"
$pythonExe = Join-Path $pluginRoot ".venv\Scripts\python.exe"
$enginePy = Join-Path $pluginRoot "engine\call_diegin.py"
$time = Get-Date -Format "yyyy-MM-dd HH:mm:ss.fff"

try { "$time [HOOK:PostToolUse] ACTIVE | root=$pluginRoot" | Add-Content -Path $auditLog -ErrorAction SilentlyContinue } catch {}

try {
    if (Test-Path $pythonExe) {
        $ctxJson = '{"hook":"post_tool","op":"cmd","exit":' + $LASTEXITCODE + ',"time":"' + $time + '"}'
        $null = $ctxJson | & $pythonExe $enginePy check 2>&1
    }
} catch {
    try { "$time [HOOK:PostToolUse] EXCEPTION | $_" | Add-Content -Path $auditLog -ErrorAction SilentlyContinue } catch {}
}
exit 0
