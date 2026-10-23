# Preparação e treinamento de EPIs

## Estado atual

O cadastro técnico contém quatro EPIs obrigatórios e dois modelos planejados:
epis_detector (YOLO11n, cinco classes) e mascara_posicao (YOLO11n-cls, três classes).
Não há pesos treinados, dataset real nem aprovação operacional. O dashboard continua
com inferência explicitamente simulada.

O treinamento de verdade exige dados autorizados/rotulados e as dependências
opcionais de treinamento. Os testes automatizados usam fixtures sintéticas em
diretórios temporários; esses arquivos não viram dataset do projeto.

## 1. Conferir o cadastro e o ambiente

No PowerShell, na raiz do repositório, sem ativar .venv:

```powershell
python ai-service/training.py catalog
python ai-service/training.py doctor
```

- ai-service/config/epis.json: cadastro dos quatro EPIs.
- ai-service/config/modelos.json: tarefa, classes e parâmetros iniciais dos modelos.
- Fabricante e modelo comercial ficam null até serem informados pelo responsável.
- Preencha apenas manufacturer/model dos EPIs com os dados reais. Não remova as
  quatro categorias nem altere a ordem das classes sem revisar código e datasets.
- Pessoa é uma classe auxiliar do detector; não é um quinto EPI.
- Luvas usam uma classe de detecção e duas verificações, uma para cada mão.

O comando doctor apenas verifica o ambiente; não instala bibliotecas nem baixa pesos.

## 2. Inicializar as pastas privadas

```powershell
python ai-service/training.py init
```

A estrutura padrão já foi criada nesta entrega. Executar init novamente não
sobrescreve os templates, anotações ou registros existentes:

```text
ai-service/datasets/local/
├── detection/
│   ├── data.yaml
│   ├── images/{train,val,test}/
│   └── labels/{train,val,test}/
├── helmet/
│   ├── train/{abaixada,inconclusiva,levantada}/
│   ├── val/{abaixada,inconclusiva,levantada}/
│   └── test/{abaixada,inconclusiva,levantada}/
├── provenance.csv
├── base_weights/
├── runs/
└── registry.json
```

Esse diretório é ignorado pelo Git. Não use git add -f nele. Faça backup privado
autorizado dos datasets e registros. O YAML gerado usa sintaxe JSON, válida em YAML.

Para usar outra pasta, passe --workspace em todos os comandos:

```powershell
python ai-service/training.py init --workspace C:\datasets\tecnosolda
```

Use um workspace por versão imutável do conjunto de dados. Se os dados mudarem,
prepare uma nova versão; a avaliação verifica se correspondem ao treinamento.

## Capturar fotos pela interface gráfica

Na raiz do projeto, execute com o Python do sistema:

```powershell
python tirar_foto.py
```

1. Feche o aplicativo Câmera e pare a transmissão do serviço se estiverem usando
   a mesma câmera.
2. Informe o índice da câmera (comece por 0; tente 1 para outra câmera USB).
3. Defina um código de sessão, como sessao_001, sem nomes de pessoas.
4. Clique em **Conectar câmera** e confira a imagem real na prévia.
5. Clique em **Tirar foto** para cada imagem desejada. Só esse botão salva fotos.
6. Use **Abrir pasta da sessão** para conferir os arquivos.
7. Clique em **Desconectar** ou feche a janela ao terminar.

As fotos originais são salvas em
`ai-service/datasets/local/coleta/<sessao>/`, fora do Git. A prévia é reduzida
para caber na janela; a foto salva mantém a resolução recebida da câmera, sem
caixas, rótulos ou espelhamento. O contador vale para a abertura atual do programa.
Não há gravação de vídeo, reconhecimento facial ou inferência nesta ferramenta.
Uma câmera desconectada ou sem quadros recentes desabilita a captura.
Fotos idênticas ou visualmente muito parecidas com outras na pasta de coleta,
inclusive de outra sessão, são recusadas antes da gravação. A interface pede uma
nova pose ou enquadramento e mostra qual foto parece repetida. O contador só muda
quando uma foto é salva. Nenhuma foto antiga é apagada. A comparação tolera pequenas
variações de luz, ruído e compressão, mas é heurística e ainda requer revisão humana.

