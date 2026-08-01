$script:utf8NoBOM = [System.Text.UTF8Encoding]::new($false)
function Add-NoBOMLog { param([string]$Path,[string]$Message) $ts=Get-Date -Format "yyyy-MM-dd HH:mm:ss.fff"; $d=Split-Path $Path -Parent; if($d-and -not(Test-Path $d)){New-Item $d -Force|Out-Null}; $oldContent=""; if(Test-Path $Path){$oldContent=[System.IO.File]::ReadAllText($Path,$script:utf8NoBOM)}; [System.IO.File]::WriteAllText($Path,"$ts $Message`r`n$oldContent",$script:utf8NoBOM) }

$pluginRoot = Split-Path -Parent (Split-Path -Parent $PSCommandPath)
$auditLog = Join-Path $pluginRoot "var\logs\diegin_audit.log"
$time = Get-Date -Format "yyyy-MM-dd HH:mm:ss.fff"

$stateFile = Join-Path $pluginRoot "var\state
otify_state.json"
Add-NoBOMLog -Path $auditLog -Message "$time [NOTIFY] diegin enforce | turn-ended"
$state = @{last_notify=(Get-Date -Format "o");status="ok"}
$json = $state | ConvertTo-Json -Compress
[System.IO.File]::WriteAllText($stateFile, $json, $script:utf8NoBOM)
exit 0
