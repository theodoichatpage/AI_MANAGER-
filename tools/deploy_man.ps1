# Deploy a branch into the live MAN checkout and restart MAN, only by the session that owns deploys.
# Usage: powershell -ExecutionPolicy Bypass -File tools\deploy_man.ps1 -Owner "<session name>" [-Branch wincontrol/takeover-20261111]
# The owner is written in %LOCALAPPDATA%\AI_MANAGER\DEPLOY_OWNER.json. Any other caller is refused.
param(
  [Parameter(Mandatory=$true)][string]$Owner,
  [string]$Branch = 'wincontrol/takeover-20261111',
  [string]$Prod = 'C:\Users\PC\Projects\AI_MANAGER'
)
$ErrorActionPreference = 'Stop'
$lockPath = Join-Path $env:LOCALAPPDATA 'AI_MANAGER\DEPLOY_OWNER.json'
if (-not (Test-Path -LiteralPath $lockPath)) { throw "No deploy owner recorded in $lockPath; refusing." }
$lock = Get-Content -LiteralPath $lockPath -Raw -Encoding utf8 | ConvertFrom-Json
if ($lock.owner -ne $Owner) { throw "Deploy owner is '$($lock.owner)', not '$Owner'; refusing. Ask the user before changing the owner." }

$stamp = (Get-Date).ToUniversalTime().ToString('yyyyMMddTHHmmssZ')
$receipts = Join-Path $Prod "integration_reports\deploys\$stamp"
New-Item -ItemType Directory -Path $receipts -Force | Out-Null

function Git { param([Parameter(ValueFromRemainingArguments=$true)]$a) $out = & git -C $Prod @a 2>&1; if ($LASTEXITCODE) { throw "git $($a -join ' '): $out" }; $out }

function Get-CheckpointView($state) {
  $tasks = @($state.automation.tasks | ForEach-Object {
    [ordered]@{ id=$_.id; status=$_.status; in_flight=[bool]$_.in_flight; next_action=$_.next_action; result_count=@($_.results).Count }
  } | Sort-Object id)
  $queue = @($state.queue | ForEach-Object {
    [ordered]@{ id=$_.id; status=$_.status; automation_task_id=$_.automation_task_id; action_done=$_.action_done; action_total=$_.action_total }
  } | Sort-Object id)
  [ordered]@{ tasks=$tasks; queue=$queue }
}

function Start-Manager {
  $pythonw = Join-Path $env:LOCALAPPDATA 'AI_MANAGER\runtime-v02\Scripts\pythonw.exe'
  Start-Process -FilePath $pythonw -ArgumentList @('app_launcher.pyw','--background') -WorkingDirectory $Prod -WindowStyle Hidden
  $deadline = (Get-Date).AddSeconds(90)
  while ((Get-Date) -lt $deadline) {
    try { $s = Invoke-RestMethod 'http://127.0.0.1:8765/api/state' -TimeoutSec 3; if ($s.automation.online -and $s.automation.pid) { return $s } } catch { }
    Start-Sleep -Milliseconds 500
  }
  throw 'Manager did not return online within 90 seconds.'
}

function Stop-Manager {
  $l = Get-NetTCPConnection -State Listen -ErrorAction SilentlyContinue | Where-Object LocalPort -eq 8765 | Select-Object -First 1
  if (-not $l) { return }
  Stop-Process -Id $l.OwningProcess -Force
  $deadline = (Get-Date).AddSeconds(20)
  while ((Get-Date) -lt $deadline -and (Get-NetTCPConnection -State Listen -ErrorAction SilentlyContinue | Where-Object LocalPort -eq 8765)) { Start-Sleep -Milliseconds 250 }
  if (Get-NetTCPConnection -State Listen -ErrorAction SilentlyContinue | Where-Object LocalPort -eq 8765) { throw 'Old Manager did not release port 8765.' }
  Start-Sleep -Seconds 2
}

