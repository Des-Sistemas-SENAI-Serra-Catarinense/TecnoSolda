@echo off
chcp 65001 >nul
cd /d "%~dp0"
echo Abrindo o Label Studio em http://localhost:8080  (feche esta janela para parar)
.venv-label\Scripts\label-studio start
