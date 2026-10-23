# TecnoSolda — monitoramento local da cabine

**Preparação da IA:** [cadastro, datasets, treinamento e registro dos modelos](docs/treinamento/guia-pratico.md).
Comece com `python ai-service/training.py catalog` e `python ai-service/training.py doctor`.
Os comandos usam o Python do sistema; nenhum modelo foi treinado ou ativado automaticamente.

O módulo de câmera ao vivo usa **React + FastAPI + OpenCV**, com transmissão MJPEG,
estados por WebSocket e acesso autenticado. O vídeo vem de câmera real; as caixas,
confianças, sensor e sinalização são explicitamente simulados nesta etapa.
Não há imagens fictícias para substituir uma câmera desconectada.

**Comece pelo [guia da câmera ao vivo](docs/arquitetura/camera-ao-vivo.md)**:
instalação, criação da senha, execução local, configuração HTTPS da LAN e testes.
O componente está em frontend/src/components/CameraLiveView.tsx.

Acesso local após configuração: http://127.0.0.1:8000. Não há usuário/senha padrão.
Nenhuma câmera foi encontrada no ambiente de desenvolvimento; captura física e
desempenho no Raspberry Pi ainda precisam de validação no dispositivo.

## Teste gráfico da máscara

Execute `python teste_mascara.py` para coletar fotos, treinar um classificador
experimental local e testar vermelho (levantada), verde (abaixada) ou inconclusivo.
O ensaio usa características visuais reais, é separado do YOLO e não aciona hardware.
Consulte o [passo a passo do teste gráfico](docs/testes/mascara-grafica.md).

## Protótipo da máquina de estados (CLI)

A primeira versão executável simula uma cabine, uma câmera frontal, o sensor da
tocha, as luzes e o alarme. Não utiliza IA treinada ou dispositivos reais.

```sh
python ai-service/run.py --scenario perda-visibilidade --events
python ai-service/run.py --interactive --role operador
python -m unittest discover -s ai-service/tests -p test_safety.py -v
```

Requer Python >= 3.11, sem dependências externas. A confirmação ocorre em duas
etapas: respirador e demais EPIs visíveis com máscara levantada, depois máscara
abaixada. Perda de visibilidade ou falha desliga o verde e exige nova verificação.

- [Plano técnico e modelo de dados](docs/arquitetura/plano-tecnico.md)
- [Máquina de estados](docs/arquitetura/maquina-de-estados.md)
- [Execução, cenários e testes](docs/testes/prototipo.md)
- [Limites e privacidade](docs/seguranca/limites-e-privacidade.md)

O verde indica somente uma verificação visual satisfatória. Não substitui
supervisão, inspeção física ou procedimentos da oficina.

O roteiro pedagógico original está preservado abaixo.

---

# EPI nas Cabines de Solda — Roteiro do Aluno

> Encontro 1 · 22/10/2026 · Prof. Vitor

## O desafio

Vocês vão construir um sistema que, quando o aluno de solda pega a tocha, confere por câmera se ele está com os EPIs e dispara um alarme se faltar algum. Hoje vocês não programam nem instalam nada: hoje vocês descobrem o problema na oficina, levantam os materiais e fazem a primeira versão da modelagem.

**Pergunta-guia:** como garantir que ninguém abra o arco sem os EPIs, sem vigiar nem expor os alunos?

**O que sai daqui hoje:**

- Respostas da entrevista, lista de EPIs por processo e medidas da cabine.
- Quadro de necessidades e as 3 ideias mais votadas.
- Lista de materiais preenchida, com o que temos e o que falta.
- Um artefato de modelagem v1 por equipe, salvo no repositório.

**Regras de segurança na oficina de solda:**

1. Ninguém olha para o arco sem proteção. Assistam à solda atrás da cortina ou com a proteção que o instrutor indicar.
2. Usem os EPIs que o instrutor exigir para circular na oficina.
3. Ninguém entra na cabine, encosta nas máquinas, nos cabos ou na tocha sem autorização.

**Regras de privacidade do projeto:**

1. Nada de fotografar ou filmar pessoas: fotos só da cabine vazia.
2. O sistema nunca vai identificar quem é o aluno, só se o EPI está lá.
3. Nenhuma imagem de pessoa vai para o repositório público.
4. Toda decisão vale só se estiver registrada (arquivo ou issue no repositório).

## Formem as equipes (10 min)

A turma se divide em cinco equipes de 4 a 6 pessoas; cada equipe é dona de uma parte do sistema, mas todas participam de todos os passos. Escrevam os nomes na tabela.

