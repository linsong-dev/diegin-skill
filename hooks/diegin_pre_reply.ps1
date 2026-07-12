$script:utf8NoBOM = [System.Text.UTF8Encoding]::new($false)

function Add-NoBOMLog {
    param([string]$Path,[string]$Message)
    $ts = Get-Date -Format "yyyy-MM-dd HH:mm:ss.fff"
    $d = Split-Path $Path -Parent
    if ($d -and -not(Test-Path $d)) { New-Item $d -Force | Out-Null }
    $oldContent = ""
    if (Test-Path $Path) { $oldContent = [System.IO.File]::ReadAllText($Path,$script:utf8NoBOM) }
    [System.IO.File]::WriteAllText($Path,"$ts $Message`r`n$oldContent",$script:utf8NoBOM)
}

$pluginRoot = Split-Path -Parent (Split-Path -Parent $PSCommandPath)
$auditLog = Join-Path $pluginRoot "diegin_audit.log"
$time = Get-Date -Format "yyyy-MM-dd HH:mm:ss.fff"
$pythonExe = Join-Path $pluginRoot "bin\.venv\Scripts\python.exe"
$enginePy = Join-Path $pluginRoot "engine\call_diegin.py"
$stateFile = Join-Path $pluginRoot "var\state\dgen_last_reply.json"

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

        if ($checkResult.decision -eq "block" -or $checkResult.decision -eq "iron_wall_block") {
            Add-NoBOMLog -Path $auditLog -Message "$time [HOOK:DGEN-CHECK] BLOCK rule=$($checkResult.winning_rule_id) $($checkResult.reason)"
            Write-Output $checkResult.display_line
            exit 1
        } else {
            Add-NoBOMLog -Path $auditLog -Message "$time [HOOK:DGEN-CHECK] OK decision=$($checkResult.decision) matched=$($checkResult.matched_interceptions)"
            Write-Output "[DGEN] ✅ 通过"
        }
    } else {
        Write-Output "[DGEN] ⚡ 迭进引擎检查中"
    }
} catch {
    Add-NoBOMLog -Path $auditLog -Message "$time [HOOK:DGEN-CHECK] EXCEPTION $_"
    Write-Output "[DGEN] ⚡ 迭进引擎检查中"
}