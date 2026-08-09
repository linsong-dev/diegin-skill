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



function Write-DGENContextAndExit {
    param([int]$ExitCode=1)
    $ctxTool = Join-Path $script:g_pr "var\state\diegin_pre_tool_context.json"
    $dc="unknown"; $dm=0; $tn="unknown"
    if (Test-Path $script:gateFile) {
        try { $g = Get-Content $script:gateFile -Raw -Encoding UTF8 | ConvertFrom-Json; $dc = $g.decision; $dm = $g.matched_count } catch { }
    }
    try { $tn = $script:toolName } catch { }
    $toolCtxStr = '{"ts":"' + (Get-Date -Format "o") + '","decision":"' + $dc + '","matched_count":' + $dm + ',"tool_name":"' + $tn + '"}'
    try { [System.IO.File]::WriteAllText($ctxTool, $toolCtxStr, $script:utf8NoBOM) } catch { }
    exit $ExitCode
}

function Write-DGENStatusFile {
    param([string]$Status,[string]$Rules,[string]$Decision,[string]$Matched)
    try {
        $sf = Join-Path $script:g_pr "var\state\dgen_status.txt"
        $s = "=== DGEN STATUS ==="
        $s += "`nSTATUS: $Status"
        $s += "`nRULES: $Rules"
        $s += "`nDECISION: $Decision"
        $s += "`nMATCHED: $Matched"
        $s += "`nTS: " + (Get-Date -Format "o")
        $s += "`n=================="
        Write-AtomicFile -Path $sf -Content $s
    } catch {}
}

$g_scriptDir = if ($PSCommandPath) { Split-Path $PSCommandPath -Parent } else { $null }
$g_pluginRoot = if ($g_scriptDir) { Split-Path $g_scriptDir -Parent } else { $null }
$g_fallback_root = if ($g_pluginRoot) { $g_pluginRoot } else { $env:CODEX_HOME + "\diegin" }
$g_psPath = $PSCommandPath
if ([string]::IsNullOrEmpty($g_psPath)) { $g_psPath = Join-Path $g_fallback_root "hooks\diegin_pre_tool.ps1" }
$g_pr = Split-Path -Parent (Split-Path -Parent $g_psPath)
if ([string]::IsNullOrEmpty($g_pr)) { $g_pr = $g_fallback_root }
$g_sf=Join-Path $g_pr "var\state\phase_state.json"

$auditLog = Join-Path $g_pr "var\logs\diegin_audit.log"
$time = Get-Date -Format "yyyy-MM-dd HH:mm:ss.fff"
$pythonExe = $env:DGEN_PYTHON; if (-not $pythonExe) { $pythonExe = "$env:USERPROFILE\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe" }
$enginePy = Join-Path $g_pr "engine\call_diegin.py"
$stateDir = Join-Path $g_pr "var\state"
$gateFile = Join-Path $g_pr "var/state/dgen_last_reply.json"
$markerFile = Join-Path $g_pr "var\state\dgen_marker_pending.json"

Add-NoBOMLog -Path $auditLog -Message "$time [HOOK:PreToolUse] FIRED"
 

