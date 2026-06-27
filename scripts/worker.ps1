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

if (-not $env:OPENCODE_BASE_URL) {
  $env:OPENCODE_BASE_URL = "http://127.0.0.1:4096"
}

if (-not $env:EVAL_WORKDIR_HOST) {
  $env:EVAL_WORKDIR_HOST = Join-Path $root ".data/eval-runs"
} elseif (-not [System.IO.Path]::IsPathRooted($env:EVAL_WORKDIR_HOST)) {
  $env:EVAL_WORKDIR_HOST = Join-Path $root $env:EVAL_WORKDIR_HOST
}

New-Item -ItemType Directory -Force -Path $env:EVAL_WORKDIR_HOST | Out-Null

Push-Location (Join-Path $root "apps/backend")
try {
  uv run python -m skillhub_worker.main
} finally {
  Pop-Location
}
