$script:utf8NoBOM = [System.Text.UTF8Encoding]::new($false)
# [2026-08-09] 中文传输加固：PS5.1 默认 $OutputEncoding=ASCII/控制台GBK 会破坏管道中文
# → 强制 UTF-8，保证 PS->Python stdin / Python stdout->PS 均无损（防 prompt 入库乱码、pre_reply JSON 解析失败）
try { $OutputEncoding = $script:utf8NoBOM } catch {}
try { [Console]::OutputEncoding = $script:utf8NoBOM } catch {}

function Write-AtomicFile {
    param([string]$Path,[string]$Content)
    # [C2] 原子写：tmp+Replace(真实备份) 防读半截；失败兜底 Delete+Move；任何情况清理 tmp 防残留
    $tmp = $Path + ".tmp_" + [System.Guid]::NewGuid().ToString("N")
    $bak = $Path + ".bak"
    [System.IO.File]::WriteAllText($tmp, $Content, $script:utf8NoBOM)
    $ok = $false
    try {
        if ([System.IO.File]::Exists($Path)) {
            [System.IO.File]::Replace($tmp, $Path, $bak)
            if ([System.IO.File]::Exists($bak)) { [System.IO.File]::Delete($bak) }
        } else {
            [System.IO.File]::Move($tmp, $Path)
        }
        $ok = $true
    } catch {
        # 兜底：非原子但保证不失败不残留
        if ([System.IO.File]::Exists($Path)) { [System.IO.File]::Delete($Path) }
        [System.IO.File]::Move($tmp, $Path)
        $ok = $true
    }
    if ([System.IO.File]::Exists($tmp)) { [System.IO.File]::Delete($tmp) }
}

function Add-NoBOMLog {
    param([string]$Path,[string]$Message)
    $ts=Get-Date -Format "yyyy-MM-dd HH:mm:ss.fff"
    $d=Split-Path $Path -Parent
    if($d -and -not(Test-Path $d)){New-Item $d -Force|Out-Null}
    $mtx = New-Object System.Threading.Mutex($false, "Global\DieginLogMutex")
    $mtx.WaitOne(5000) | Out-Null
    try {
        # [PERF] append 追加写，不再整文件读改写
        # [PERF] 超 8MB 自动归档为 .1，防止单文件无限膨胀
        if(Test-Path $Path){
            $len=(Get-Item $Path).Length
            if($len -gt 8388608){
                $arc = $Path + ".1"
                if(Test-Path $arc){Remove-Item $arc -Force}
                Move-Item $Path $arc -Force
            }
        }
        [System.IO.File]::AppendAllText($Path,"$ts $Message`r`n",$script:utf8NoBOM)
    } finally {
        $mtx.ReleaseMutex()
    }
}

function Write-PhaseState {
    param([string]$Phase,[string]$Status,[hashtable]$Data=@{})
    $d=Split-Path $g_sf -Parent
    if(-not(Test-Path $d)){New-Item $d -Force|Out-Null}
    $s=$null
    if(Test-Path $g_sf){try{$r=[System.IO.File]::ReadAllText($g_sf,$script:utf8NoBOM);$s=$r|ConvertFrom-Json}catch{}}
    if(-not$s){$s=[PSCustomObject]@{session_id="";phases=[PSCustomObject]@{};last_update=""}}
    if(-not$s.phases){$s|Add-Member NoteProperty "phases" ([PSCustomObject]@{}) -Force}
    $o=[PSCustomObject]@{ts=(Get-Date -Format "o");status=$Status}
    $Data.Keys|ForEach-Object{$o|Add-Member NoteProperty $_ $Data[$_] -Force}
    $s.phases|Add-Member NoteProperty $Phase $o -Force
    $s.last_update=(Get-Date -Format "o")
    Write-AtomicFile -Path $g_sf -Content ($s|ConvertTo-Json -Depth 5)
}

