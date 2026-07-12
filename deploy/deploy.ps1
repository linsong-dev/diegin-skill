# 迭进·DGEN — AI 全域常驻自我迭代进化系统 一键部署脚本
# 用法: powershell -ExecutionPolicy Bypass -File deploy.ps1
# 注意：本脚本使用 Write-NoBOM 安全写入，不产生 BOM

$ErrorActionPreference = "Stop"

# ── 内置 NoBOM 安全写入函数（不依赖外部模块） ──
$script:utf8NoBOM = [System.Text.UTF8Encoding]::new($false)
function Write-NoBOM { param([string]$Path, [string]$Content) [System.IO.File]::WriteAllText($Path, $Content, $script:utf8NoBOM) }
function Write-NoBOMJson { param([string]$Path, $Object, [int]$Depth=10) $j = $Object | ConvertTo-Json -Depth $Depth; [System.IO.File]::WriteAllText($Path, $j, $script:utf8NoBOM) }
function Test-BOM { param([string]$Path) if (-not (Test-Path $Path)) { return $false }; $b = [System.IO.File]::ReadAllBytes($Path); return ($b.Length -ge 3 -and $b[0] -eq 239 -and $b[1] -eq 187 -and $b[2] -eq 191) }

function Write-Step {
    param([string]$Msg, [string]$Status = "INFO")
    $colors = @{INFO="White"; OK="Green"; WARN="Yellow"; ERR="Red"; STEP="Cyan"}
    Write-Host ("[{0}] {1}" -f @{INFO=".."; OK="OK"; WARN="!!"; ERR="XX"; STEP=">>"}[$Status], $Msg) -ForegroundColor $colors[$Status]
}

Write-Host "============================================" -ForegroundColor Cyan
Write-Host "  迭进·DGEN 一键部署" -ForegroundColor Cyan
Write-Host "  全域常驻 - AI 不可绕过 - 自我进化" -ForegroundColor Cyan
Write-Host "============================================" -ForegroundColor Cyan

# ── 1. 路径检测 ──
Write-Step "阶段 1/7: 检测环境路径" "STEP"
$srcRoot = Resolve-Path (Join-Path $PSScriptRoot "..")
$codexHome = "$env:USERPROFILE\.codex"
$runtimeRoot = "$codexHome\diegin"
$agentsDir = "$env:USERPROFILE\.agents"
$pluginMarketDir = "$agentsDir\plugins\diegin"
Write-Step "源码目录: $srcRoot" "OK"
Write-Step "运行时目录: $runtimeRoot" "OK"

# ── 2. 部署运行时 ──
Write-Step "阶段 2/7: 部署引擎和钩子" "STEP"
@($runtimeRoot, "$runtimeRoot\engine", "$runtimeRoot\hooks", "$runtimeRoot\config",
  "$runtimeRoot\var\logs", "$runtimeRoot\var\state", "$runtimeRoot\var\workspace",
  $pluginMarketDir) | ForEach-Object {
    if (-not (Test-Path $_)) { New-Item -ItemType Directory -Path $_ -Force | Out-Null }
}
Copy-Item "$srcRoot\engine\*" "$runtimeRoot\engine" -Recurse -Force
Copy-Item "$srcRoot\hooks\*" "$runtimeRoot\hooks" -Recurse -Force
Copy-Item "$srcRoot\config\*" "$runtimeRoot\config" -Recurse -Force
if (Test-Path "$srcRoot\SKILL.md") { Copy-Item "$srcRoot\SKILL.md" "$runtimeRoot\SKILL.md" -Force }
Write-Step "  引擎 + 钩子 已部署" "OK"

# ── 3. Marketplace 注册 ──
Write-Step "阶段 3/7: 注册 Personal Marketplace" "STEP"
$pluginContent = Get-Content "$srcRoot\.codex-plugin\plugin.json" -Encoding UTF8 -Raw
$ver = ($pluginContent | ConvertFrom-Json).version
$ts = Get-Date -Format "yyyyMMddHHmmss"
$newVer = "$ver+codex.$ts"
$pluginContent = $pluginContent -replace '"version":\s*"[^"]+"', '"version": "'+$newVer+'"'
New-Item -ItemType Directory -Path "$pluginMarketDir\.codex-plugin" -Force | Out-Null
Write-NoBOM -Path "$pluginMarketDir\.codex-plugin\plugin.json" -Content $pluginContent
Write-Step "  版本: $newVer" "OK"

