@echo off
setlocal
echo ========================================================
echo   Launching RCPET IMRD Campus Explorer (Standalone 3D)  
echo ========================================================

set EXE_PATH=%~dp0IMRD_Campus_Explorer.exe
set CONSOLE_PATH=%~dp0IMRD_Campus_Explorer_console.exe
set GAME_DIR=%~dp0..\..\..\game

if "%1"=="--console" (
    echo Starting in console debug mode...
    "%CONSOLE_PATH%" --path "%GAME_DIR%"
) else (
    echo Launching game window...
    start "" "%EXE_PATH%" --path "%GAME_DIR%"
)

endlocal
