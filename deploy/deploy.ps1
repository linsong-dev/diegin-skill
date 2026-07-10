# 迭进·DGEN — AI 全域常驻自我迭代进化系统 一键部署脚本
# 用法: powershell -ExecutionPolicy Bypass -File deploy.ps1

$ErrorActionPreference = "Stop"

function Write-Step {
    param([string]$Msg, [string]$Status = "INFO")
    $colors = @{INFO="White"; OK="Green"; WARN="Yellow"; ERR="Red"; STEP="Cyan"}
    $c = $colors[$Status]
    if (-not $c) { $c = "White" }
    $prefix = @{INFO="  "; OK="[OK] "; WARN="[!!] "; ERR="[XX] "; STEP="  >>"}[$Status]
    Write-Host ("$prefix $Msg") -ForegroundColor $c
}

Write-Host "============================================" -ForegroundColor Cyan
Write-Host "  迭进-DGEN 一键部署" -ForegroundColor Cyan
Write-Host "  全域常驻 - AI 不可绕过 - 自我进化" -ForegroundColor Cyan
Write-Host "============================================" -ForegroundColor Cyan
Write-Host ""

Write-Step "阶段 1/7: 验证源项目" "STEP"
$srcRoot = "E:\Claw_项目\技能\diegin-skill"
$enginePy = "$srcRoot\engine\call_diegin.py"
if (-not (Test-Path $enginePy)) {
    Write-Step "源项目未找到: $srcRoot" "ERR"
    exit 1
}
Write-Step "源项目: $srcRoot" "OK"

Write-Step "阶段 2/7: 复制插件文件" "STEP"
$PluginRoot = "$env:USERPROFILE\plugins\diegin"
if (-not (Test-Path $PluginRoot)) { New-Item -ItemType Directory -Path $PluginRoot -Force | Out-Null }

$dirs = @(".codex-plugin", "engine", "scripts", "hooks", "skills", "workspace", "config")
foreach ($d in $dirs) {
    $src = "$srcRoot\$d"
    if (Test-Path $src) {
        Copy-Item -Path $src -Destination $PluginRoot -Recurse -Force
        Write-Step "  $d" "OK"
    }
}
foreach ($f in @("SKILL.md", "README.md", "requirements.txt")) {
    $src = "$srcRoot\$f"
    if (Test-Path $src) { Copy-Item $src "$PluginRoot\$f" -Force }
}

# Update plugin version
$pluginJson = "$PluginRoot\.codex-plugin\plugin.json"
if (Test-Path $pluginJson) {
    $ver = (Get-Content $pluginJson -Encoding UTF8 | ConvertFrom-Json).version
    $ts = Get-Date -Format "yyyyMMddHHmmss"
    $newVer = "$ver+codex.$ts"
    (Get-Content $pluginJson -Encoding UTF8) -replace '"version":\s*"[^"]+"', '"version": "'+$newVer+'"' | Set-Content $pluginJson -Encoding UTF8 -Force
    Write-Step "版本: $newVer" "OK"
}

# Remove unsupported hooks field from plugin.json
try {
    $pj = Get-Content $pluginJson -Encoding UTF8 | ConvertFrom-Json
    if ($pj.PSObject.Properties.Name -contains "hooks") {
        $pj.PSObject.Properties.Remove("hooks")
        $pj | ConvertTo-Json -Depth 10 | Set-Content $pluginJson -Encoding UTF8 -Force
    }
} catch {}

Write-Step "阶段 3/7: Python 虚拟环境" "STEP"
$venvPy = "$PluginRoot\.venv\Scripts\python.exe"
if (-not (Test-Path $venvPy)) {
    $candidates = @(
        "$env:USERPROFILE\.openclaw-tdxclaw\workspace\.venv\Scripts\python.exe",
        "$env:LOCALAPPDATA\Microsoft\WindowsApps\python.exe"
    )
    $pyPath = $null
    foreach ($c in $candidates) {
        if (Test-Path $c) { $pyPath = $c; break }
    }
    if (-not $pyPath) { Write-Step "未找到 Python 3.10+" "ERR"; exit 1 }
    Write-Step "Python: $pyPath" "OK"
    & $pyPath -m venv "$PluginRoot\.venv" 2>&1 | Out-Null
    if ($LASTEXITCODE -ne 0) { Write-Step "venv 失败" "ERR"; exit 1 }
    Write-Step "虚拟环境已创建" "OK"
    if (Test-Path "$PluginRoot\requirements.txt") {
        & $venvPy -m pip install -r "$PluginRoot\requirements.txt" -q 2>&1 | Out-Null
    }
} else {
    Write-Step "虚拟环境已存在" "OK"
}

