@echo off
REM Windows'ta tek dosyalik BordroProgrami.exe uretir (dist klasorune).
cd /d "%~dp0"
set PY=python
where python >nul 2>nul || set PY=py
%PY% -m pip install -r requirements.txt pyinstaller
if errorlevel 1 goto hata
%PY% -m PyInstaller --noconfirm --onefile --windowed --name BordroProgrami bordro_app.py
if errorlevel 1 goto hata
if not exist "dist\BordroProgrami.exe" goto hata
echo.
echo Hazir: %~dp0dist\BordroProgrami.exe
explorer "%~dp0dist"
pause
exit /b 0
:hata
echo.
echo HATA: exe olusturulamadi. Yukaridaki mesajlarin fotografini gonderin.
pause
exit /b 1
