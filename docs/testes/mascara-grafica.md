# Teste gráfico da máscara de soldagem

Este ensaio mostra se a máscara está **levantada** (vermelho) ou **abaixada** (verde),
usando a câmera. Não exige fotos de exemplo nem treino. Amarelo indica teste parado
ou imagem indisponível. Não é uma liberação para soldagem e não aciona luz física,
sensor, relé ou GPIO.

## Abrir

No PowerShell, na raiz do projeto:

```powershell
python teste_mascara.py
```

Usa OpenCV e Tkinter. Feche qualquer outro programa que esteja usando a câmera.

## Usar

1. Clique em **Conectar** (índice 0; para outra câmera USB, tente 1).
2. Fique de frente para a câmera com a cabeça visível. A imagem inteira é analisada.
3. Clique em **Iniciar teste**.
4. Levante a máscara: o sinal fica **vermelho**.
5. Abaixe a máscara: o sinal fica **verde** após 3 quadros e 0,5 s estável.
6. Desconectar a câmera ou parar o teste remove o verde.

## Como decide

Na imagem inteira da câmera, a máscara é considerada **levantada** se o rosto estiver visível
e **abaixada** se estiver coberto. O rosto conta como visível se o detector de rostos
do OpenCV o encontra ou se há pelo menos 12% de pixels de cor de pele na região central.

Limitações:

- Sem pessoa na área, o resultado é "abaixada" (rosto não visível). Fique no enquadramento.
- Iluminação muito escura ou colorida, barba/pele muito escura e mãos ou pescoço
  dentro da área podem causar erro. O limite de pele foi ajustado com poucas fotos
  de uma só pessoa e cabine, e não foi validado em outras condições.
- Não reconhece pessoas, não grava imagens e não envia nada pela internet.

O código está em `mask_state.py`; os arquivos de coleta e treino (`helmet_experiment.py`
e `ai-service/datasets/local/teste_mascara/`) não são mais usados por esta tela.
