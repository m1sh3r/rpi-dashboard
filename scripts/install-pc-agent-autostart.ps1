param(
    [string]$TaskName = "RpiPythonPcAgent"
)

$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$agentScript = Join-Path $scriptDir "pc_agent.py"

$pythonw = (Get-Command pythonw.exe -ErrorAction SilentlyContinue).Source
if (-not $pythonw) {
    $pythonExe = (Get-Command python.exe -ErrorAction SilentlyContinue).Source
    if ($pythonExe) {
        $candidate = Join-Path (Split-Path -Parent $pythonExe) "pythonw.exe"
        if (Test-Path $candidate) {
            $pythonw = $candidate
        } else {
            $pythonw = $pythonExe
        }
    } else {
        throw "Python не найден в PATH. Пожалуйста, убедитесь, что Python установлен."
    }
}

Write-Host "Используется интерпретатор: $pythonw" -ForegroundColor Cyan
Write-Host "Скрипт агента: $agentScript" -ForegroundColor Cyan

Unregister-ScheduledTask -TaskName $TaskName -Confirm:$false -ErrorAction SilentlyContinue

$action = New-ScheduledTaskAction -Execute "`"$pythonw`"" -Argument "`"$agentScript`"" -WorkingDirectory $scriptDir
$trigger = New-ScheduledTaskTrigger -AtLogOn
$settings = New-ScheduledTaskSettingsSet -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries -ExecutionTimeLimit 0

Register-ScheduledTask `
    -TaskName $TaskName `
    -Action $action `
    -Trigger $trigger `
    -Settings $settings `
    -Description "RPI Dashboard Python Metrics Agent" `
    -Force | Out-Null

Start-ScheduledTask -TaskName $TaskName

Write-Host "Задача '$TaskName' успешно зарегистрирована в Планировщике задач Windows и запущена в фоновом режиме." -ForegroundColor Green