# ========== 一二不过三：读阻断文件（实时拦截·支持数组格式）==========
function Test-DieginOverride {
    $overridesPath = Join-Path $script:stateDir "dgen_overrides.json"
    $legacyPath = Join-Path $script:stateDir "dgen_override.json"
    $entries = @()
    $now = Get-Date
    $overrideTTL = [TimeSpan]::FromHours(72)   # TTL: 3天
    $cleaned = $false
    if (Test-Path $overridesPath) {
        try {
            $data = Get-Content $overridesPath -Raw -Encoding UTF8 | ConvertFrom-Json
            if ($data -is [array]) {
                # [P0-20260806] 闭环: 对应错误类型在 strikes_db 中 fix_status=verified → 跳过该 override（修复已验证不再 72h 残留阻断）
                $strikes = $null
                try { $strikes = Get-Content (Join-Path $script:stateDir "strikes_db.json") -Raw -Encoding UTF8 | ConvertFrom-Json } catch {}
                $entries = @($data | Where-Object {
                    # [P0-20260806] verified 跳过前置：避免 blocked_at 无时区 ParseExact 异常导致跳过失效（TTL 自愈也因此失效）
                    try {
                        $errType = [string]$_.blocked_error_type
                        if ($errType -and $strikes -and $strikes.$errType -and $strikes.$errType.fix_status -eq "verified") {
                            Add-NoBOMLog -Path $auditLog -Message "$time [HOOK:OVERRIDE] SKIP verified type=$errType"
                            return $false
                        }
                    } catch {}
                    if ($_.blocked_at) {
                        try {
                            $blockedAt = [DateTime]::ParseExact($_.blocked_at, 'o', $null)
                            $age = $now - $blockedAt
                            if ($age -gt $overrideTTL) { $cleaned = $true; return $false }
                        } catch { return $true }
                    }
                    return $true
                })
                if ($entries.Count -eq 0 -and @($data).Count -gt 0) {
                    try {
                        [System.IO.File]::WriteAllText($overridesPath, (@() | ConvertTo-Json -Compress), $script:utf8NoBOM)
                        Add-NoBOMLog -Path $auditLog -Message "$time [HOOK:OVERRIDE] CLEANED all_verified"
                    } catch {}
                }
            } elseif ($data -is [pscustomobject]) { $entries = @($data) }
        } catch {}
    }
    # 自愈：全部过期则自动清空归档
    if ($cleaned) {
        try {
            $emptyJson = @() | ConvertTo-Json -Compress
            [System.IO.File]::WriteAllText($overridesPath, $emptyJson, $script:utf8NoBOM)
        } catch {}
    }
    if ($entries.Count -eq 0 -and (Test-Path $legacyPath)) {
        try {
            $data = Get-Content $legacyPath -Raw -Encoding UTF8 | ConvertFrom-Json
            if ($data -and $data.blocked_error_type) {
                if ($data.blocked_at) {
                    try {
                        $blockedAt = [DateTime]::ParseExact($data.blocked_at, 'o', $null)
                        $age = $now - $blockedAt
                        if ($age -gt $overrideTTL) {
                            $nullJson = @{blocked_error_type="";strike_count=0;blocked_at=$null;last_detail="";decision="allow"} | ConvertTo-Json
                            [System.IO.File]::WriteAllText($legacyPath, $nullJson, $script:utf8NoBOM)
                            return @()
                        }
                    } catch {}
                }
                $entries = @($data)
            }
        } catch {}
    }
    return $entries
}

# 检查所有阻断条目：任何未过期的条目都触发阻断
$overrideEntries = Test-DieginOverride
$blockedType = ""
$strikeCount = 0
$reason = ""
$escalated = $false

foreach ($entry in $overrideEntries) {
    $bt = $entry.blocked_error_type
    if ($bt) {
        if (-not $blockedType) { $blockedType = $bt }
        $strikeCount = [Math]::Max($strikeCount, [int]($entry.strike_count))
        $reason = $entry.reason
        if ($entry.escalated) { $escalated = $true }
        Add-NoBOMLog -Path $auditLog -Message "$time [HOOK:OVERRIDE] FOUND type=$bt strike=$($entry.strike_count) escalated=$($entry.escalated)"
    }
}

if ($blockedType) {
    Add-NoBOMLog -Path $auditLog -Message "$time [HOOK:OVERRIDE] BLOCK type=$blockedType strike=$strikeCount escalated=$escalated"
    Write-DGENStatusFile -Status "OVERRIDE_BLOCKED" -Rules "0" -Decision "block" -Matched "0"
    Write-Output "[一二不过三] 阻断: 错误类型 '$blockedType' 已被系统拦截（已触发 ${strikeCount}次）"
    Write-Output "  $reason"
    Write-Output ""
    Write-Output "[DGEN] OVERRIDE_BLOCK"
    exit 1
}

# ============================================================
# 第1步：读取 stdin，获取命令详情
# ============================================================
$toolName = "unknown"
$command = ""
try {
    $stdin = [System.IO.StreamReader]::new([System.Console]::OpenStandardInput()).ReadToEnd()
    if ($stdin) {
        $hookInput = $stdin | ConvertFrom-Json
        $toolName = $hookInput.tool_name
        $toolInput = $hookInput.tool_input
        if ($toolInput) {
            if ($toolInput.command) { $command = $toolInput.command }
            elseif ($toolInput.tool_input -and $toolInput.tool_input.command) { $command = $toolInput.tool_input.command }
        }
    }
} catch {}

