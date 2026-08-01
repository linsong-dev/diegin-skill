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

$pluginRoot = Split-Path -Parent (Split-Path -Parent $PSCommandPath)
$auditLog = Join-Path $pluginRoot "var\logs\diegin_audit.log"
$pythonExe = Join-Path $pluginRoot "bin\.venv\Scripts\python.exe"
$enginePy = Join-Path $pluginRoot "engine\call_diegin.py"
$time = Get-Date -Format "yyyy-MM-dd HH:mm:ss.fff"

# 查找会话文件
$sessionsDir = if ($env:CODEX_HOME) { Join-Path $env:CODEX_HOME "sessions" } else { Join-Path (Split-Path $pluginRoot -Parent) "sessions" }
$allSessions = Get-ChildItem "$sessionsDir\*\*\*\*.jsonl" -ErrorAction SilentlyContinue | Where-Object { $_.LastWriteTime -gt (Get-Date).AddHours(-24) } | Sort-Object LastWriteTime -Descending

if (-not $allSessions) {
    Add-NoBOMLog -Path $auditLog -Message "$time [IMAGE-PROTECT] no_sessions"
    exit 0
}

$totalCleaned = 0

foreach ($sessionFile in $allSessions) {
    $sessionPath = $sessionFile.FullName
    try {
        $content = [System.IO.File]::ReadAllText($sessionPath, $script:utf8NoBOM)
    } catch { continue }

    if (-not $content.Contains('"input_image"')) { continue }

    # 正则替换：{"type":"input_image",...,"detail":"..."} → 文本占位
    $newContent = $content -replace '"type":"input_image"[^}]*"detail":"[^"]*"', '"type":"text","text":"[Diegin: 图片已移除，当前模型不支持image_url]"'
    if ($newContent -ne $content) {
        $diff = [Math]::Max(0, $content.Length - $newContent.Length)
        [System.IO.File]::WriteAllText($sessionPath, $newContent, $script:utf8NoBOM)
        Add-NoBOMLog -Path $auditLog -Message "$time [IMAGE-PROTECT] cleaned $($sessionFile.Name) (-${diff}B)"
        $totalCleaned++
    }
}

if ($totalCleaned -gt 0) {
    Add-NoBOMLog -Path $auditLog -Message "$time [IMAGE-PROTECT] total: cleaned $totalCleaned files"

    # 记录到一二不过三
    if (Test-Path $pythonExe) {
        & $pythonExe $enginePy record_error "image_url" "session_image_clean: 清理了${totalCleaned}个会话文件" "high" 2>&1 | Out-Null
    }
} else {
    Add-NoBOMLog -Path $auditLog -Message "$time [IMAGE-PROTECT] clean_noop"
}

exit 0
