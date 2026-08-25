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

function Write-DGENStatusFile {
    param([string]$Status,[string]$Rules,[string]$Decision,[string]$Matched)
    try {
        $sf = Join-Path $script:stateDir "dgen_status.txt"
        $s = "=== DGEN STATUS ==="
        $s += "`nSTATUS: $Status"
        $s += "`nRULES: $Rules"
        $s += "`nDECISION: $Decision"
        $s += "`nMATCHED: $Matched"
        $s += "`nTS: " + (Get-Date -Format "o")
        $s += "`n=================="
        Write-AtomicFile -Path $sf -Content $s
    } catch {}
}

$g_pr=Split-Path -Parent (Split-Path -Parent $PSCommandPath)
$g_sf=Join-Path $g_pr "var\state\phase_state.json"
$auditLog=Join-Path $g_pr "var\logs\diegin_audit.log"
$time=Get-Date -Format "yyyy-MM-dd HH:mm:ss.fff"

$pythonExe = $env:DGEN_PYTHON; if (-not $pythonExe) { $pythonExe = Join-Path $g_pr "bin\.venv\Scripts\python.exe"; if (-not (Test-Path $pythonExe)) { $pythonExe = "$env:USERPROFILE\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe" } }
$enginePy=Join-Path $g_pr "engine\call_diegin.py"
$stateDir=Join-Path $g_pr "var\state"

Write-PhaseState -Phase "post_tool" -Status "completed"
# [P1.2] 统一读取 hook 输入（stdin 只读一次，供 detect/record_error/closure 复用）
$stdin = ""
$hookInput = $null
$toolName = ""
$toolCmd = ""
$toolExitCode = $null
$toolError = ""
$snapshotExit = $LASTEXITCODE
try {
    $stdin = [System.IO.StreamReader]::new([System.Console]::OpenStandardInput()).ReadToEnd()
    if ($stdin) {
        $hookInput = $stdin | ConvertFrom-Json
        $toolName = $hookInput.tool_name
        if ($hookInput.tool_input) { if ($hookInput.tool_input.command) { $toolCmd = $hookInput.tool_input.command } }
        if ($hookInput.command) { $toolCmd = $hookInput.command }
        if ($hookInput.cmd) { $toolCmd = $hookInput.cmd }
        if ($null -ne $hookInput.exit_code) { $toolExitCode = $hookInput.exit_code }
        if ($hookInput.error) { $toolError = $hookInput.error }
        if ($hookInput.stderr) { $toolError = $hookInput.stderr }
        if ($hookInput.tool_response) {
            $resp = [string]$hookInput.tool_response
            if ($resp -match 'Cannot find drive|DriveNotFound|not recognized|command not found|Access is denied|Permission denied|Cannot find path|is not recognized|不是内部或外部命令|找不到路径|拒绝访问|未能找到') {
                if (-not $toolError) { $toolError = $resp; if ($toolError.Length -gt 400) { $toolError = $toolError.Substring(0, 400) } }
                if ($null -eq $toolExitCode) { $toolExitCode = 1 }
            }
        }
    }
} catch {
    Add-NoBOMLog -Path $auditLog -Message "$time [DETECT] hook_input_parse_error=$($_.Exception.Message)"
}


# [PERF-B 2026-08-19] health/feedback_adopt/record_success/closure/mindol/evidence
# → 全部并入 post_tool_batch 单次 Python 进程调用（下方 batch 段），消除 5 次独立进程启动 + contract.py 双层 subprocess
# DGEN 标志状态升级（allowed -> verified）移至 batch 调用之后，复用其返回的 active_rules
$markerFile = Join-Path $stateDir "dgen_marker_pending.json"
$activeRules = "?"

Add-NoBOMLog -Path $auditLog -Message "$time [HOOK:PostToolUse] ACTIVE"
# [B1-20260806] 变更-验证绑定（ACC-QRY-004）：检测源码变更 → 最小验证 → 可审计记录
function Test-DieginChangeEvent {
    param([string]$ToolName,[string]$Cmd,[int]$ExitCode)
    if ($ToolName -match 'apply_patch|edit|write') { return $true }
    if ($ToolName -ne 'shell_command') { return $false }
    if ($null -ne $ExitCode -and $ExitCode -ne 0) { return $false }
    if (-not $Cmd) { return $false }
    # 只认写文件语义（排除只读/查询 → 防 better-harness 式误判）
    if ($Cmd -match '(>>|Set-Content|WriteAllText|Add-Content|Out-File|Move-Item|Remove-Item|New-Item|Copy-Item|apply_patch|git\s+add|git\s+commit)') { return $true }
    return $false
}

