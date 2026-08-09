$script:utf8NoBOM = [System.Text.UTF8Encoding]::new($false)
# [2026-08-09] 中文传输加固：PS5.1 默认 $OutputEncoding=ASCII/控制台GBK 会破坏管道中文
# → 强制 UTF-8，保证 PS->Python stdin / Python stdout->PS 均无损（防 prompt 入库乱码、pre_reply JSON 解析失败）
try { $OutputEncoding = $script:utf8NoBOM } catch {}
try { [Console]::OutputEncoding = $script:utf8NoBOM } catch {}



function Write-AtomicFile {
    param([string]$Path,[string]$Content)
    # [C2] 原子写：tmp+Replace(真实备份) 防读半截；失败兜底 Delete+Move；任何情况清理 tmp 防残留
    $tmp = $Path + ".tmp_" + [System.Guid]::NewGuid().ToString("N")
    $bak = $Path + ".bak"
    [System.IO.File]::WriteAllText($tmp, $Content, $script:utf8NoBOM)
    $ok = $false
    try {
        if ([System.IO.File]::Exists($Path)) {
            [System.IO.File]::Replace($tmp, $Path, $bak)
            if ([System.IO.File]::Exists($bak)) { [System.IO.File]::Delete($bak) }
        } else {
            [System.IO.File]::Move($tmp, $Path)
        }
        $ok = $true
    } catch {
        # 兜底：非原子但保证不失败不残留
        if ([System.IO.File]::Exists($Path)) { [System.IO.File]::Delete($Path) }
        [System.IO.File]::Move($tmp, $Path)
        $ok = $true
    }
    if ([System.IO.File]::Exists($tmp)) { [System.IO.File]::Delete($tmp) }
}

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

    Write-AtomicFile -Path $g_sf -Content ($s|ConvertTo-Json -Depth 5)

}



$g_pr=Split-Path -Parent (Split-Path -Parent $PSCommandPath)

$g_sf=Join-Path $g_pr "var\state\phase_state.json"

# 引擎调用路径
$pythonExe = "$env:USERPROFILE\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe"
$enginePy = Join-Path $g_pr "engine\call_diegin.py"

$auditLog=Join-Path $g_pr "var\logs\diegin_audit.log"

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

        $pythonExe = "$env:USERPROFILE\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe"

        if (Test-Path $pythonExe) {

            $cleanResult = & $pythonExe $tmpFile 2>&1

            Add-NoBOMLog -Path $auditLog -Message "$time 🧹 log_cleanup db=$(($dbSize/1MB -as [int]))MB result=$cleanResult"

        }

        if (Test-Path $tmpFile) { Remove-Item $tmpFile -Force }

    } elseif ($dbSize -gt 100MB) {

        Add-NoBOMLog -Path $auditLog -Message "$time 🧹 log_cleanup db=$(($dbSize/1MB -as [int]))MB under_threshold"

    }

}


# 去伪存真·硬地板: 将阶段状态传给引擎规则匹配
$phaseJson = ""
if (Test-Path $g_sf) {
    try { $phaseJson = [System.IO.File]::ReadAllText($g_sf, $script:utf8NoBOM) } catch {}
}
if ($phaseJson -and (Test-Path $pythonExe)) {
    try {
        # 构建上下文，匹配 hard_floor 规则
        $ctxForEngine = "{`"phase`":`"stop_verification`",`"phase_check`":false,`"phase_state`":" + $phaseJson + "}"
        $engineResult = $ctxForEngine | & $pythonExe $enginePy check 2>&1
        $engineDecision = $engineResult | ConvertFrom-Json
        Add-NoBOMLog -Path $auditLog -Message "$time [HOOK:Stop] HARD_FLOOR_CHECK decision=$($engineDecision.decision) matched=$($engineDecision.matched_interceptions)"
        if ($engineDecision.decision -in @("BLOCK","IRON_WALL_BLOCK")) {
            Write-PhaseState -Phase "stop_verification" -Status "hard_floor_blocked" -Data @{engine_decision=$engineDecision.decision;reason=$engineDecision.reason}
            # 硬地板阻断是正常机制，不作为 strike 记录（已修复）
            Add-NoBOMLog -Path $auditLog -Message "$time [HOOK:Stop] HARD_FLOOR_BLOCK (expected, no strike)"
        }
    } catch {
        Add-NoBOMLog -Path $auditLog -Message "$time [HOOK:Stop] HARD_FLOOR_ERROR $_"
    }
}
# ---- Mindol 语义记忆写入（Stop事件） ----
# ensure engineDecision exists, default to 'no_check'
if (-not $engineDecision) { $engineDecision = @{decision='no_check'} }
$mindolBridge = Join-Path $g_pr "engine\mindol_bridge.py"
if (Test-Path $mindolBridge) {
    $mindolText = "phase=stop priority=stop hardFloor=" + $engineDecision.decision + " phaseJson=" + [System.Convert]::ToBoolean($phaseJson -ne "")
    if ($mindolText.Length -gt 500) { $mindolText = $mindolText.Substring(0, 500) }
    $null = & $pythonExe $mindolBridge record stop $mindolText 2>&1
}

