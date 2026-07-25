import * as THREE from 'three';
import { pbr, makeCanvas, makeRng, noiseOverlay, texture, heightToNormal,
         grit, cracks, streaks, blob } from './tex.js';

// ============================================================
// The material library for the street.
// ============================================================

// ---------- asphalt ----------
// The road is two layers: a mirror plane underneath, and this surface on top
// with puddles punched out of its alpha so only the wet patches reflect.
//
// Surface detail and puddles tile at completely different rates — grit needs
// to repeat every few metres to stay sharp underfoot, while puddles repeating
// that often would read as wallpaper. three gives every texture slot its own
// UV transform, so the alpha mask is stretched far longer than the base maps.
export function asphalt({ detailRepeat = [2, 38], puddleRepeat = [1, 7] } = {}) {
  const S = 1024;
  const P = 2048;
  const rng = makeRng(7);
  const puddles = [];
  for (let i = 0; i < 11; i++) {
    puddles.push({ x: rng() * P, y: rng() * P, r: 40 + rng() * 150 });
  }

  const paintBase = (ctx, w, h, r) => {
    ctx.fillStyle = '#3f3d38';
    ctx.fillRect(0, 0, w, h);
    noiseOverlay(ctx, w, h, { seed: 11, grid: 3, octaves: 5, color: [86, 82, 74], alpha: 0.55 });
    noiseOverlay(ctx, w, h, { seed: 29, grid: 14, octaves: 4, color: [22, 20, 17], alpha: 0.45 });
    // resurfacing patches with visible seams
    for (let i = 0; i < 8; i++) {
      const pw = 90 + r() * 260, ph = 70 + r() * 220;
      const px = r() * (w - pw), py = r() * (h - ph);
      ctx.fillStyle = `rgba(${30 + r() * 26 | 0},${28 + r() * 24 | 0},${25 + r() * 20 | 0},0.6)`;
      ctx.fillRect(px, py, pw, ph);
      ctx.strokeStyle = 'rgba(16,15,13,0.7)';
      ctx.lineWidth = 2.5;
      ctx.strokeRect(px, py, pw, ph);
    }
    grit(ctx, w, h, 26000, r, 0.4, 0.22);
  };

  const albedo = (ctx, w, h) => {
    const r = makeRng(7);
    paintBase(ctx, w, h, r);
    // oil drips down the centre of the lane
    for (let i = 0; i < 9; i++) {
      const ox = r() * w, oy = r() * h, rad = 26 + r() * 70;
      const g = ctx.createRadialGradient(ox, oy, 2, ox, oy, rad);
      g.addColorStop(0, 'rgba(12,11,10,0.62)');
      g.addColorStop(1, 'rgba(12,11,10,0)');
      ctx.fillStyle = g;
      ctx.beginPath(); ctx.arc(ox, oy, rad, 0, 7); ctx.fill();
    }
    cracks(ctx, w, h, 26, r, 'rgba(15,14,12,0.72)', 2.1);
  };

  const height = (ctx, w, h) => {
    const r = makeRng(7);
    ctx.fillStyle = '#808080';
    ctx.fillRect(0, 0, w, h);
    noiseOverlay(ctx, w, h, { seed: 29, grid: 14, octaves: 4, color: [255, 255, 255], alpha: 0.5 });
    noiseOverlay(ctx, w, h, { seed: 41, grid: 40, octaves: 3, color: [0, 0, 0], alpha: 0.4 });
    grit(ctx, w, h, 30000, r, 0.5, 0.5);
    cracks(ctx, w, h, 26, makeRng(7), 'rgba(0,0,0,0.9)', 2.1);
  };

  const rough = (ctx, w, h) => {
    ctx.fillStyle = '#d8d8d8'; // dry asphalt: very rough
    ctx.fillRect(0, 0, w, h);
    // damp streaks that never quite dried out
    noiseOverlay(ctx, w, h, { seed: 61, grid: 6, octaves: 4, color: [140, 140, 140], alpha: 0.6 });
    noiseOverlay(ctx, w, h, { seed: 83, grid: 2, octaves: 3, color: [88, 88, 88], alpha: 0.45 });
  };

  // alpha: puddle centres go transparent so the mirror plane shows through
  const alphaCanvas = makeCanvas(P, P, (ctx, w, h) => {
    ctx.fillStyle = '#ffffff';
    ctx.fillRect(0, 0, w, h);
    for (const p of puddles) {
      const g = ctx.createRadialGradient(p.x, p.y, p.r * 0.2, p.x, p.y, p.r);
      g.addColorStop(0, 'rgba(0,0,0,0.72)');
      g.addColorStop(1, 'rgba(0,0,0,0)');
      blob(ctx, p.x, p.y, p.r, makeRng(p.x | 0), g);
    }
  });

  const mat = pbr({
    size: S, albedo, height, rough,
    repeat: detailRepeat, normalScale: 1.0, roughness: 1.0, metalness: 0.0,
    transparent: true, depthWrite: true,
  });
  mat.alphaMap = texture(alphaCanvas, { repeat: puddleRepeat });
  return mat;
}