function Write-DieginChangeRecord {
    param([string]$ToolName,[string]$Cmd,[int]$ExitCode)
    try {
        $logFile = Join-Path $stateDir "dgen_change_log.json"
        $records = @()
        if (Test-Path $logFile) {
            try { $records = @(Get-Content $logFile -Raw -Encoding UTF8 | ConvertFrom-Json) } catch { $records = @() }
        }
        # 最小验证：self_check（只读无副作用）
        $vStatus = "unverified"; $vErr = ""
        try {
            $sc = & $pythonExe (Join-Path $g_pr "engine\diegin_self_check.py") 2>&1 | Out-String
            if ($sc -match '"status":\s*"ok"') { $vStatus = "passed" } else { $vStatus = "failed"; $vErr = $sc.Substring(0, [Math]::Min(200, $sc.Length)) }
        } catch { $vStatus = "error"; $vErr = $_.Exception.Message }
        $preview = $Cmd
        if ($preview.Length -gt 200) { $preview = $preview.Substring(0, 200) }
        $hashBytes = [System.Security.Cryptography.SHA256]::Create().ComputeHash([System.Text.Encoding]::UTF8.GetBytes($Cmd))
        $cmdHash = ([System.BitConverter]::ToString($hashBytes)).Replace("-", "").Substring(0, 16)
        $rec = @{
            ts=(Get-Date -Format "o")
            tool=$ToolName
            exit_code=$ExitCode
            command_preview=$preview
            command_hash=$cmdHash
            verification=@{check="diegin_self_check"; status=$vStatus; err=$vErr; ts=(Get-Date -Format "o")}
        }
        $records = @($rec) + $records
        if ($records.Count -gt 200) { $records = $records[0..199] }
        [System.IO.File]::WriteAllText($logFile, ($records | ConvertTo-Json -Depth 5), $script:utf8NoBOM)
        Add-NoBOMLog -Path $auditLog -Message "$time [B1-CHANGE] recorded tool=$ToolName verify=$vStatus"
    } catch {
        Add-NoBOMLog -Path $auditLog -Message "$time [B1-CHANGE] record_error=$($_.Exception.Message)"
    }
}

try {
    if (Test-DieginChangeEvent -ToolName $toolName -Cmd $toolCmd -ExitCode $toolExitCode) {
        Write-DieginChangeRecord -ToolName $toolName -Cmd $toolCmd -ExitCode $toolExitCode
    }
} catch {
    Add-NoBOMLog -Path $auditLog -Message "$time [B1-CHANGE] detect_error=$($_.Exception.Message)"
}


# 会话图片清理
$cleanScript = Join-Path $g_pr "hooks\diegin_session_image_clean.ps1"
if (Test-Path $cleanScript) { & $cleanScript }

# 举一反三：跨域泛化（每5次触发一次）
$genCounterFile = Join-Path $stateDir "generalize_counter.txt"
$genCount = 0
if (Test-Path $genCounterFile) { $genCount = [int](Get-Content $genCounterFile -Raw -ErrorAction SilentlyContinue) }
$genCount++
[System.IO.File]::WriteAllText($genCounterFile, "$genCount", $script:utf8NoBOM)
if ($genCount -ge 5) {
[System.IO.File]::WriteAllText($genCounterFile, "0", $script:utf8NoBOM)
    if (Test-Path $pythonExe) {
        $genResult = & $pythonExe $enginePy generalize_cross_domain 2>&1
        Add-NoBOMLog -Path $auditLog -Message "$time 举一反三 generalize_result=$genResult"
        # 攻七·泛化提速：从成功模式泛化为拦截规则（门槛 复用≥2次 或 conf≥4.5，函数内已过滤）
        $genPatResult = & $pythonExe $enginePy generalize_patterns 2>&1
        Add-NoBOMLog -Path $auditLog -Message "$time 攻七 generalize_patterns_result=$genPatResult"
    }
}