$g_scriptDir = if ($PSCommandPath) { Split-Path $PSCommandPath -Parent } else { $null }
$g_pluginRoot = if ($g_scriptDir) { Split-Path $g_scriptDir -Parent } else { $null }
$g_fallback_root = if ($g_pluginRoot) { $g_pluginRoot } else { $env:CODEX_HOME + "\diegin" }
$g_psPath = $PSCommandPath
if ([string]::IsNullOrEmpty($g_psPath)) { $g_psPath = Join-Path $g_fallback_root "hooks\diegin_pre_reply.ps1" }
$g_pr = Split-Path -Parent (Split-Path -Parent $g_psPath)
if ([string]::IsNullOrEmpty($g_pr)) { $g_pr = $g_fallback_root }

$g_sf=Join-Path $g_pr "var\state\phase_state.json"
$auditLog = Join-Path $g_pr "var\logs\diegin_audit.log"
$time = Get-Date -Format "yyyy-MM-dd HH:mm:ss.fff"
$pythonExe = $env:DGEN_PYTHON; if (-not $pythonExe) { $pythonExe = Join-Path $g_pr "bin\.venv\Scripts\python.exe"; if (-not (Test-Path $pythonExe)) { $pythonExe = "$env:USERPROFILE\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe" } }
$enginePy = Join-Path $g_pr "engine\call_diegin.py"
$stateDir = Join-Path $g_pr "var\state"
# [2026-09-13 去重解耦] 行动记忆同一 key 的重投时间窗（分钟）。
# 原设计「同 key 一次即永久跳过」，其解除完全依赖 PostCompact 清除闸门文件；
# 若压缩未发生（或 PostCompact 未触发），该特征会被永久压制。改为时间窗后，
# 投递不再依赖任何压缩事件，同时对短间隔重复仍保持静默。
$script:ActionMemoryRedeliverMin = 10
# [行动时刻记忆迁移 2026-09-13] 原挂 PreToolUse：其 additionalContext 会被平台插成 developer
# 消息并落在 function_call 与 function_call_output 之间 → 上游 400 "No tool output found
# for tool call ..."，整轮中断（当日实测 21 次）。现改为在 UserPromptSubmit（回合边界）投递：
# 内容取自 action_memory_last.json（由 diegin_pre_tool.ps1 在「有命中」时写入最近一次非空行动记忆；
# 不用 pre_tool_inject_cache.json——后者无命中即清空，会导致本特征在多数轮次消失）。
# 去重：同会话同 inject_key 只投递一次（规则集变化才再投递）；超 30 分钟视为陈旧不投递。
function Get-ActionMemoryInjection {
    param([string]$SessionId)
    if (-not $SessionId) { Add-NoBOMLog -Path $auditLog -Message "$time [HOOK:ACTION-MEMORY][pre_reply] skip_no_session"; return "" }
    try {
        $cacheFile = Join-Path $stateDir "action_memory_last.json"
        if (-not (Test-Path $cacheFile)) { Add-NoBOMLog -Path $auditLog -Message "$time [HOOK:ACTION-MEMORY][pre_reply] skip_no_file"; return "" }
        $ic = Get-Content $cacheFile -Raw -Encoding UTF8 | ConvertFrom-Json
        if (-not $ic -or -not $ic.inject) { Add-NoBOMLog -Path $auditLog -Message "$time [HOOK:ACTION-MEMORY][pre_reply] skip_no_inject"; return "" }
        if ($ic.session_id -ne $SessionId) { Add-NoBOMLog -Path $auditLog -Message "$time [HOOK:ACTION-MEMORY][pre_reply] skip_session_mismatch file_sid=$($ic.session_id) call_sid=$SessionId"; return "" }
        $key = [string]$ic.inject_key
        if (-not $key) { Add-NoBOMLog -Path $auditLog -Message "$time [HOOK:ACTION-MEMORY][pre_reply] skip_no_key"; return "" }
        try {
            $age = (Get-Date) - [DateTime]::Parse($ic.ts)
            if ($age.TotalMinutes -gt 30) {
                Add-NoBOMLog -Path $auditLog -Message "$time [HOOK:ACTION-MEMORY][pre_reply] skip_stale age_min=$([int]$age.TotalMinutes)"
                return ""
            }
        } catch {}
        $seenFile = Join-Path $stateDir "pre_reply_action_memory_seen.json"
        $seenKey = ""
        $seenTs = ""
        try {
            if (Test-Path $seenFile) {
                $sj = Get-Content $seenFile -Raw -Encoding UTF8 | ConvertFrom-Json
                if ($sj -and $sj.session_id -eq $SessionId) { $seenKey = [string]$sj.key; if ($sj.ts) { $seenTs = [string]$sj.ts } }
            }
        } catch {}
        if ($key -eq $seenKey) {
            $redeliver = $false
            if ($seenTs) {
                try { if (((Get-Date) - [DateTime]::Parse($seenTs)).TotalMinutes -ge $script:ActionMemoryRedeliverMin) { $redeliver = $true } } catch {}
            }
            if (-not $redeliver) {
                Add-NoBOMLog -Path $auditLog -Message "$time [HOOK:ACTION-MEMORY][pre_reply] skip_seen key=$key"
                return ""
            }
            $ageMin = -1; try { $ageMin = [int]((Get-Date) - [DateTime]::Parse($seenTs)).TotalMinutes } catch {}
            Add-NoBOMLog -Path $auditLog -Message "$time [HOOK:ACTION-MEMORY][pre_reply] redeliver_window key=$key seen_age_min=$ageMin"
        }
        try {
            $rec = @{session_id=$SessionId; key=$key; ts=(Get-Date -Format "o")}
            Write-AtomicFile -Path $seenFile -Content ($rec | ConvertTo-Json -Compress)
        } catch { Add-NoBOMLog -Path $auditLog -Message "$time [HOOK:ACTION-MEMORY][pre_reply] seen_write_error=$($_.Exception.Message)" }
        $amLen = ([string]$ic.inject).Length
        Add-NoBOMLog -Path $auditLog -Message "$time [HOOK:ACTION-MEMORY][pre_reply] deliver key=$key len=$amLen"
        return [string]$ic.inject
    } catch {
        Add-NoBOMLog -Path $auditLog -Message "$time [HOOK:ACTION-MEMORY][pre_reply] error=$($_.Exception.Message)"
        return ""
    }
}