// ---------- pavement slabs ----------
export function sidewalk() {
  const rng = makeRng(23);
  const slab = (ctx, w, h, groove) => {
    for (let x = 0; x <= w; x += 128) {
      ctx.fillStyle = groove; ctx.fillRect(x - 3, 0, 6, h);
    }
    for (let y = 0; y <= h; y += 128) {
      ctx.fillStyle = groove; ctx.fillRect(0, y - 3, w, 6);
    }
  };
  return pbr({
    size: 512,
    albedo: (ctx, w, h) => {
      const r = makeRng(23);
      ctx.fillStyle = '#7c7466'; ctx.fillRect(0, 0, w, h);
      noiseOverlay(ctx, w, h, { seed: 5, grid: 3, octaves: 5, color: [150, 142, 126], alpha: 0.5 });
      noiseOverlay(ctx, w, h, { seed: 17, grid: 11, octaves: 4, color: [40, 36, 30], alpha: 0.4 });
      grit(ctx, w, h, 14000, r);
      slab(ctx, w, h, 'rgba(38,34,28,0.75)');
      // chipped slab corners
      for (let i = 0; i < 16; i++) {
        const bx = Math.floor(r() * 4) * 128, by = Math.floor(r() * 4) * 128;
        ctx.fillStyle = 'rgba(46,42,35,0.6)';
        ctx.beginPath(); ctx.moveTo(bx, by);
        ctx.lineTo(bx + 16 + r() * 44, by); ctx.lineTo(bx, by + 16 + r() * 44);
        ctx.closePath(); ctx.fill();
      }
      cracks(ctx, w, h, 10, r, 'rgba(30,27,22,0.5)', 1.2);
    },
    height: (ctx, w, h) => {
      ctx.fillStyle = '#8c8c8c'; ctx.fillRect(0, 0, w, h);
      noiseOverlay(ctx, w, h, { seed: 17, grid: 11, octaves: 4, color: [255, 255, 255], alpha: 0.35 });
      grit(ctx, w, h, 16000, makeRng(23), 0.5, 0.5);
      slab(ctx, w, h, 'rgba(0,0,0,0.9)');
    },
    repeat: [2, 56], normalScale: 1.1, roughness: 0.94,
  });
}

// ---------- painted concrete / stucco wall ----------
export function stucco(seed) {
  const tints = ['#a2977f', '#ada08a', '#98907f', '#b3a892', '#9c968a'];
  return pbr({
    size: 512,
    albedo: (ctx, w, h) => {
      const r = makeRng(seed);
      ctx.fillStyle = tints[seed % tints.length]; ctx.fillRect(0, 0, w, h);
      noiseOverlay(ctx, w, h, { seed: seed * 3 + 1, grid: 3, octaves: 5, color: [70, 62, 50], alpha: 0.34 });
      noiseOverlay(ctx, w, h, { seed: seed * 7 + 2, grid: 16, octaves: 4, color: [225, 216, 196], alpha: 0.22 });
      grit(ctx, w, h, 9000, r, 0.22, 0.16);
      // flaking paint reveals grey render underneath
      for (let i = 0; i < 12; i++) {
        blob(ctx, r() * w, r() * h, 10 + r() * 40, r, `rgba(122,116,104,${0.2 + r() * 0.3})`);
      }
      cracks(ctx, w, h, 7, r, 'rgba(58,52,44,0.4)', 1.1);
      streaks(ctx, 0, 0, w, h * 0.7, r, { alpha: 0.16, count: 14 });
    },
    height: (ctx, w, h) => {
      ctx.fillStyle = '#808080'; ctx.fillRect(0, 0, w, h);
      noiseOverlay(ctx, w, h, { seed: seed * 7 + 2, grid: 16, octaves: 5, color: [255, 255, 255], alpha: 0.45 });
      noiseOverlay(ctx, w, h, { seed: seed * 11, grid: 60, octaves: 3, color: [0, 0, 0], alpha: 0.35 });
      cracks(ctx, w, h, 7, makeRng(seed), 'rgba(0,0,0,0.85)', 1.1);
    },
    repeat: [0.5, 0.5], normalScale: 0.85, roughness: 0.93,
  });
}

