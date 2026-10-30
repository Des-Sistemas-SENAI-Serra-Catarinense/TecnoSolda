# Welding API — Guia de Segurança em Soldagem

Site informativo e interativo sobre segurança em soldagem: EPIs, equipamentos, locais de trabalho, riscos, checklist de procedimento, proteção coletiva, responsabilidades e normas de referência.

O conteúdo é baseado no documento *Guia de Segurança em Soldagem*. É material informativo e **não substitui** treinamento, análise de risco, procedimentos locais nem a orientação de um profissional competente.

## Como abrir

**Opção 1 — arquivo único (mais simples)**
Abra o `index.html` no navegador. Ele já tem o CSS e o JavaScript embutidos, então não depende de nenhum outro arquivo.

**Opção 2 — arquivos separados (para editar)**
1. Mantenha `index-modular.html`, `style.css` e `script.js` na mesma pasta.
2. Abra o `index-modular.html` no navegador (ou a pasta no Visual Studio Code).
3. Edite o CSS e o JS normalmente. Os links já têm `?v=3` para o navegador não reaproveitar uma versão antiga; se mexer e não ver a mudança, aumente esse número ou recarregue com `Ctrl + F5`.

> As fontes (Barlow e Barlow Condensed) vêm do Google Fonts e precisam de internet. Sem conexão, o site usa as fontes padrão do sistema.

## Arquivos

| Arquivo | Para que serve |
|---|---|
| `index.html` | Site completo em um só arquivo (HTML + CSS + JS embutidos). |
| `index-modular.html` | Mesmo site, mas ligado a `style.css` e `script.js`. |
| `style.css` | Estilos, layout responsivo e animações. |
| `script.js` | Menu móvel, filtro de EPIs, checklist interativo e animação de solda. |
| `LEIA-ME.txt` | Resumo curto do projeto. |

> Se você editar o `style.css` ou o `script.js`, as mudanças só aparecem no `index-modular.html`. O `index.html` tem uma cópia embutida e precisa ser gerado de novo.

## Recursos

- **Menu responsivo**, com botão para celular.
- **Filtro de EPIs** por categoria, com botões acessíveis (`aria-pressed`).
- **Checklist por etapa** (antes, durante e depois da atividade), com contador de progresso e botão de reiniciar. Os itens são lembretes e não autorizam a execução do serviço.
- **Animação de solda no topo da página** (veja abaixo).
- Layout adaptado para desktop, tablet e celular.
- Respeita a preferência de sistema "reduzir movimento".

## Animação de solda (clique na ilustração do topo)

A placa quente do topo da página é interativa. Clique nela (ou use `Tab` e `Enter`/`Espaço`):

| Clique | O que acontece |
|---|---|
| 1º | Uma barra cai sobre a placa e a tocha passa soldando, com faíscas e cordão de solda que esfria. |
| 2º | A segunda barra é soldada em cima da primeira. |
| 3º | A terceira barra é soldada, formando a pilha de 3. |
| 4º | O martelo desce, a tela treme, a pilha racha e as barras caem. |

Depois disso a cena volta ao início e dá para repetir. Cliques durante uma animação são ignorados.

### Ajustes rápidos

- **Altura e posição das barras:** no CSS, a classe `.bar` usa `bottom: calc(170px + var(--i) * 25px)` e `height: 22px`. No `script.js`, as constantes `BASE` (170) e `STEP` (25) precisam ter os mesmos valores, porque a tocha usa esses números para achar a altura da solda.
- **Velocidade da solda:** em `weldBar()`, altere `travel = {duration: 1600}` (em milissegundos).
- **Quantidade de estilhaços:** em `impactEffects()`, altere o limite do laço `for (let n = 0; n < 18; n++)`.
- **Cores:** as cores principais estão nas variáveis no início do `style.css` (`--accent`, `--accent-light`, `--bg` etc.).

## Acessibilidade

- Link "Pular para o conteúdo" no início da página.
- Menu, filtros e abas do checklist com atributos `aria-*`.
- A ilustração interativa tem `role="button"`, é acessível por teclado e anuncia o progresso ("0/3", "Clique para soldar a 2ª barra") para leitores de tela.
- Com "reduzir movimento" ativado no sistema, as animações longas são encurtadas e o tremor e os estilhaços do martelo são desativados.

## Compatibilidade

Funciona nos navegadores atuais (Chrome, Edge, Firefox e Safari). A animação usa a *Web Animations API*, então navegadores muito antigos não vão exibi-la.

## Aviso de responsabilidade

Este conteúdo é informativo. A seleção final de EPIs, filtros, controles de incêndio e requisitos para trabalho a quente deve ser feita por profissionais competentes, considerando o processo, o material, o local e os riscos reais. Consulte sempre as normas vigentes (como a NR-34, quando aplicável) e os procedimentos da empresa.
