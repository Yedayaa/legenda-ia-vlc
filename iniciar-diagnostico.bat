@echo off
setlocal
chcp 65001 >nul
cd /d "%~dp0"

if not exist ".venv\Scripts\python.exe" (
    echo O aplicativo ainda nao foi instalado.
    echo Execute instalar.bat primeiro.
    pause
    exit /b 1
)

echo Abrindo o Legenda IA em modo de diagnostico...
echo Nao feche esta janela enquanto o aplicativo estiver aberto.
echo.
".venv\Scripts\python.exe" "app.py"
echo.
echo O aplicativo foi encerrado.
pause