Add-NoBOMLog -Path $auditLog -Message "$time [HOOK:UserPromptSubmit] FIRED"

# [PERF-C 2026-08-20] Shalou 入口阈值防线：每日一次检查 active>20000 → 触发维护（防再膨胀）
try {
    $maintCheckFile = Join-Path $stateDir "shalou_active_check.txt"
    $today = (Get-Date).ToString("yyyy-MM-dd")
    $needCheck = $true
    if (Test-Path $maintCheckFile) {
        $lastCheck = (Get-Content $maintCheckFile -Raw -ErrorAction SilentlyContinue).Trim()
        if ($lastCheck -eq $today) { $needCheck = $false }
    }
    if ($needCheck) {
        $maintPy = Join-Path $g_pr "engine\shalou_maintenance.py"
        $maintOut = & $pythonExe $maintPy --dry-run 2>&1 | Out-String
        [System.IO.File]::WriteAllText($maintCheckFile, $today, $script:utf8NoBOM)
        if ($maintOut -match "active_total=(\d+)") {
            $mActive = [int]$Matches[1]
            Add-NoBOMLog -Path $auditLog -Message "$time [SHALOU-MAINT] entry_check active=$mActive"
            if ($mActive -gt 20000) {
                Add-NoBOMLog -Path $auditLog -Message "$time [SHALOU-MAINT] THRESHOLD_HIT active=$mActive -> trigger apply"
                & $pythonExe $maintPy --apply 2>&1 | Out-Null
            }
        }
    }
} catch {
    Add-NoBOMLog -Path $auditLog -Message "$time [SHALOU-MAINT] entry_check_error=$($_.Exception.Message)"
}

