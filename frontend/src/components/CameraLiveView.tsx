import { useState } from 'react';
import { useLiveCamera } from '../hooks/useLiveCamera';
import { acknowledge, ApiError, configureSimulation } from '../services/api';
import type { Access, Mode } from '../types';

const states: Record<string, string> = {
  AGUARDANDO_TOCHA: 'Aguardando retirada da tocha',
  VERIFICANDO_EPIS: 'Verificando EPIs',
  AGUARDANDO_MASCARA_ABAIXADA: 'Aguardando máscara abaixada',
  CONFORME_VISUAL: 'Verificação visual satisfatória',
  INCONCLUSIVO: 'Verificação inconclusiva',
  POSSIVEL_IRREGULARIDADE: 'Possível irregularidade',
  CAMERA_INDISPONIVEL: 'Câmera indisponível',
  SENSOR_INDISPONIVEL: 'Sensor indisponível',
  FALHA_PROCESSAMENTO: 'Processamento indisponível',
};
const evidence = (value?: string) => value === 'PRESENTE' ? 'Presente · simulado' :
  value === 'AUSENCIA_OBSERVADA' ? 'Possível ausência · simulada' : 'Não confirmado';

export function CameraLiveView({ access, onExpired, onLogout }: {
  access: Access; onExpired: () => void; onLogout: () => void;
}) {
  const live = useLiveCamera(access, onExpired);
  const { data, connected, videoFresh, imageUrl, secondsLeft } = live;
  const [mode, setMode] = useState<Mode>('raised');
  const [simulationAgreed, setSimulationAgreed] = useState(false);
  const [busy, setBusy] = useState(false);
  const [message, setMessage] = useState('');
  const [filter, setFilter] = useState('all');
  const fresh = connected && videoFresh && !!data?.camera.connected;
  const green = fresh && data?.inference.available && data.status.green;
  const state = !connected ? 'Conexão interrompida' :
    !data?.camera.connected ? 'Câmera indisponível' :
    !videoFresh ? 'Aguardando vídeo atualizado' :
    states[data.status.state] ?? 'Aguardando verificação';
  const events = [...(data?.events ?? [])].reverse().filter(event =>
    filter === 'all' || (filter === 'alerts' && (
      event.state.includes('FALHA') || event.state.includes('INCONCLUSIVO') ||
      event.state.includes('IRREGULARIDADE') || event.kind.includes('ALARME') ||
      event.kind.includes('INDISPONIVEL'))));

  async function perform(action: () => Promise<unknown>) {
    setBusy(true); setMessage('');
    try { await action(); }
    catch (error) {
      if (error instanceof ApiError && error.status === 401) onExpired();
      else setMessage(error instanceof Error ? error.message : 'Falha na operação.');
    } finally { setBusy(false); }
  }

  return <div className="dashboard">
    <header className="topbar">
      <a className="brand" href="/" aria-label="TecnoSolda início"><span className="brand-icon">T<span>↗</span></span>
        <span>TECNO<span className="brand-light">SOLDA</span><small>LABORATÓRIO DE SOLDAGEM</small></span></a>
      <div className="topbar-right"><span className="network-tag"><i className={connected ? 'dot green' : 'dot'}/> REDE LOCAL</span>
        <div className="operator"><strong>{access.username}</strong><small>Sessão · {Math.floor(secondsLeft / 60)}:{String(secondsLeft % 60).padStart(2, '0')}</small></div>
        <button className="quiet-button" onClick={onLogout}>Sair</button></div>
    </header>

    <main className="workspace">
      <div className="page-heading"><div><p className="eyebrow">MONITORAMENTO / CABINE 01</p>
        <h1>Visão da cabine<span className="amber">.</span></h1>
        <p className="muted">Acompanhe a câmera e as etapas de verificação.</p></div>
        <span className="recording-note"><span className="outline-dot"/> Sem gravação de vídeo</span></div>

      <div className="notice" role="note"><span className="notice-symbol">!</span><div><strong>Câmera real. Inferência em demonstração.</strong>
        <p>As caixas, confianças, sensor e sinais são simulados. Não representam detecções reais nem validam os EPIs da pessoa na imagem.</p></div>
        <span className="label amber-label">SEM MODELO YOLO</span></div>

      <div className="monitor-grid">
        <section className="video-card panel" aria-labelledby="video-heading">
          <div className="panel-heading"><h2 id="video-heading"><span className="camera-icon">▣</span> Câmera frontal <span className="subtle">/ 01</span></h2>
            <span className={'label ' + (fresh ? 'live-label' : 'neutral-label')}>{fresh ? '● AO VIVO' : '○ SEM VÍDEO'}</span></div>
          <div className="video-stage" style={{ aspectRatio: data ? data.camera.width / data.camera.height : 16 / 9 }}>
            {imageUrl && fresh ? <img src={imageUrl} alt="Câmera real da cabine com sobreposições explicitamente simuladas" /> :
              <div className="video-placeholder"><span className="placeholder-icon">▣</span>
                <h3>{connected ? data?.camera.message || 'Conectando à câmera' : 'Conectando ao serviço local'}</h3>
                <p>{connected ? 'Verifique o cabo, a permissão e o índice da câmera no Raspberry Pi.' :
                  'O vídeo e a indicação verde ficam ocultos até a conexão ser restabelecida.'}</p></div>}
            <span className="video-corner">CABINE 01 · CÂMERA REAL</span>
          </div>
          <div className="metrics">
            <Metric label="CAPTURA" value={fresh ? data.metrics.fps.toFixed(1) : '—'} unit="FPS"/>
            <Metric label="CAPTURA + PROCESSAMENTO" value={fresh && data.metrics.pipeline_ms !== null ? data.metrics.pipeline_ms.toFixed(0) : '—'} unit="ms"/>
            <Metric label="CÂMERA" value={fresh ? 'Conectada' : 'Indisponível'} />
            <Metric label="ANÁLISE" value={!data?.sensor.removed ? 'Em espera' : data.inference.available ? 'Simulada' : 'Indisponível'} />
          </div>
          <div className="legend"><span><i className="dot green"/> Confirmado</span><span><i className="dot red"/> Possível irregularidade</span>
            <span><i className="dot amber-dot"/> Inconclusivo</span><small>Classificações de demonstração</small></div>
          {data?.sensor.removed && !data.inference.available && <p className="inline-warning" role="status">Processamento de IA indisponível. A câmera pode continuar transmitindo, mas os EPIs não estão sendo verificados.</p>}
        </section>

        <aside className="verification panel">
          <p className="eyebrow">VERIFICAÇÃO DA SESSÃO</p>
          <div className={'state-indicator ' + (green ? 'state-green' : 'state-pending')}>
            <span className="status-symbol">{green ? '✓' : '!'}</span>
            <div><strong>{state}</strong><small>{green ? 'Resultado exclusivamente simulado' : 'Acompanhe as etapas abaixo'}</small></div></div>
          <div className="sensor-row"><span>Sensor da tocha <small>SIMULADO</small></span><strong>{connected && data ? data.sensor.removed ? 'Retirada' : 'No suporte' : '—'}</strong></div>
          <ol className="steps"><li className={fresh && data?.status.initial_verified ? 'step-done' : ''}><span>01</span><div><strong>Apresentar EPIs</strong><small>Máscara levantada e respirador visível</small></div></li>
            <li className={green ? 'step-done' : ''}><span>02</span><div><strong>Abaixar a máscara</strong><small>Confirmar a posição em vários quadros</small></div></li></ol>
          <div className="epi-list">
            <Epi label="Avental de soldagem" value={fresh ? evidence(data?.status.apron) : 'Não confirmado'} />
            <Epi label="Luvas de soldagem" value={fresh ? 'E: ' + evidence(data?.status.left_glove) : 'Esquerda não confirmada'}
              detail={fresh ? 'D: ' + evidence(data?.status.right_glove) : 'Direita não confirmada'} />
            <Epi label="Respirador com válvula" value={fresh && data?.status.respirator_verified ? 'Verificado na sessão · simulado' : 'Não confirmado'} />
            <Epi label="Máscara de soldagem" value={fresh && data ? (data.status.helmet === 'ABAIXADA' ? 'Abaixada · simulada' :
              data.status.helmet === 'LEVANTADA' ? 'Levantada · simulada' : 'Posição inconclusiva') : 'Não confirmado'} />
          </div>
          <div className="physical-note"><span className="outline-dot"/> Sinalização física não conectada</div>
          <p className="small muted">Uma verificação visual não substitui a supervisão e a inspeção física dos EPIs.</p>
        </aside>
      </div>

      <div className="lower-grid">
        <section className="panel detections-panel"><div className="panel-heading"><h2>Detecções <span className="subtle">/ demonstração</span></h2>
          <span className="label neutral-label">{fresh ? data?.detections.length ?? 0 : 0} REGIÕES</span></div>
          <div className="detection-list">{fresh && data && data.detections.length > 0 ? data.detections.map(box =>
            <div className={'detection-row ' + box.assessment} key={box.label}><span><i className="dot"/>{box.label}<small>Posição ilustrativa · simulada</small></span>
              <strong>{box.confidence === null ? 'Inconclusivo / ausência' : Math.round(box.confidence * 100) + '% simulado'}</strong></div>) :
            <div className="empty-state"><strong>Nenhuma detecção real disponível</strong><p>O modelo YOLO treinado ainda não está instalado.</p></div>}</div>
          <details className="simulation-controls"><summary>Controles de demonstração</summary>
            <p>Os cenários não analisam a imagem. As regiões e confianças são ilustrativas.</p>
            <label className="checkbox-row"><input type="checkbox" checked={simulationAgreed} onChange={e => setSimulationAgreed(e.target.checked)}/>
              Entendo que os resultados são simulados.</label>
            <label className="field-label" htmlFor="scenario">Cenário de teste</label>
            <select id="scenario" value={mode} onChange={e => setMode(e.target.value as Mode)}>
              <option value="raised">EPIs presentes / máscara levantada</option><option value="lowered">Máscara abaixada</option>
              <option value="missing_glove">Possível ausência da luva direita</option><option value="hidden_glove">Luva direita oculta</option>
              <option value="occluded">Perda de visibilidade</option><option value="unavailable">Processamento indisponível</option>
              <option value="off">Desativar detecções simuladas</option></select>
            <div className="button-row"><button disabled={!simulationAgreed || !connected || busy}
              onClick={() => void perform(() => configureSimulation(access.csrf, true, mode))}>Retirar tocha / aplicar cenário</button>
              <button className="secondary-button" disabled={!connected || busy}
                onClick={() => void perform(() => configureSimulation(access.csrf, false, 'off'))}>Devolver tocha</button></div>
          </details>
        </section>

        <section className="panel history"><div className="panel-heading"><h2>Histórico de eventos</h2>
          <select aria-label="Filtrar eventos" value={filter} onChange={e => setFilter(e.target.value)}>
            <option value="all">Todos os eventos</option><option value="alerts">Alertas e falhas</option></select></div>
          <div className="event-list" aria-label="Eventos recentes">{events.length ? events.map(event =>
            <article className="event-row" key={event.sequence}><span className="event-mark"/>
              <div><strong>{event.kind.replaceAll('_', ' ')}</strong><p>{states[event.state] ?? event.state}</p>
                <small>{event.reason.replaceAll('_', ' ')}{event.epi ? ' · ' + event.epi : ''}</small>
                <small>{event.actor ? 'Operador: ' + event.actor : 'Origem: ' + event.origin} · {event.review === 'PENDENTE' ? 'Revisão pendente' : event.review}</small></div>
              <time dateTime={event.occurred_at} title={new Date(event.occurred_at).toLocaleString('pt-BR')}>
                {new Date(event.occurred_at).toLocaleTimeString('pt-BR')}</time></article>) :
            <div className="empty-state"><strong>Nenhum evento nesta visualização</strong><p>Os eventos chegam automaticamente pelo serviço local.</p></div>}</div>
          <div className="history-footer"><small>Últimos 100 eventos · somente em memória</small>
            <button className="quiet-button" disabled={!connected || busy}
              onClick={() => void perform(() => acknowledge(access.csrf))}>Reconhecer alarme simulado</button></div>
        </section>
      </div>
      {message && <p role="alert" className="action-message">{message}</p>}
      <footer className="footer"><span>TECNO SOLDA <span className="subtle">/</span> CABINE 01</span><span>Processamento local · Sem identificação de alunos</span></footer>
    </main>
  </div>;
}

function Metric({ label, value, unit }: { label: string; value: string; unit?: string }) {
  return <div className="metric"><small>{label}</small><strong>{value}<span>{unit}</span></strong></div>;
}
function Epi({ label, value, detail }: { label: string; value: string; detail?: string }) {
  return <div className="epi"><span className="epi-icon">◇</span><div><strong>{label}</strong><small>{value}</small>{detail && <small>{detail}</small>}</div></div>;
}
