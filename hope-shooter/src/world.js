import * as THREE from 'three';
import { Reflector } from 'three/addons/objects/Reflector.js';
import { RoundedBoxGeometry } from 'three/addons/geometries/RoundedBoxGeometry.js';
import * as M from './materials.js';
import { makeRng } from './tex.js';
import { flattenByMaterial } from './util.js';
import { loadEnvironment } from './env.js';

export const STREET_LENGTH = 210;
export const STREET_WIDTH = 14;

// ============================================================
// Sky, sun and image-based lighting
// ============================================================
// A dust-loaded sky: milky and almost uniform, with blue only surviving near
// the zenith. An analytic Preetham sky goes near-black opposite the sun, which
// is wrong for this weather and leaves the street lit from one side only.
const SKY_SHADER = {
  vertexShader: `
    varying vec3 vDir;
    void main() {
      vDir = position;
      gl_Position = projectionMatrix * modelViewMatrix * vec4(position, 1.0);
    }`,
  fragmentShader: `
    varying vec3 vDir;
    uniform vec3 uSun, uHorizon, uZenith, uGlow;
    void main() {
      vec3 d = normalize(vDir);
      float h = clamp(d.y, 0.0, 1.0);
      vec3 col = mix(uHorizon, uZenith, pow(h, 0.85));
      float s = max(dot(d, uSun), 0.0);
      col += uGlow * pow(s, 5.0) * 0.42;           // broad glow, no hard disc
      col += uHorizon * 0.2 * pow(1.0 - h, 9.0);   // haze piling up at the horizon
      gl_FragColor = vec4(col, 1.0);
    }`,
};

export function setupSky(scene, renderer) {
  const sunDir = new THREE.Vector3().setFromSphericalCoords(
    1, THREE.MathUtils.degToRad(90 - 29), THREE.MathUtils.degToRad(62));

  const horizon = new THREE.Color().setRGB(1.08, 0.99, 0.86, THREE.LinearSRGBColorSpace);
  const zenith = new THREE.Color().setRGB(0.58, 0.64, 0.8, THREE.LinearSRGBColorSpace);
  const glow = new THREE.Color().setRGB(1.5, 1.28, 0.92, THREE.LinearSRGBColorSpace);

  const makeDome = (radius) => new THREE.Mesh(
    new THREE.SphereGeometry(radius, 32, 20),
    new THREE.ShaderMaterial({
      ...SKY_SHADER,
      side: THREE.BackSide, depthWrite: false, fog: false,
      uniforms: {
        uSun: { value: sunDir }, uHorizon: { value: horizon },
        uZenith: { value: zenith }, uGlow: { value: glow },
      },
    }));

  const dome = makeDome(760);
  scene.add(dome);

  // The visible sky stays analytic so it matches the fog exactly, but the
  // lighting comes from a photographed urban HDRI — that structure is what
  // makes the glass, chrome and wet asphalt read as real rather than plastic.
  scene.environment = loadEnvironment(renderer, { tint: [1.07, 1.0, 0.88] });
  scene.environmentIntensity = 0.88;
  scene.environmentRotation = new THREE.Euler(0, THREE.MathUtils.degToRad(62), 0);

  // distance fades into exactly the sky's horizon colour
  scene.fog = new THREE.FogExp2(0x000000, 0.0042);
  scene.fog.color.copy(horizon);

  // The sun itself is owned by the cascaded shadow rig in main.js, which
  // needs the camera to split its frustum.

  // the sky IBL already supplies ambient; this only lifts the ground bounce
  scene.add(new THREE.HemisphereLight(0xd0c3a4, 0x4a4238, 0.08));

  return { dome, sunDir: sunDir.clone() };
}

// ============================================================
// Shared material library — built once, reused by every building.
// ============================================================
const SHOPS = [
  ['슬기전자', '#1b2f58', '#efe6d2'], ['서울식당', '#75201b', '#f4e5c2'],
  ['희망약국', '#165630', '#eeeee0'], ['대성상회', '#563617', '#ece0c8'],
  ['호프사진관', '#20323c', '#e4dccb'], ['금성다방', '#661f3c', '#eeddcd'],
  ['제일이발관', '#134058', '#e9ecdd'], ['평화철물', '#3b3b20', '#e7e1cc'],
  ['영진상사', '#2f2a4a', '#ece4d4'], ['부산횟집', '#0f4a44', '#f0e8d6'],
];

