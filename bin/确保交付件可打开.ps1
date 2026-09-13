# 确保交付件可打开.ps1 · 通用版（2026-09-12 由 legacy 硬编码版升级）  UTF8-BOM
# 为什么需要（实测三次复发，非推测）：
#   Codex 桌面 UI 里 Markdown 链接 [名](outputs/xxx.md) 是**相对会话 cwd** 解析的。
#   交付件真实位置 = <本次会话交付目录>；若会话 cwd 漂移到上层（如 projectless-tasks），
#   cwd 下没有 outputs ⇒ 点链接打不开（右栏空白）。
#   2026-09-05 按"相对路径"修过一次 → 09-11 复发 → 09-12 复发（根因：会话 cwd 漂移）。
#   ⇒ 修「写法」不等于修「环境」：凡"上次修过又复发"的故障，先查环境漂移。
# 作用：在指定工作区根下建立 outputs 目录联接 → 本次交付目录。幂等；**绝不删除/覆盖真实文件**。
# 用法：
#   powershell -NoProfile -ExecutionPolicy Bypass -File 确保交付件可打开.ps1 -DeliveryDir "E:\...\dgen-xxxx\outputs"
#   powershell -NoProfile -ExecutionPolicy Bypass -File 确保交付件可打开.ps1          # 默认取 cwd 下唯一的 outputs 候选
param([string]$DeliveryDir = "", [string]$WorkspaceRoot = "")
$ErrorActionPreference = 'Stop'

if (-not $DeliveryDir) { throw "必须指定 -DeliveryDir（本次交付目录的绝对路径）" }
if (-not (Test-Path -LiteralPath $DeliveryDir)) { throw "交付目录不存在：$DeliveryDir" }
$real = (Get-Item -LiteralPath $DeliveryDir -Force).FullName
if (-not $WorkspaceRoot -or $WorkspaceRoot.Trim() -eq "") { $WorkspaceRoot = (Get-Location).Path }
$link = Join-Path $WorkspaceRoot "outputs"

if ($real -eq $link) { Write-Output "本目录自带 outputs，无需联接。"; exit 0 }

if (Test-Path -LiteralPath $link) {
  $it = Get-Item -LiteralPath $link -Force
  if (-not $it.LinkType) {
    Write-Output ("注意：{0} 是真实目录（非联接），**未触碰**。" -f $link); exit 0
  }
  $tgt = @($it.Target)[0]
  if ($tgt -and (Test-Path -LiteralPath $tgt)) {
    if ($real -eq (Get-Item -LiteralPath $tgt -Force).FullName) {
      Write-Output ("已就绪：{0} -> {1}" -f $link, $tgt)
    } else {
      # ★ 跨会话防误伤：联接指向别的会话交付目录 → 只报告，不擅自改（改了会破坏那个会话）
      Write-Output ("⚠ 联接已存在但指向【其它目录】：{0} -> {1}" -f $link, $tgt)
      Write-Output ("  本次需要的目标：{0}" -f $real)
      Write-Output  "  处置：若确认旧联接已无会话在用，请人工删除后再跑本脚本；本脚本不自动改指向。"
      exit 2
    }
  } else {
    cmd /c rmdir "$link" | Out-Null
    New-Item -ItemType Junction -Path $link -Target $real | Out-Null
    Write-Output ("断链联接已重建：{0} -> {1}" -f $link, $real)
  }
} else {
  New-Item -ItemType Junction -Path $link -Target $real | Out-Null
  Write-Output ("已建立：{0} -> {1}" -f $link, $real)
}

# 收尾自检：用相对路径真实解析一次（至少一个 .md）
$probe = Get-ChildItem -LiteralPath $link -Filter *.md -EA 0 | Select-Object -First 1
if ($probe) {
  $rel = "outputs/" + $probe.Name
  if (Test-Path -LiteralPath (Join-Path $WorkspaceRoot $rel)) { Write-Output ("自检通过：{0} 可解析。" -f $rel) }
  else { Write-Output "自检未通过：请人工检查。" }
} else { Write-Output "目录已就绪（暂无 .md 可自检）。" }