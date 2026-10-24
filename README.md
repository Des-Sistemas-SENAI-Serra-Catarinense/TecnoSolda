# Detector de EPI na Cabine de Solda — YOLO26 + Raspberry Pi 3

Webcam apontada para a cabine → Raspberry Pi 3 roda um modelo YOLO treinado pela turma →
se o aluno está **com a tocha na mão** e falta **luva**, **avental** ou **máscara abaixada**,
o Pi aciona um **relé** e acende a **luz vermelha**.

```
webcam ──► Raspberry Pi 3 ──► YOLO26n (.onnx) ──► regras ──► GPIO17 ──► relé ──► luz vermelha
```

```
epi-solda-yolo/
├── instalar_windows.bat           # prepara o Windows (Python + Ultralytics + Label Studio)
├── abrir_label_studio.bat         # abre a ferramenta de anotação
├── enviar_para_pi.bat             # copia a pasta pi\ para o Raspberry via rede (SSH)
├── dataset_tools/
│   ├── coletar.py                 # tira fotos da webcam/vídeo por cenário (sessão)
│   ├── label_studio_config.xml    # interface de anotação com as 8 classes
│   ├── classes.txt
│   └── dividir_dataset.py         # separa treino/validação por sessão e gera dataset.zip
├── treino/
│   ├── treinar_epi_solda.ipynb    # notebook do Google Colab (GPU grátis)
│   └── treinar_local.py           # treino no próprio PC (bom se tiver placa NVIDIA)
└── pi/
    ├── config.py                  # TUDO que se ajusta por cabine fica aqui
    ├── detector_epi.py            # programa que roda no Pi
    ├── testar_regras.py           # testa a lógica sem câmera nem modelo
    └── instalar_pi.sh             # instala dependências + serviço de inicialização
```

---

## Custo zero

Todo o software é gratuito. O único gasto é o hardware (Pi 3, webcam, módulo relé e sinalizador).

| Etapa | Ferramenta | Custo |
|---|---|---|
| Coleta, dataset, teste ao vivo | Python + OpenCV | grátis |
| Anotação | Label Studio Community (local) | grátis |
| Treino | Ultralytics YOLO26 no **Google Colab** (GPU T4 do plano grátis) | grátis |
| Rodar no Pi | Raspberry Pi OS 64-bit + ONNX Runtime + gpiozero | grátis |
| Enviar para o Pi | SSH/SCP que já vem no Windows | grátis |

- **Ultralytics (AGPL-3.0):** grátis para uso escolar/didático. A licença paga só é exigida para vender ou distribuir o sistema com código fechado.
- **Colab grátis:** a sessão cai se ficar parada ou depois de algumas horas, e às vezes a GPU não está disponível. O notebook salva tudo no Drive: basta reabrir e continuar. Se o Colab negar a GPU, o **Kaggle Notebooks** também é grátis (≈30 h de GPU por semana).
- **PC deste projeto:** Ryzen 3 5400U com vídeo AMD, **sem NVIDIA**. Treine no Colab; o `treinar_local.py` aqui roda na CPU e leva muitas horas.
- **Python:** use o **3.12** do python.org (grátis). O `instalar_windows.bat` pede 3.11–3.13, e o Label Studio pode falhar no 3.14.

---

## Checklist: o que fazer e com qual arquivo

