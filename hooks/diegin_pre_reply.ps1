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



$g_scriptDir = if ($PSCommandPath) { Split-Path $PSCommandPath -Parent } else { $null }

$g_pluginRoot = if ($g_scriptDir) { Split-Path $g_scriptDir -Parent } else { $null }

$g_fallback_root = if ($g_pluginRoot) { $g_pluginRoot } else { $env:CODEX_HOME + "\diegin" }

$g_psPath = $PSCommandPath

if ([string]::IsNullOrEmpty($g_psPath)) { $g_psPath = Join-Path $g_fallback_root "hooks\diegin_pre_reply.ps1" }

$g_pr = Split-Path -Parent (Split-Path -Parent $g_psPath)

if ([string]::IsNullOrEmpty($g_pr)) { $g_pr = $g_fallback_root }



$auditLog = Join-Path $g_pr "var\logs\diegin_audit.log"

$time = Get-Date -Format "yyyy-MM-dd HH:mm:ss.fff"

$pythonExe = Join-Path $g_pr "bin\.venv\Scripts\python.exe"

$enginePy = Join-Path $g_pr "engine\call_diegin.py"

$stateFile = Join-Path $g_pr "var\state\dgen_last_reply.json"

$stateDir = Split-Path $stateFile -Parent



Add-NoBOMLog -Path $auditLog -Message "$time [HOOK:UserPromptSubmit] FIRED"



if (-not (Test-Path $stateDir)) { New-Item $stateDir -Force | Out-Null }



try {

    $stdin = [System.IO.StreamReader]::new([System.Console]::OpenStandardInput()).ReadToEnd()

    $hookInput = $stdin | ConvertFrom-Json

    $prompt = $hookInput.prompt



    if (Test-Path $pythonExe) {

        $ctx = [ordered]@{

            task_type="user_prompt"

            text=$prompt

            hook_event_name="UserPromptSubmit"

            prompt=$prompt

        }

        $ctxJson = $ctx | ConvertTo-Json -Compress

        $rawOutput = $ctxJson | & $pythonExe $enginePy check 2>&1

        $checkResult = $rawOutput | ConvertFrom-Json



        $state = @{

            ts=(Get-Date -Format "o")

            decision=$checkResult.decision

            reason=$checkResult.reason

            winning_rule=$checkResult.winning_rule_id

            matched_count=$checkResult.matched_interceptions

        }

        $stateJson = $state | ConvertTo-Json -Compress

        [System.IO.File]::WriteAllText($stateFile, $stateJson, $script:utf8NoBOM)



        try {

            $ctxFile = Join-Path $stateDir "diegin_context.json"

            $engineHealthRaw = & $pythonExe $enginePy health 2>&1

            $engineHealth = $engineHealthRaw | ConvertFrom-Json

            $suggestList = @()

            try { $sugRaw2 = & $pythonExe $enginePy suggest ('{"prompt":"' + $prompt.Replace('"','\"') + '","task_type":"general","op":"reply"}') 2>&1; $sugR = $sugRaw2 | ConvertFrom-Json; if ($sugR.suggestions) { $suggestList = $sugR.suggestions } } catch {}

            $ctx = [ordered]@{

                ts = (Get-Date -Format "o")

                engine = [ordered]@{

                    active_rules = $engineHealth.active_rules

                    total_rules = $engineHealth.total_rules

                    cached_rules = $engineHealth.cached_rules

                    entropy_status = $engineHealth.entropy_status

                }

                check = [ordered]@{

                    decision = $checkResult.decision

                    matched_count = $checkResult.matched_interceptions

                    winning_rule = $checkResult.winning_rule_id

                    reason = $checkResult.reason

                }

                suggestions = $suggestList

                status = "active"

            }

            [System.IO.File]::WriteAllText($ctxFile, ($ctx | ConvertTo-Json -Depth 5 -Compress), $script:utf8NoBOM)

            Add-NoBOMLog -Path $auditLog -Message "$time [HOOK:DGEN-CTX] context_written"

        } catch { Add-NoBOMLog -Path $auditLog -Message "$time [HOOK:DGEN-CTX] write_error: $_" }



        try {

            $markerFile = Join-Path $stateDir "dgen_marker_pending.json"

            $markerState = @{status="pending";turn_id=$hookInput.turn_id;ts=(Get-Date -Format "o")}

            [System.IO.File]::WriteAllText($markerFile, ($markerState | ConvertTo-Json -Compress), $script:utf8NoBOM)

            Add-NoBOMLog -Path $auditLog -Message "$time [HOOK:DGEN-MARKER] pending_written"

        } catch { Add-NoBOMLog -Path $auditLog -Message "$time [HOOK:DGEN-MARKER] write_error: $_" }



        if ($checkResult.decision -in @("block","iron_wall_block")) {

            Add-NoBOMLog -Path $auditLog -Message "$time [HOOK:DGEN-CHECK] BLOCK rule=$($checkResult.winning_rule_id)"

            Write-Output $checkResult.display_line

            exit 1

        } else {

            $suggestions = ""

            try {

                $sugRaw = & $pythonExe $enginePy suggest ('{"prompt":"' + $prompt.Replace('"','\"') + '","task_type":"general","op":"reply"}') 2>&1

                $sugResult = $sugRaw | ConvertFrom-Json

                if ($sugResult.count -gt 0 -and $sugResult.suggestions) {

                    $sugLines = @()

                    foreach ($s in $sugResult.suggestions) {

                        $sugLines += "  - $($s.id): $($s.decision)"

                    }

                    $suggestions = "`n攻七·推荐路径`n" + ($sugLines -join "`n")

                    Add-NoBOMLog -Path $auditLog -Message "$time 攻七 suggest injected=$($sugResult.count) patterns"

                }

            } catch {}



            $markerStr = "`[DGEN`]"

            $output = $markerStr + " PASS" + $suggestions

            Add-NoBOMLog -Path $auditLog -Message "$time [HOOK:DGEN-CHECK] OK decision=$($checkResult.decision) matched=$($checkResult.matched_interceptions)"



            $output += "`n`n=== PROTOCOL ==="

            $output += "`nFirst tool command MUST contain: " + $markerStr

            $output += "`n=== END PROTOCOL ==="

            Write-Output $output

        }

    } else {

        $m = "`[DGEN`]"

        Write-Output "$m ENGINE_CHECK"

    }

} catch {

    Add-NoBOMLog -Path $auditLog -Message "$time [HOOK:DGEN-CHECK] EXCEPTION $_"

    $m = "`[DGEN`]"

    Write-Output "$m ENGINE_CHECK"

}

