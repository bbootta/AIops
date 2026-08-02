import * as THREE from 'three';
import { RoundedBoxGeometry } from 'three/addons/geometries/RoundedBoxGeometry.js';
import { makeCanvas, makeRng, noiseOverlay, texture, heightToNormal, detailNormal,
         grit, streaks, blob } from './tex.js';
import { buildBody, RIG } from './body.js';

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
    ctx.fillStyle = '#241b15';
    ctx.fillRect(0, 0, w, h);
    // low-contrast grain: strong blotches read as camouflage rags, not leather
    noiseOverlay(ctx, w, h, { seed: 12, grid: 10, octaves: 4, color: [66, 52, 40], alpha: 0.32 });
    noiseOverlay(ctx, w, h, { seed: 19, grid: 40, octaves: 3, color: [12, 9, 7], alpha: 0.35 });
    // rubbed-through highlights on the wear points, kept faint
    for (let i = 0; i < 22; i++) {
      blob(ctx, rng() * w, rng() * h, 5 + rng() * 18, rng, `rgba(104,84,62,${0.06 + rng() * 0.1})`);
    }
    grit(ctx, w, h, 4000, rng, 0.16, 0.12);
  };
  return {
    map: texture(makeCanvas(512, 512, (c, w, h) => paint(c, w, h, 'a')), { srgb: true }),
    height: makeCanvas(512, 512, (c, w, h) => paint(c, w, h, 'h')),
    // creased leather is polished where it rubs and matte in the folds. The
    // floor matters: a near-mirror patch under this sky blows out to a white
    // slab, which is what shredded the jacket in the sun.
    rough: texture(makeCanvas(512, 512, (ctx, w, h) => {
      const r2 = makeRng(402);
      ctx.fillStyle = '#b4b4b4';
      ctx.fillRect(0, 0, w, h);
      noiseOverlay(ctx, w, h, { seed: 19, grid: 34, octaves: 3, color: [225, 225, 225], alpha: 0.45 });
      for (let i = 0; i < 22; i++) {
        blob(ctx, r2() * w, r2() * h, 5 + r2() * 18, r2, `rgba(128,128,128,${0.25 + r2() * 0.3})`);
      }
    })),
  };
}