| # | O que fazer | Arquivo | Pronto? |
|---|---|---|---|
| 1 | Instalar o Python 3.12 e rodar a instalação no Windows | [instalar_windows.bat](instalar_windows.bat) | ☐ |
| 2 | Fixar a webcam na cabine na posição definitiva | — (ver passo 0) | ☐ |
| 3 | Gravar as sessões de fotos, **com você como modelo** | [dataset_tools/coletar.py](dataset_tools/coletar.py) | ☐ |
| 4 | Anotar as fotos (8 classes) | [abrir_label_studio.bat](abrir_label_studio.bat) + [dataset_tools/label_studio_config.xml](dataset_tools/label_studio_config.xml) | ☐ |
| 5 | Exportar "YOLO with Images" e montar o `dataset.zip` | [dataset_tools/dividir_dataset.py](dataset_tools/dividir_dataset.py) | ☐ |
| 6 | Subir o `dataset.zip` para `Meu Drive/epi_solda/` e treinar no Colab | [treino/treinar_epi_solda.ipynb](treino/treinar_epi_solda.ipynb) | ☐ |
| 7 | Baixar `epi_solda.onnx` do Drive para `pi\modelos\` | [pi/modelos/](pi/modelos/) | ☐ |
| 8 | Testar no Windows com a webcam | [pi/detector_epi.py](pi/detector_epi.py) `--mostrar` | ☐ |
| 9 | Gravar o cartão do Pi (Raspberry Pi OS Lite **64-bit**, SSH ligado) | Raspberry Pi Imager | ☐ |
| 10 | Mandar a pasta `pi\` para o Raspberry | [enviar_para_pi.bat](enviar_para_pi.bat) | ☐ |
| 11 | Instalar no Pi e testar a lógica | [pi/instalar_pi.sh](pi/instalar_pi.sh), [pi/testar_regras.py](pi/testar_regras.py) | ☐ |
| 12 | Ligar o relé e a luz no GPIO17 | — (ver passo 6) | ☐ |
| 13 | Calibrar `ZONA_SUPORTE`, `CONFIANCA_MIN` etc. e ativar o serviço | [pi/config.py](pi/config.py) | ☐ |
| 14 | Testar com outras pessoas e retreinar com os erros (v2) | notebook (fim) + `SALVAR_FOTOS` | ☐ |

> [treino/gerar_notebook.py](treino/gerar_notebook.py) só serve para recriar o `.ipynb`. Não precisa rodar.

---

## Fluxo de trabalho: tudo no Windows, depois manda para o Pi

Todo o desenvolvimento roda no Windows; o Pi só recebe a pasta `pi\` pronta.

| Etapa | Onde | Comando (na pasta do projeto) |
|---|---|---|
| Instalar | Windows | duplo clique em `instalar_windows.bat` |
| Coletar fotos | Windows + webcam | `.venv\Scripts\python dataset_tools\coletar.py --sessao cab1_ok_ana --mostrar` |
| Anotar | Windows | `abrir_label_studio.bat` |
| Montar dataset | Windows | `.venv\Scripts\python dataset_tools\dividir_dataset.py --imagens export\images --rotulos export\labels --classes export\classes.txt --saida dataset --zip` |
| Treinar | Windows c/ NVIDIA **ou** Colab | `.venv\Scripts\python treino\treinar_local.py --dataset dataset` |
| Testar ao vivo | Windows + webcam | `.venv\Scripts\python pi\detector_epi.py --mostrar` |
| Enviar | Windows → Pi | duplo clique em `enviar_para_pi.bat` |
| Rodar | Pi | `bash instalar_pi.sh` (1ª vez) e `sudo systemctl restart epi-solda` |

- No Windows a luz roda em **modo simulado** automaticamente: aparece no terminal e como um círculo vermelho na janela do `--mostrar`. O mesmo código, sem mudar nada, aciona o relé quando roda no Pi.
- Webcam USB num notebook costuma ser a câmera **1** (a 0 é a embutida): use `--fonte 1`.
- O teste no Windows mostra se o **modelo** acerta. A velocidade real só se vê no Pi 3, que é bem mais lento.
- **Use a mesma webcam e a mesma posição** na coleta e no Pi. Se coletar com a câmera ligada no notebook e depois passar para o Pi, a imagem é a mesma.
- Ajuste o `pi\config.py` no Windows e reenvie: o `enviar_para_pi.bat` sobrescreve a pasta no Pi e já corrige as quebras de linha do Windows.

---

## As 8 classes (o que anotar)

O modelo não detecta bem a *ausência* de algo, então ensinamos ele a ver **o EPI** e também **a falta dele**.

| Classe | Caixa em volta de… |
|---|---|
| `tocha` | a tocha/pistola (corpo + pescoço), na mão **ou** pendurada no suporte |
| `mao_com_luva` | cada mão com luva de raspa de solda |
| `mao_sem_luva` | cada mão sem luva (luva de procedimento/fina também conta como **sem**) |
| `avental` | o avental de raspa visível |
| `tronco_sem_avental` | o tronco do aluno quando ele **não** está de avental |
| `mascara_abaixada` | a máscara cobrindo o rosto (posição de soldar) |
| `mascara_levantada` | a máscara na cabeça, virada para cima |
| `cabeca_sem_mascara` | a cabeça/rosto sem máscara nenhuma |

**Regra da luz** (`avaliar_quadro()` em `detector_epi.py`):

1. A tocha está **em uso** se a caixa dela encosta numa caixa de mão — ou, se `ZONA_SUPORTE` estiver configurada, se ela saiu da zona do suporte.
2. Com a tocha em uso, falta EPI quando aparece uma classe de falta (`mao_sem_luva`, `tronco_sem_avental`, `mascara_levantada`, `cabeca_sem_mascara`).
   No `MODO_ESTRITO` (padrão), também conta como falta quando o EPI **não é visto** — é o comportamento mais seguro.
3. Para não piscar, a luz acende quando **3 dos últimos 5** quadros têm violação e apaga depois de **3 quadros seguidos** sem violação (ajustável no `config.py`).

---

## Passo a passo

### 0. Posicionar a câmera (antes de coletar qualquer foto)

- Posição **fixa e definitiva**: o modelo aprende *aquela* cena. Mudou a câmera de lugar, precisa de mais dados.
- Precisa enxergar ao mesmo tempo: tocha, as duas mãos, tronco e cabeça. Vista lateral/diagonal de cima costuma funcionar melhor que frontal.
- **Não aponte direto para o arco** e proteja a lente com uma placa de policarbonato contra respingos.
- Use exposição manual (`EXPOSICAO_MANUAL` no `config.py`) para a imagem não "estourar" quando o arco abre. O momento mais confiável da decisão é quando o aluno **pega a tocha**, antes do arco.

### 1. Coletar imagens na cabine

Com o Pi (ou um notebook) e **a mesma webcam já instalada**:

```bash
python3 dataset_tools/coletar.py --sessao cab1_ok_ana --intervalo 0.7 --duracao 60
```

**Na 1ª versão, o modelo nas fotos é só você** (nenhum aluno aparece). Cada sessão é um cenário.
Como o modelo vai ver uma pessoa só, **varie o máximo possível** para ele não "decorar" você:

- roupas diferentes (cores, manga curta/longa, jaleco, camiseta), boné/cabelo preso ou solto;
- as duas mãos, mão esquerda e direita na tocha, posições em pé/inclinado, de lado e de frente para a câmera;
- horários e luz diferentes (manhã, tarde, luz da cabine acesa/apagada, porta aberta/fechada);
- se tiver, luvas, aventais e máscaras de modelos e cores diferentes.

Coloque um número de variação no fim do nome da sessão (`_r1`, `_r2`… = roupa/luz). O `dividir_dataset.py` separa a validação por sessão.

| Sessão (exemplo) | O que você faz |
|---|---|
| `cab1_ok_tochamao_r1` | EPI completo, pega a tocha, posiciona para soldar |
| `cab1_ok_arco_r1` | EPI completo **soldando de verdade** (o modelo precisa ver o arco) |
| `cab1_ok_parado_r1` | EPI completo, tocha no suporte, mexendo na peça |
| `cab1_semluva_r1` | sem luva em 1 e em 2 mãos, pegando a tocha |
| `cab1_semavental_r1` | sem avental, pegando a tocha |
| `cab1_mascaraup_r1` | máscara levantada na cabeça, pegando a tocha |
| `cab1_semmascara_r1` | sem máscara, pegando a tocha |
| `cab1_vazia_r1` | cabine vazia (ensina o que **não** é nada) |

Exemplo, com prévia para enquadrar (webcam USB no notebook costuma ser `--fonte 1`):

```bat
.venv\Scripts\python dataset_tools\coletar.py --sessao cab1_semluva_r1 --fonte 1 --duracao 60 --mostrar
```

> ⚠️ **Segurança:** todo cenário **sem EPI** é gravado com a **máquina de solda desligada**: você só simula. Nunca abra arco sem EPI para gerar dados. Para a sessão `ok_arco`, peça para outra pessoa iniciar/parar a coleta.

> 🔒 **LGPD:** como as fotos de treino são só suas, você pode subi-las para o Google Drive/Colab. Ainda assim, **evite o plano gratuito do Roboflow**: nele, todo projeto fica público no Roboflow Universe. Quando alunos entrarem nas imagens (testes reais e passo 8), aí sim precisa de autorização de uso de imagem (dos responsáveis, no caso de menores), e as fotos devem ficar nas máquinas da escola.

Meta para a 1ª versão: algumas centenas de fotos variadas (umas 30–60 por sessão, várias sessões de cada cenário), com pelo menos ~100 exemplos de cada classe. Depois o ciclo de melhoria (passo 8) aumenta isso com os erros reais.

### 2. Anotar com o Label Studio (roda local, dados não saem da escola)

No Windows: duplo clique em `abrir_label_studio.bat` (abre em http://localhost:8080).

1. Crie um projeto → **Settings › Labeling Interface › Code** → cole `dataset_tools/label_studio_config.xml`.
2. Importe as fotos da pasta `coleta/` (pode dividir sessões entre os alunos; teclas 1–8 escolhem a classe).
3. Regras de anotação (combine com a turma e siga **sempre igual**):
   - anote **tudo** que aparece em **todas** as fotos, inclusive a tocha parada no suporte;
   - objeto cortado na borda ou tampado: anote se dá para reconhecer (mais ou menos 1/3 visível);
   - caixa justa no objeto, sem sobra grande.
4. O professor revisa por amostragem (≈10%) — erro de anotação vira erro do modelo.
5. **Export › YOLO with Images** → descompacte numa pasta `export/`.

### 3. Montar o dataset

```bash
python3 dataset_tools/dividir_dataset.py --imagens export/images --rotulos export/labels \
        --classes export/classes.txt --saida dataset --zip