# 一二不过三：错误检测（读取工具执行结果，如有错误则记录strike）
try {
    if ($null -eq $toolExitCode) { $toolExitCode = $snapshotExit }
    
    # 从 stdin 读取更多上下文
    if ($stdin) {
        try {
            $hookInput = $stdin | ConvertFrom-Json
            if ($hookInput.exit_code -or $hookInput.exit_code -eq 0) { $toolExitCode = $hookInput.exit_code }
            if ($hookInput.error) { $toolError = $hookInput.error }
            if ($hookInput.stderr) { $toolError = $hookInput.stderr }
        if ($hookInput.tool_response) {
            $resp = [string]$hookInput.tool_response
            if ($resp -match 'Cannot find drive|DriveNotFound|not recognized|command not found|Access is denied|Permission denied|Cannot find path|is not recognized|不是内部或外部命令|找不到路径|拒绝访问|未能找到') {
                if (-not $toolError) { $toolError = $resp; if ($toolError.Length -gt 400) { $toolError = $toolError.Substring(0, 400) } }
                if ($null -eq $toolExitCode) { $toolExitCode = 1 }
            }
        }
            if ($hookInput.command) { $toolCmd = $hookInput.command }
            if ($hookInput.cmd) { $toolCmd = $hookInput.cmd }
        } catch {}
    }
    
    # 有错误时调用 analyze 模式记录 strike
    $shouldAnalyze = $false
    if ($toolExitCode -ne 0 -and $toolExitCode -ne $null) { $shouldAnalyze = $true }
    if ($toolError) { $shouldAnalyze = $true }
    
    if ($shouldAnalyze -and (Test-Path $pythonExe)) {
        $analyzeCtx = @{
            tool_name = if ($toolName) { $toolName } else { "unknown" }
            exit_code = $toolExitCode
            error = $toolError
            cmd = $toolCmd
        } | ConvertTo-Json -Compress
        $analyzeResult = $analyzeCtx | & $pythonExe $enginePy analyze 2>&1
        $analyzeText = ($analyzeResult | Out-String).Trim()
        $flat = $analyzeText.Replace("`n", " ").Replace("`r", "")
        Add-NoBOMLog -Path $auditLog -Message "$time [DETECT] tool=$toolName exit=$toolExitCode result=$flat"
        if ($analyzeText -match '"error"') {
            # v3.8 修复：条件倒挂（原 -notmatch 导致检测到错误反而跳过记录）
            # 现在：analyze 检测到错误（含 "error" 字段）→ 立即记录一二不过三 strike
            $errType = "tool_error_" + $toolName
            $errDetail = "exit=" + $toolExitCode
            if ($toolError) { $errDetail = $toolError }
            if ($errDetail.Length -gt 200) { $errDetail = $errDetail.Substring(0, 200) }
            $recErrCtx = @{
                error_type = $errType
                detail = $errDetail
                severity = "high"
                cmd = $toolCmd
            } | ConvertTo-Json -Compress
            $recErrResult = $recErrCtx | & $pythonExe $enginePy record_error 2>&1
            $flatRec = $recErrResult.Replace("`n", " ").Replace("`r", "")
            Add-NoBOMLog -Path $auditLog -Message "$time [TRACKER] record_error type=$errType result=$flatRec"
        } else {
            Add-NoBOMLog -Path $auditLog -Message "$time [TRACKER] analyze no_error skip_record"
        }
        # 即时重检：analyze 后立即检查 strike 状态，如已达第2次则确保 override 已写入
        $strikesFile = Join-Path $g_pr "var\state\strikes_db.json"
        if (Test-Path $strikesFile) {
            try {
                $strikes = Get-Content $strikesFile -Raw -Encoding UTF8 | ConvertFrom-Json
                foreach ($etype in $strikes.PSObject.Properties) {
                    $count = $etype.Value.count
                    if ($count -ge 2) {
                        Add-NoBOMLog -Path $auditLog -Message "$time [TRACKER] RE-CHECK error_type=$($etype.Name) count=$count"
                    }
                }
            } catch {}
        }
    }
} catch {
    Add-NoBOMLog -Path $auditLog -Message "$time [TRACKER] analyze error=$($_.Exception.Message)"
}