| Equipe | Do que cuida | Entrega de hoje | Integrantes |
| --- | --- | --- | --- |
| Campo e Usuário | Entrevista, observação, lista de EPIs e medidas da cabine | Respostas da entrevista e tabela de EPIs por processo |  |
| Hardware e Sensores | Câmera, computador, gatilho da tocha, sirene, luz e proteção contra respingo e calor | Lista de materiais preenchida |  |
| Visão Computacional | Modelo de detecção, conjunto de imagens e testes | Plano do conjunto de imagens |  |
| Software e Modelagem | Lógica de decisão, alarme, registro de eventos, diagramas e repositório | Diagrama de blocos v1 e máquina de estados da cabine |  |
| Segurança e Privacidade | Regras da oficina, posição dos equipamentos e regras de privacidade | Checklist de segurança e regras de privacidade v1 |  |

**Líder de projeto (troca a cada encontro):** \_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_

O líder cria agora o repositório `epi-solda-visao` no GitHub, adiciona todos como colaboradores e cria as pastas `docs/entrevista`, `docs/materiais` e `docs/modelagem`, com um arquivo `.gitkeep` em cada uma, porque o Git não guarda pasta vazia.

## Passo 1 — Imersão na oficina de solda (40 min)

Vocês vão até as cabines para ver como a solda acontece de verdade, antes de pensar em qualquer solução. Antes de entrar, a equipe de Segurança e Privacidade confirma com o instrutor onde a turma pode ficar e quais EPIs são obrigatórios.

**1.1 Observem uma solda (10 min).** Atrás da cortina, anotem em que momento o aluno veste cada EPI, onde a tocha fica antes e depois de soldar, e quando ele baixa a máscara.

**1.2 Entrevistem (15 min).** A equipe Campo conduz, as outras escutam e anotam. Preencham as respostas aqui mesmo.

| Pergunta | Instrutor de soldagem | Aluno de solda |
| --- | --- | --- |
| Quais EPIs são obrigatórios em cada processo usado aqui? |  |  |
| Quais EPIs os alunos mais esquecem ou tiram, e em que momento? |  |  |
| Como o instrutor confere os EPIs hoje? O que escapa? |  |  |
| Em quais processos existe tocha, e onde ela fica quando não está em uso? |  |  |
| Quantas cabines existem, quantas pessoas usam cada uma e como é a iluminação dentro dela? |  |  |
| Onde uma câmera ficaria sem receber respingo e sem apontar direto para o arco? |  |  |
| O alarme deve avisar só o aluno ou também o instrutor? Como ele seria percebido de máscara abaixada? |  |  |
| Tem tomada e rede perto das cabines? Pode fixar algo nelas? |  |  |

**1.3 EPIs por processo.** Com o instrutor, marquem com X o que é obrigatório em cada processo. Na última coluna, digam se dá para ver aquele EPI de longe, por uma câmera.

| EPI | Eletrodo revestido | MIG/MAG | TIG | Visível na câmera? |
| --- | --- | --- | --- | --- |
| Máscara de solda |  |  |  |  |
| Óculos de segurança |  |  |  |  |
| Luvas de raspa |  |  |  |  |
| Avental ou jaqueta de raspa |  |  |  |  |
| Mangote |  |  |  |  |
| Perneira |  |  |  |  |
| Botina de segurança |  |  |  |  |
| Protetor auricular |  |  |  |  |
| Outro: |  |  |  |  |

**1.4 Meçam e fotografem (10 min).** Usem trena e fotografem só a cabine vazia, de dentro para fora e de fora para dentro.

| Medida | Valor (cm) |
| --- | --- |
| Largura da cabine |  |
| Profundidade da cabine |  |
| Altura da cabine (ou da cortina) |  |
| Altura e posição do suporte da tocha |  |
| Distância até a tomada mais próxima |  |
| Distância até o ponto de rede mais próximo (se houver) |  |

As fotos vão para `docs/entrevista` no repositório, com nomes que digam o que mostram (`cabine-frente.jpg`, `suporte-tocha.jpg`).

## Passo 2 — Síntese e ideias (50 min)

De volta à sala, vocês transformam o que viram em necessidades e, só depois, em ideias. Depois deste passo, intervalo de 15 minutos.

**2.1 Quadro de necessidades (25 min).** Cada pessoa escreve post-its com o que viu e ouviu e cola na coluna certa. Depois, juntem os repetidos e passem para a tabela os mais importantes.

