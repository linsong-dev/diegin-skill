$script:utf8NoBOM = [System.Text.UTF8Encoding]::new($false)

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
        $old=""
        if(Test-Path $Path){$old=[System.IO.File]::ReadAllText($Path,$script:utf8NoBOM)}
        [System.IO.File]::WriteAllText($Path,"$ts $Message`r`n$old",$script:utf8NoBOM)
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

$pythonExe="$env:USERPROFILE\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe"
$enginePy=Join-Path $g_pr "engine\call_diegin.py"
$stateDir=Join-Path $g_pr "var\state"

Write-PhaseState -Phase "post_tool" -Status "completed"

# DGEN 标志状态升级：allowed -> verified
$markerFile = Join-Path $stateDir "dgen_marker_pending.json"
$activeRules = "?"
try {
    if (Test-Path $pythonExe) {
        $h = & $pythonExe $enginePy health 2>&1 | ConvertFrom-Json; $activeRules = $h.active_rules
    }
} catch {}

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

# 攻七：记录工具调用成功（v3.6.1 传递命令文本，实质化模式库）
try {
    $stdin = [System.IO.StreamReader]::new([System.Console]::OpenStandardInput()).ReadToEnd()
    if ($stdin) {
        $hookInput = $stdin | ConvertFrom-Json
        $toolName = $hookInput.tool_name
        $toolCmd = ""
        if ($hookInput.tool_input) { if ($hookInput.tool_input.command) { $toolCmd = $hookInput.tool_input.command } }
        if ($hookInput.command) { $toolCmd = $hookInput.command }
        if ($hookInput.cmd) { $toolCmd = $hookInput.cmd }
        if ($toolName -and (Test-Path $pythonExe)) {
            # v3.6.6 修复：PowerShell argv 会拆分含引号/分号的命令 → 改 stdin JSON 传递（无损）
            $rsJson = @{tool_name=$toolName; method=$toolCmd} | ConvertTo-Json -Compress
            $recResult = $rsJson | & $pythonExe $enginePy record_success 2>&1
            if ($LASTEXITCODE -eq 0) {
                Add-NoBOMLog -Path $auditLog -Message "$time 攻七 post_tool tool=$toolName pattern_saved"
            }
            Add-NoBOMLog -Path $auditLog -Message "$time 攻七 post_tool tool=$toolName sandwich=ok"
        }
    }
} catch {
    Add-NoBOMLog -Path $auditLog -Message "$time 攻七 post_tool record_error=$($_.Exception.Message)"
}

Add-NoBOMLog -Path $auditLog -Message "$time [HOOK:PostToolUse] ACTIVE"

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
    }
}

# 一二不过三：错误检测（读取工具执行结果，如有错误则记录strike）
try {
    $toolExitCode = $LASTEXITCODE
    $toolError = ""
    $toolCmd = ""
    
    # 从 stdin 读取更多上下文
    if ($stdin) {
        try {
            $hookInput = $stdin | ConvertFrom-Json
            if ($hookInput.exit_code -or $hookInput.exit_code -eq 0) { $toolExitCode = $hookInput.exit_code }
            if ($hookInput.error) { $toolError = $hookInput.error }
            if ($hookInput.stderr) { $toolError = $hookInput.stderr }
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
        if ($LASTEXITCODE -eq 0) {
            Add-NoBOMLog -Path $auditLog -Message "$time [TRACKER] analyze done exit=$toolExitCode result=$($analyzeResult -replace "`n",' ' -replace "`r",'')"
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

# v3.6: post_review 节流接入（每5次成功工具调用触发一次复盘：置信度回流 + 24h维护）
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

# ---- Mindol 语义记忆写入 ----
$mindolBridge = Join-Path $g_pr "engine\mindol_bridge.py"
if (Test-Path $mindolBridge) {
    $mindolText = "tool=$toolName decision=$decision matched=$matched snippet=$cmdSnippet"
    if ($mindolText.Length -gt 500) { $mindolText = $mindolText.Substring(0, 500) }
    & $pythonExe $mindolBridge record post_tool $mindolText 2>&1 | Out-Null

    # 去伪存真：写入证据裁决
    $evidenceVault = Join-Path $g_pr "engine\call_diegin.py"
    $evCtx = @{
        rule_id = if ($toolName) { $toolName } else { "unknown" }
        verdict = if ($toolExitCode -eq 0 -or $toolExitCode -eq $null) { "pass" } else { "fail" }
        reason = "tool=$toolName exit=$toolExitCode"
        source = "post_tool"
        detail = $toolCmd
    } | ConvertTo-Json -Compress
    $evCtx | & $pythonExe $evidenceVault record_evidence 2>&1 | Out-Null

    # 同时写入 raw_chat 空间（对话上下文记忆）
    $chatText = "tool=$toolName cmd=$toolCmd exit=$toolExitCode"
    if ($chatText.Length -gt 450) { $chatText = $chatText.Substring(0, 450) }
    & $pythonExe $mindolBridge record raw_chat "$chatText (raw_chat)" 2>&1 | Out-Null
}

exit 0
