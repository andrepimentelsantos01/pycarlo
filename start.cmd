@echo off
setlocal
cd /d "%~dp0"

if /I not "%~1"=="--local" (
    echo Uso: .\start --local
    exit /b 2
)
if not "%~2"=="" (
    echo Uso: .\start --local
    exit /b 2
)

if not exist ".venv\Scripts\python.exe" (
    where py >nul 2>&1
    if not errorlevel 1 (
        py -3 -m venv .venv
    ) else (
        python -m venv .venv
    )
    if errorlevel 1 (
        echo Falha ao criar o ambiente virtual. Instale Python 3.10 ou superior.
        exit /b 1
    )
)

".venv\Scripts\python.exe" -m pip install -e .
if errorlevel 1 (
    echo Falha ao instalar o PyCarlo e suas dependencias no ambiente virtual.
    exit /b 1
)

".venv\Scripts\python.exe" examples\demo.py
if errorlevel 1 (
    echo Falha ao executar o exemplo demonstrativo.
    exit /b 1
)

echo Exemplo concluido. Consulte a pasta output\.
exit /b 0
