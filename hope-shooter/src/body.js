import * as THREE from 'three';

// ============================================================
// A skinned body for the officer.
//
// The limbs used to be a chain of capsules with spheres dropped over the
// joints. That reads as segments however carefully the spheres are sized,
// because each capsule keeps its own closed silhouette — nothing actually
// joins. This builds one continuous surface instead and deforms it with
// linear blend skinning, so the elbow bends rather than pivots.
//
// No rigged character asset is used because none is available on terms this
// project can ship: npm has nothing suitable, and the one humanoid generator
// there is AGPL, which would reach the whole codebase.
//
// The bone hierarchy deliberately mirrors the Group hierarchy it replaces —
// same names, same rest positions, same parents — so the aim, walk cycle and
// two-bone IK in player.js drive it without changing a line. A Bone is an
// Object3D; setting .rotation.x on one does what it did on a Group.
// ============================================================

const RADIAL = 16;

// Rest geometry, in the officer root's space (metres, feet at y=0).
export const RIG = {
  hips: new THREE.Vector3(0, 0.95, 0),
  spine: new THREE.Vector3(0, 0.07, 0),        // relative to hips -> y 1.02
  // Bladed stance: left shoulder forward, right shoulder back.
  armL: new THREE.Vector3(-0.16, 0.4, -0.09),  // relative to spine
  armR: new THREE.Vector3(0.2, 0.4, 0.05),
  legL: new THREE.Vector3(-0.105, 0, 0),       // relative to hips
  legR: new THREE.Vector3(0.105, 0, 0),
  upperArm: 0.32,
  foreArm: 0.3,
  thigh: 0.47,
  shin: 0.45,
};

/**
 * Cross-section profiles. Each row is [t, radius] with t running 0 at the
 * root of the limb to 1 at its tip; the swell at t≈0.06 on the arm is the
 * deltoid, the one past the knee on the leg is the calf.
 */
const ARM_PROFILE = [
  [0.00, 0.079], [0.06, 0.087], [0.18, 0.072], [0.35, 0.063],
  [0.52, 0.055], [0.68, 0.054], [0.84, 0.046], [1.00, 0.037],
];
const LEG_PROFILE = [
  [0.00, 0.113], [0.10, 0.104], [0.25, 0.094], [0.40, 0.083],
  [0.51, 0.076], [0.62, 0.085], [0.78, 0.065], [1.00, 0.049],
];
// Torso and pelvis are elliptical — a person is wider than they are deep.
// Torso width is the ribcage, NOT the shoulder span — the deltoids come from
// the arm tubes at x = +/-0.16..0.20. Sized to the shoulders it reads as a
// barrel with thin sticks attached.
const TORSO_PROFILE = [
  // Starts below the waist and tapers in, so its closing cap sits well inside
  // the pelvis. Ended flush at 0.94 the two surfaces met at the same radius
  // and left a notch ringing the waist.
  [0.88, 0.108, 0.080], [0.94, 0.150, 0.104], [1.00, 0.157, 0.110], [1.08, 0.159, 0.112],
  [1.18, 0.167, 0.118], [1.28, 0.178, 0.126], [1.38, 0.196, 0.130],
  [1.44, 0.190, 0.124], [1.49, 0.132, 0.100], [1.53, 0.086, 0.076],
];
const PELVIS_PROFILE = [
  [0.83, 0.134, 0.099], [0.89, 0.147, 0.110],
  [0.95, 0.152, 0.114], [1.01, 0.148, 0.110],
];

const smoothstep = (a, b, x) => {
  const t = THREE.MathUtils.clamp((x - a) / (b - a), 0, 1);
  return t * t * (3 - 2 * t);
};

/** Accumulates rings of vertices into one indexed, skinned buffer. */
class TubeBuilder {
  constructor() {
    this.pos = [];
    this.uv = [];
    this.idx = [];
    this.skinIndex = [];
    this.skinWeight = [];
    this.groups = [];
  }