export function buildMaterials() {
  return {
    stucco: [M.stucco(1), M.stucco(2), M.stucco(3), M.stucco(4)],
    brick: [M.brick(11), M.brick(12)],
    trim: M.stucco(21),
    kerb: M.stucco(22),
    walk: Object.assign(M.sidewalk(), { vertexColors: true }),
    road: Object.assign(M.asphalt(), { vertexColors: true }),
    roadLine: M.roadLine(),
    dirt: M.dirt(),
    glass: [M.glass(2), M.glass(3)],
    shutter: [M.shutter(31), M.shutter(32)],
    awning: [M.awning(41), M.awning(42)],
    metal: M.paintedMetal(0x8d8578, 51, { rust: 0.7, rough: 0.6 }),
    darkMetal: M.paintedMetal(0x4d443a, 52, { rust: 0.4, rough: 0.9 }),
    rust: M.paintedMetal(0x6a5a48, 53, { rust: 1.0, rough: 0.85 }),
    wood: M.paintedMetal(0x6b563c, 54, { rust: 0.15, rough: 0.92 }),
    crate: M.paintedMetal(0x7a6446, 55, { rust: 0.3, rough: 0.9 }),
    cabinet: M.paintedMetal(0x5e6a5a, 56, { rust: 0.8, rough: 0.7 }),
    signs: SHOPS.map(([t, bg, fg], i) => M.signBoard(t, bg, fg, i + 1)),
    interior: new THREE.MeshStandardMaterial({ color: 0x0a0b0c, roughness: 1 }),
    insulator: new THREE.MeshStandardMaterial({ color: 0xd6cdb6, roughness: 0.35 }),
    paper: new THREE.MeshStandardMaterial({
      // dirty newsprint, not fresh copier paper — the bright sheets read as
      // glowing white parallelograms scattered down the road
      color: 0x877c66, roughness: 0.97, side: THREE.DoubleSide,
    }),
  };
}

