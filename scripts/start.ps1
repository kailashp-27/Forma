param([ValidateRange(1024,65535)][int]$Port = 8765)
$ErrorActionPreference = 'Stop'
$projectRoot = Split-Path -Parent $PSScriptRoot
Set-Location -LiteralPath $projectRoot
if (-not (Test-Path '.venv\Scripts\python.exe')) { throw 'Run .\scripts\setup.ps1 first.' }
if (-not (Test-Path 'frontend\dist\index.html')) { throw 'Build the UI first: cd frontend; npm.cmd run build' }
$env:COACH_PORT = [string]$Port
Write-Host "Open http://localhost:$Port. Press Ctrl+C to stop." -ForegroundColor Green
& .\.venv\Scripts\python.exe -m backend
exit $LASTEXITCODE
