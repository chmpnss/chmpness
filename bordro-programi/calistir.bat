@echo off
REM Programi .exe olusturmadan dogrudan calistirir.
cd /d "%~dp0"
set PY=python
where python >nul 2>nul || set PY=py
%PY% -m pip install -q -r requirements.txt
%PY% bordro_app.py
if errorlevel 1 pause
