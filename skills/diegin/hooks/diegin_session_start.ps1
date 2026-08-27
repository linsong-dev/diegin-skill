$script:utf8NoBOM = [System.Text.UTF8Encoding]::new($false)

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
        # [PERF] append 追加写，不再整文件读改写
        # [PERF] 超 8MB 自动归档为 .1，防止单文件无限膨胀
        if(Test-Path $Path){
            $len=(Get-Item $Path).Length
            if($len -gt 8388608){
                $arc = $Path + ".1"
                if(Test-Path $arc){Remove-Item $arc -Force}
                Move-Item $Path $arc -Force
            }
        }
        [System.IO.File]::AppendAllText($Path,"$ts $Message`r`n",$script:utf8NoBOM)
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
    Write-AtomicFile -Path $g_sf -Content ($s|ConvertTo-Json -Depth 5)
}

$g_pr=Split-Path -Parent (Split-Path -Parent $PSCommandPath)
$g_sf=Join-Path $g_pr "var\state\phase_state.json"
$auditLog=Join-Path $g_pr "var\logs\diegin_audit.log"
$time=Get-Date -Format "yyyy-MM-dd HH:mm:ss.fff"

$pythonExe = Join-Path $g_pr "bin\.venv\Scripts\python.exe"
if (-not (Test-Path $pythonExe)) { $pythonExe = "$env:USERPROFILE\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe" }
$enginePy=Join-Path $g_pr "engine\contract.py"
$engineOk=$false;$ruleCount=0
if(Test-Path $pythonExe){
    # [M1 契约通道 v1.0] SessionStart → 统一信封 → contract.py（session_start → health）
    $dgEnv = [ordered]@{ contract="1.0"; event="session_start"; ts=(Get-Date -Format "o"); context=@{ platform="codex"; hook="SessionStart" } }
    $envJson = $dgEnv | ConvertTo-Json -Compress -Depth 5
    $result = $envJson | & $pythonExe $enginePy 2>&1
    try{
        $resp = $result | ConvertFrom-Json
        $engineOk = $true
        if ($resp.health) { $ruleCount = $resp.health.active_rules } else { $ruleCount = 0 }
    }catch{}
}

Write-PhaseState -Phase "session_start" -Status "passed" -Data @{engine_ok=$engineOk.ToString();time=(Get-Date -Format "yyyy-MM-dd HH:mm:ss")}
Add-NoBOMLog -Path $auditLog -Message "$time [HOOK:SessionStart] ACTIVE engine=$engineOk rules=$ruleCount"

# 写初始状态文件，确保 PreToolUse 通过
$initialStateFile = Join-Path $g_pr "var\state\dgen_last_reply.json"
$initialState = @{ts=(Get-Date -Format "o");decision="allow";reason="session_start_init";winning_rule="";matched_count=0}
$initialJson = $initialState | ConvertTo-Json -Compress
[System.IO.File]::WriteAllText($initialStateFile, $initialJson, $script:utf8NoBOM)
Add-NoBOMLog -Path $auditLog -Message "$time [HOOK:SessionStart] STATE_FILE_WRITTEN"

# 重置 DGEN 标志：新对话全新开始，PreToolUse 自举 pending
$markerFile = Join-Path $g_pr "var\state\dgen_marker_pending.json"
if (Test-Path $markerFile) { Remove-Item $markerFile -Force }
Add-NoBOMLog -Path $auditLog -Message "$time [HOOK:SessionStart] MARKER_RESET for_new_session"

# 引擎状态上下文
$ctxFile = Join-Path $g_pr "var\state\diegin_context.json"
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


# 会话图片清理：在模型请求前移除 image_url 等二进制内容（防止 keysync/DeepSeek 反序列化失败）
try {
    $imgClean = Join-Path $g_pr "hooks\diegin_session_image_clean.ps1"
    if (Test-Path $imgClean) { & $imgClean }
    Add-NoBOMLog -Path $auditLog -Message "$time [HOOK:SessionStart] IMAGE-CLEAN done"
} catch {
    Add-NoBOMLog -Path $auditLog -Message "$time [HOOK:SessionStart] IMAGE-CLEAN error: $($_.Exception.Message)"
}


# 迭进引擎自检（防复发 P4）：每次会话启动验证 Mindol 可加载/双存储一致/无恒真规则/关键规则/无图片残留
try {
    $selfCheck = Join-Path $g_pr "engine\diegin_self_check.py"
    if (Test-Path $selfCheck) {
        $pyExe = Join-Path $g_pr "bin\.venv\Scripts\python.exe"
        if (-not (Test-Path $pyExe)) { $pyExe = "$env:USERPROFILE\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe" }
        if (Test-Path $pyExe) {
            $scOut = & $pyExe $selfCheck 2>&1
            $scExit = $LASTEXITCODE
            $scStatus = "unknown"
            try { $scJson = $scOut | ConvertFrom-Json; $scStatus = $scJson.status } catch {}
            Add-NoBOMLog -Path $auditLog -Message "$time [HOOK:SessionStart] SELF-CHECK status=$scStatus exit=$scExit"
            if ($scJson.baseline_regressions) {
                Add-NoBOMLog -Path $auditLog -Message "$time [HOOK:SessionStart] BASELINE regression_count=$($scJson.baseline_regressions.Count)"
            }
            if ($scStatus -ne "ok") {
                Add-NoBOMLog -Path $auditLog -Message "$time [HOOK:SessionStart] SELF-CHECK WARN: $($scOut -join ' ' | Select-Object -First 1)"
            }
        } else {
            Add-NoBOMLog -Path $auditLog -Message "$time [HOOK:SessionStart] SELF-CHECK skip (no python)"
        }
    }
} catch {
    Add-NoBOMLog -Path $auditLog -Message "$time [HOOK:SessionStart] SELF-CHECK error: $($_.Exception.Message)"
}


# [防再生] 启动自愈：清理原子写遗留的 tmp 残留（Write-AtomicFile 异常终止时可能残留）
$tmpFiles = @(Get-ChildItem -Path (Join-Path $g_pr "var\state") -Filter "*.tmp_*" -ErrorAction SilentlyContinue)
if ($tmpFiles.Count -gt 0) {
    foreach ($tf in $tmpFiles) {
        try { [System.IO.File]::Delete($tf.FullName) } catch {}
    }
    Add-NoBOMLog -Path $auditLog -Message "$time [HOOK:SessionStart] TMP-CLEANUP removed=$($tmpFiles.Count)"
} else {
    Add-NoBOMLog -Path $auditLog -Message "$time [HOOK:SessionStart] TMP-CLEANUP none"
}
exit 0
