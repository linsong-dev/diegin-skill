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

$g_sf=Join-Path $g_pr "var\state\phase_state.json"




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

# 一二不过三：读阻断文件
$overrideFile = Join-Path $stateDir "dgen_override.json"
$blockedType = ""
if (Test-Path $overrideFile) {
    try { $override = Get-Content $overrideFile -Raw -Encoding UTF8 | ConvertFrom-Json; $blockedType = $override.blocked_error_type } catch {}
}

# ========== 一二不过三：阻断检查 ==========
# override 存在时直接阻断用户输入，不让 AI 有机会再犯
if ($blockedType) {
    $strikeCount = 0
    $reason = ""
    try { $strikeCount = $override.strike_count; $reason = $override.reason } catch {}
    Add-NoBOMLog -Path $auditLog -Message "$time [HOOK:OVERRIDE] BLOCK prompt type=$blockedType strike=$strikeCount"
    Write-Output "[一二不过三] 阻断: 错误类型 '$blockedType' 已被系统拦截（已触发 ${strikeCount}次）"
    if ($reason) { Write-Output "  $reason" }
    Write-Output ""
    Write-Output "[DGEN] OVERRIDE_BLOCK"
    exit 1
}



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
            blocked_error_type=$blockedType

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
                mindol_context = if ($checkResult.mindol_context) { $checkResult.mindol_context.Substring(0, [Math]::Min(500, $checkResult.mindol_context.Length)) } else { "" }

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

            $enhancedLine = $checkResult.display_line
            if ($checkResult.mindol_context) {
                $shortCtx = $checkResult.mindol_context -replace "`n"," " -replace "`r",""
                if ($shortCtx.Length -gt 200) { $shortCtx = $shortCtx.Substring(0, 200) + "..." }
                $enhancedLine = $enhancedLine + " | mem:" + $shortCtx
            }
            Write-Output $enhancedLine

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

            $mindolCtxStr = ""
            if ($checkResult.mindol_context) {
                $shortCtx = $checkResult.mindol_context -replace "`n"," " -replace "`r",""
                if ($shortCtx.Length -gt 150) { $shortCtx = $shortCtx.Substring(0, 150) + "..." }
                $mindolCtxStr = " mem:" + $shortCtx
            }
            $output = $markerStr + " PASS" + $mindolCtxStr + $suggestions

            Add-NoBOMLog -Path $auditLog -Message "$time [HOOK:DGEN-CHECK] OK decision=$($checkResult.decision) matched=$($checkResult.matched_interceptions)"

            # 去伪存真：冲突仲裁详情
            try {
                $detailRaw = $ctxJson | & $pythonExe $enginePy arbitrate_detail 2>&1
                Add-NoBOMLog -Path $auditLog -Message "$time [HOOK:ARBITER] detail=$($detailRaw -replace "`n",' ' -replace "`r",'')"
            } catch {
                Add-NoBOMLog -Path $auditLog -Message "$time [HOOK:ARBITER] error=$($_.Exception.Message)"
            }

            # 去伪存真：一致性验证（决策是否反转）
            try {
                $checkJson = $checkResult | ConvertTo-Json -Compress
                $verifyRaw = $checkJson | & $pythonExe $enginePy verify 2>&1
                Add-NoBOMLog -Path $auditLog -Message "$time [HOOK:VERIFY] result=$($verifyRaw -replace "`n",' ' -replace "`r",'')"
            } catch {
                Add-NoBOMLog -Path $auditLog -Message "$time [HOOK:VERIFY] error=$($_.Exception.Message)"
            }




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

# 阶段状态写入: pre_reply
# ---- Mindol 语义记忆 ----
$mindolBridge = Join-Path $pluginRoot "engine\mindol_bridge.py"
if (Test-Path $mindolBridge) {
    & $pyExe $mindolBridge record pre_reply "decision=$finalDecision matched=$finalMatched status=$st" codex 2>&1 | Out-Null
}
Write-PhaseState -Phase "pre_reply" -Status "completed" -Data @{ts=(Get-Date -Format "o")}