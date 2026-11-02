@echo off
chcp 65001 >nul
echo ========================================================
echo   DANG DONG GOI bangquanaoe.exe (PyInstaller)
echo ========================================================
cd /d "%~dp0"
if not exist ".venv\Scripts\python.exe" (
    python -m venv --system-site-packages .venv
)
if not exist ".venv\Scripts\pyinstaller.exe" (
    .venv\Scripts\pip.exe install -r requirements.txt
)
.venv\Scripts\pyinstaller.exe --noconsole --onefile --name "bangquanaoe" bangquanaoe.py
echo.
echo [HOAN TAT] File chay doc lap da duoc tao tai: dist\bangquanaoe.exe
pause