  /** One ring of RADIAL+1 vertices; the extra one duplicates the seam for UVs. */
  ring(centre, rx, rz, v, weights) {
    const first = this.pos.length / 3;
    for (let i = 0; i <= RADIAL; i++) {
      const a = (i / RADIAL) * Math.PI * 2;
      this.pos.push(centre.x + Math.cos(a) * rx, centre.y, centre.z + Math.sin(a) * rz);
      this.uv.push(i / RADIAL, v);
      this.pushWeights(weights);
    }
    return first;
  }

  /** Up to four influences, normalised. */
  pushWeights(weights) {
    const total = weights.reduce((s, w) => s + w[1], 0) || 1;
    for (let i = 0; i < 4; i++) {
      const w = weights[i];
      this.skinIndex.push(w ? w[0] : 0);
      this.skinWeight.push(w ? w[1] / total : 0);
    }
  }

  /**
   * Rings run counter-clockwise seen from +Y and ringB sits below ringA, so
   * this winding is what puts the face normals OUTWARD. The other order looks
   * equally plausible and is wrong: it turns the body inside out, and because
   * back faces are culled you do not get an obvious black mess, you get the
   * far inner wall of each limb showing through as a thin flat ribbon.
   */
  bridge(ringA, ringB) {
    for (let i = 0; i < RADIAL; i++) {
      const a0 = ringA + i, a1 = ringA + i + 1;
      const b0 = ringB + i, b1 = ringB + i + 1;
      this.idx.push(a0, b1, b0, a0, a1, b1);
    }
  }

  /** Closes an end with a triangle fan, so no limb shows a hollow tube. */
  cap(ringStart, centre, weights, flip) {
    const c = this.pos.length / 3;
    this.pos.push(centre.x, centre.y, centre.z);
    this.uv.push(0.5, flip ? 0 : 1);
    this.pushWeights(weights);
    for (let i = 0; i < RADIAL; i++) {
      const a = ringStart + i, b = ringStart + i + 1;
      if (flip) this.idx.push(c, b, a);
      else this.idx.push(c, a, b);
    }
  }

  beginGroup() {
    return this.idx.length;
  }

  endGroup(start, materialIndex) {
    this.groups.push([start, this.idx.length - start, materialIndex]);
  }

  build() {
    const g = new THREE.BufferGeometry();
    g.setAttribute('position', new THREE.Float32BufferAttribute(this.pos, 3));
    g.setAttribute('uv', new THREE.Float32BufferAttribute(this.uv, 2));
    g.setAttribute('skinIndex', new THREE.Uint16BufferAttribute(this.skinIndex, 4));
    g.setAttribute('skinWeight', new THREE.Float32BufferAttribute(this.skinWeight, 4));
    g.setIndex(this.idx);
    for (const [start, count, mat] of this.groups) g.addGroup(start, count, mat);
    g.computeVertexNormals();
    return g;
  }
}

/** Samples a [t, r] or [y, rx, rz] profile table. */
function sample(profile, t) {
  for (let i = 0; i < profile.length - 1; i++) {
    const a = profile[i], b = profile[i + 1];
    if (t <= b[0]) {
      const f = (t - a[0]) / (b[0] - a[0] || 1);
      return [
        THREE.MathUtils.lerp(a[1], b[1], f),
        THREE.MathUtils.lerp(a[2] ?? a[1], b[2] ?? b[1], f),
      ];
    }
  }
  const last = profile[profile.length - 1];
  return [last[1], last[2] ?? last[1]];
}

/**
 * A limb: one tube from the joint root straight down, weighted so it hands
 * over from the upper bone to the lower one across a band at the joint and
 * fades into the torso at the very top. That fade is what stops the shoulder
 * tearing away from the chest when the arm swings.
 */
