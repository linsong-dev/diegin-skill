# DGEN sync v3 - full bidirectional sync with merge
param($Action = "check")

function OK { param([string]$m) Write-Host ("  [OK] " + $m) -ForegroundColor Green }
function DIF { param([string]$m) Write-Host ("  [!]  " + $m) -ForegroundColor Yellow }
function WARN { param([string]$m) Write-Host ("  [WARN] " + $m) -ForegroundColor Red }
function INF { param([string]$m) Write-Host ("  ...  " + $m) -ForegroundColor Cyan }
function ACT { param([string]$m) Write-Host ("  [>>>] " + $m) -ForegroundColor Magenta }

$srcRoot = $PSScriptRoot
$dieginRoot = [System.Text.Encoding]::UTF8.GetString([System.Convert]::FromBase64String("RTpc6aG555uuXENvZGV4X+S+v+aQuueJiFwuY29kZXhcZGllZ2lu"))

Add-Type -AssemblyName System.Web.Extensions

function Get-Json {
    param($Path)
    $jss = New-Object System.Web.Script.Serialization.JavaScriptSerializer
    $jss.MaxJsonLength = 20971520
    return $jss.DeserializeObject([System.IO.File]::ReadAllText($Path, [System.Text.UTF8Encoding]::new($false)))
}

function Write-Json {
    param($Path, $Obj)
    $jss = New-Object System.Web.Script.Serialization.JavaScriptSerializer
    $jss.MaxJsonLength = 20971520
    $json = $jss.Serialize($Obj)  # compact
    # Pretty-print for readability
    $json = $jss.Serialize($Obj)
    # Use native JSON formatting
    [System.IO.File]::WriteAllText($Path, $json, [System.Text.UTF8Encoding]::new($false))
}

function Write-JsonPretty {
    param($Path, $Obj)
    # Pretty print with 2-space indent
    $json = $Obj | ConvertTo-Json -Depth 10
    [System.IO.File]::WriteAllText($Path, $json, [System.Text.UTF8Encoding]::new($false))
}

function Merge-One {
    param($srcFile, $runFile, $label)
    $src = Get-Json $srcFile
    $run = Get-Json $runFile
    $ids = @{}; foreach ($x in $src) { $ids[$x["id"]] = $true }
    $extra = @(); foreach ($x in $run) { if (-not $ids.ContainsKey($x["id"])) { $extra += $x } }
    if ($extra.Count -eq 0) { OK ($label + ": " + $src.Count + " (consistent)"); return $false }
    else {
        DIF ($label + ": src=" + $src.Count + " +rt-only=" + $extra.Count + " = " + ($src.Count + $extra.Count))
        foreach ($x in $extra) { Write-Host ("      rt-only: " + $x["id"]) -ForegroundColor DarkYellow }
        return $extra
    }
}

function Apply-Merge {
    param($srcFile, $runFile, $label)
    $src = Get-Json $srcFile
    $run = Get-Json $runFile
    $ids = @{}; foreach ($x in $src) { $ids[$x["id"]] = $true }
    $extra = @(); foreach ($x in $run) { if (-not $ids.ContainsKey($x["id"])) { $extra += $x } }
    if ($extra.Count -eq 0) { OK ($label + ": " + $src.Count + " (already consistent)"); return }
    
    $merged = $src + $extra
    Write-JsonPretty $srcFile $merged
    ACT ($label + ": merged " + $extra.Count + " runtime-only items → src (" + $merged.Count + " total)")
}

function SR-Check {
    INF "Rules: src←→runtime (diff)"
    $s = Join-Path $srcRoot "engine\evo\rules"
    $r = Join-Path $dieginRoot "engine\evo\rules"
    Merge-One (Join-Path $s "interception_rules.json") (Join-Path $r "interception_rules.json") "interception"
    Merge-One (Join-Path $s "success_patterns.json") (Join-Path $r "success_patterns.json") "patterns"
    $sd = Join-Path $s "domain_rules"; $rd = Join-Path $r "domain_rules"
    $sf = Get-ChildItem $sd -Filter "*.json" -EA 0
    $rf = Get-ChildItem $rd -Filter "*.json" -EA 0
    $sn = @{}; $rn = @{}
    foreach ($f in $sf) { $sn[$f.Name] = $true }
    foreach ($f in $rf) { $rn[$f.Name] = $true }
    $toR = @(); $toS = @()
    foreach ($f in $sf) { if (-not $rn.ContainsKey($f.Name)) { $toR += $f } }
    foreach ($f in $rf) { if (-not $sn.ContainsKey($f.Name)) { $toS += $f } }
    if ($toR.Count -eq 0 -and $toS.Count -eq 0) { OK "domain_rules/ consistent" }
    else {
        if ($toR.Count -gt 0) { DIF ("  src→rt: " + (($toR | % { $_.Name }) -join ", ")) }
        if ($toS.Count -gt 0) { DIF ("  rt→src: " + (($toS | % { $_.Name }) -join ", ")) }
    }
}