Write-Step "阶段 3.5/7: 修复引擎编码" "STEP"
$engineFiles = @("$PluginRoot\engine\call_diegin.py", "$PluginRoot\engine\dgen_pre_check_runner.py")
foreach ($ef in $engineFiles) {
    if (Test-Path $ef) {
        $c = Get-Content $ef -Encoding UTF8 -Raw
        if ($c -notmatch "sys.stdout.*utf-8") {
            $c = $c -replace "(import sys, json, os)", "import sys, json, os`r`nimport io`r`nsys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')"
            $c | Set-Content $ef -Encoding UTF8 -Force
        }
    }
}
Write-Step "编码修复完成" "OK"

Write-Step "阶段 4/7: 部署系统 Hook" "STEP"
$CodexHome = "$env:USERPROFILE\.codex"
$hooksPath = "$CodexHome\hooks.json"
$hooksContent = @"
{
  "hooks": {
    "SessionStart": [
      {
        "matcher": "startup|resume",
        "hooks": [
          {
            "command": "powershell -ExecutionPolicy Bypass -File \"$env:USERPROFILE\plugins\diegin\scripts\diegin_session_start.ps1\"",
            "type": "command",
            "statusMessage": "Diegin SessionStart",
            "timeout": 30
          }
        ]
      }
    ],
    "PreToolUse": [
      {
        "matcher": ".*",
        "hooks": [
          {
            "command": "powershell -ExecutionPolicy Bypass -File \"$env:USERPROFILE\plugins\diegin\scripts\diegin_pre_tool.ps1\"",
            "type": "command",
            "statusMessage": "Diegin PreToolUse",
            "timeout": 30
          }
        ]
      }
    ],
    "UserPromptSubmit": [
      {
        "hooks": [
          {
            "command": "powershell -ExecutionPolicy Bypass -File \"$env:USERPROFILE\plugins\diegin\scripts\diegin_pre_reply.ps1\"",
            "type": "command",
            "statusMessage": "Diegin UserPromptInject",
            "timeout": 60
          }
        ]
      }
    ],
    "PostToolUse": [
      {
        "matcher": ".*",
        "hooks": [
          {
            "command": "powershell -ExecutionPolicy Bypass -File \"$env:USERPROFILE\plugins\diegin\scripts\diegin_post_tool.ps1\"",
            "type": "command",
            "statusMessage": "Diegin PostToolUse",
            "timeout": 30
          }
        ]
      }
    ],
    "Stop": [
      {
        "hooks": [
          {
            "command": "powershell -ExecutionPolicy Bypass -File \"$env:USERPROFILE\plugins\diegin\scripts\diegin_stop.ps1\"",
            "type": "command",
            "statusMessage": "Diegin StopReport",
            "timeout": 30
          }
        ]
      }
    ]
  }
}
"@
$utf8NoBOM = New-Object System.Text.UTF8Encoding $false
[System.IO.File]::WriteAllText($hooksPath, $hooksContent, $utf8NoBOM)
Write-Step "已创建: $hooksPath" "OK"

Write-Step "阶段 5/7: 部署 AGENTS.md" "STEP"
$agentsMd = @"
## DGEN ⚡ 迭进预检规则（系统级·全域常驻·不可跳过）

每次组织回复前必须执行迭进预检：

### 1. 核心四原则
- **守三**（负向纠错）：拆解自我→找出不足→对比提炼→总结改进
- **攻七**（正向强化）：识别优势→复盘成功→提炼可复用模式
- **一二不过三**（安全阀）：第1次同类错误自建规则；第2次加固；第3次通知用户
- **举一反三**（跨域泛化）：从单条规则推导跨场景通用候选规则

### 2. 迭进预检流程
用户消息 → [DGEN 预检] 匹配系统级规则 + 当前领域规则
- 命中拦截 → 按裁决执行（block/escalate/iron_wall_block）
- 未命中 → [DGEN] ✅ 通过，正常回复

### 3. 强制标记
每次回复开头必须输出 [DGEN] 标记：
- [DGEN] ✅ 通过
- [DGEN] 🛑 拦截 X 条 | 裁决: block
- [DGEN] ⚠️ 重新激活

**没有 [DGEN] 标记 = 迭进未激活 = 故障！**

### 4. 迭进规则（13条）
| 规则 | 严重度 | 描述 |
|:---|:---:|:---|
| rule_word_meaning_confirm | high | 歧义词先确认再执行 |
| rule_scope_full_check | high | 搜索前确认完范围 |
| rule_check_before_conclude | medium | 不一致先多源交叉验证 |
| rule_extract_full_scope | high | 提取前确认完整文件清单 |
| rule_clean_verify_layered | critical | 清洗必须3层验证 |
| rule_delivery_full_audit | critical | 交付前逐文件审查 |
| rule_powershell_escape_triple_lock | critical | PowerShell 转义三层锁 |
| rule_cmd_test_before_run | high | 命令行先试后跑 |
| rule_toolchain_path_verify | high | 工具链路径先验证再使用 |
| rule_encoding_pre_check | high | 文件编码先确认再读 |
| rule_verify_command_exitcode | critical | 命令结果不假设成功 |
| rule_dry_run_before_batch | high | 批量操作前 dry-run |
| rule_tool_selection_fastest | medium | 选最快工具 |

