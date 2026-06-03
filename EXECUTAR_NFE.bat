@echo off
setlocal enabledelayedexpansion

echo ===================================================
echo INICIANDO AUTOMACAO NFE
echo ===================================================

cd /d "%~dp0"

rem Deixamos o script Python decidir a aba correta (Hoje vs Amanha)
python -u "gerar_nfe_automatica.py"

if %ERRORLEVEL% NEQ 0 (
    echo [ERRO] Ocorreu um problema na execucao.
    pause
) else (
    echo [OK] Processamento finalizado.
    timeout /t 10
)