A interface usa Tkinter e o OpenCV headless já previsto nas dependências; não
precisa substituir o OpenCV nem instalar Pillow. Se o Python não incluir Tkinter,
instale o suporte Tcl/Tk correspondente à sua distribuição Python. Execute no
equipamento conectado à câmera; câmeras CSI do Raspberry Pi podem exigir um
adaptador de captura específico.

Colete apenas com autorização, sem soldagem ativa. As imagens ainda precisam de
anotação, separação por sessão e referências em provenance.csv conforme os passos
abaixo. A pasta coleta não é utilizada diretamente pelo comando de treinamento.

## 3. Coletar, rotular e separar

Colete somente com autorização institucional. Não use nomes de alunos nos arquivos.
Mantenha os documentos de autorização em local restrito; o dataset guarda apenas
uma referência operacional.

Os EPIs e a câmera precisam representar as condições da oficina. Inclua exemplos
de todos os itens, máscara levantada/abaixada, mãos ocultas, cabine vazia,
objetos fora do corpo e variações de iluminação. A coleta de situações sem EPI
deve ser uma demonstração controlada, sem atividade de soldagem.

No anotador local, use exatamente:

| ID | Classe |
| --- | --- |
| 0 | pessoa |
| 1 | avental_soldagem |
| 2 | luva_soldagem |
| 3 | mascara_soldagem |
| 4 | respirador_valvula |

Anote cada objeto identificável; cada luva recebe uma caixa. Um objeto sobre
a bancada continua sendo objeto detectável, mas não deve ser considerado EPI
em uso pelo futuro associador. Um respirador totalmente oculto não recebe caixa
inventada.

Exporte imagens e labels YOLO para as pastas correspondentes. Para cada imagem
é obrigatório um .txt com o mesmo nome. Uma imagem revisada sem nenhum objeto
das classes deve ter um .txt vazio, para não confundir falta de anotação com negativo.

Cada linha não vazia tem classe, centro_x, centro_y, largura e altura, normalizados
em [0,1]. Caixas não podem ultrapassar a imagem. Não use polígonos nesse dataset.

Divida por gravação/sessão e, quando possível, por participante autorizado;
quadros da mesma gravação não podem ir para splits diferentes.
70/15/15 é uma distribuição inicial possível, não uma exigência do programa.
Todos os splits precisam conter exemplos das classes esperadas.

## 4. Registrar origem/autorização

Preencha ai-service/datasets/local/provenance.csv, uma linha por imagem,
com caminhos relativos ao workspace. Exemplo de formato (substitua por registros reais):

```csv
image,group_id,authorization_ref
detection/images/train/sessao_a_001.jpg,sessao_a,referencia_institucional_a
detection/images/val/sessao_b_001.jpg,sessao_b,referencia_institucional_b
detection/images/test/sessao_c_001.jpg,sessao_c,referencia_institucional_c
helmet/train/levantada/sessao_a_001.jpg,sessao_a,referencia_institucional_a
```

group_id identifica a sessão/gravação, não a identidade nominal de uma pessoa.
Recortes da mesma gravação devem conservar o mesmo group_id, inclusive entre
detector e classificador. Não crie grupos artificiais apenas para passar no validador.

A ferramenta verifica o preenchimento e a consistência das referências. Ela não
autentica documentos nem comprova que uma autorização institucional foi concedida.

## 5. Validar antes de instalar/treinar

```powershell
python ai-service/training.py validate --task detect
python ai-service/training.py validate --task classify
python ai-service/training.py train --task detect --dry-run
```

valid=false ou código de saída 2 significa que há pendências; o JSON lista os
problemas. No dataset ainda vazio isso é esperado.

O validador confere imagens legíveis, classes, caixas, correspondência imagem/label,
classes em todos os splits, origem, grupos compartilhados e imagens idênticas em
conjuntos diferentes. Um hash identifica o conteúdo do dataset e das anotações.

Isso não garante qualidade da anotação nem detecta todo quadro quase duplicado.
Revisão humana, diversidade, visibilidade e adequação dos EPIs continuam necessárias.
Um conjunto minúsculo pode passar nas verificações estruturais sem ser útil.

--dry-run imprime o plano e a validação, sem importar YOLO, baixar pesos ou treinar.

## 6. Instalar as dependências opcionais

Somente quando os dados estiverem preparados:

```powershell
python -m pip install --user -r ai-service/requirements-training.txt
python ai-service/training.py doctor
python -c "import torch; print(torch.__version__); print(torch.cuda.is_available())"
```

