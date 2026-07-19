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

function Write-DGENStatusFile {
    param([string]$Status,[string]$Rules,[string]$Decision,[string]$Matched)
    try {
        $sf = Join-Path $script:stateDir "dgen_status.txt"
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

$pluginRoot=Split-Path -Parent (Split-Path -Parent $PSCommandPath)
$g_sf=Join-Path $pluginRoot "var\state\phase_state.json"
$auditLog=Join-Path $pluginRoot "var\logs\diegin_audit.log"
$time=Get-Date -Format "yyyy-MM-dd HH:mm:ss.fff"

$pythonExe=Join-Path $pluginRoot "bin\.venv\Scripts\python.exe"
$enginePy=Join-Path $pluginRoot "engine\call_diegin.py"
$stateDir=Join-Path $pluginRoot "var\state"

Write-PhaseState -Phase "post_tool" -Status "completed"

# DGEN 标志状态升级：allowed -> verified
$markerFile = Join-Path $stateDir "dgen_marker_pending.json"
$activeRules = "?"
try {
    if (Test-Path $pythonExe) {
        $h = & $pythonExe $enginePy health 2>&1 | ConvertFrom-Json; $activeRules = $h.active_rules
    }
} catch {}

if (Test-Path $markerFile) {
    try {
        $m = Get-Content $markerFile -Raw -Encoding UTF8 | ConvertFrom-Json
        if ($m.status -eq "allowed") {
            $verified = @{status="verified";turn_id=$m.turn_id;ts=(Get-Date -Format "o")}
            [System.IO.File]::WriteAllText($markerFile, ($verified | ConvertTo-Json -Compress), $script:utf8NoBOM)
            Add-NoBOMLog -Path $auditLog -Message "$time [HOOK:DGEN-MARKER] UPGRADED allowed_to_verified"
            Write-DGENStatusFile -Status "VERIFIED" -Rules $activeRules -Decision "allow" -Matched "0"
        }
    } catch {
        Add-NoBOMLog -Path $auditLog -Message "$time [HOOK:DGEN-MARKER] UPGRADE_ERROR $($_.Exception.Message)"
    }
}

# 攻七：记录工具调用成功
try {
    $stdin = [System.IO.StreamReader]::new([System.Console]::OpenStandardInput()).ReadToEnd()
    if ($stdin) {
        $hookInput = $stdin | ConvertFrom-Json
        $toolName = $hookInput.tool_name
        if ($toolName -and (Test-Path $pythonExe)) {
            $recResult = & $pythonExe $enginePy record_success $toolName 2>&1
            if ($LASTEXITCODE -eq 0) {
                Add-NoBOMLog -Path $auditLog -Message "$time 攻七 post_tool tool=$toolName pattern_saved"
            }
            Add-NoBOMLog -Path $auditLog -Message "$time 攻七 post_tool tool=$toolName sandwich=ok"
        }
    }
} catch {
    Add-NoBOMLog -Path $auditLog -Message "$time 攻七 post_tool record_error=$($_.Exception.Message)"
}

Add-NoBOMLog -Path $auditLog -Message "$time [HOOK:PostToolUse] ACTIVE"
exit 0