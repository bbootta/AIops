import * as THREE from 'three';
import { RoundedBoxGeometry } from 'three/addons/geometries/RoundedBoxGeometry.js';
import { makeCanvas, makeRng, noiseOverlay, texture, heightToNormal, detailNormal,
         grit, streaks, blob } from './tex.js';

// ============================================================
// The player: a riot-police officer in a worn leather jacket, built to
// match the costume and build in the film still rather than any real
// person's face. Assembled from primitives, rigged as nested groups so the
// spine can follow the aim while the legs run their own walk cycle.
// ============================================================

function leatherMaterial() {
  const rng = makeRng(401);
  const paint = (ctx, w, h, mode) => {
    if (mode === 'h') {
      ctx.fillStyle = '#808080';
      ctx.fillRect(0, 0, w, h);
      // creases fanning from the elbows and waist
      noiseOverlay(ctx, w, h, { seed: 12, grid: 7, octaves: 4, color: [255, 255, 255], alpha: 0.5 });
      noiseOverlay(ctx, w, h, { seed: 19, grid: 34, octaves: 3, color: [0, 0, 0], alpha: 0.45 });
      return;
    }
    ctx.fillStyle = '#2b211a';
    ctx.fillRect(0, 0, w, h);
    noiseOverlay(ctx, w, h, { seed: 12, grid: 7, octaves: 4, color: [92, 72, 54], alpha: 0.55 });
    noiseOverlay(ctx, w, h, { seed: 19, grid: 34, octaves: 3, color: [12, 9, 7], alpha: 0.5 });
    // rubbed-through highlights on the wear points
    for (let i = 0; i < 26; i++) {
      blob(ctx, rng() * w, rng() * h, 6 + rng() * 26, rng, `rgba(126,101,74,${0.12 + rng() * 0.22})`);
    }
    grit(ctx, w, h, 4000, rng, 0.22, 0.16);
  };
  return {
    map: texture(makeCanvas(512, 512, (c, w, h) => paint(c, w, h, 'a')), { srgb: true }),
    height: makeCanvas(512, 512, (c, w, h) => paint(c, w, h, 'h')),
    // creased leather is polished where it rubs and matte in the folds
    rough: texture(makeCanvas(512, 512, (ctx, w, h) => {
      const r2 = makeRng(402);
      ctx.fillStyle = '#b4b4b4';
      ctx.fillRect(0, 0, w, h);
      noiseOverlay(ctx, w, h, { seed: 19, grid: 34, octaves: 3, color: [230, 230, 230], alpha: 0.5 });
      for (let i = 0; i < 26; i++) {
        blob(ctx, r2() * w, r2() * h, 6 + r2() * 26, r2, `rgba(70,70,70,${0.3 + r2() * 0.4})`);
      }
    })),
  };
}

function fabricMaterial(hex, seed) {
  const rng = makeRng(seed);
  return new THREE.MeshStandardMaterial({
    color: hex,
    roughness: 0.94,
    metalness: 0,
    map: texture(makeCanvas(256, 256, (ctx, w, h) => {
      ctx.fillStyle = '#ffffff';
      ctx.fillRect(0, 0, w, h);
      // a coarse weave, so the cloth doesn't read as flat plastic
      ctx.strokeStyle = 'rgba(0,0,0,0.14)';
      ctx.lineWidth = 1;
      for (let x = 0; x < w; x += 3) {
        ctx.beginPath(); ctx.moveTo(x, 0); ctx.lineTo(x, h); ctx.stroke();
      }
      for (let y = 0; y < h; y += 3) {
        ctx.beginPath(); ctx.moveTo(0, y); ctx.lineTo(w, y); ctx.stroke();
      }
      noiseOverlay(ctx, w, h, { seed, grid: 6, octaves: 4, color: [40, 36, 30], alpha: 0.35 });
      streaks(ctx, 0, 0, w, h, rng, { alpha: 0.16, count: 8 });
      grit(ctx, w, h, 2500, rng, 0.2, 0.1);
    }), { srgb: true, repeat: [2, 2] }),
  });
}

