import * as THREE from 'three';
import { EffectComposer } from 'three/addons/postprocessing/EffectComposer.js';
import { RenderPass } from 'three/addons/postprocessing/RenderPass.js';
import { ShaderPass } from 'three/addons/postprocessing/ShaderPass.js';
import { OutputPass } from 'three/addons/postprocessing/OutputPass.js';
import { UnrealBloomPass } from 'three/addons/postprocessing/UnrealBloomPass.js';
import { GTAOPass } from 'three/addons/postprocessing/GTAOPass.js';
import { SMAAPass } from 'three/addons/postprocessing/SMAAPass.js';
import { CSM } from 'three/addons/csm/CSM.js';

import { setupSky, buildMaterials, buildStreet, STREET_LENGTH, STREET_WIDTH } from './world.js';
import { makeShadowCreature, makeRifle } from './actors.js';
import { makeOfficer, poseOfficer, attachScannedHead } from './player.js';
import { makeCanvas, makeRng, setAnisotropy, setDetailNormals, texture } from './tex.js';
import { loadDetailNormals } from './detail.js';
import { loadScannedHead } from './head.js';

const EYE_HEIGHT = 1.68;
const MAG_SIZE = 30;
const FIRE_INTERVAL = 0.1;

const $ = (id) => document.getElementById(id);
const rng = makeRng(99);

// ============================================================
// Renderer
// ============================================================
const canvas = $('game');
const renderer = new THREE.WebGLRenderer({ canvas, antialias: false, powerPreference: 'high-performance' });
renderer.setPixelRatio(Math.min(devicePixelRatio, 2));
renderer.setSize(innerWidth, innerHeight);
renderer.shadowMap.enabled = true;
// PCFSoftShadowMap is deprecated in this three version and silently falls back
// to PCFShadowMap, so the "soft" shadows were never soft. Ask for what we
// actually get; the softness comes from the cascade resolution instead.
renderer.shadowMap.type = THREE.PCFShadowMap;
renderer.toneMapping = THREE.ACESFilmicToneMapping;
renderer.toneMappingExposure = 0.76;
setAnisotropy(renderer.capabilities.getMaxAnisotropy());

const scene = new THREE.Scene();
const camera = new THREE.PerspectiveCamera(68, innerWidth / innerHeight, 0.02, 900);
scene.add(camera);

// The player's feet. The camera is derived from this every frame, so the
// same movement code drives both the first- and third-person views.
const player = new THREE.Vector3(0, 0, -4);
const eye = new THREE.Vector3();

// Dust, smoke and muzzle flashes live on their own layer. The ambient-occlusion
// pass renders the scene with an override material, which turns a billboard
// into a solid wall in its depth buffer — a haze card a few metres ahead would
// otherwise occlude the entire street. Its camera only ever sees layer 0.
const FX_LAYER = 1;
camera.layers.enable(FX_LAYER);
const aoCamera = camera.clone();
aoCamera.layers.set(0);

const toFx = (obj) => { obj.layers.set(FX_LAYER); return obj; };

// ============================================================
// Atmosphere: airborne dust, ground haze, smoke columns
// ============================================================
function softSprite(inner, outer) {
  return texture(makeCanvas(128, 128, (ctx) => {
    const g = ctx.createRadialGradient(64, 64, 2, 64, 64, 62);
    g.addColorStop(0, inner);
    g.addColorStop(1, outer);
    ctx.fillStyle = g;
    ctx.fillRect(0, 0, 128, 128);
  }), { srgb: true });
}

const hazeTex = softSprite('rgba(196,178,142,0.42)', 'rgba(196,178,142,0)');
// Smoke lit by a bright overcast sky reads mid-grey, not black — and each
// puff has to stay faint, because a column stacks nine of them.
const smokeTex = texture(makeCanvas(256, 256, (ctx) => {
  for (let i = 0; i < 7; i++) {
    const bx = 84 + Math.random() * 88, by = 84 + Math.random() * 88, r = 38 + Math.random() * 50;
    const g = ctx.createRadialGradient(bx, by, 3, bx, by, r);
    g.addColorStop(0, 'rgba(122,114,102,0.17)');
    g.addColorStop(1, 'rgba(122,114,102,0)');
    ctx.fillStyle = g;
    ctx.fillRect(0, 0, 256, 256);
  }
}), { srgb: true });
const wispTex = softSprite('rgba(12,9,18,0.62)', 'rgba(12,9,18,0)');
const flashTex = texture(makeCanvas(128, 128, (ctx) => {
  const g = ctx.createRadialGradient(64, 64, 2, 64, 64, 60);
  g.addColorStop(0, 'rgba(255,250,222,1)');
  g.addColorStop(0.28, 'rgba(255,186,84,0.92)');
  g.addColorStop(1, 'rgba(255,122,30,0)');
  ctx.fillStyle = g;
  ctx.fillRect(0, 0, 128, 128);
  ctx.strokeStyle = 'rgba(255,236,182,0.85)';
  ctx.lineWidth = 5;
  for (let a = 0; a < 7; a++) {
    ctx.beginPath();
    ctx.moveTo(64, 64);
    ctx.lineTo(64 + Math.cos(a * 0.9) * 60, 64 + Math.sin(a * 0.9) * 60);
    ctx.stroke();
  }
}), { srgb: true });

const hazeSprites = [];
const smokeSprites = [];