# 1. Live MAN must be served from $Prod and idle.
$before = Invoke-RestMethod 'http://127.0.0.1:8765/api/state' -TimeoutSec 10
$listener = Get-NetTCPConnection -State Listen | Where-Object LocalPort -eq 8765 | Select-Object -First 1
if (-not $listener) { throw 'Manager listener is missing; refusing.' }
$cmd = (Get-CimInstance Win32_Process -Filter "ProcessId=$($listener.OwningProcess)").CommandLine
if ($cmd -notmatch [regex]::Escape((Join-Path $Prod 'server.py')) -and $cmd -notmatch 'server\.py') { throw "Port 8765 is not this MAN: $cmd" }
# A stopped task can keep an old in_flight flag (kept on purpose for review); only running/waiting work blocks a restart.
$active = @($before.automation.tasks | Where-Object { $_.status -in @('running','waiting') })
$runningQueue = @($before.queue | Where-Object { $_.status -eq 'running' })
if ($before.automation.current_task -or $active.Count -or $runningQueue.Count) {
  throw "Active work (tasks: $(@($active.id) -join ','); queue: $(@($runningQueue.name) -join ',')); refusing restart. Pause production at a safe point first."
}

# 2. Prod checkout: only untracked files and tracked .pyc may differ; the branch must fast-forward.
$dirty = @(Git status --porcelain --untracked-files=no | Where-Object { $_ -notmatch '\.pyc$' })
if ($dirty.Count) { throw "Prod checkout has uncommitted source changes: $($dirty -join '; ')" }
$old = (Git rev-parse HEAD).Trim()
$new = (Git rev-parse $Branch).Trim()
if ($old -eq $new) { Write-Output 'Already deployed; restarting is not needed.'; return }
& git -C $Prod merge-base --is-ancestor $old $new; if ($LASTEXITCODE) { throw "$Branch does not fast-forward from $old; merge it into main first." }

$beforeView = Get-CheckpointView $before
$beforeView | ConvertTo-Json -Depth 8 | Set-Content -LiteralPath (Join-Path $receipts 'before.json') -Encoding utf8
[ordered]@{ owner=$Owner; branch=$Branch; from=$old; to=$new; files=@(Git diff --name-only $old $new) } | ConvertTo-Json -Depth 4 | Set-Content -LiteralPath (Join-Path $receipts 'plan.json') -Encoding utf8

$moved = $false
try {
  Git merge --ff-only $new | Out-Null; $moved = $true
  Stop-Manager
  $after = Start-Manager
  $left = $beforeView | ConvertTo-Json -Depth 8 -Compress
  $right = (Get-CheckpointView $after) | ConvertTo-Json -Depth 8 -Compress
  if ($left -cne $right) { $right | Set-Content -LiteralPath (Join-Path $receipts 'after_mismatch.json') -Encoding utf8; throw 'Task/queue checkpoints changed during restart.' }
  if ($after.automation.current_task) { throw 'Agent did not come back idle.' }
  $js = (Invoke-WebRequest 'http://127.0.0.1:8765/wincontrol.js' -UseBasicParsing -TimeoutSec 10).Content
  if ($js -notmatch 'winControlSubmit') { throw 'WinControl UI bundle was not served.' }
  $result = [ordered]@{ result='deployed'; at=$stamp; owner=$Owner; from=$old; to=$new; manager_pid=(Get-NetTCPConnection -State Listen | Where-Object LocalPort -eq 8765 | Select-Object -First 1).OwningProcess; agent_pid=$after.automation.pid; checkpoints='unchanged'; studio=$after.studio.status; extension=$after.extension.status }
  $result | ConvertTo-Json -Depth 4 | Set-Content -LiteralPath (Join-Path $receipts 'result.json') -Encoding utf8
  $result | ConvertTo-Json -Depth 4 -Compress
}
catch {
  $failure = $_.Exception.Message
  Set-Content -LiteralPath (Join-Path $receipts 'failure.txt') -Value $failure -Encoding utf8
  if ($moved) {
    Stop-Manager
    # Controlled rollback of this deploy only: --keep refuses if it would drop local changes.
    Git reset --keep $old | Out-Null
    try { $null = Start-Manager } catch { throw "Deploy failed ($failure); code rolled back to $old but Manager restart failed: $($_.Exception.Message)" }
  }
  throw "Deploy failed and was rolled back to ${old}: $failure"
}