function SR-Sync {
    INF "Rules: merge runtime-only → src"
    $s = Join-Path $srcRoot "engine\evo\rules"
    $r = Join-Path $dieginRoot "engine\evo\rules"
    Apply-Merge (Join-Path $s "interception_rules.json") (Join-Path $r "interception_rules.json") "interception"
    Apply-Merge (Join-Path $s "success_patterns.json") (Join-Path $r "success_patterns.json") "patterns"
    
    # domain_rules: bidirectional sync
    $sd = Join-Path $s "domain_rules"; $rd = Join-Path $r "domain_rules"
    if (-not (Test-Path $sd)) { New-Item -ItemType Directory -Path $sd -Force | Out-Null }
    $sf = Get-ChildItem $sd -Filter "*.json" -EA 0
    $rf = Get-ChildItem $rd -Filter "*.json" -EA 0
    $sn = @{}; $rn = @{}
    foreach ($f in $sf) { $sn[$f.Name] = $true }
    foreach ($f in $rf) { $rn[$f.Name] = $true }
    # Copy src→rt for files only in src
    foreach ($f in $sf) {
        if (-not $rn.ContainsKey($f.Name)) {
            Copy-Item $f.FullName (Join-Path $rd $f.Name) -Force
            ACT ("domain_rules: " + $f.Name + " → runtime")
        }
    }
    # Copy rt→src for files only in runtime
    foreach ($f in $rf) {
        if (-not $sn.ContainsKey($f.Name)) {
            Copy-Item $f.FullName (Join-Path $sd $f.Name) -Force
            ACT ("domain_rules: " + $f.Name + " → src")
        }
    }
    if ($sf.Count -eq $rf.Count) { OK "domain_rules/ consistent" }
}

function SH-Check {
    INF "Hooks: rt→src (diff)"
    $sd = Join-Path $srcRoot "hooks"; $rd = Join-Path $dieginRoot "hooks"
    $files = @("diegin_pre_reply.ps1","diegin_pre_tool.ps1","diegin_post_tool.ps1","diegin_stop.ps1","diegin_session_start.ps1","diegin_notify.ps1","diegin_notify_wrapper.ps1","diegin_session_image_clean.ps1","dgen_evolve.py","monitor_v3.py","hooks.json")
    $diffCount = 0
    foreach ($f in $files) {
        $rf = Join-Path $rd $f; $sf = Join-Path $sd $f
        if (-not (Test-Path $rf)) { DIF ("missing in rt: " + $f); $diffCount++; continue }
        $rc = [System.IO.File]::ReadAllBytes($rf)
        if (Test-Path $sf) {
            $sc = [System.IO.File]::ReadAllBytes($sf)
            if ($rc.Length -ne $sc.Length) { DIF ("$f size differs"); $diffCount++ }
            else {
                $same = $true
                for ($i = 0; $i -lt $rc.Length; $i++) { if ($rc[$i] -ne $sc[$i]) { $same = $false; break } }
                if (-not $same) { DIF ("$f content differs"); $diffCount++ }
                else { OK ("$f consistent") }
            }
        } else {
            DIF ("missing in src: " + $f); $diffCount++
        }
    }
    if ($diffCount -eq 0) { OK "all hooks consistent" }
}

function SH-Sync {
    INF "Hooks: runtime → src (sync)"
    $sd = Join-Path $srcRoot "hooks"; $rd = Join-Path $dieginRoot "hooks"
    if (-not (Test-Path $sd)) { New-Item -ItemType Directory -Path $sd -Force | Out-Null }
    $files = @("diegin_pre_reply.ps1","diegin_pre_tool.ps1","diegin_post_tool.ps1","diegin_stop.ps1","diegin_session_start.ps1","diegin_notify.ps1","diegin_notify_wrapper.ps1","diegin_session_image_clean.ps1","dgen_evolve.py","monitor_v3.py","hooks.json")
    $copied = 0
    foreach ($f in $files) {
        $rf = Join-Path $rd $f; $sf = Join-Path $sd $f
        if (-not (Test-Path $rf)) { DIF ("missing in runtime: " + $f); continue }
        $needsCopy = $false
        if (-not (Test-Path $sf)) { $needsCopy = $true }
        else {
            $rc = [System.IO.File]::ReadAllBytes($rf)
            $sc = [System.IO.File]::ReadAllBytes($sf)
            if ($rc.Length -ne $sc.Length) { $needsCopy = $true }
            else {
                for ($i = 0; $i -lt $rc.Length; $i++) { if ($rc[$i] -ne $sc[$i]) { $needsCopy = $true; break } }
            }
        }
        if ($needsCopy) {
            Copy-Item $rf $sf -Force
            ACT ("$f → src")
            $copied++
        } else {
            OK ("$f consistent")
        }
    }
    if ($copied -gt 0) { Write-Host ("  synced " + $copied + " files to src") -ForegroundColor Green }
}

# ===== Main =====
Write-Host "=== DGEN Sync v3 ===" -ForegroundColor Cyan
Write-Host ("  Action: " + $Action)
Write-Host ("  Src:    " + $srcRoot)
Write-Host ("  RT:     " + $dieginRoot)
Write-Host ""

switch ($Action) {
    "check"       { SR-Check; Write-Host ""; SH-Check }
    "sync-rules"  { SR-Sync }
    "sync-hooks"  { SH-Sync }
    "sync-all"    { SR-Check; Write-Host ""; SH-Check; Write-Host ""; SR-Sync; SH-Sync }
    default {
        Write-Host "Usage: .\sync.ps1 <action>" -ForegroundColor Yellow
        Write-Host "  check       — 仅检查差异（默认）" -ForegroundColor Cyan
        Write-Host "  sync-rules  — 合并运行时独有规则 → 源码库" -ForegroundColor Cyan
        Write-Host "  sync-hooks  — 同步运行时钩子 → 源码库" -ForegroundColor Cyan
        Write-Host "  sync-all    — 先检查，再同步全部" -ForegroundColor Cyan
    }
}
