(() => {
  const menuButton = document.getElementById('menu-toggle');
  const nav = document.getElementById('main-nav');
  if (menuButton && nav) {
    menuButton.addEventListener('click', () => {
      const open = nav.classList.toggle('open');
      menuButton.setAttribute('aria-expanded', String(open));
      menuButton.setAttribute('aria-label', open ? 'Fechar menu' : 'Abrir menu');
      menuButton.textContent = open ? '×' : '☰';
    });
    nav.querySelectorAll('a').forEach(link => link.addEventListener('click', () => {
      nav.classList.remove('open');
      menuButton.setAttribute('aria-expanded', 'false');
      menuButton.setAttribute('aria-label', 'Abrir menu');
      menuButton.textContent = '☰';
    }));
  }

  // Filtro acessível dos cards de EPI
  const filterButtons = document.querySelectorAll('.filter-btn');
  const epiCards = document.querySelectorAll('.info-card');
  filterButtons.forEach(button => button.addEventListener('click', () => {
    const filter = button.dataset.filter;
    filterButtons.forEach(item => {
      const active = item === button;
      item.classList.toggle('active', active);
      item.setAttribute('aria-pressed', String(active));
    });
    epiCards.forEach(card => {
      card.hidden = filter !== 'todos' && card.dataset.category !== filter;
    });
  }));

  // Checklist por etapa: os itens são lembretes, não autorização para executar o serviço.
  const stages = {
    antes: [
      'Confirmar autorização do serviço e avaliação dos riscos por pessoa competente.',
      'Verificar se a área está sinalizada e isolada, protegendo as pessoas próximas.',
      'Retirar ou proteger materiais combustíveis e verificar os controles contra incêndio.',
      'Inspecionar cabos, conectores, tochas, mangueiras, reguladores e acessórios.',
      'Confirmar ventilação/exaustão adequada e EPIs compatíveis com os riscos.',
      'Confirmar treinamento, instruções do fabricante e procedimentos locais.'
    ],
    durante: [
      'Manter proteção ocular e facial adequada e cobrir a pele exposta.',
      'Impedir que pessoas sem proteção fiquem expostas ao arco ou às projeções.',
      'Manter ventilação/exaustão funcionando e controlar a fonte dos contaminantes.',
      'Manter cabos e mangueiras organizados, longe do calor, danos e passagens.',
      'Não soldar recipientes que possam conter inflamáveis sem avaliação e procedimento formal.',
      'Interromper o trabalho e avisar o responsável diante de qualquer condição insegura.'
    ],
    depois: [
      'Desligar e guardar os equipamentos conforme as instruções e o procedimento local.',
      'Inspecionar a área e os arredores para identificar calor residual ou risco de incêndio.',
      'Identificar peças quentes e deixá-las em local seguro.',
      'Limpar, inspecionar e armazenar os EPIs adequadamente.',
      'Comunicar danos, desgaste, perda ou inadequação dos equipamentos.',
      'Registrar defeitos e não devolver equipamentos danificados ao uso antes da avaliação.'
    ]
  };
  const labels = {antes:'Antes da atividade',durante:'Durante a atividade',depois:'Depois da atividade'};
  const checkItems = document.getElementById('check-items');
  const progressLabel = document.getElementById('progress-label');
  const progressFill = document.getElementById('progress-fill');
  const stageStatus = document.getElementById('stage-status');
  const resetButton = document.getElementById('reset-checklist');
  const tabs = document.querySelectorAll('.check-tab');
  let currentStage = 'antes';
  const checked = {antes: new Set(), durante: new Set(), depois: new Set()};

  function updateProgress() {
    const total = stages[currentStage].length;
    const count = checked[currentStage].size;
    progressLabel.textContent = `${count} de ${total} concluídos`;
    progressFill.style.width = `${count / total * 100}%`;
    stageStatus.textContent = count === total ? 'Etapa conferida. Siga os procedimentos autorizados.' : 'Marque os itens conferidos.';
  }
  function renderStage(stage) {
    currentStage = stage;
    tabs.forEach(tab => {
      const active = tab.dataset.stage === stage;
      tab.classList.toggle('active', active);
      tab.setAttribute('aria-selected', String(active));
    });
    checkItems.replaceChildren();
    stages[stage].forEach((item, index) => {
      const label = document.createElement('label');
      label.className = 'check-item';
      const input = document.createElement('input');
      input.type = 'checkbox';
      input.checked = checked[stage].has(index);
      input.addEventListener('change', () => {
        if (input.checked) checked[stage].add(index);
        else checked[stage].delete(index);
        updateProgress();
      });
      const span = document.createElement('span');
      span.textContent = item;
      label.append(input, span);
      checkItems.append(label);
    });
    updateProgress();
  }
  tabs.forEach(tab => tab.addEventListener('click', () => renderStage(tab.dataset.stage)));
  resetButton?.addEventListener('click', () => {
    checked[currentStage].clear();
    renderStage(currentStage);
  });
  renderStage(currentStage);
  // Interação de solda no hero: 3 cliques soldam barras; o 4º chama o martelo.
  const art = document.querySelector('.hero-art');
  if (art) {
    const bars = [...art.querySelectorAll('.bar')];
    const torch = art.querySelector('.torch');
    const hammer = art.querySelector('.hammer');
    const hammerBody = art.querySelector('.hammer-body');
    const impact = art.querySelector('.impact');
    const hintText = document.getElementById('weld-hint-text');
    const hintCount = document.getElementById('weld-count');
    const reduced = window.matchMedia('(prefers-reduced-motion: reduce)').matches;
    const SKEW = 'skewX(-17deg)';
    const BASE = 170, STEP = 25; // mesmos valores do CSS (.bar)
    const hints = ['Clique para soldar a 1ª barra', 'Clique para soldar a 2ª barra', 'Clique para soldar a 3ª barra', 'Clique para dar a martelada'];
    let welded = 0, busy = false;

    // Atalho para o Web Animations API: devolve uma Promise que resolve ao terminar.
    const run = (el, frames, o) => el.animate(frames, {
      fill: 'forwards', easing: 'linear', ...o,
      duration: reduced ? 1 : o.duration, delay: reduced ? 0 : (o.delay || 0)
    }).finished;
    const cancelAll = el => el.getAnimations({subtree: true}).forEach(a => a.cancel());
    const setHint = () => { hintCount.textContent = `${welded}/3`; hintText.textContent = hints[welded]; };

    async function weldBar(i) {
      const bar = bars[i], seam = bar.querySelector('.seam');
      cancelAll(torch);
      bar.style.visibility = 'visible';
      await run(bar, [{transform: 'translateY(-90px)', opacity: 0}, {transform: 'translateY(0)', opacity: 1}], {duration: 380, easing: 'cubic-bezier(.3,.8,.4,1)'});
      torch.style.bottom = `${BASE + i * STEP - 1}px`;
      await run(torch, [{opacity: 0}, {opacity: 1}], {duration: 150});
      const travel = {duration: 1600};
      await Promise.all([
        run(torch, [{left: '18%'}, {left: '82%'}], travel),
        run(seam, [{transform: `${SKEW} scaleX(0)`}, {transform: `${SKEW} scaleX(1)`}], travel)
      ]);
      await run(torch, [{opacity: 1}, {opacity: 0}], {duration: 200});
      seam.classList.add('cooled'); // o cordão esfria aos poucos
      welded++;
    }

    function impactEffects() {
      run(impact, [{opacity: 1, transform: 'translate(-50%,50%) scale(.3)'}, {opacity: 0, transform: 'translate(-50%,50%) scale(1.4)'}], {duration: 380, easing: 'ease-out'});
      if (reduced) return;
      art.animate([
        {transform: 'translate(0,0)'}, {transform: 'translate(-7px,4px)'}, {transform: 'translate(6px,-4px)'},
        {transform: 'translate(-3px,2px)'}, {transform: 'translate(0,0)'}
      ], {duration: 380});
      for (let n = 0; n < 18; n++) {
        const chip = document.createElement('i');
        chip.className = 'chip' + (Math.random() < .45 ? ' hot' : '');
        art.append(chip);
        const dx = (Math.random() - .5) * 320, peak = -(50 + Math.random() * 120), r = (Math.random() - .5) * 720;
        chip.animate([
          {transform: 'translate(0,0) rotate(0deg)', opacity: 1, easing: 'ease-out'},
          {transform: `translate(${dx * .6}px,${peak}px) rotate(${r / 2}deg)`, opacity: 1, offset: .4, easing: 'cubic-bezier(.5,0,1,.6)'},
          {transform: `translate(${dx}px,${peak + 280}px) rotate(${r}deg)`, opacity: 0}
        ], {duration: 700 + Math.random() * 400}).finished.then(() => chip.remove());
      }
    }

    function resetScene() {
      bars.forEach(bar => {
        const seam = bar.querySelector('.seam');
        cancelAll(bar);
        bar.classList.remove('broken');
        seam.style.transition = 'none';
        seam.classList.remove('cooled');
        void seam.offsetWidth;
        seam.style.transition = '';
        bar.style.visibility = 'hidden';
      });
      cancelAll(hammer);
      hammer.style.visibility = 'hidden';
      welded = 0;
    }

    async function smash() {
      hammer.style.visibility = 'visible';
      await run(hammerBody, [
        {transform: 'translate(110px,-120px) rotate(40deg)', easing: 'ease-out'},
        {transform: 'translate(150px,-170px) rotate(62deg)', offset: .4, easing: 'cubic-bezier(.7,0,1,.6)'},
        {transform: 'translate(0,0) rotate(0deg)'}
      ], {duration: 620});
      impactEffects();
      bars.forEach(b => b.classList.add('broken'));
      const falls = bars.flatMap((bar, i) => ['l', 'r'].map(side => {
        const d = side === 'l' ? -1 : 1;
        return run(bar.querySelector('.half-' + side), [
          {transform: `translate(0,0) rotate(0deg) ${SKEW}`, easing: 'ease-out'},
          {transform: `translate(${d * 10}px,-16px) rotate(${d * 5}deg) ${SKEW}`, offset: .12, easing: 'cubic-bezier(.5,0,1,.7)'},
          {transform: `translate(${d * (40 + i * 18)}px,520px) rotate(${d * (30 + i * 12)}deg) ${SKEW}`}
        ], {duration: 900 + i * 70, delay: (2 - i) * 70}); // a barra de cima cai primeiro
      }));
      const retract = (async () => {
        await new Promise(r => setTimeout(r, reduced ? 0 : 160));
        await run(hammerBody, [{transform: 'translate(0,0) rotate(0deg)', opacity: 1}, {transform: 'translate(70px,-100px) rotate(30deg)', opacity: 0}], {duration: 350});
      })();
      await Promise.all([retract, ...falls]);
      resetScene();
    }

    async function activate() {
      if (busy) return;
      busy = true;
      art.classList.add('is-playing', 'is-busy');
      try {
        if (welded < 3) { hintText.textContent = 'Soldando…'; await weldBar(welded); }
        else { hintText.textContent = 'Martelando…'; await smash(); art.classList.remove('is-playing'); }
      } finally {
        busy = false;
        art.classList.remove('is-busy');
        setHint();
      }
    }
    art.addEventListener('click', activate);
    art.addEventListener('keydown', e => {
      if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); activate(); }
    });
  }
})();