/** The gold shoulder emblem, painted as its own little decal. */
function patchMaterial() {
  return new THREE.MeshStandardMaterial({
    roughness: 0.62,
    metalness: 0.15,
    map: texture(makeCanvas(128, 128, (ctx, w, h) => {
      ctx.fillStyle = '#1d2432';
      ctx.fillRect(0, 0, w, h);
      ctx.strokeStyle = '#c8a63f';
      ctx.lineWidth = 5;
      ctx.strokeRect(6, 6, w - 12, h - 12);
      // a laurel-and-star emblem, readable at a glance from behind
      ctx.fillStyle = '#d3ab52';
      ctx.beginPath();
      for (let i = 0; i < 10; i++) {
        const a = (i / 10) * Math.PI * 2 - Math.PI / 2;
        const r = i % 2 === 0 ? 34 : 15;
        const fn = i === 0 ? 'moveTo' : 'lineTo';
        ctx[fn](w / 2 + Math.cos(a) * r, h / 2 - 8 + Math.sin(a) * r);
      }
      ctx.closePath();
      ctx.fill();
      ctx.fillStyle = '#b8963f';
      ctx.fillRect(24, h - 34, w - 48, 9);
      noiseOverlay(ctx, w, h, { seed: 5, grid: 8, octaves: 3, color: [20, 16, 12], alpha: 0.4 });
    }), { srgb: true }),
  });
}

function jointedLimb(mat, upperLen, lowerLen, r, { boot = null, hand = null } = {}) {
  const pivot = new THREE.Group();
  const upper = new THREE.Mesh(new THREE.CapsuleGeometry(r, upperLen - r * 2, 4, 12), mat);
  upper.position.y = -upperLen / 2;
  const lower = new THREE.Group();
  lower.position.y = -upperLen;
  const seg = new THREE.Mesh(
    new THREE.CapsuleGeometry(r * 0.86, lowerLen - r * 1.7, 4, 12), mat);
  seg.position.y = -lowerLen / 2;
  lower.add(seg);
  if (boot) {
    const foot = new THREE.Mesh(new RoundedBoxGeometry(r * 2.1, r * 1.5, lowerLen * 0.66, 3, 0.02), boot);
    foot.position.set(0, -lowerLen - r * 0.5, lowerLen * 0.2);
    lower.add(foot);
  }
  if (hand) {
    const palm = new THREE.Mesh(new RoundedBoxGeometry(r * 1.7, r * 1.9, r * 1.05, 3, 0.015), hand);
    palm.position.y = -lowerLen - r * 0.8;
    lower.add(palm);
    // curled fingers and an opposed thumb, so the grip reads as a hand
    for (let f = 0; f < 4; f++) {
      const finger = new THREE.Mesh(
        new THREE.CapsuleGeometry(r * 0.19, r * 0.62, 3, 8), hand);
      finger.position.set(r * (0.42 - f * 0.28), -lowerLen - r * 1.62, r * 0.16);
      finger.rotation.x = 1.25;
      lower.add(finger);
    }
    const thumb = new THREE.Mesh(new THREE.CapsuleGeometry(r * 0.22, r * 0.5, 3, 8), hand);
    thumb.position.set(r * 0.72, -lowerLen - r * 1.15, -r * 0.2);
    thumb.rotation.set(0.5, 0, -0.75);
    lower.add(thumb);
  }
  pivot.add(upper, lower);
  pivot.userData.lower = lower;
  pivot.userData.upperLen = upperLen;
  pivot.userData.lowerLen = lowerLen;
  return pivot;
}