/** Worn leather gloves — a riot officer's hands are never bare. */
function gloveMaterial() {
  const rng = makeRng(407);
  return new THREE.MeshStandardMaterial({
    roughness: 0.82,
    metalness: 0.02,
    map: texture(makeCanvas(256, 256, (ctx, w, h) => {
      ctx.fillStyle = '#241d18'; ctx.fillRect(0, 0, w, h);
      noiseOverlay(ctx, w, h, { seed: 3, grid: 8, octaves: 4, color: [74, 60, 47], alpha: 0.4 });
      noiseOverlay(ctx, w, h, { seed: 8, grid: 26, octaves: 3, color: [12, 10, 8], alpha: 0.4 });
      grit(ctx, w, h, 2600, rng, 0.24, 0.1);
    }), { srgb: true }),
  });
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

/**
 * A gloved hand at the end of a forearm bone. Rigid, and rightly so — the
 * skinned body stops at the wrist because a hand curled around a weapon does
 * not deform, it just goes where the forearm goes.
 */
function makeHand(mat, foreLen, side) {
  const g = new THREE.Group();
  g.position.y = -foreLen;
  const r = 0.062;

  const palm = new THREE.Mesh(new RoundedBoxGeometry(r * 1.7, r * 1.9, r * 1.05, 3, 0.015), mat);
  palm.position.y = -r * 0.8;
  g.add(palm);
  // curled fingers and an opposed thumb, so the grip reads as a hand
  for (let f = 0; f < 4; f++) {
    const finger = new THREE.Mesh(new THREE.CapsuleGeometry(r * 0.19, r * 0.62, 3, 8), mat);
    finger.position.set(r * (0.42 - f * 0.28), -r * 1.62, r * 0.16);
    finger.rotation.x = 1.25;
    g.add(finger);
  }
  const thumb = new THREE.Mesh(new THREE.CapsuleGeometry(r * 0.22, r * 0.5, 3, 8), mat);
  thumb.position.set(side * r * 0.72, -r * 1.15, -r * 0.2);
  thumb.rotation.set(0.5, 0, side * -0.75);
  g.add(thumb);
  return g;
}

export function makeOfficer() {
  const root = new THREE.Group();

  const lea = leatherMaterial();
  const leather = new THREE.MeshStandardMaterial({
    map: lea.map, roughness: 0.62, metalness: 0.02, color: 0xffffff,
    roughnessMap: lea.rough,
    // sun-facing angles: the full sleeve blew out cream from the bright sky
    // in the environment map, not just a rim
    envMapIntensity: 0.8,
  });
  leather.normalMap = texture(detailNormal(heightToNormal(lea.height, 1.4), 3, 0.5));
  leather.normalScale.set(0.55, 0.55);

  const trousers = fabricMaterial(0x24262c, 71);
  const boots = new THREE.MeshStandardMaterial({ color: 0x14120f, roughness: 0.55, metalness: 0.06 });
  const glove = gloveMaterial();
  const hairMat = new THREE.MeshStandardMaterial({ color: 0x100d0c, roughness: 0.72 });
  const patch = patchMaterial();

  // ---- skinned body ----
  // Torso, arms and legs are one continuous SkinnedMesh; see body.js. The
  // bones it returns take the place of the Groups this rig used to be built
  // from, under the same names, so poseOfficer and the IK below are unchanged.
  const body = buildBody(leather, trousers);
  root.add(body.root);
  const { spine, armL, armR, legL, legR } = body.bones;

  // Bone chains, described the way the IK and the walk cycle expect.
  armL.userData = { lower: body.bones.foreL, upperLen: RIG.upperArm, lowerLen: RIG.foreArm };
  armR.userData = { lower: body.bones.foreR, upperLen: RIG.upperArm, lowerLen: RIG.foreArm };
  legL.userData = { lower: body.bones.shinL };
  legR.userData = { lower: body.bones.shinR };

  // Rigid kit, hung off the bones it should follow.
  const belt = new THREE.Mesh(new THREE.TorusGeometry(0.156, 0.026, 8, 22), boots);
  belt.position.y = 0.05;
  belt.rotation.x = Math.PI / 2;
  const buckle = new THREE.Mesh(new RoundedBoxGeometry(0.07, 0.05, 0.02, 2, 0.008),
    new THREE.MeshStandardMaterial({ color: 0x9c8a5e, roughness: 0.42, metalness: 0.8 }));
  buckle.position.set(0, 0.05, -0.168);
  const holster = new THREE.Mesh(new RoundedBoxGeometry(0.1, 0.2, 0.07, 3, 0.02), boots);
  holster.position.set(0.168, -0.05, 0.03);
  holster.rotation.z = -0.12;
  const radio = new THREE.Mesh(new RoundedBoxGeometry(0.07, 0.13, 0.05, 3, 0.015), boots);
  radio.position.set(-0.16, 0.0, 0.04);
  const antenna = new THREE.Mesh(new THREE.CylinderGeometry(0.006, 0.005, 0.16, 5), boots);
  antenna.position.set(-0.16, 0.13, 0.04);
  body.bones.hips.add(belt, buckle, holster, radio, antenna);

  // Boots on the shins, gloves on the forearms — rigid parts of a body that
  // genuinely is rigid there, so they gain nothing from being skinned.
  for (const [shin, boot] of [[body.bones.shinL, 0], [body.bones.shinR, 0]]) {
    void boot;
    const foot = new THREE.Mesh(
      new RoundedBoxGeometry(0.115, 0.085, 0.3, 3, 0.02), boots);
    foot.position.set(0, -RIG.shin - 0.03, 0.06);
    shin.add(foot);
  }
  for (const [fore, side] of [[body.bones.foreL, -1], [body.bones.foreR, 1]]) {
    fore.add(makeHand(glove, RIG.foreArm, side));
  }

  // The jacket hem and waistband that used to ring the waist are gone: they
  // existed to hide the seam between the old capsule torso and the hip block,
  // and the skinned body has no such seam. Stacked on top of the duty belt
  // they just read as an inner tube.
  const collarMat = leather.clone();
  collarMat.side = THREE.DoubleSide;      // open cylinder, seen into from above
  const collar = new THREE.Mesh(
    new THREE.CylinderGeometry(0.082, 0.104, 0.1, 16, 1, true), collarMat);
  collar.position.y = 0.485;
  spine.add(collar);

  const neckMat = new THREE.MeshStandardMaterial({ color: 0x6d5140, roughness: 0.85 });
  const neck = new THREE.Mesh(new THREE.CapsuleGeometry(0.058, 0.07, 3, 10), neckMat);
  neck.position.y = 0.5;
  spine.add(neck);

  // ---- head ----
  const skin = new THREE.MeshStandardMaterial({ color: 0x8f6a50, roughness: 0.8 });
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
  // thick, short hair: a skull cap plus a hairline sweep
  const hair = new THREE.Mesh(new THREE.SphereGeometry(0.117, 18, 16,
    0, Math.PI * 2, 0, Math.PI * 0.62), hairMat);
  hair.position.set(0, 0.622, 0.002);
  hair.scale.set(0.98, 1.06, 1.06);
  // The procedural head is a stand-in: it renders immediately, then the
  // scanned head swaps in once its mesh has decoded.
  const headSocket = new THREE.Group();
  headSocket.userData.hairMat = hairMat;
  headSocket.add(head, jaw, brow, nose, hair);
  spine.add(headSocket);

  // shoulder emblem, riding on the upper-left sleeve so it follows the arm
  const emblem = new THREE.Mesh(new THREE.PlaneGeometry(0.085, 0.1), patch);
  emblem.position.set(-0.076, -0.12, 0);
  emblem.rotation.y = -Math.PI / 2;
  armL.add(emblem);

  // where the rifle rides — parented to the spine so it tracks the aim
  const grip = new THREE.Group();
  grip.position.set(0.18, 0.37, -0.12);
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
  // The scan is centred on its own bounding box, whose middle sits well below
  // the skull, so this is not the head's centre — it is the offset that puts
  // the skull on the shoulders and buries the cut neck inside the collar.
  mesh.position.set(0, 0.545, 0.012);
  mesh.rotation.y = Math.PI;
  socket.add(mesh);

  // Cropped hair as one close-fitting cap, raked back so the whole face and
  // forehead stay clear. The previous pair of oversized shells swallowed the
  // head down to the jaw — a featureless black helmet from every angle.
  // The hair comes cut from the scan's own scalp in head.js, so there is no
  // shell to build here and the placeholder's hair material goes unused.
  void hairMat;

  mesh.traverse((o) => {
    if (o.isMesh) { o.castShadow = true; o.receiveShadow = true; }
  });
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

  // Right-handed: the stock sits into the right shoulder and the muzzle runs
  // down the aim line, crossing very slightly left the way a right-hander's
  // rifle does. Sighting brings it in under the right eye rather than centring
  // it on the chest.
  // Two carries, solved rather than eyeballed.
  //
  // At rest, a low ready: butt in the right shoulder pocket, muzzle 15 degrees
  // down. Forward is -Z, so pitching the muzzle DOWN needs a NEGATIVE
  // rotation.x — the old positive 0.14 had him carrying it 8 degrees skyward.
  // The position is then whatever puts the butt at the shoulder given that
  // angle and the rifle's offset inside the grip, which is what these numbers
  // are; they are not free parameters.
  //
  // Aiming brings it level and onto the centreline, under the right eye.
  u.grip.position.set(
    THREE.MathUtils.lerp(0.18, 0.07, aim),
    THREE.MathUtils.lerp(0.37, 0.42, aim),
    THREE.MathUtils.lerp(-0.12, -0.16, aim));
  u.grip.rotation.set(
    // 8 degrees down, not the 15 of a true low ready: at 15 the weapon fell
    // entirely behind the officer's back from the third-person camera, and a
    // shooter that cannot see their own rifle is worse than a slightly high one
    THREE.MathUtils.lerp(-0.14, 0.0, aim) + s.recoil * 0.1,
    THREE.MathUtils.lerp(0.05, 0.0, aim),
    THREE.MathUtils.lerp(0.04, 0.0, aim));

  // The hands are solved onto the weapon rather than posed by eye: hand-tuned
  // Euler angles never quite land on the grip, and any change to the rifle's
  // position silently breaks them again.
  officer.updateMatrixWorld(true);
  reachFor(armR, u.grip, spine, RIGHT_HAND, 1);
  reachFor(armL, u.grip, spine, LEFT_HAND, -1);
}

// Hand targets, in the weapon grip's space.
//
// These have to stay inside the arms' 0.62 m reach. The support hand was out
// at the handguard, 0.78 m from the left shoulder — unreachable, so the solver
// clamped it and left the arm a straight rod pointing off to the side. Moving
// it back to the magazine well is both reachable and a real technique.
const RIGHT_HAND = new THREE.Vector3(0.0, -0.10, -0.28);  // pistol grip, trigger hand
const LEFT_HAND = new THREE.Vector3(0.0, -0.02, -0.40);   // magazine well, support hand
const _target = new THREE.Vector3();
const _origin = new THREE.Vector3();
const _dir = new THREE.Vector3();
const _pole = new THREE.Vector3();
const _elbow = new THREE.Vector3();
const _bx = new THREE.Vector3();
const _by = new THREE.Vector3();
const _bz = new THREE.Vector3();
const _fore = new THREE.Vector3();
const _m = new THREE.Matrix4();

/**
 * Two-bone IK with a pole vector: puts the hand on `localTarget` (expressed
 * in the weapon grip's space) and — the part the old solver got wrong — pins
 * WHERE the elbow goes. The elbow sits on a circle around the shoulder-target
 * axis; without choosing a point on it, the arms folded up and over the rifle
 * like chicken wings. A human elbow on a rifle lives down, out and back.
 */
function reachFor(arm, grip, spine, localTarget, side) {
  _target.copy(localTarget);
  grip.localToWorld(_target);
  spine.worldToLocal(_target);            // the arm's parent space

  _origin.copy(arm.position);
  _dir.copy(_target).sub(_origin);

  const l1 = arm.userData.upperLen;
  const l2 = arm.userData.lowerLen;
  const d = THREE.MathUtils.clamp(_dir.length(), Math.abs(l1 - l2) + 0.02, l1 + l2 - 0.02);
  _dir.normalize();

  // pole: down, a little outward, slightly behind — projected off the reach
  // axis. Keep the outward push small: at 0.55 the elbows flared wide enough
  // to read as a crab stance.
  _pole.set(side * 0.28, -0.9, 0.2);
  _pole.addScaledVector(_dir, -_pole.dot(_dir));
  if (_pole.lengthSq() < 1e-6) _pole.set(0, -1, 0);
  _pole.normalize();

  // law of cosines fixes how far along the axis the elbow sits; the pole
  // picks its place on the circle around it
  const along = (l1 * l1 - l2 * l2 + d * d) / (2 * d);
  const radius = Math.sqrt(Math.max(l1 * l1 - along * along, 1e-6));
  _elbow.copy(_origin).addScaledVector(_dir, along).addScaledVector(_pole, radius);

  // upper arm: local -Y runs shoulder→elbow, local X is the bend axis, so the
  // elbow's single rotation.x stays in the shoulder-elbow-hand plane
  _by.copy(_elbow).sub(_origin).normalize();          // upper-arm direction
  _fore.copy(_target).sub(_elbow).normalize();        // forearm direction
  _bx.crossVectors(_by, _fore);
  if (_bx.lengthSq() < 1e-8) _bx.copy(_pole);         // straight arm: any axis
  _bx.normalize();
  const bend = Math.acos(THREE.MathUtils.clamp(_by.dot(_fore), -1, 1));
  _by.negate();                                       // limb hangs along -Y
  _bz.crossVectors(_bx, _by);
  arm.quaternion.setFromRotationMatrix(_m.makeBasis(_bx, _by, _bz));
  arm.userData.lower.rotation.set(bend, 0, 0);
}
