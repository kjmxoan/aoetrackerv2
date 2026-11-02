@echo off
chcp 65001 >nul
echo ========================================================
echo   DANG DONG GOI bangquanaoe.exe (PyInstaller)
echo ========================================================
cd /d "%~dp0"
pip install -r requirements.txt
pyinstaller --noconsole --onefile --name "bangquanaoe" bangquanaoe.py
echo.
echo [HOAN TAT] File chay doc lap da duoc tao tai: dist\bangquanaoe.exe
pause