export function makeOfficer() {
  const root = new THREE.Group();

  const lea = leatherMaterial();
  const leather = new THREE.MeshStandardMaterial({
    map: lea.map, roughness: 0.46, metalness: 0.04, color: 0xffffff,
    roughnessMap: lea.rough,
  });
  leather.normalMap = texture(detailNormal(heightToNormal(lea.height, 1.9), 3, 0.6));
  leather.normalScale.set(0.9, 0.9);

  const trousers = fabricMaterial(0x24262c, 71);
  const shirt = fabricMaterial(0x2c3340, 73);
  const boots = new THREE.MeshStandardMaterial({ color: 0x14120f, roughness: 0.55, metalness: 0.06 });
  const skin = new THREE.MeshStandardMaterial({ color: 0xa97d5f, roughness: 0.72 });
  const hairMat = new THREE.MeshStandardMaterial({ color: 0x100d0c, roughness: 0.66 });
  const patch = patchMaterial();

  // ---- lower body ----
  const hips = new THREE.Mesh(new THREE.CapsuleGeometry(0.16, 0.1, 4, 12), trousers);
  hips.position.y = 0.95;
  root.add(hips);

  // duty belt with a holster and a radio, the details that read from behind
  const belt = new THREE.Mesh(new THREE.TorusGeometry(0.172, 0.028, 8, 22), boots);
  belt.position.y = 1.0;
  belt.rotation.x = Math.PI / 2;
  const buckle = new THREE.Mesh(new RoundedBoxGeometry(0.07, 0.05, 0.02, 2, 0.008),
    new THREE.MeshStandardMaterial({ color: 0x9c8a5e, roughness: 0.42, metalness: 0.8 }));
  buckle.position.set(0, 1.0, -0.185);
  const holster = new THREE.Mesh(new RoundedBoxGeometry(0.1, 0.2, 0.07, 3, 0.02), boots);
  holster.position.set(0.185, 0.9, 0.03);
  holster.rotation.z = -0.12;
  const radio = new THREE.Mesh(new RoundedBoxGeometry(0.07, 0.13, 0.05, 3, 0.015), boots);
  radio.position.set(-0.175, 0.95, 0.04);
  const antenna = new THREE.Mesh(new THREE.CylinderGeometry(0.006, 0.005, 0.16, 5), boots);
  antenna.position.set(-0.175, 1.08, 0.04);
  root.add(belt, buckle, holster, radio, antenna);

  const legL = jointedLimb(trousers, 0.47, 0.45, 0.085, { boot: boots });
  legL.position.set(-0.105, 0.95, 0);
  const legR = jointedLimb(trousers, 0.47, 0.45, 0.085, { boot: boots });
  legR.position.set(0.105, 0.95, 0);
  root.add(legL, legR);

  // ---- spine: everything above the waist pitches with the aim ----
  const spine = new THREE.Group();
  spine.position.y = 1.02;
  root.add(spine);

  const torso = new THREE.Mesh(new THREE.CapsuleGeometry(0.148, 0.22, 4, 14), shirt);
  torso.position.y = 0.16;
  spine.add(torso);

  // the jacket: a slightly larger shell over the shirt, open at the hem
  const jacket = new THREE.Mesh(new THREE.CapsuleGeometry(0.176, 0.28, 4, 16), leather);
  jacket.position.y = 0.24;
  const skirt = new THREE.Mesh(new THREE.CylinderGeometry(0.184, 0.196, 0.17, 16, 1, true), leather);
  skirt.position.y = 0.05;
  skirt.material = leather;
  const collar = new THREE.Mesh(new THREE.TorusGeometry(0.1, 0.042, 8, 16), leather);
  collar.position.y = 0.46;
  collar.rotation.x = Math.PI / 2;
  spine.add(jacket, skirt, collar);

  const shoulders = new THREE.Mesh(new RoundedBoxGeometry(0.4, 0.14, 0.21, 3, 0.06), leather);
  shoulders.position.y = 0.42;
  spine.add(shoulders);

  // cuffs and a yoke seam across the back, which is the side the player sees
  for (const cx of [-0.185, 0.185]) {
    const cuffBand = new THREE.Mesh(new THREE.TorusGeometry(0.062, 0.014, 6, 14), leather);
    cuffBand.position.set(cx, 0.4, 0);
    cuffBand.rotation.x = Math.PI / 2;
    spine.add(cuffBand);
  }
  const yoke = new THREE.Mesh(new THREE.BoxGeometry(0.36, 0.014, 0.02), leather);
  yoke.position.set(0, 0.34, -0.166);
  spine.add(yoke);
  const waistband = new THREE.Mesh(new THREE.TorusGeometry(0.174, 0.024, 8, 20), leather);
  waistband.position.y = 0.04;
  waistband.rotation.x = Math.PI / 2;
  spine.add(waistband);

  // shoulder emblem, on the left arm as in the still
  const emblem = new THREE.Mesh(new THREE.PlaneGeometry(0.11, 0.13), patch);
  emblem.position.set(-0.178, 0.34, 0.02);
  emblem.rotation.y = -Math.PI / 2;
  spine.add(emblem);

  // ---- head ----
  const neck = new THREE.Mesh(new THREE.CapsuleGeometry(0.058, 0.07, 3, 10), skin);
  neck.position.y = 0.5;
  const head = new THREE.Mesh(new THREE.SphereGeometry(0.108, 20, 18), skin);
  head.position.set(0, 0.62, 0.006);
  head.scale.set(0.94, 1.12, 1.04);
  const jaw = new THREE.Mesh(new RoundedBoxGeometry(0.15, 0.1, 0.15, 3, 0.05), skin);
  jaw.position.set(0, 0.567, 0.016);
  // a brow ridge and nose, enough to break the silhouette of a bare sphere
  const brow = new THREE.Mesh(new RoundedBoxGeometry(0.15, 0.026, 0.05, 3, 0.012), skin);
  brow.position.set(0, 0.645, 0.086);
  brow.rotation.x = -0.16;
  const nose = new THREE.Mesh(new THREE.ConeGeometry(0.027, 0.062, 8), skin);
  nose.position.set(0, 0.607, 0.108);
  nose.rotation.x = Math.PI * 0.52;
  const ears = new THREE.Group();
  for (const ex of [-0.098, 0.098]) {
    const ear = new THREE.Mesh(new THREE.SphereGeometry(0.026, 8, 8), skin);
    ear.scale.set(0.5, 1, 0.8);
    ear.position.set(ex, 0.618, -0.004);
    ears.add(ear);
  }
  // thick, short hair: a skull cap plus a hairline sweep
  const hair = new THREE.Mesh(new THREE.SphereGeometry(0.117, 18, 16,
    0, Math.PI * 2, 0, Math.PI * 0.62), hairMat);
  hair.position.set(0, 0.622, 0.002);
  hair.scale.set(0.98, 1.06, 1.06);
  const nape = new THREE.Mesh(new THREE.SphereGeometry(0.106, 14, 12,
    0, Math.PI * 2, Math.PI * 0.4, Math.PI * 0.35), hairMat);
  nape.position.set(0, 0.622, -0.028);
  nape.scale.set(1, 1.05, 0.9);
  // The procedural head is a stand-in: it renders immediately, then the
  // scanned head swaps in once its mesh has decoded.
  const headSocket = new THREE.Group();
  headSocket.userData.hairMat = hairMat;
  headSocket.add(head, jaw, brow, nose, ears, hair, nape);
  spine.add(neck, headSocket);

  // ---- arms ----
  const armL = jointedLimb(leather, 0.3, 0.28, 0.062, { hand: skin });
  armL.position.set(-0.185, 0.4, 0);
  const armR = jointedLimb(leather, 0.3, 0.28, 0.062, { hand: skin });
  armR.position.set(0.185, 0.4, 0);
  spine.add(armL, armR);

  // where the rifle rides — parented to the spine so it tracks the aim.
  // Forward is -Z, so the grip has to sit in front of the chest or the
  // rifle ends up buried inside the jacket.
  const grip = new THREE.Group();
  grip.position.set(0.13, 0.31, -0.2);
  spine.add(grip);

  root.traverse((m) => {
    if (m.isMesh) { m.castShadow = true; m.receiveShadow = true; }
  });

  root.userData = { spine, legL, legR, armL, armR, grip, headSocket, phase: 0 };
  return root;
}

