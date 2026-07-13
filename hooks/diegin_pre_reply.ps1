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
if ([string]::IsNullOrEmpty($g_psPath)) { $g_psPath = Join-Path $g_fallback_root "hooks\diegin_pre_reply.ps1" }
$g_pr = Split-Path -Parent (Split-Path -Parent $g_psPath)
if ([string]::IsNullOrEmpty($g_pr)) { $g_pr = $g_fallback_root }

$auditLog = Join-Path $g_pr "var\logs\diegin_audit.log"
$time = Get-Date -Format "yyyy-MM-dd HH:mm:ss.fff"
$pythonExe = Join-Path $g_pr "bin\.venv\Scripts\python.exe"
$enginePy = Join-Path $g_pr "engine\call_diegin.py"
$stateFile = Join-Path $g_pr "var\state\dgen_last_reply.json"

Add-NoBOMLog -Path $auditLog -Message "$time [HOOK:UserPromptSubmit] FIRED"

try {
    $stdin = [System.IO.StreamReader]::new([System.Console]::OpenStandardInput()).ReadToEnd()
    $hookInput = $stdin | ConvertFrom-Json
    $prompt = $hookInput.prompt

    if (Test-Path $pythonExe) {
        $ctx = [ordered]@{
            task_type="user_prompt"
            session_id=$hookInput.session_id
            turn_id=$hookInput.turn_id
            text=$prompt
            hook_event_name="UserPromptSubmit"
            prompt=$prompt
        }
        $ctxJson = $ctx | ConvertTo-Json -Compress
        $rawOutput = $ctxJson | & $pythonExe $enginePy check 2>&1
        $checkResult = $rawOutput | ConvertFrom-Json

        $stateDir = Split-Path $stateFile -Parent
        if (-not (Test-Path $stateDir)) { New-Item $stateDir -Force | Out-Null }
        $state = @{
            ts=(Get-Date -Format "o")
            decision=$checkResult.decision
            reason=$checkResult.reason
            winning_rule=$checkResult.winning_rule_id
            matched_count=$checkResult.matched_interceptions
        }
        $stateJson = $state | ConvertTo-Json -Compress
        [System.IO.File]::WriteAllText($stateFile, $stateJson, $script:utf8NoBOM)

        if ($checkResult.decision -in @("block","iron_wall_block")) {
            Add-NoBOMLog -Path $auditLog -Message "$time [HOOK:DGEN-CHECK] BLOCK rule=$($checkResult.winning_rule_id)"
            Write-Output $checkResult.display_line
            exit 1
        } else {
            Add-NoBOMLog -Path $auditLog -Message "$time [HOOK:DGEN-CHECK] OK decision=$($checkResult.decision) matched=$($checkResult.matched_interceptions)"
            Write-Output "[DGEN] PASS"
        }
    } else {
        Write-Output "[DGEN] ENGINE_CHECK"
    }
} catch {
    Add-NoBOMLog -Path $auditLog -Message "$time [HOOK:DGEN-CHECK] EXCEPTION $_"
    Write-Output "[DGEN] ENGINE_CHECK"
}