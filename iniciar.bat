@echo off
setlocal
cd /d "%~dp0"

if not exist ".venv\Scripts\pythonw.exe" (
    echo O aplicativo ainda nao foi instalado.
    echo Execute instalar.bat primeiro.
    pause
    exit /b 1
)

".venv\Scripts\python.exe" -m py_compile "app.py" >nul 2>&1
if errorlevel 1 (
    echo O arquivo do aplicativo esta corrompido ou incompleto.
    echo Extraia novamente o pacote completo.
    pause
    exit /b 1
)

".venv\Scripts\python.exe" -c "import app; missing=app.missing_runtime_dependencies(); print('Componentes ausentes: ' + ', '.join(missing)) if missing else None; raise SystemExit(1 if missing else 0)"
if errorlevel 1 (
    echo Execute instalar.bat novamente.
    pause
    exit /b 1
)

start "" ".venv\Scripts\pythonw.exe" "app.py"
