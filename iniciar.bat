@echo off
title Iniciando meu-app-geo (Geoprocessamento)
color 0B
echo =================================================================
echo             MEU-APP-GEO - PROCESSADOR DE COORDENADAS
echo =================================================================
echo.
echo [1/2] Iniciando o servidor Flask em segundo plano...
echo.

:: Abre o navegador padrao do usuario no endereço local da aplicacao
start http://localhost:5000

:: Executa a aplicacao Python
python app.py

if %ERRORLEVEL% neq 0 (
    color 0C
    echo.
    echo [ERRO] Ocorreu um problema ao executar o Python. 
    echo Certifique-se de que o Python esta instalado e adicionado ao PATH do Windows.
    echo.
    pause
)
