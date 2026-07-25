import * as THREE from 'three';
import { EXRLoader } from 'three/addons/loaders/EXRLoader.js';
import cityExr from '@pmndrs/assets/hdri/city.exr.js';

// ============================================================
// Image-based lighting from a real captured environment.
//
// An analytic sky only knows about a smooth gradient, so metal and glass
// reflect a featureless wash. A photographed HDRI carries the actual
// structure of an urban sky — buildings, bright patches, a sun lobe — which
// is what makes reflective surfaces read as real.
//
// The EXR ships as a base64 data URI, and is decoded straight to bytes and
// parsed in memory. No network request is made for it.
// ============================================================

function base64ToBytes(dataUri) {
  const b64 = dataUri.slice(dataUri.indexOf(',') + 1);
  const bin = atob(b64);
  const out = new Uint8Array(bin.length);
  for (let i = 0; i < bin.length; i++) out[i] = bin.charCodeAt(i);
  return out;
}

/**
 * Decodes the HDRI, grades it to this street's dusty palette, and returns a
 * prefiltered environment map.
 *
 * @param {THREE.WebGLRenderer} renderer
 * @param {{tint: number[], exposure: number}} grade
 */
export function loadEnvironment(renderer, { tint = [1.06, 1.0, 0.9], exposure = 1 } = {}) {
  const loader = new EXRLoader();
  loader.setDataType(THREE.FloatType);
  const bytes = base64ToBytes(cityExr);
  const exr = loader.parse(bytes.buffer);

  const data = exr.data;
  const stride = exr.format === THREE.RGBAFormat ? 4 : 3;

  // Normalise mean luminance first, so swapping the HDRI later never silently
  // changes how bright the whole street is.
  let sum = 0, n = 0;
  for (let i = 0; i < data.length; i += stride) {
    sum += data[i] * 0.2126 + data[i + 1] * 0.7152 + data[i + 2] * 0.0722;
    n++;
  }
  const mean = sum / Math.max(1, n);
  const gain = mean > 1e-5 ? (0.42 / mean) * exposure : exposure;

  for (let i = 0; i < data.length; i += stride) {
    data[i] *= gain * tint[0];
    data[i + 1] *= gain * tint[1];
    data[i + 2] *= gain * tint[2];
  }

  const tex = new THREE.DataTexture(
    data, exr.width, exr.height, exr.format, exr.type);
  tex.mapping = THREE.EquirectangularReflectionMapping;
  tex.colorSpace = THREE.LinearSRGBColorSpace;
  tex.minFilter = THREE.LinearFilter;
  tex.magFilter = THREE.LinearFilter;
  tex.generateMipmaps = false;
  tex.needsUpdate = true;

  const pmrem = new THREE.PMREMGenerator(renderer);
  const target = pmrem.fromEquirectangular(tex);
  pmrem.dispose();
  tex.dispose();
  return target.texture;
}