# ============================================================
# [PERF-B 2026-08-19] post_tool_batch：单进程合并 6 动作
#   health + feedback_adopt(条件) + record_success(条件) + closure_close + mindol×2 + record_evidence
#   替代原 5 次独立 Python 进程启动（contract→health 双层 subprocess / feedback_adopt / record_success / closure_close / mindol+evidence）
# ============================================================
$batchCtx = @{}
$learnings = @()
$prioPatternId = ""
$prioReady = $false
try {
    # 1) 攻七反馈闭环 Q4: 工具成功 + 有 priority 推荐 → 自动采纳（置信度+0.5）
    $prioFile = Join-Path $stateDir "dgen_priority_pattern.json"
    $prioReady = (Test-Path $prioFile) -and -not $toolError -and ($null -eq $toolExitCode -or $toolExitCode -eq 0)
    if ($prioReady) {
        $prioRec = Get-Content $prioFile -Raw -Encoding UTF8 | ConvertFrom-Json
        if ($prioRec.pattern_id) { $prioPatternId = [string]$prioRec.pattern_id }
    }
    if ($prioPatternId) { $batchCtx.prio_pattern_id = $prioPatternId; $batchCtx.adopted = $true }

    # 2) 攻七：记录工具调用成功（v3.6.1 传递命令文本，实质化模式库）+ 预策·③ 三重判定意图上下文
    $intentSummary = ""
    $intentNegative = $null
    $resultText = ""
    try {
        $intentFile = Join-Path $stateDir "current_intent.json"
        if (Test-Path $intentFile) {
            $ii = Get-Content $intentFile -Raw -Encoding UTF8 | ConvertFrom-Json
            $iiAgeMin = 999
            try {
                $iiTs = [DateTime]::Parse([string]$ii.ts)
                $iiAgeMin = ((Get-Date) - $iiTs).TotalMinutes
            } catch {}
            if ($iiAgeMin -le 60) {
                $intentSummary = [string]$ii.intent_summary
                if ($null -ne $ii.user_negative) { $intentNegative = [bool]$ii.user_negative }
            }
        }
        if ($hookInput.tool_response) {
            $resultText = [string]$hookInput.tool_response
            if ($resultText.Length -gt 800) { $resultText = $resultText.Substring(0, 800) }
        }
    } catch {}
    $toolOkFlag = ($null -eq $toolExitCode -or $toolExitCode -eq 0)
    if ($toolName) {
        $batchCtx.tool_name = $toolName
        $batchCtx.method = $toolCmd
        $batchCtx.intent_summary = $intentSummary
        $batchCtx.result_text = $resultText
        if ($null -ne $intentNegative) { $batchCtx.user_negative = $intentNegative }
        $batchCtx.tool_ok = $toolOkFlag
    }

    # 3) 止观门：post_tool 封存本次工具调用（[CLOSURE] 配对 + archive 增长 + learnings 打包）
    $closureId = "post_tool_" + $toolName + "_" + (Get-Date -Format "yyyyMMddHHmmssfff")
    $closeSummary = "tool=" + $toolName + " exit=" + $toolExitCode
    $learnings = @()
    $learnings += ("tool=" + $toolName)
    $learnings += ("exit=" + $toolExitCode)
    if ($toolError) {
        $lkErr = $toolError
        if ($lkErr.Length -gt 150) { $lkErr = $lkErr.Substring(0, 150) }
        $learnings += ("error: " + $lkErr)
    }
    # 定稿第八章：执行轨迹只读快照（阻断记录/工具调用序列/裁决日志摘要）→ 供守三应急复盘只读访问
    $snapBlock = @()
    if ($analyzeText -match '"error"') {
        $sb = "tool=" + $toolName + " exit=" + $toolExitCode
        if ($toolError) { $sb += " err=" + $toolError }
        if ($sb.Length -gt 500) { $sb = $sb.Substring(0, 500) }
        $snapBlock += $sb
    }
    $snapSeq = @()
    if ($toolName) {
        $sq = $toolName
        if ($toolCmd) { $sq += ": " + $toolCmd }
        if ($sq.Length -gt 500) { $sq = $sq.Substring(0, 500) }
        $snapSeq += $sq
    }
    $snapArb = "exit=" + $toolExitCode + " decision=" + $decision + " matched=" + $matched
    if ($toolError) { $snapArb += " error=" + $toolError }
    if ($snapArb.Length -gt 2000) { $snapArb = $snapArb.Substring(0, 2000) }
    $batchCtx.closure = @{
        item_id = $closureId
        summary = $closeSummary
        learnings = $learnings
        snapshot = @{
            block_records = $snapBlock
            tool_call_sequence = $snapSeq
            arbitration_log = $snapArb
        }
    }

    # 4) Mindol 语义记忆写入 + 去伪存真证据裁决（并入 batch；引擎内 save_chat 同步 codex/raw_chat 双空间）
    $batchCtx.mindol_post_text = "tool=$toolName decision=$decision matched=$matched snippet=$cmdSnippet"
    if ($batchCtx.mindol_post_text.Length -gt 500) { $batchCtx.mindol_post_text = $batchCtx.mindol_post_text.Substring(0, 500) }
    $chatText = "tool=$toolName cmd=$toolCmd exit=$toolExitCode"
    if ($chatText.Length -gt 450) { $chatText = $chatText.Substring(0, 450) }
    $batchCtx.mindol_raw_chat_text = $chatText
    $batchCtx.evidence = @{
        rule_id = if ($toolName) { $toolName } else { "unknown" }
        verdict = if ($toolExitCode -eq 0 -or $toolExitCode -eq $null) { "pass" } else { "fail" }
        reason = "tool=$toolName exit=$toolExitCode"
        source = "post_tool"
        detail = $toolCmd
    }
} catch {
    Add-NoBOMLog -Path $auditLog -Message "$time [PERF-B] batch_ctx_error=$($_.Exception.Message)"
}

