param([switch]$SkipPose, [switch]$SkipFrontend)
$ErrorActionPreference = 'Stop'
$projectRoot = Split-Path -Parent $PSScriptRoot
Set-Location -LiteralPath $projectRoot
$env:TEMP = Join-Path $projectRoot 'artifacts\tmp'
$env:TMP = $env:TEMP
New-Item -ItemType Directory -Force $env:TEMP | Out-Null
function Invoke-Checked { param([scriptblock]$Command) & $Command; if ($LASTEXITCODE -ne 0) { throw "Command failed with exit code $LASTEXITCODE" } }
if (-not (Test-Path '.venv\Scripts\python.exe')) {
    Invoke-Checked { python -m venv --without-pip .venv }
}
$requirements = if ($SkipPose) { 'requirements-core.txt' } else { 'requirements-ml.txt' }
# Keep the project independent from globally installed Python packages.
(Get-Content .venv\pyvenv.cfg) -replace 'include-system-site-packages = true','include-system-site-packages = false' | Set-Content .venv\pyvenv.cfg
$constraints = @()
if (Test-Path 'requirements-lock.txt') { $constraints = @('-c','requirements-lock.txt') }
# Use the host pip to seed environments where ensurepip is restricted.
Invoke-Checked { python -m pip --python .venv\Scripts\python.exe install @constraints -r $requirements }
if (-not $SkipFrontend) {
    Push-Location frontend
    try { Invoke-Checked { npm.cmd ci }; Invoke-Checked { npm.cmd run build } } finally { Pop-Location }
}
if (-not $SkipPose) {
    Invoke-Checked { .\.venv\Scripts\python.exe scripts\download_model.py }
    Invoke-Checked { .\.venv\Scripts\python.exe scripts\doctor.py --deep }
    Invoke-Checked { .\.venv\Scripts\python.exe scripts\verify_pose.py }
}
Write-Host 'Setup complete. Start with: .\scripts\start.ps1' -ForegroundColor Green