```

Separa treino/validação **por sessão** (quadros do mesmo vídeo são quase iguais; misturar daria uma validação falsamente boa), mostra quantos exemplos cada classe tem e gera `dataset.zip`.

### 4. Treinar (no PC ou no Colab)

**No Windows**, se tiver placa NVIDIA (siga o aviso do `instalar_windows.bat` para instalar o PyTorch com CUDA):

```bat
.venv\Scripts\python treino\treinar_local.py --dataset dataset
```

Ele mostra as métricas por classe e já deixa o modelo em `pi\modelos\epi_solda.onnx`.
Sem placa NVIDIA o treino roda na CPU, mas pode levar horas; prefira o Colab:

1. Suba `dataset.zip` para `Meu Drive/epi_solda/dataset.zip`.
2. Abra `treino/treinar_epi_solda.ipynb` no Colab → **Ambiente de execução › Alterar tipo › GPU T4**.
3. Rode as células em ordem. Os resultados ficam salvos no Drive em `epi_solda/treinos/epi_v1/`.
4. Confira na célula 5 o **recall das classes de falta** — é ele que garante que a luz acende quando deve.
5. A célula 7 gera `exportados/epi_solda.onnx` no Drive: baixe e coloque em `pi\modelos\epi_solda.onnx`.

Antes de ir para o Pi, teste no Windows com a webcam: `.venv\Scripts\python pi\detector_epi.py --mostrar`.

### 5. Instalar no Raspberry Pi 3

- Grave o cartão com **Raspberry Pi OS Lite (64-bit)** pelo Raspberry Pi Imager (o 32-bit não roda o ONNX Runtime). Em *Personalizar*, ative o **SSH** e o Wi-Fi.
- No Windows, rode `enviar_para_pi.bat` (pede o IP e a senha do Pi; usa o SSH que já vem no Windows 10/11).
- No Pi (pelo SSH: `ssh pi@IP`):

```bash
cd ~/epi-solda-yolo/pi
bash instalar_pi.sh
~/epi-venv/bin/python testar_regras.py   # lógica OK?
~/epi-venv/bin/python detector_epi.py    # modelo + câmera + relé
```

> Se aparecer `$'\r': command not found`, o arquivo foi com quebra de linha do Windows: `sed -i 's/\r$//' *.sh *.py` (o `enviar_para_pi.bat` já faz isso).

### 6. Ligar a luz

```
Pi pino 2  (5V)      ──► VCC do módulo relé
Pi pino 6  (GND)     ──► GND do módulo relé
Pi pino 11 (GPIO17)  ──► IN  do módulo relé
Relé COM + NA        ──► interrompem a alimentação do sinalizador vermelho
```

- Para testar na bancada, um LED + resistor de 330 Ω no GPIO17 basta.
- Se a luz ficar invertida, troque `RELE_ATIVO_EM_BAIXO` no `config.py`.
- Prefira sinalizador de **12/24 V** com fonte própria. Ligação em 127/220 V só por pessoa habilitada (NR-10).

### 7. Calibrar e colocar para rodar sozinho

```bash
~/epi-venv/bin/python detector_epi.py --mostrar   # precisa de monitor/VNC
```

- Clique na imagem para ver coordenadas e defina `ZONA_SUPORTE` (onde a tocha fica pendurada).
- Ajuste `CONFIANCA_MIN`, `MODO_ESTRITO`, `JANELA`/`LIMIAR_LIGA` conforme os testes.
- Sem monitor: `--salvar-video teste.mp4 --max-quadros 200` e assista no PC.
- Quando estiver bom: `sudo systemctl enable --now epi-solda` (inicia sozinho ao ligar). Logs: `journalctl -u epi-solda -f`.
- Cada violação fica registrada em `pi/registros/violacoes.csv` (início, fim, EPIs faltando).
- Se a câmera desconectar, a luz vermelha **pisca** (modo falha).

### 8. Ciclo de melhoria

Um modelo treinado só com você pode errar com outras pessoas (outro tamanho, outra roupa, tom de pele). Este passo corrige isso.

1. Ative `SALVAR_FOTOS = True` por alguns dias. As fotos agora são de alunos: só com autorização de uso de imagem, guardadas nas máquinas da escola (sem Drive/Colab), e o treino da v2 fica no PC local (lento, mas grátis; use `--epocas 60 --imgsz 320` e coloque `IMGSZ = 320` no `config.py`).
2. Separe os **erros**: luz acesa sem motivo e faltas que passaram.
3. Anote, rode o `dividir_dataset.py` de novo e treine `epi_v2` partindo do `best.pt` anterior (instruções no fim do notebook).

---

## Desempenho e limites

- O Pi 3 analisa **poucos quadros por segundo** (o programa mostra o valor a cada 5 s). Para esta tarefa basta, porque a decisão é suavizada em ~2–3 s. Se ficar lento demais: treine e exporte com `IMGSZ = 320`, ou use um Pi 4/5 (aí dá para usar a pasta `_ncnn_model` com a biblioteca ultralytics, mais rápida).
- O sistema é **didático e auxiliar**: não substitui a supervisão do instrutor nem as obrigações da NR-6, e **não** deve ser usado para cortar a máquina de solda sem projeto e avaliação de segurança próprios.
- Uma câmera vê um ângulo só: mão escondida atrás do corpo ou máscara fora do quadro geram "não visto". O `MODO_ESTRITO` trata isso como falta, de propósito.

## Divisão sugerida para a turma

| Equipe | Responsável por |
|---|---|
| Dados | roteiro de cenários, coleta, autorizações |
| Anotação | regras de anotação, revisão cruzada |
| Treino | Colab, métricas, comparação entre versões |
| Hardware | Pi, relé, sinalizador, caixa de proteção da câmera |
| Software | `config.py`, regras, testes, painel com o `violacoes.csv` |