A instalação do dashboard não inclui PyTorch/Ultralytics. A compatibilidade da
GPU depende das versões e do driver; use o seletor oficial do PyTorch.
Se CUDA não estiver disponível, o modo auto utiliza CPU. O programa não instala
CUDA nem muda automaticamente a versão do Python.

A biblioteca pode baixar pesos iniciais genéricos para base_weights ao iniciar
um treinamento válido. As integrações conhecidas de sincronização/logs externos
são desabilitadas na configuração local do workspace. Não se utiliza serviço
de treinamento em nuvem nem dados de exemplo externos.

## 7. Treinar o detector

Primeiro teste o fluxo com uma época:

```powershell
python ai-service/training.py train --task detect --epochs 1 --batch 4 --device cpu
```

Uma época é um teste de execução, não um modelo pronto. Depois, inicie uma nova
execução com os parâmetros iniciais:

```powershell
python ai-service/training.py train --task detect --epochs 100 --batch 4 --device auto
```

O script usa imagens 640, seed 42, patience 20 e workers 0.
Cada execução recebe um ID único e salva plano, ambiente, versão dos dados,
pesos e gráficos em runs. As versões efetivamente instaladas são registradas.
Os parâmetros precisam ser ajustados a partir dos resultados reais.

Nenhum dataset inválido chega ao carregamento de YOLO. Falhas deixam run.json
com FALHOU; interrupções deixam INTERROMPIDO. Um best.pt válido e com as classes
esperadas é registrado como TREINADO_NAO_VALIDADO, com SHA-256.

## 8. Treinar a posição da máscara

Prepare recortes da região da cabeça e máscara, preservando contexto suficiente
para distinguir levantada e abaixada. Organize-os nas pastas helmet e registre
origem, autorização e grupo no mesmo provenance.csv.

```powershell
python ai-service/training.py validate --task classify
python ai-service/training.py train --task classify --epochs 50 --device auto
```

O classificador usa YOLO11n-cls, imagem 224 e batch 8 por padrão. As classes
são abaixada, inconclusiva e levantada. Não são reconhecidas automaticamente
pelo detector de cinco classes. A integração precisa validar a qualidade dos
recortes; não basta confiar na classe com maior pontuação.

## 9. Avaliar e consultar o registro

```powershell
python ai-service/training.py registry
```

Copie o id de uma execução concluída e use-o:

```powershell
python ai-service/training.py evaluate --model-id COLE_O_ID_AQUI --device cpu
```

A avaliação usa explicitamente split=test, confere o hash dos pesos e exige
a versão original dos dados. O registro passa a AVALIADO_AGUARDANDO_REVISAO,
com métricas gerais e por classe. Não há aprovação automática.

Use val para decisões de treinamento; preserve test para uma avaliação final.
Observe precision, recall, F1 quando disponível, mAP do detector e matriz de
confusão. No classificador avalie também confusões entre levantada/abaixada.
Não use uma média geral para encobrir falhas no respirador ou nas luvas.
Defina critérios de aceitação com o instrutor/responsável antes da liberação.

O histórico registry.json é local e privado; o comando não carrega pesos externos
arbitrários nem oferece ativação no dashboard.

## 10. Etapas ainda necessárias após treinamento

- Associar EPIs ao corpo da pessoa, não a objetos presentes na cabine.
- Associar cada luva à mão anatômica correspondente; o eixo X não resolve isso.
- Detectar/recortar a cabeça para o classificador da máscara.
- Rejeitar imagem ruim, oclusão e confiança insuficiente como inconclusivas.
- Integrar os resultados ao motor temporal e ao cache de respirador.
- Medir câmera, latência, FPS e temperatura no Raspberry Pi.
- Validar em ensaio supervisionado antes de conectar sinalização física.

Não há reconhecimento facial, inferência real ativada ou alteração de saídas
físicas nesta entrega.

## Testes e referências

```powershell
python -m unittest discover -s ai-service/tests -p test_training.py -v
```

Os testes cobrem os validadores e a orquestração com um modelo dublê, sem treinar
nem baixar um modelo real. Não são uma medição de acurácia de IA.

[Ultralytics: treinamento](https://docs.ultralytics.com/modes/train/),
[validação](https://docs.ultralytics.com/modes/val/),
[classificação](https://docs.ultralytics.com/datasets/classify/) e
[instalação do PyTorch](https://pytorch.org/get-started/locally/).