// ============================================================
// One shopfront building, windows punched as real openings
// ============================================================
function makeBuilding({ width, floors, seed, rng, lib }) {
  const g = new THREE.Group();
  const groundH = 4.3;
  const floorH = 3.05;
  const height = groundH + floors * floorH;
  const depth = 8 + rng() * 4.5;

  const wall = rng() < 0.3 ? lib.brick[seed % lib.brick.length]
                           : lib.stucco[seed % lib.stucco.length];
  const trim = lib.trim;
  const glass = lib.glass[seed % lib.glass.length];
  const metal = lib.metal;

  // --- openings ---
  const winW = 1.35, winH = 1.75;
  const perFloor = Math.max(2, Math.round(width / 3.4));
  const openings = [];
  for (let f = 0; f < floors; f++) {
    const y = groundH + f * floorH + 0.72;
    for (let i = 0; i < perFloor; i++) {
      openings.push({
        x: -width / 2 + (width / perFloor) * (i + 0.5),
        y, boarded: rng() < 0.16,
      });
    }
  }

  const shape = new THREE.Shape();
  shape.moveTo(-width / 2, 0);
  shape.lineTo(width / 2, 0);
  shape.lineTo(width / 2, height);
  shape.lineTo(-width / 2, height);
  shape.closePath();
  for (const o of openings) {
    const p = new THREE.Path();
    p.moveTo(o.x - winW / 2, o.y);
    p.lineTo(o.x + winW / 2, o.y);
    p.lineTo(o.x + winW / 2, o.y + winH);
    p.lineTo(o.x - winW / 2, o.y + winH);
    p.closePath();
    shape.holes.push(p);
  }
  const panel = new THREE.Mesh(
    new THREE.ExtrudeGeometry(shape, { depth: 0.45, bevelEnabled: false, curveSegments: 1 }),
    wall);
  panel.position.z = -0.45;
  g.add(panel);

  const body = new THREE.Mesh(new THREE.BoxGeometry(width, height, depth), wall);
  body.position.set(0, height / 2, -0.45 - depth / 2);
  g.add(body);

  const interior = new THREE.Mesh(
    new THREE.BoxGeometry(width - 0.12, height - 0.12, 1.6), lib.interior);
  interior.position.set(0, height / 2, -1.32);
  g.add(interior);

  // --- glazing, sills, boards, air-con ---
  for (const o of openings) {
    if (o.boarded) {
      for (let b = 0; b < 4; b++) {
        const plank = new THREE.Mesh(
          new THREE.BoxGeometry(winW * (1.02 + rng() * 0.06), winH / 4.6, 0.04), lib.wood);
        plank.position.set(o.x + (rng() - 0.5) * 0.1, o.y + 0.2 + b * (winH / 4.4), -0.28);
        plank.rotation.z = (rng() - 0.5) * 0.06;
        g.add(plank);
      }
    } else {
      const pane = new THREE.Mesh(new THREE.PlaneGeometry(winW, winH), glass);
      pane.position.set(o.x, o.y + winH / 2, -0.34);
      g.add(pane);
      const mv = new THREE.Mesh(new THREE.BoxGeometry(0.05, winH, 0.05), trim);
      mv.position.set(o.x, o.y + winH / 2, -0.3);
      const mh = new THREE.Mesh(new THREE.BoxGeometry(winW, 0.05, 0.05), trim);
      mh.position.set(o.x, o.y + winH * 0.55, -0.3);
      g.add(mv, mh);
    }
    const sill = new THREE.Mesh(new THREE.BoxGeometry(winW + 0.34, 0.1, 0.28), trim);
    sill.position.set(o.x, o.y - 0.05, 0.08);
    g.add(sill);
    if (rng() < 0.3) {
      const ac = new THREE.Mesh(new RoundedBoxGeometry(0.68, 0.44, 0.4, 2, 0.03), metal);
      ac.position.set(o.x + (rng() - 0.5) * 0.3, o.y - 0.35, 0.2);
      const brk = new THREE.Mesh(new THREE.BoxGeometry(0.7, 0.04, 0.34), metal);
      brk.position.set(ac.position.x, o.y - 0.58, 0.18);
      g.add(ac, brk);
    }
  }

  // --- floor bands ---
  for (let f = 0; f <= floors; f++) {
    const y = groundH + f * floorH - 0.18;
    if (y > height) break;
    const band = new THREE.Mesh(new THREE.BoxGeometry(width + 0.1, 0.22, 0.22), trim);
    band.position.set(0, y, 0.06);
    g.add(band);
  }

  // --- sign box over the shopfront ---
  const signH = 0.92;
  const box = new THREE.Mesh(new THREE.BoxGeometry(width * 0.94, signH, 0.34), trim);
  box.position.set(0, groundH - 0.72, 0.17);
  const face = new THREE.Mesh(
    new THREE.PlaneGeometry(width * 0.94, signH), lib.signs[seed % lib.signs.length]);
  face.position.set(0, groundH - 0.72, 0.345);
  g.add(box, face);

  // --- shutter or display window ---
  const bayW = width * 0.86, bayH = 2.5;
  if (seed % 3 === 0) {
    const sh = new THREE.Mesh(new THREE.PlaneGeometry(bayW, bayH),
      lib.shutter[seed % lib.shutter.length]);
    sh.position.set(0, bayH / 2 + 0.12, 0.02);
    g.add(sh);
  } else {
    const bay = new THREE.Mesh(new THREE.PlaneGeometry(bayW * 0.68, bayH), glass);
    bay.position.set(-bayW * 0.14, bayH / 2 + 0.12, -0.12);
    const door = new THREE.Mesh(new THREE.PlaneGeometry(bayW * 0.24, bayH * 0.92), glass);
    door.position.set(bayW * 0.32, bayH * 0.46 + 0.12, -0.1);
    g.add(bay, door);
    for (const px of [-bayW / 2, bayW * 0.2, bayW / 2]) {
      const post = new THREE.Mesh(new THREE.BoxGeometry(0.12, bayH + 0.24, 0.16), trim);
      post.position.set(px, bayH / 2 + 0.12, 0.04);
      g.add(post);
    }
    const head = new THREE.Mesh(new THREE.BoxGeometry(bayW + 0.2, 0.16, 0.2), trim);
    head.position.set(0, bayH + 0.2, 0.06);
    g.add(head);
  }

  // --- awning ---
  if (rng() < 0.45) {
    const aw = new THREE.Mesh(new THREE.PlaneGeometry(width * 0.8, 1.5, 14, 4),
      lib.awning[seed % lib.awning.length]);
    const pos = aw.geometry.attributes.position;
    for (let i = 0; i < pos.count; i++) {
      const x = pos.getX(i), y = pos.getY(i);
      pos.setZ(i, Math.sin((x / (width * 0.8) + 0.5) * Math.PI * 5) * 0.06 * (0.5 - y / 1.5));
    }
    aw.geometry.computeVertexNormals();
    aw.rotation.x = -Math.PI / 2 + 0.42;
    aw.position.set(0, 3.36, 0.86);
    g.add(aw);
    for (const sx of [-width * 0.36, width * 0.36]) {
      const bar = new THREE.Mesh(new THREE.CylinderGeometry(0.025, 0.025, 1.5, 6), metal);
      bar.position.set(sx, 3.15, 0.75);
      bar.rotation.x = 0.9;
      g.add(bar);
    }
  }

  // --- drain pipe ---
  if (rng() < 0.75) {
    const px = (rng() < 0.5 ? -1 : 1) * (width / 2 - 0.24);
    const pipe = new THREE.Mesh(new THREE.CylinderGeometry(0.075, 0.075, height, 8), metal);
    pipe.position.set(px, height / 2, 0.14);
    g.add(pipe);
    for (let f = 0; f <= floors; f++) {
      const clamp = new THREE.Mesh(new THREE.TorusGeometry(0.1, 0.02, 4, 8), metal);
      clamp.position.set(px, groundH + f * floorH, 0.14);
      clamp.rotation.x = Math.PI / 2;
      g.add(clamp);
    }
  }

  // --- roof clutter ---
  const parapet = new THREE.Mesh(new THREE.BoxGeometry(width + 0.2, 0.62, 0.3), trim);
  parapet.position.set(0, height + 0.3, 0.02);
  g.add(parapet);
  if (rng() < 0.5) {
    const tx = (rng() - 0.5) * width * 0.5, tz = -1.8 - rng() * 2;
    const tank = new THREE.Mesh(new THREE.CylinderGeometry(0.85, 0.85, 1.3, 16), metal);
    tank.position.set(tx, height + 0.95, tz);
    g.add(tank);
    for (let l = 0; l < 4; l++) {
      const leg = new THREE.Mesh(new THREE.CylinderGeometry(0.05, 0.05, 0.6, 5), metal);
      leg.position.set(tx + Math.cos(l * 1.57) * 0.6, height + 0.3, tz + Math.sin(l * 1.57) * 0.6);
      g.add(leg);
    }
  }
  if (rng() < 0.55) {
    const mx = (rng() - 0.5) * width * 0.6, mz = -1 - rng() * 3;
    const mast = new THREE.Mesh(new THREE.CylinderGeometry(0.03, 0.035, 2.6, 6), metal);
    mast.position.set(mx, height + 1.3, mz);
    g.add(mast);
    for (let a = 0; a < 4; a++) {
      const el = new THREE.Mesh(new THREE.CylinderGeometry(0.016, 0.016, 0.95 - a * 0.18, 4), metal);
      el.rotation.z = Math.PI / 2;
      el.position.set(mx, height + 0.9 + a * 0.5, mz);
      g.add(el);
    }
  }

  return g;
}

