import { describe, it, expect } from 'vitest';
import { MjpegDecoder } from './mjpeg';
const packet = new TextEncoder().encode('--frame\r\nContent-Type: image/jpeg\r\nContent-Length: 4\r\n\r\nJPEG\r\n');
describe('MJPEG incremental', () => {
  it('decodifica cabeçalhos e quadros repartidos byte a byte', () => {
    const decoder = new MjpegDecoder(); const frames: Uint8Array[] = [];
    for (const byte of packet) frames.push(...decoder.feed(new Uint8Array([byte])));
    expect(frames).toHaveLength(1);
    expect(new TextDecoder().decode(frames[0])).toBe('JPEG');
  });
  it('processa vários quadros sem acumular atraso', () => {
    const decoder = new MjpegDecoder();
    const frames = decoder.feed(new Uint8Array([...packet, ...packet, ...packet]));
    expect(frames).toHaveLength(3);
  });
  it('recusa limites e cabeçalhos inválidos', () => {
    expect(() => new MjpegDecoder().feed(new Uint8Array(4_000_001))).toThrow();
    expect(() => new MjpegDecoder().feed(new TextEncoder().encode('--frame\r\nContent-Length: 99999999\r\n\r\n'))).toThrow();
  });
});