// ---------- brick ----------
export function brick(seed) {
  const paint = (ctx, w, h, mode) => {
    const r = makeRng(seed + 99);
    const bw = 64, bh = 26, gap = 5;
    ctx.fillStyle = mode === 'h' ? '#5a5a5a' : '#6d6156';
    ctx.fillRect(0, 0, w, h);
    for (let y = 0, row = 0; y < h; y += bh + gap, row++) {
      const off = (row % 2) * (bw / 2);
      for (let x = -bw; x < w + bw; x += bw + gap) {
        const shade = r();
        if (mode === 'h') {
          ctx.fillStyle = `rgb(${180 + shade * 50 | 0},${180 + shade * 50 | 0},${180 + shade * 50 | 0})`;
        } else {
          const base = [138, 78, 58];
          const v = 0.7 + shade * 0.6;
          ctx.fillStyle = `rgb(${base[0] * v | 0},${base[1] * v | 0},${base[2] * v | 0})`;
        }
        ctx.fillRect(x + off, y, bw, bh);
      }
    }
    if (mode === 'a') {
      noiseOverlay(ctx, w, h, { seed: seed * 5, grid: 4, octaves: 5, color: [46, 38, 30], alpha: 0.42 });
      grit(ctx, w, h, 9000, r, 0.3, 0.14);
      streaks(ctx, 0, 0, w, h, r, { alpha: 0.2, count: 10 });
    } else {
      grit(ctx, w, h, 9000, r, 0.35, 0.35);
    }
  };
  return pbr({
    size: 512,
    albedo: (ctx, w, h) => paint(ctx, w, h, 'a'),
    height: (ctx, w, h) => paint(ctx, w, h, 'h'),
    repeat: [0.55, 0.55], normalScale: 1.35, roughness: 0.95,
  });
}

// ---------- corrugated steel shutter ----------
export function shutter(seed) {
  const ribs = (ctx, w, h, mode) => {
    const r = makeRng(seed + 5);
    for (let y = 0; y < h; y += 16) {
      for (let k = 0; k < 16; k++) {
        const t = k / 16;
        const shade = Math.sin(t * Math.PI);
        if (mode === 'h') {
          const v = 40 + shade * 200;
          ctx.fillStyle = `rgb(${v | 0},${v | 0},${v | 0})`;
        } else {
          const v = 0.5 + shade * 0.55;
          ctx.fillStyle = `rgb(${118 * v | 0},${113 * v | 0},${102 * v | 0})`;
        }
        ctx.fillRect(0, y + k, w, 1);
      }
    }
    if (mode === 'a') {
      noiseOverlay(ctx, w, h, { seed: seed * 13, grid: 5, octaves: 4, color: [96, 54, 24], alpha: 0.4 });
      streaks(ctx, 0, 0, w, h, r, { alpha: 0.4, rusty: true, count: 16 });
      for (let i = 0; i < 10; i++) blob(ctx, r() * w, r() * h, 8 + r() * 26, r, 'rgba(88,48,22,0.4)');
      grit(ctx, w, h, 5000, r, 0.3, 0.12);
    }
  };
  const m = pbr({
    size: 512,
    albedo: (ctx, w, h) => ribs(ctx, w, h, 'a'),
    height: (ctx, w, h) => ribs(ctx, w, h, 'h'),
    rough: (ctx, w, h) => {
      ctx.fillStyle = '#9a9a9a'; ctx.fillRect(0, 0, w, h);
      noiseOverlay(ctx, w, h, { seed: seed * 13, grid: 5, octaves: 4, color: [230, 230, 230], alpha: 0.6 });
    },
    repeat: [1, 1], normalScale: 1.1, roughness: 0.7, metalness: 0.55,
  });
  return m;
}

