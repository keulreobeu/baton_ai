# Install this checkout in its own environment; never repoint another checkout's venv.
[CmdletBinding()]
param([switch]$Offline)
$ErrorActionPreference = 'Stop'
$environmentRepo = Split-Path -Parent $PSScriptRoot
$environmentVenv = Join-Path $environmentRepo '.venv'
$environmentPython = Join-Path $environmentVenv 'Scripts/python.exe'
if (-not (Test-Path -LiteralPath $environmentPython)) {
    & python -m venv $environmentVenv
    if ($LASTEXITCODE -ne 0) { throw 'Could not create the checkout virtual environment.' }
}
$environmentPipArgs = @()
if ($Offline) { $environmentPipArgs += '--no-index' }
& $environmentPython -m pip install @environmentPipArgs 'setuptools>=68' wheel
if ($LASTEXITCODE -ne 0) { throw 'Could not install build dependencies.' }
& $environmentPython -m pip install @environmentPipArgs --no-build-isolation -e "${environmentRepo}[gms]"
if ($LASTEXITCODE -ne 0) { throw 'Could not install this BATON checkout.' }
& $environmentPython -m pip check
if ($LASTEXITCODE -ne 0) { throw 'Dependency check failed.' }
Write-Output "Installed BATON from $environmentRepo"
Write-Output "Enter this environment: . '$PSScriptRoot/enter-environment.ps1'"
