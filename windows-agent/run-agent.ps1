param(
  [switch]$Once,
  [string]$Runtime = "win-x64",
  [switch]$SelfContained,
  [switch]$NoBuild
)

$scriptDirectory = Split-Path -Parent $MyInvocation.MyCommand.Path
$publishDirectory = Join-Path $scriptDirectory "publish\$Runtime"
$agentPath = Join-Path $publishDirectory "rpi-dashboard-agent.exe"

Set-Location $scriptDirectory

if (-not (Test-Path ".env")) {
  Copy-Item ".env.example" ".env"
  Write-Host "Создан .env из .env.example. Проверьте PC_STATUS_ENDPOINT и PC_STATUS_TOKEN."
}

if (-not $NoBuild) {
  # Завершаем текущие сессии агента (процесс и планировщик задач), чтобы освободить файлы для перезаписи
  Write-Host "Останавливаем задачу планировщика 'RpiWindowsAgent'..." -ForegroundColor Cyan
  Stop-ScheduledTask -TaskName "RpiWindowsAgent" -ErrorAction SilentlyContinue

  $agentProcesses = Get-Process -Name "rpi-dashboard-agent" -ErrorAction SilentlyContinue
  if ($agentProcesses) {
    Write-Host "Найдены запущенные процессы агента. Завершаем их принудительно..." -ForegroundColor Yellow
    $agentProcesses | Stop-Process -Force -ErrorAction SilentlyContinue
    
    # Ожидаем завершения процессов до 5 секунд
    $timeout = 5
    while ((Get-Process -Name "rpi-dashboard-agent" -ErrorAction SilentlyContinue) -and $timeout -gt 0) {
      Start-Sleep -Seconds 1
      $timeout--
    }
  }

  # Дополнительно пытаемся удалить старый exe перед публикацией, чтобы проверить блокировку
  if (Test-Path $agentPath) {
    try {
      Remove-Item $agentPath -Force -ErrorAction Stop
    }
    catch {
      Write-Warning "Файл $agentPath заблокирован! Публикация dotnet может завершиться ошибкой, если процесс не был завершен с правами Администратора."
    }
  }

  $selfContainedValue = if ($SelfContained) { "true" } else { "false" }

  dotnet publish `
    "rpi-dashboard-agent.csproj" `
    -c Release `
    -r $Runtime `
    --self-contained $selfContainedValue `
    -o $publishDirectory

  Copy-Item ".env" (Join-Path $publishDirectory ".env") -Force
}

if (-not (Test-Path $agentPath)) {
  throw "Не найден $agentPath. Выполните .\run-agent.ps1 без -NoBuild."
}

$arguments = @()

if ($Once) {
  $arguments += "--once"
}

& $agentPath @arguments

