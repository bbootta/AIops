import * as THREE from 'three';
import { RoundedBoxGeometry } from 'three/addons/geometries/RoundedBoxGeometry.js';
import { makeCanvas, makeRng, noiseOverlay, texture, grit } from './tex.js';

// ============================================================
// The shadow creature
// ============================================================

// Near-black skin that still catches a rim of sky light along its edges,
// so the silhouette reads against the hazy street instead of going flat.
function shadowSkin() {
  const mat = new THREE.MeshStandardMaterial({
    color: 0x07070a, roughness: 0.52, metalness: 0.0,
  });
  mat.onBeforeCompile = (shader) => {
    shader.uniforms.uRim = { value: new THREE.Color(0x6b5f8a) };
    shader.fragmentShader = shader.fragmentShader
      .replace('#include <common>', `#include <common>\n uniform vec3 uRim;`)
      .replace('#include <dithering_fragment>', `#include <dithering_fragment>
        float rim = 1.0 - max(dot(normalize(vNormal), normalize(vViewPosition)), 0.0);
        gl_FragColor.rgb += uRim * pow(rim, 3.2) * 0.55;`);
    mat.userData.shader = shader;
  };
  return mat;
}

function limb(mat, upperLen, lowerLen, r, isLeg) {
  const pivot = new THREE.Group();
  const upper = new THREE.Mesh(new THREE.CapsuleGeometry(r, upperLen, 4, 10), mat);
  upper.position.y = -upperLen / 2;
  const lower = new THREE.Group();
  lower.position.y = -upperLen - r * 0.2;
  const seg = new THREE.Mesh(new THREE.CapsuleGeometry(r * 0.82, lowerLen, 4, 10), mat);
  seg.position.y = -lowerLen / 2;
  lower.add(seg);
  if (isLeg) {
    const foot = new THREE.Mesh(new RoundedBoxGeometry(r * 2.0, r * 1.2, lowerLen * 0.6, 2, 0.02), mat);
    foot.position.set(0, -lowerLen - r * 0.5, lowerLen * 0.2);
    lower.add(foot);
  } else {
    const palm = new THREE.Mesh(new RoundedBoxGeometry(r * 1.9, r * 2.1, r * 1.0, 2, 0.02), mat);
    palm.position.y = -lowerLen - r * 0.9;
    lower.add(palm);
    for (let f = -1; f <= 1; f++) {
      const claw = new THREE.Mesh(new THREE.ConeGeometry(r * 0.3, lowerLen * 0.42, 5), mat);
      claw.position.set(f * r * 0.6, -lowerLen - r * 2.2, r * 0.15);
      claw.rotation.x = Math.PI;
      lower.add(claw);
    }
  }
  pivot.add(upper, lower);
  pivot.userData.lower = lower;
  return pivot;
}

export function makeShadowCreature(rng) {
  const g = new THREE.Group();
  const mat = shadowSkin();

  const pelvis = new THREE.Mesh(new THREE.CapsuleGeometry(0.15, 0.14, 3, 10), mat);
  pelvis.position.y = 1.12;
  const waist = new THREE.Mesh(new THREE.CapsuleGeometry(0.145, 0.26, 3, 10), mat);
  waist.position.set(0, 1.38, 0.01);
  const chest = new THREE.Mesh(new THREE.CapsuleGeometry(0.2, 0.3, 4, 12), mat);
  chest.position.set(0, 1.66, 0.02);
  chest.rotation.x = 0.14;
  const clav = new THREE.Mesh(new RoundedBoxGeometry(0.5, 0.13, 0.2, 2, 0.05), mat);
  clav.position.set(0, 1.84, 0.02);
  const neck = new THREE.Mesh(new THREE.CapsuleGeometry(0.055, 0.1, 3, 8), mat);
  neck.position.set(0, 1.95, 0.035);

  const head = new THREE.Mesh(new THREE.SphereGeometry(0.135, 16, 14), mat);
  head.position.set(0, 2.09, 0.055);
  head.scale.set(0.9, 1.18, 1.0);
  head.rotation.x = -0.18;

  // sunken glowing eyes
  const eyeMat = new THREE.MeshStandardMaterial({
    color: 0x000000, emissive: 0x9fd94a, emissiveIntensity: 3.4, roughness: 1,
  });
  const eyes = new THREE.Group();
  for (const ex of [-0.052, 0.052]) {
    const eye = new THREE.Mesh(new THREE.SphereGeometry(0.021, 8, 8), eyeMat);
    eye.position.set(ex, 2.11, 0.16);
    eyes.add(eye);
  }

  // matted hair, fanning back off the skull
  const hair = new THREE.Group();
  for (let i = 0; i < 16; i++) {
    const len = 0.14 + rng() * 0.22;
    const spike = new THREE.Mesh(new THREE.ConeGeometry(0.022 + rng() * 0.016, len, 5), mat);
    const a = rng() * Math.PI * 2;
    const rad = 0.05 + rng() * 0.07;
    spike.position.set(Math.cos(a) * rad, 2.15 + rng() * 0.04, 0.05 + Math.sin(a) * rad * 0.9);
    spike.rotation.set(-0.4 - rng() * 0.8 + Math.sin(a) * 0.4, rng() * 0.5, Math.cos(a) * 0.8);
    hair.add(spike);
  }

  const armL = limb(mat, 0.5, 0.46, 0.062, false);
  armL.position.set(-0.26, 1.83, 0.02);
  armL.rotation.z = 0.14;
  const armR = limb(mat, 0.5, 0.46, 0.062, false);
  armR.position.set(0.26, 1.83, 0.02);
  armR.rotation.z = -0.14;
  const legL = limb(mat, 0.55, 0.52, 0.082, true);
  legL.position.set(-0.115, 1.1, 0);
  const legR = limb(mat, 0.55, 0.52, 0.082, true);
  legR.position.set(0.115, 1.1, 0);

  g.add(pelvis, waist, chest, clav, neck, head, eyes, hair, armL, armR, legL, legR);
  g.traverse((m) => { if (m.isMesh) { m.castShadow = true; m.userData.enemy = g; } });
  head.userData.headshot = true;

  g.userData = {
    mat, eyeMat, armL, armR, legL, legR,
    hp: 3, speed: 0, phase: rng() * Math.PI * 2,
    state: 'walk', attackCooldown: 0, dieT: 0, hitT: 0, wispT: 0,
  };
  return g;
}

