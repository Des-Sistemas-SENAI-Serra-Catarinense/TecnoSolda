# Teste gráfico da luva de raspa

Este ensaio mostra se a mão na câmera está **com luva de raspa** (verde) ou **sem luva**
(vermelho). Não exige fotos nem treino de modelo: você calibra ao vivo, mostrando a mão
com e sem luva. Amarelo indica teste parado, falta de calibração ou imagem indisponível.
Não é uma liberação para soldagem e não aciona luz física, sensor, relé ou GPIO.

## Abrir

```powershell
python teste_luva.py
```

Usa OpenCV e Tkinter. Feche qualquer outro programa que esteja usando a câmera.

## Usar

1. Clique em **Conectar** (índice 0; para outra câmera USB, tente 1).
2. Com a **luva calçada**, mostre a mão bem à frente da câmera e clique em
   **Calibrar COM luva** de 3 a 5 vezes, variando posição e ângulo.
3. Com a **mão nua**, faça o mesmo em **Calibrar SEM luva**.
4. Clique em **Iniciar teste**. Calce e tire a luva: vermelho = sem luva; verde = com
   luva, após 3 quadros e 0,5 s estável.
5. **Limpar calibração** apaga as referências. Recalibre se a luz ou o fundo mudarem.

## Como decide

Compara a distribuição de cores (luminosidade e cor, no espaço Lab) da área da mão com
as duas referências que você calibrou e escolhe a mais próxima. Se a imagem não lembra
nenhuma delas, ou as duas estão igualmente próximas, o resultado é inconclusivo.

Limitações:

- É só cor: não reconhece mãos nem a forma da luva. Qualquer coisa com cor parecida
  (couro, mesa de madeira, pele de outra pessoa) pode ser confundida.
- Analisa a imagem inteira: rosto, roupa e fundo entram na comparação, então mantenha só a mão em destaque. Não distingue esquerda de direita.
- Depende da luz e do fundo. Mantenha o fundo igual ao da calibração.
- Não foi validado com luvas reais. Confira vendo o resultado na tela antes de confiar.
- Não grava imagens, não guarda a calibração em disco e não envia nada pela internet.

O código está em `color_presence.py`; a janela comum em `teste_presenca.py`, aberta por `teste_luva.py`.