function buildAtmosphere() {
  // airborne motes, lit warm so they read against the haze
  const N = 1400;
  const pos = new Float32Array(N * 3);
  for (let i = 0; i < N; i++) {
    pos[i * 3] = (rng() - 0.5) * 46;
    pos[i * 3 + 1] = rng() * 9;
    pos[i * 3 + 2] = 6 - rng() * STREET_LENGTH;
  }
  const geo = new THREE.BufferGeometry();
  geo.setAttribute('position', new THREE.BufferAttribute(pos, 3));
  const motes = new THREE.Points(geo, new THREE.PointsMaterial({
    map: softSprite('rgba(255,238,198,0.9)', 'rgba(255,238,198,0)'),
    size: 0.075, transparent: true, depthWrite: false,
    blending: THREE.AdditiveBlending, opacity: 0.5, sizeAttenuation: true,
  }));
  scene.add(toFx(motes));

  // low dust banks drifting across the road
  for (let i = 0; i < 22; i++) {
    const sp = new THREE.Sprite(new THREE.SpriteMaterial({
      map: hazeTex, transparent: true, depthWrite: false,
      opacity: 0.1 + rng() * 0.09, fog: true,
    }));
    sp.position.set((rng() - 0.5) * 26, 0.9 + rng() * 2.6, -8 - rng() * (STREET_LENGTH - 16));
    sp.scale.set(17 + rng() * 15, 5 + rng() * 4, 1);
    sp.userData.drift = 0.18 + rng() * 0.5;
    hazeSprites.push(sp);
    scene.add(toFx(sp));
  }

  // fires burning out of sight, feeding smoke columns
  for (const [sx, sz] of [[24, -78], [-26, -124], [20, -168], [-22, -200]]) {
    for (let i = 0; i < 8; i++) {
      const sp = new THREE.Sprite(new THREE.SpriteMaterial({
        map: smokeTex, transparent: true, depthWrite: false, opacity: 0.32,
        rotation: rng() * Math.PI * 2, fog: true,
      }));
      sp.position.set(sx + (rng() - 0.5) * 3.5, 3 + i * 3.4, sz);
      sp.scale.setScalar(5 + i * 2.1);
      sp.userData = { baseY: sp.position.y, speed: 0.35 + rng() * 0.4, spin: (rng() - 0.5) * 0.14 };
      smokeSprites.push(sp);
      scene.add(toFx(sp));
    }
  }
  return motes;
}

// ============================================================
// Two ways to hold the same rifle.
//
// The film still is framed over the officer's shoulder, so third person is
// the default; first person keeps the detailed view model and gloved hands.
// Both share one muzzle, which is re-parented when the view changes.
// ============================================================
const viewRifle = makeRifle({ hands: true });
const REST = new THREE.Vector3(0.15, -0.17, -0.5);
const AIM = new THREE.Vector3(0, -0.075, -0.4);
viewRifle.scale.setScalar(0.86);
viewRifle.position.copy(REST);
camera.add(viewRifle);

const officer = makeOfficer();
const bodyRifle = makeRifle({ hands: false });
// slide the weapon back inside the grip so its butt lands at the shoulder
// instead of poking out through the officer's back
bodyRifle.scale.setScalar(0.85);
bodyRifle.position.set(0, 0, -0.18);
officer.userData.grip.add(bodyRifle);
scene.add(officer);

const muzzle = new THREE.Sprite(new THREE.SpriteMaterial({
  map: flashTex, transparent: true, opacity: 0, depthWrite: false, depthTest: false,
  blending: THREE.AdditiveBlending,
}));
toFx(muzzle);
muzzle.scale.setScalar(0.32);
muzzle.position.set(0, 0.01, -0.79);
const muzzleLight = new THREE.PointLight(0xffb15c, 0, 12, 2);
muzzleLight.position.copy(muzzle.position);

function applyView() {
  const host = S.thirdPerson ? bodyRifle : viewRifle;
  host.add(muzzle, muzzleLight);
  viewRifle.visible = !S.thirdPerson;
  officer.visible = S.thirdPerson;
}

// ============================================================
// Transient effects
// ============================================================
const wisps = [], sparks = [], tracers = [];

function shedWisp(p, scale) {
  if (wisps.length > 160) return;
  const sp = new THREE.Sprite(new THREE.SpriteMaterial({
    map: wispTex, transparent: true, depthWrite: false, opacity: 0.5,
    rotation: rng() * Math.PI * 2, fog: true,
  }));
  sp.position.copy(p);
  sp.position.x += (rng() - 0.5) * 0.35;
  sp.position.z += (rng() - 0.5) * 0.35;
  sp.scale.setScalar(scale);
  sp.userData = { life: 1.0, vy: 0.45 + rng() * 0.6 };
  scene.add(toFx(sp));
  wisps.push(sp);
}

function burst(p, color, n, speed, size) {
  const arr = new Float32Array(n * 3);
  const vel = [];
  for (let i = 0; i < n; i++) {
    arr[i * 3] = p.x; arr[i * 3 + 1] = p.y; arr[i * 3 + 2] = p.z;
    vel.push(new THREE.Vector3(
      (rng() - 0.5) * speed, rng() * speed * 0.85, (rng() - 0.5) * speed));
  }
  const geo = new THREE.BufferGeometry();
  geo.setAttribute('position', new THREE.BufferAttribute(arr, 3));
  const pts = new THREE.Points(geo, new THREE.PointsMaterial({
    color, size, transparent: true, opacity: 0.95, depthWrite: false, sizeAttenuation: true,
  }));
  pts.userData = { vel, life: 0.55 };
  scene.add(toFx(pts));
  sparks.push(pts);
}

