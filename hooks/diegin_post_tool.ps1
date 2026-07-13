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
$pythonExe=Join-Path $pluginRoot "bin\.venv\Scripts\python.exe"
$enginePy=Join-Path $pluginRoot "engine\call_diegin.py"
$time=Get-Date -Format "yyyy-MM-dd HH:mm:ss.fff"

# 写阶段状态
Write-PhaseState -Phase "post_tool" -Status "completed"

# ⚔️ 攻七：记录工具调用成功，提取成功模式
try {
    $stdin = [System.IO.StreamReader]::new([System.Console]::OpenStandardInput()).ReadToEnd()
    if ($stdin) {
        $hookInput = $stdin | ConvertFrom-Json
        $toolName = $hookInput.tool_name
        if ($toolName -and (Test-Path $pythonExe)) {
            # 记录成功操作到 sandwitch 复盘
            $recResult = & $pythonExe $enginePy record_success $toolName 2>&1
            if ($LASTEXITCODE -eq 0) {
                Add-NoBOMLog -Path $auditLog -Message "$time ⚔️ 攻七 post_tool tool=$toolName pattern_saved"
            } else {
                Add-NoBOMLog -Path $auditLog -Message "$time ⚔️ 攻七 post_tool tool=$toolName record_error"
            }
            Add-NoBOMLog -Path $auditLog -Message "$time ⚔️ 攻七 post_tool tool=$toolName sandwich=ok"
        }
    }
} catch {
    Add-NoBOMLog -Path $auditLog -Message "$time ⚔️ 攻七 post_tool record_error=$($_.Exception.Message)"
}

Add-NoBOMLog -Path $auditLog -Message "$time [HOOK:PostToolUse] ACTIVE"
exit 0