# 一二不过三：读阻断文件
$overrideFile = Join-Path $stateDir "dgen_override.json"
$blockedType = ""
$now = Get-Date
$overrideTTL = [TimeSpan]::FromHours(72)
if (Test-Path $overrideFile) {
    try {
        $override = Get-Content $overrideFile -Raw -Encoding UTF8 | ConvertFrom-Json
        $blockedType = $override.blocked_error_type
        if ($blockedType -and $override.blocked_at) {
            try {
                $blockedAt = [DateTime]::ParseExact($override.blocked_at, "o", $null)
                $age = $now - $blockedAt
                if ($age -gt $overrideTTL) {
                    $nullJson = @{blocked_error_type="";strike_count=0;blocked_at=$null;last_detail="";decision="allow"} | ConvertTo-Json
                    [System.IO.File]::WriteAllText($overrideFile, $nullJson, $script:utf8NoBOM)
                    $blockedType = ""
                }
            } catch {}
        }
    } catch {}
}
if ($blockedType) {
    $strikeCount = 0
    $reason = ""
    try { $strikeCount = $override.strike_count; $reason = $override.reason } catch {}
    Add-NoBOMLog -Path $auditLog -Message "$time [HOOK:OVERRIDE] BLOCK prompt type=$blockedType strike=$strikeCount"
    Write-Output ""
    Write-Output "⚠️ [迭进] 收到阻断请求 | 类型: $blockedType（已触发 ${strikeCount}次）"
    if ($reason) { Write-Output "   原因: $reason" }
    Write-Output ""
    Write-PhaseState -Phase "pre_reply" -Status "override_blocked"
    exit 1
}

function Write-PreReplyEngineError {
    param([string]$Detail,[string]$UserMessage)
    Add-NoBOMLog -Path $auditLog -Message "$time [HOOK:DGEN-ENGINE-ERROR] $Detail"
    Write-PhaseState -Phase "pre_reply" -Status "engine_error" -Data @{ts=(Get-Date -Format "o")}
    $script:preReplyEngineError = $true
    # [2026-09-13] 原为裸文本 Write-Output——桌面版丢弃纯文本 stdout，等于 AI 看不到该告警。
    # 改走 hookSpecificOutput.additionalContext（与正常注入同通道，实测可达）。
    $errMsg = "⚠️ [迭进] $UserMessage"
    $errOut = [ordered]@{
        hookSpecificOutput = [ordered]@{
            hookEventName = "UserPromptSubmit"
            additionalContext = $errMsg
        }
    } | ConvertTo-Json -Depth 5 -Compress
    Write-Output $errOut
}

