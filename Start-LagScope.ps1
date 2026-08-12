[CmdletBinding()]
param(
    [ValidateRange(0.001, 1440)]
    [double]$Minutes = 120,

    [ValidateRange(1, 60000)]
    [int]$LatencyThresholdMs = 100,

    [ValidateRange(0, 60)]
    [double]$IntervalSeconds = 1,

    [ValidateRange(1, 60000)]
    [int]$TimeoutMs = 1000,

    [string]$Target = "8.8.8.8",

    [string]$ServiceHost = "example.com",

    [ValidateRange(1, 65535)]
    [int]$ServicePort = 443
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

# $PSScriptRoot is supplied by PowerShell and identifies this script's folder.
$pythonPath = Join-Path $PSScriptRoot ".venv\Scripts\python.exe"
$lagScopePath = Join-Path $PSScriptRoot "src\lagscope.py"

if (-not (Test-Path -LiteralPath $pythonPath)) {
    throw "LagScope virtual-environment Python was not found at: $pythonPath"
}

if (-not (Test-Path -LiteralPath $lagScopePath)) {
    throw "LagScope application was not found at: $lagScopePath"
}

# Run from the repository root so automatic CSV files are placed in .\output.
Push-Location -LiteralPath $PSScriptRoot

try {
    & $pythonPath $lagScopePath `
        --duration-minutes $Minutes `
        --latency-threshold-ms $LatencyThresholdMs `
        --interval $IntervalSeconds `
        --timeout-ms $TimeoutMs `
        --target $Target `
        --service-host $ServiceHost `
        --service-port $ServicePort

    if ($LASTEXITCODE -ne 0) {
        throw "LagScope exited with code $LASTEXITCODE"
    }
}
finally {
    Pop-Location
}
