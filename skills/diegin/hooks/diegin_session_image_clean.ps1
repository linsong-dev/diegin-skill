$script:utf8NoBOM = [System.Text.UTF8Encoding]::new($false)

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

# 读取/写入会话文件时使用 FileShare.ReadWrite，避免 Codex 应用瞬态占用导致静默失败
function Read-TextShare {
    param([string]$Path)
    for ($i=0; $i -lt 8; $i++) {
        try {
            $fs = [System.IO.File]::Open($Path, [System.IO.FileMode]::Open, [System.IO.FileAccess]::Read, [System.IO.FileShare]::ReadWrite)
            try {
                $sr = New-Object System.IO.StreamReader($fs, $script:utf8NoBOM)
                return $sr.ReadToEnd()
            } finally { $fs.Dispose() }
        } catch {
            if ($i -eq 7) { throw }
            Start-Sleep -Milliseconds 300
        }
    }
}

function Write-TextShare {
    param([string]$Path,[string]$Content)
    for ($i=0; $i -lt 8; $i++) {
        try {
            $fs = [System.IO.File]::Open($Path, [System.IO.FileMode]::Create, [System.IO.FileAccess]::Write, [System.IO.FileShare]::ReadWrite)
            try {
                $sw = New-Object System.IO.StreamWriter($fs, $script:utf8NoBOM)
                $sw.Write($Content); $sw.Flush()
            } finally { $fs.Dispose() }
            return
        } catch {
            if ($i -eq 7) { throw }
            Start-Sleep -Milliseconds 300
        }
    }
}

$pluginRoot = Split-Path -Parent (Split-Path -Parent $PSCommandPath)
$auditLog = Join-Path $pluginRoot "var\logs\diegin_audit.log"
$time = Get-Date -Format "yyyy-MM-dd HH:mm:ss.fff"
$pythonExe = Join-Path $pluginRoot "bin\.venv\Scripts\python.exe"
$enginePy = Join-Path $pluginRoot "engine\call_diegin.py"

# 查找会话文件（仅活动会话，排除备份/补丁副本）
$sessionsDir = if ($env:CODEX_HOME) { Join-Path $env:CODEX_HOME "sessions" } else { Join-Path (Split-Path $pluginRoot -Parent) "sessions" }
$allSessions = Get-ChildItem "$sessionsDir\*\*\*\*.jsonl" -ErrorAction SilentlyContinue |
    Where-Object { $_.Name -notlike "*.bak*" -and $_.Name -notlike "*.patched" -and $_.LastWriteTime -gt (Get-Date).AddHours(-24) } |
    Sort-Object LastWriteTime -Descending

if (-not $allSessions) {
    Add-NoBOMLog -Path $auditLog -Message "$time [IMAGE-PROTECT] no_sessions"
    exit 0
}

# 二进制内容类型：keysync/DeepSeek 桥接不支持，会触发 "unknown variant image_url" 反序列化错误
$binaryTypes = @('input_image','image_url','output_image','input_file','output_file','input_audio','output_audio','input_video','output_video')
$placeholder = "[Diegin: 图片/文件内容已移除，当前模型不支持image_url]"

function Test-BinaryPart {
    param($Part)
    if (-not $Part) { return $false }
    if ($Part -is [string]) { return $false }
    try { return $binaryTypes -contains $Part.type } catch { return $false }
}

$totalCleaned = 0
$failures = @()

