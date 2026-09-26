'use strict';
// 실제 크로미움에서 게임을 띄워 런타임 오류 없이 핵심 루프(빔 → 기절 → 트랩 포획, 보손 폭발, 차량 탈취·주행)가 돌아가는지 확인하는 스모크 테스트.
// 실행: node ghostbusters/smoke-test.cjs [스크린샷 폴더]
//  - playwright 와 three@0.160.0 이 require 가능한 곳(예: NODE_PATH)에 있어야 한다. CDN 요청은 로컬 three 로 돌려준다.
const fs = require('fs');
const path = require('path');
const { chromium } = require('playwright');

const html = fs.readFileSync(path.join(__dirname, 'index.html'), 'utf8');
const threeRoot = path.resolve(path.dirname(require.resolve('three')), '..');
const shotDir = process.argv[2];
const errors = [];

(async () => {
  const browser = await chromium.launch({ executablePath: process.env.CHROMIUM_PATH || undefined, args: ['--use-gl=angle', '--use-angle=swiftshader', '--enable-unsafe-swiftshader'] });
  const page = await browser.newPage({ viewport: { width: 1280, height: 720 } });
  page.on('pageerror', e => errors.push('pageerror: ' + e.message));
  page.on('console', m => { if (m.type() === 'error') errors.push('console: ' + m.text()); });
  await page.route('**/*', route => {
    const url = route.request().url();
    if (url === 'http://game.test/') return route.fulfill({ status: 200, contentType: 'text/html', body: html });
    const m = url.match(/three@0\.160\.0\/(.*)$/);
    if (m) return route.fulfill({ status: 200, contentType: 'application/javascript', body: fs.readFileSync(path.join(threeRoot, m[1])) });
    if (/fonts\.(googleapis|gstatic)\.com/.test(url)) return route.fulfill({ status: 200, contentType: 'text/css', body: '' });
    return route.abort();
  });
  await page.goto('http://game.test/');
  await page.waitForFunction(() => window.__game && window.__game.ghosts.length > 0, null, { timeout: 60000 });
  await page.waitForTimeout(1500);
  const shot = async n => { if (shotDir) await page.screenshot({ path: path.join(shotDir, n + '.png') }); };
  await shot('1-menu');

  await page.click('#go');
  await page.waitForTimeout(800);
  const cv = await page.$('#game canvas');
  const box = await cv.boundingBox();
  await page.mouse.move(box.x + box.width / 2, box.y + box.height / 2);
  await page.keyboard.down('KeyW'); await page.waitForTimeout(700); await page.keyboard.up('KeyW');

  // 유령 하나를 조준선 앞으로 데려와 양성자 빔을 쏜다
  const place = () => page.evaluate(() => {
    const G = window.__game, a = G.computeAim(), g = G.ghosts.find(x => x.type !== 'boss');
    g.state = 'hunt'; g.spawnT = 0; g.pos.copy(a.o).addScaledVector(a.dir, 11); g.vel.set(0, 0, 0); g.atk = 99; return g.hp;
  });
  await page.evaluate(() => { window.__game.player.pitch = 0.05; });
  const hp0 = await place();
  await page.mouse.down();
  for (let i = 0; i < 6; i++) { await page.waitForTimeout(250); await place().catch(() => {}); }
  await shot('2-beam');
  const r1 = await page.evaluate(() => { const G = window.__game; return { lock: !!G.beam.lock, heat: G.player.heat, minHp: Math.min(...G.ghosts.map(g => g.hp)) }; });
  await page.mouse.up();
  if (!r1.lock) errors.push('proton stream did not lock onto the ghost');
  if (!(r1.minHp < hp0)) errors.push('ghost took no damage from the proton stream');
  if (!(r1.heat > 0)) errors.push('pack heat did not rise');

  // 기절시킨 뒤 트랩 포획
  await page.evaluate(() => { const G = window.__game; G.trap.state = 'held'; });
  await page.keyboard.press('KeyG');
  await page.waitForFunction(() => window.__game.trap.state === 'armed', null, { timeout: 120000 });
  await page.evaluate(() => { const G = window.__game, g = G.ghosts.find(x => x.type !== 'boss'); g.damage(9999); g.pos.set(G.trap.pos.x + 3, 3.5, G.trap.pos.z + 3); });
  await page.waitForFunction(() => window.__game.player.captures >= 1, null, { timeout: 180000 }).catch(() => {});
  await shot('3-capture');
  const r2 = await page.evaluate(() => ({ money: window.__game.player.money, caps: window.__game.player.captures }));
  if (r2.caps < 1) errors.push('trap did not capture the stunned ghost');

  // 보손 다트 폭발
  await page.keyboard.press('Digit3');
  await page.evaluate(() => { const G = window.__game, a = G.computeAim(); G.explosion(a.o.clone().addScaledVector(a.dir, 14), 7, 65); });
  await page.mouse.down(); await page.waitForTimeout(300); await page.mouse.up();
  await page.waitForTimeout(250);
  await shot('4-explosion');

  // 고스트 왜건 탑승 후 주행
  await page.evaluate(() => { const G = window.__game, w = G.cars.find(c => c.type === 'wagon'); G.player.pos.set(w.pos.x - 1.5, 0.15, w.pos.z); });
  await page.keyboard.press('KeyF');
  await page.keyboard.press('KeyH');
  await page.keyboard.down('KeyW');
  await page.waitForFunction(() => window.__game.player.car && window.__game.player.car.speed > 8, null, { timeout: 120000 }).catch(() => {});
  await page.keyboard.up('KeyW');
  await shot('5-drive');
  const r3 = await page.evaluate(() => { const G = window.__game; return { inCar: !!G.player.car, speed: G.player.car ? G.player.car.speed : 0 }; });
  if (!r3.inCar) errors.push('could not enter the wagon');
  if (!(r3.speed > 2)) errors.push('wagon did not accelerate');
  await page.keyboard.press('KeyF');
  await page.waitForTimeout(400);

  const stats = await page.evaluate(() => { const G = window.__game; return { ghosts: G.ghosts.length, cars: G.cars.length, peds: G.peds.length, hp: Math.round(G.player.hp), inCar: !!G.player.car }; });
  console.log(JSON.stringify({ r1, r2, r3, stats }));
  await browser.close();
  if (errors.length) { console.error('FAIL\n' + [...new Set(errors)].join('\n')); process.exit(1); }
  console.log('PASS');
})().catch(e => { console.error(e); process.exit(2); });