const tracerMat = new THREE.LineBasicMaterial({
  color: 0xffd79a, transparent: true, opacity: 0.85, blending: THREE.AdditiveBlending,
});
function tracer(a, b) {
  const line = new THREE.Line(new THREE.BufferGeometry().setFromPoints([a, b]), tracerMat.clone());
  line.userData.life = 0.06;
  scene.add(toFx(line));
  tracers.push(line);
}

// ============================================================
// Audio
// ============================================================
let actx = null, reverb = null;
function initAudio() {
  if (actx) { if (actx.state === 'suspended') actx.resume(); return; }
  actx = new (window.AudioContext || window.webkitAudioContext)();
  // short concrete-street reverb
  const len = actx.sampleRate * 1.1;
  const buf = actx.createBuffer(2, len, actx.sampleRate);
  for (let c = 0; c < 2; c++) {
    const d = buf.getChannelData(c);
    for (let i = 0; i < len; i++) {
      d[i] = (Math.random() * 2 - 1) * Math.pow(1 - i / len, 3.4) * 0.55;
    }
  }
  reverb = actx.createConvolver();
  reverb.buffer = buf;
  const wet = actx.createGain();
  wet.gain.value = 0.34;
  reverb.connect(wet).connect(actx.destination);
}
function shotSound() {
  if (!actx) return;
  const t = actx.currentTime, dur = 0.26;
  const buf = actx.createBuffer(1, actx.sampleRate * dur, actx.sampleRate);
  const d = buf.getChannelData(0);
  for (let i = 0; i < d.length; i++) {
    d[i] = (Math.random() * 2 - 1) * Math.pow(1 - i / d.length, 2.2);
  }
  const src = actx.createBufferSource();
  src.buffer = buf;
  const lp = actx.createBiquadFilter();
  lp.type = 'lowpass';
  lp.frequency.setValueAtTime(4200, t);
  lp.frequency.exponentialRampToValueAtTime(260, t + dur);
  const g = actx.createGain();
  g.gain.setValueAtTime(0.5, t);
  g.gain.exponentialRampToValueAtTime(0.001, t + dur);
  src.connect(lp).connect(g);
  g.connect(actx.destination);
  g.connect(reverb);
  src.start(t);
}
function click(freq, gain = 0.11) {
  if (!actx) return;
  const t = actx.currentTime;
  const o = actx.createOscillator();
  o.type = 'square';
  o.frequency.value = freq;
  const g = actx.createGain();
  g.gain.setValueAtTime(gain, t);
  g.gain.exponentialRampToValueAtTime(0.001, t + 0.06);
  o.connect(g).connect(actx.destination);
  o.start(t); o.stop(t + 0.07);
}
function growl() {
  if (!actx) return;
  const t = actx.currentTime;
  const o = actx.createOscillator();
  o.type = 'sawtooth';
  o.frequency.setValueAtTime(96, t);
  o.frequency.exponentialRampToValueAtTime(42, t + 0.55);
  const g = actx.createGain();
  g.gain.setValueAtTime(0.14, t);
  g.gain.exponentialRampToValueAtTime(0.001, t + 0.55);
  o.connect(g);
  g.connect(actx.destination);
  g.connect(reverb);
  o.start(t); o.stop(t + 0.6);
}

// ============================================================
// Pickups dropped by the dead
// ============================================================
const pickups = [];
const PICKUP_MATS = {
  ammo: new THREE.MeshStandardMaterial({
    color: 0x4a4b3c, roughness: 0.7, metalness: 0.3,
    emissive: 0xffb552, emissiveIntensity: 0.5,
  }),
  health: new THREE.MeshStandardMaterial({
    color: 0xd8d2c4, roughness: 0.6, metalness: 0.05,
    emissive: 0xd0402c, emissiveIntensity: 0.7,
  }),
};
const PICKUP_GEO = new THREE.BoxGeometry(0.3, 0.2, 0.22);

function dropPickup(at) {
  const roll = rng();
  const kind = roll < 0.34 ? 'ammo' : (roll < 0.5 ? 'health' : null);
  if (!kind) return;
  const box = new THREE.Mesh(PICKUP_GEO, PICKUP_MATS[kind]);
  box.position.set(at.x, 0.22, at.z);
  box.castShadow = true;
  box.userData = { kind, spin: 0.9 + rng() * 0.5, life: 26 };
  scene.add(box);
  pickups.push(box);
}

function collectPickups(dt) {
  for (const p of [...pickups]) {
    p.userData.life -= dt;
    p.rotation.y += p.userData.spin * dt;
    p.position.y = 0.22 + Math.sin(elapsed * 2.4 + p.id) * 0.045;

    const near = Math.hypot(p.position.x - player.x, p.position.z - player.z) < 1.15;
    if (near) {
      if (p.userData.kind === 'ammo') {
        S.reserve += 30;
        banner('탄약 보급');
      } else {
        S.hp = Math.min(100, S.hp + 30);
        banner('응급 처치');
      }
      click(660, 0.09);
      syncHUD();
    }
    if (near || p.userData.life <= 0) {
      scene.remove(p);
      pickups.splice(pickups.indexOf(p), 1);
    }
  }
}

// ============================================================
// Game state
// ============================================================
const S = {
  running: false, over: false, ready: false,
  yaw: 0, pitch: 0, keys: {},
  firing: false, aiming: false, fireT: 0,
  reloading: false, reloadT: 0,
  ammo: MAG_SIZE, reserve: 90,
  hp: 100, kills: 0, score: 0,
  wave: 0, pending: 0, spawnT: 0,
  recoil: 0, kick: 0, bob: 0, shake: 0, aimBlend: 0,
  thirdPerson: true, camDist: 2.35, wasLocked: false,
};

