import type { Access, Mode } from '../types';

export class ApiError extends Error {
  constructor(message: string, public status: number) { super(message); }
}

export async function api<T>(path: string, options: RequestInit = {}): Promise<T> {
  const response = await fetch('/api' + path, { ...options, credentials: 'same-origin',
    headers: { 'Content-Type': 'application/json', ...options.headers }, cache: 'no-store' });
  if (!response.ok) {
    const body = await response.json().catch(() => ({}));
    throw new ApiError(typeof body.detail === 'string' ? body.detail : 'Não foi possível concluir a operação.', response.status);
  }
  return response.json() as Promise<T>;
}
export const getAccess = () => api<Access>('/auth/session');
export const login = (username: string, password: string) =>
  api<Access>('/auth/login', { method: 'POST', body: JSON.stringify({ username, password }) });
export const logout = (csrf: string) =>
  api('/auth/logout', { method: 'POST', headers: { 'X-CSRF-Token': csrf } });
export const configureSimulation = (csrf: string, removed: boolean, mode: Mode) =>
  api('/simulation', { method: 'POST', headers: { 'X-CSRF-Token': csrf }, body: JSON.stringify({ removed, mode }) });
export const acknowledge = (csrf: string) =>
  api('/alerts/acknowledge', { method: 'POST', headers: { 'X-CSRF-Token': csrf } });