Add-NoBOMLog -Path $auditLog -Message "$time [HOOK:PreToolUse] tool=$toolName cmd_len=$($command.Length)"

# ============================================================
# 第2步：DGEN 标志强制检查（自举 + 过期重置）
#   marker 生命周期:
#     无 marker → 自动创建"pending"
#     pending → 检查命令含 [DGEN STATUS: xxx] 才放行
#     allowed → 等待 PostToolUse 升级
#     verified → 检查是否过期（5分钟）→ 过期则重置 pending
# ============================================================
$markerStatus = ""
$markerMissing = $false  # 由标记检查设置，引擎据此裁决
$markerTs = $null
$markerHas = $false      # [B方案] 本次命令是否含 [DGEN] 标记（验证闭环输入）
if (Test-Path $markerFile) {
    try {
        $m = Get-Content $markerFile -Raw -Encoding UTF8 | ConvertFrom-Json
        $markerStatus = $m.status
        if ($m.ts) { $markerTs = $m.ts }
    } catch {}
} else {
    # [B方案] 自举：无 marker 文件 → 创建 pending，启动标记状态机
    try {
        $newMarker = @{status="pending";turn_id="auto";ts=(Get-Date -Format "o")}
        [System.IO.File]::WriteAllText($markerFile, ($newMarker | ConvertTo-Json -Compress), $script:utf8NoBOM)
        $markerStatus = "pending"
        Add-NoBOMLog -Path $auditLog -Message "$time [HOOK:DGEN-MARKER] BOOTSTRAP created_pending"
    } catch {
        Add-NoBOMLog -Path $auditLog -Message "$time [HOOK:DGEN-MARKER] BOOTSTRAP_ERROR $($_.Exception.Message)"
    }
}

# verified 过期检查：超过5分钟重置为 pending
if ($markerStatus -eq "verified" -and $markerTs) {
    try {
        $age = [DateTime]::Now - [DateTime]::Parse($markerTs)
        if ($age.TotalSeconds -gt 300) {
            $markerState = @{status="pending";turn_id="expired";ts=(Get-Date -Format "o")}
            [System.IO.File]::WriteAllText($markerFile, ($markerState | ConvertTo-Json -Compress), $script:utf8NoBOM)
            $markerStatus = "pending"
            Add-NoBOMLog -Path $auditLog -Message "$time [HOOK:DGEN-MARKER] EXPIRED verified_gt5min_reset_pending"
        } else {
            Add-NoBOMLog -Path $auditLog -Message "$time [HOOK:DGEN-MARKER] VERIFIED_SKIP fresh_verified_no_check"
        }
    } catch {}
}

if ($markerStatus -eq "") {
    # 无 dgen_marker_pending.json → 非迭进线程，跳过标记检查
    $markerStatus = "skip"
    Add-NoBOMLog -Path $auditLog -Message "$time [HOOK:DGEN-MARKER] SKIP no_marker_file"
}

if ($markerStatus -eq "pending") {
    # [A方案] 审计模式：不因缺标记阻断，引擎裁决由后面的 Python pre_check 处理
    # [B方案] verify 闭环：检查命令是否含 [DGEN] 标记 → 记录验证结果（绝不阻断）
    try {
        $markerHas = ($command -match "\[DGEN\]")
        $verifyFile = Join-Path $stateDir "dgen_verify_result.json"
        $vRec = @{ts=(Get-Date -Format "o");tool=$toolName;has_marker=$markerHas;status="record_only";decision="allow"}
        [System.IO.File]::WriteAllText($verifyFile, ($vRec | ConvertTo-Json -Compress), $script:utf8NoBOM)
        if ($markerHas) {
            Add-NoBOMLog -Path $auditLog -Message "$time [HOOK:DGEN-VERIFY] marker_found tool=$toolName record_only"
        } else {
            Add-NoBOMLog -Path $auditLog -Message "$time [HOOK:DGEN-VERIFY] marker_missing tool=$toolName record_only_no_block"
        }
    } catch {
        Add-NoBOMLog -Path $auditLog -Message "$time [HOOK:DGEN-VERIFY] RECORD_ERROR $($_.Exception.Message)"
    }
    $newMarker = @{status="allowed";turn_id="auto";ts=(Get-Date -Format "o")}
    [System.IO.File]::WriteAllText($markerFile, ($newMarker | ConvertTo-Json -Compress), $script:utf8NoBOM)
    Add-NoBOMLog -Path $auditLog -Message "$time [HOOK:DGEN-MARKER] AUDIT_MODE skip_marker_check tool=$toolName"
}

