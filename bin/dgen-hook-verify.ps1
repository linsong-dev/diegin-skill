# [DGEN] dgen-hook-verify — 钩子注入健康体检
#   1) PostCompact 是否真实触发（区分隔离探针 vs 真实压缩）
#   2) 行动时刻记忆在 UserPromptSubmit 的投递判定（含 skip_* 归因）
#   3) strip-proxy.log 有无新增「孤儿工具调用」400
#   4) hooks.json 注册 + config.toml 信任状态
# 用法：powershell -NoProfile -ExecutionPolicy Bypass -File .\dgen-hook-verify.ps1 [-Minutes 30]
param([int]$Minutes = 30)

$ErrorActionPreference = 'Continue'
$codexHome  = if ($env:CODEX_HOME) { $env:CODEX_HOME } else { Join-Path $env:USERPROFILE '.codex' }
$dieginRoot = Join-Path $codexHome 'diegin'
$auditLog   = Join-Path $dieginRoot 'var\logs\diegin_audit.log'
$proxyLog   = Join-Path (Split-Path $codexHome -Parent) 'KeySync-Bridge\strip-proxy.log'
if (-not (Test-Path $proxyLog)) { $proxyLog = 'E:\项目\Codex_便携版\KeySync-Bridge\strip-proxy.log' }

$since = (Get-Date).AddMinutes(-1 * $Minutes)
function Emit { param([string]$Tag,[string]$Msg,[string]$Color='Gray') Write-Host ("  [" + $Tag + "] " + $Msg) -ForegroundColor $Color }
function CountOf { param($Lines,[string]$Pat) @($Lines | Where-Object { $_.Line -match $Pat }).Count }

Write-Host ("=== DGEN Hook Verify ===  (window: last " + $Minutes + " min, since " + $since.ToString('yyyy-MM-dd HH:mm:ss') + ")") -ForegroundColor Cyan
Write-Host ("  audit: " + $auditLog)
Write-Host ("  proxy: " + $proxyLog)
Write-Host ""

# ---- 1) PostCompact ----
$pcAll   = @(Select-String -Path $auditLog -Pattern '\[HOOK:PostCompact\]' -ErrorAction SilentlyContinue)
$pcFired = @($pcAll | Where-Object { $_.Line -match 'FIRED' })
$pcReal  = @($pcFired | Where-Object { $_.Line -notmatch 'session=probe' })
Write-Host "-- 1) PostCompact 触发 --" -ForegroundColor White
if ($pcAll.Count -eq 0) {
    Emit 'PENDING' "审计里没有任何 [HOOK:PostCompact] 记录 -> 从未被派发" 'Yellow'
    Emit 'ACTION'  "先重启一次 Codex 让 hooks.json 重载，再触发一次压缩（自动或手动 /compact）" 'Yellow'
} else {
    Emit 'SEEN' ("记录 " + $pcAll.Count + " 条；FIRED " + $pcFired.Count + " 条；其中真实压缩 " + $pcReal.Count + " 条") $(if ($pcReal.Count -gt 0) { 'Green' } else { 'Yellow' })
    $pcAll | Select-Object -Last 4 | ForEach-Object { Write-Host ("      " + $_.Line) -ForegroundColor DarkGray }
}
Write-Host ""

# ---- 2) 行动记忆投递 ----
Write-Host "-- 2) 行动时刻记忆投递（UserPromptSubmit） --" -ForegroundColor White
$am = @(Select-String -Path $auditLog -Pattern '\[HOOK:ACTION-MEMORY\]\[pre_reply\]' -ErrorAction SilentlyContinue)
if ($am.Count -eq 0) {
    Emit 'PENDING' "尚无 pre_reply 记录 -> 该会话未在 UserPromptSubmit 上跑过此特征" 'Yellow'
} else {
    Emit 'STAT' ("deliver=" + (CountOf $am ' deliver ') + " skip_seen=" + (CountOf $am 'skip_seen') +
                 " redeliver_window=" + (CountOf $am 'redeliver_window') + " skip_stale=" + (CountOf $am 'skip_stale') +
                 " session_mismatch=" + (CountOf $am 'skip_session_mismatch') + " no_file=" + (CountOf $am 'skip_no_file') +
                 " no_inject=" + (CountOf $am 'skip_no_inject') + " no_key=" + (CountOf $am 'skip_no_key')) 'Green'
    $am | Select-Object -Last 6 | ForEach-Object { Write-Host ("      " + $_.Line) -ForegroundColor DarkGray }
    if ((CountOf $am 'skip_session_mismatch') -gt 0 -and (CountOf $am ' deliver ') -eq 0) {
        Emit 'HINT' "只有 mismatch：说明 pre_tool 最近一次命中的会话不是当前会话（多会话共用同一 CODEX_HOME 时正常）" 'Yellow'
    }
}
Write-Host ""