# ---- 一次调用完成所有预检 ----
$preReplyEngineError = $false
try {
    # 读取 stdin（Codex 传入的用户 prompt）
    $stdin = [System.IO.StreamReader]::new([System.Console]::OpenStandardInput()).ReadToEnd()
    $hookInput = $stdin | ConvertFrom-Json
    $prompt = $hookInput.prompt
    $sessionId = $hookInput.session_id
    if (-not $sessionId) { $sessionId = $hookInput.turn_id }

    if (Test-Path $pythonExe) {
        # [M1 契约通道 v1.0] Codex 适配器：UserPromptSubmit → 统一信封 → contract.py（三态响应）
        $contractPy = Join-Path $g_pr "engine\contract.py"
        $dgEnv = [ordered]@{
            contract="1.0"
            event="prompt_pre"
            ts=(Get-Date -Format "o")
            context=@{ platform="codex"; hook="UserPromptSubmit"; prompt=$prompt; turn_id=$hookInput.turn_id; session_id=$sessionId; blocked_error_type=$blockedType }
        }
        $envJson = $dgEnv | ConvertTo-Json -Compress -Depth 5

        # 单次 Python 调用，完成所有操作（契约统一入口）
        $rawOutput = $envJson | & $pythonExe $contractPy 2>&1
        $lastExit = $LASTEXITCODE

        $resp = $null
        try { $resp = $rawOutput | ConvertFrom-Json } catch { $resp = $null }
        if ($null -ne $resp -and $resp.decision -eq "block") {
            # 契约裁决 block：输出阻断信息
            Write-Output $resp.reason
            Write-PhaseState -Phase "pre_reply" -Status "engine_blocked" -Data @{ts=(Get-Date -Format "o")}
            exit 1
        } elseif ($null -ne $resp -and $resp.decision -eq "allow") {
            # 契约响应 allow：inject 即注入文本（display_text）
            $displayText = $resp.inject
            if (-not $displayText) { $displayText = "[DGEN] PASS" }
            # [行动时刻记忆迁移 2026-09-13] 取最近一次工具预检命中规则的 action 正文（见上方函数）
            $amText = Get-ActionMemoryInjection -SessionId $sessionId

            # [TOKEN 治理 v3.9.12] 注入指纹去重：按「注入前文本」判定（保持既有省 token 语义）
            # 判重与投递分离——行动记忆有独立去重键，不因拼接而击穿指纹缓存
            $isDup = $false
            $fpFile = Join-Path $g_pr "var\state\inject_fingerprint.json"
            $fpTable = @{}
            $sha = ""
            try {
                if ($sessionId) {
                    if (Test-Path $fpFile) {
                        try {
                            $fpObj = Get-Content $fpFile -Raw -Encoding UTF8 | ConvertFrom-Json
                            if ($fpObj) { $fpObj.PSObject.Properties | ForEach-Object { $fpTable[$_.Name] = $_.Value } }
                        } catch {}
                    }
                    $shaBytes = [System.Security.Cryptography.SHA256]::Create().ComputeHash([System.Text.Encoding]::UTF8.GetBytes($displayText))
                    $sha = -join ($shaBytes | ForEach-Object { $_.ToString("x2") })
                    $lastRec = $fpTable[$sessionId]
                    if ($lastRec -and $lastRec.hash -eq $sha) {
                        try {
                            $lastTs = [DateTime]::Parse($lastRec.ts)
                            $isDup = ((Get-Date) - $lastTs).TotalSeconds -lt 600
                        } catch { $isDup = $false }
                    }
                }
            } catch {
                Add-NoBOMLog -Path $auditLog -Message "$time [HOOK:DGEN-INJECT] DEDUP-ERROR $($_.Exception.Message)"
            }

            if ($isDup -and -not $amText) {
                $displayText = "[DGEN] PASS（迭进上下文未变化，跳过重复注入）"
                Add-NoBOMLog -Path $auditLog -Message "$time [HOOK:DGEN-INJECT] DEDUP skip session=$sessionId"
            } else {
                if ($amText) { $displayText = $displayText + "`n" + $amText }
                try {
                    if ($sessionId -and $sha) {
                        $fpTable[$sessionId] = @{hash=$sha; ts=(Get-Date -Format "o"); len=$displayText.Length}
                        Write-AtomicFile -Path $fpFile -Content ($fpTable | ConvertTo-Json -Compress)
                    }
                } catch {}
                Add-NoBOMLog -Path $auditLog -Message "$time [HOOK:DGEN-INJECT] FULL len=$($displayText.Length) session=$sessionId"
            }
            # [A通道] 2026-08-19：桌面版丢弃纯文本 stdout → 改走 hookSpecificOutput.additionalContext（核心 codex.exe 已确认支持该 Wire）
            $hookOut = [ordered]@{
                hookSpecificOutput = [ordered]@{
                    hookEventName = "UserPromptSubmit"
                    additionalContext = $displayText
                }
            } | ConvertTo-Json -Depth 5 -Compress
            Write-Output $hookOut
            Add-NoBOMLog -Path $auditLog -Message "$time [HOOK:DGEN-CHECK] OK decision=allow matched=$($resp.matched_count)"
        } else {
            # [A1] 契约输出异常 = 引擎输出异常，显式标注（不伪装 allow）
            Write-PreReplyEngineError -Detail "contract pre_reply 输出异常 exit=$lastExit" -UserMessage "引擎输出异常（预检未验证），本次放行"
        }
    } else {
        # [A1] python 缺失 = 引擎不可用，显式标注
        Write-PreReplyEngineError -Detail "pre_reply python 缺失" -UserMessage "引擎不可用（python 缺失），本次放行但状态未验证"
    }
} catch {
    Write-PreReplyEngineError -Detail "EXCEPTION $_" -UserMessage "预检脚本异常，本次放行但状态未验证"
}


# 会话图片清理：在模型请求前移除 image_url 等二进制内容（防止 keysync/DeepSeek 反序列化失败）
try {
    $imgClean = Join-Path $g_pr "hooks\diegin_session_image_clean.ps1"
    if (Test-Path $imgClean) { & $imgClean }
    Add-NoBOMLog -Path $auditLog -Message "$time [HOOK:UserPromptSubmit] IMAGE-CLEAN done"
} catch {
    Add-NoBOMLog -Path $auditLog -Message "$time [HOOK:UserPromptSubmit] IMAGE-CLEAN error: $($_.Exception.Message)"
}

if (-not $preReplyEngineError) { Write-PhaseState -Phase "pre_reply" -Status "completed" -Data @{ts=(Get-Date -Format "o")} }
