$script:utf8NoBOM = [System.Text.UTF8Encoding]::new($false)

function Add-NoBOMLog {
    param([string]$Path,[string]$Message)
    $ts=Get-Date -Format "yyyy-MM-dd HH:mm:ss.fff"
    $d=Split-Path $Path -Parent
    if($d -and -not(Test-Path $d)){New-Item $d -Force|Out-Null}
    $old=""
    if(Test-Path $Path){$old=[System.IO.File]::ReadAllText($Path,$script:utf8NoBOM)}
    [System.IO.File]::WriteAllText($Path,"$ts $Message`r`n$old",$script:utf8NoBOM)
}

$g_fallback_root = "$env:USERPROFILE\.codex\diegin"
$g_psPath = $PSCommandPath
if ([string]::IsNullOrEmpty($g_psPath)) { $g_psPath = Join-Path $g_fallback_root "hooks\diegin_pre_tool.ps1" }
$g_pr = Split-Path -Parent (Split-Path -Parent $g_psPath)
if ([string]::IsNullOrEmpty($g_pr)) { $g_pr = $g_fallback_root }

$auditLog = Join-Path $g_pr "var\logs\diegin_audit.log"
$time = Get-Date -Format "yyyy-MM-dd HH:mm:ss.fff"
$pythonExe = Join-Path $g_pr "bin\.venv\Scripts\python.exe"
$enginePy = Join-Path $g_pr "engine\call_diegin.py"
$stateDir = Join-Path $g_pr "var\state"

Add-NoBOMLog -Path $auditLog -Message "$time [HOOK:PreToolUse] FIRED"

function Check-StateFile($fp) {
    if (-not (Test-Path $fp)) { return $null }
    try { $raw=[System.IO.File]::ReadAllText($fp,$script:utf8NoBOM); $s=$raw|ConvertFrom-Json
        $age=[DateTime]::Now-[DateTime]::Parse($s.ts)
        if($age.TotalSeconds -gt 60) { return $null }
        if($s.decision -in @("block","iron_wall_block")) { return $s }
    } catch{}; return $null
}

try {
    $stdin = [System.IO.StreamReader]::new([System.Console]::OpenStandardInput()).ReadToEnd()
    $hookInput = $stdin | ConvertFrom-Json
    $toolName = $hookInput.tool_name
    $toolInput = $hookInput.tool_input
    $command = ""; if ($toolInput -and $toolInput.command) { $command = $toolInput.command }

    $replyFile = Join-Path $stateDir "dgen_last_reply.json"
    $replyState = Check-StateFile $replyFile
    if ($replyState) {
        Add-NoBOMLog -Path $auditLog -Message "$time [HOOK:DGEN-BLOCK-RELAY] $($replyState.reason)"
        Write-Error "[DGEN] TOOL BLOCKED (hook): $($replyState.reason)"
        exit 1
    }

    $overrideFile = Join-Path $stateDir "dgen_override.json"
    $overrideState = Check-StateFile $overrideFile
    if ($overrideState) {
        Add-NoBOMLog -Path $auditLog -Message "$time [HOOK:DGEN-BLOCK-OVERRIDE] $($overrideState.reason)"
        Write-Error "[DGEN] TOOL BLOCKED (ai-override): $($overrideState.reason)"
        exit 1
    }

    if (Test-Path $pythonExe) {
        $ctx = [ordered]@{
            task_type="pre_tool"
            session_id=$hookInput.session_id
            turn_id=$hookInput.turn_id
            tool_name=$toolName
            tool_input=$toolInput
            command=$command
            text=$command
            hook_event_name="PreToolUse"
        }
        $ctxJson = $ctx | ConvertTo-Json -Compress -Depth 3
        $rawOutput = $ctxJson | & $pythonExe $enginePy check 2>&1
        $checkResult = $rawOutput | ConvertFrom-Json

        $s2=@{ts=(Get-Date -Format "o");decision=$checkResult.decision;reason=$checkResult.reason;winning_rule=$checkResult.winning_rule_id;matched_count=$checkResult.matched_interceptions}
        [System.IO.File]::WriteAllText($replyFile,($s2|ConvertTo-Json -Compress),$script:utf8NoBOM)

        if($checkResult.decision -in @("block","iron_wall_block")){
            Add-NoBOMLog -Path $auditLog -Message "$time [HOOK:DGEN-BLOCK] rule=$($checkResult.winning_rule_id)"
            Write-Error "[DGEN] TOOL BLOCKED: $($checkResult.reason)"
            exit 1
        }
        Add-NoBOMLog -Path $auditLog -Message "$time [HOOK:DGEN-ALLOW] $($checkResult.decision) matched=$($checkResult.matched_interceptions)"
    }
} catch {
    Add-NoBOMLog -Path $auditLog -Message "$time [HOOK:DGEN-ERROR] $_"
}
exit 0