foreach ($sessionFile in $allSessions) {
    $sessionPath = $sessionFile.FullName
    try {
        $content = Read-TextShare -Path $sessionPath
    } catch {
        $failures += "$($sessionFile.Name):locked"
        continue
    }
    # 快速过滤：无二进制标记则跳过
    $needleFound = $false
    foreach ($t in $binaryTypes) {
        if ($content.Contains('"' + $t + '"')) { $needleFound = $true; break }
    }
    if (-not $needleFound) { continue }

    $lines = $content -split "`n"
    $outLines = New-Object System.Collections.Generic.List[string]
    $lineChanged = $false

    foreach ($line in $lines) {
        $trimmed = $line.Trim()
        if ($trimmed -eq '') { $outLines.Add($line); continue }
        $obj = $null
        try { $obj = $line | ConvertFrom-Json } catch { $outLines.Add($line); continue }
        if (-not $obj -or -not $obj.payload) { $outLines.Add($line); continue }
        $payload = $obj.payload
        $pt = $payload.type
        $dirty = $false

        # 1) function_call_output：output 数组/对象含二进制 → 替换为纯文本字符串（与已验证的手工修复一致）
        if ($pt -eq 'function_call_output') {
            $out = $payload.output
            if ($out -is [System.Array]) {
                $hasBinary = $false
                foreach ($part in $out) { if (Test-BinaryPart $part) { $hasBinary = $true; break } }
                if ($hasBinary) { $payload.output = $placeholder; $dirty = $true }
            } elseif (Test-BinaryPart $out) {
                $payload.output = $placeholder
                $dirty = $true
            }
        }

        # 2) message content 数组：二进制 part → text part
        if ($payload.content -is [System.Array]) {
            $newContent = @()
            $contentDirty = $false
            foreach ($part in $payload.content) {
                if (Test-BinaryPart $part) {
                    $newContent += [pscustomobject]@{ type='text'; text=$placeholder }
                    $contentDirty = $true
                } else {
                    $newContent += $part
                }
            }
            if ($contentDirty) { $payload.content = $newContent; $dirty = $true }
        }

        if ($dirty) {
            $outLines.Add(($obj | ConvertTo-Json -Compress -Depth 100))
            $lineChanged = $true
        } else {
            $outLines.Add($line)
        }
    }

    if ($lineChanged) {
        $newContent = $outLines -join "`n"
        if ($content.EndsWith("`n") -and -not $newContent.EndsWith("`n")) { $newContent += "`n" }
        try {
            Write-TextShare -Path $sessionPath -Content $newContent
            # 写后验证：可解析 + 无二进制标记
            $verify = Read-TextShare -Path $sessionPath
            $verifyOk = $true
            foreach ($t in $binaryTypes) { if ($verify.Contains('"' + $t + '"')) { $verifyOk = $false; break } }
            $allParseOk = $true
            foreach ($vl in ($verify -split "`n")) {
                if ($vl.Trim() -eq '') { continue }
                try { $null = $vl | ConvertFrom-Json } catch { $allParseOk = $false }
            }
            if ($verifyOk -and $allParseOk) {
                Add-NoBOMLog -Path $auditLog -Message "$time [IMAGE-PROTECT] cleaned $($sessionFile.Name) (-$($content.Length - $newContent.Length)B) verified"
                $totalCleaned++
            } else {
                Add-NoBOMLog -Path $auditLog -Message "$time [IMAGE-PROTECT] WARN $($sessionFile.Name) write-verify failed (clean=$verifyOk parse=$allParseOk)"
            }
        } catch {
            Add-NoBOMLog -Path $auditLog -Message "$time [IMAGE-PROTECT] WARN $($sessionFile.Name) write failed: $($_.Exception.Message)"
        }
    }
}

if ($totalCleaned -gt 0) {
    $extra = ""
    if ($failures.Count -gt 0) { $extra = " (skipped locked: $($failures -join ','))" }
    Add-NoBOMLog -Path $auditLog -Message "$time [IMAGE-PROTECT] total: cleaned $totalCleaned files$extra"
    # [P0-20260826] 修复误伤：清理会话图片/二进制内容是正常维护动作，不是错误，
    # 不再 record_error（此前导致 image_url 升级熔断 + override 阻断所有命令）
} else {
    $msg = if ($failures.Count -gt 0) { "clean_noop (skipped locked: $($failures -join ','))" } else { "clean_noop" }
    Add-NoBOMLog -Path $auditLog -Message "$time [IMAGE-PROTECT] $msg"
}

exit 0
