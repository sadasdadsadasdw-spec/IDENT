# Export task configuration to XML for analysis

$TaskName = "IdentBitrix24Integration"
$TaskPath = "\IDENT\"
$OutputFile = "task_config.xml"

Write-Host "Exporting task configuration..." -ForegroundColor Cyan

Export-ScheduledTask -TaskName $TaskName -TaskPath $TaskPath | Out-File -FilePath $OutputFile -Encoding UTF8

Write-Host "Saved to: $OutputFile" -ForegroundColor Green
Write-Host ""
Write-Host "Task details:" -ForegroundColor Cyan
Write-Host ""

# Show triggers
Write-Host "Triggers:" -ForegroundColor Yellow
Get-ScheduledTask -TaskName $TaskName -TaskPath $TaskPath |
    Select-Object -ExpandProperty Triggers |
    ForEach-Object { Write-Host "  $($_.GetType().Name)" -ForegroundColor White }

Write-Host ""

# Show actions
Write-Host "Actions:" -ForegroundColor Yellow
Get-ScheduledTask -TaskName $TaskName -TaskPath $TaskPath |
    Select-Object -ExpandProperty Actions |
    ForEach-Object {
        Write-Host "  Execute: $($_.Execute)" -ForegroundColor White
        Write-Host "  Arguments: $($_.Arguments)" -ForegroundColor White
        Write-Host "  WorkingDir: $($_.WorkingDirectory)" -ForegroundColor White
    }

Write-Host ""
Write-Host "Check task_config.xml for full details" -ForegroundColor Yellow
