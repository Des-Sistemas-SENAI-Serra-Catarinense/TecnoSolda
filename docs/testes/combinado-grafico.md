# Teste gráfico combinado de EPIs

Uma só janela mostra **máscara, luva e avental** ao mesmo tempo, cada um com sua cor,
e a combinação geral. Não exige fotos nem treino de modelo e não aciona luz física,
sensor, relé ou GPIO. Não é uma liberação para soldagem.

## Abrir

```powershell
python teste_combinado.py
```

## Usar

1. Clique em **Conectar** e posicione-se de frente para a câmera, com cabeça, tronco e mãos visíveis.
2. Calibre **uma combinação por botão** (a máscara não precisa de calibração): com a
   máscara abaixada, vista exatamente o que o botão diz e clique de 3 a 5 vezes,
   variando levemente a posição:
   - **COM luva + COM avental**
   - **COM luva + SEM avental**
   - **SEM luva + COM avental**
   - **SEM luva + SEM avental**

   As quatro precisam ser calibradas; enquanto faltar alguma, luva e avental ficam
   indefinidos. O contador entre parênteses mostra quantos cliques cada botão já recebeu.
3. Clique em **Iniciar teste** e vista ou tire os itens.

## Combinações

| Máscara | Luva | Avental | Resultado geral |
| --- | --- | --- | --- |
| abaixada | com luva | com avental | **Verde** (após 0,5 s estável) |
| levantada | qualquer | qualquer | Vermelho |
| qualquer | sem luva | qualquer | Vermelho |
| qualquer | qualquer | sem avental | Vermelho |
| sem nenhum item fora do padrão, mas algum indefinido | | | Amarelo |

O vermelho vem de qualquer item comprovadamente fora do padrão, mesmo que outro esteja
indefinido. O verde exige os três corretos ao mesmo tempo, cada um com 3 quadros e
0,5 s estáveis. Cada cartão mostra o estado do item e o texto geral lista o que está pendente.

## Como decide

- **Máscara**: rosto visível = levantada; coberto = abaixada ([mascara-grafica.md](mascara-grafica.md)).
- **Luva e avental**: cor da imagem inteira comparada às quatro combinações calibradas
  (versões isoladas: [luva-grafica.md](luva-grafica.md), [avental-grafico.md](avental-grafico.md)).

Como luva e avental usam a **mesma imagem inteira**, a calibração é por combinação:
cada botão guarda como a imagem fica naquela combinação, e o teste escolhe a mais próxima.
Assim, uma mudança causada só pelo avental não é atribuída à luva. Se as duas combinações
mais próximas discordam num item e estão muito parecidas, só esse item fica indefinido.

Limitações: a cor da roupa, do fundo e a luz têm de ser as da calibração; recalibre se
mudarem. Não foi validado com EPIs reais. Nada é gravado em disco nem enviado pela internet.

## O que está sendo identificado

Com **Mostrar o que está sendo identificado** marcado e o teste rodando, a imagem da câmera
ganha caixas e a linha "Marcado na imagem" lista o que foi marcado. As caixas mostram o que
sustenta cada decisão:

| Caixa | Cor | O que é |
| --- | --- | --- |
| Rosto | azul | Rosto encontrado pelo detector do OpenCV (máscara levantada) |
| Pele | azul | Maior região de cor de pele na área central (também indica máscara levantada) |
| Luva (cor compativel) | laranja | Maior região com cores que só aparecem nas referências "com luva" |
| Avental (cor compativel) | roxo | Maior região com cores que só aparecem nas referências "com avental" |

Elas **não são detecção de objeto**: são regiões de cor ou de rosto. Servem para você ver se o
teste está olhando para a coisa certa. Se a caixa da luva aparecer no fundo ou na roupa, a
calibração está confundindo outra coisa com a luva; recalibre com fundo e luz iguais aos do teste.
Sem o item (ou com item indefinido) não há caixa. As marcações só aparecem enquanto a análise
está recente (até 0,6 s); sem imagem ou com o teste parado elas somem. Os textos nas caixas não
têm acentos porque o OpenCV não os desenha.
