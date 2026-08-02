import detail0 from '@pmndrs/assets/normals/0007.webp.js';
import detail1 from '@pmndrs/assets/normals/0021.webp.js';

// ============================================================
// Authored micro-surface normal maps.
//
// Procedural noise gives even, statistical grain; real plaster and asphalt
// have organic structure that noise never quite produces. These are tiled
// several times inside each generated normal map, so the fine relief repeats
// far more often than the base texture and stays sharp underfoot.
//
// Decoded through a Blob rather than an <img src="data:…"> so no content
// policy has to allow data URIs for it to work.
// ============================================================

function toBitmap(dataUri) {
  const comma = dataUri.indexOf(',');
  const mime = dataUri.slice(5, dataUri.indexOf(';'));
  const bin = atob(dataUri.slice(comma + 1));
  const bytes = new Uint8Array(bin.length);
  for (let i = 0; i < bin.length; i++) bytes[i] = bin.charCodeAt(i);
  return createImageBitmap(new Blob([bytes], { type: mime }));
}

export function loadDetailNormals() {
  return Promise.all([toBitmap(detail0), toBitmap(detail1)]);
}
