# 迭进·DGEN Notify 强制执行 - 由 Codex OS级通知机制触发，AI无法绕过
$dieginHome = "$env:USERPROFILE\.codex"
$auditLog = Join-Path $dieginHome "diegin_audit.log"
$stateFile = Join-Path $dieginHome "diegin_state.json"
$time = Get-Date -Format "yyyy-MM-dd HH:mm:ss.fff"

# 记录通知触发
"$time [NOTIFY] turn-ended | 迭进强制执行点" | Add-Content -Path $auditLog

# 写入状态文件供 AI 读取
$state = @{
    last_check = $time
    instruction = "[DGEN] 迭进预检指令 - AI必须遵守守三攻七+一二不过三+举一反三"
    source = "notify"
}
$state | ConvertTo-Json -Compress | Out-File -FilePath $stateFile -Encoding UTF8 -Force

# 输出到 stdout（Codex 可能捕获）
Write-Host "[DGEN] Notify: 迭进强制执行点已触发"
exit 0
