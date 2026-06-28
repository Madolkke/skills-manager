param(
  [string] $ContainerName = "skills-manager-opencode-1",
  [string] $Image = "ghcr.io/pilinux/opencode:latest"
)

$ErrorActionPreference = "Stop"

$root = Resolve-Path (Join-Path $PSScriptRoot "..")
$envPath = Join-Path $root ".env"
$configDir = Join-Path $root ".data/opencode/config"
$evalRunsDir = Join-Path $root ".data/eval-runs"

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

function Resolve-InWorkspacePath {
  param(
    [string] $Path,
    [string] $DefaultRelativePath
  )

  $candidate = if ($Path) { $Path } else { Join-Path $root $DefaultRelativePath }
  if (-not [System.IO.Path]::IsPathRooted($candidate)) {
    $candidate = Join-Path $root $candidate
  }
  $full = [System.IO.Path]::GetFullPath($candidate)
  $rootFull = [System.IO.Path]::GetFullPath($root)
  if (-not $full.StartsWith($rootFull, [System.StringComparison]::OrdinalIgnoreCase)) {
    throw "Refusing to use a local Opencode path outside workspace: $full"
  }
  return $full
}

function Ensure-OpencodeLaminarPlugin {
  param([string] $ConfigDirectory)

  New-Item -ItemType Directory -Force -Path $ConfigDirectory | Out-Null
  $configPath = Join-Path $ConfigDirectory "config.json"
  $pluginName = "@lmnr-ai/opencode-plugin"
  $config = [ordered]@{
    '$schema' = "https://opencode.ai/config.json"
    plugin = @($pluginName)
  }

  if (Test-Path $configPath) {
    try {
      $existing = Get-Content $configPath -Raw | ConvertFrom-Json
      if ($existing.PSObject.Properties.Name -contains '$schema') {
        $config['$schema'] = $existing.'$schema'
      }
      $plugins = @()
      if ($existing.PSObject.Properties.Name -contains "plugin") {
        $plugins = @($existing.plugin)
      }
      if ($plugins -notcontains $pluginName) {
        $plugins += $pluginName
      }
      foreach ($property in $existing.PSObject.Properties) {
        if ($property.Name -notin @('$schema', 'plugin')) {
          $config[$property.Name] = $property.Value
        }
      }
      $config["plugin"] = $plugins
    } catch {
      $backupPath = "$configPath.bak"
      Copy-Item -LiteralPath $configPath -Destination $backupPath -Force
      Write-Host "Existing config.json could not be parsed; backed up to $backupPath and wrote Laminar plugin config."
    }
  }

  $config | ConvertTo-Json -Depth 20 | Set-Content -Path $configPath -Encoding UTF8
  if (-not (Test-Path (Join-Path $ConfigDirectory ".gitignore"))) {
    Set-Content -Path (Join-Path $ConfigDirectory ".gitignore") -Value "node_modules/`n" -Encoding UTF8
  }
}

function Resolve-OpencodeLaminarGrpcPort {
  param([string] $BaseUrl)

  if ($env:OPENCODE_LMNR_GRPC_PORT) {
    return $env:OPENCODE_LMNR_GRPC_PORT
  }
  if ($env:LMNR_GRPC_PORT) {
    return $env:LMNR_GRPC_PORT
  }
  if ($env:OPENCODE_LMNR_HTTP_PORT -and $env:OPENCODE_LMNR_HTTP_PORT -match "^\d+$") {
    return ([int] $env:OPENCODE_LMNR_HTTP_PORT + 1).ToString()
  }
  if ($BaseUrl -and $BaseUrl -ne "https://api.lmnr.ai") {
    return "8001"
  }
  return ""
}

Import-SkillHubEnv -Path $envPath

foreach ($command in @("docker")) {
  if (-not (Get-Command $command -ErrorAction SilentlyContinue)) {
    throw "$command is required but was not found in PATH."
  }
}

$configDir = Resolve-InWorkspacePath -Path $env:OPENCODE_CONFIG_HOST -DefaultRelativePath ".data/opencode/config"
$evalRunsDir = Resolve-InWorkspacePath -Path $env:EVAL_WORKDIR_HOST -DefaultRelativePath ".data/eval-runs"
$evalRunsContainer = if ($env:EVAL_WORKDIR_CONTAINER) { $env:EVAL_WORKDIR_CONTAINER.TrimEnd("/") } else { "/workspace/eval-runs" }
$laminarBaseUrl = if ($env:OPENCODE_LMNR_BASE_URL) { $env:OPENCODE_LMNR_BASE_URL } elseif ($env:LMNR_BASE_URL) { $env:LMNR_BASE_URL } else { "https://api.lmnr.ai" }
$laminarGrpcPort = Resolve-OpencodeLaminarGrpcPort -BaseUrl $laminarBaseUrl

New-Item -ItemType Directory -Force -Path $evalRunsDir | Out-Null
Ensure-OpencodeLaminarPlugin -ConfigDirectory $configDir

$existing = docker ps -a --filter "name=^/$ContainerName$" --format "{{.Names}}"
if ($existing -eq $ContainerName) {
  docker stop $ContainerName | Out-Null
  docker rm $ContainerName | Out-Null
}

$envArgs = @(
  "-e", "NO_PROXY=127.0.0.1,localhost,host.docker.internal",
  "-e", "no_proxy=127.0.0.1,localhost,host.docker.internal",
  "-e", "LMNR_BASE_URL=$laminarBaseUrl"
)
if ($env:LMNR_PROJECT_API_KEY) {
  $envArgs += @("-e", "LMNR_PROJECT_API_KEY=$env:LMNR_PROJECT_API_KEY")
}
if ($laminarGrpcPort) {
  $envArgs += @("-e", "LMNR_GRPC_PORT=$laminarGrpcPort")
}

$dockerArgs = @(
  "run", "-d",
  "--name", $ContainerName,
  "-p", "127.0.0.1:4096:4096",
  $envArgs,
  "-v", "${configDir}:/home/opencode/.config/opencode",
  "-v", "skills-manager_opencode-share:/home/opencode/.local/share/opencode",
  "-v", "skills-manager_opencode-state:/home/opencode/.local/state/opencode",
  "-v", "${evalRunsDir}:${evalRunsContainer}",
  $Image,
  "sh",
  "-lc",
  "cd /home/opencode/.config/opencode && npm install @lmnr-ai/opencode-plugin >/tmp/opencode-plugin-install.log 2>&1 || (cat /tmp/opencode-plugin-install.log && exit 1); opencode serve --hostname 0.0.0.0 --port 4096"
)

docker @dockerArgs | Out-Host

Write-Host "Opencode started on http://127.0.0.1:4096"
Write-Host "Config: $configDir"
Write-Host "Eval runs mount: $evalRunsDir -> $evalRunsContainer"
Write-Host "Laminar trace config: base=$laminarBaseUrl grpc=$laminarGrpcPort key_set=$([bool] $env:LMNR_PROJECT_API_KEY)"
