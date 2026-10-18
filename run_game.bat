@echo off
setlocal enabledelayedexpansion
title RCPET IMRD Campus Explorer Launcher

set EXE_PATH=%~dp0output\builds\windows\IMRD_Campus_Explorer.exe
set CONSOLE_PATH=%~dp0output\builds\windows\IMRD_Campus_Explorer_console.exe
set BLENDER_EXE=C:\Program Files\Blender Foundation\Blender 5.2\blender.exe
set BLEND_FILE=%~dp0output\imrd_campus.blend
set BLENDER_SCRIPT=%~dp0scripts\run_game.py

if "%1"=="--blender" goto launch_blender
if "%1"=="--standalone" goto launch_standalone
if "%1"=="--console" goto launch_console

:show_menu
cls
echo ========================================================
echo        RCPET IMRD CAMPUS EXPLORER - GAME LAUNCHER       
echo ========================================================
echo.
echo  [1] Standalone 3D Game (Godot Engine - Recommended)
echo      Full desktop game with updated Blender models,
echo      PBR lighting, quests, audio, and player controls.
echo.
echo  [2] Live Blender 3D Viewport Game (Blender 5.2 EEVEE Next)
echo      Runs directly inside the original Blender .blend file
echo      with realistic EEVEE Next shaders and Python game loop.
echo.
echo  [3] Standalone Game in Console Debug Mode
echo.
echo ========================================================
set /p choice="Select an option [1-3] (Default is 1): "

if "%choice%"=="2" goto launch_blender
if "%choice%"=="3" goto launch_console
goto launch_standalone

:launch_standalone
echo.
echo Launching RCPET IMRD Campus Explorer (Standalone 3D)...
if not exist "%EXE_PATH%" (
    echo [ERROR] Game executable not found at: %EXE_PATH%
    pause
    exit /b 1
)
start "" "%EXE_PATH%"
exit /b 0

:launch_blender
echo.
echo Launching Live Blender 5.2 Interactive Campus...
if not exist "%BLENDER_EXE%" (
    echo [ERROR] Blender executable not found at: %BLENDER_EXE%
    pause
    exit /b 1
)
start "" "%BLENDER_EXE%" "%BLEND_FILE%" --python "%BLENDER_SCRIPT%"
exit /b 0

:launch_console
echo.
echo Launching Standalone with Debug Console...
if not exist "%CONSOLE_PATH%" (
    echo [ERROR] Console executable not found at: %CONSOLE_PATH%
    pause
    exit /b 1
)
"%CONSOLE_PATH%"
exit /b 0