/**
 * Paints slow, non-repeating light and dirt variation into a ground plane's
 * vertex colours. The asphalt texture has to tile every few metres to stay
 * sharp underfoot, and tiling that tight reads as wallpaper; this rides on
 * top of it at a scale nothing repeats at.
 */
function mottled(geo, amount) {
  const pos = geo.attributes.position;
  const col = new Float32Array(pos.count * 3);
  for (let i = 0; i < pos.count; i++) {
    // the plane is still in XY here — it gets rotated flat afterwards
    const x = pos.getX(i), z = pos.getY(i);
    const n = Math.sin(x * 0.13) * Math.cos(z * 0.071)
            + Math.sin(z * 0.037 + x * 0.19) * 0.7
            + Math.sin(x * 0.41 + z * 0.011) * 0.35;
    const v = 1 - amount * 0.5 + (n / 2.05) * amount * 0.5;
    col[i * 3] = v;
    col[i * 3 + 1] = v * 0.995;
    col[i * 3 + 2] = v * 0.985;
  }
  geo.setAttribute('color', new THREE.BufferAttribute(col, 3));
  return geo;
}

// ============================================================
// The street
// ============================================================
export function buildStreet(scene, lib) {
  const rng = makeRng(20240721);
  const obstacles = [];
  const root = new THREE.Group();
  scene.add(root);

  const ground = new THREE.Mesh(new THREE.PlaneGeometry(900, 900), lib.dirt);
  ground.rotation.x = -Math.PI / 2;
  ground.position.y = -0.02;
  ground.receiveShadow = true;
  scene.add(ground);

  // Wet road: a mirror plane below, asphalt with puddle alpha above.
  //
  // A planar reflector is used rather than screen-space reflections. For a
  // flat road it is exact where SSR would drop out at the screen edges, and
  // three's SSRPass renders the scene into its own target the same way the
  // ambient-occlusion pass does, so the two cannot share a chain — SSR would
  // have cost the contact shadows across the whole street.
  // Darker than feels right in isolation: through the puddle cut-outs a
  // brighter mirror bounced the red facades back as saturated ember-like
  // patches on the road.
  const mirror = new Reflector(
    new THREE.PlaneGeometry(STREET_WIDTH, STREET_LENGTH + 60),
    { textureWidth: 1024, textureHeight: 1024, color: 0x101114 });
  mirror.rotation.x = -Math.PI / 2;
  mirror.position.set(0, 0.004, -STREET_LENGTH / 2 + 12);
  root.add(mirror);

  const road = new THREE.Mesh(
    mottled(new THREE.PlaneGeometry(STREET_WIDTH, STREET_LENGTH + 60, 10, 150), 0.24),
    lib.road);
  road.rotation.x = -Math.PI / 2;
  road.position.set(0, 0.014, -STREET_LENGTH / 2 + 12);
  road.receiveShadow = true;
  root.add(road);

  const line = new THREE.Mesh(
    new THREE.PlaneGeometry(0.17, STREET_LENGTH + 60), lib.roadLine);
  line.rotation.x = -Math.PI / 2;
  line.position.set(0, 0.016, -STREET_LENGTH / 2 + 12);
  root.add(line);

  const statics = new THREE.Group();

  for (const side of [-1, 1]) {
    const kerb = new THREE.Mesh(
      new RoundedBoxGeometry(0.4, 0.2, STREET_LENGTH + 60, 2, 0.04), lib.kerb);
    kerb.position.set(side * (STREET_WIDTH / 2 + 0.2), 0.1, -STREET_LENGTH / 2 + 12);
    statics.add(kerb);
    const walk = new THREE.Mesh(
      mottled(new THREE.PlaneGeometry(6.4, STREET_LENGTH + 60, 4, 120), 0.2), lib.walk);
    walk.rotation.x = -Math.PI / 2;
    walk.position.set(side * (STREET_WIDTH / 2 + 3.6), 0.2, -STREET_LENGTH / 2 + 12);
    statics.add(walk);
  }

  let seed = 5;
  for (const side of [-1, 1]) {
    let z = 8, lot = 0;
    while (z > -STREET_LENGTH) {
      const width = 9 + rng() * 6;
      if (lot === 5) {
        collapsedLot(statics, side, z, width, rng, lib);
        z -= width + 1.2; lot++;
        continue;
      }
      lot++;
      const b = makeBuilding({ width, floors: 1 + Math.floor(rng() * 2), seed: seed++, rng, lib });
      b.position.set(side * (STREET_WIDTH / 2 + 6.8), 0.2, z - width / 2);
      b.rotation.y = side === -1 ? Math.PI / 2 : -Math.PI / 2;
      statics.add(b);
      z -= width + (rng() < 0.22 ? 2.6 : 0.35);
    }
  }

  for (const [x, z, ry, col] of [
    [4.3, -24, 0.14, 0x7c786e], [-4.7, -55, -0.36, 0x565a52],
    [3.7, -92, 2.94, 0x6b6459], [-3.9, -136, 0.08, 0x74705f],
    [4.5, -172, 3.05, 0x5f5b52],
  ]) {
    car(statics, x, z, ry, col, rng, lib);
    obstacles.push({ minX: x - 2.5, maxX: x + 2.5, minZ: z - 2.5, maxZ: z + 2.5 });
  }

  streetProps(statics, rng, lib);

  // collapse the whole static set into a handful of draw calls
  root.add(flattenByMaterial(statics));

  // things that must stay separate
  poles(root, rng, lib);
  debris(root, rng, lib);

  return { obstacles, root, mirror };
}

