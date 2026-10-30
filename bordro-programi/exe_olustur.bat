@echo off
REM Windows'ta tek dosyalik BordroProgrami.exe uretir (dist klasorune).
cd /d "%~dp0"
set PY=python
where python >nul 2>nul || set PY=py
%PY% -m pip install -r requirements.txt pyinstaller
%PY% -m PyInstaller --noconfirm --onefile --windowed --name BordroProgrami bordro_app.py
echo.
echo Hazir: dist\BordroProgrami.exe
pause