# ============================================================
# 第3步：Soft Gate 状态检查
# ============================================================
function Check-StateFile($fp) {
    if (-not (Test-Path $fp)) { return $null }
    try { $raw=[System.IO.File]::ReadAllText($fp,$script:utf8NoBOM); $s=$raw|ConvertFrom-Json
        $age=[DateTime]::Now-[DateTime]::Parse($s.ts)
        if($age.TotalSeconds -gt 120) { return $null }
        # [v3.6.6] 自阻断修复：source=pre_tool 的记录是本次钩子自己写的引擎裁决，
        # 已通过 exit 1 生效；relay 仅对 pre_reply 的决策生效，避免 120 秒幽灵阻断
        if($s.source -eq "pre_tool") { return $null }
        if($s.decision -in @("block","iron_wall_block")) { return $s }
    } catch{}; return $null
}

if (-not (Test-Path $gateFile)) {
    $initState = @{ts=(Get-Date -Format "o");decision="allow";reason="pre_tool_auto_init";winning_rule="";matched_count=0}
    [System.IO.File]::WriteAllText($gateFile, ($initState | ConvertTo-Json -Compress), $script:utf8NoBOM)
    Add-NoBOMLog -Path $auditLog -Message "$time [HOOK:DGEN-GATE] AUTO_INIT"
}

$replyFile = Join-Path $stateDir "dgen_last_reply.json"
$replyState = Check-StateFile $replyFile
if ($replyState) {
    Add-NoBOMLog -Path $auditLog -Message "$time [HOOK:DGEN-BLOCK-RELAY] $($replyState.reason)"
    Write-Error ("DGEN_BLOCK|reason=" + $replyState.reason + "|rule=pre_reply_relay")
    Write-DGENContextAndExit -ExitCode 1
}

# 一二不过三：检查数组+旧格式（重用函数）
$overrideEntries = Test-DieginOverride
$blockedType = ""
foreach ($entry in $overrideEntries) {
    $bt = $entry.blocked_error_type
    if ($bt) {
        if (-not $blockedType) { $blockedType = $bt }
        Add-NoBOMLog -Path $auditLog -Message "$time [HOOK:DGEN-BLOCK-OVERRIDE] type=$bt strike=$($entry.strike_count) escalated=$($entry.escalated)"
    }
}
if ($blockedType) {
    Write-Error ("DGEN_BLOCK|reason=" + $overrideEntries[0].reason + "|rule=ai_override")
    Write-DGENContextAndExit -ExitCode 1
}

