param(
  [string]$TaskName = "RpiWindowsAgent",
  [string]$Runtime = "win-x64",
  [switch]$SelfContained
)

# Проверка прав Администратора
$isAdmin = ([Security.Principal.WindowsPrincipal][Security.Principal.WindowsIdentity]::GetCurrent()).IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)
if (-not $isAdmin) {
  Write-Warning "Этот скрипт требует прав Администратора для регистрации задачи автозапуска."
  Write-Host "Попытка перезапустить скрипт от имени Администратора..." -ForegroundColor Cyan

  $currentShell = [System.Diagnostics.Process]::GetCurrentProcess().MainModule.FileName
  $myPath = $MyInvocation.MyCommand.Path
  $scriptDir = Split-Path -Parent $myPath

  # Используем -NoExit, чтобы окно не закрывалось сразу и пользователь мог увидеть результат/ошибки
  $arguments = @("-NoExit", "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", "`"$myPath`"")
  foreach ($key in $PSBoundParameters.Keys) {
    if ($PSBoundParameters[$key] -is [switch]) {
      if ($PSBoundParameters[$key]) { $arguments += "-$key" }
    } else {
      $arguments += "-$key"
      $arguments += "`"$($PSBoundParameters[$key])`""
    }
  }

  try {
    Start-Process $currentShell -ArgumentList $arguments -WorkingDirectory $scriptDir -Verb RunAs -ErrorAction Stop
    Write-Host "Запущено новое окно с повышенными привилегиями. Пожалуйста, проверьте результаты выполнения в нем." -ForegroundColor Green
    exit
  } catch {
    throw "Не удалось запустить скрипт с правами Администратора: $($_.Exception.Message)`nПожалуйста, запустите PowerShell от имени Администратора вручную и выполните этот скрипт."
  }
}

$scriptDirectory = Split-Path -Parent $MyInvocation.MyCommand.Path
$publishDirectory = Join-Path $scriptDirectory "publish\$Runtime"
$agentPath = Join-Path $publishDirectory "rpi-dashboard-agent.exe"
$envPath = Join-Path $publishDirectory ".env"

# Останавливаем существующую задачу и процессы агента, чтобы разблокировать файлы для сборки
Write-Host "Останавливаем задачу планировщика '$TaskName'..." -ForegroundColor Cyan
Stop-ScheduledTask -TaskName $TaskName -ErrorAction SilentlyContinue

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

# Удаляем старый исполняемый файл с попытками повтора, если он заблокирован
if (Test-Path $agentPath) {
  Write-Host "Удаляем старый исполняемый файл агента..." -ForegroundColor Cyan
  $deleted = $false
  for ($i = 1; $i -le 5; $i++) {
    try {
      Remove-Item $agentPath -Force -ErrorAction Stop
      $deleted = $true
      break
    }
    catch {
      Write-Warning "Файл $agentPath занят, ожидание 1 сек перед повторной попыткой удаления (попытка $i из 5)..."
      Start-Sleep -Seconds 1
    }
  }
  if (-not $deleted) {
    throw "Не удалось удалить файл $agentPath. Убедитесь, что процесс агента действительно завершен."
  }
}

Write-Host "Сборка агента..." -ForegroundColor Cyan
$selfContainedValue = if ($SelfContained) { "true" } else { "false" }

dotnet publish `
  (Join-Path $scriptDirectory "rpi-dashboard-agent.csproj") `
  -c Release `
  -r $Runtime `
  --self-contained $selfContainedValue `
  -o $publishDirectory

if ($LASTEXITCODE -ne 0) {
  throw "Ошибка при выполнении dotnet publish."
}

if (-not (Test-Path $agentPath)) {
  throw "Не удалось найти скомпилированный файл $agentPath."
}

# Копируем .env в директорию публикации
if (Test-Path (Join-Path $scriptDirectory ".env")) {
  Copy-Item (Join-Path $scriptDirectory ".env") (Join-Path $publishDirectory ".env") -Force
} else {
  Copy-Item (Join-Path $scriptDirectory ".env.example") (Join-Path $publishDirectory ".env") -Force
}


if (-not (Test-Path $envPath)) {
  throw "Не найден $envPath. Проверьте publish-каталог."
}

$currentUser = [System.Security.Principal.WindowsIdentity]::GetCurrent().Name

try {
  $existingTask = Get-ScheduledTask -TaskName $TaskName -ErrorAction SilentlyContinue
  if ($existingTask) {
    Unregister-ScheduledTask -TaskName $TaskName -Confirm:$false -ErrorAction Stop
  }

  # Запускаем исполняемый файл агента напрямую из рабочей директории
  $action = New-ScheduledTaskAction -Execute $agentPath -WorkingDirectory $publishDirectory -ErrorAction Stop
  
  # Запуск при старте системы (boot), чтобы агент работал в фоне независимо от входа пользователя
  $trigger = New-ScheduledTaskTrigger -AtStartup -ErrorAction Stop
  $settings = New-ScheduledTaskSettingsSet -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries -ErrorAction Stop
  
  # Используем системную учетную запись SYSTEM с правами Администратора (нужно для LibreHardwareMonitorLib)
  $principal = New-ScheduledTaskPrincipal -UserId "SYSTEM" -LogonType ServiceAccount -RunLevel Highest -ErrorAction Stop

  Register-ScheduledTask `
    -TaskName $TaskName `
    -Action $action `
    -Trigger $trigger `
    -Settings $settings `
    -Principal $principal `
    -Description "Windows agent для панели Raspberry Pi (Запуск от SYSTEM)" `
    -Force `
    -ErrorAction Stop | Out-Null
}
catch {
  throw @"
Не удалось зарегистрировать задачу '$TaskName': $($_.Exception.Message)
Если задача уже существует и заблокирована, попробуйте удалить её в Планировщике задач вручную.
"@
}

$registeredTask = Get-ScheduledTask -TaskName $TaskName -ErrorAction SilentlyContinue
if (-not $registeredTask) {
  throw "После выполнения Register-ScheduledTask задача '$TaskName' не найдена."
}

Write-Host "Задача $TaskName успешно зарегистрирована." -ForegroundColor Green
Write-Host "Тип запуска: При старте системы (от имени SYSTEM)" -ForegroundColor Cyan
Write-Host "Agent EXE: $agentPath" -ForegroundColor Cyan