| O instrutor precisa garantir | Onde os EPIs falham hoje | Restrições da cabine |
| --- | --- | --- |
|  |  |  |
|  |  |  |
|  |  |  |
|  |  |  |
|  |  |  |

Fechem a síntese com uma frase: **"O aluno de solda precisa \_\_\_\_\_\_ porque \_\_\_\_\_\_."**

**2.2 Crazy 8s (25 min).**

1. Cada pessoa dobra uma folha A4 em 8 partes.
2. Em 8 minutos, desenha 8 ideias diferentes, uma por quadro, sem se preocupar com capricho.
3. Cada ideia precisa mostrar três coisas: onde fica a câmera, o que avisa o sistema de que a solda vai começar (o gatilho) e como o alarme avisa.
4. Cada um apresenta suas 2 melhores ideias em 1 minuto.
5. Votação: cada pessoa tem 3 votos (bolinhas) e pode colocar mais de um na mesma ideia.
6. Registrem as 3 mais votadas abaixo e fotografem as folhas para `docs/entrevista`.

| Ideia | Onde fica a câmera | Gatilho | Como o alarme avisa | Votos |
| --- | --- | --- | --- | --- |
| 1 |  |  |  |  |
| 2 |  |  |  |  |
| 3 |  |  |  |  |

## Passo 3 — Levantamento de materiais (45 min)

A equipe de Hardware e Sensores conduz, mas cada equipe confere os itens da sua parte com o professor e o almoxarifado. Na coluna "Temos?", escrevam **Sim**, **Não** ou **Verificar** em cada linha; o que ficar como "Não" vira lista de compras.

| Item | Para quê | Temos? | Onde está ou preço + link |
| --- | --- | --- | --- |
| Notebook ou PC da escola + webcam USB | Protótipo na bancada |  |  |
| Câmera USB 1080p ou Raspberry Pi Camera Module 3 | Ver a cabine |  |  |
| Raspberry Pi 5 (4 GB ou mais) | Rodar o sistema na cabine |  |  |
| Acelerador de IA para o Pi (AI HAT+) | Deixar a detecção mais rápida |  |  |
| Cartão microSD 64 GB e fonte oficial do Pi 5 | Sistema e energia |  |  |
| Chave fim de curso ou sensor magnético (reed switch + ímã) | Perceber que a tocha saiu do suporte |  |  |
| Módulo relé | Acionar sirene e luz |  |  |
| Sirene 12 V e sinaleiro luminoso verde/vermelho | Alarme |  |  |
| Fonte 12 V | Alimentar sirene e sinaleiro |  |  |
| Caixa metálica com janela de policarbonato | Proteger a câmera de respingo e calor |  |  |
| Cabos USB blindados e ferrites | Reduzir a interferência elétrica da solda |  |  |
| Canaleta metálica e abraçadeiras | Organizar os cabos |  |  |
| EPIs de solda emprestados (máscara, luvas, avental, mangote) | Fotografar exemplos para o modelo |  |  |
| Placa de aviso na cabine | Avisar que há detecção de EPI, sem gravação |  |  |

**Itens que a ideia escolhida de vocês precisa a mais:**

| Item | Para quê | Temos? | Onde está ou preço + link |
| --- | --- | --- | --- |
|  |  |  |  |
|  |  |  |  |
|  |  |  |  |

**Dicas para decidir:**

- Comecem pelo que a escola já tem: o protótipo inteiro pode rodar num notebook com webcam.
- O Raspberry Pi só entra na versão instalada na cabine, e o acelerador de IA só se os testes mostrarem que falta velocidade.
- Perto de fagulhas, plástico comum é risco: caixas e canaletas metálicas.
- Para cotar, usem revendedores autorizados no Brasil, como RoboCore, FilipeFlop, Eletrogate e UsinaInfo, e colem o link na tabela.

## Passo 4 — Modelagem v1 (60 min)

Cada equipe transforma a ideia mais votada em um artefato de modelagem, usando só o que foi visto, medido e respondido na oficina. O que ficar em dúvida não é inventado: vira uma pergunta escrita no próprio artefato.

