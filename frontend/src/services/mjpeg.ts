// Multipart incremental: tolera fronteiras repartidas entre pacotes de rede.
// Content-Length evita procurar delimitadores dentro de um JPEG.
export class MjpegDecoder {
  private buffer = new Uint8Array(0);
  feed(chunk: Uint8Array): Uint8Array[] {
    const combined = new Uint8Array(this.buffer.length + chunk.length);
    combined.set(this.buffer); combined.set(chunk, this.buffer.length); this.buffer = combined;
    if (this.buffer.length > 4_000_000) throw new Error('Transmissão excedeu o limite de memória.');
    const frames: Uint8Array[] = [];
    while (true) {
      let end = -1;
      for (let i = 0; i < this.buffer.length - 3; i++) {
        if (this.buffer[i] === 13 && this.buffer[i + 1] === 10 &&
            this.buffer[i + 2] === 13 && this.buffer[i + 3] === 10) { end = i; break; }
      }
      if (end < 0) break;
      if (end > 4096) throw new Error('Cabeçalho de vídeo inválido.');
      const header = new TextDecoder().decode(this.buffer.slice(0, end));
      const match = /Content-Length:\s*(\d+)/i.exec(header);
      const length = Number(match?.[1]);
      if (!header.includes('--frame') || !/Content-Type: image\/jpeg/i.test(header) ||
          !Number.isInteger(length) || length < 1 || length > 2_000_000) {
        throw new Error('Formato de vídeo inválido.');
      }
      if (this.buffer.length < end + 4 + length) break;
      frames.push(this.buffer.slice(end + 4, end + 4 + length));
      this.buffer = this.buffer.slice(end + 4 + length);
    }
    return frames;
  }
}
