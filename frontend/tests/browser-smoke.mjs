import { chromium, expect } from '@playwright/test';
import { spawn } from 'node:child_process';
import { fileURLToPath } from 'node:url';
import path from 'node:path';
import { mkdir } from 'node:fs/promises';

const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '../..');
const python = process.env.LIVE_TEST_PYTHON || path.join(root, '.venv', process.platform === 'win32' ? 'Scripts/python.exe' : 'bin/python');
const server = spawn(python, [path.join(root, 'ai-service/tests/browser_server.py')], {
  cwd: root, windowsHide: true, env: { ...process.env, PYTHONDONTWRITEBYTECODE: '1' }, stdio: ['ignore', 'pipe', 'pipe'],
});
let serverErrors = '';
server.stderr.on('data', chunk => { serverErrors += chunk; });
let browser;
try {
  let ready = false;
  for (let attempt = 0; attempt < 40; attempt++) {
    try { const response = await fetch('http://127.0.0.1:8765/'); ready = response.ok; } catch {}
    if (ready) break;
    await new Promise(resolve => setTimeout(resolve, 250));
  }
  if (!ready) throw new Error('Servidor de teste não iniciou: ' + serverErrors);
  browser = await chromium.launch({ channel: process.env.LIVE_BROWSER_CHANNEL || 'msedge', headless: true });
  const page = await browser.newPage({ viewport: { width: 1440, height: 1000 } });
  const errors = [];
  page.on('pageerror', error => errors.push(error.message));
  await page.goto('http://127.0.0.1:8765/');
  await expect(page.getByRole('heading', { name: /Acompanhe a cabine/ })).toBeVisible();
  const direct = await page.request.get('http://127.0.0.1:8765/api/live/video.mjpg');
  expect(direct.status()).toBe(401);
  await page.getByLabel('Usuário', { exact: true }).fill('browser-test');
  await page.getByLabel('Senha', { exact: true }).fill('only-for-local-browser-tests');
  await page.getByRole('button', { name: /Acessar monitoramento/ }).click();
  await expect(page.getByRole('heading', { name: /Visão da cabine/ })).toBeVisible();
  await expect(page.getByText('Câmera real. Inferência em demonstração.')).toBeVisible();
  await expect(page.getByText('Câmera indisponível', { exact: true })).toBeVisible();
  await expect(page.locator('.video-stage img')).toHaveCount(0);
  await page.getByText('Controles de demonstração', { exact: true }).click();
  await page.getByLabel('Entendo que os resultados são simulados.').check();
  await page.getByRole('button', { name: 'Retirar tocha / aplicar cenário' }).click();
  await expect(page.getByText('Retirada', { exact: true })).toBeVisible();
  await expect(page.getByText('Resultado exclusivamente simulado')).toHaveCount(0);
  await mkdir(path.join(root, 'test-artifacts'), { recursive: true });
  await page.screenshot({ path: path.join(root, 'test-artifacts/dashboard-desktop.png'), fullPage: true });
  await page.setViewportSize({ width: 390, height: 844 });
  await expect(page.getByRole('heading', { name: /Visão da cabine/ })).toBeVisible();
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true);
  await page.screenshot({ path: path.join(root, 'test-artifacts/dashboard-mobile.png'), fullPage: true });
  await expect(page.getByRole('heading', { name: /Acompanhe a cabine/ })).toBeVisible({ timeout: 18000 });
  await expect(page.getByText(/Sessão encerrada/)).toBeVisible();
  expect(errors).toEqual([]);
  console.log('Browser OK: login, acesso protegido, câmera ausente, controles, mobile e expiração.');
} finally {
  await browser?.close();
  server.kill();
}