function limbTube(b, origin, upperLen, lowerLen, profile, upperBone, lowerBone, rootBone, rings,
  { anchorWeight = 0.35, anchorSpan = 0.08 } = {}) {
  const total = upperLen + lowerLen;
  const joint = upperLen / total;
  const centre = new THREE.Vector3();
  let prev = -1;
  let firstRing = -1;

  // The shoulder (and hip) tuck.
  //
  // A limb cannot simply be capped where it meets the trunk: the joint sits at
  // the trunk's outer edge by definition, so a disc there is half outside the
  // body and swings into view the moment the limb moves. Widening the trunk to
  // swallow it would need a torso 56cm across. Instead the tube carries on
  // past the joint, converging to a point drawn inward and upward — which is
  // also what a deltoid does as it runs up under the trapezius. The point ends
  // up inside the trunk, so the cap there is never seen.
  const inward = origin.x < 0 ? 1 : -1;
  const TUCK = [
    [-0.105, 0.058, 0.048, 0.012],   // [t, inward, up, radius]
    [-0.052, 0.029, 0.024, 0.052],
  ];
  for (const [t, dx, dy, r] of TUCK) {
    centre.set(origin.x + inward * dx, origin.y + dy, origin.z);
    // Pinned to the trunk: this part of the surface belongs to the shoulder,
    // not to the swinging limb.
    const hold = 1 - smoothstep(-0.105, 0.0, t) * 0.45;
    const ring = b.ring(centre, r, r, t, [[rootBone, hold], [upperBone, 1 - hold]]);
    if (prev >= 0) b.bridge(prev, ring);
    else firstRing = ring;
    prev = ring;
  }

  for (let i = 0; i <= rings; i++) {
    const t = i / rings;
    const [r] = sample(profile, t);
    centre.set(origin.x, origin.y - t * total, origin.z);

    // Hand-over between the two bones, over a band either side of the joint.
    const lower = smoothstep(joint - 0.13, joint + 0.13, t);
    // A little of the parent at the very top, so the limb does not tear away
    // from the trunk. It has to stay SMALL and SHORT on the arms: this rig has
    // no clavicle, so anything welded to the spine stays put while the arm
    // swings 80 degrees onto the rifle, and the surface between the two
    // stretches into a flat web off the shoulder. Legs barely swing, so they
    // can afford a broader, stronger blend into the hips.
    const anchor = (1 - lower) * anchorWeight * (1 - smoothstep(0.0, anchorSpan, t));
    const upper = (1 - lower) - anchor;

    const w = [[lowerBone, lower], [upperBone, upper]];
    if (anchor > 0.001) w.push([rootBone, anchor]);

    const ring = b.ring(centre, r, r, t, w);
    if (prev >= 0) b.bridge(prev, ring);
    else firstRing = ring;
    prev = ring;
  }

  // Both ends closed. The tip is a visible wrist or ankle; the root cap is the
  // 1.2cm disc at the top of the tuck, inside the trunk.
  b.cap(firstRing,
    new THREE.Vector3(origin.x + inward * TUCK[0][1], origin.y + TUCK[0][2], origin.z),
    [[rootBone, 1]], true);
  b.cap(prev, centre.clone(), [[lowerBone, 1]], false);
}

/** Torso or pelvis: an elliptical tube stacked in world Y. */
function trunkTube(b, profile, weightFor, rings) {
  const y0 = profile[0][0];
  const y1 = profile[profile.length - 1][0];
  const centre = new THREE.Vector3();
  let prev = -1;
  let firstRing = -1;

  for (let i = 0; i <= rings; i++) {
    const y = THREE.MathUtils.lerp(y0, y1, i / rings);
    const [rx, rz] = sample(profile, y);
    centre.set(0, y, 0);
    const ring = b.ring(centre, rx, rz, (y - y0) / (y1 - y0), weightFor(y));
    if (prev >= 0) b.bridge(prev, ring);
    else firstRing = ring;
    prev = ring;
  }
  b.cap(firstRing, new THREE.Vector3(0, y0, 0), weightFor(y0), true);
  b.cap(prev, new THREE.Vector3(0, y1, 0), weightFor(y1), false);
}

