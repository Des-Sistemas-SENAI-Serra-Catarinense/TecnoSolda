import { useEffect, useRef, useState } from 'react';
import { MjpegDecoder } from '../services/mjpeg';
import type { Access, LiveState } from '../types';

export function useLiveCamera(access: Access, onExpired: () => void) {
  const [data, setData] = useState<LiveState | null>(null);
  const [connected, setConnected] = useState(false);
  const [lastStateAt, setLastStateAt] = useState(0);
  const [image, setImage] = useState<{ url: string; at: number } | null>(null);
  const [now, setNow] = useState(Date.now());
  const [expiresAt, setExpiresAt] = useState(Date.now() + access.expires_in * 1000);
  const expiredCallback = useRef(onExpired);
  expiredCallback.current = onExpired;

  useEffect(() => {
    const timer = window.setInterval(() => setNow(Date.now()), 200);
    return () => clearInterval(timer);
  }, []);
  useEffect(() => {
    if (now >= expiresAt) expiredCallback.current();
  }, [now, expiresAt]);

  useEffect(() => {
    let stopped = false;
    let socket: WebSocket | undefined;
    let retry: number | undefined;
    function connect() {
      socket = new WebSocket(location.origin.replace(/^http/, 'ws') + '/api/live/ws');
      socket.onmessage = (event) => {
        try {
          const next = JSON.parse(event.data) as LiveState;
          if (!next.camera || !next.status || !Number.isFinite(next.access_expires_in)) throw new Error();
          setData(next); setConnected(true); setLastStateAt(Date.now());
          setExpiresAt(Date.now() + next.access_expires_in * 1000);
        } catch { setConnected(false); socket?.close(); }
      };
      socket.onerror = () => { setConnected(false); socket?.close(); };
      socket.onclose = (event) => {
        setConnected(false); setData(null);
        if (stopped) return;
        if (event.code === 4401 || event.code === 1008) expiredCallback.current();
        else retry = window.setTimeout(connect, 1500);
      };
    }
    connect();
    return () => { stopped = true; clearTimeout(retry); socket?.close(); };
  }, []);

  const stateFresh = connected && now - lastStateAt < 1500;
  const shouldStream = stateFresh && !!data?.camera.connected && now < expiresAt;
  useEffect(() => {
    if (!shouldStream) { setImage(null); return; }
    const controller = new AbortController();
    let retry: number | undefined;
    let currentUrl: string | undefined;
    async function stream() {
      try {
        const response = await fetch('/api/live/video.mjpg', {
          signal: controller.signal, credentials: 'same-origin', cache: 'no-store',
        });
        if (response.status === 401 || response.status === 403) { expiredCallback.current(); return; }
        if (!response.ok || !response.body) throw new Error('Transmissão indisponível.');
        const reader = response.body.getReader();
        const decoder = new MjpegDecoder();
        while (!controller.signal.aborted) {
          const part = await reader.read();
          if (part.done) break;
          const frames = decoder.feed(part.value);
          if (frames.length) {
            const frame = frames[frames.length - 1];
            const next = URL.createObjectURL(new Blob([new Uint8Array(frame).buffer], { type: 'image/jpeg' }));
            if (currentUrl) URL.revokeObjectURL(currentUrl);
            currentUrl = next;
            setImage({ url: next, at: Date.now() });
          }
        }
      } catch {
        // O próximo ciclo tenta novamente; nunca preservar verde de vídeo parado.
      } finally {
        if (!controller.signal.aborted) {
          setImage(null);
          retry = window.setTimeout(stream, 1500);
        }
      }
    }
    void stream();
    return () => {
      controller.abort(); clearTimeout(retry);
      if (currentUrl) URL.revokeObjectURL(currentUrl);
      setImage(null);
    };
  }, [shouldStream]);

  const videoFresh = shouldStream && !!image && now - image.at < 1500;
  return { data, connected: stateFresh, imageUrl: videoFresh ? image?.url : undefined,
    videoFresh, secondsLeft: Math.max(0, Math.ceil((expiresAt - now) / 1000)) };
}
