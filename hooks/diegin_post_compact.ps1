$script:utf8NoBOM = [System.Text.UTF8Encoding]::new($false)
# [PostCompact 2026-09-13] 上下文压缩后「补投」行动时刻记忆（迁移事故配套）
#
# 平台契约（codex.exe 内嵌 schema: post-compact.command.output）**只允许**四个字段：
#     continue / stopReason / suppressOutput / systemMessage
# —— 没有 hookSpecificOutput，即 PostCompact 通道**无法**注入模型上下文。故本钩子不注入、只重置闸门，
#    由下一个安全边界补投（本次实测：PreToolUse 的 additionalContext 会被平台插在 function_call 与
#    function_call_output 之间 → 上游 400 "No tool output found"，当日 21 次。补投点必须落在回合边界）。
#
# 本钩子做三件事（全部是本地状态文件操作，不写 stdout 注入）：
#   ① 清除 pre_reply_action_memory_seen.json
#      → 下一次 UserPromptSubmit(diegin_pre_reply.ps1) 重新投递行动记忆（该通道已实测可达）
#   ② 清除本会话在 inject_fingerprint.json 里的条目
#      → 防止 600 秒指纹去重把补投折叠成 "[DGEN] PASS（迭进上下文未变化，跳过重复注入）"
#   ③ 写 action_memory_rearm.json 留痕（可观测 + 供后续扩展）
#
# 实测依据：会话 01a0989b rollout 中 "compacted" 记录 @2026-09-13T03:10:22（11:10 本地），
#   该轮注入随压缩前的历史一并被摘要掉 —— 本钩子即为此场景而设。

function Write-AtomicFile {
    param([string]$Path,[string]$Content)
    # [C2] 原子写：tmp+Replace(真实备份) 防读半截；失败兜底 Delete+Move；任何情况清理 tmp 防残留
    $tmp = $Path + ".tmp_" + [System.Guid]::NewGuid().ToString("N")
    $bak = $Path + ".bak"
    [System.IO.File]::WriteAllText($tmp, $Content, $script:utf8NoBOM)
    try {
        if ([System.IO.File]::Exists($Path)) {
            [System.IO.File]::Replace($tmp, $Path, $bak)
            if ([System.IO.File]::Exists($bak)) { [System.IO.File]::Delete($bak) }
        } else {
            [System.IO.File]::Move($tmp, $Path)
        }
    } catch {
        # 兜底：非原子但保证不失败不残留
        if ([System.IO.File]::Exists($Path)) { [System.IO.File]::Delete($Path) }
        [System.IO.File]::Move($tmp, $Path)
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
        if(Test-Path $Path){
            $len=(Get-Item $Path).Length
            if($len -gt 8388608){
                $arc = $Path + ".1"
                if(Test-Path $arc){[System.IO.File]::Delete($arc)}
                [System.IO.File]::Move($Path,$arc)
            }
        }
        [System.IO.File]::AppendAllText($Path,"$ts $Message`r`n",$script:utf8NoBOM)
    } finally {
        $mtx.ReleaseMutex()
    }
}

$g_scriptDir = if ($PSCommandPath) { Split-Path $PSCommandPath -Parent } else { $null }
$g_pluginRoot = if ($g_scriptDir) { Split-Path $g_scriptDir -Parent } else { $null }
$g_pr = if ($g_pluginRoot) { $g_pluginRoot } else { $env:CODEX_HOME + "\diegin" }

$stateDir = Join-Path $g_pr "var\state"
$auditLog = Join-Path $g_pr "var\logs\diegin_audit.log"
$time = Get-Date -Format "yyyy-MM-dd HH:mm:ss.fff"

