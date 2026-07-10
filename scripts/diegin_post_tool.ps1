# ???DGEN PostToolUse ?? - ?????????/????
# ???????detect_failure?+ ???detect_success?

$pluginRoot = "$env:USERPROFILE\plugins\diegin"
$auditLog = Join-Path $pluginRoot "diegin_audit.log"
$pythonExe = Join-Path $pluginRoot ".venv\Scripts\python.exe"
$enginePy = Join-Path $pluginRoot "engine\call_diegin.py"
$time = Get-Date -Format "yyyy-MM-dd HH:mm:ss.fff"

try {
    "$time [HOOK:PostToolUse] ACTIVE" | Add-Content -Path $auditLog -ErrorAction SilentlyContinue
} catch {}

# ?? Python ?????????
try {
    if (Test-Path $pythonExe) {
        $ctxJson = '{"hook":"post_tool","op":"cmd","exit":' + $LASTEXITCODE + ',"time":"' + $time + '"}'
        $null = $ctxJson | & $pythonExe $enginePy post_tool 2>&1
    }
} catch {
    try { "$time [HOOK:PostToolUse] EXCEPTION | $_" | Add-Content -Path $auditLog -ErrorAction SilentlyContinue } catch {}
}
exit 0