/**
 * Swaps the placeholder head for the photogrammetry scan.
 * The scan is normalised and centred on its own origin, so it only needs
 * placing at the neck and turning to face the officer's forward, which is -Z.
 */
export function attachScannedHead(officer, mesh) {
  const socket = officer.userData.headSocket;
  const hairMat = socket.userData.hairMat;
  socket.clear();
  mesh.position.set(0, 0.63, 0.012);
  mesh.rotation.y = Math.PI;
  socket.add(mesh);

  // The scan is a bare head, so the hair is still ours. It has to wrap the
  // skull down past the ears — a hemisphere sitting on the crown reads as a
  // helmet floating above the scalp.
  const cap = new THREE.Mesh(
    new THREE.SphereGeometry(0.094, 24, 18, 0, Math.PI * 2, 0, Math.PI * 0.76), hairMat);
  cap.position.set(0, 0.652, -0.004);
  cap.scale.set(1.0, 1.06, 1.04);
  cap.rotation.x = -0.2;          // sits back off the forehead
  cap.castShadow = true;
  // a shorter crop at the nape, below where the cap stops
  const nape = new THREE.Mesh(
    new THREE.SphereGeometry(0.088, 20, 14, 0, Math.PI * 2, Math.PI * 0.42, Math.PI * 0.3), hairMat);
  nape.position.set(0, 0.63, -0.018);
  nape.scale.set(1.0, 1.12, 0.94);
  nape.castShadow = true;
  socket.add(cap, nape);
}