# ============================================================
# 第4步：引擎检查 + 写状态文件供 AI 读取
# ============================================================
$finalDecision = "allow"
$finalMatched = 0
$finalRule = ""
$activeRules = "?"
$engineError = $false
try {
    if (Test-Path $pythonExe) {
        $ctx = [ordered]@{
            task_type="pre_tool"
            tool_name=$toolName
            blocked_error_type=$blockedType
            marker_missing=$false
            command=$command
            text=$command
            hook_event_name="PreToolUse"
        }
        $ctxJson = $ctx | ConvertTo-Json -Compress -Depth 3
        $checkResult = $null
        for ($_attempt = 1; $_attempt -le 3; $_attempt++) {
            $rawOutput = $ctxJson | & $pythonExe $enginePy check 2>&1
            try { $checkResult = $rawOutput | ConvertFrom-Json } catch { $checkResult = $null }
            if ($null -ne $checkResult -and -not [string]::IsNullOrEmpty($checkResult.decision)) { break }
            if ($_attempt -lt 3) {
                Add-NoBOMLog -Path $auditLog -Message "$time [HOOK:DGEN-RETRY] check attempt=$_attempt"
                Start-Sleep -Milliseconds 300
            }
        }
        if ($null -eq $checkResult -or [string]::IsNullOrEmpty($checkResult.decision)) {
            $engineError = $true
            # v3.8.3: fail-open 补异常详情日志，便于定位引擎预检失败根因
            $errDetail = ($rawOutput -join ' ')
            if ([string]::IsNullOrWhiteSpace($errDetail)) { $errDetail = '(no output)' }
            if ($errDetail.Length -gt 500) { $errDetail = $errDetail.Substring(0, 500) + '...(truncated)' }
            Add-NoBOMLog -Path $auditLog -Message ($time + ' [HOOK:DGEN-ENGINE-ERROR] 引擎异常，本次放行但状态未验证 | python=' + $pythonExe + ' | output=' + $errDetail)
        } else {
            $finalDecision = $checkResult.decision
            $finalMatched = $checkResult.matched_interceptions
            $finalRule = $checkResult.winning_rule_id

            $s2=@{ts=(Get-Date -Format "o");decision=$finalDecision;reason=$checkResult.reason;winning_rule=$finalRule;matched_count=$finalMatched;source="pre_tool"}
            [System.IO.File]::WriteAllText($replyFile,($s2|ConvertTo-Json -Compress),$script:utf8NoBOM)

            if($finalDecision -in @("block","iron_wall_block")){
                Add-NoBOMLog -Path $auditLog -Message "$time [HOOK:DGEN-BLOCK] rule=$finalRule"
                $blockRule = $finalRule
                if ([string]::IsNullOrEmpty($blockRule)) { $blockRule = "unknown" }
        Write-Output ("")
        Write-Output ("⚠️ [迭进] 规则阻断 | 规则: " + $blockRule + " | 原因: " + $checkResult.reason)
        Write-Output ("")
                Write-Error ("DGEN_BLOCK|reason=" + $checkResult.reason + "|rule=" + $blockRule)
                Write-DGENStatusFile -Status "BLOCKED" -Rules $activeRules -Decision $finalDecision -Matched $finalMatched
                Write-DGENContextAndExit -ExitCode 1
            }
            
            # 读取活跃规则数
            try { $h = & $pythonExe $enginePy health 2>&1 | ConvertFrom-Json; $activeRules = $h.active_rules } catch {}
            
            Add-NoBOMLog -Path $auditLog -Message "$time [HOOK:DGEN-ALLOW] decision=$finalDecision matched=$finalMatched"
            # v3.8 攻七强化 Q1: 建议注入（高置信度模式优先推荐采用）
            $sugText = ""
            $priorityText = ""
            $priorityPatternId = ""
            try {
                if ($checkResult.suggestions -and $checkResult.suggestions.Count -gt 0) {
                    $sugLines = @()
                    foreach ($s in $checkResult.suggestions) {
                        $sugName = if ($s.scenario) { $s.scenario } else { $s.id }
                        $sugLine = "  - " + $sugName + " (置信度 " + $s.confidence + ")"
                        if ($s.decision) {
                            $dText = [string]$s.decision
                            if ($dText.Length -gt 80) { $dText = $dText.Substring(0, 80) + "…" }
                            $sugLine += " 做法: " + $dText
                        }
                        $sugLines += $sugLine
                        # 攻七·优先采用判定：以引擎 priority 字段为准（v3.9 单一事实源）
                        # 引擎 build_gongqi_suggestions 已剔除工具名级噪音 + conf>=4.5 + 实质决策逻辑
                        $sDec = ""
                        if ($s.decision) { $sDec = [string]$s.decision }
                        $sIsPriority = $false
                        if ($null -ne $s.priority) {
                            try { $sIsPriority = [bool]$s.priority } catch { $sIsPriority = $false }
                        } else {
                            # 旧引擎回退：高置信度 + 实质决策逻辑
                            $sConf = 0.0
                            try { $sConf = [double]$s.confidence } catch { $sConf = 0.0 }
                            if ($sConf -ge 4.5 -and $sDec.Length -ge 6) { $sIsPriority = $true }
                        }
                        if ($sIsPriority) {
                            $pText = $sDec
                            if ($pText.Length -gt 100) { $pText = $pText.Substring(0, 100) + "…" }
                            if (-not $priorityText) { $priorityText = $pText }
                            # 攻七反馈闭环 Q4: 记录推荐 pattern_id（post_tool 成功后自动采纳）
                            if (-not $priorityPatternId -and $s.id) {
                                $priorityPatternId = [string]$s.id
                            }
                        }
                    }
                    if ($sugLines.Count -gt 0) {
                        $sugText = "`n攻七·推荐:" + ($sugLines -join "`n")
                    }
                }
            } catch {}
            if ($finalMatched -gt 0) {
                Write-Output ("ℹ️ [迭进] 预检完成 | 匹配 " + $finalMatched + " 条规则 | 放行" + $sugText)
            } elseif ($sugText) {
                Write-Output ("ℹ️ [迭进] 预检放行" + $sugText)
            }
            if ($priorityText) {
                Write-Output ("")
                Write-Output ("✅ [迭进] 攻七·推荐优先采用: " + $priorityText)
                Write-Output ("")
                # 攻七反馈闭环 Q4: 记录推荐 pattern_id（post_tool 工具成功时自动采纳）
                if ($priorityPatternId) {
                    try {
                        $prioRec = @{pattern_id=$priorityPatternId; ts=(Get-Date -Format "o")}
                        [System.IO.File]::WriteAllText((Join-Path $stateDir "dgen_priority_pattern.json"), ($prioRec | ConvertTo-Json -Compress), $script:utf8NoBOM)
                        Add-NoBOMLog -Path $auditLog -Message "$time [FEEDBACK-ADOPT] recommend pattern=$priorityPatternId"
                    } catch {
                        Add-NoBOMLog -Path $auditLog -Message "$time [FEEDBACK-ADOPT] write_error=$($_.Exception.Message)"
                    }
                }
            }
            # v3.9 无优先推荐时清理旧推荐文件：防止 post_tool 采纳过期的伪模式推荐
            if (-not $priorityPatternId) {
                try {
                    $prioFileTmp = Join-Path $stateDir "dgen_priority_pattern.json"
                    if (Test-Path $prioFileTmp) {
                        [System.IO.File]::Delete($prioFileTmp)
                        Add-NoBOMLog -Path $auditLog -Message "$time [FEEDBACK-ADOPT] clear_stale_priority"
                    }
                } catch { }
            }
        }
    } else {
        $engineError = $true
    }
} catch {
    Add-NoBOMLog -Path $auditLog -Message "$time [HOOK:DGEN-ERROR] $($_.Exception.Message)"
    $engineError = $true
}