// ---------- shop sign board ----------
export function signBoard(text, bg, fg, seed) {
  const W = 1024, H = 256;
  const paint = (ctx, w, h, mode) => {
    const r = makeRng(seed + 71);
    if (mode === 'h') {
      ctx.fillStyle = '#9a9a9a'; ctx.fillRect(0, 0, w, h);
      ctx.fillStyle = '#d0d0d0'; ctx.fillRect(0, 0, w, 14);
      ctx.fillStyle = '#4a4a4a'; ctx.fillRect(0, h - 14, w, 14);
      ctx.font = 'bold 150px "Malgun Gothic", "Apple SD Gothic Neo", sans-serif';
      ctx.textAlign = 'center'; ctx.textBaseline = 'middle';
      ctx.fillStyle = '#c8c8c8';
      ctx.fillText(text, w / 2, h / 2 + 6);
      return;
    }
    ctx.fillStyle = bg; ctx.fillRect(0, 0, w, h);
    noiseOverlay(ctx, w, h, { seed: seed * 3, grid: 4, octaves: 4, color: [14, 12, 10], alpha: 0.3 });
    // panel joints
    ctx.fillStyle = 'rgba(0,0,0,0.28)';
    for (let x = 0; x < w; x += 256) ctx.fillRect(x, 0, 3, h);
    // hand-painted hangul: dark offset then the face
    ctx.font = 'bold 150px "Malgun Gothic", "Apple SD Gothic Neo", sans-serif';
    ctx.textAlign = 'center'; ctx.textBaseline = 'middle';
    ctx.fillStyle = 'rgba(0,0,0,0.45)';
    ctx.fillText(text, w / 2 + 5, h / 2 + 11);
    ctx.fillStyle = fg;
    ctx.fillText(text, w / 2, h / 2 + 6);
    // weathering over the paint
    for (let i = 0; i < 16; i++) blob(ctx, r() * w, r() * h, 6 + r() * 26, r, 'rgba(40,34,26,0.22)');
    streaks(ctx, 0, 0, w, h, r, { alpha: 0.28, rusty: true, count: 12 });
    grit(ctx, w, h, 4000, r, 0.24, 0.1);
  };
  return pbr({
    size: [W, H],
    albedo: (ctx, w, h) => paint(ctx, w, h, 'a'),
    height: (ctx, w, h) => paint(ctx, w, h, 'h'),
    repeat: [1, 1], normalScale: 0.55, roughness: 0.72,
  });
}

// ---------- striped awning canvas ----------
export function awning(seed) {
  const paint = (ctx, w, h, mode) => {
    const r = makeRng(seed + 3);
    const cols = ['#8c3f33', '#d8cdb4'];
    for (let x = 0, i = 0; x < w; x += 64, i++) {
      ctx.fillStyle = mode === 'h' ? '#8a8a8a' : cols[i % 2];
      ctx.fillRect(x, 0, 64, h);
    }
    if (mode === 'h') {
      // sag ripples between the ribs
      for (let x = 0; x < w; x++) {
        const v = 128 + Math.sin(x / 64 * Math.PI * 2) * 60;
        ctx.fillStyle = `rgba(${v | 0},${v | 0},${v | 0},0.6)`;
        ctx.fillRect(x, 0, 1, h);
      }
      return;
    }
    noiseOverlay(ctx, w, h, { seed: seed * 9, grid: 6, octaves: 4, color: [46, 40, 30], alpha: 0.4 });
    streaks(ctx, 0, 0, w, h, r, { alpha: 0.3, count: 10 });
    grit(ctx, w, h, 3000, r, 0.2, 0.1);
  };
  return pbr({
    size: 512,
    albedo: (ctx, w, h) => paint(ctx, w, h, 'a'),
    height: (ctx, w, h) => paint(ctx, w, h, 'h'),
    repeat: [1, 1], normalScale: 0.7, roughness: 0.88,
    side: THREE.DoubleSide,
  });
}

