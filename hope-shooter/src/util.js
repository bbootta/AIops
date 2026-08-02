import * as THREE from 'three';
import { mergeGeometries } from 'three/addons/utils/BufferGeometryUtils.js';

/**
 * Bakes a group's meshes into one mesh per material.
 * A building is ~50 little parts; without this the street would cost
 * well over a thousand draw calls a frame.
 * Lines, points and sprites are passed through untouched.
 */
export function flattenByMaterial(group) {
  group.updateMatrixWorld(true);
  const byMat = new Map();
  const passthrough = [];

  group.traverse((o) => {
    if (o.isInstancedMesh || o.isSprite || o.isLine || o.isPoints) {
      passthrough.push(o);
    } else if (o.isMesh) {
      if (Array.isArray(o.material)) return; // not used; keep merge simple
      const geo = o.geometry.index ? o.geometry.toNonIndexed() : o.geometry.clone();
      geo.applyMatrix4(o.matrixWorld);
      for (const name of Object.keys(geo.attributes)) {
        if (name !== 'position' && name !== 'normal' && name !== 'uv') {
          geo.deleteAttribute(name);
        }
      }
      if (!byMat.has(o.material)) byMat.set(o.material, []);
      byMat.get(o.material).push(geo);
    }
  });

  const out = new THREE.Group();
  for (const [mat, geos] of byMat) {
    const merged = geos.length === 1 ? geos[0] : mergeGeometries(geos, false);
    if (!merged) continue;
    const mesh = new THREE.Mesh(merged, mat);
    mesh.castShadow = true;
    mesh.receiveShadow = true;
    out.add(mesh);
  }
  for (const o of passthrough) {
    o.matrix.copy(o.matrixWorld);
    o.matrix.decompose(o.position, o.quaternion, o.scale);
    out.add(o);
  }
  return out;
}