$mktplFile = "$agentsDir\.agents\plugins\marketplace.json"
if (-not (Test-Path $mktplFile)) {
    New-Item -ItemType Directory -Path "$agentsDir\.agents\plugins" -Force | Out-Null
    $m = @{ name="personal"; interface=@{displayName="Personal"}; plugins=@(
        @{ name="diegin"; source=@{source="local"; path="./plugins/diegin"}; policy=@{installation="AVAILABLE";authentication="ON_INSTALL"}; category="Productivity" }
    )}
    Write-NoBOMJson -Path $mktplFile -Object $m
    Write-Step "  marketplace.json 已创建" "OK"
} else {
    $m = Get-Content $mktplFile -Encoding UTF8 -Raw | ConvertFrom-Json
    if ($m.plugins.name -notcontains "diegin") {
        $m.plugins += @{ name="diegin"; source=@{source="local"; path="./plugins/diegin"}; policy=@{installation="AVAILABLE";authentication="ON_INSTALL"}; category="Productivity" }
        Write-NoBOMJson -Path $mktplFile -Object $m
        Write-Step "  已添加 diegin" "OK"
    } else {
        Write-Step "  已存在" "OK"
    }
}

Write-Step "阶段 4/7: 部署系统级 Hook" "STEP"
if (Test-Path "$srcRoot\deploy\hooks-template.json") {
    $h = Get-Content "$srcRoot\deploy\hooks-template.json" -Encoding UTF8 -Raw
    Write-NoBOM -Path "$codexHome\hooks.json" -Content $h
    Write-Step "  hooks.json 已部署" "OK"
}

# ── 5. AGENTS.md ──
Write-Step "阶段 5/7: 部署 AGENTS.md" "STEP"
if (Test-Path "$srcRoot\AGENTS.md") {
    $a = Get-Content "$srcRoot\AGENTS.md" -Encoding UTF8 -Raw
    Write-NoBOM -Path "$codexHome\AGENTS.md" -Content $a
    Write-Step "  AGENTS.md 已部署" "OK"
}

# ── 6. Codex 配置 ──
Write-Step "阶段 6/7: 更新 Codex 配置" "STEP"
$configPath = "$codexHome\config.toml"
$config = Get-Content $configPath -Encoding UTF8 -Raw
if ($config -notmatch 'hooks\s*=\s*true') {
    $config = $config -replace '(\[features\][^\[]*)', "`$1`nhooks = true`n"
}
if ($config -notmatch 'diegin@personal') {
    $entry = "`n[plugins.`"diegin@personal`"]`nenabled = true`n"
    $config = $config -replace "(\[mcp_servers)", "$entry`$1"
}
if ($config -notmatch 'marketplace.*personal') {
    $mktplEntry = "`n[marketplaces.personal]`nsource_type = `"local`"`nsource = `"$agentsDir`"`n"
    $config = $config -replace "(\[marketplaces.openai-bundled)", "$mktplEntry`$1"
}
Write-NoBOM -Path $configPath -Content $config
Write-Step "  config.toml 已更新" "OK"

# ── 7. 安装插件 ──
Write-Step "阶段 7/7: 安装插件" "STEP"
$codexCli = Get-ChildItem "$env:LOCALAPPDATA\OpenAI\Codex\bin" -Recurse -Filter "codex.exe" -ErrorAction SilentlyContinue | Select-Object -First 1 -ExpandProperty FullName
if ($codexCli) {
    & $codexCli plugin remove "diegin@personal" 2>&1 | Out-Null
    $out = & $codexCli plugin add "diegin@personal" 2>&1
    if ($LASTEXITCODE -eq 0) { Write-Step "  diegin@personal 安装成功" "OK" }
    else { Write-Step "  安装输出: $out" "WARN" }
} else { Write-Step "  未找到 codex CLI" "WARN" }

# ── BOM 门禁：部署后自检 ──
Write-Step "BOM 自检..." "STEP"
$bomFiles = @($codexHome, $runtimeRoot, $pluginMarketDir)
$hasBOM = $false
Get-ChildItem $bomFiles -Recurse -Include "*.json","*.ps1","*.toml","*.md" -ErrorAction SilentlyContinue | Where-Object { $_.FullName -notmatch '\\.git\\' } | ForEach-Object {
    if (Test-BOM $_.FullName) {
        Write-Host "  ❌ BOM: $(Split-Path $_.FullName -Leaf)" -ForegroundColor Red
        # 自动修复
        $c = [System.IO.File]::ReadAllText($_.FullName, [System.Text.Encoding]::UTF8)
        Write-NoBOM -Path $_.FullName -Content $c
        $hasBOM = $true
    }
}
if (-not $hasBOM) { Write-Step "  BOM check all clean (NoBOM)" "OK" }

Write-Host ""
Write-Host "============================================" -ForegroundColor Green
Write-Host "  部署完成！重启 Codex 生效" -ForegroundColor Green
Write-Host "============================================" -ForegroundColor Cyan