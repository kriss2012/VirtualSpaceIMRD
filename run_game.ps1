<#
.SYNOPSIS
    Launches the standalone IMRD Campus Explorer 3D game.
.PARAMETER Console
    Launch with console logging enabled for debugging.
#>
param(
    [switch]$Console
)

$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$exePath = Join-Path $scriptDir "output\builds\windows\IMRD_Campus_Explorer.exe"
$consolePath = Join-Path $scriptDir "output\builds\windows\IMRD_Campus_Explorer_console.exe"

if (-not (Test-Path $exePath)) {
    Write-Error "Game executable not found at $exePath. Please run the build pipeline first."
    exit 1
}

Write-Host "========================================================" -ForegroundColor Cyan
Write-Host "   Launching RCPET IMRD Campus Explorer (Standalone 3D)  " -ForegroundColor Yellow
Write-Host "========================================================" -ForegroundColor Cyan

if ($Console) {
    Write-Host "Starting with console output..." -ForegroundColor Green
    & $consolePath
} else {
    Write-Host "Launching desktop game window..." -ForegroundColor Green
    Start-Process -FilePath $exePath
}