function collapsedLot(parent, side, z, width, rng, lib) {
  const x = side * (STREET_WIDTH / 2 + 9.5);
  // rubble is plaster choked with dust, far darker than the walls it fell from
  if (!lib.rubble) {
    lib.rubble = lib.stucco[2].clone();
    lib.rubble.color.setRGB(0.5, 0.47, 0.44);
  }
  const mound = new THREE.Mesh(new THREE.SphereGeometry(width * 0.45, 14, 10), lib.rubble);
  mound.scale.set(1, 0.3, 1);
  mound.position.set(x, 0.1, z - width / 2);
  parent.add(mound);
  for (let i = 0; i < 12; i++) {
    const slab = new THREE.Mesh(
      new RoundedBoxGeometry(1.6 + rng() * 3, 0.26, 1.2 + rng() * 2, 2, 0.04), lib.rubble);
    slab.position.set(x + (rng() - 0.5) * width, 0.3 + rng() * width * 0.16,
                      z - width / 2 + (rng() - 0.5) * width);
    slab.rotation.set((rng() - 0.5) * 1.1, rng() * Math.PI, (rng() - 0.5) * 1.1);
    parent.add(slab);
  }
  for (let i = 0; i < 14; i++) {
    const bar = new THREE.Mesh(
      new THREE.CylinderGeometry(0.022, 0.022, 1.2 + rng() * 1.4, 5), lib.rust);
    bar.position.set(x + (rng() - 0.5) * width * 0.8, 0.9 + rng() * 1.2,
                     z - width / 2 + (rng() - 0.5) * width * 0.8);
    bar.rotation.set((rng() - 0.5) * 1.4, 0, (rng() - 0.5) * 1.4);
    parent.add(bar);
  }
}

