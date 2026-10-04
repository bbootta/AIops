'use strict';
// 실제 크로미움에서 게임을 띄워 런타임 오류 없이 핵심 루프(빔 → 기절 → 트랩 포획, 보손 폭발, 차량 탈취·주행)와
// 의뢰 4종, 경찰 추격·체포, 사다리·짚라인·옥상 샘플, 오 박사 상점, 저장·이어 하기가 돌아가는지 확인하는 스모크 테스트.
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

  // 헤드리스 렌더는 아주 느리다(초당 1프레임 안팎, 게임 시간은 프레임당 최대 0.05초). 그래서 대기는 게임 상태를 기준으로 넉넉히 잡고,
  // 한 단계가 실패해도 다음 단계를 계속 확인하도록 단계마다 오류를 따로 모은다.
  const ev = (fn, arg) => page.evaluate(fn, arg);
  const until = (fn, t = 300000, arg) => page.waitForFunction(fn, arg, { timeout: t, polling: 250 }).then(() => true, () => false);
  const check = (ok, msg) => { if (!ok) errors.push(msg); return ok; };
  const step = async (name, fn) => { try { await fn(); } catch (e) { errors.push(`${name}: ${String(e.message).split('\n')[0]}`); } };
  const stand = (x, y, z, yaw) => ev(([x, y, z, yaw]) => { const P = window.__game.player; P.pos.set(x, y, z); P.vel.set(0, 0, 0); if (yaw !== null) P.yaw = yaw; }, [x, y, z, yaw]);
  const giver = kind => ev(k => { const g = window.__game.givers.find(x => x.kind === k); return { x: g.pos.x, z: g.pos.z }; }, kind);
  const rep = () => ev(() => window.__game.save.rep);
  // 트랩을 던지고, 의뢰 유령을 기절시켜 트랩 옆에 둔다
  const trapMissionGhost = async () => {
    await ev(() => { window.__game.trap.state = 'held'; });
    await page.keyboard.press('KeyG');
    if (!check(await until(() => window.__game.trap.state === 'armed'), 'trap did not arm')) return;
    await ev(() => { const G = window.__game, g = G.mission.ghost; g.damage(1e6); g.pos.set(G.trap.pos.x + 3, G.trap.pos.y + 3.5, G.trap.pos.z + 3); g.vel.set(0, 0, 0); });
  };
  const out = {};

  // 의뢰 1: 김 사서에게 E로 말을 걸어 수락하고, 이름 붙은 원령을 포획
  await step('exorcism', async () => {
    const gv = await giver('exorcism');
    await stand(gv.x + 1.5, 0.15, gv.z + 1.5, null);
    await page.waitForTimeout(300);
    await page.keyboard.press('KeyE');
    if (!check(await until(() => window.__game.modal === 'dlg', 60000), 'E did not open the mission dialog')) return;
    await shot('6-dialog');
    await page.keyboard.press('KeyE');
    if (!check(await until(() => window.__game.mission && window.__game.mission.kind === 'exorcism', 60000), 'accepting did not start the exorcism mission')) return;
    await until(() => document.getElementById('misT').textContent.includes('서고의 원령') && !document.getElementById('wp').hidden, 60000);
    const hud = await ev(() => ({ panel: !document.getElementById('mis').hidden, obj: !document.getElementById('obj').hidden, title: document.getElementById('misT').textContent, wp: !document.getElementById('wp').hidden, named: window.__game.mission.ghost.name, icons: window.__game.givers.every(g => !g.icon.visible) }));
    check(hud.panel && !hud.obj && hud.title.includes('서고의 원령') && hud.wp && hud.icons, 'mission HUD, waypoint or giver icons are wrong: ' + JSON.stringify(hud));
    check(hud.named === '책벌레 원령', 'mission ghost is not named');
    await shot('7-mission');
    const r0 = await rep();
    await trapMissionGhost();
    check(await until(r => !window.__game.mission && window.__game.save.rep === r + 1, 300000, r0), 'exorcism did not complete on capture');
  });

  // 의뢰 2: 귀신 들린 택시. 퇴마 게이지가 차면 귀신이 튀어나오고, 실패하면 깨끗이 정리된다
  await step('possessed', async () => {
    const pz = await ev(() => { const G = window.__game; G.startMission(G.givers.find(x => x.kind === 'possessed')); const c = G.mission.car; G.player.pos.set(c.pos.x + 7, 0.15, c.pos.z + 7); G.player.yaw = Math.atan2(-7, -7); window.__taxi = c; return { possessed: !!c.possessed, top: c.T.top }; });
    check(pz.possessed && pz.top > 33, 'possessed taxi was not set up');
    await ev(() => window.__game.mission.car.damage(200));
    if (!check(await until(() => { const m = window.__game.mission; return m && m.ghost && m.ghost.state === 'stunned' && m.ghost.name === '택시 귀신'; }), 'possessed taxi did not release its ghost')) return;
    await until(() => document.getElementById('misO').textContent.includes('택시 귀신'), 60000);
    await shot('8-possessed');
    await ev(() => { window.__ghost = window.__game.mission.ghost; window.__game.endMission(false, 'test'); });
    const pz2 = await ev(() => ({ gone: !window.__game.ghosts.includes(window.__ghost), calm: !window.__taxi.possessed, top: window.__taxi.T.top }));
    check(pz2.gone && pz2.calm && pz2.top === 33, 'failed taxi mission did not clean up: ' + JSON.stringify(pz2));
  });

  // 의뢰 3: 편의점 사수. 습격 유령이 오고, 시간을 버티면 성공
  await step('hold', async () => {
    const gv = await giver('hold');
    await stand(gv.x, 0.15, gv.z + 6, Math.PI);
    await ev(() => { const G = window.__game; G.startMission(G.givers.find(x => x.kind === 'hold')); G.mission.spawnT = 0; });
    if (!check(await until(() => { const m = window.__game.mission; return m && m.kind === 'hold' && m.raiders.length >= 1; }), 'no raiders came for the store')) return;
    await page.waitForTimeout(1500);
    await shot('9-hold');
    const r0 = await rep();
    await ev(() => { window.__game.mission.time = 0.05; });
    check(await until(r => !window.__game.mission && window.__game.save.rep === r + 1, 120000, r0), 'store defence did not succeed when time ran out');
    check(await ev(() => window.__game.ghosts.every(g => !g.raid && !g.mission)), 'raiders kept raiding after the mission');
  });

  // 경찰: 수배 2단계 추격, 5단계 헬기, 경관 체포 후 본부 석방
  await step('police', async () => {
    await ev(() => window.__game.crime(2, 'test', 0));
    check(await until(() => window.__game.wanted === 2 && window.__game.cars.some(c => c.type === 'police' && c.cop.mode === 'chase')), 'no police chase after a crime');
    check(await until(() => !document.getElementById('stars').hidden, 60000), 'wanted stars are not shown');
    await ev(() => window.__game.crime(3, 'test2', 0));
    check(await until(() => window.__game.wanted === 5 && window.__game.heli.active && window.__game.heli.cone.visible), 'helicopter did not launch at 5 stars');
    await page.waitForTimeout(1200);
    await shot('10-police');
    const money0 = await ev(() => { const G = window.__game, P = G.player, p = P.pos; P.hp = P.maxHp; G.spawnCop(p.x + 1, p.z); return P.money; });
    check(await until(() => window.__game.player.busted), 'officer did not arrest the player');
    check(await until(() => !window.__game.player.busted && window.__game.wanted === 0), 'player was not released after the arrest');
    const money1 = await ev(() => window.__game.player.money);
    out.fine = [money0, money1];
    check(money1 < money0, 'arrest did not cost a fine');
  });

  // 의뢰 4: 생방송 레이스. 차에 타면 출발, 링을 지나면 진행
  await step('race', async () => {
    const r0 = await rep();
    await ev(() => { const G = window.__game; G.startMission(G.givers.find(x => x.kind === 'race')); });
    check(await ev(() => window.__game.mission && window.__game.mission.phase === 'wait'), 'race did not wait for a car');
    await ev(() => { const G = window.__game, w = G.cars.find(c => c.type === 'wagon'); G.player.pos.set(w.pos.x - 1.5, 0.15, w.pos.z); G.player.vel.set(0, 0, 0); });
    await page.waitForTimeout(300);
    await page.keyboard.press('KeyF');
    if (!check(await until(() => { const m = window.__game.mission; return m && m.phase === 'run' && m.pts.length === m.n; }), 'race did not start after entering a car')) return;
    await ev(() => { const G = window.__game, p = G.mission.pts[0], c = G.player.car; c.pos.set(p.x, 0, p.z); c.vel.set(0, 0); });
    check(await until(() => window.__game.mission && window.__game.mission.k === 1), 'first race checkpoint was not counted');
    await page.waitForTimeout(400);
    await shot('11-race');
    await ev(() => { const G = window.__game, m = G.mission; m.k = m.n - 1; const p = m.pts[m.k], c = G.player.car; c.pos.set(p.x, 0, p.z); c.vel.set(0, 0); });
    check(await until(r => !window.__game.mission && window.__game.save.rep === r + 1, 120000, r0), 'race did not finish');
    await page.keyboard.press('KeyF');
    await until(() => !window.__game.player.car, 60000);
  });

  // 옥상: 사다리로 오르내리기 (오르는 구간 대부분은 건너뛰고 마지막 몇 미터를 W로 오른다)
  await step('ladder', async () => {
    const L = await ev(() => { const L = [...window.__game.ladders].sort((a, b) => a.h - b.h)[0]; return { x: L.x, z: L.z, nx: L.nx, nz: L.nz, h: L.h }; });
    out.ladder = L.h;
    await stand(L.x + L.nx * 0.6, 0.15, L.z + L.nz * 0.6, Math.atan2(-L.nx, -L.nz));
    await page.waitForTimeout(300);
    await page.keyboard.press('KeyE');
    if (!check(await until(() => !!window.__game.player.climb, 60000), 'E did not grab the ladder')) return;
    await ev(h => { window.__game.player.pos.y = h - 2.2; }, L.h);
    await page.keyboard.down('KeyW');
    const climbed = await until(() => !window.__game.player.climb && window.__game.player.onGround && window.__game.player.pos.y > 5);
    await page.keyboard.up('KeyW');
    const roof = await ev(() => window.__game.player.pos.y);
    check(climbed && Math.abs(roof - L.h) < 0.3, `ladder climb ended at y=${roof}, roof is ${L.h}`);
    await shot('12-roof');
    await stand(L.x - L.nx * 1.3, L.h, L.z - L.nz * 1.3, null);
    await page.waitForTimeout(300);
    await page.keyboard.press('KeyE');
    if (!check(await until(h => !!window.__game.player.climb && window.__game.player.pos.y < h - 1, 60000, L.h), 'E did not start climbing down')) return;
    await ev(() => { window.__game.player.pos.y = 1.2; });
    await page.keyboard.down('KeyS');
    check(await until(() => !window.__game.player.climb && window.__game.player.pos.y < 0.5), 'did not get off the ladder at the bottom');
    await page.keyboard.up('KeyS');
  });

  // 짚라인: 높은 옥상에서 길 건너 낮은 옥상으로 (탑승 장면을 찍은 뒤 남은 구간 대부분은 건너뛴다)
  await step('zip', async () => {
    const Z = await ev(() => { const z = window.__game.zips[0]; return z && { x: z.p0.x, z: z.p0.z, dx: z.dir.x, dz: z.dir.z, hA: z.hA, drop: z.drop }; });
    if (!check(Z, 'no ziplines were generated')) return;
    out.zip = [Z.hA, Z.drop];
    await stand(Z.x, Z.hA, Z.z, Math.atan2(Z.dx, Z.dz));
    await page.waitForTimeout(300);
    await page.keyboard.press('KeyE');
    if (!check(await until(() => !!window.__game.player.zip, 60000), 'E did not hook onto the zipline')) return;
    await page.waitForTimeout(1500);
    await shot('13-zip');
    await ev(() => { const z = window.__game.player.zip; if (z) z.s = Math.max(z.s, z.Z.len - 8); });
    const zipped = await until(() => !window.__game.player.zip && window.__game.player.onGround);
    const land = await ev(() => window.__game.player.pos.y);
    check(zipped && Math.abs(land - (Z.hA - Z.drop)) < 0.3, `zipline ended at y=${land}, landing roof is ${Z.hA - Z.drop}`);
  });

  // 옥상 PKE 샘플 줍기
  await step('sample', async () => {
    const sm = await ev(() => { const G = window.__game, s = G.samples.find(q => !q.got); return s && { x: s.pos.x, y: s.pos.y, z: s.pos.z, n: G.save.samples.length }; });
    if (!check(sm, 'no rooftop samples left')) return;
    await stand(sm.x, sm.y, sm.z, null);
    check(await until(n => window.__game.save.samples.length > n, 120000, sm.n), 'rooftop sample was not collected');
  });

  // 오 박사 연구실: E로 열고 업그레이드 구매, 저장 확인
  await step('shop', async () => {
    await ev(() => { window.__game.player.money = 20000; });
    const sp = await ev(() => ({ x: window.__game.shop.pos.x, z: window.__game.shop.pos.z }));
    await stand(sp.x + 1.2, 0.15, sp.z + 1.2, null);
    await page.waitForTimeout(300);
    await page.keyboard.press('KeyE');
    if (!check(await until(() => window.__game.modal === 'shop', 60000), 'E did not open the workshop')) return;
    await page.click('#ups button[data-id="beam"]');
    await page.click('#ups button[data-id="armor"]');
    await shot('14-shop');
    const s = await ev(() => { const G = window.__game; return { beam: G.save.up.beam, armor: G.save.up.armor, maxHp: G.player.maxHp, money: G.player.money, rep: G.save.rep, stored: JSON.parse(localStorage.getItem('ghost-patrol-save-v1') || '{}') }; });
    check(s.beam === 1 && s.armor === 1 && s.maxHp === 125 && s.money === 16500, 'upgrades were not applied: ' + JSON.stringify(s));
    check(s.stored.up && s.stored.up.beam === 1 && s.stored.rep === s.rep && s.stored.money === 16500, 'progress was not saved');
    await page.keyboard.press('KeyE');
    check(await until(() => window.__game.modal === null, 60000), 'workshop did not close');
  });

  // 새로 고침 후 이어 하기
  await step('reload', async () => {
    const before = await ev(() => ({ rep: window.__game.save.rep, samples: window.__game.save.samples.length }));
    await page.reload();
    await page.waitForFunction(() => window.__game && window.__game.ghosts.length > 0, null, { timeout: 120000 });
    await page.waitForTimeout(800);
    await shot('15-continue');
    const c = await ev(() => { const G = window.__game, el = document.getElementById('saveInfo'); return { info: el.hidden ? '' : el.textContent, rep: G.save.rep, beam: G.save.up.beam, got: G.samples.filter(s => s.got).length }; });
    out.rep = c.rep;
    check(c.info.includes('평판 ' + before.rep) && c.rep === before.rep && c.beam === 1 && c.got === before.samples && c.got >= 1, 'saved progress was not restored: ' + JSON.stringify(c));
    await page.click('#go');
    await page.waitForTimeout(500);
    const r = await ev(() => ({ money: window.__game.player.money, maxHp: window.__game.player.maxHp }));
    check(r.money === 16500 && r.maxHp === 125, 'resumed game lost money or upgrades: ' + JSON.stringify(r));
  });

  const stats = await page.evaluate(() => { const G = window.__game; return { ghosts: G.ghosts.length, cars: G.cars.length, peds: G.peds.length, ladders: G.ladders.length, zips: G.zips.length, samples: G.samples.length }; });
  console.log(JSON.stringify({ r1, r2, r3, ...out, stats }));
  await browser.close();
  if (errors.length) { console.error('FAIL\n' + [...new Set(errors)].join('\n')); process.exit(1); }
  console.log('PASS');
})().catch(e => { console.error(e); if (errors.length) console.error([...new Set(errors)].join('\n')); process.exit(2); });
