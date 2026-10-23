import { render, screen } from '@testing-library/react';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { CameraLiveView } from './CameraLiveView';
import { useLiveCamera } from '../hooks/useLiveCamera';
import type { LiveState } from '../types';

vi.mock('../hooks/useLiveCamera');
const mock = vi.mocked(useLiveCamera);
const access = { username: 'instrutor-teste', role: 'operador', csrf: 'csrf-teste', expires_in: 900 };
const data: LiveState = {
  sequence: 10, camera: { connected: true, source: 'real', message: '', width: 960, height: 540 },
  inference: { mode: 'lowered', simulated: true, available: true, analyzing: true, message: '' },
  sensor: { simulated: true, removed: true }, metrics: { fps: 12, pipeline_ms: 8, frame_age_ms: 50 },
  status: { state: 'CONFORME_VISUAL', reason: '', green: true, red: false, respirator_verified: true,
    initial_verified: true, helmet: 'ABAIXADA', apron: 'PRESENTE', left_glove: 'PRESENTE', right_glove: 'PRESENTE' },
  simulated_outputs: { green: true, red: false, alarm: false }, physical_outputs_connected: false,
  detections: [], events: [], access_expires_in: 900,
};
beforeEach(() => mock.mockReturnValue({ data, connected: true, videoFresh: true, imageUrl: 'blob:test', secondsLeft: 900 }));
function view() { return render(<CameraLiveView access={access} onExpired={vi.fn()} onLogout={vi.fn()}/>); }
describe('CameraLiveView', () => {
  it('identifica simulação e não afirma acionar luz física', () => {
    view();
    expect(screen.getByText('Câmera real. Inferência em demonstração.')).toBeInTheDocument();
    expect(screen.getByText('Resultado exclusivamente simulado')).toBeInTheDocument();
    expect(screen.getByText('Sinalização física não conectada')).toBeInTheDocument();
  });
  it('remove conformidade e imagem ao perder WebSocket', () => {
    mock.mockReturnValue({ data, connected: false, videoFresh: false, imageUrl: undefined, secondsLeft: 800 });
    view();
    expect(screen.queryByText('Verificação visual satisfatória')).not.toBeInTheDocument();
    expect(screen.queryByRole('img')).not.toBeInTheDocument();
  });
  it('remove verde quando vídeo para mesmo com WebSocket ativo', () => {
    mock.mockReturnValue({ data, connected: true, videoFresh: false, imageUrl: undefined, secondsLeft: 800 });
    view();
    expect(screen.getByText('Aguardando vídeo atualizado')).toBeInTheDocument();
    expect(screen.queryByText('Resultado exclusivamente simulado')).not.toBeInTheDocument();
  });
  it('mostra falha de IA e mantém mensagem de indisponibilidade', () => {
    mock.mockReturnValue({ data: { ...data, inference: { ...data.inference, available: false },
      status: { ...data.status, state: 'FALHA_PROCESSAMENTO', green: false } },
      connected: true, videoFresh: true, imageUrl: 'blob:test', secondsLeft: 800 });
    view();
    expect(screen.getByText(/Processamento de IA indisponível/)).toBeInTheDocument();
    expect(screen.queryByText('Resultado exclusivamente simulado')).not.toBeInTheDocument();
  });
  it('controles de simulação exigem reconhecimento explícito', () => {
    view();
    expect(screen.getByRole('button', { name: 'Retirar tocha / aplicar cenário', hidden: true })).toBeDisabled();
  });
});
