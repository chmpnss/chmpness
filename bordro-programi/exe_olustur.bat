@echo off
REM Windows'ta tek dosyalik BordroProgrami.exe uretir (dist klasorune).
python -m pip install -r requirements.txt pyinstaller
python -m PyInstaller --noconfirm --onefile --windowed --name BordroProgrami bordro_app.py
echo.
echo Hazir: dist\BordroProgrami.exe
pause