const enemies = [];
const enemyMeshes = [];
let obstacles = [];

const ui = {
  hud: $('hud'), start: $('start'), over: $('over'), loading: $('loading'),
  loadFill: $('loadFill'), ammoNum: $('ammoNum'), ammoRes: $('ammoRes'),
  hpFill: $('hpFill'), waveNum: $('waveNum'), kills: $('kills'),
  banner: $('banner'), reloadHint: $('reloadHint'), damage: $('damage'),
  hitMarker: $('hitMarker'), score: $('score'),
};

function drawGunIcon() {
  const ctx = $('gunIcon').getContext('2d');
  ctx.fillStyle = '#ddd8c9';
  ctx.fillRect(8, 14, 52, 6);
  ctx.fillRect(60, 15, 26, 3);
  ctx.fillRect(12, 20, 9, 9);
  ctx.beginPath();
  ctx.moveTo(8, 14); ctx.lineTo(0, 25); ctx.lineTo(8, 25);
  ctx.closePath(); ctx.fill();
  ctx.fillRect(30, 8, 4, 6);
  ctx.fillRect(35, 20, 6, 6);
}

function syncHUD() {
  ui.ammoNum.textContent = S.ammo;
  ui.ammoNum.style.color = S.ammo === 0 ? '#e0553a' : '#e8e4d8';
  ui.ammoRes.textContent = '/ ' + S.reserve;
  ui.hpFill.style.width = Math.max(0, S.hp) + '%';
  ui.waveNum.textContent = S.wave;
  ui.kills.textContent = S.kills;
  ui.reloadHint.style.display =
    (!S.reloading && S.reserve > 0 && S.ammo <= 6) ? 'block' : 'none';
}

let bannerTimer = 0;
function banner(text) {
  ui.banner.textContent = text;
  ui.banner.style.opacity = 1;
  clearTimeout(bannerTimer);
  bannerTimer = setTimeout(() => { ui.banner.style.opacity = 0; }, 1900);
}

// ============================================================
// Waves
// ============================================================
function spawnEnemy() {
  const e = makeShadowCreature(rng);
  // from wave three a heavier one shows up: slower, far harder to put down
  const brute = S.wave >= 3 && rng() < 0.2;
  e.position.set(
    (rng() - 0.5) * (STREET_WIDTH - 3), 0,
    Math.max(player.z - (56 + rng() * 60), -STREET_LENGTH + 8));
  e.userData.brute = brute;
  e.userData.hp = (3 + Math.floor(S.wave / 2)) * (brute ? 3 : 1);
  e.userData.speed = (1.55 + rng() * 0.8) * (1 + S.wave * 0.065) * (brute ? 0.62 : 1);
  e.scale.setScalar(brute ? 1.6 + rng() * 0.2 : 1.08 + rng() * 0.34);
  if (brute) e.userData.eyeMat.emissive.setHex(0xff5a2a);
  scene.add(e);
  enemies.push(e);
  e.traverse((m) => { if (m.isMesh) enemyMeshes.push(m); });
}

function dropEnemy(e) {
  scene.remove(e);
  enemies.splice(enemies.indexOf(e), 1);
  e.traverse((m) => {
    if (m.isMesh) {
      const i = enemyMeshes.indexOf(m);
      if (i >= 0) enemyMeshes.splice(i, 1);
    }
  });
}

function nextWave() {
  S.wave++;
  S.pending = 4 + S.wave * 2;
  S.spawnT = 0;
  banner('WAVE ' + S.wave);
  growl();
  syncHUD();
}

// ============================================================
// Shooting
// ============================================================
const ray = new THREE.Raycaster();
ray.far = 220;
const v3 = new THREE.Vector3();

function shoot() {
  if (S.ammo === 0) { click(170, 0.08); S.firing = false; reload(); return; }
  S.ammo--;
  S.recoil = 1;
  S.kick = 1;
  S.shake = S.aiming ? 0.35 : 0.6;
  shotSound();
  muzzle.material.opacity = 1;
  muzzle.material.rotation = rng() * Math.PI * 2;
  muzzleLight.intensity = 26;

  const moving = S.keys.KeyW || S.keys.KeyA || S.keys.KeyS || S.keys.KeyD;
  const spread = (S.aiming ? 0.003 : 0.009) + (moving ? 0.012 : 0);
  const dir = new THREE.Vector3((rng() - 0.5) * spread, (rng() - 0.5) * spread, -1)
    .unproject(camera).sub(camera.position).normalize();

  ray.set(camera.position, dir);
  const hits = ray.intersectObjects(enemyMeshes, false);
  const from = muzzle.getWorldPosition(new THREE.Vector3());
  let to = camera.position.clone().addScaledVector(dir, 140);

  const hit = hits.find((h) => h.object.userData.enemy?.userData.state === 'walk');
  if (hit) {
    to = hit.point;
    const e = hit.object.userData.enemy;
    const head = !!hit.object.userData.headshot;
    e.userData.hp -= head ? 3 : 1;
    e.userData.hitT = 0.14;
    burst(hit.point, 0x30234a, head ? 26 : 18, head ? 4.4 : 3.6, 0.055);
    shedWisp(hit.point, 0.75);
    ui.hitMarker.style.opacity = 1;
    ui.hitMarker.classList.toggle('head', head);
    if (head) click(880, 0.06);
    setTimeout(() => { ui.hitMarker.style.opacity = 0; }, 90);
    if (e.userData.hp <= 0) {
      e.userData.state = 'dying';
      e.userData.dieT = 0.85;
      S.kills++;
      S.score += (e.userData.brute ? 250 : 100) + (head ? 50 : 0);
      dropPickup(e.position);
      growl();
    }
  } else {
    burst(to, 0xa2957c, 7, 2.2, 0.05);
  }
  tracer(from, to);
  syncHUD();
}

