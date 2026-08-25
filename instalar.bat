@echo off
setlocal
chcp 65001 >nul
title Instalador - Legenda IA para VLC
cd /d "%~dp0"

echo.
echo  LEGENDA IA PARA VLC - INSTALACAO
echo  ---------------------------------
echo.

set "PY_LAUNCHER="
py -3.12 -c "import struct; raise SystemExit(0 if struct.calcsize('P') == 8 else 1)" >nul 2>&1
if not errorlevel 1 set "PY_LAUNCHER=py -3.12"

if not defined PY_LAUNCHER (
    py -3.13 -c "import struct; raise SystemExit(0 if struct.calcsize('P') == 8 else 1)" >nul 2>&1
    if not errorlevel 1 set "PY_LAUNCHER=py -3.13"
)

if not defined PY_LAUNCHER (
    py -3.11 -c "import struct; raise SystemExit(0 if struct.calcsize('P') == 8 else 1)" >nul 2>&1
    if not errorlevel 1 set "PY_LAUNCHER=py -3.11"
)

if not defined PY_LAUNCHER (
    py -3.10 -c "import struct; raise SystemExit(0 if struct.calcsize('P') == 8 else 1)" >nul 2>&1
    if not errorlevel 1 set "PY_LAUNCHER=py -3.10"
)

if not defined PY_LAUNCHER (
    python -c "import struct, sys; raise SystemExit(0 if (3, 10) ^<= sys.version_info[:2] ^<= (3, 13) and struct.calcsize('P') == 8 else 1)" >nul 2>&1
    if not errorlevel 1 set "PY_LAUNCHER=python"
)

if not defined PY_LAUNCHER (
    python3 -c "import struct, sys; raise SystemExit(0 if (3, 10) ^<= sys.version_info[:2] ^<= (3, 13) and struct.calcsize('P') == 8 else 1)" >nul 2>&1
    if not errorlevel 1 set "PY_LAUNCHER=python3"
)

if not defined PY_LAUNCHER (
    echo ERRO: Python compativel nao foi encontrado.
    echo O aplicativo precisa do Python 3.10, 3.11, 3.12 ou 3.13 de 64 bits.
    echo Se voce instalou o Python 3.14, instale tambem o Python 3.12.10.
    echo Download oficial:
    echo https://www.python.org/ftp/python/3.12.10/python-3.12.10-amd64.exe
    echo Marque a opcao "Add python.exe to PATH" durante a instalacao.
    echo.
    pause
    exit /b 1
)

if exist ".venv\Scripts\python.exe" (
    ".venv\Scripts\python.exe" -c "import struct, sys; raise SystemExit(0 if (3, 10) ^<= sys.version_info[:2] ^<= (3, 13) and struct.calcsize('P') == 8 else 1)" >nul 2>&1
    if errorlevel 1 (
        echo Removendo ambiente antigo incompatível...
        rmdir /s /q ".venv"
    )
)

if not exist ".venv\Scripts\python.exe" (
    echo Criando ambiente do aplicativo...
    %PY_LAUNCHER% -m venv .venv
    if errorlevel 1 goto :failure
)

call ".venv\Scripts\activate.bat"
python -m pip install --upgrade pip wheel setuptools
if errorlevel 1 goto :failure

echo.
echo Instalando suporte CUDA compativel com a GTX 1070...
python -m pip install --upgrade torch==2.7.1 --index-url https://download.pytorch.org/whl/cu118
if errorlevel 1 (
    echo Nao foi possivel instalar a versao CUDA. Tentando a versao para CPU...
    python -m pip install --upgrade torch==2.7.1 --index-url https://download.pytorch.org/whl/cpu
    if errorlevel 1 goto :failure
)

echo.
echo Instalando o aplicativo e as IAs...
python -m pip install --upgrade --prefer-binary -r requirements.txt
if errorlevel 1 goto :failure

echo.
echo Verificando a instalacao...
python -c "import imageio_ffmpeg, sentencepiece, torch, transformers, whisper; print('Componentes: OK'); print('CUDA ativa:', torch.cuda.is_available())"
if errorlevel 1 goto :failure

python -m unittest discover -s tests -v
if errorlevel 1 goto :failure

echo.
echo Instalacao concluida.
echo Agora use o arquivo iniciar.bat.
echo Os modelos de IA serao baixados na primeira legenda.
echo.
pause
exit /b 0

:failure
echo.
echo A instalacao falhou. Verifique sua internet e execute este arquivo novamente.
echo.
pause
exit /b 1
