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
    Write-AtomicFile -Path $g_sf -Content ($s|ConvertTo-Json -Depth 5)
}

$g_scriptDir = if ($PSCommandPath) { Split-Path $PSCommandPath -Parent } else { $null }
$g_pluginRoot = if ($g_scriptDir) { Split-Path $g_scriptDir -Parent } else { $null }
$g_fallback_root = if ($g_pluginRoot) { $g_pluginRoot } else { $env:CODEX_HOME + "\diegin" }
$g_psPath = $PSCommandPath
if ([string]::IsNullOrEmpty($g_psPath)) { $g_psPath = Join-Path $g_fallback_root "hooks\diegin_pre_reply.ps1" }
$g_pr = Split-Path -Parent (Split-Path -Parent $g_psPath)
if ([string]::IsNullOrEmpty($g_pr)) { $g_pr = $g_fallback_root }

$g_sf=Join-Path $g_pr "var\state\phase_state.json"
$auditLog = Join-Path $g_pr "var\logs\diegin_audit.log"
$time = Get-Date -Format "yyyy-MM-dd HH:mm:ss.fff"
$pythonExe = $env:DGEN_PYTHON; if (-not $pythonExe) { $pythonExe = "$env:USERPROFILE\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe" }
$enginePy = Join-Path $g_pr "engine\call_diegin.py"
$stateDir = Join-Path $g_pr "var\state"

Add-NoBOMLog -Path $auditLog -Message "$time [HOOK:UserPromptSubmit] FIRED"

# 一二不过三：读阻断文件
$overrideFile = Join-Path $stateDir "dgen_override.json"
$blockedType = ""
$now = Get-Date
$overrideTTL = [TimeSpan]::FromHours(72)
if (Test-Path $overrideFile) {
    try {
        $override = Get-Content $overrideFile -Raw -Encoding UTF8 | ConvertFrom-Json
        $blockedType = $override.blocked_error_type
        if ($blockedType -and $override.blocked_at) {
            try {
                $blockedAt = [DateTime]::ParseExact($override.blocked_at, "o", $null)
                $age = $now - $blockedAt
                if ($age -gt $overrideTTL) {
                    $nullJson = @{blocked_error_type="";strike_count=0;blocked_at=$null;last_detail="";decision="allow"} | ConvertTo-Json
                    [System.IO.File]::WriteAllText($overrideFile, $nullJson, $script:utf8NoBOM)
                    $blockedType = ""
                }
            } catch {}
        }
    } catch {}
}
if ($blockedType) {
    $strikeCount = 0
    $reason = ""
    try { $strikeCount = $override.strike_count; $reason = $override.reason } catch {}
    Add-NoBOMLog -Path $auditLog -Message "$time [HOOK:OVERRIDE] BLOCK prompt type=$blockedType strike=$strikeCount"
    Write-Output ""
    Write-Output "⚠️ [迭进] 收到阻断请求 | 类型: $blockedType（已触发 ${strikeCount}次）"
    if ($reason) { Write-Output "   原因: $reason" }
    Write-Output ""
    Write-PhaseState -Phase "pre_reply" -Status "override_blocked"
    exit 1
}

function Write-PreReplyEngineError {
    param([string]$Detail,[string]$UserMessage)
    Add-NoBOMLog -Path $auditLog -Message "$time [HOOK:DGEN-ENGINE-ERROR] $Detail"
    Write-PhaseState -Phase "pre_reply" -Status "engine_error" -Data @{ts=(Get-Date -Format "o")}
    $script:preReplyEngineError = $true
    Write-Output ""
    Write-Output "⚠️ [迭进] $UserMessage"
    Write-Output ""
}

# ---- 一次调用完成所有预检 ----
$preReplyEngineError = $false
try {
    # 读取 stdin（Codex 传入的用户 prompt）
    $stdin = [System.IO.StreamReader]::new([System.Console]::OpenStandardInput()).ReadToEnd()
    $hookInput = $stdin | ConvertFrom-Json
    $prompt = $hookInput.prompt

    if (Test-Path $pythonExe) {
        # 构建输入 JSON，传递给 pre_reply 模式
        $ctx = [ordered]@{
            prompt=$prompt
            turn_id=$hookInput.turn_id
            blocked_error_type=$blockedType
        }
        $ctxJson = $ctx | ConvertTo-Json -Compress

        # 单次 Python 调用，完成所有操作
        $rawOutput = $ctxJson | & $pythonExe $enginePy pre_reply 2>&1
        $lastExit = $LASTEXITCODE

        if ($lastExit -ne 0) {
            # [A1] 区分引擎故障(Traceback)与引擎裁决(block)：故障放行但显式标注
            if ($rawOutput -match "Traceback|AttributeError|TypeError|KeyError|ImportError|ModuleNotFoundError") {
                Write-PreReplyEngineError -Detail "pre_reply 引擎异常 exit=$lastExit" -UserMessage "引擎异常（预检未执行），本次放行但状态未验证"
            } else {
                # 引擎裁决为 block，输出阻断信息
                Write-Output $rawOutput
                Write-PhaseState -Phase "pre_reply" -Status "engine_blocked" -Data @{ts=(Get-Date -Format "o")}
                exit 1
            }
        } else {
            # allow 路径：解析 JSON，提取显示文本，输出
            try {
                $result = $rawOutput | ConvertFrom-Json
                $displayText = $result.display_text
                Write-Output $displayText
                Add-NoBOMLog -Path $auditLog -Message "$time [HOOK:DGEN-CHECK] OK decision=allow matched=$($result.matched_count)"
            } catch {
                # [A1] JSON 解析失败 = 引擎输出异常，显式标注（不伪装 allow）
                Write-PreReplyEngineError -Detail "pre_reply 输出非JSON" -UserMessage "引擎输出异常（预检未验证），本次放行"
            }
        }
    } else {
        # [A1] python 缺失 = 引擎不可用，显式标注
        Write-PreReplyEngineError -Detail "pre_reply python 缺失" -UserMessage "引擎不可用（python 缺失），本次放行但状态未验证"
    }
} catch {
    Write-PreReplyEngineError -Detail "EXCEPTION $_" -UserMessage "预检脚本异常，本次放行但状态未验证"
}


# 会话图片清理：在模型请求前移除 image_url 等二进制内容（防止 keysync/DeepSeek 反序列化失败）
try {
    $imgClean = Join-Path $g_pr "hooks\diegin_session_image_clean.ps1"
    if (Test-Path $imgClean) { & $imgClean }
    Add-NoBOMLog -Path $auditLog -Message "$time [HOOK:UserPromptSubmit] IMAGE-CLEAN done"
} catch {
    Add-NoBOMLog -Path $auditLog -Message "$time [HOOK:UserPromptSubmit] IMAGE-CLEAN error: $($_.Exception.Message)"
}

if (-not $preReplyEngineError) { Write-PhaseState -Phase "pre_reply" -Status "completed" -Data @{ts=(Get-Date -Format "o")} }