function poles(root, rng, lib) {
  const wireMat = new THREE.LineBasicMaterial({ color: 0x17150f });
  const xs = [-(STREET_WIDTH / 2 + 1.4), STREET_WIDTH / 2 + 1.4];
  const group = new THREE.Group();
  for (let i = 0, z = -2; z > -STREET_LENGTH; z -= 23, i++) {
    const px = xs[i % 2];
    const pole = new THREE.Mesh(new THREE.CylinderGeometry(0.13, 0.18, 9.4, 8), lib.darkMetal);
    pole.position.set(px, 4.7, z);
    group.add(pole);
    for (const [ay, aw] of [[8.7, 1.9], [7.9, 1.4]]) {
      const arm = new THREE.Mesh(new THREE.BoxGeometry(aw, 0.11, 0.11), lib.darkMetal);
      arm.position.set(px, ay, z);
      group.add(arm);
      for (const ix of [-aw / 2 + 0.15, aw / 2 - 0.15]) {
        const ins = new THREE.Mesh(
          new THREE.CylinderGeometry(0.045, 0.055, 0.12, 6), lib.insulator);
        ins.position.set(px + ix, ay + 0.11, z);
        group.add(ins);
      }
    }
    if (rng() < 0.35) {
      const tr = new THREE.Mesh(new THREE.CylinderGeometry(0.28, 0.28, 0.72, 12), lib.darkMetal);
      tr.position.set(px + 0.3, 6.9, z);
      group.add(tr);
    }
    const nx = xs[(i + 1) % 2];
    if (z - 23 > -STREET_LENGTH) {
      for (const [off, y] of [[-0.8, 8.7], [0.8, 8.7], [-0.55, 7.9], [0.55, 7.9]]) {
        const pts = [];
        for (let t = 0; t <= 14; t++) {
          const k = t / 14;
          pts.push(new THREE.Vector3(
            px + off + (nx - px) * k,
            y - Math.sin(k * Math.PI) * (0.75 + Math.abs(off) * 0.5),
            z - 23 * k));
        }
        root.add(new THREE.Line(new THREE.BufferGeometry().setFromPoints(pts), wireMat));
      }
    }
  }
  root.add(flattenByMaterial(group));
}

