# 迭进·DGEN UserPromptSubmit 钩子 - AI 回复前迭进预检
# 由 Codex 运行时自动触发，AI 无法绕过

# 从脚本路径推导插件根目录（消除硬编码）
$pluginRoot = Split-Path -Parent (Split-Path -Parent $PSCommandPath)
$auditLog = Join-Path $pluginRoot "diegin_audit.log"
$pythonExe = Join-Path $pluginRoot ".venv\Scripts\python.exe"
$enginePy = Join-Path $pluginRoot "engine\call_diegin.py"
$time = Get-Date -Format "yyyy-MM-dd HH:mm:ss.fff"

try { "$time [HOOK:UserPromptSubmit] FIRED | root=$pluginRoot" | Add-Content -Path $auditLog -ErrorAction SilentlyContinue } catch {}

$dgenOutput = "[DGEN] ⚡ 迭进引擎检查中"

try {
    if (Test-Path $pythonExe) {
        # Step 1: 迭进预检（同步，必须完成）
        $ctxJson = '{"message":"hook","session_id":"dgen"}'
        $checkOutput = $ctxJson | & $pythonExe $enginePy check 2>&1
        if ($LASTEXITCODE -eq 0) {
            $dgenOutput = "[DGEN] ✅ 通过"
            try { "$time [HOOK:DGEN-CHECK] OK" | Add-Content -Path $auditLog -ErrorAction SilentlyContinue } catch {}
        } else {
            try { "$time [HOOK:DGEN-CHECK] ERR exit=$LASTEXITCODE" | Add-Content -Path $auditLog -ErrorAction SilentlyContinue } catch {}
        }

        # Step 2: 守三攻七复盘（同步执行，不阻塞回复）- 快速操作
        try {
            $sandwichOut = & $pythonExe $enginePy sandwich 2>&1
            $exitCode = $LASTEXITCODE
            if ($exitCode -eq 0) {
                "$time [HOOK:SANDWICH] OK | $sandwichOut" | Add-Content -Path $auditLog -ErrorAction SilentlyContinue
            } else {
                "$time [HOOK:SANDWICH] ERR exit=$exitCode | $sandwichOut" | Add-Content -Path $auditLog -ErrorAction SilentlyContinue
            }
        } catch {
            "$time [HOOK:SANDWICH] EXCEPTION | $_" | Add-Content -Path $auditLog -ErrorAction SilentlyContinue
        }

        # Step 3: 举一反三规则泛化（同步执行）
        try {
            $generalizeOut = & $pythonExe $enginePy generalize 2>&1
            $exitCode = $LASTEXITCODE
            if ($exitCode -eq 0) {
                "$time [HOOK:GENERALIZE] OK | $(($generalizeOut | Measure-Object -Line).Lines) lines" | Add-Content -Path $auditLog -ErrorAction SilentlyContinue
            } else {
                "$time [HOOK:GENERALIZE] ERR exit=$exitCode | $generalizeOut" | Add-Content -Path $auditLog -ErrorAction SilentlyContinue
            }
        } catch {
            "$time [HOOK:GENERALIZE] EXCEPTION | $_" | Add-Content -Path $auditLog -ErrorAction SilentlyContinue
        }
    }
} catch {
    try { "$time [HOOK:DGEN-CHECK] EXCEPTION | $_" | Add-Content -Path $auditLog -ErrorAction SilentlyContinue } catch {}
}

# 输出迭进标记注入 AI 上下文
@"
$dgenOutput

## DGEN ⚡ 迭进引擎已激活

当前迭进规则已就绪：
- 系统级拦截规则 + 成功模式
- 守三攻七自动复盘（后台运行）
- 一二不过三错误追踪
- 举一反三规则泛化
- 请在每次回复开头输出 [DGEN] 标记
"@
exit 0
