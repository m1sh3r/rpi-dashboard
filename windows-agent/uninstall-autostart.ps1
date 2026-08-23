param(
  [string]$TaskName = "RpiWindowsAgent",
  [string]$Runtime = "win-x64",
  [switch]$RemoveFiles
)

# Проверка прав Администратора
$isAdmin = ([Security.Principal.WindowsPrincipal][Security.Principal.WindowsIdentity]::GetCurrent()).IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)
if (-not $isAdmin) {
  Write-Warning "Этот скрипт требует прав Администратора для удаления задачи автозапуска."
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

# Останавливаем задачу планировщика
Write-Host "Останавливаем задачу планировщика '$TaskName'..." -ForegroundColor Cyan
Stop-ScheduledTask -TaskName $TaskName -ErrorAction SilentlyContinue

# Удаляем задачу из Планировщика задач
Write-Host "Удаляем задачу '$TaskName' из Планировщика задач..." -ForegroundColor Cyan
try {
  $existingTask = Get-ScheduledTask -TaskName $TaskName -ErrorAction SilentlyContinue
  if ($existingTask) {
    Unregister-ScheduledTask -TaskName $TaskName -Confirm:$false -ErrorAction Stop
    Write-Host "Задача '$TaskName' успешно удалена." -ForegroundColor Green
  } else {
    Write-Host "Задача '$TaskName' не найдена в Планировщике задач." -ForegroundColor Yellow
  }
}
catch {
  Write-Warning "Не удалось удалить задачу '$TaskName': $($_.Exception.Message)"
}

# Завершаем процессы агента, если они запущены
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

# Удаляем исполняемые файлы, если передан флаг -RemoveFiles
if ($RemoveFiles) {
  if (Test-Path $publishDirectory) {
    Write-Host "Удаляем файлы сборки в каталоге: $publishDirectory..." -ForegroundColor Cyan
    try {
      Remove-Item $publishDirectory -Recurse -Force -ErrorAction Stop
      Write-Host "Файлы сборки успешно удалены." -ForegroundColor Green
    }
    catch {
      Write-Warning "Не удалось удалить каталог сборки $publishDirectory. Ошибка: $($_.Exception.Message)"
    }
  }
} else {
  Write-Host "Файлы сборки в каталоге '$publishDirectory' сохранены. Для их удаления запустите скрипт с флагом -RemoveFiles." -ForegroundColor Gray
}

Write-Host "Удаление автозапуска завершено." -ForegroundColor Green
