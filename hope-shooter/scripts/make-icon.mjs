import { deflateSync } from 'node:zlib';
import { writeFileSync, mkdirSync } from 'node:fs';

// A 512px launcher icon, encoded by hand so the build needs no image library.
const SIZE = 512;

const crcTable = Array.from({ length: 256 }, (_, n) => {
  let c = n;
  for (let k = 0; k < 8; k++) c = c & 1 ? 0xedb88320 ^ (c >>> 1) : c >>> 1;
  return c >>> 0;
});
const crc32 = (buf) => {
  let c = 0xffffffff;
  for (const b of buf) c = crcTable[(c ^ b) & 0xff] ^ (c >>> 8);
  return (c ^ 0xffffffff) >>> 0;
};
const chunk = (type, data) => {
  const len = Buffer.alloc(4);
  len.writeUInt32BE(data.length);
  const body = Buffer.concat([Buffer.from(type, 'ascii'), data]);
  const crc = Buffer.alloc(4);
  crc.writeUInt32BE(crc32(body));
  return Buffer.concat([len, body, crc]);
};

const px = Buffer.alloc(SIZE * SIZE * 4);
const set = (x, y, r, g, b, a = 255) => {
  const i = (y * SIZE + x) * 4;
  px[i] = r; px[i + 1] = g; px[i + 2] = b; px[i + 3] = a;
};

const c = SIZE / 2;
for (let y = 0; y < SIZE; y++) {
  for (let x = 0; x < SIZE; x++) {
    const d = Math.hypot(x - c, y - c) / c;
    // dusty charcoal ground, warmer toward the middle
    const t = Math.max(0, 1 - d * 1.15);
    set(x, y, 18 + t * 40, 16 + t * 32, 14 + t * 22);
  }
}

// a worn amber reticle: the HUD crosshair, blown up
const ring = 168, thick = 13;
for (let y = 0; y < SIZE; y++) {
  for (let x = 0; x < SIZE; x++) {
    const dx = x - c, dy = y - c;
    const r = Math.hypot(dx, dy);
    const onRing = Math.abs(r - ring) < thick;
    const gapped = Math.abs(dx) > 26 && Math.abs(dy) > 26;
    const onTick = (Math.abs(dx) < thick * 0.55 || Math.abs(dy) < thick * 0.55)
      && r > ring - 74 && r < ring + 74;
    if ((onRing && gapped) || onTick) {
      const fade = 1 - Math.min(1, r / (SIZE * 0.62));
      set(x, y, 210 + fade * 40, 140 + fade * 45, 60 + fade * 30);
    }
  }
}

const raw = Buffer.alloc((SIZE * 4 + 1) * SIZE);
for (let y = 0; y < SIZE; y++) {
  raw[y * (SIZE * 4 + 1)] = 0; // no per-scanline filtering
  px.copy(raw, y * (SIZE * 4 + 1) + 1, y * SIZE * 4, (y + 1) * SIZE * 4);
}

const ihdr = Buffer.alloc(13);
ihdr.writeUInt32BE(SIZE, 0);
ihdr.writeUInt32BE(SIZE, 4);
ihdr[8] = 8;   // bit depth
ihdr[9] = 6;   // RGBA
const png = Buffer.concat([
  Buffer.from([0x89, 0x50, 0x4e, 0x47, 0x0d, 0x0a, 0x1a, 0x0a]),
  chunk('IHDR', ihdr),
  chunk('IDAT', deflateSync(raw, { level: 9 })),
  chunk('IEND', Buffer.alloc(0)),
]);

mkdirSync('build', { recursive: true });
writeFileSync('build/icon.png', png);
console.log(`build/icon.png — ${SIZE}x${SIZE}, ${(png.length / 1024).toFixed(0)} kB`);