// ---------- dusty window glass ----------
export function glass(seed) {
  return pbr({
    size: 512,
    albedo: (ctx, w, h) => {
      const r = makeRng(seed + 41);
      const g = ctx.createLinearGradient(0, 0, 0, h);
      g.addColorStop(0, '#2c3336'); g.addColorStop(0.55, '#171c1f'); g.addColorStop(1, '#0e1113');
      ctx.fillStyle = g; ctx.fillRect(0, 0, w, h);
      // dust film and hand smears
      noiseOverlay(ctx, w, h, { seed: seed * 17, grid: 5, octaves: 4, color: [176, 164, 138], alpha: 0.3 });
      streaks(ctx, 0, 0, w, h, r, { alpha: 0.18, count: 14 });
      // cracks radiating from an impact
      if (seed % 2 === 0) {
        const cx = w * (0.25 + r() * 0.5), cy = h * (0.25 + r() * 0.5);
        ctx.strokeStyle = 'rgba(226,222,208,0.5)';
        for (let k = 0; k < 9; k++) {
          ctx.lineWidth = 0.8 + r() * 1.6;
          ctx.beginPath(); ctx.moveTo(cx, cy);
          const a = (k / 9) * Math.PI * 2 + r();
          ctx.lineTo(cx + Math.cos(a) * (40 + r() * 180), cy + Math.sin(a) * (40 + r() * 180));
          ctx.stroke();
        }
      }
    },
    repeat: [1, 1], normalScale: 0.25, roughness: 0.18, metalness: 0.05,
  });
}

// ---------- rusted / painted metal (poles, pipes, cars) ----------
export function paintedMetal(hex, seed, { rust = 0.5, rough = 0.55 } = {}) {
  return pbr({
    size: 512,
    color: hex,
    albedo: (ctx, w, h) => {
      const r = makeRng(seed + 13);
      ctx.fillStyle = '#ffffff'; ctx.fillRect(0, 0, w, h);
      noiseOverlay(ctx, w, h, { seed: seed * 23, grid: 4, octaves: 4, color: [30, 26, 22], alpha: 0.3 });
      for (let i = 0; i < 40 * rust; i++) {
        blob(ctx, r() * w, r() * h, 4 + r() * 26, r, `rgba(112,64,30,${0.25 + r() * 0.45})`);
      }
      streaks(ctx, 0, 0, w, h, r, { alpha: 0.3 * rust, rusty: true, count: 12 });
      // road dust settling on upper faces
      noiseOverlay(ctx, w, h, { seed: seed * 31, grid: 9, octaves: 3, color: [186, 172, 142], alpha: 0.28 });
      grit(ctx, w, h, 4000, r, 0.2, 0.12);
    },
    repeat: [1, 1], normalScale: 0.6, roughness: rough, metalness: 0.72,
  });
}

// ---------- generic dusty ground beyond the street ----------
export function dirt() {
  return pbr({
    size: 512,
    albedo: (ctx, w, h) => {
      const r = makeRng(97);
      ctx.fillStyle = '#7d7361'; ctx.fillRect(0, 0, w, h);
      noiseOverlay(ctx, w, h, { seed: 3, grid: 4, octaves: 5, color: [148, 136, 112], alpha: 0.6 });
      noiseOverlay(ctx, w, h, { seed: 19, grid: 18, octaves: 4, color: [48, 42, 34], alpha: 0.4 });
      grit(ctx, w, h, 12000, r, 0.3, 0.2);
    },
    repeat: [40, 40], normalScale: 0.8, roughness: 0.98,
  });
}

// ---------- painted road markings ----------
// Kept off the asphalt texture: that tiles several times across the road
// width, which would paint a centre line in every lane.
export function roadLine() {
  return pbr({
    size: [128, 512],
    albedo: (ctx, w, h) => {
      const r = makeRng(131);
      // the canvas stays transparent between dashes so alphaTest cuts them out
      for (let y = 0; y < h; y += 256) {
        ctx.fillStyle = `rgb(198,180,126)`;
        ctx.fillRect(10, y + 8, w - 20, 150);
      }
      // tyres have scrubbed chips out of the paint
      ctx.globalCompositeOperation = 'destination-out';
      for (let k = 0; k < 220; k++) {
        ctx.fillStyle = `rgba(0,0,0,${0.5 + r() * 0.5})`;
        ctx.fillRect(4 + r() * (w - 8), r() * h, 3 + r() * 11, 3 + r() * 10);
      }
      // grime settling on the paint, clipped to the dashes
      ctx.globalCompositeOperation = 'source-atop';
      noiseOverlay(ctx, w, h, { seed: 7, grid: 9, octaves: 4, color: [40, 34, 26], alpha: 0.5 });
      ctx.globalCompositeOperation = 'source-over';
    },
    repeat: [1, 34], normalScale: 0.4, roughness: 0.88,
    transparent: true, alphaTest: 0.35, depthWrite: false, polygonOffset: true,
    polygonOffsetFactor: -2, polygonOffsetUnits: -2,
  });
}