# 单进程聚合调用（替代原 5 次进程启动；stdin JSON 无损传递中文）
if (Test-Path $pythonExe) {
    try {
        $batchJson = $batchCtx | ConvertTo-Json -Compress -Depth 8
        $batchOut = (($batchJson | & $pythonExe $enginePy post_tool_batch 2>&1) | Out-String).Trim()
        $batchObj = $null
        try { $batchObj = $batchOut | ConvertFrom-Json } catch {}
        if ($batchObj) {
            # health → DGEN 状态（active_rules）
            if ($batchObj.health) { $activeRules = [string]$batchObj.health.active_rules }
            # 攻七记录回写
            if ($batchObj.record_success) {
                if ($batchObj.record_success.action -eq "saved") {
                    Add-NoBOMLog -Path $auditLog -Message "$time 攻七 post_tool tool=$toolName pattern_saved"
                }
                $rsFlat = ($batchObj.record_success | ConvertTo-Json -Compress).Replace("`n", " ").Replace("`r", "")
                if ($rsFlat.Length -gt 200) { $rsFlat = $rsFlat.Substring(0, 200) }
                Add-NoBOMLog -Path $auditLog -Message "$time 攻七 post_tool tool=$toolName sandwich=$rsFlat"
            }
            # 反馈闭环回写
            if ($batchObj.feedback_adopt) {
                $adoptFlat = ($batchObj.feedback_adopt | ConvertTo-Json -Compress).Replace("`n", " ").Replace("`r", "")
                if ($adoptFlat.Length -gt 150) { $adoptFlat = $adoptFlat.Substring(0, 150) }
                Add-NoBOMLog -Path $auditLog -Message "$time [FEEDBACK-ADOPT] auto_adopt pattern=$prioPatternId result=$adoptFlat"
            }
            # 止观封存回写
            if ($batchObj.closure) {
                $flatClose = ($batchObj.closure | ConvertTo-Json -Compress).Replace("`n", " ").Replace("`r", "")
                Add-NoBOMLog -Path $auditLog -Message "$time [CLOSURE] post_tool close id=$closureId learnings=$($learnings.Count) result=$flatClose"
            }
        } else {
            Add-NoBOMLog -Path $auditLog -Message "$time [PERF-B] batch_parse_fail out=$batchOut"
        }
        # 采纳完成后删除 priority 文件（保持原语义：满足条件即删）
        if ($prioReady) {
            try { if (Test-Path $prioFile) { [System.IO.File]::Delete($prioFile) } } catch {}
        }
    } catch {
        Add-NoBOMLog -Path $auditLog -Message "$time [PERF-B] batch_error=$($_.Exception.Message)"
    }
}

