import { build } from 'esbuild';
import { readFile, writeFile, mkdir } from 'node:fs/promises';

const result = await build({
  entryPoints: ['src/main.js'],
  bundle: true,
  format: 'iife',
  target: 'es2022',
  minify: true,
  legalComments: 'none',
  // the scanned head and its skin maps are inlined, so the built page stays
  // a single file with no side-car requests
  loader: { '.glb': 'base64', '.jpg': 'base64' },
  write: false,
});

const js = result.outputFiles[0].text;
const html = await readFile('src/index.html', 'utf8');
// a function replacer, so `$&` and friends inside the minified bundle are
// never read as replacement patterns
const page = html.replace('<!--BUNDLE-->', () => `<script>\n${js}\n</script>`);

await mkdir('dist', { recursive: true });
await writeFile('dist/index.html', page);
console.log(`dist/index.html — ${(page.length / 1024).toFixed(0)} kB`);
