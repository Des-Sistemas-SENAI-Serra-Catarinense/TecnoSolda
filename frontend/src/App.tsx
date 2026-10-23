import { useCallback, useEffect, useState, type FormEvent } from 'react';
import { CameraLiveView } from './components/CameraLiveView';
import { getAccess, login, logout } from './services/api';
import type { Access } from './types';

export default function App() {
  const [access, setAccess] = useState<Access | null>(null);
  const [loading, setLoading] = useState(true);
  const [message, setMessage] = useState('');
  const [username, setUsername] = useState('');
  const [password, setPassword] = useState('');
  const [busy, setBusy] = useState(false);
  useEffect(() => { let active = true; getAccess().then(value => { if (active) setAccess(value); })
    .catch(() => {}).finally(() => { if (active) setLoading(false); }); return () => { active = false; }; }, []);
  const expired = useCallback(() => { setAccess(null); setMessage('Sessão encerrada. Entre novamente para visualizar a câmera.'); }, []);
  async function submit(event: FormEvent) {
    event.preventDefault(); setBusy(true); setMessage('');
    try { setAccess(await login(username, password)); setPassword(''); }
    catch (error) { setMessage(error instanceof Error ? error.message : 'Falha ao autenticar.'); }
    finally { setBusy(false); }
  }
  async function signOut() {
    if (!access) return;
    try { await logout(access.csrf); setAccess(null); }
    catch { setAccess(null); setMessage('Vídeo encerrado neste navegador. Não foi possível confirmar a revogação no servidor; a sessão expira automaticamente.'); }
  }
  if (loading) return <main className="login-shell"><p>Verificando acesso local…</p></main>;
  if (access) return <CameraLiveView access={access} onExpired={expired} onLogout={() => void signOut()}/>;
  return <main className="login-shell"><section className="login-card">
    <div className="brand"><span className="brand-icon">T<span>↗</span></span><span>TECNO<span className="brand-light">SOLDA</span></span></div>
    <p className="eyebrow">ACESSO RESTRITO / REDE LOCAL</p><h1>Acompanhe a cabine<span className="amber">.</span></h1>
    <p className="muted">Entre com a conta de operador autorizada pela instituição.</p>
    <form onSubmit={submit}><label htmlFor="username">Usuário</label><input id="username" autoComplete="username" required maxLength={80}
      value={username} onChange={e => setUsername(e.target.value)}/>
      <label htmlFor="password">Senha</label><input id="password" type="password" autoComplete="current-password" required maxLength={256}
        value={password} onChange={e => setPassword(e.target.value)}/>
      <button disabled={busy}>{busy ? 'Verificando…' : 'Acessar monitoramento →'}</button>
    </form>{message && <p className="action-message" role="alert">{message}</p>}
    <p className="small muted">Câmera real · Sem gravação por padrão<br/>Inferência de EPIs disponível somente em demonstração.</p>
  </section></main>;
}
