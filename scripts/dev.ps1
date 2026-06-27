$ErrorActionPreference = "Stop"

$root = Resolve-Path (Join-Path $PSScriptRoot "..")
$envPath = Join-Path $root ".env"

if (Test-Path $envPath) {
  Get-Content $envPath | ForEach-Object {
    $line = $_.Trim()
    if (-not $line -or $line.StartsWith("#") -or -not $line.Contains("=")) {
      return
    }
    $parts = $line -split "=", 2
    [Environment]::SetEnvironmentVariable($parts[0], $parts[1], "Process")
  }
}

if (-not $env:SKILLHUB_DATABASE_URL) {
  throw "SKILLHUB_DATABASE_URL is required."
}

$hostName = if ($env:SKILLHUB_HOST) { $env:SKILLHUB_HOST } else { "127.0.0.1" }
$apiPort = if ($env:SKILLHUB_API_PORT) { $env:SKILLHUB_API_PORT } else { "8000" }
$webPort = if ($env:SKILLHUB_WEB_PORT) { $env:SKILLHUB_WEB_PORT } else { "3030" }

function Start-SkillHubProcess {
  param(
    [string] $Name,
    [string] $WorkingDirectory,
    [string] $Command
  )
  $process = Start-Process powershell -WindowStyle Hidden -PassThru -ArgumentList @(
    "-NoProfile",
    "-ExecutionPolicy",
    "Bypass",
    "-Command",
    "Set-Location '$WorkingDirectory'; $Command"
  )
  Write-Host "$Name started: pid=$($process.Id)"
}

$apiDir = Join-Path $root "apps/backend"
$webDir = Join-Path $root "apps/frontend"
$workerScript = Join-Path $root "scripts/worker.ps1"

Start-SkillHubProcess -Name "api" -WorkingDirectory $apiDir -Command "uv run uvicorn skillhub.bootstrap.app:create_app --factory --host $hostName --port $apiPort"
Start-SkillHubProcess -Name "web" -WorkingDirectory $webDir -Command "`$env:VITE_SKILLHUB_API_PORT='$apiPort'; if (-not `$env:VITE_OPENCODE_RUN_POLL_INTERVAL_MS) { `$env:VITE_OPENCODE_RUN_POLL_INTERVAL_MS='5000' }; npm run dev -- --host $hostName --port $webPort"
Start-SkillHubProcess -Name "worker" -WorkingDirectory $root -Command "& '$workerScript'"

Write-Host "SkillHub web: http://127.0.0.1:$webPort"
Write-Host "SkillHub API: http://127.0.0.1:$apiPort"
Write-Host "Worker is required for Opencode queued jobs."
