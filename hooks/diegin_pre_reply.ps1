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
    Write-Output ""
    Write-Output "⚠️ [迭进] $UserMessage"
    Write-Output ""
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
            # [TOKEN 治理 v3.9.12] 注入指纹去重：同会话 600 秒内相同注入 → 最小标记（省每轮新增 token / 缓存未命中）
            try {
                if ($sessionId) {
                    $fpFile = Join-Path $g_pr "var\state\inject_fingerprint.json"
                    $fpTable = @{}
                    if (Test-Path $fpFile) {
                        try {
                            $fpObj = Get-Content $fpFile -Raw -Encoding UTF8 | ConvertFrom-Json
                            if ($fpObj) { $fpObj.PSObject.Properties | ForEach-Object { $fpTable[$_.Name] = $_.Value } }
                        } catch {}
                    }
                    $shaBytes = [System.Security.Cryptography.SHA256]::Create().ComputeHash([System.Text.Encoding]::UTF8.GetBytes($displayText))
                    $sha = -join ($shaBytes | ForEach-Object { $_.ToString("x2") })
                    $lastRec = $fpTable[$sessionId]
                    $isDup = $false
                    if ($lastRec -and $lastRec.hash -eq $sha) {
                        try {
                            $lastTs = [DateTime]::Parse($lastRec.ts)
                            $isDup = ((Get-Date) - $lastTs).TotalSeconds -lt 600
                        } catch { $isDup = $false }
                    }
                    if ($isDup) {
                        $displayText = "[DGEN] PASS（迭进上下文未变化，跳过重复注入）"
                        Add-NoBOMLog -Path $auditLog -Message "$time [HOOK:DGEN-INJECT] DEDUP skip session=$sessionId"
                    } else {
                        $fpTable[$sessionId] = @{hash=$sha; ts=(Get-Date -Format "o"); len=$displayText.Length}
                        Write-AtomicFile -Path $fpFile -Content ($fpTable | ConvertTo-Json -Compress)
                        Add-NoBOMLog -Path $auditLog -Message "$time [HOOK:DGEN-INJECT] FULL len=$($displayText.Length) session=$sessionId"
                    }
                }
            } catch {
                Add-NoBOMLog -Path $auditLog -Message "$time [HOOK:DGEN-INJECT] DEDUP-ERROR $($_.Exception.Message)"
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
