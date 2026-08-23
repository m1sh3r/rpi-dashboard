param(
  [string]$TaskName = "RpiWindowsAgent"
)

# Проверка прав Администратора
$isAdmin = ([Security.Principal.WindowsPrincipal][Security.Principal.WindowsIdentity]::GetCurrent()).IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)
if (-not $isAdmin) {
  Write-Warning "Этот скрипт требует прав Администратора для полной остановки службы/задачи автозапуска."
  Write-Host "Попытка перезапустить скрипт от имени Администратора..." -ForegroundColor Cyan

  $currentShell = [System.Diagnostics.Process]::GetCurrentProcess().MainModule.FileName
  $myPath = $MyInvocation.MyCommand.Path
  $scriptDir = Split-Path -Parent $myPath

  $arguments = @("-NoProfile", "-ExecutionPolicy", "Bypass", "-File", "`"$myPath`"")
  foreach ($key in $PSBoundParameters.Keys) {
    $arguments += "-$key"
    $arguments += "`"$($PSBoundParameters[$key])`""
  }

  try {
    Start-Process $currentShell -ArgumentList $arguments -WorkingDirectory $scriptDir -Verb RunAs -ErrorAction Stop
    exit
  } catch {
    Write-Warning "Не удалось запустить от имени Администратора. Продолжаем выполнение с текущими правами..."
  }
}

Write-Host "Остановка процессов и задач Windows Agent..." -ForegroundColor Cyan

$taskStopped = $false
try {
  $task = Get-ScheduledTask -TaskName $TaskName -ErrorAction SilentlyContinue
  if ($task) {
    Stop-ScheduledTask -TaskName $TaskName -ErrorAction Stop
    $taskStopped = $true
  }
} catch {
  Write-Warning "Не удалось остановить запланированную задачу '$TaskName'. $($_.Exception.Message)"
}

$processStopped = $false
$processes = Get-Process -Name "rpi-dashboard-agent" -ErrorAction SilentlyContinue
if ($processes) {
  Stop-Process -Name "rpi-dashboard-agent" -Force -ErrorAction Stop
  $processStopped = $true
}

if ($taskStopped) {
  Write-Host "Запланированная задача '$TaskName' успешно остановлена." -ForegroundColor Green
}
if ($processStopped) {
  Write-Host "Процессы 'rpi-dashboard-agent' успешно завершены." -ForegroundColor Green
}
if (-not $taskStopped -and -not $processStopped) {
  Write-Host "Активных процессов или задач агента не найдено." -ForegroundColor Yellow
}