# DGEN 标志状态升级：allowed -> verified（置于 batch 之后，复用其返回的 active_rules）
if (Test-Path $markerFile) {
    try {
        $m = Get-Content $markerFile -Raw -Encoding UTF8 | ConvertFrom-Json
        if ($m.status -eq "allowed") {
            $verified = @{status="verified";turn_id=$m.turn_id;ts=(Get-Date -Format "o")}
            [System.IO.File]::WriteAllText($markerFile, ($verified | ConvertTo-Json -Compress), $script:utf8NoBOM)
            Add-NoBOMLog -Path $auditLog -Message "$time [HOOK:DGEN-MARKER] UPGRADED allowed_to_verified"
            Write-DGENStatusFile -Status "VERIFIED" -Rules $activeRules -Decision "allow" -Matched "0"
            # [B方案] 验证闭环完成：标记生命周期 verified（回复含标记 → 工具链执行完毕）
            try {
                $vRec = @{ts=(Get-Date -Format "o");tool="post_tool";has_marker=$true;status="verified";decision="allow"}
                [System.IO.File]::WriteAllText((Join-Path $stateDir "dgen_verify_result.json"), ($vRec | ConvertTo-Json -Compress), $script:utf8NoBOM)
                Add-NoBOMLog -Path $auditLog -Message "$time [HOOK:DGEN-VERIFY] verified_marker_cycle_complete"
            } catch {
                Add-NoBOMLog -Path $auditLog -Message "$time [HOOK:DGEN-VERIFY] UPGRADE_RECORD_ERROR $($_.Exception.Message)"
            }
        }
    } catch {
        Add-NoBOMLog -Path $auditLog -Message "$time [HOOK:DGEN-MARKER] UPGRADE_ERROR $($_.Exception.Message)"
    }
}
try {
    $reviewCounterFile = Join-Path $stateDir "post_review_counter.txt"
    $reviewCount = 0
    if (Test-Path $reviewCounterFile) { $reviewCount = [int](Get-Content $reviewCounterFile -Raw -ErrorAction SilentlyContinue) }
    $reviewCount++
[System.IO.File]::WriteAllText($reviewCounterFile, "$reviewCount", $script:utf8NoBOM)
    $isSuccess = ($toolExitCode -eq 0 -or $toolExitCode -eq $null)
    if ($reviewCount -ge 5 -and $isSuccess -and (Test-Path $pythonExe)) {
[System.IO.File]::WriteAllText($reviewCounterFile, "0", $script:utf8NoBOM)
        $reviewToolName = "unknown"
        if ($toolName) { $reviewToolName = $toolName }
        $reviewCtx = @{
            task_type = "post_tool_review"
            tool_name = $reviewToolName
            cmd = $toolCmd
        } | ConvertTo-Json -Compress
        $reviewResult = @{status="completed"; tool=$toolName; exit_code=$toolExitCode} | ConvertTo-Json -Compress
        # v3.6.1: 经临时文件传 JSON（Windows argv/管道对长 JSON+中文+引号会损坏）
        $reviewTmp = Join-Path $env:TEMP ("diegin_review_" + [System.Guid]::NewGuid().ToString("N") + ".json")
        [System.IO.File]::WriteAllText($reviewTmp, (@($reviewCtx, $reviewResult) | ConvertTo-Json -Compress -Depth 6), $script:utf8NoBOM)
        $rv = & $pythonExe $enginePy review ("@" + $reviewTmp) 2>&1
        if (Test-Path $reviewTmp) { Remove-Item -LiteralPath $reviewTmp -Force -ErrorAction SilentlyContinue }
        $rvText = ($rv | Out-String).Trim()
        Add-NoBOMLog -Path $auditLog -Message "$time v3.6 post_review triggered tool=$toolName result=$rvText"
    }
} catch {
    Add-NoBOMLog -Path $auditLog -Message "$time v3.6 post_review error=$($_.Exception.Message)"
}

# Mindol 语义记忆写入与证据裁决已并入 post_tool_batch（见上方 batch 段）

exit 0
