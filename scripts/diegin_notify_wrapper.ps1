<#
.SYNOPSIS
    迭进·DGEN Notify Wrapper - OS级强制触发
    由 Codex notify="turn-ended" 机制自动调用，AI 无法绕过
    同时保留 Computer Use 通知功能
#>

# 设置控制台输出编码为 UTF8
$OutputEncoding = [Console]::OutputEncoding = [System.Text.Encoding]::UTF8

$dieginHome = "$env:USERPROFILE\.codex"
$auditLog = Join-Path $dieginHome "diegin_audit.log"
$stateFile = Join-Path $dieginHome "diegin_state.json"
$time = Get-Date -Format "yyyy-MM-dd HH:mm:ss.fff"

# ===== 1. 迭进·DGEN 审计触发 =====
try {
    "$time [NOTIFY] diegin enforce | turn-ended" | Add-Content -Path $auditLog -ErrorAction SilentlyContinue
    $state = @{
        last_notify = $time
        source = "notify"
        instruction = "[DGEN] diegin pre-check: shou-san-gong-qi + yi-er-bu-guo-san + ju-yi-fan-san"
    }
    $state | ConvertTo-Json -Compress | Out-File -FilePath $stateFile -Encoding UTF8 -Force -ErrorAction SilentlyContinue
} catch {
    # 不影响 Computer Use
}

# ===== 2. Computer Use 通知（保留原功能）=====
try {
    $cuExe = "$env:USERPROFILE\AppData\Local\OpenAI\Codex\runtimes\cua_node\1b23c930bdf84ed6\bin\node_modules\@oai\sky\bin\windows\codex-computer-use.exe"
    if (Test-Path $cuExe) {
        Start-Process -FilePath $cuExe -WindowStyle Hidden
    }
} catch {
    # 静默
}

exit 0