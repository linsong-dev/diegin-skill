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
exit 0
