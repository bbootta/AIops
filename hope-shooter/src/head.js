import * as THREE from 'three';
import { GLTFLoader } from 'three/addons/loaders/GLTFLoader.js';
import glbData from '../assets/head-scan.glb';
import albedoData from '../assets/head-albedo.jpg';
import normalData from '../assets/head-normal.jpg';

// ============================================================
// A photogrammetry head scan, with its matching skin texture set.
//
// Primitives can approximate a body under clothing, but not a face: skin
// needs the pore-level normal detail and the uneven colour that only a scan
// carries. This is Lee Perry-Smith's head, released for exactly this use —
// see ATTRIBUTION.md.
//
// Everything is inlined as base64 and decoded in memory, so no request goes
// out for it and no content policy has to allow data URIs.
// ============================================================

const HEAD_HEIGHT = 0.245; // crown to chin, in metres

function bytesOf(base64) {
  const bin = atob(base64);
  const out = new Uint8Array(bin.length);
  for (let i = 0; i < bin.length; i++) out[i] = bin.charCodeAt(i);
  return out;
}

async function jpegTexture(base64, srgb) {
  const bitmap = await createImageBitmap(
    new Blob([bytesOf(base64)], { type: 'image/jpeg' }));
  const tex = new THREE.Texture(bitmap);
  tex.colorSpace = srgb ? THREE.SRGBColorSpace : THREE.NoColorSpace;
  tex.flipY = false;               // matches the glTF UV convention
  tex.anisotropy = 8;
  tex.needsUpdate = true;
  return tex;
}

export async function loadScannedHead() {
  const gltf = await new GLTFLoader().parseAsync(bytesOf(glbData).buffer, '');

  let source = null;
  gltf.scene.traverse((o) => { if (o.isMesh && !source) source = o; });
  if (!source) throw new Error('head scan contains no mesh');

  const geo = source.geometry.clone();
  geo.computeBoundingBox();
  const box = geo.boundingBox;
  const size = new THREE.Vector3();
  box.getSize(size);
  const centre = new THREE.Vector3();
  box.getCenter(centre);

  // The scan arrives at an arbitrary scale and offset; normalise it so the
  // caller can position a head without knowing anything about the asset.
  //
  // The extent is NOT crown-to-chin: measured band-by-band, the mesh carries
  // a neck and a wide bust cut below it, so its full height normalised to
  // 0.245 m left the actual skull about 13 cm tall — a doll's head. The 1.38
  // puts the skull back at human size (15 cm wide, measured at the temples).
  const scale = (HEAD_HEIGHT / size.y) * 1.38;
  geo.translate(-centre.x, -centre.y, -centre.z);
  geo.scale(scale, scale, scale);

  // Drop the bust: its rim flares far wider than any collar can swallow and
  // rendered as a bare-skin ring around the neck. Keep every face with at
  // least one vertex above mid-neck.
  const cut = -0.045 * 1.38;
  const pos = geo.attributes.position;
  if (geo.index) {
    const idx = geo.index.array;
    const kept = [];
    for (let i = 0; i < idx.length; i += 3) {
      if (pos.getY(idx[i]) >= cut || pos.getY(idx[i + 1]) >= cut || pos.getY(idx[i + 2]) >= cut) {
        kept.push(idx[i], idx[i + 1], idx[i + 2]);
      }
    }
    geo.setIndex(kept);
  }
  geo.computeVertexNormals();

  const [map, normalMap] = await Promise.all([
    jpegTexture(albedoData, true),
    jpegTexture(normalData, false),
  ]);

  const mesh = new THREE.Mesh(geo, new THREE.MeshStandardMaterial({
    map, normalMap,
    // The albedo is a fair-skinned studio scan lit from every side. Left at
    // white it rendered as a blown-out mask under this sky — brighter than
    // the road, brighter than the sun-facing brick. The multiplier pulls it
    // to a plausible tone and, more importantly, back into the scene's range.
    color: 0x8a6a54,
    roughness: 0.78, metalness: 0,
  }));
  mesh.material.normalScale.set(0.8, 0.8);
  mesh.castShadow = true;
  mesh.receiveShadow = true;

  const head = new THREE.Group();
  head.add(mesh);
  const hair = buildHair(geo);
  if (hair) head.add(hair);
  return head;
}

/**
 * Cropped hair, cut from the scan's own scalp.
 *
 * The scan is effectively bald, so it needs hair — but every sphere-cap
 * approximation read as a bowl helmet, because a hemisphere cannot follow a
 * hairline. Taking the triangles above a tilted plane through the skull and
 * floating them a few millimetres along their normals gives a shell that
 * matches the head exactly, by construction.
 *
 * The plane is high at the front and low at the back, which is what a hairline
 * is: measured against this scan, the brow sits near y=0.085 and the crown at
 * y=0.169, so the front edge lands on the forehead and the back reaches the nape.
 */
function buildHair(geo) {
  if (!geo.index) return null;

  const pos = geo.attributes.position;
  const nrm = geo.attributes.normal;
  const HAIRLINE = 0.078;      // height of the plane at the ear line
  const RAKE = 0.62;           // how much higher it sits toward the face (+Z)
  const above = (i) => pos.getY(i) > HAIRLINE + RAKE * pos.getZ(i);

  const idx = geo.index.array;
  const kept = [];
  for (let i = 0; i < idx.length; i += 3) {
    if (above(idx[i]) && above(idx[i + 1]) && above(idx[i + 2])) {
      kept.push(idx[i], idx[i + 1], idx[i + 2]);
    }
  }
  if (kept.length < 3) return null;

  const hg = geo.clone();
  hg.setIndex(kept);
  // lift off the scalp, or it z-fights with the skin underneath
  const p = hg.attributes.position;
  for (let i = 0; i < p.count; i++) {
    p.setXYZ(i,
      p.getX(i) + nrm.getX(i) * 0.005,
      p.getY(i) + nrm.getY(i) * 0.005,
      p.getZ(i) + nrm.getZ(i) * 0.005);
  }
  p.needsUpdate = true;

  const hair = new THREE.Mesh(hg, new THREE.MeshStandardMaterial({
    // not black: pure black reads as a hole punched in the silhouette
    color: 0x191411, roughness: 0.82, metalness: 0,
  }));
  hair.castShadow = true;
  return hair;
}
