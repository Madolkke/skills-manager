param(
  [switch] $SkipWorker
)

$ErrorActionPreference = "Stop"

$root = Resolve-Path (Join-Path $PSScriptRoot "..")
$envPath = Join-Path $root ".env"
$logDir = Join-Path $root ".logs"

New-Item -ItemType Directory -Force -Path $logDir | Out-Null

<#
Loads simple KEY=VALUE entries from the store .env file into the current
process environment. Lines without "=" and comments are ignored.
#>
function Import-SkillHubEnv {
  param([string] $Path)

  if (-not (Test-Path $Path)) {
    return
  }

  Get-Content $Path | ForEach-Object {
    $line = $_.Trim()
    if (-not $line -or $line.StartsWith("#") -or -not $line.Contains("=")) {
      return
    }

    $parts = $line -split "=", 2
    $name = $parts[0].Trim()
    $value = $parts[1].Trim()
    if (($value.StartsWith('"') -and $value.EndsWith('"')) -or ($value.StartsWith("'") -and $value.EndsWith("'"))) {
      $value = $value.Substring(1, $value.Length - 2)
    }
    [Environment]::SetEnvironmentVariable($name, $value, "Process")
  }
}

<#
Returns a single-quoted PowerShell literal for embedding paths in child process
commands without relying on the caller's current directory.
#>
function ConvertTo-PowerShellLiteral {
  param([string] $Value)

  return "'" + $Value.Replace("'", "''") + "'"
}

<#
Checks whether a local TCP port is already listening so repeated script runs do
not start duplicate API or Web processes.
#>
function Test-LocalPortListening {
  param(
    [int] $Port,
    [string] $HostName
  )

  try {
    $connections = Get-NetTCPConnection -LocalPort $Port -State Listen -ErrorAction Stop
  } catch {
    return $false
  }

  foreach ($connection in $connections) {
    if ($HostName -eq "0.0.0.0" -or $connection.LocalAddress -in @($HostName, "0.0.0.0", "::", "127.0.0.1")) {
      return $true
    }
  }
  return $false
}

<#
Detects an existing SkillHub worker process. The worker has no listening port,
so process command line matching is the least invasive duplicate guard.
#>
function Test-WorkerRunning {
  $worker = Get-CimInstance Win32_Process | Where-Object {
    $_.CommandLine -match "skillhub_worker\.main"
  } | Select-Object -First 1

  return $null -ne $worker
}

<#
Starts a hidden long-running service process and redirects stdout/stderr into
.logs so startup failures are inspectable without keeping terminals open.
#>
function Start-SkillHubProcess {
  param(
    [string] $Name,
    [string] $WorkingDirectory,
    [string] $Command
  )

  $outLog = Join-Path $logDir "$Name.out.log"
  $errLog = Join-Path $logDir "$Name.err.log"
  $workingDirectoryLiteral = ConvertTo-PowerShellLiteral $WorkingDirectory
  $childCommand = "Set-Location -LiteralPath $workingDirectoryLiteral; $Command"
  $process = Start-Process powershell -WindowStyle Hidden -PassThru `
    -RedirectStandardOutput $outLog `
    -RedirectStandardError $errLog `
    -ArgumentList @(
      "-NoProfile",
      "-ExecutionPolicy",
      "Bypass",
      "-Command",
      $childCommand
    )

  Write-Host "$Name started: pid=$($process.Id), logs=$outLog / $errLog"
}

Import-SkillHubEnv -Path $envPath

if (-not $env:SKILLHUB_DATABASE_URL) {
  throw "SKILLHUB_DATABASE_URL is required. Configure it in .env."
}

if (-not $env:OPENCODE_BASE_URL) {
  $env:OPENCODE_BASE_URL = "http://127.0.0.1:4096"
}

if (-not $env:NO_PROXY) {
  $env:NO_PROXY = "127.0.0.1,localhost,host.docker.internal"
}
if (-not $env:no_proxy) {
  $env:no_proxy = $env:NO_PROXY
}

foreach ($command in @("uv", "npm")) {
  if (-not (Get-Command $command -ErrorAction SilentlyContinue)) {
    throw "$command is required but was not found in PATH."
  }
}

$hostName = if ($env:SKILLHUB_HOST) { $env:SKILLHUB_HOST } else { "127.0.0.1" }
$apiPort = if ($env:SKILLHUB_API_PORT) { [int] $env:SKILLHUB_API_PORT } else { 8000 }
$webPort = if ($env:SKILLHUB_WEB_PORT) { [int] $env:SKILLHUB_WEB_PORT } else { 3030 }
$pollInterval = if ($env:VITE_OPENCODE_RUN_POLL_INTERVAL_MS) { $env:VITE_OPENCODE_RUN_POLL_INTERVAL_MS } else { "5000" }

$apiDir = Join-Path $root "apps/backend"
$webDir = Join-Path $root "apps/frontend"
$workerScript = Join-Path $root "scripts/worker.ps1"

Write-Host "External dependencies are expected to be running already:"
Write-Host "  PostgreSQL: configured by SKILLHUB_DATABASE_URL"
Write-Host "  Opencode:   $env:OPENCODE_BASE_URL"

if (Test-LocalPortListening -Port $apiPort -HostName $hostName) {
  Write-Host "api already listening on ${hostName}:${apiPort}; skipped."
} else {
  Start-SkillHubProcess -Name "api" -WorkingDirectory $apiDir -Command "uv run uvicorn skillhub.bootstrap.app:create_app --factory --host $hostName --port $apiPort"
}

if (Test-LocalPortListening -Port $webPort -HostName $hostName) {
  Write-Host "web already listening on ${hostName}:${webPort}; skipped."
} else {
  Start-SkillHubProcess -Name "web" -WorkingDirectory $webDir -Command "`$env:VITE_SKILLHUB_API_PORT='$apiPort'; `$env:VITE_OPENCODE_RUN_POLL_INTERVAL_MS='$pollInterval'; npm run dev -- --host $hostName --port $webPort"
}

if ($SkipWorker) {
  Write-Host "worker skipped by -SkipWorker."
} elseif (Test-WorkerRunning) {
  Write-Host "worker already running; skipped."
} else {
  $workerScriptLiteral = ConvertTo-PowerShellLiteral $workerScript
  Start-SkillHubProcess -Name "worker" -WorkingDirectory $root -Command "& $workerScriptLiteral"
}

Write-Host ""
Write-Host "SkillHub web: http://127.0.0.1:$webPort/skills"
Write-Host "SkillHub API: http://127.0.0.1:$apiPort"
Write-Host "Logs: $logDir"
