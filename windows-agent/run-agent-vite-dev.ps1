param(
  [switch]$Once,
  [string]$Endpoint = "http://localhost:5173/api/pc-status",
  [string]$Token = "change-me",
  [int]$IntervalMs = 1000,
  [string]$Runtime = "win-x64",
  [switch]$SelfContained,
  [switch]$NoBuild
)

$scriptDirectory = Split-Path -Parent $MyInvocation.MyCommand.Path
$publishDirectory = Join-Path $scriptDirectory "publish\vite-dev\$Runtime"
$agentPath = Join-Path $publishDirectory "rpi-dashboard-agent.exe"
$publishEnvPath = Join-Path $publishDirectory ".env"

Set-Location $scriptDirectory

if (-not $NoBuild) {
  $selfContainedValue = if ($SelfContained) { "true" } else { "false" }

  dotnet publish `
    "rpi-dashboard-agent.csproj" `
    -c Release `
    -r $Runtime `
    --self-contained $selfContainedValue `
    -o $publishDirectory

  if ($LASTEXITCODE -ne 0) {
    throw "dotnet publish failed with exit code $LASTEXITCODE."
  }
}

if (-not (Test-Path $agentPath)) {
  throw "Agent executable was not found: $agentPath. Run .\run-agent-vite-dev.ps1 without -NoBuild."
}

@(
  "PC_STATUS_ENDPOINT=$Endpoint",
  "PC_STATUS_TOKEN=$Token",
  "PC_STATUS_INTERVAL_MS=$IntervalMs",
  "PC_STATUS_LOG_NETWORK_DIAGNOSTICS=false",
  "PC_STATUS_LOG_SUCCESS=true",
  "PC_STATUS_LOG_TEMPERATURE_DIAGNOSTICS=false"
) | Set-Content -Encoding UTF8 -Path $publishEnvPath

$arguments = @()

if ($Once) {
  $arguments += "--once"
}

Write-Host "Starting Windows Agent for Vite dev: $Endpoint"

Push-Location $publishDirectory

try {
  & $agentPath @arguments
} finally {
  Pop-Location
}