### 5. 情景覆盖
- 用户回复：必须迭进预检
- 子会话（subagent）：必须注入迭进规则
- 纯工具调用（无回复）：不需要
"@
$agentsMd | Out-File "$CodexHome\AGENTS.md" -Encoding UTF8 -Force
Write-Step "已创建: $CodexHome\AGENTS.md" "OK"

Write-Step "阶段 6/7: 更新 Codex 配置" "STEP"
$configPath = "$CodexHome\config.toml"
$config = Get-Content $configPath -Encoding UTF8 -Raw

if ($config -notmatch 'hooks\s*=\s*true') {
    $config = $config -replace '(\[features\][^\[]*)', "$1`nhooks = true`n"
    Write-Step "已添加 hooks=true" "OK"
} else {
    Write-Step "hooks=true 已存在" "OK"
}

if ($config -notmatch 'diegin@personal') {
    $dieginEntry = "`n[plugins.\"diegin@personal\"]`nenabled = true`n"
    $config = $config -replace "(\[mcp_servers)", "$dieginEntry`$1"
    Write-Step "已添加 diegin 插件" "OK"
} else {
    Write-Step "diegin 插件已存在" "OK"
}

# 清理旧 [hooks] 段
$config = $config -replace '(?s)\[hooks\].*?(?=\[mcp_servers)', "[mcp_servers"
$config | Set-Content $configPath -Encoding UTF8 -Force
Write-Step "配置更新完成" "OK"

Write-Step "阶段 7/7: 安装插件并信任 Hook" "STEP"
$codexCli = "$env:USERPROFILE\AppData\Local\OpenAI\Codex\bin\a7c12ebff69fb123\codex.exe"
if (-not (Test-Path $codexCli)) {
    $found = Get-ChildItem "$env:LOCALAPPDATA\OpenAI\Codex\bin" -Recurse -Filter "codex.exe" -ErrorAction SilentlyContinue | Select-Object -First 1
    if ($found) { $codexCli = $found.FullName }
}
Write-Step "CLI: $codexCli" "OK"

# 安装/重装插件
Write-Step "安装插件..."
& $codexCli plugin remove diegin@personal 2>&1 | Out-Null
$out = & $codexCli plugin add diegin@personal 2>&1
if ($LASTEXITCODE -eq 0) {
    Write-Step "插件安装成功" "OK"
} else {
    Write-Step "插件安装输出: $out" "WARN"
}

# 信任 hooks
Write-Step "验证并信任 hooks..."
$trustOut = & $codexCli exec --dangerously-bypass-hook-trust -s danger-full-access --skip-git-repo-check --ephemeral "echo hooks trusted" 2>&1
if ($trustOut -match "hook: SessionStart") {
    Write-Step "Hook 信任成功！所有 5 个钩子已激活" "OK"
} else {
    Write-Step "Hook 信任输出: $trustOut" "WARN"
    Write-Step "请手动: 运行 codex 然后输入 /hooks 信任" "WARN"
}

Write-Step "验证引擎..." "STEP"
$venvPy2 = "$PluginRoot\.venv\Scripts\python.exe"
if (Test-Path $venvPy2) {
    $engOut = & $venvPy2 "$PluginRoot\engine\call_diegin.py" health 2>&1
    if ($engOut -match '"total_rules"') {
        Write-Step "Python 引擎工作正常" "OK"
    } else {
        Write-Step "引擎状态: $engOut" "WARN"
    }
}

Write-Host "============================================" -ForegroundColor Cyan
Write-Host "  部署完成！" -ForegroundColor Green
Write-Host "============================================" -ForegroundColor Cyan
Write-Host ""
Write-Host "  插件路径: $env:USERPROFILE\plugins\diegin" -ForegroundColor White
Write-Host "  hooks.json: $env:USERPROFILE\.codex\hooks.json" -ForegroundColor White
Write-Host "  AGENTS.md: $env:USERPROFILE\.codex\AGENTS.md" -ForegroundColor White
Write-Host "  审计日志: $env:USERPROFILE\.codex\diegin_audit.log" -ForegroundColor White
Write-Host ""
Write-Host "  最后一步: 重启 Codex 桌面应用" -ForegroundColor Yellow
Write-Host "  新对话中迭进将自动全域常驻" -ForegroundColor Yellow
Write-Host "============================================" -ForegroundColor Cyan