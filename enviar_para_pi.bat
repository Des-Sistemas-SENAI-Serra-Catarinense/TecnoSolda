@echo off
chcp 65001 >nul
REM ==========================================================================
REM  Copia a pasta pi\ (programa + config + modelo) para o Raspberry Pi via SSH
REM  No Pi, o SSH precisa estar ativado (Raspberry Pi Imager > Personalizar > SSH)
REM ==========================================================================
cd /d "%~dp0"

if not exist pi\modelos\epi_solda.onnx (
  echo ATENCAO: pi\modelos\epi_solda.onnx nao existe ainda. Treine ou copie o modelo antes.
  pause & exit /b 1
)

set /p IP=IP do Raspberry Pi (ex.: 192.168.0.50): 
set /p USUARIO=Usuario do Pi [pi]: 
if "%USUARIO%"=="" set USUARIO=pi

echo.
echo == Criando a pasta no Pi (vai pedir a senha do Pi) ==
ssh %USUARIO%@%IP% "mkdir -p ~/epi-solda-yolo"
echo == Copiando arquivos ==
scp -r pi %USUARIO%@%IP%:~/epi-solda-yolo/
echo == Ajustando quebras de linha do Windows (CRLF) para Linux ==
ssh %USUARIO%@%IP% "sed -i 's/\r$//' ~/epi-solda-yolo/pi/*.sh ~/epi-solda-yolo/pi/*.py && rm -rf ~/epi-solda-yolo/pi/__pycache__"

echo.
echo Enviado! No Pi:
echo   1a vez:        cd ~/epi-solda-yolo/pi ^&^& bash instalar_pi.sh
echo   Atualizacoes:  sudo systemctl restart epi-solda
pause