function reload() {
  if (S.reloading || S.ammo === MAG_SIZE || S.reserve === 0 || !S.running) return;
  S.reloading = true;
  S.reloadT = 1.7;
  click(320);
}

// ============================================================
// Input
// ============================================================
// Aim tracks raw mouse movement whether or not the pointer is locked. Locking
// can be refused — Electron does it depending on how the page was loaded — and
// gating aim on it left the player unable to look around at all.
addEventListener('mousemove', (e) => {
  if (!S.running) return;
  const sens = S.aiming ? 0.0011 : 0.0021;
  S.yaw -= e.movementX * sens;
  S.pitch = THREE.MathUtils.clamp(S.pitch - e.movementY * sens, -1.3, 1.3);
});
addEventListener('mousedown', (e) => {
  if (!S.running) return;
  if (e.button === 0) S.firing = true;
  if (e.button === 2) S.aiming = true;
});
addEventListener('mouseup', (e) => {
  if (e.button === 0) S.firing = false;
  if (e.button === 2) S.aiming = false;
});
addEventListener('contextmenu', (e) => e.preventDefault());
addEventListener('keydown', (e) => {
  S.keys[e.code] = true;
  if (e.code === 'KeyR') reload();
  if (e.code === 'KeyV') { S.thirdPerson = !S.thirdPerson; applyView(); }
});
addEventListener('keyup', (e) => { S.keys[e.code] = false; });

// Esc releases the pointer; that pauses the round rather than leaving the
// player firing blind at a cursor they can no longer see.
document.addEventListener('pointerlockchange', () => {
  if (document.pointerLockElement !== canvas && S.running && !S.over && S.wasLocked) {
    S.running = false;
    S.firing = false;
    ui.start.hidden = false;
    $('startBtn').textContent = '작전 재개';
  }
  S.wasLocked = document.pointerLockElement === canvas;
});

function begin() {
  initAudio();
  if (S.wave === 0) nextWave();
  ui.start.hidden = true;
  ui.over.hidden = true;
  ui.hud.style.display = 'block';
  S.running = true;
  // Chromium returns a promise here and rejects it when the document is not
  // eligible — an unhandled rejection either way, and pointerlockchange
  // already covers the not-locked case.
  const lock = canvas.requestPointerLock();
  if (lock && typeof lock.catch === 'function') lock.catch(() => {});
}

function restart() {
  for (const e of [...enemies]) dropEnemy(e);
  for (const p of [...pickups]) { scene.remove(p); pickups.splice(pickups.indexOf(p), 1); }
  Object.assign(S, {
    over: false, hp: 100, kills: 0, score: 0, wave: 0, ammo: MAG_SIZE, reserve: 90,
    reloading: false, firing: false, aiming: false, yaw: 0, pitch: 0,
  });
  player.set(0, 0, -4);
  nextWave();
  begin();
}

function gameOver() {
  S.over = true;
  S.running = false;
  S.firing = false;
  document.exitPointerLock();
  ui.hud.style.display = 'none';
  ui.score.textContent = `점수 ${S.score} · 사살 ${S.kills} · 도달 웨이브 ${S.wave}`;
  ui.over.hidden = false;
}

$('startBtn').addEventListener('click', begin);
$('againBtn').addEventListener('click', restart);

// ============================================================
// Collision
// ============================================================
function collide(p) {
  const half = STREET_WIDTH / 2 + 5.4;
  p.x = THREE.MathUtils.clamp(p.x, -half, half);
  p.z = THREE.MathUtils.clamp(p.z, -STREET_LENGTH + 6, 4);
  const R = 0.45;
  for (const o of obstacles) {
    if (p.x > o.minX - R && p.x < o.maxX + R && p.z > o.minZ - R && p.z < o.maxZ + R) {
      const dxa = p.x - (o.minX - R), dxb = (o.maxX + R) - p.x;
      const dza = p.z - (o.minZ - R), dzb = (o.maxZ + R) - p.z;
      const m = Math.min(dxa, dxb, dza, dzb);
      if (m === dxa) p.x = o.minX - R;
      else if (m === dxb) p.x = o.maxX + R;
      else if (m === dza) p.z = o.minZ - R;
      else p.z = o.maxZ + R;
    }
  }
}

// ============================================================
// Cascaded shadow maps
//
// One shadow map stretched over the whole street has to trade near detail
// against distant coverage. Cascades give the metres around the player their
// own high-resolution slice while still catching the far end.
// ============================================================
let csm = null;

function setupShadows() {
  csm = new CSM({
    camera, parent: scene,
    cascades: 4,
    maxFar: 130,
    mode: 'practical',
    shadowMapSize: 2048,
    lightDirection: sunDir.clone().negate().normalize(),
    lightIntensity: 3.3,
    lightMargin: 160,
    shadowBias: -0.00022,
  });
  csm.fade = true;
  for (const light of csm.lights) {
    light.color.setHex(0xffe8c4);
    light.shadow.normalBias = 0.028;
  }

  // setupMaterial installs its own onBeforeCompile, so anything that already
  // uses one — the shadow creatures' rim shader — is left alone. They read as
  // near-black silhouettes anyway, so they lose nothing visible.
  const seen = new Set();
  scene.traverse((o) => {
    const mats = Array.isArray(o.material) ? o.material : [o.material];
    for (const m of mats) {
      if (!m || seen.has(m) || !m.isMeshStandardMaterial || m.onBeforeCompile) continue;
      seen.add(m);
      csm.setupMaterial(m);
    }
  });
}

