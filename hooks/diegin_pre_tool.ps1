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

function Write-DGENContextAndExit {
    param([int]$ExitCode=1)
    $ctxTool = Join-Path $script:g_pr "var\state\diegin_pre_tool_context.json"
    $dc="unknown"; $dm=0; $tn="unknown"
    if (Test-Path $script:gateFile) {
        try { $g = Get-Content $script:gateFile -Raw -Encoding UTF8 | ConvertFrom-Json; $dc = $g.decision; $dm = $g.matched_count } catch { }
    }
    try { $tn = $script:toolName } catch { }
    $toolCtxStr = '{"ts":"' + (Get-Date -Format "o") + '","decision":"' + $dc + '","matched_count":' + $dm + ',"tool_name":"' + $tn + '"}'
    try { [System.IO.File]::WriteAllText($ctxTool, $toolCtxStr, $script:utf8NoBOM) } catch { }
    exit $ExitCode
}

function Write-DGENStatusFile {
    param([string]$Status,[string]$Rules,[string]$Decision,[string]$Matched)
    try {
        $sf = Join-Path $script:g_pr "var\state\dgen_status.txt"
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

$g_scriptDir = if ($PSCommandPath) { Split-Path $PSCommandPath -Parent } else { $null }
$g_pluginRoot = if ($g_scriptDir) { Split-Path $g_scriptDir -Parent } else { $null }
$g_fallback_root = if ($g_pluginRoot) { $g_pluginRoot } else { $env:CODEX_HOME + "\diegin" }
$g_psPath = $PSCommandPath
if ([string]::IsNullOrEmpty($g_psPath)) { $g_psPath = Join-Path $g_fallback_root "hooks\diegin_pre_tool.ps1" }
$g_pr = Split-Path -Parent (Split-Path -Parent $g_psPath)
if ([string]::IsNullOrEmpty($g_pr)) { $g_pr = $g_fallback_root }

$auditLog = Join-Path $g_pr "var\logs\diegin_audit.log"
$time = Get-Date -Format "yyyy-MM-dd HH:mm:ss.fff"
$pythonExe = Join-Path $g_pr "bin\.venv\Scripts\python.exe"
$enginePy = Join-Path $g_pr "engine\call_diegin.py"
$stateDir = Join-Path $g_pr "var\state"
$gateFile = Join-Path $g_pr "var/state/dgen_last_reply.json"
$markerFile = Join-Path $g_pr "var\state\dgen_marker_pending.json"

Add-NoBOMLog -Path $auditLog -Message "$time [HOOK:PreToolUse] FIRED"

# ============================================================
# 第1步：读取 stdin，获取命令详情
# ============================================================
$toolName = "unknown"
$command = ""
try {
    $stdin = [System.IO.StreamReader]::new([System.Console]::OpenStandardInput()).ReadToEnd()
    if ($stdin) {
        $hookInput = $stdin | ConvertFrom-Json
        $toolName = $hookInput.tool_name
        $toolInput = $hookInput.tool_input
        if ($toolInput) {
            if ($toolInput.command) { $command = $toolInput.command }
            elseif ($toolInput.tool_input -and $toolInput.tool_input.command) { $command = $toolInput.tool_input.command }
        }
    }
} catch {}

Add-NoBOMLog -Path $auditLog -Message "$time [HOOK:PreToolUse] tool=$toolName cmd_len=$($command.Length)"

# ============================================================
# 第2步：DGEN 标志强制检查（自举 + 过期重置）
#   marker 生命周期:
#     无 marker → 自动创建"pending"
#     pending → 检查命令含 [DGEN STATUS: xxx] 才放行
#     allowed → 等待 PostToolUse 升级
#     verified → 检查是否过期（5分钟）→ 过期则重置 pending
# ============================================================
$markerStatus = ""
$markerTs = $null
if (Test-Path $markerFile) {
    try {
        $m = Get-Content $markerFile -Raw -Encoding UTF8 | ConvertFrom-Json
        $markerStatus = $m.status
        if ($m.ts) { $markerTs = $m.ts }
    } catch {}
}

# verified 过期检查：超过5分钟重置为 pending
if ($markerStatus -eq "verified" -and $markerTs) {
    try {
        $age = [DateTime]::Now - [DateTime]::Parse($markerTs)
        if ($age.TotalSeconds -gt 300) {
            $markerState = @{status="pending";turn_id="expired";ts=(Get-Date -Format "o")}
            [System.IO.File]::WriteAllText($markerFile, ($markerState | ConvertTo-Json -Compress), $script:utf8NoBOM)
            $markerStatus = "pending"
            Add-NoBOMLog -Path $auditLog -Message "$time [HOOK:DGEN-MARKER] EXPIRED verified_gt5min_reset_pending"
        } else {
            Add-NoBOMLog -Path $auditLog -Message "$time [HOOK:DGEN-MARKER] VERIFIED_SKIP fresh_verified_no_check"
        }
    } catch {}
}

if ($markerStatus -eq "") {
    $markerState = @{status="pending";turn_id="auto";ts=(Get-Date -Format "o")}
    [System.IO.File]::WriteAllText($markerFile, ($markerState | ConvertTo-Json -Compress), $script:utf8NoBOM)
    $markerStatus = "pending"
    Add-NoBOMLog -Path $auditLog -Message "$time [HOOK:DGEN-MARKER] AUTO_CREATED pending"
}

if ($markerStatus -eq "pending") {
    # 检查 [DGEN STATUS: xxx] 格式（比单纯的 [DGEN] 更具体）
    $hasMarker = ($command -and $command -match '\[DGEN')
    if (-not $hasMarker) {
        Add-NoBOMLog -Path $auditLog -Message "$time [HOOK:DGEN-MARKER] BLOCK no_DGEN_STATUS tool=$toolName"
        Write-Error ("DGEN_BLOCK|reason=缺标志:命令不含[DGEN]|rule=dgen_marker_gate")
        Write-DGENStatusFile -Status "BLOCKED" -Rules "?" -Decision "block" -Matched "?" 
        Write-DGENContextAndExit -ExitCode 1
    } else {
        $newMarker = @{status="allowed";turn_id="auto";ts=(Get-Date -Format "o")}
        [System.IO.File]::WriteAllText($markerFile, ($newMarker | ConvertTo-Json -Compress), $script:utf8NoBOM)
        Add-NoBOMLog -Path $auditLog -Message "$time [HOOK:DGEN-MARKER] ALLOW marker_detected tool=$toolName"
    }
}

# ============================================================
# 第3步：Soft Gate 状态检查
# ============================================================
function Check-StateFile($fp) {
    if (-not (Test-Path $fp)) { return $null }
    try { $raw=[System.IO.File]::ReadAllText($fp,$script:utf8NoBOM); $s=$raw|ConvertFrom-Json
        $age=[DateTime]::Now-[DateTime]::Parse($s.ts)
        if($age.TotalSeconds -gt 120) { return $null }
        if($s.decision -in @("block","iron_wall_block")) { return $s }
    } catch{}; return $null
}

if (-not (Test-Path $gateFile)) {
    $initState = @{ts=(Get-Date -Format "o");decision="allow";reason="pre_tool_auto_init";winning_rule="";matched_count=0}
    [System.IO.File]::WriteAllText($gateFile, ($initState | ConvertTo-Json -Compress), $script:utf8NoBOM)
    Add-NoBOMLog -Path $auditLog -Message "$time [HOOK:DGEN-GATE] AUTO_INIT"
}

$replyFile = Join-Path $stateDir "dgen_last_reply.json"
$replyState = Check-StateFile $replyFile
if ($replyState) {
    Add-NoBOMLog -Path $auditLog -Message "$time [HOOK:DGEN-BLOCK-RELAY] $($replyState.reason)"
    Write-Error ("DGEN_BLOCK|reason=" + $replyState.reason + "|rule=pre_reply_relay")
    Write-DGENContextAndExit -ExitCode 1
}

$overrideFile = Join-Path $stateDir "dgen_override.json"
$overrideState = Check-StateFile $overrideFile
if ($overrideState) {
    Add-NoBOMLog -Path $auditLog -Message "$time [HOOK:DGEN-BLOCK-OVERRIDE] $($overrideState.reason)"
    Write-Error ("DGEN_BLOCK|reason=" + $overrideState.reason + "|rule=ai_override")
    Write-DGENContextAndExit -ExitCode 1
}

# ============================================================
# 第4步：引擎检查 + 写状态文件供 AI 读取
# ============================================================
$finalDecision = "allow"
$finalMatched = 0
$finalRule = ""
$activeRules = "?"
try {
    if (Test-Path $pythonExe) {
        $ctx = [ordered]@{
            task_type="pre_tool"
            tool_name=$toolName
            command=$command
            text=$command
            hook_event_name="PreToolUse"
        }
        $ctxJson = $ctx | ConvertTo-Json -Compress -Depth 3
        $rawOutput = $ctxJson | & $pythonExe $enginePy check 2>&1
        $checkResult = $rawOutput | ConvertFrom-Json
        $finalDecision = $checkResult.decision
        $finalMatched = $checkResult.matched_interceptions
        $finalRule = $checkResult.winning_rule_id

        $s2=@{ts=(Get-Date -Format "o");decision=$finalDecision;reason=$checkResult.reason;winning_rule=$finalRule;matched_count=$finalMatched}
        [System.IO.File]::WriteAllText($replyFile,($s2|ConvertTo-Json -Compress),$script:utf8NoBOM)

        if($finalDecision -in @("block","iron_wall_block")){
            Add-NoBOMLog -Path $auditLog -Message "$time [HOOK:DGEN-BLOCK] rule=$finalRule"
            $blockRule = $finalRule
            if ([string]::IsNullOrEmpty($blockRule)) { $blockRule = "unknown" }
            Write-Error ("DGEN_BLOCK|reason=" + $checkResult.reason + "|rule=" + $blockRule)
            Write-DGENStatusFile -Status "BLOCKED" -Rules $activeRules -Decision $finalDecision -Matched $finalMatched
            Write-DGENContextAndExit -ExitCode 1
        }
        
        # 读取活跃规则数
        try { $h = & $pythonExe $enginePy health 2>&1 | ConvertFrom-Json; $activeRules = $h.active_rules } catch {}
        
        Add-NoBOMLog -Path $auditLog -Message "$time [HOOK:DGEN-ALLOW] decision=$finalDecision matched=$finalMatched"
    }
} catch {
    Add-NoBOMLog -Path $auditLog -Message "$time [HOOK:DGEN-ERROR] $($_.Exception.Message)"
}

# 写状态文件供 AI 读取
$st = $markerStatus
if ($st -eq "allowed") { $st = "ALLOWED" }
elseif ($st -eq "verified") { $st = "VERIFIED" }
elseif ($st -eq "pending") { $st = "PENDING" }
Write-DGENStatusFile -Status $st -Rules $activeRules -Decision $finalDecision -Matched $finalMatched
Write-DGENContextAndExit -ExitCode 0