# 迭进·DGEN SessionStart 钩子 - 会话启动/恢复时初始化迭进状态
# 由 Codex 运行时自动触发，AI 无法绕过

$pluginRoot = Split-Path -Parent (Split-Path -Parent $PSCommandPath)
$dieginHome = if ($env:CODEX_HOME) { $env:CODEX_HOME } else { Join-Path $env:USERPROFILE ".codex" }
$auditLog = Join-Path $dieginHome "diegin_audit.log"
$stateFile = Join-Path $dieginHome "diegin_state.json"
$time = Get-Date -Format "yyyy-MM-dd HH:mm:ss.fff"

try {
    "$time [HOOK:SessionStart] ACTIVE | root=$pluginRoot" | Add-Content -Path $auditLog -ErrorAction SilentlyContinue
    # 写入状态：迭进已激活
    $state = @{
        started_at = $time
        status = "active"
        version = "3.0.0"
        root = $pluginRoot
    }
    $state | ConvertTo-Json -Compress | Out-File -FilePath $stateFile -Encoding UTF8 -Force -ErrorAction SilentlyContinue
    # 输出激活标记注入 AI 上下文
@"
[DGEN] ⚡ 迭进·DGEN 引擎已激活
- 规则库: 拦截规则 + 成功模式
- 每次回复开头必须输出 [DGEN] 标记
"@
} catch {
    try { "$time [HOOK:SessionStart] ERR | $_" | Add-Content -Path $auditLog -ErrorAction SilentlyContinue } catch {}
}
exit 0