// ============================================================
// The rifle, plus the hands holding it
// ============================================================
export function makeRifle() {
  const g = new THREE.Group();

  // Parkerised steel is a dark matte grey; keep metalness moderate or the
  // bright sky reflection turns the whole rifle silver.
  const gunmetal = new THREE.MeshStandardMaterial({
    color: 0x181a1d, roughness: 0.52, metalness: 0.7,
  });
  const parkerized = new THREE.MeshStandardMaterial({
    color: 0x121417, roughness: 0.64, metalness: 0.6,
  });
  const polymer = new THREE.MeshStandardMaterial({
    color: 0x0e1013, roughness: 0.78, metalness: 0.0,
  });

  // worn leather glove for the hands
  const gloveTex = texture(makeCanvas(256, 256, (ctx, w, h) => {
    const r = makeRng(9);
    ctx.fillStyle = '#2a221c'; ctx.fillRect(0, 0, w, h);
    noiseOverlay(ctx, w, h, { seed: 3, grid: 6, octaves: 4, color: [92, 74, 58], alpha: 0.5 });
    noiseOverlay(ctx, w, h, { seed: 8, grid: 24, octaves: 3, color: [14, 11, 9], alpha: 0.45 });
    grit(ctx, w, h, 3000, r, 0.3, 0.12);
  }), { srgb: true });
  const glove = new THREE.MeshStandardMaterial({ map: gloveTex, roughness: 0.78, metalness: 0.03 });

  // --- receiver group ---
  const upper = new THREE.Mesh(new RoundedBoxGeometry(0.064, 0.078, 0.34, 3, 0.012), gunmetal);
  upper.position.set(0, 0.012, -0.02);
  const lower = new THREE.Mesh(new RoundedBoxGeometry(0.06, 0.07, 0.24, 3, 0.012), gunmetal);
  lower.position.set(0, -0.052, 0.03);
  // carry handle
  const hRail = new THREE.Mesh(new RoundedBoxGeometry(0.052, 0.022, 0.22, 2, 0.008), gunmetal);
  hRail.position.set(0, 0.088, -0.02);
  for (const hz of [-0.1, 0.08]) {
    const post = new THREE.Mesh(new THREE.BoxGeometry(0.05, 0.042, 0.016), gunmetal);
    post.position.set(0, 0.058, hz);
    g.add(post);
  }
  const rearAperture = new THREE.Mesh(new THREE.TorusGeometry(0.012, 0.005, 6, 12), gunmetal);
  rearAperture.position.set(0, 0.086, 0.07);
  rearAperture.rotation.y = Math.PI / 2;
  // ejection port + forward assist
  const port = new THREE.Mesh(new THREE.BoxGeometry(0.008, 0.03, 0.08), parkerized);
  port.position.set(0.034, 0.016, -0.03);
  const assist = new THREE.Mesh(new THREE.CylinderGeometry(0.012, 0.012, 0.03, 8), gunmetal);
  assist.rotation.z = Math.PI / 2;
  assist.position.set(0.04, 0.042, 0.04);

  // --- handguard: tapered triangular polymer ---
  const hg = new THREE.Mesh(new THREE.CylinderGeometry(0.034, 0.044, 0.3, 3, 1), polymer);
  hg.rotation.set(Math.PI / 2, 0, Math.PI);
  hg.position.set(0, 0.004, -0.33);
  const hgRing = new THREE.Mesh(new THREE.CylinderGeometry(0.042, 0.042, 0.026, 12), gunmetal);
  hgRing.rotation.x = Math.PI / 2;
  hgRing.position.set(0, 0.008, -0.185);

  // --- barrel, front sight, flash hider ---
  const barrel = new THREE.Mesh(new THREE.CylinderGeometry(0.0125, 0.0135, 0.3, 12), parkerized);
  barrel.rotation.x = Math.PI / 2;
  barrel.position.set(0, 0.01, -0.58);
  const fsBase = new THREE.Mesh(new THREE.CylinderGeometry(0.026, 0.03, 0.05, 8), gunmetal);
  fsBase.position.set(0, 0.032, -0.49);
  const fsWings = new THREE.Mesh(new THREE.BoxGeometry(0.03, 0.055, 0.014), gunmetal);
  fsWings.position.set(0, 0.062, -0.49);
  const gasBlock = new THREE.Mesh(new THREE.CylinderGeometry(0.011, 0.011, 0.14, 8), parkerized);
  gasBlock.rotation.x = Math.PI / 2;
  gasBlock.position.set(0, 0.032, -0.4);
  const hider = new THREE.Mesh(new THREE.CylinderGeometry(0.019, 0.016, 0.075, 12), parkerized);
  hider.rotation.x = Math.PI / 2;
  hider.position.set(0, 0.01, -0.75);
  for (let i = 0; i < 4; i++) {
    const slot = new THREE.Mesh(new THREE.BoxGeometry(0.042, 0.005, 0.03), polymer);
    slot.position.set(0, 0.01, -0.75);
    slot.rotation.z = (i / 4) * Math.PI;
    g.add(slot);
  }

  // --- magazine, grip, stock ---
  const mag = new THREE.Mesh(new RoundedBoxGeometry(0.05, 0.19, 0.078, 3, 0.01), parkerized);
  mag.position.set(0, -0.16, -0.055);
  mag.rotation.x = 0.2;
  const magWell = new THREE.Mesh(new RoundedBoxGeometry(0.058, 0.06, 0.088, 2, 0.01), gunmetal);
  magWell.position.set(0, -0.075, -0.045);
  const grip = new THREE.Mesh(new RoundedBoxGeometry(0.042, 0.125, 0.055, 3, 0.014), polymer);
  grip.position.set(0, -0.115, 0.098);
  grip.rotation.x = 0.36;
  const trigger = new THREE.Mesh(new THREE.BoxGeometry(0.01, 0.032, 0.012), gunmetal);
  trigger.position.set(0, -0.075, 0.055);
  const guard = new THREE.Mesh(new THREE.TorusGeometry(0.03, 0.006, 6, 12, Math.PI), gunmetal);
  guard.position.set(0, -0.078, 0.055);
  guard.rotation.set(Math.PI / 2, 0, 0);
  const stock = new THREE.Mesh(new RoundedBoxGeometry(0.056, 0.082, 0.3, 3, 0.02), polymer);
  stock.position.set(0, -0.026, 0.29);
  stock.rotation.x = 0.05;
  const butt = new THREE.Mesh(new RoundedBoxGeometry(0.058, 0.115, 0.024, 3, 0.008), polymer);
  butt.position.set(0, -0.042, 0.44);

  g.add(upper, lower, hRail, rearAperture, port, assist, hg, hgRing, barrel,
        fsBase, fsWings, gasBlock, hider, mag, magWell, grip, trigger, guard, stock, butt);

  // --- hands ---
  const handR = new THREE.Group();
  const foreR = new THREE.Mesh(new THREE.CapsuleGeometry(0.045, 0.2, 4, 10), glove);
  foreR.position.set(0.01, -0.2, 0.24);
  foreR.rotation.set(-0.5, 0, 0.1);
  const palmR = new THREE.Mesh(new RoundedBoxGeometry(0.052, 0.085, 0.075, 3, 0.02), glove);
  palmR.position.set(0.004, -0.128, 0.108);
  palmR.rotation.x = 0.36;
  handR.add(foreR, palmR);
  for (let i = 0; i < 4; i++) {
    const fing = new THREE.Mesh(new THREE.CapsuleGeometry(0.011, 0.05, 3, 8), glove);
    fing.position.set(-0.026, -0.108 + i * 0.004, 0.075 + i * 0.018);
    fing.rotation.set(1.35, 0, 0);
    handR.add(fing);
  }

  const handL = new THREE.Group();
  const foreL = new THREE.Mesh(new THREE.CapsuleGeometry(0.045, 0.22, 4, 10), glove);
  foreL.position.set(-0.15, -0.17, -0.2);
  foreL.rotation.set(-1.1, 0, -0.55);
  const palmL = new THREE.Mesh(new RoundedBoxGeometry(0.05, 0.08, 0.09, 3, 0.02), glove);
  palmL.position.set(-0.052, -0.062, -0.322);
  palmL.rotation.set(0.2, 0, -0.5);
  handL.add(foreL, palmL);
  for (let i = 0; i < 4; i++) {
    const fing = new THREE.Mesh(new THREE.CapsuleGeometry(0.011, 0.055, 3, 8), glove);
    fing.position.set(-0.022 + i * 0.002, -0.03 - i * 0.001, -0.35 + i * 0.024);
    fing.rotation.set(0.1, 0, -1.45);
    handL.add(fing);
  }
  g.add(handR, handL);

  g.traverse((m) => { if (m.isMesh) { m.castShadow = false; m.receiveShadow = false; } });
  return g;
}
