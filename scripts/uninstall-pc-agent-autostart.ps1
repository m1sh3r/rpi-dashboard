param(
    [string]$TaskName = "RpiPythonPcAgent"
)

Stop-ScheduledTask -TaskName $TaskName -ErrorAction SilentlyContinue
Unregister-ScheduledTask -TaskName $TaskName -Confirm:$false -ErrorAction SilentlyContinue

Write-Host "Задача '$TaskName' успешно остановлена и удалена из Планировщика задач." -ForegroundColor Green