/**
 * Poses the officer for this frame.
 *
 * @param {THREE.Group} officer
 * @param {object} s  {moving, sprinting, aiming, pitch, recoil, dt, speed}
 */
export function poseOfficer(officer, s) {
  const u = officer.userData;
  const { legL, legR, armL, armR, spine } = u;

  if (s.moving) u.phase += s.dt * (s.sprinting ? 11 : 7.6);
  else u.phase += s.dt * 1.4;

  const swing = s.moving ? Math.sin(u.phase) : Math.sin(u.phase) * 0.06;
  const stride = s.sprinting ? 0.72 : 0.5;

  legL.rotation.x = swing * stride;
  legR.rotation.x = -swing * stride;
  legL.userData.lower.rotation.x = Math.max(0, -swing) * stride * 1.5;
  legR.userData.lower.rotation.x = Math.max(0, swing) * stride * 1.5;

  // the spine leans into a run and follows the aim up and down
  spine.rotation.x = THREE.MathUtils.clamp(s.pitch * 0.55, -0.7, 0.7)
    + (s.sprinting && s.moving ? 0.16 : 0.04);

  const aim = s.aiming ? 1 : 0;

  u.grip.position.set(
    THREE.MathUtils.lerp(0.13, 0.03, aim),
    THREE.MathUtils.lerp(0.31, 0.42, aim),
    THREE.MathUtils.lerp(-0.2, -0.24, aim));
  u.grip.rotation.set(
    THREE.MathUtils.lerp(0.22, 0.0, aim) + s.recoil * 0.1,
    THREE.MathUtils.lerp(-0.16, 0.0, aim),
    THREE.MathUtils.lerp(0.1, 0.0, aim));

  // The hands are solved onto the weapon rather than posed by eye: hand-tuned
  // Euler angles never quite land on the grip, and any change to the rifle's
  // position silently breaks them again.
  officer.updateMatrixWorld(true);
  reachFor(armR, u.grip, spine, RIGHT_HAND, 1);
  reachFor(armL, u.grip, spine, LEFT_HAND, -1);
}

const DOWN = new THREE.Vector3(0, -1, 0);
const RIGHT_HAND = new THREE.Vector3(0.005, -0.1, 0.075);   // pistol grip
const LEFT_HAND = new THREE.Vector3(0, 0.0, -0.3);          // handguard
const _target = new THREE.Vector3();
const _origin = new THREE.Vector3();
const _dir = new THREE.Vector3();
const _q = new THREE.Quaternion();

/**
 * Two-bone IK: swings the shoulder so the hand lands on `localTarget`
 * (expressed in the weapon grip's space) and bends the elbow to match.
 * `side` flips which way the elbow breaks.
 */
function reachFor(arm, grip, spine, localTarget, side) {
  _target.copy(localTarget);
  grip.localToWorld(_target);
  spine.worldToLocal(_target);

  _origin.copy(arm.position);
  _dir.copy(_target).sub(_origin);

  const l1 = arm.userData.upperLen;
  const l2 = arm.userData.lowerLen;
  const d = THREE.MathUtils.clamp(_dir.length(), Math.abs(l1 - l2) + 0.02, l1 + l2 - 0.02);
  _dir.normalize();

  // law of cosines for the shoulder offset and the elbow's interior angle
  const shoulder = Math.acos(
    THREE.MathUtils.clamp((l1 * l1 + d * d - l2 * l2) / (2 * l1 * d), -1, 1));
  const elbow = Math.acos(
    THREE.MathUtils.clamp((l1 * l1 + l2 * l2 - d * d) / (2 * l1 * l2), -1, 1));

  arm.quaternion.copy(_q.setFromUnitVectors(DOWN, _dir));
  arm.rotateX(shoulder);
  arm.rotateY(side * 0.12);          // let the elbows break outward a little
  arm.userData.lower.rotation.set(-(Math.PI - elbow), 0, 0);
}