function car(parent, x, z, ry, color, rng, lib) {
  const g = new THREE.Group();
  const body = lib.carPaint || (lib.carPaint = {});
  if (!body[color]) {
    body[color] = M.paintedMetal(color, (color & 0xff) + 3, { rust: 0.35, rough: 0.42 });
  }
  const bodyMat = body[color];
  const glassMat = lib.carGlass || (lib.carGlass = new THREE.MeshStandardMaterial({
    color: 0x14181a, roughness: 0.12, metalness: 0.1 }));
  const chrome = lib.chrome || (lib.chrome = new THREE.MeshStandardMaterial({
    color: 0x9a978e, roughness: 0.35, metalness: 0.9 }));
  const tyre = lib.tyre || (lib.tyre = new THREE.MeshStandardMaterial({
    color: 0x101010, roughness: 0.95 }));

  const lower = new THREE.Mesh(new RoundedBoxGeometry(4.5, 0.72, 1.86, 3, 0.12), bodyMat);
  lower.position.y = 0.66;
  const hood = new THREE.Mesh(new RoundedBoxGeometry(1.5, 0.3, 1.8, 3, 0.09), bodyMat);
  hood.position.set(1.5, 1.06, 0);
  const boot = new THREE.Mesh(new RoundedBoxGeometry(1.2, 0.3, 1.8, 3, 0.09), bodyMat);
  boot.position.set(-1.62, 1.06, 0);
  const greenhouse = new THREE.Mesh(new RoundedBoxGeometry(2.1, 0.62, 1.7, 3, 0.1), glassMat);
  greenhouse.position.set(-0.1, 1.44, 0);
  const roof = new THREE.Mesh(new RoundedBoxGeometry(2.0, 0.12, 1.74, 3, 0.06), bodyMat);
  roof.position.set(-0.1, 1.72, 0);
  const pf = new THREE.Mesh(new THREE.BoxGeometry(0.1, 0.6, 1.7), bodyMat);
  pf.position.set(0.94, 1.44, 0);
  const pr = new THREE.Mesh(new THREE.BoxGeometry(0.1, 0.6, 1.7), bodyMat);
  pr.position.set(-1.14, 1.44, 0);
  g.add(lower, hood, boot, greenhouse, roof, pf, pr);

  for (const bx of [2.32, -2.32]) {
    const bump = new THREE.Mesh(new RoundedBoxGeometry(0.2, 0.2, 1.94, 3, 0.06), chrome);
    bump.position.set(bx, 0.56, 0);
    g.add(bump);
  }
  for (const [wx, wz] of [[-1.5, 0.96], [1.5, 0.96], [-1.5, -0.96], [1.5, -0.96]]) {
    const flat = rng() < 0.35;
    const wheel = new THREE.Mesh(new THREE.CylinderGeometry(0.38, 0.38, 0.28, 18), tyre);
    wheel.rotation.x = Math.PI / 2;
    wheel.scale.y = flat ? 0.72 : 0.97;
    wheel.position.set(wx, flat ? 0.3 : 0.36, wz);
    const hub = new THREE.Mesh(new THREE.CylinderGeometry(0.16, 0.16, 0.3, 12), chrome);
    hub.rotation.x = Math.PI / 2;
    hub.position.copy(wheel.position);
    g.add(wheel, hub);
  }
  g.position.set(x, 0, z);
  g.rotation.y = ry;
  parent.add(g);
}