// ============================================================
// Post-processing
// ============================================================
const gradeShader = {
  uniforms: {
    tDiffuse: { value: null },
    uTime: { value: 0 },
    uAberration: { value: 0.0008 },
    uTexel: { value: new THREE.Vector2(1 / 1920, 1 / 1080) },
  },
  vertexShader: `
    varying vec2 vUv;
    void main() { vUv = uv; gl_Position = projectionMatrix * modelViewMatrix * vec4(position, 1.0); }`,
  fragmentShader: `
    uniform sampler2D tDiffuse;
    uniform float uTime;
    uniform float uAberration;
    uniform vec2 uTexel;
    varying vec2 vUv;
    float hash(vec2 p) { return fract(sin(dot(p, vec2(12.9898, 78.233))) * 43758.5453); }
    void main() {
      vec2 d = vUv - 0.5;
      float r2 = dot(d, d);
      // lateral chromatic aberration, strongest toward the frame edge
      vec2 off = d * r2 * uAberration * 6.0;
      vec3 c;
      c.r = texture2D(tDiffuse, vUv + off).r;
      c.g = texture2D(tDiffuse, vUv).g;
      c.b = texture2D(tDiffuse, vUv - off).b;
      // unsharp mask: antialiasing costs micro-contrast, this buys it back
      vec3 blur = (
        texture2D(tDiffuse, vUv + vec2( uTexel.x, 0.0)).rgb +
        texture2D(tDiffuse, vUv + vec2(-uTexel.x, 0.0)).rgb +
        texture2D(tDiffuse, vUv + vec2(0.0,  uTexel.y)).rgb +
        texture2D(tDiffuse, vUv + vec2(0.0, -uTexel.y)).rgb) * 0.25;
      c += (c - blur) * 0.26;
      // dusty warm grade, slight desaturation, gentle S-curve
      float l = dot(c, vec3(0.2126, 0.7152, 0.0722));
      c = mix(vec3(l), c, 0.92);
      c *= vec3(1.035, 1.0, 0.945);
      c = (c - 0.5) * 1.2 + 0.5;
      c += vec3(0.014, 0.010, 0.004);
      // vignette
      c *= 0.66 + 0.34 * smoothstep(0.86, 0.16, sqrt(r2));
      // film grain, coarser in the shadows the way real stock behaves
      float g = hash(vUv * 1024.0 + fract(uTime) * 91.0) - 0.5;
      c += g * (0.030 + 0.026 * (1.0 - l));
      gl_FragColor = vec4(c, 1.0);
    }`,
};

let composer, gtao, gradePass;
function setupPost() {
  composer = new EffectComposer(renderer);
  composer.setSize(innerWidth, innerHeight);
  composer.addPass(new RenderPass(scene, camera));

  gtao = new GTAOPass(scene, aoCamera, innerWidth, innerHeight);
  gtao.output = GTAOPass.OUTPUT.Default;
  gtao.updateGtaoMaterial({
    radius: 0.42, distanceExponent: 1.4, thickness: 1.0,
    scale: 1.1, samples: 16, screenSpaceRadius: false,
  });
  composer.addPass(gtao);

  const bloom = new UnrealBloomPass(new THREE.Vector2(innerWidth, innerHeight), 0.24, 0.62, 0.94);
  composer.addPass(bloom);

  composer.addPass(new OutputPass());

  gradePass = new ShaderPass(gradeShader);
  gradePass.uniforms.uTexel.value.set(1 / innerWidth, 1 / innerHeight);
  composer.addPass(gradePass);

  composer.addPass(new SMAAPass(innerWidth, innerHeight));
}

addEventListener('resize', () => {
  camera.aspect = innerWidth / innerHeight;
  camera.updateProjectionMatrix();
  renderer.setSize(innerWidth, innerHeight);
  composer?.setSize(innerWidth, innerHeight);
  gtao?.setSize(innerWidth, innerHeight);
  csm?.updateFrustums();
  gradePass?.uniforms.uTexel.value.set(1 / innerWidth, 1 / innerHeight);
});

// ============================================================
// Frame
// ============================================================
// THREE.Clock is deprecated in this three version, and the loop only needs a
// clamped delta and a running total.
let prevTime = performance.now() / 1000;
let elapsed = 0;
const fwd = new THREE.Vector3(), right = new THREE.Vector3(), move = new THREE.Vector3();
const camDir = new THREE.Vector3(), camOff = new THREE.Vector3();
const camRay = new THREE.Raycaster();
camRay.layers.set(0);
let solids = [];

