import * as THREE from 'three';

// ============================================================
// Procedural PBR texture toolkit
// Every surface gets albedo + normal + roughness so it reacts to
// the sun and the sky IBL the way a real material would.
// ============================================================

export function makeRng(seed) {
  let s = (seed >>> 0) || 1;
  return () => {
    s ^= s << 13; s >>>= 0;
    s ^= s >> 17;
    s ^= s << 5; s >>>= 0;
    return s / 4294967296;
  };
}

// ---------- tileable value-noise fbm ----------
function lattice(size, rng) {
  const a = new Float32Array(size * size);
  for (let i = 0; i < a.length; i++) a[i] = rng();
  return a;
}

function fbm(w, h, octaves, baseGrid, rng) {
  const out = new Float32Array(w * h);
  let amp = 1, norm = 0, grid = baseGrid;
  for (let o = 0; o < octaves; o++) {
    const g = Math.max(2, Math.round(grid));
    const lat = lattice(g, rng);
    for (let y = 0; y < h; y++) {
      const fy = (y / h) * g, y0 = Math.floor(fy), ty = fy - y0;
      const sy = ty * ty * (3 - 2 * ty);
      const r0 = ((y0 % g) + g) % g * g, r1 = ((y0 + 1) % g) * g;
      for (let x = 0; x < w; x++) {
        const fx = (x / w) * g, x0 = Math.floor(fx), tx = fx - x0;
        const sx = tx * tx * (3 - 2 * tx);
        const c0 = ((x0 % g) + g) % g, c1 = (x0 + 1) % g;
        const v = (lat[r0 + c0] * (1 - sx) + lat[r0 + c1] * sx) * (1 - sy)
                + (lat[r1 + c0] * (1 - sx) + lat[r1 + c1] * sx) * sy;
        out[y * w + x] += v * amp;
      }
    }
    norm += amp;
    amp *= 0.5;
    grid *= 2;
  }
  for (let i = 0; i < out.length; i++) out[i] /= norm;
  return out;
}

/** Paint an fbm field onto a canvas context as a tinted overlay. */
export function noiseOverlay(ctx, w, h, { octaves = 4, grid = 4, seed = 1,
                                          lo = 0, hi = 1, color = [0, 0, 0], alpha = 1 } = {}) {
  const f = fbm(w, h, octaves, grid, makeRng(seed));
  const img = ctx.createImageData(w, h);
  const d = img.data;
  for (let i = 0; i < f.length; i++) {
    const v = Math.min(1, Math.max(0, (f[i] - lo) / (hi - lo)));
    d[i * 4] = color[0]; d[i * 4 + 1] = color[1]; d[i * 4 + 2] = color[2];
    d[i * 4 + 3] = v * 255 * alpha;
  }
  const tmp = document.createElement('canvas');
  tmp.width = w; tmp.height = h;
  tmp.getContext('2d').putImageData(img, 0, 0);
  ctx.drawImage(tmp, 0, 0);
}

export function makeCanvas(w, h, draw) {
  const c = document.createElement('canvas');
  c.width = w; c.height = h;
  const ctx = c.getContext('2d', { willReadFrequently: true });
  draw(ctx, w, h);
  return c;
}

/**
 * Sobel a greyscale height canvas into a tangent-space normal map.
 * Wraps at the edges so tiled surfaces stay seamless.
 */
export function heightToNormal(heightCanvas, strength = 2.2) {
  const w = heightCanvas.width, h = heightCanvas.height;
  const src = heightCanvas.getContext('2d', { willReadFrequently: true })
    .getImageData(0, 0, w, h).data;
  const out = document.createElement('canvas');
  out.width = w; out.height = h;
  const octx = out.getContext('2d');
  const img = octx.createImageData(w, h);
  const d = img.data;
  const H = (x, y) => src[((((y % h) + h) % h) * w + (((x % w) + w) % w)) * 4] / 255;
  for (let y = 0; y < h; y++) {
    for (let x = 0; x < w; x++) {
      const dx = (H(x + 1, y - 1) + 2 * H(x + 1, y) + H(x + 1, y + 1)
                - H(x - 1, y - 1) - 2 * H(x - 1, y) - H(x - 1, y + 1)) * strength;
      const dy = (H(x - 1, y + 1) + 2 * H(x, y + 1) + H(x + 1, y + 1)
                - H(x - 1, y - 1) - 2 * H(x, y - 1) - H(x + 1, y - 1)) * strength;
      let nx = -dx, ny = -dy, nz = 1;
      const len = Math.hypot(nx, ny, nz);
      nx /= len; ny /= len; nz /= len;
      const i = (y * w + x) * 4;
      d[i] = (nx * 0.5 + 0.5) * 255;
      d[i + 1] = (ny * 0.5 + 0.5) * 255;
      d[i + 2] = (nz * 0.5 + 0.5) * 255;
      d[i + 3] = 255;
    }
  }
  octx.putImageData(img, 0, 0);
  return out;
}

