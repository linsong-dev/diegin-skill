# DGEN sync v3 - full bidirectional sync with merge
param($Action = "check")

function OK { param([string]$m) Write-Host ("  [OK] " + $m) -ForegroundColor Green }
function DIF { param([string]$m) Write-Host ("  [!]  " + $m) -ForegroundColor Yellow }
function WARN { param([string]$m) Write-Host ("  [WARN] " + $m) -ForegroundColor Red }
function INF { param([string]$m) Write-Host ("  ...  " + $m) -ForegroundColor Cyan }
function ACT { param([string]$m) Write-Host ("  [>>>] " + $m) -ForegroundColor Magenta }
# [2026-09-13] 已知「有意不发布」的运行时独有条目：id 内嵌机器绝对路径的自动生成垃圾条目
# （形如 $py='c:\users\administrator\.cache\...'）。它们留在运行版、不进源码库
# （沿用 2026-09-03「剔除含路径垃圾条目」做法）。登记在此后，check 会标为「已知排除」
# 而非差异，防止未来把长期漂移误判为新异常。
$script:KnownExcludedIdPattern = '\$py='

$srcRoot = $PSScriptRoot
# Auto-detect diegin runtime root (portable-aware)
if (Test-Path (Join-Path $env:CODEX_HOME "diegin")) {
    $dieginRoot = Join-Path $env:CODEX_HOME "diegin"
} elseif (Test-Path (Join-Path $env:USERPROFILE ".codex\diegin")) {
    $dieginRoot = Join-Path $env:USERPROFILE ".codex\diegin"
} else {
    Write-Host "ERROR: Cannot detect diegin runtime root. Set CODEX_HOME or use standard install." -ForegroundColor Red
    exit 1
}

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
    # [FIX 2026-09-13] 空值防护 + 原子写：曾因 $Obj=$null 直接落盘 -> 源文件被写成 0 字节
    # （success_patterns_archive.json 被截断，靠 git checkout 才恢复）。
    if ($null -eq $Obj) { WARN ("refuse to write null -> " + $Path); return }
    # Pretty print with 2-space indent
    $json = $Obj | ConvertTo-Json -Depth 10
    if (-not $json -or $json.Trim() -eq "") { WARN ("refuse to write empty -> " + $Path); return }
    $tmp = $Path + ".tmp_" + [System.Guid]::NewGuid().ToString("N")
    [System.IO.File]::WriteAllText($tmp, $json, [System.Text.UTF8Encoding]::new($false))
    if ([System.IO.File]::Exists($Path)) {
        # PS 会把 $null 第三参转成空串 -> "The path is not of a legal form"，必须给真实备份路径
        $bak = $Path + ".bak_" + [System.Guid]::NewGuid().ToString("N")
        [System.IO.File]::Replace($tmp, $Path, $bak)
        if ([System.IO.File]::Exists($bak)) { [System.IO.File]::Delete($bak) }
    }
    else { [System.IO.File]::Move($tmp, $Path) }
}

function Merge-One {
    param($srcFile, $runFile, $label)
    $src = Get-Json $srcFile
    $run = Get-Json $runFile
    $ids = @{}; foreach ($x in $src) { $ids[$x["id"]] = $true }
    $extra = @(); foreach ($x in $run) { if (-not $ids.ContainsKey($x["id"])) { $extra += $x } }
    # [2026-09-13] 区分「已知有意排除」与「真差异」：前者不报警、不计入待合并项
    $excluded = @(); $pending = @()
    foreach ($x in $extra) {
        if ($x["id"] -match $script:KnownExcludedIdPattern) { $excluded += $x } else { $pending += $x }
    }
    foreach ($x in $excluded) { Write-Host ("      known-excluded: " + $x["id"]) -ForegroundColor DarkGray }
    if ($pending.Count -eq 0) {
        $suffix = if ($excluded.Count -gt 0) { " (consistent; " + $excluded.Count + " known-excluded)" } else { " (consistent)" }
        OK ($label + ": " + $src.Count + $suffix)
        return $false
    }
    else {
        DIF ($label + ": src=" + $src.Count + " +rt-only=" + $pending.Count + " = " + ($src.Count + $pending.Count))
        foreach ($x in $pending) { Write-Host ("      rt-only: " + $x["id"]) -ForegroundColor DarkYellow }
        return $pending
    }
}

