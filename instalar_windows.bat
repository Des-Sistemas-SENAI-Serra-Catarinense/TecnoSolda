@echo off
chcp 65001 >nul
REM ==========================================================================
REM  Instala o ambiente no WINDOWS (coleta, anotação, treino e teste)
REM  Requisito: Python 3.11, 3.12 ou 3.13 do python.org
REM  (marque "Add python.exe to PATH" na instalação)
REM ==========================================================================
cd /d "%~dp0"

where py >nul 2>nul
if errorlevel 1 (
  echo Python nao encontrado. Instale em https://www.python.org/downloads/ e rode de novo.
  pause & exit /b 1
)

echo == Ambiente do projeto (.venv) ==
py -3 -m venv .venv
.venv\Scripts\python -m pip install --upgrade pip
.venv\Scripts\python -m pip install ultralytics onnx onnxruntime onnxslim

echo.
echo == Label Studio (anotacao) em ambiente separado (.venv-label) ==
py -3 -m venv .venv-label
.venv-label\Scripts\python -m pip install --upgrade pip
.venv-label\Scripts\python -m pip install label-studio

echo.
where nvidia-smi >nul 2>nul
if not errorlevel 1 (
  echo ===================================================================
  echo  Placa NVIDIA encontrada. Para treinar com GPU, instale o PyTorch
  echo  com CUDA DENTRO do .venv:
  echo    1. Abra https://pytorch.org/get-started/locally/
  echo    2. Escolha Windows / Pip / Python / CUDA e copie o comando
  echo    3. Rode o comando copiado trocando "pip3" por ".venv\Scripts\python -m pip"
  echo ===================================================================
) else (
  echo Sem placa NVIDIA: o treino aqui sera na CPU ^(lento^). Para treinar, prefira o Colab.
)

echo.
echo Pronto! Comandos principais (rodar nesta pasta):
echo   Coletar:  .venv\Scripts\python dataset_tools\coletar.py --sessao cab1_ok_ana --mostrar
echo   Anotar:   abrir_label_studio.bat
echo   Dividir:  .venv\Scripts\python dataset_tools\dividir_dataset.py --imagens export\images --rotulos export\labels --classes export\classes.txt --saida dataset --zip
echo   Treinar:  .venv\Scripts\python treino\treinar_local.py --dataset dataset
echo   Testar:   .venv\Scripts\python pi\detector_epi.py --mostrar
echo   Mandar para o Pi:  enviar_para_pi.bat
pause