| Equipe | O que produzir | O artefato precisa responder | Ferramenta |
| --- | --- | --- | --- |
| Campo e Usuário | Lista de EPIs-alvo e regra de decisão | Quais 3 ou 4 EPIs o sistema confere primeiro, e o que conta como "está usando"? | README no GitHub |
| Hardware e Sensores | Esboço da cabine com o campo de visão da câmera | Onde ficam câmera, gatilho e alarme, e o que a câmera enxerga dali? | Papel quadriculado, Tinkercad ou SketchUp |
| Visão Computacional | Plano do conjunto de imagens | Quais classes, quantas imagens de cada, em que condições e com quem? | Tabela abaixo |
| Software e Modelagem | Diagrama de blocos, máquina de estados da cabine e casos de uso | Quais partes existem, em que estados a cabine pode estar e quem faz o quê? | draw.io ou PlantUML |
| Segurança e Privacidade | Checklist de segurança e regras de privacidade v1 | O sistema pode ser instalado sem risco e sem expor ninguém? | Este documento |

**Perguntas que todas as equipes precisam enfrentar:**

1. Como a câmera vai enxergar se o arco da solda ofusca qualquer imagem?
2. Como proteger a câmera de respingos, fumaça e calor?
3. O que acontece se o aluno estiver de costas ou com as mãos fora da imagem?
4. O aluno costuma posicionar a peça com a máscara levantada e só baixar na hora de abrir o arco. Como o sistema lida com isso?
5. O que é pior: o alarme tocar sem motivo ou o sistema deixar passar a falta de um EPI? Como medir cada erro?

**Plano do conjunto de imagens** (equipe Visão Computacional):

| Classe | Quantas imagens | Condições (luz, ângulo, distância) | Quem ou o que aparece |
| --- | --- | --- | --- |
|  |  |  |  |
|  |  |  |  |
|  |  |  |  |
|  |  |  |  |

**Regras de privacidade v1** (equipe Segurança e Privacidade). Respondam no README:

- O que a câmera captura, e o que é guardado?
- Quem pode ver o registro de alarmes, e por quanto tempo ele fica guardado?
- Como os alunos de solda vão ser avisados de que há câmera na cabine?
- Como as imagens para treinar o modelo vão ser coletadas sem expor ninguém?

**Lista de requisitos** (equipe Software e Modelagem, com sugestões de todas). Usem este formato no README:

- RF01 — O sistema deve \_\_\_\_\_\_. (requisito funcional: o que o sistema faz)
- RNF01 — O sistema deve \_\_\_\_\_\_. (requisito não funcional: em que condições ou com que qualidade)

**Checklist da equipe de Segurança** (marquem só o que o instrutor confirmou):

- [ ] O local escolhido para a câmera fica fora da linha de respingos e do calor.
- [ ] Nada do sistema será ligado à máquina de solda; o gatilho é só um sensor no suporte da tocha.
- [ ] Caixas e fixações podem ser de material não inflamável.
- [ ] Os cabos podem passar longe do cabo-terra, do cabo da tocha e do chão de passagem.
- [ ] Extintor, cortinas e saídas continuam livres.
- [ ] O alarme pode ser percebido de máscara abaixada e com protetor auricular.

Todo artefato leva no canto o nome da equipe e a marca **v1**.

## Passo 5 — Apresentação e registro (15 min)

Cada equipe mostra o que produziu em 2 minutos, e tudo vai para o repositório antes de sair da sala.

1. Cada equipe apresenta seu artefato v1: o que decidiu e qual dúvida ficou.
2. A turma faz no máximo uma pergunta por equipe.
3. Cada dúvida aberta vira uma issue no GitHub, com o nome da equipe no título.
4. Fotografem ou exportem os artefatos e façam commit em `docs/modelagem`, com mensagem clara (ex.: `modelagem: maquina de estados v1`).
5. Antes do commit, confiram que nenhuma foto mostra pessoas.
6. O líder de projeto confere se cada equipe fez pelo menos um commit.

## Checklist de saída

O encontro só termina quando todos os itens abaixo estiverem marcados.

- [ ] Equipes e líder de projeto definidos.
- [ ] Repositório `epi-solda-visao` criado, com todos como colaboradores.
- [ ] Tabela da entrevista preenchida pelas duas pessoas entrevistadas.
- [ ] Tabela de EPIs por processo preenchida com o instrutor.
- [ ] Medidas anotadas e fotos da cabine vazia no repositório.
- [ ] Quadro de necessidades e frase de síntese prontos.
- [ ] 3 ideias mais votadas registradas.
- [ ] Lista de materiais com "Temos?" marcado em todas as linhas.
- [ ] Um artefato v1 por equipe no repositório.
- [ ] Regras de privacidade v1 e checklist de segurança revisados com o instrutor.
- [ ] Nenhuma imagem de pessoa no repositório.
- [ ] Dúvidas abertas registradas como issues.
