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


function Read-PhaseState {
    if(-not(Test-Path $g_sf)){return $null}
    try{$r=[System.IO.File]::ReadAllText($g_sf,$script:utf8NoBOM);return($r|ConvertFrom-Json)}catch{}return $null
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

$state=Read-PhaseState
$integrity="NO_STATE"
if($state -and $state.phases){
    $integrity="OK"
    $bad=@()
    $state.phases.PSObject.Properties|ForEach-Object{if($_.Value.status -in @("stalled","error")){$bad+=$_.Name}}
    if($bad.Count -gt 0){$integrity="STALLED:$($bad -join ',')"}
}

$summary=""
if($state -and $state.phases){$names=$state.phases.PSObject.Properties|ForEach-Object{$_.Name};$summary=($names|ForEach-Object{"$_=$($state.phases.$_.status)"})-join" | "}

if($integrity -eq "NO_STATE" -or -not $state){
    Add-NoBOMLog -Path $auditLog -Message "$time [HOOK:Stop] CLEAN_NO_TASK"
}elseif($integrity -like "STALLED*"){
    Add-NoBOMLog -Path $auditLog -Message "$time [HOOK:Stop] STALLED integrity=$integrity | $summary"
    Write-PhaseState -Phase "stop_verification" -Status "stalled" -Data @{integrity=$integrity;summary=$summary}
}else{
    Add-NoBOMLog -Path $auditLog -Message "$time [HOOK:Stop] VERIFIED | $summary"
    Write-PhaseState -Phase "stop_verification" -Status "verified" -Data @{integrity=$integrity;summary=$summary}
}

# ── 🧹 日志库自动清理（当 >200MB 时删 7 天前的 TRACE） ──
$logDb = "$env:USERPROFILE\.codex\logs_2.sqlite"
if (Test-Path $logDb) {
    $dbSize = (Get-Item $logDb).Length
    if ($dbSize -gt 200MB) {
        $cleanScript = @"
import sqlite3, os, sys
sys.stdout.reconfigure(encoding="utf-8")
db = r"$logDb"
try:
    before = os.path.getsize(db)
    conn = sqlite3.connect(db, timeout=30000)
    deleted = conn.execute("DELETE FROM logs WHERE level='TRACE' AND ts < strftime('%s','now','-7 day')").rowcount
    conn.execute("VACUUM")
    conn.close()
    after = os.path.getsize(db)
    saved = (before - after) // (1024*1024)
    print(f"OK deleted={deleted} saved={saved}MB")
except Exception as e:
    print(f"SKIP {e}")
"@
        $tmpFile = Join-Path $env:TEMP "clean_logs_$([Guid]::NewGuid().ToString('N')).py"
        [System.IO.File]::WriteAllText($tmpFile, $cleanScript, $script:utf8NoBOM)
        $pyExe = Join-Path $root_run "bin\.venv\Scripts\python.exe"
        if (Test-Path $pyExe) {
            $cleanResult = & $pyExe $tmpFile 2>&1
            Add-NoBOMLog -Path $auditLog -Message "$time 🧹 log_cleanup db=$(($dbSize/1MB -as [int]))MB result=$cleanResult"
        }
        if (Test-Path $tmpFile) { Remove-Item $tmpFile -Force }
    } elseif ($dbSize -gt 100MB) {
        Add-NoBOMLog -Path $auditLog -Message "$time 🧹 log_cleanup db=$(($dbSize/1MB -as [int]))MB under_threshold"
    }
}
exit 0
