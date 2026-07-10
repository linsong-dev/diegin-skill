$dieginHome = "$env:USERPROFILE\.codex"
$auditLog = Join-Path $dieginHome "diegin_audit.log"
$reportFile = Join-Path $dieginHome "diegen_compliance.json"
$time = Get-Date -Format "yyyy-MM-dd HH:mm:ss.fff"

try { "$time [HOOK:Stop] ACTIVE" | Add-Content -Path $auditLog -ErrorAction SilentlyContinue } catch {}

try {
    $violations = 0
    $hookCalls = 0
    if (Test-Path $auditLog) {
        $lines = Get-Content $auditLog -ErrorAction SilentlyContinue
        if ($lines) {
            $sessionLines = $lines[-50..-1]
            $violations = ($sessionLines | Where-Object { $_ -match 'BLOCKED' }).Count
            $hookCalls = ($sessionLines | Where-Object { $_ -match '\[HOOK\]' }).Count
        }
    }
    $report = @{
        session_end = $time
        hook_calls = $hookCalls
        violations = $violations
        status = if ($violations -eq 0) { "clean" } else { "violation" }
    }
    $report | ConvertTo-Json -Compress | Out-File -FilePath $reportFile -Encoding UTF8 -Force -ErrorAction SilentlyContinue
} catch {}
exit 0