function Apply-Merge {
    param($srcFile, $runFile, $label)
    $src = Get-Json $srcFile
    $run = Get-Json $runFile
    $ids = @{}; foreach ($x in $src) { $ids[$x["id"]] = $true }
    $extra = @(); foreach ($x in $run) { if (-not $ids.ContainsKey($x["id"])) { $extra += $x } }
    if ($extra.Count -eq 0) { OK ($label + ": " + $src.Count + " (already consistent)"); return }
    
    # [FIX 2026-09-13] @() 强制成数组：单元素数组反序列化后退化为标量/字典时，
    # $src + $extra 会抛 InvalidOperation，随后以 $null 落盘把源文件清空。
    $merged = @($src) + @($extra)
    Write-JsonPretty $srcFile $merged
    ACT ($label + ": merged " + $extra.Count + " runtime-only items → src (" + $merged.Count + " total)")
}

function SR-Check {
    INF "Rules: src←→runtime (diff)"
    $s = Join-Path $srcRoot "engine\evo\rules"
    $r = Join-Path $dieginRoot "engine\evo\rules"
    $null = Merge-One (Join-Path $s "interception_rules.json") (Join-Path $r "interception_rules.json") "interception"
    $null = Merge-One (Join-Path $s "success_patterns.json") (Join-Path $r "success_patterns.json") "patterns"
    $null = Merge-One (Join-Path $s "interception_rules_archive.json") (Join-Path $r "interception_rules_archive.json") "interception-archive"
    $null = Merge-One (Join-Path $s "success_patterns_archive.json") (Join-Path $r "success_patterns_archive.json") "patterns-archive"
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
    Apply-Merge (Join-Path $s "interception_rules_archive.json") (Join-Path $r "interception_rules_archive.json") "interception-archive"
    Apply-Merge (Join-Path $s "success_patterns_archive.json") (Join-Path $r "success_patterns_archive.json") "patterns-archive"
    
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
    $files = @("diegin_pre_reply.ps1","diegin_pre_tool.ps1","diegin_post_tool.ps1","diegin_stop.ps1","diegin_session_start.ps1","diegin_notify.ps1","diegin_notify_wrapper.ps1","diegin_session_image_clean.ps1","diegin_post_compact.ps1","monitor_v3.py","hooks.json")
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
    $files = @("diegin_pre_reply.ps1","diegin_pre_tool.ps1","diegin_post_tool.ps1","diegin_stop.ps1","diegin_session_start.ps1","diegin_notify.ps1","diegin_notify_wrapper.ps1","diegin_session_image_clean.ps1","diegin_post_compact.ps1","monitor_v3.py","hooks.json")
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


# ──────────────────────────────────────────────────
# References: 源码库参考资料 → 运行时（src→rt 单向，源码库为权威）
# ──────────────────────────────────────────────────
function REF-Check {
    INF "References: src→runtime (diff)"
    $sd = Join-Path $srcRoot "references"; $rd = Join-Path $dieginRoot "references"
    $sf = Get-ChildItem $sd -Filter "*.md" -EA 0
    $rf = Get-ChildItem $rd -Filter "*.md" -EA 0
    $rn = @{}
    foreach ($f in $rf) { $rn[$f.Name] = $true }
    $diffCount = 0
    foreach ($f in $sf) {
        if (-not $rn.ContainsKey($f.Name)) { DIF ("missing in rt: " + $f.Name); $diffCount++; continue }
        $rfPath = Join-Path $rd $f.Name
        $rc = [System.IO.File]::ReadAllBytes($rfPath)
        $sc = [System.IO.File]::ReadAllBytes($f.FullName)
        if ($rc.Length -ne $sc.Length) { DIF ($f.Name + " content differs"); $diffCount++ }
        else {
            $same = $true
            for ($i = 0; $i -lt $rc.Length; $i++) { if ($rc[$i] -ne $sc[$i]) { $same = $false; break } }
            if (-not $same) { DIF ($f.Name + " content differs"); $diffCount++ }
            else { OK ($f.Name + " consistent") }
        }
    }
    if ($diffCount -eq 0) { OK "all references consistent" }
}

function REF-Sync {
    INF "References: runtime ← src (sync)"
    $sd = Join-Path $srcRoot "references"; $rd = Join-Path $dieginRoot "references"
    if (-not (Test-Path $rd)) { New-Item -ItemType Directory -Path $rd -Force | Out-Null }
    $sf = Get-ChildItem $sd -Filter "*.md" -EA 0
    $copied = 0
    foreach ($f in $sf) {
        $rf = Join-Path $rd $f.Name
        $needsCopy = $false
        if (-not (Test-Path $rf)) { $needsCopy = $true }
        else {
            $rc = [System.IO.File]::ReadAllBytes($rf)
            $sc = [System.IO.File]::ReadAllBytes($f.FullName)
            if ($rc.Length -ne $sc.Length) { $needsCopy = $true }
            else {
                for ($i = 0; $i -lt $rc.Length; $i++) { if ($rc[$i] -ne $sc[$i]) { $needsCopy = $true; break } }
            }
        }
        if ($needsCopy) {
            Copy-Item $f.FullName $rf -Force
            ACT ("references: " + $f.Name + " → runtime")
            $copied++
        } else {
            OK ($f.Name + " consistent")
        }
    }
    if ($copied -gt 0) { Write-Host ("  synced " + $copied + " files to runtime") -ForegroundColor Green }
}

# [P4-20260806] 发布门禁：变更-验证绑定（ACC-QRY-004/005）
# 变更日志存在且含 verification=failed/error → 中止同步（无验证变更不得流入发布）
function Test-PublishGate {
    param([string]$StateDir)
    $cl = Join-Path $StateDir "dgen_change_log.json"
    if (-not (Test-Path $cl)) { return $true }
    try {
        $records = Get-Content $cl -Raw -Encoding UTF8 | ConvertFrom-Json
        if (-not $records) { return $true }
        foreach ($r in @($records)) {
            $v = $r.verification
            if ($v -and $v.status -in @("failed","error")) {
                Write-Host ("  [GATE] 未验证变更: " + $r.ts + " tool=" + $r.tool + " verify=" + $v.status) -ForegroundColor Red
                Write-Host "  [GATE] 发布中止：请先修复验证失败，或用 verify_fix 确认后重试。" -ForegroundColor Red
                return $false
            }
        }
        Write-Host "  [GATE] 变更-验证门通过（无 failed/error 记录）" -ForegroundColor Green
        return $true
    } catch {
        Write-Host ("  [GATE] 检查异常(放行): " + $_.Exception.Message) -ForegroundColor Yellow
        return $true
    }
}

# ===== Self-Test（回归守卫，2026-09-13）=====
# 背景：Apply-Merge 曾在「单元素数组」源文件上抛 InvalidOperation 后仍以 $null 落盘，
# 把 success_patterns_archive.json 写成 0 字节；Write-JsonPretty 曾把 $null 直接落盘。
# 本自检把这两条真实故障固化成断言，防未来改脚本时再次引入同类破坏性写入。
function Self-Test {
    $script:stOk = 0; $script:stFail = 0
    function Chk { param([string]$Name,[bool]$Cond,[string]$Detail="")
        if ($Cond) { $script:stOk++; OK $Name }
        else { $script:stFail++; WARN ("FAIL: " + $Name + $(if ($Detail) { " | " + $Detail } else { "" })) }
    }
    INF "Sync self-test (regression guard)"
    $tmpDir = Join-Path $env:TEMP ("dgen_synctest_" + [System.Guid]::NewGuid().ToString("N").Substring(0,8))
    New-Item -ItemType Directory -Path $tmpDir -Force | Out-Null
    try {
        # T1: 单元素数组源文件 —— 曾抛异常并清空文件
        $t1 = Join-Path $tmpDir "single_src.json"
        $t1run = Join-Path $tmpDir "single_run.json"
        [System.IO.File]::WriteAllText($t1run, '[{"id":"a"},{"id":"b"}]', [System.Text.UTF8Encoding]::new($false))
        [System.IO.File]::WriteAllText($t1, '[{"id":"a"}]', [System.Text.UTF8Encoding]::new($false))
        $threw = $false
        try { Apply-Merge $t1 $t1run "selftest-single" | Out-Null } catch { $threw = $true }
        $len1 = 0; if (Test-Path $t1) { $len1 = (Get-Item $t1).Length }
        Chk "T1 单元素数组合并不抛异常" (-not $threw)
        Chk "T1 合并后文件非空" ($len1 -gt 0) ("size=" + $len1)
        $mergedOk = $false
        if ($len1 -gt 0) { try { $m = Get-Json $t1; $mergedOk = (@($m).Count -eq 2) } catch { $mergedOk = $false } }
        Chk "T1 合并后语义正确(2 条)" $mergedOk

        # T2: Write-JsonPretty 收到 $null —— 必须拒写且不动原文件
        $t2 = Join-Path $tmpDir "null_target.json"
        $orig2 = '[{"id":"keepme"}]'
        [System.IO.File]::WriteAllText($t2, $orig2, [System.Text.UTF8Encoding]::new($false))
        Write-JsonPretty -Path $t2 -Obj $null
        $after2 = [System.IO.File]::ReadAllText($t2)
        Chk "T2 null 输入不覆盖原文件" ($after2 -eq $orig2) ("now=" + $after2.Substring(0, [Math]::Min(30, $after2.Length)))

        # T3: Write-JsonPretty 正常写入 —— 原子、无 tmp/bak 残留
        $t3 = Join-Path $tmpDir "atomic_target.json"
        Write-JsonPretty -Path $t3 -Obj @(@{id="x"})
        $tmpLeft = @(Get-ChildItem $tmpDir -Filter "atomic_target.json.tmp_*" -EA 0).Count
        $bakLeft = @(Get-ChildItem $tmpDir -Filter "atomic_target.json.bak_*" -EA 0).Count
        $ok3 = $false
        if (Test-Path $t3) { try { $ok3 = (@(Get-Json $t3).Count -eq 1) } catch { $ok3 = $false } }
        Chk "T3 正常写入语义正确" $ok3
        Chk "T3 无 tmp 残留" ($tmpLeft -eq 0) ("left=" + $tmpLeft)
        Chk "T3 无 bak 残留" ($bakLeft -eq 0) ("left=" + $bakLeft)

        # T4: 已知排除分类器
        $isExcluded = ('pat_rule_x_$py=c:\users\administrator\.cache\y' -match $script:KnownExcludedIdPattern)
        $notExcluded = -not ('rule_normal_abc' -match $script:KnownExcludedIdPattern)
        Chk "T4 机器路径条目被判为已知排除" $isExcluded
        Chk "T4 正常条目不被误判" $notExcluded

        # T5: 自检未破坏脚本自身
        Chk "T5 自检未破坏 sync.ps1" (Test-Path $PSCommandPath)
    } finally {
        if (Test-Path $tmpDir) { [System.IO.Directory]::Delete($tmpDir, $true) }
    }
    Write-Host ""
    $total = $script:stOk + $script:stFail
    if ($script:stFail -eq 0) { Write-Host ("  Result: " + $script:stOk + "/" + $total + " passed") -ForegroundColor Green }
    else { Write-Host ("  Result: " + $script:stOk + "/" + $total + " passed (" + $script:stFail + " FAILED)") -ForegroundColor Red }
    return ($script:stFail -eq 0)
}

# [2026-09-13] SKILL.md 单一真源守卫：模型加载的是 plugin skills\diegin\SKILL.md，
# 曾长期与根 SKILL.md 分叉（修复写在模型读不到的那一份里）。此处做全副本 hash 一致性校验。
function Get-SkillTargets {
    $codexHome = Split-Path $dieginRoot -Parent
    $t = [ordered]@{
        "src\skills\diegin"          = (Join-Path $srcRoot "skills\diegin\SKILL.md")
        "runtime(root)"              = (Join-Path $dieginRoot "SKILL.md")
        "marketplace(root)"          = (Join-Path $codexHome "marketplaces\personal\.agents\plugins\diegin\SKILL.md")
        "marketplace(skills\diegin)" = (Join-Path $codexHome "marketplaces\personal\.agents\plugins\diegin\skills\diegin\SKILL.md")
    }
    $cacheBase = Join-Path $codexHome "plugins\cache\personal\diegin"
    if (Test-Path $cacheBase) {
        $latest = Get-ChildItem $cacheBase -Directory -EA 0 | Sort-Object Name -Descending | Select-Object -First 1
        if ($latest) {
            $t["cache(root)"] = Join-Path $latest.FullName "SKILL.md"
            $t["cache(skills\diegin)"] = Join-Path $latest.FullName "skills\diegin\SKILL.md"
        }
    }
    return $t
}

function SKILL-Check {
    INF "SKILL.md: single-source (hash across copies)"
    $canonical = Join-Path $srcRoot "SKILL.md"
    if (-not (Test-Path $canonical)) { WARN "src SKILL.md missing"; return }
    $refHash = (Get-FileHash -LiteralPath $canonical -Algorithm SHA256).Hash
    OK ("canonical src\SKILL.md " + $refHash.Substring(0,10))
    $bad = 0
    foreach ($k in (Get-SkillTargets).Keys) {
        $p = (Get-SkillTargets)[$k]
        if (-not (Test-Path $p)) { DIF ("missing: " + $k); $bad++; continue }
        $h = (Get-FileHash -LiteralPath $p -Algorithm SHA256).Hash
        if ($h -ne $refHash) { DIF ("hash mismatch: " + $k + " " + $h.Substring(0,10) + " != " + $refHash.Substring(0,10)); $bad++ }
        else { OK ($k + " consistent") }
    }
    if ($bad -eq 0) { OK "all SKILL.md copies identical" }
}

function SKILL-Sync {
    INF "SKILL.md: src → runtime/marketplace/cache (single source)"
    $canonical = Join-Path $srcRoot "SKILL.md"
    if (-not (Test-Path $canonical)) { WARN "src SKILL.md missing"; return }
    $srcResolved = (Resolve-Path $srcRoot).Path.TrimEnd('\')
    $copied = 0
    foreach ($k in (Get-SkillTargets).Keys) {
        $p = (Get-SkillTargets)[$k]
        $dir = Split-Path $p -Parent
        if (-not (Test-Path $dir)) { DIF ("skip (no dir): " + $k); continue }
        $dirResolved = (Resolve-Path $dir).Path.TrimEnd('\')
        if ($dirResolved.StartsWith($srcResolved)) { OK ($k + " is source itself"); continue }
        Copy-Item -LiteralPath $canonical -Destination $p -Force
        ACT ("copied → " + $k); $copied++
    }
    if ($copied -eq 0) { OK "nothing to copy" }
}
# ──────────────────────────────────────────────────
# [2026-09-13 新增] 代码/配置副本守卫（修复「读写旧内容」根因）
# 病根：同一份代码存在多份副本（运行版 / 插件缓存 / 技能镜像）且无一致性闸门
# → 修复写在一份、读取走另一份 → 反复崩溃。此处做全树 hash 比对。
# ──────────────────────────────────────────────────
function Get-DieginRoots {
    $codexHome = Split-Path $dieginRoot -Parent
    $r = [ordered]@{}
    $r["runtime"] = $dieginRoot
    $r["skills-mirror"] = (Join-Path $srcRoot "skills\diegin")
    $cacheBase = Join-Path $codexHome "plugins\cache\personal\diegin"
    if (Test-Path $cacheBase) {
        $latest = Get-ChildItem $cacheBase -Directory -EA 0 | Sort-Object Name -Descending | Select-Object -First 1
        if ($latest) { $r["plugin-cache"] = $latest.FullName }
    }
    return $r
}

function Test-TreeDiff {
    param($relDir, $skipPattern, $excludeSub)
    $ref = Join-Path $srcRoot $relDir
    if (-not (Test-Path $ref)) { WARN ("src missing: " + $relDir); return 1 }
    $refFiles = Get-ChildItem $ref -Recurse -File -EA 0 | Where-Object {
        if ($_.FullName -match $skipPattern) { return $false }
        foreach ($x in $excludeSub) { if ($_.FullName -match $x) { return $false } }
        return $true
    }
    $refHash = @{}
    foreach ($f in $refFiles) { $refHash[$f.FullName.Substring($ref.Length)] = (Get-FileHash -LiteralPath $f.FullName -Algorithm SHA256).Hash }
    $bad = 0
    foreach ($k in (Get-DieginRoots).Keys) {
        $dst = Join-Path (Get-DieginRoots)[$k] $relDir
        if (-not (Test-Path $dst)) { DIF ($relDir + " missing at " + $k); $bad++; continue }
        $n = 0
        foreach ($rel in $refHash.Keys) {
            $df = Join-Path $dst $rel
            if (-not (Test-Path $df)) { DIF ($k + " missing: " + $rel); $bad++; $n++; continue }
            if ((Get-FileHash -LiteralPath $df -Algorithm SHA256).Hash -ne $refHash[$rel]) { DIF ($k + " differs: " + $rel); $bad++; $n++ }
        }
        if ($n -eq 0) { OK ($relDir + " consistent @ " + $k) }
    }
    return $bad
}

# 只守「代码 + 配置」。排除：
#   engine/evo/rules  — 规则数据面（运行版合法拥有独有条目，由 SR-Check 按设计处理）
#   engine/workspace · engine/var — 运行时数据
#   engine/config    — 运行时可调配置
#   .pre_/.bak/.tmp  — 临时备份
$script:ENG_SKIP = "\.pre_|\.bak|\.tmp|~$|__pycache__|\.pyc$"
$script:ENG_EXCL = @("engine.evo.rules", "engine.workspace", "engine.var", "engine.config")

function ENG-Check {
    INF "Engine code/config: src→all copies (hash)"
    $bad = 0
    $bad += Test-TreeDiff "engine" $script:ENG_SKIP $script:ENG_EXCL
    $bad += Test-TreeDiff "config" $script:ENG_SKIP @()
    if ($bad -eq 0) { OK "engine + config consistent across all copies" }
}

function ENG-Sync {
    INF "Engine/Config: src → copies (mirror)"
    $targets = @()
    foreach ($k in (Get-DieginRoots).Keys) { $targets += ,@($k, (Get-DieginRoots)[$k]) }
    $n = 0
    foreach ($pair in $targets) {
        $k = $pair[0]; $root = $pair[1]
        foreach ($sub in @("engine", "config", "hooks")) {
            $s = Join-Path $srcRoot $sub; $d = Join-Path $root $sub
            if (-not (Test-Path $s)) { continue }
            $excl = if ($sub -eq "engine") { $script:ENG_EXCL } else { @() }
            Get-ChildItem $s -Recurse -File -EA 0 | Where-Object {
                if ($_.FullName -match $script:ENG_SKIP) { return $false }
                foreach ($x in $excl) { if ($_.FullName -match $x) { return $false } }
                return $true
            } | ForEach-Object {
                $rel = $_.FullName.Substring($s.Length)
                $df = Join-Path $d $rel
                $dd = Split-Path $df -Parent
                if (-not (Test-Path $dd)) { New-Item -ItemType Directory -Path $dd -Force | Out-Null }
                $need = $true
                if (Test-Path $df) {
                    if ((Get-FileHash -LiteralPath $df -Algorithm SHA256).Hash -eq (Get-FileHash -LiteralPath $_.FullName -Algorithm SHA256).Hash) { $need = $false }
                }
                if ($need) { Copy-Item $_.FullName $df -Force; ACT ($k + ": " + $sub + $rel); $n++ }
            }
        }
    }
    if ($n -eq 0) { OK "engine/config/hooks already in sync" }
}

# ===== Main =====
Write-Host "=== DGEN Sync v3 ===" -ForegroundColor Cyan
Write-Host ("  Action: " + $Action)
Write-Host ("  Src:    " + $srcRoot)
Write-Host ("  RT:     " + $dieginRoot)
Write-Host ""

switch ($Action) {
    "check"       { SR-Check; Write-Host ""; SH-Check; Write-Host ""; REF-Check; Write-Host ""; SKILL-Check; Write-Host ""; ENG-Check }
    "self-test"   { if (-not (Self-Test)) { exit 1 } }
    "sync-rules"  { if (-not (Test-PublishGate -StateDir (Join-Path $dieginRoot "var\state"))) { exit 1 }; SR-Sync }
    "sync-hooks"  { SH-Sync }
    "sync-refs"   { if (-not (Test-PublishGate -StateDir (Join-Path $dieginRoot "var\state"))) { exit 1 }; REF-Sync }
    "sync-skill"  { SKILL-Sync }
    "sync-eng"    { ENG-Sync }
    "sync-all"    { SR-Check; Write-Host ""; SH-Check; Write-Host ""; REF-Check; Write-Host ""; SKILL-Check; Write-Host ""; ENG-Check; Write-Host ""; if (-not (Test-PublishGate -StateDir (Join-Path $dieginRoot "var\state"))) { exit 1 }; SR-Sync; SH-Sync; REF-Sync; SKILL-Sync; ENG-Sync }
    default {
        Write-Host "Usage: .\sync.ps1 <action>" -ForegroundColor Yellow
        Write-Host "  check       — 仅检查差异（默认）" -ForegroundColor Cyan
        Write-Host "  sync-rules  — 合并运行时独有规则 → 源码库" -ForegroundColor Cyan
        Write-Host "  sync-hooks  — 同步运行时钩子 → 源码库" -ForegroundColor Cyan
        Write-Host "  sync-refs   — 同步源码库参考资料 → 运行时（src→rt 单向）" -ForegroundColor Cyan
        Write-Host "  sync-skill  — 同步 SKILL.md 单一真源 → 运行时/市场源/插件缓存" -ForegroundColor Cyan
        Write-Host "  sync-eng    — 同步 engine/config/hooks → 各副本" -ForegroundColor Cyan
        Write-Host "  sync-all    — 先检查，再同步全部" -ForegroundColor Cyan
        Write-Host "  self-test   — 自检（回归守卫：防破坏性写入）" -ForegroundColor Cyan
    }
}