function frame() {
  requestAnimationFrame(frame);
  const now = performance.now() / 1000;
  const dt = Math.min(now - prevTime, 0.05);
  prevTime = now;
  elapsed += dt;
  const t = elapsed;
  gradePass.uniforms.uTime.value = t;

  aoCamera.position.copy(camera.position);
  aoCamera.quaternion.copy(camera.quaternion);
  aoCamera.fov = camera.fov;
  aoCamera.aspect = camera.aspect;
  aoCamera.updateProjectionMatrix();
  aoCamera.updateMatrixWorld();

  // --- ambient life, runs behind the menus too ---
  for (const sp of smokeSprites) {
    sp.position.y += sp.userData.speed * dt;
    sp.material.rotation += sp.userData.spin * dt;
    const rise = sp.position.y - sp.userData.baseY;
    if (rise > 22) sp.position.y = sp.userData.baseY;
    sp.material.opacity = 0.5 * Math.max(0, 1 - rise / 22);
  }
  for (const sp of hazeSprites) {
    sp.position.x += sp.userData.drift * dt;
    if (sp.position.x > 17) sp.position.x = -17;
  }

  if (S.running && !S.over) {
    // ---- look & move ----
    const sprint = (S.keys.ShiftLeft || S.keys.ShiftRight) && !S.aiming;
    const speed = S.aiming ? 2.4 : (sprint ? 7.0 : 4.1);
    fwd.set(-Math.sin(S.yaw), 0, -Math.cos(S.yaw));
    right.set(-fwd.z, 0, fwd.x);
    move.set(0, 0, 0);
    if (S.keys.KeyW) move.add(fwd);
    if (S.keys.KeyS) move.sub(fwd);
    if (S.keys.KeyD) move.add(right);
    if (S.keys.KeyA) move.sub(right);
    const walking = move.lengthSq() > 0;
    if (walking) {
      move.normalize().multiplyScalar(speed * dt);
      player.add(move);
      collide(player);
      S.bob += dt * (sprint ? 10.5 : 7.2);
    }

    S.shake = Math.max(0, S.shake - dt * 4.2);
    const bobY = Math.sin(S.bob * 2) * 0.022 * (walking ? 1 : 0);
    const breathe = Math.sin(t * 1.3) * 0.0022;
    S.aimBlend += ((S.aiming ? 1 : 0) - S.aimBlend) * Math.min(1, dt * 12);
    S.recoil = Math.max(0, S.recoil - dt * 7.5);
    S.kick = Math.max(0, S.kick - dt * 9);

    // ---- camera rig ----
    eye.set(player.x, EYE_HEIGHT + bobY, player.z);
    camera.rotation.set(
      S.pitch + (rng() - 0.5) * 0.005 * S.shake + breathe - S.kick * 0.045,
      S.yaw + (rng() - 0.5) * 0.005 * S.shake + Math.cos(S.bob) * 0.0016 * (walking ? 1 : 0),
      Math.sin(S.bob) * 0.005 * (walking ? 1 : 0),
      'YXZ');

    if (S.thirdPerson) {
      // over the officer's right shoulder, tucked in closer while aiming
      const back = THREE.MathUtils.lerp(2.35, 1.55, S.aimBlend);
      const side = THREE.MathUtils.lerp(0.52, 0.42, S.aimBlend);
      const lift = THREE.MathUtils.lerp(0.14, 0.1, S.aimBlend);
      camDir.set(0, 0, 1).applyQuaternion(camera.quaternion);
      camOff.copy(right).multiplyScalar(side).addScaledVector(camDir, back);
      camOff.y += lift;
      // never let a wall end up between the camera and the officer
      const len = camOff.length();
      camRay.set(eye, camOff.clone().normalize());
      camRay.far = len;
      const blocked = camRay.intersectObjects(solids, false)[0];
      const dist = blocked ? Math.max(0.5, blocked.distance - 0.25) : len;
      S.camDist += (dist - S.camDist) * Math.min(1, dt * 14);
      camera.position.copy(eye).addScaledVector(camOff.normalize(), S.camDist);
    } else {
      camera.position.copy(eye);
    }

    // ---- weapon pose ----
    const target = REST.clone().lerp(AIM, S.aimBlend);
    viewRifle.position.set(
      target.x + Math.sin(S.bob) * 0.005 * (walking ? 1 : 0) * (1 - S.aimBlend),
      target.y + bobY * 0.5 - (S.reloading ? 0.11 : 0),
      target.z + S.recoil * 0.055);
    viewRifle.rotation.set(
      S.recoil * 0.1 - (S.reloading ? 0.45 : 0),
      -0.02 * (1 - S.aimBlend),
      (S.reloading ? 0.3 : 0) + Math.sin(S.bob * 0.5) * 0.008 * (walking ? 1 : 0));
    camera.fov = THREE.MathUtils.lerp(68, 50, S.aimBlend);
    camera.updateProjectionMatrix();

    // ---- the officer ----
    officer.position.set(player.x, 0, player.z);
    officer.rotation.y = S.yaw;
    poseOfficer(officer, {
      dt, moving: walking, sprinting: sprint, aiming: S.aiming,
      pitch: S.pitch, recoil: S.recoil,
    });

    muzzle.material.opacity = Math.max(0, muzzle.material.opacity - dt * 15);
    muzzleLight.intensity = Math.max(0, muzzleLight.intensity - dt * 260);

    // ---- fire & reload ----
    S.fireT -= dt;
    if (S.firing && !S.reloading && S.fireT <= 0) {
      shoot();
      S.fireT = FIRE_INTERVAL;
    }
    if (S.reloading) {
      S.reloadT -= dt;
      if (S.reloadT <= 0) {
        const take = Math.min(MAG_SIZE - S.ammo, S.reserve);
        S.ammo += take;
        S.reserve -= take;
        S.reloading = false;
        click(520);
        syncHUD();
      }
    }

    // ---- waves ----
    if (S.pending > 0) {
      S.spawnT -= dt;
      if (S.spawnT <= 0 && enemies.length < 9) {
        spawnEnemy();
        S.pending--;
        S.spawnT = 1.1 + rng() * 1.3;
      }
    } else if (S.pending === 0 && enemies.length === 0) {
      S.pending = -1;
      S.reserve += 30;
      banner('구역 확보');
      syncHUD();
      setTimeout(() => { if (!S.over) nextWave(); }, 2300);
    }

    collectPickups(dt);

    // ---- enemies ----
    for (const e of [...enemies]) {
      const u = e.userData;
      if (u.state === 'dying') {
        u.dieT -= dt;
        e.scale.y = Math.max(0.04, e.scale.y - dt * 1.5);
        e.position.y -= dt * 0.75;
        u.eyeMat.emissiveIntensity = Math.max(0, u.eyeMat.emissiveIntensity - dt * 6);
        if (rng() < 0.55) {
          v3.copy(e.position); v3.y += 1;
          burst(v3, 0x1c1428, 5, 2.4, 0.05);
          shedWisp(v3, 1.15);
        }
        if (u.dieT <= 0) dropEnemy(e);
        continue;
      }

      u.mat.color.setHex(u.hitT > 0 ? 0x4d3070 : 0x07070a);
      if (u.hitT > 0) u.hitT -= dt;

      u.wispT -= dt;
      if (u.wispT <= 0) {
        u.wispT = 0.16 + rng() * 0.12;
        v3.copy(e.position);
        v3.y = 0.5 + rng() * 1.7;
        shedWisp(v3, 0.45 + rng() * 0.5);
      }

      v3.copy(player).sub(e.position);
      v3.y = 0;
      const dist = v3.length();
      e.lookAt(player.x, e.position.y, player.z);

      if (dist > 1.55) {
        e.position.addScaledVector(v3.normalize(), u.speed * dt);
        u.phase += dt * u.speed * 3.1;
        const s = Math.sin(u.phase);
        u.armL.rotation.x = s * 0.72;
        u.armR.rotation.x = -s * 0.72;
        u.armL.userData.lower.rotation.x = -0.35 - Math.max(0, s) * 0.5;
        u.armR.userData.lower.rotation.x = -0.35 - Math.max(0, -s) * 0.5;
        u.legL.rotation.x = -s * 0.62;
        u.legR.rotation.x = s * 0.62;
        u.legL.userData.lower.rotation.x = Math.max(0, s) * 0.85;
        u.legR.userData.lower.rotation.x = Math.max(0, -s) * 0.85;
      } else {
        u.armL.rotation.x = -1.9;
        u.armR.rotation.x = -1.9;
        u.armL.userData.lower.rotation.x = -0.6;
        u.armR.userData.lower.rotation.x = -0.6;
        u.attackCooldown -= dt;
        if (u.attackCooldown <= 0) {
          u.attackCooldown = 1.0;
          S.hp -= u.brute ? 22 : 12;
          growl();
          ui.damage.style.opacity = 1;
          setTimeout(() => { ui.damage.style.opacity = 0; }, 340);
          S.shake = 1.3;
          syncHUD();
          if (S.hp <= 0) gameOver();
        }
      }
    }
  }

  // ---- transient effects ----
  for (const sp of [...wisps]) {
    sp.userData.life -= dt;
    sp.position.y += sp.userData.vy * dt;
    sp.scale.multiplyScalar(1 + dt * 0.85);
    sp.material.opacity = 0.5 * Math.max(0, sp.userData.life);
    if (sp.userData.life <= 0) { scene.remove(sp); wisps.splice(wisps.indexOf(sp), 1); }
  }
  for (const p of [...sparks]) {
    p.userData.life -= dt;
    const arr = p.geometry.attributes.position.array;
    p.userData.vel.forEach((v, i) => {
      arr[i * 3] += v.x * dt; arr[i * 3 + 1] += v.y * dt; arr[i * 3 + 2] += v.z * dt;
      v.y -= 6.5 * dt;
    });
    p.geometry.attributes.position.needsUpdate = true;
    p.material.opacity = Math.max(0, p.userData.life / 0.55);
    if (p.userData.life <= 0) { scene.remove(p); sparks.splice(sparks.indexOf(p), 1); }
  }
  for (const l of [...tracers]) {
    l.userData.life -= dt;
    l.material.opacity = Math.max(0, l.userData.life / 0.06) * 0.85;
    if (l.userData.life <= 0) { scene.remove(l); tracers.splice(tracers.indexOf(l), 1); }
  }

  // the cascades re-fit themselves to the camera every frame
  csm?.update();

  composer.render();
}