# ---- 3) 孤儿 400 ----
Write-Host "-- 3) strip-proxy.log 孤儿工具调用 400 --" -ForegroundColor White
if (Test-Path $proxyLog) {
    $orphan = @(Select-String -Path $proxyLog -Pattern 'No tool output found for tool call' -ErrorAction SilentlyContinue)
    $recent = @($orphan | Where-Object {
        if ($_.Line -match '^(\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2})') {
            ([DateTime]::Parse($Matches[1] + 'Z')).ToLocalTime() -ge $since
        } else { $false }
    })
    Emit 'STAT' ("累计 " + $orphan.Count + " 条；窗口内 " + $recent.Count + " 条") $(if ($recent.Count -eq 0) { 'Green' } else { 'Red' })
    if ($orphan.Count -gt 0) { $orphan | Select-Object -Last 2 | ForEach-Object { Write-Host ("      " + $_.Line) -ForegroundColor DarkGray } }
} else { Emit 'SKIP' "找不到 strip-proxy.log：$proxyLog" 'DarkGray' }
Write-Host ""

# ---- 4) 注册与信任 ----
Write-Host "-- 4) 注册与信任 --" -ForegroundColor White
$hooksJson = Join-Path $codexHome 'hooks.json'
if (Test-Path $hooksJson) {
    $hj = [IO.File]::ReadAllText($hooksJson, [Text.Encoding]::UTF8)
    Emit 'REG' ("PostCompact 已注册 = " + ($hj -match '"PostCompact"')) $(if ($hj -match '"PostCompact"') { 'Green' } else { 'Red' })
} else { Emit 'SKIP' "找不到 hooks.json" 'DarkGray' }
$cfg = Join-Path $codexHome 'config.toml'
if (Test-Path $cfg) {
    $ct = [IO.File]::ReadAllText($cfg, [Text.Encoding]::UTF8)
    $i = $ct.IndexOf("post_compact:0:0']")
    if ($i -ge 0) {
        $win = $ct.Substring($i, [Math]::Min(400, $ct.Length - $i))
        $m = [regex]::Match($win, 'trusted_hash\s*=\s*"([^"]+)"')
        if ($m.Success) { Emit 'TRUST' ("post_compact trusted_hash = " + $m.Groups[1].Value) 'Green' }
        else { Emit 'TRUST' "找到 post_compact 段但没有 trusted_hash" 'Yellow' }
    } else { Emit 'TRUST' "config.toml 无 post_compact 信任条目（UI 里确认钩子已开启）" 'Yellow' }
}
Write-Host ""

Write-Host "=== 判定 ===" -ForegroundColor Cyan
if ($pcReal.Count -eq 0) { Write-Host "  PostCompact：未验证真实压缩（隔离探针不算）" -ForegroundColor Yellow }
else { Write-Host "  PostCompact：已随真实压缩触发" -ForegroundColor Green }
if ((CountOf $am ' deliver ') -gt 0) { Write-Host "  行动时刻记忆：已在回合边界成功投递" -ForegroundColor Green }
else { Write-Host "  行动时刻记忆：本窗口无成功投递（看上面 skip_* 归因）" -ForegroundColor Yellow }
Write-Host "  注入位置：PreToolUse 禁注入 / UserPromptSubmit 主力 / PostToolUse 未实杀" -ForegroundColor DarkGray
Write-Host "  契约依据：references/钩子事件契约与注入位置矩阵_2026-09-13.md" -ForegroundColor DarkGray