# [A1] 去伪存真：引擎故障必须显式标注 ENGINE_ERROR，不得伪装 VERIFIED
# 放行（audit 精神·不阻断业务），但状态文件与上下文如实记录
if ($engineError) {
    Write-DGENStatusFile -Status "ENGINE_ERROR" -Rules "?" -Decision "unknown" -Matched "0"
    $toolCtxStr = '{"ts":"' + (Get-Date -Format "o") + '","decision":"engine_error","matched_count":0,"tool_name":"' + $toolName + '","error":"engine_unavailable"}'
    try { [System.IO.File]::WriteAllText((Join-Path $stateDir "diegin_pre_tool_context.json"), $toolCtxStr, $script:utf8NoBOM) } catch {}
    Write-Output ("")
    Write-Output ("⚠️ [迭进] 引擎异常（预检未执行），本次放行但状态未验证")
    Write-Output ("")
    exit 0
}

# 写状态文件供 AI 读取
$st = $markerStatus
if ($st -eq "allowed") { $st = "ALLOWED" }
elseif ($st -eq "verified") { $st = "VERIFIED" }
elseif ($st -eq "pending") { $st = "PENDING" }
Write-DGENStatusFile -Status $st -Rules $activeRules -Decision $finalDecision -Matched $finalMatched
# ---- Mindol 语义记忆 ----
$mindolBridge = Join-Path $g_pr "engine\mindol_bridge.py"
if (Test-Path $mindolBridge) {
    & $pythonExe $mindolBridge record pre_tool "decision=$finalDecision matched=$finalMatched status=$st" codex 2>&1 | Out-Null
}
Write-DGENContextAndExit -ExitCode 0

# 阶段状态写入: pre_tool
Write-PhaseState -Phase "pre_tool" -Status "completed" -Data @{ts=(Get-Date -Format "o")}