let maxAniso = 8;
export function setAnisotropy(v) { maxAniso = v; }

export function texture(canvas, { srgb = false, repeat = [1, 1] } = {}) {
  const t = new THREE.CanvasTexture(canvas);
  t.wrapS = t.wrapT = THREE.RepeatWrapping;
  t.repeat.set(repeat[0], repeat[1]);
  t.anisotropy = maxAniso;
  if (srgb) t.colorSpace = THREE.SRGBColorSpace;
  return t;
}

/**
 * Build a MeshStandardMaterial from painter callbacks.
 * `height` and `rough` are optional; when absent the albedo luminance
 * stands in for relief, which reads well on concrete and asphalt.
 */
export function pbr({ size = 512, albedo, height, rough, repeat = [1, 1],
                      normalScale = 1, roughness = 0.9, metalness = 0,
                      color = 0xffffff, ...rest }) {
  const [w, h] = Array.isArray(size) ? size : [size, size];
  const albedoCanvas = makeCanvas(w, h, albedo);
  const heightCanvas = height ? makeCanvas(w, h, height) : greyscale(albedoCanvas);
  const mat = new THREE.MeshStandardMaterial({
    color,
    map: texture(albedoCanvas, { srgb: true, repeat }),
    normalMap: texture(heightToNormal(heightCanvas, 2.4), { repeat }),
    roughness, metalness,
    ...rest,
  });
  mat.normalScale.set(normalScale, normalScale);
  if (rough) mat.roughnessMap = texture(makeCanvas(w, h, rough), { repeat });
  return mat;
}

function greyscale(canvas) {
  const w = canvas.width, h = canvas.height;
  const src = canvas.getContext('2d', { willReadFrequently: true }).getImageData(0, 0, w, h);
  const d = src.data;
  for (let i = 0; i < d.length; i += 4) {
    const l = d[i] * 0.299 + d[i + 1] * 0.587 + d[i + 2] * 0.114;
    d[i] = d[i + 1] = d[i + 2] = l;
  }
  const out = document.createElement('canvas');
  out.width = w; out.height = h;
  out.getContext('2d').putImageData(src, 0, 0);
  return out;
}

// ---------- shared painting helpers ----------

/** Scatter fine light/dark grit — reads as aggregate in concrete and asphalt. */
export function grit(ctx, w, h, n, rng, darkA = 0.35, lightA = 0.18) {
  for (let i = 0; i < n; i++) {
    const s = 0.6 + rng() * 2.4;
    ctx.fillStyle = rng() < 0.55
      ? `rgba(24,21,17,${rng() * darkA})`
      : `rgba(248,242,226,${rng() * lightA})`;
    ctx.fillRect(rng() * w, rng() * h, s, s);
  }
}

/** Branching crack lines. */
export function cracks(ctx, w, h, n, rng, color = 'rgba(20,18,15,0.65)', width = 1.6) {
  ctx.strokeStyle = color;
  for (let i = 0; i < n; i++) {
    let x = rng() * w, y = rng() * h;
    let a = rng() * Math.PI * 2;
    ctx.lineWidth = width * (0.6 + rng() * 0.8);
    ctx.beginPath();
    ctx.moveTo(x, y);
    const steps = 5 + Math.floor(rng() * 8);
    for (let j = 0; j < steps; j++) {
      a += (rng() - 0.5) * 1.1;
      const len = 8 + rng() * 34;
      x += Math.cos(a) * len; y += Math.sin(a) * len;
      ctx.lineTo(x, y);
    }
    ctx.stroke();
  }
}

/** Vertical grime/rust runs beneath a ledge. */
export function streaks(ctx, x, y, width, len, rng, { alpha = 0.3, rusty = false, count = 5 } = {}) {
  const rgb = rusty ? '104,62,30' : '36,32,26';
  for (let i = 0; i < count; i++) {
    const sx = x + rng() * width;
    const sl = len * (0.35 + rng() * 0.65);
    const g = ctx.createLinearGradient(0, y, 0, y + sl);
    g.addColorStop(0, `rgba(${rgb},${alpha})`);
    g.addColorStop(0.25, `rgba(${rgb},${alpha * 0.7})`);
    g.addColorStop(1, `rgba(${rgb},0)`);
    ctx.fillStyle = g;
    ctx.fillRect(sx, y, 1 + rng() * 3.5, sl);
  }
}

/** Soft irregular blob — puddles, stains, damp patches. */
export function blob(ctx, cx, cy, r, rng, fill) {
  ctx.beginPath();
  const pts = 9;
  for (let i = 0; i <= pts; i++) {
    const a = (i / pts) * Math.PI * 2;
    const rr = r * (0.6 + rng() * 0.6);
    const x = cx + Math.cos(a) * rr, y = cy + Math.sin(a) * rr * 0.7;
    if (i === 0) ctx.moveTo(x, y); else ctx.lineTo(x, y);
  }
  ctx.closePath();
  ctx.fillStyle = fill;
  ctx.fill();
}