function debris(root, rng, lib) {
  const m = new THREE.Matrix4(), q = new THREE.Quaternion();
  const e = new THREE.Euler(), s = new THREE.Vector3(), p = new THREE.Vector3();

  const N = 420;
  const chunks = new THREE.InstancedMesh(
    new RoundedBoxGeometry(1, 0.6, 0.8, 2, 0.06), lib.stucco[3], N);
  chunks.castShadow = true; chunks.receiveShadow = true;
  const tint = new THREE.Color();
  for (let i = 0; i < N; i++) {
    const scale = 0.12 + rng() * 0.55;
    s.set(scale * (0.6 + rng()), scale, scale * (0.6 + rng()));
    const lane = rng() < 0.5 ? -1 : 1;
    p.set(lane * (1.5 + rng() * (STREET_WIDTH / 2 + 5)), scale * 0.3, 4 - rng() * STREET_LENGTH);
    e.set(rng() * 0.4, rng() * Math.PI * 2, rng() * 0.4);
    m.compose(p, q.setFromEuler(e), s);
    chunks.setMatrixAt(i, m);
    // per-chunk darkening: uniformly pale plaster read as styrofoam blocks
    const v = 0.32 + rng() * 0.3;
    chunks.setColorAt(i, tint.setRGB(v, v * (0.94 + rng() * 0.08), v * 0.9));
  }
  root.add(chunks);

  const P = 90;
  const papers = new THREE.InstancedMesh(new THREE.PlaneGeometry(0.3, 0.4), lib.paper, P);
  papers.receiveShadow = true;
  for (let i = 0; i < P; i++) {
    const scale = 0.45 + rng() * 0.85;
    s.set(scale, scale, 1);
    const lane = rng() < 0.5 ? -1 : 1;
    p.set(lane * (1 + rng() * (STREET_WIDTH / 2 + 5)), 0.035, 4 - rng() * STREET_LENGTH);
    e.set(-Math.PI / 2 + (rng() - 0.5) * 0.35, 0, rng() * Math.PI);
    m.compose(p, q.setFromEuler(e), s);
    papers.setMatrixAt(i, m);
    const v = 0.55 + rng() * 0.45;
    papers.setColorAt(i, tint.setRGB(v, v, v));
  }
  root.add(papers);
}

function streetProps(parent, rng, lib) {
  for (let i = 0; i < 16; i++) {
    const side = rng() < 0.5 ? -1 : 1;
    const z = -6 - rng() * (STREET_LENGTH - 20);
    const x = side * (STREET_WIDTH / 2 + 1.6 + rng() * 3);
    if (rng() < 0.5) {
      const box = new THREE.Mesh(new RoundedBoxGeometry(0.7, 1.1, 0.5, 2, 0.04), lib.cabinet);
      box.position.set(x, 0.75, z);
      box.rotation.y = rng() * Math.PI;
      parent.add(box);
    } else {
      const bin = new THREE.Mesh(new THREE.CylinderGeometry(0.32, 0.28, 0.86, 14), lib.cabinet);
      bin.position.set(x, 0.63, z);
      bin.rotation.z = rng() < 0.25 ? 1.4 : 0;
      parent.add(bin);
    }
  }
  for (let i = 0; i < 20; i++) {
    const side = rng() < 0.5 ? -1 : 1;
    const crate = new THREE.Mesh(
      new RoundedBoxGeometry(0.5 + rng() * 0.3, 0.4, 0.4 + rng() * 0.3, 2, 0.03), lib.crate);
    crate.position.set(side * (STREET_WIDTH / 2 + 0.9 + rng() * 3.4), 0.4,
                       -4 - rng() * (STREET_LENGTH - 16));
    crate.rotation.set((rng() - 0.5) * 0.6, rng() * Math.PI, (rng() - 0.5) * 0.6);
    parent.add(crate);
  }
}
