@echo off
chcp 65001 >nul
echo ╔══════════════════════════════════════════════════╗
echo ║     SpaceSniffer - Build Script                  ║
echo ║     Build standalone Windows executable          ║
echo ╚══════════════════════════════════════════════════╝
echo.

:: Check Python
python --version >nul 2>&1
if %errorlevel% neq 0 (
    echo [ERROR] Python not found. Please install Python 3.8+.
    pause
    exit /b 1
)

:: Check / install PyInstaller
python -c "import PyInstaller" >nul 2>&1
if %errorlevel% neq 0 (
    echo [INFO] Installing PyInstaller...
    pip install pyinstaller
    if %errorlevel% neq 0 (
        echo [ERROR] Failed to install PyInstaller.
        pause
        exit /b 1
    )
)

echo [INFO] Building SpaceSniffer.exe ...
echo.

python -m PyInstaller ^
    --onefile ^
    --windowed ^
    --name SpaceSniffer ^
    --clean ^
    --hidden-import tkinter ^
    --hidden-import tkinter.ttk ^
    --hidden-import tkinter.filedialog ^
    --hidden-import tkinter.messagebox ^
    --hidden-import queue ^
    --hidden-import threading ^
    --hidden-import ctypes ^
    --hidden-import collections ^
    --hidden-import pathlib ^
    --noconfirm ^
    space_sniffer.py

if %errorlevel% equ 0 (
    echo.
    echo ╔══════════════════════════════════════════════════╗
    echo ║  BUILD SUCCESS!                                 ║
    echo ║  Executable: dist\SpaceSniffer.exe              ║
    echo ╚══════════════════════════════════════════════════╝
    echo.
    echo Run: dist\SpaceSniffer.exe
) else (
    echo.
    echo [ERROR] Build failed. Check output above.
)

pause
