import { build } from 'esbuild';
import { readFile, writeFile, mkdir } from 'node:fs/promises';

const result = await build({
  entryPoints: ['src/main.js'],
  bundle: true,
  format: 'iife',
  target: 'es2022',
  minify: true,
  legalComments: 'none',
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