/**
 * Builds the skeleton and the skinned body.
 *
 * @param {THREE.Material} jacket  worn over the torso and arms
 * @param {THREE.Material} trousers
 * @returns {{root, skinned, bones}} bones keyed by name for player.js to pose
 */
export function buildBody(jacket, trousers) {
  const bone = (pos) => {
    const b = new THREE.Bone();
    b.position.copy(pos);
    return b;
  };

  const hips = bone(RIG.hips);
  const spine = bone(RIG.spine);
  const armL = bone(RIG.armL);
  const foreL = bone(new THREE.Vector3(0, -RIG.upperArm, 0));
  const armR = bone(RIG.armR);
  const foreR = bone(new THREE.Vector3(0, -RIG.upperArm, 0));
  const legL = bone(RIG.legL);
  const shinL = bone(new THREE.Vector3(0, -RIG.thigh, 0));
  const legR = bone(RIG.legR);
  const shinR = bone(new THREE.Vector3(0, -RIG.thigh, 0));

  hips.add(spine, legL, legR);
  spine.add(armL, armR);
  armL.add(foreL);
  armR.add(foreR);
  legL.add(shinL);
  legR.add(shinR);

  // Index order defines skinIndex.
  const bones = [hips, spine, armL, foreL, armR, foreR, legL, shinL, legR, shinR];
  const I = {};
  bones.forEach((b, i) => { I[b.uuid] = i; });
  const ix = (b) => I[b.uuid];

  const b = new TubeBuilder();

  // --- jacket: torso and both arms ---
  let g = b.beginGroup();
  trunkTube(b, TORSO_PROFILE, (y) => {
    // Below the spine pivot the jacket should ride the hips, or it scissors
    // away from the waistband every time the officer leans into a run.
    const s = smoothstep(0.94, 1.10, y);
    return [[ix(spine), s], [ix(hips), 1 - s]];
  }, 16);

  const shoulderL = RIG.spine.clone().add(RIG.hips).add(RIG.armL);
  const shoulderR = RIG.spine.clone().add(RIG.hips).add(RIG.armR);
  limbTube(b, shoulderL, RIG.upperArm, RIG.foreArm, ARM_PROFILE,
    ix(armL), ix(foreL), ix(spine), 18);
  limbTube(b, shoulderR, RIG.upperArm, RIG.foreArm, ARM_PROFILE,
    ix(armR), ix(foreR), ix(spine), 18);

  b.endGroup(g, 0);

  // --- trousers: pelvis and both legs ---
  g = b.beginGroup();
  trunkTube(b, PELVIS_PROFILE, () => [[ix(hips), 1]], 6);
  const hipL = RIG.hips.clone().add(RIG.legL);
  const hipR = RIG.hips.clone().add(RIG.legR);
  const legAnchor = { anchorWeight: 0.8, anchorSpan: 0.16 };
  limbTube(b, hipL, RIG.thigh, RIG.shin, LEG_PROFILE,
    ix(legL), ix(shinL), ix(hips), 18, legAnchor);
  limbTube(b, hipR, RIG.thigh, RIG.shin, LEG_PROFILE,
    ix(legR), ix(shinR), ix(hips), 18, legAnchor);
  b.endGroup(g, 1);

  const skinned = new THREE.SkinnedMesh(b.build(), [jacket, trousers]);
  skinned.castShadow = true;
  skinned.receiveShadow = true;
  // The body is authored in the officer root's space, so it stays at the
  // origin and the bind matrix comes out as identity.
  skinned.frustumCulled = false;

  const root = new THREE.Group();
  root.add(hips, skinned);
  root.updateMatrixWorld(true);
  skinned.bind(new THREE.Skeleton(bones));

  return {
    root,
    skinned,
    bones: { hips, spine, armL, foreL, armR, foreR, legL, shinL, legR, shinR },
  };
}
