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
  const scale = HEAD_HEIGHT / size.y;
  geo.translate(-centre.x, -centre.y, -centre.z);
  geo.scale(scale, scale, scale);
  geo.computeVertexNormals();

  const [map, normalMap] = await Promise.all([
    jpegTexture(albedoData, true),
    jpegTexture(normalData, false),
  ]);

  const mesh = new THREE.Mesh(geo, new THREE.MeshStandardMaterial({
    map, normalMap,
    roughness: 0.66, metalness: 0,
  }));
  mesh.material.normalScale.set(0.8, 0.8);
  mesh.castShadow = true;
  mesh.receiveShadow = true;
  return mesh;
}
