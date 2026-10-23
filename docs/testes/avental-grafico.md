# Teste gráfico do avental

Este ensaio mostra se a pessoa na câmera está **com avental** (verde) ou **sem avental**
(vermelho). Não exige fotos nem treino de modelo: você calibra ao vivo, aparecendo com
e sem o avental. Amarelo indica teste parado, falta de calibração ou imagem indisponível.
Não é uma liberação para soldagem e não aciona luz física, sensor, relé ou GPIO.

## Abrir

```powershell
python teste_avental.py
```

Usa OpenCV e Tkinter. Feche qualquer outro programa que esteja usando a câmera.

## Usar

1. Clique em **Conectar** (índice 0; para outra câmera USB, tente 1).
2. Com o **avental vestido**, fique de frente para a câmera com o tronco visível e clique em
   **Calibrar COM avental** de 3 a 5 vezes, variando levemente posição e inclinação.
3. Sem o avental, faça o mesmo em **Calibrar SEM avental**.
4. Clique em **Iniciar teste**. Vista e tire o avental: vermelho = sem avental; verde = com
   avental, após 3 quadros e 0,5 s estável.
5. **Limpar calibração** apaga as referências. Recalibre se a luz, o fundo ou a roupa mudarem.

## Como decide

Compara a distribuição de cores (luminosidade e cor, no espaço Lab) da imagem inteira com
as duas referências que você calibrou e escolhe a mais próxima. Se a imagem não lembra
nenhuma delas, ou as duas estão igualmente próximas, o resultado é inconclusivo.

Limitações:

- É só cor: não reconhece o avental nem a forma dele. Roupa ou fundo com cor parecida
  pode ser confundido, e roupa diferente da calibrada muda o resultado.
- A imagem inteira entra na comparação (rosto, fundo, outras pessoas). Mantenha o fundo
  igual ao da calibração e apenas uma pessoa em quadro.
- Depende da luz. Não foi validado com aventais reais: confira na tela antes de confiar.
- Não grava imagens, não guarda a calibração em disco e não envia nada pela internet.

O código está em `color_presence.py`; a janela comum em `teste_presenca.py`, aberta por
`teste_avental.py`.
