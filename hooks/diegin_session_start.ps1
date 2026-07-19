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

$pluginRoot=Split-Path -Parent (Split-Path -Parent $PSCommandPath)
$g_sf=Join-Path $pluginRoot "var\state\phase_state.json"
$auditLog=Join-Path $pluginRoot "var\logs\diegin_audit.log"
$time=Get-Date -Format "yyyy-MM-dd HH:mm:ss.fff"

$pythonExe=Join-Path $pluginRoot "bin\.venv\Scripts\python.exe"
$enginePy=Join-Path $pluginRoot "engine\call_diegin.py"
$engineOk=$false;$ruleCount=0
if(Test-Path $pythonExe){
    $result=& $pythonExe $enginePy health 2>&1
    try{$p=$result|ConvertFrom-Json;$engineOk=$true;$ruleCount=$p.active_rules}catch{}
}

Write-PhaseState -Phase "session_start" -Status "passed" -Data @{engine_ok=$engineOk.ToString();time=(Get-Date -Format "yyyy-MM-dd HH:mm:ss")}
Add-NoBOMLog -Path $auditLog -Message "$time [HOOK:SessionStart] ACTIVE engine=$engineOk rules=$ruleCount"

# 写初始状态文件，确保 PreToolUse 通过
$initialStateFile = Join-Path $pluginRoot "var\state\dgen_last_reply.json"
$initialState = @{ts=(Get-Date -Format "o");decision="allow";reason="session_start_init";winning_rule="";matched_count=0}
$initialJson = $initialState | ConvertTo-Json -Compress
[System.IO.File]::WriteAllText($initialStateFile, $initialJson, $script:utf8NoBOM)
Add-NoBOMLog -Path $auditLog -Message "$time [HOOK:SessionStart] STATE_FILE_WRITTEN"

# 重置 DGEN 标志：新对话全新开始，PreToolUse 自举 pending
$markerFile = Join-Path $pluginRoot "var\state\dgen_marker_pending.json"
if (Test-Path $markerFile) { Remove-Item $markerFile -Force }
Add-NoBOMLog -Path $auditLog -Message "$time [HOOK:SessionStart] MARKER_RESET for_new_session"

# 引擎状态上下文
$ctxFile = Join-Path $pluginRoot "var\state\diegin_context.json"
$ts = Get-Date -Format "o"
if ($engineOk) { $t = $ruleCount; $h = "OK" } else { $t = 0; $h = "ERR" }
$ctxObj = New-Object PSObject -Property @{
    ts = $ts
    engine = New-Object PSObject -Property @{active_rules=$ruleCount;total_rules=$t;health=$h}
    check = New-Object PSObject -Property @{decision="allow";matched_count=0;winning_rule="";reason="session_start_init"}
    suggestions = @()
    status = "active"
}
try {
    $ctxJson = $ctxObj | ConvertTo-Json -Depth 5 -Compress
    [System.IO.File]::WriteAllText($ctxFile, $ctxJson, $script:utf8NoBOM)
} catch { }

exit 0