# ---- 读取 hook 输入（PostCompact 必带 session_id/turn_id/trigger/cwd）----
$sessionId = ""; $trigger = ""; $turnId = ""; $cwd = ""
try {
    $stdin = [System.IO.StreamReader]::new([System.Console]::OpenStandardInput()).ReadToEnd()
    if ($stdin) {
        $hookInput = $stdin | ConvertFrom-Json
        if ($hookInput.session_id) { $sessionId = [string]$hookInput.session_id }
        if ($hookInput.trigger)    { $trigger   = [string]$hookInput.trigger }
        if ($hookInput.turn_id)    { $turnId    = [string]$hookInput.turn_id }
        if ($hookInput.cwd)        { $cwd       = [string]$hookInput.cwd }
    }
} catch {
    Add-NoBOMLog -Path $auditLog -Message "$time [HOOK:PostCompact] stdin_parse_error=$($_.Exception.Message)"
}

Add-NoBOMLog -Path $auditLog -Message "$time [HOOK:PostCompact] FIRED trigger=$trigger session=$sessionId turn=$turnId"

# ---- ① 重置行动记忆投递闸门 ----
try {
    $seenFile = Join-Path $stateDir "pre_reply_action_memory_seen.json"
    if (Test-Path $seenFile) {
        $prevKey = ""; $prevSess = ""
        try {
            $sj = Get-Content $seenFile -Raw -Encoding UTF8 | ConvertFrom-Json
            if ($sj) { $prevKey = [string]$sj.key; $prevSess = [string]$sj.session_id }
        } catch {}
        [System.IO.File]::Delete($seenFile)
        Add-NoBOMLog -Path $auditLog -Message "$time [HOOK:PostCompact] reset_action_memory_seen prev_key=$prevKey prev_session=$prevSess"
    } else {
        Add-NoBOMLog -Path $auditLog -Message "$time [HOOK:PostCompact] reset_action_memory_seen already_absent"
    }
} catch {
    Add-NoBOMLog -Path $auditLog -Message "$time [HOOK:PostCompact] reset_action_memory_seen_error=$($_.Exception.Message)"
}

# ---- ② 清除本会话注入指纹（防 600 秒去重把补投折叠掉）----
try {
    $fpFile = Join-Path $stateDir "inject_fingerprint.json"
    if ($sessionId -and (Test-Path $fpFile)) {
        $fpTable = @{}
        try {
            $fpObj = Get-Content $fpFile -Raw -Encoding UTF8 | ConvertFrom-Json
            if ($fpObj) { $fpObj.PSObject.Properties | ForEach-Object { $fpTable[$_.Name] = $_.Value } }
        } catch {}
        if ($fpTable.ContainsKey($sessionId)) {
            $fpTable.Remove($sessionId)
            Write-AtomicFile -Path $fpFile -Content ($fpTable | ConvertTo-Json -Compress)
            Add-NoBOMLog -Path $auditLog -Message "$time [HOOK:PostCompact] reset_inject_fingerprint session=$sessionId"
        } else {
            Add-NoBOMLog -Path $auditLog -Message "$time [HOOK:PostCompact] reset_inject_fingerprint not_present"
        }
    }
} catch {
    Add-NoBOMLog -Path $auditLog -Message "$time [HOOK:PostCompact] reset_inject_fingerprint_error=$($_.Exception.Message)"
}

# ---- ③ 留痕（rearm 标记，可观测）----
try {
    $rearm = @{session_id=$sessionId; trigger=$trigger; turn_id=$turnId; cwd=$cwd; ts=(Get-Date -Format "o")}
    Write-AtomicFile -Path (Join-Path $stateDir "action_memory_rearm.json") -Content ($rearm | ConvertTo-Json -Compress)
    Add-NoBOMLog -Path $auditLog -Message "$time [HOOK:PostCompact] rearm_written trigger=$trigger"
} catch {
    Add-NoBOMLog -Path $auditLog -Message "$time [HOOK:PostCompact] rearm_write_error=$($_.Exception.Message)"
}

# ---- 输出：schema 允许的最小合法响应（不注入任何上下文）----
try {
    $out = [ordered]@{ continue = $true; suppressOutput = $true } | ConvertTo-Json -Compress
    Write-Output $out
} catch {}

exit 0
