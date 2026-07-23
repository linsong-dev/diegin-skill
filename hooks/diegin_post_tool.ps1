$script:utf8NoBOM = [System.Text.UTF8Encoding]::new($false)

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
    [System.IO.File]::WriteAllText($g_sf,($s|ConvertTo-Json -Depth 5),$script:utf8NoBOM)
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
        [System.IO.File]::WriteAllText($sf, $s, $script:utf8NoBOM)
    } catch {}
}

$pluginRoot=Split-Path -Parent (Split-Path -Parent $PSCommandPath)
$g_sf=Join-Path $pluginRoot "var\state\phase_state.json"
$auditLog=Join-Path $pluginRoot "var\logs\diegin_audit.log"
$time=Get-Date -Format "yyyy-MM-dd HH:mm:ss.fff"

$pythonExe=Join-Path $pluginRoot "bin\.venv\Scripts\python.exe"
$enginePy=Join-Path $pluginRoot "engine\call_diegin.py"
$stateDir=Join-Path $pluginRoot "var\state"

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
        }
    } catch {
        Add-NoBOMLog -Path $auditLog -Message "$time [HOOK:DGEN-MARKER] UPGRADE_ERROR $($_.Exception.Message)"
    }
}

# 攻七：记录工具调用成功
try {
    $stdin = [System.IO.StreamReader]::new([System.Console]::OpenStandardInput()).ReadToEnd()
    if ($stdin) {
        $hookInput = $stdin | ConvertFrom-Json
        $toolName = $hookInput.tool_name
        if ($toolName -and (Test-Path $pythonExe)) {
            $recResult = & $pythonExe $enginePy record_success $toolName 2>&1
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
$cleanScript = Join-Path $pluginRoot "hooks\diegin_session_image_clean.ps1"
if (Test-Path $cleanScript) { & $cleanScript }

# 举一反三：跨域泛化（每5次触发一次）
$genCounterFile = Join-Path $stateDir "generalize_counter.txt"
$genCount = 0
if (Test-Path $genCounterFile) { $genCount = [int](Get-Content $genCounterFile -Raw -ErrorAction SilentlyContinue) }
$genCount++
Set-Content -Path $genCounterFile -Value $genCount -NoNewline
if ($genCount -ge 5) {
    Set-Content -Path $genCounterFile -Value "0" -NoNewline
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
        $strikesFile = Join-Path $pluginRoot "var\state\strikes_db.json"
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

# ---- Mindol 语义记忆写入 ----
$mindolBridge = Join-Path $pluginRoot "engine\mindol_bridge.py"
if (Test-Path $mindolBridge) {
    $mindolText = "tool=$toolName decision=$decision matched=$matched snippet=$cmdSnippet"
    if ($mindolText.Length -gt 500) { $mindolText = $mindolText.Substring(0, 500) }
    & $pyExe $mindolBridge record post_tool $mindolText 2>&1 | Out-Null
}

exit 0