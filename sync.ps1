# DGEN sync v2 - intelligent merge
param($Action = "check")
function OK { param([string]$m) Write-Host ("  [OK] " + $m) -ForegroundColor Green }
function DIF { param([string]$m) Write-Host ("  [!]  " + $m) -ForegroundColor Yellow }
function INF { param([string]$m) Write-Host ("  ...  " + $m) -ForegroundColor Cyan }
$srcRoot = $PSScriptRoot
$dieginRoot = [System.Text.Encoding]::UTF8.GetString([System.Convert]::FromBase64String("RTpc6aG555uuXENvZGV4X+S+v+aQuueJiFwuY29kZXhcZGllZ2lu"))
Add-Type -AssemblyName System.Web.Extensions
function Merge-One {
    param($srcFile, $runFile, $label)
    $jss = New-Object System.Web.Script.Serialization.JavaScriptSerializer
    $jss.MaxJsonLength = 20971520
    $src = $jss.DeserializeObject([System.IO.File]::ReadAllText($srcFile, [System.Text.UTF8Encoding]::new($false)))
    $run = $jss.DeserializeObject([System.IO.File]::ReadAllText($runFile, [System.Text.UTF8Encoding]::new($false)))
    $ids = @{}; foreach ($x in $src) { $ids[$x["id"]] = $true }
    $extra = @(); foreach ($x in $run) { if (-not $ids.ContainsKey($x["id"])) { $extra += $x } }
    if ($extra.Count -eq 0) { OK ($label + ": " + $src.Count + " (consistent)") }
    else {
        DIF ($label + ": src=" + $src.Count + " +rt-only=" + $extra.Count + " = " + ($src.Count + $extra.Count))
    }
}
function SR {
    INF "Rules: src->runtime (merge)"
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
        if ($toR.Count -gt 0) { DIF ("  src->rt: " + (($toR | % { $_.Name }) -join ", ")) }
        if ($toS.Count -gt 0) { DIF ("  rt->src: " + (($toS | % { $_.Name }) -join ", ")) }
    }
}
function SH {
    INF "Hooks: rt->src"
    $sd = Join-Path $srcRoot "hooks"; $rd = Join-Path $dieginRoot "hooks"
    $files = @("diegin_pre_reply.ps1","diegin_pre_tool.ps1","diegin_post_tool.ps1","diegin_stop.ps1","diegin_session_start.ps1","diegin_notify.ps1","diegin_notify_wrapper.ps1","diegin_session_image_clean.ps1","dgen_evolve.py","monitor_v3.py","hooks.json")
    $n = 0
    foreach ($f in $files) {
        $rf = Join-Path $rd $f; $sf = Join-Path $sd $f
        if (-not (Test-Path $rf)) { DIF ("missing: " + $f); continue }
        $rl = (Get-Content $rf -Raw).Length
        $sl = if (Test-Path $sf) { (Get-Content $sf -Raw).Length } else { 0 }
        if ($rl -ne $sl) { DIF ("$f differs") } else { OK ("$f consistent") }
    }
}
Write-Host "=== DGEN Sync v2 ===" -ForegroundColor Cyan
Write-Host ("  Action: " + $Action)
switch ($Action) {
    "check"      { SR; SH; Write-Host "  check done" -ForegroundColor Green }
    default      { Write-Host "Usage: check" -ForegroundColor Yellow }
}