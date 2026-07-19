# DGEN bidirectional sync v1
param($Action = "check")

function OK { param([string]$m) Write-Host ("  [OK] " + $m) -ForegroundColor Green }
function DIF { param([string]$m) Write-Host ("  [!]  " + $m) -ForegroundColor Yellow }
function INF { param([string]$m) Write-Host ("  ...  " + $m) -ForegroundColor Cyan }

$srcRoot = $PSScriptRoot
$dieginRoot = [System.Text.Encoding]::UTF8.GetString([System.Convert]::FromBase64String("RTpc6aG555uuXENvZGV4X+S+v+aQuueJiFwuY29kZXhcZGllZ2lu"))

function Sync-Rules {
    INF "Rules: source -> runtime"
    $s = Join-Path $srcRoot "engine\evo\rules"
    $r = Join-Path $dieginRoot "engine\evo\rules"
    $a=Join-Path $s "interception_rules.json"; $b=Join-Path $r "interception_rules.json"
    $ca=(Get-Content $a -Encoding UTF8 -Raw | ConvertFrom-Json).Count
    $cb=(Get-Content $b -Encoding UTF8 -Raw | ConvertFrom-Json).Count
    if ($ca -eq $cb) { OK ("interception: " + $ca) }
    else { DIF ("interception: src=" + $ca + " run=" + $cb); if ($Action -ne "check") { Copy-Item $a $b -Force; OK "synced" } }
    $a=Join-Path $s "success_patterns.json"; $b=Join-Path $r "success_patterns.json"
    $ca=(Get-Content $a -Encoding UTF8 -Raw | ConvertFrom-Json).Count
    $cb=(Get-Content $b -Encoding UTF8 -Raw | ConvertFrom-Json).Count
    if ($ca -eq $cb) { OK ("patterns: " + $ca) }
    else { DIF ("patterns: src=" + $ca + " run=" + $cb); if ($Action -ne "check") { Copy-Item $a $b -Force; OK "synced" } }
    $sd=Join-Path $s "domain_rules"; $rd=Join-Path $r "domain_rules"
    $sf=Get-ChildItem $sd -Filter "*.json" -ErrorAction SilentlyContinue
    $rf=Get-ChildItem $rd -Filter "*.json" -ErrorAction SilentlyContinue
    $diff=Compare-Object ($sf | ForEach-Object { $_.Name }) ($rf | ForEach-Object { $_.Name })
    if (-not $diff) { OK "domain_rules/" }
    else { DIF "domain_rules differ"; if ($Action -ne "check") { foreach ($f in $sf) { Copy-Item $f.FullName (Join-Path $rd $f.Name) -Force }; OK "synced" } }
}

function Sync-Hooks {
    INF "Hooks: runtime -> source"
    $sd=Join-Path $srcRoot "hooks"; $rd=Join-Path $dieginRoot "hooks"
    $files=@("diegin_pre_reply.ps1","diegin_pre_tool.ps1","diegin_post_tool.ps1","diegin_stop.ps1","diegin_session_start.ps1","diegin_notify.ps1","diegin_notify_wrapper.ps1","diegin_session_image_clean.ps1","dgen_evolve.py","monitor_v3.py","hooks.json")
    foreach ($f in $files) {
        $rf=Join-Path $rd $f; $sf=Join-Path $sd $f
        if (-not (Test-Path $rf)) { DIF ("missing: " + $f); continue }
        $rc=Get-Content $rf -Encoding UTF8 -Raw
        $sc=if (Test-Path $sf) { Get-Content $sf -Encoding UTF8 -Raw } else { "" }
        if ($rc -ne $sc) {
            $rl=0; $sl=0
            for ($i=0; $i -lt $rc.Length; $i++) { if ($rc[$i] -eq [char]10) { $rl++ } }
            if ($sc) { for ($i=0; $i -lt $sc.Length; $i++) { if ($sc[$i] -eq [char]10) { $sl++ } } }
            $sg=if ($rl -gt $sl) { "+" + ($rl-$sl) } else { ($rl-$sl).ToString() }
            DIF ("$f  run=" + $rl + " src=" + $sl + " (" + $sg + ")")
            if ($Action -ne "check") { Copy-Item $rf $sf -Force; OK "synced" }
        } else { OK ("$f  consistent") }
    }
}

Write-Host "=== DGEN Sync ===" -ForegroundColor Cyan
Write-Host ("  Action: " + $Action)
switch ($Action) {
    "check"      { Sync-Rules; Sync-Hooks; Write-Host "  check done" -ForegroundColor Green }
    "sync-rules" { Sync-Rules; Write-Host "  rules synced" -ForegroundColor Green }
    "sync-hooks" { Sync-Hooks; Write-Host "  hooks synced" -ForegroundColor Green }
    "sync-all"   { Sync-Rules; Sync-Hooks; Write-Host "  full sync done" -ForegroundColor Green }
    default      { Write-Host "Usage: check | sync-rules | sync-hooks | sync-all" -ForegroundColor Yellow }
}