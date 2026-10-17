@echo off
setlocal
echo ========================================================
echo   Launching RCPET IMRD Campus Explorer (Standalone 3D)  
echo ========================================================

set EXE_PATH=%~dp0output\builds\windows\IMRD_Campus_Explorer.exe
set CONSOLE_PATH=%~dp0output\builds\windows\IMRD_Campus_Explorer_console.exe
set GAME_DIR=%~dp0game

if "%1"=="--console" (
    echo Starting in console debug mode...
    "%CONSOLE_PATH%"
) else (
    echo Launching game window...
    start "" "%EXE_PATH%"
)

endlocal