// ============================================================
// Boot
// ============================================================
let sunDir = new THREE.Vector3();

const yield_ = () => new Promise((r) => requestAnimationFrame(() => setTimeout(r, 0)));

async function boot() {
  const steps = [
    ['하늘과 빛', () => { sunDir = setupSky(scene, renderer).sunDir; }],
    ['거리 재질', () => { window.__lib = buildMaterials(); }],
    ['건물과 잔해', () => {
      const r = buildStreet(scene, window.__lib);
      obstacles = r.obstacles;
      r.root.traverse((o) => { if (o.isMesh && !o.isInstancedMesh) solids.push(o); });
    }],
    ['먼지와 연기', () => { buildAtmosphere(); }],
    ['그림자 캐스케이드', () => { setupShadows(); }],
    ['후처리', () => { setupPost(); drawGunIcon(); applyView(); }],
  ];
  ui.loading.querySelector('.t').textContent = '표면 디테일';
  await yield_();
  setDetailNormals(await loadDetailNormals());

  ui.loading.querySelector('.t').textContent = '스캔 데이터';
  await yield_();
  attachScannedHead(officer, await loadScannedHead());

  for (let i = 0; i < steps.length; i++) {
    ui.loading.querySelector('.t').textContent = steps[i][0];
    ui.loadFill.style.width = `${(i / steps.length) * 100}%`;
    await yield_();
    steps[i][1]();
  }
  ui.loadFill.style.width = '100%';
  await yield_();
  ui.loading.remove();
  ui.start.hidden = false;
  S.ready = true;
  syncHUD();
  frame();
}

boot();
