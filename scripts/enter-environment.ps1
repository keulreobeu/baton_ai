# Dot-source to enter this checkout, preserving provider settings and runtime state.
$environmentRepo = Split-Path -Parent $PSScriptRoot
$environmentVenv = Join-Path $environmentRepo '.venv'
$environmentPython = Join-Path $environmentVenv 'Scripts/python.exe'
if (-not (Test-Path -LiteralPath $environmentPython)) {
    throw 'Run scripts/setup-environment.ps1 first.'
}
$environmentGitRoot = & git -C $environmentRepo rev-parse --path-format=absolute --git-common-dir 2>$null
if ($LASTEXITCODE -ne 0) { throw 'Cannot locate the shared repository runtime.' }
$environmentRuntimeRepo = Split-Path -Parent $environmentGitRoot
$environmentSource = Join-Path $environmentRepo 'src'
$env:VIRTUAL_ENV = $environmentVenv
$environmentScripts = Join-Path $environmentVenv 'Scripts'
$environmentOldPath = @($env:PATH -split ';' | Where-Object { $_ -ne $environmentScripts })
$env:PATH = (@($environmentScripts) + $environmentOldPath) -join ';'
$environmentOldPythonPath = @($env:PYTHONPATH -split ';' | Where-Object { $_ -and $_ -ne $environmentSource })
$env:PYTHONPATH = (@($environmentSource) + $environmentOldPythonPath) -join ';'
$env:GSTACK_ROOT = (Join-Path $environmentRuntimeRepo '.local_runtime/tooling/.agents/skills/gstack').Replace('\', '/')
$env:GSTACK_HOME = (Join-Path $environmentRuntimeRepo '.local_runtime/gstack').Replace('\', '/')
$env:GSTACK_PLAN_DIR = "$env:GSTACK_HOME/plans"
$env:PLAYWRIGHT_BROWSERS_PATH = (Join-Path $environmentRuntimeRepo '.local_runtime/playwright').Replace('\', '/')
$env:BROWSE_STATE_FILE = "$env:GSTACK_HOME/browser/browse.json"
if (-not $env:ORCA_CLI_COMMAND -and $env:LOCALAPPDATA) {
    $environmentOrca = Join-Path $env:LOCALAPPDATA 'Programs/orca/resources/bin/orca.exe'
    if (Test-Path -LiteralPath $environmentOrca) {
        $env:ORCA_CLI_COMMAND = $environmentOrca
    }
}
Write-Output "BATON checkout: $environmentRepo"
Write-Output "Python: $environmentPython"
Write-Output 'This shell now uses this checkout. Provider settings and task state are unchanged.'
