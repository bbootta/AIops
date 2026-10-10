'use strict';
// 실제 크로미움에서 게임을 띄워 런타임 오류 없이 핵심 루프(빔 → 기절 → 트랩 포획, 보손 폭발, 차량 탈취·주행), 달리기·제트팩·초대형 게틀링,
// 운전 중 창밖 사격과 공격용 특수차량 인터셉터, 의뢰 4종, 경찰 추격·체포, 사다리·짚라인·옥상 샘플, 오 박사 상점, 저장·이어 하기가 돌아가는지 확인하는 스모크 테스트.
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
  // GPU 없이 소프트웨어로 그리는 환경에서는 한 장에 30초(기본 제한)를 넘기기도 한다
  const shot = async n => { if (shotDir) await page.screenshot({ path: path.join(shotDir, n + '.png'), timeout: 180000 }); };
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

  // 달리기: 본부 앞마당에서 Shift + W로 달리기 속도까지 올린다
  await step('run', async () => {
    await ev(() => { const G = window.__game, H = G.lots[4][4], P = G.player; P.pos.set(H.cx - 6, 0.15, H.cz + 16); P.vel.set(0, 0, 0); P.yaw = Math.atan2(6, -22); P.pitch = -0.1; });
    await page.keyboard.down('ShiftLeft'); await page.keyboard.down('KeyW');
    const ran = await until(() => { const P = window.__game.player; return Math.hypot(P.vel.x, P.vel.z) > 9.5 && P.runK > 0.7; }, 120000);
    await page.keyboard.up('KeyW'); await page.keyboard.up('ShiftLeft');
    check(ran, 'sprinting did not reach running speed');
    await until(() => { const P = window.__game.player; return Math.hypot(P.vel.x, P.vel.z) < 0.5; }, 60000);
  });

  // 제트팩: Space를 누르고 있으면 날아오르며 연료를 쓰고, 놓으면 자동 감속 분사로 다치지 않고 내려앉은 뒤 연료가 다시 찬다
  await step('jetpack', async () => {
    const hp0 = await ev(() => window.__game.player.hp);
    await page.keyboard.down('Space');
    const flew = await until(() => window.__game.player.jet && window.__game.player.pos.y > 10);
    const fuel = await ev(() => window.__game.player.fuel / window.__game.player.fuelMax);
    await shot('5b-jetpack');
    await page.keyboard.up('Space');
    if (!check(flew, 'holding Space did not fly the jetpack')) return;
    check(fuel < 0.95, 'jetpack flight did not use fuel');
    if (!check(await until(() => window.__game.player.onGround), 'did not land after the jetpack flight')) return;
    const hp1 = await ev(() => window.__game.player.hp);
    out.jet = +(hp0 - hp1).toFixed(1);
    check(hp0 - hp1 < 1, `landing after the jetpack flight cost ${hp0 - hp1} hp`);
    check(await until(() => window.__game.player.fuel >= window.__game.player.fuelMax, 120000), 'jetpack fuel did not refill on the ground');
  });

  // 초대형 게틀링: 총열이 돈 뒤 연사해 유령을 맞히고, 탄피가 튀고, 팩이 달아오른다
  await step('gatling', async () => {
    await page.keyboard.press('Digit4');
    const place = () => ev(() => { const G = window.__game, a = G.computeAim(), g = G.ghosts.find(x => x.type !== 'boss' && x.state !== 'captured'); g.state = 'hunt'; g.spawnT = 0; g.pos.copy(a.o).addScaledVector(a.dir, 13); g.vel.set(0, 0, 0); g.atk = 99; window.__tg = g; return g.hp; });
    await ev(() => { window.__game.player.pitch = 0.05; window.__game.player.heat = 0; });
    const hp0 = await place();
    await page.mouse.down();
    const fired = await until(() => window.__game.gat.n > 25);
    await place().catch(() => {});
    await shot('5c-gatling');
    const g = await ev(() => { const G = window.__game; return { weapon: G.player.weapon, n: G.gat.n, spin: G.gat.spin, casings: G.casings.length, heat: G.player.heat, hp: window.__tg.hp, wanted: G.wanted }; });
    await page.mouse.up();
    out.gat = [g.n, +(hp0 - g.hp).toFixed(1), +g.heat.toFixed(1)];
    check(fired && g.weapon === 3 && g.spin > 0.7, 'minigun did not spin up and fire: ' + JSON.stringify(g));
    check(g.hp < hp0, 'minigun rounds did not hurt the ghost');
    check(g.casings > 0, 'minigun did not eject casings');
    check(g.heat > 0, 'minigun did not heat the pack');
    check(g.wanted === 0, 'shooting a ghost in the HQ yard raised the wanted level');
    check(await until(() => window.__game.gat.spin < 0.05, 60000), 'minigun barrels did not spin down');
    await page.keyboard.press('Digit1');
  });

  // 차 앞 조준선에 유령을 세운다. fresh 이면 기력이 찬 새 유령을 쓴다
  const placeAhead = (dist, fresh) => ev(([dist, fresh]) => {
    const G = window.__game, a = G.computeAim(); let g = window.__tg;
    if (fresh || !g || !G.ghosts.includes(g) || g.state === 'captured') { g = G.ghosts.find(x => x.type !== 'boss' && x.state !== 'captured'); g.state = 'hunt'; g.hp = g.maxHp; window.__tg = g; }
    g.spawnT = 0; g.pos.copy(a.o).addScaledVector(a.dir, a.tMin + dist); g.vel.set(0, 0, 0); g.atk = 99; return g.hp;
  }, [dist, !!fresh]);

  // 운전 중 창밖 사격: 차에서 발사를 누르면 운전석 창밖으로 상체를 내밀고 지금 고른 무기(빔)로 차 앞의 유령을 붙잡는다
  await step('driveby', async () => {
    await ev(() => { const G = window.__game, w = G.cars.find(c => c.type === 'wagon'); G.player.pos.set(w.pos.x - 1.5, 0.15, w.pos.z); G.player.vel.set(0, 0, 0); G.player.heat = 0; G.player.pitch = 0; });
    await page.waitForTimeout(300);
    await page.keyboard.press('KeyF');
    if (!check(await until(() => !!window.__game.player.car, 60000), 'could not get into the wagon for the drive-by')) return;
    const hp0 = await placeAhead(12, true);
    await page.mouse.down();
    let leaned = false;
    for (let i = 0; i < 40 && !leaned; i++) { await placeAhead(12); leaned = await until(() => { const G = window.__game; return !!G.beam.lock && G.leanK > 0.9; }, 3000); }
    await until(h => window.__tg.hp < h, 60000, hp0);
    await shot('5d-driveby');
    const d = await ev(() => { const G = window.__game; return { car: !!G.player.car, lean: G.leanK, lock: !!G.beam.lock, on: G.beam.on, hp: window.__tg.hp, cross: !document.getElementById('cross').hidden }; });
    await page.mouse.up();
    out.driveby = [+(hp0 - d.hp).toFixed(1), +d.lean.toFixed(2)];
    check(leaned && d.car && d.on, 'firing from the car did not lean out and lock the beam: ' + JSON.stringify(d));
    check(d.hp < hp0, 'the beam fired from the car did not hurt the ghost');
    check(d.cross, 'crosshair was hidden while shooting from the car');
    check(await until(() => window.__game.leanK < 0.1, 60000), 'the driver did not sit back in after releasing fire');
    await page.keyboard.press('KeyF');
    await until(() => !window.__game.player.car, 60000);
  });

  // 인터셉터: 본부 앞마당에서 기다리다가, 포탑 기관포로 유령을 맞히며 달아오르고, 유도 미사일이 쫓아가 터지고, 장갑이 피해를 줄이고, 부서지면 본부에 다시 놓인다
  await step('interceptor', async () => {
    const I0 = await ev(() => { const I = window.__game.interceptor; return { off: +I.pos.distanceTo(I.home).toFixed(2), ammo: I.ammo, wrecked: I.wrecked }; });
    check(I0.off < 3 && I0.ammo === 8 && !I0.wrecked, 'interceptor is not waiting at HQ: ' + JSON.stringify(I0));
    await ev(() => { const G = window.__game, I = G.interceptor, P = G.player; P.pos.set(I.pos.x + Math.cos(I.h) * 1.9, 0.15, I.pos.z - Math.sin(I.h) * 1.9); P.vel.set(0, 0, 0); P.pitch = 0.02; });
    await page.waitForTimeout(300);
    await page.keyboard.press('KeyF');
    if (!check(await until(() => window.__game.player.car === window.__game.interceptor, 60000), 'F did not board the interceptor')) return;
    check(await until(() => !document.getElementById('veh').hidden && document.getElementById('slots').hidden, 60000), 'interceptor HUD did not replace the weapon slots');
    const hp0 = await placeAhead(18, true);
    await page.mouse.down();
    const fired = await until(() => window.__game.interceptor.shots > 12);
    await placeAhead(18).catch(() => {});
    await until(h => window.__tg.hp < h, 60000, hp0);
    await shot('5e-interceptor');
    const k = await ev(() => { const I = window.__game.interceptor; return { shots: I.shots, heat: I.heat, hp: window.__tg.hp, lean: window.__game.leanK }; });
    await page.mouse.up();
    out.cannon = [k.shots, +(hp0 - k.hp).toFixed(1), +k.heat.toFixed(1)];
    check(fired && k.heat > 0, 'turret cannon did not fire and heat up: ' + JSON.stringify(k));
    check(k.hp < hp0, 'turret cannon did not hurt the ghost');
    check(k.lean === 0, 'the driver leaned out of the interceptor');
    // 유도 미사일: 조준선의 유령을 쫓아가 터진다
    const hp1 = await placeAhead(26, true);
    await page.mouse.down({ button: 'right' });
    let launched = false;
    for (let i = 0; i < 40 && !launched; i++) { await placeAhead(26); launched = await until(() => window.__game.projs.some(p => p.kind === 'missile'), 3000); }
    await page.mouse.up({ button: 'right' });
    const m = await ev(() => { const G = window.__game, p = G.projs.find(q => q.kind === 'missile'); return { ammo: G.interceptor.ammo, homing: !!p && p.tgt === window.__tg }; });
    await shot('5f-missile');
    if (!check(launched && m.ammo < 8, 'right click did not launch a missile: ' + JSON.stringify(m))) return;
    check(m.homing, 'missile did not lock onto the ghost under the crosshair');
    check(await until(() => !window.__game.projs.some(p => p.kind === 'missile'), 120000), 'missile never hit anything');
    const hp2 = await ev(() => window.__tg.hp);
    out.missile = +(hp1 - hp2).toFixed(1);
    check(hp2 < hp1, 'missile did not hurt the ghost');
    check(await until(a => window.__game.interceptor.ammo > a, 240000, m.ammo), 'missile pods did not reload');
    // 장갑과 재배치
    const taken = await ev(() => { const I = window.__game.interceptor, h = I.hp; I.damage(40); const t = h - I.hp; I.hp = h; return t; });
    check(Math.abs(taken - 14) < 0.01, `armor let ${taken} of 40 damage through`);
    await page.keyboard.press('KeyF');
    await until(() => !window.__game.player.car, 60000);
    await ev(() => { const G = window.__game, I = G.interceptor; G.player.pos.set(I.home.x + 30, 0.15, I.home.z + 12); I.damage(1e6); });
    if (!check(await ev(() => window.__game.interceptor.wrecked), 'interceptor did not wreck')) return;
    await ev(() => { window.__game.interceptor.wreckT = 11; });
    check(await until(() => { const I = window.__game.interceptor; return !I.wrecked && I.hp === 100 && I.ammo === 8 && I.pos.distanceTo(I.home) < 0.01; }, 120000), 'a new interceptor did not appear at HQ');
    await ev(() => window.__game.clearWanted());
  });

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
    const pz = await ev(() => { const G = window.__game; G.startMission(G.givers.find(x => x.kind === 'possessed')); const c = G.mission.car; G.player.pos.set(c.pos.x + 7, 0.15, c.pos.z + 7); G.player.yaw = Math.atan2(-7, -7); window.__taxi = c; const base = (G.cars.find(o => o.type === c.type && o !== c) || c).T.top; return { possessed: !!c.possessed, top: c.T.top, base }; });
    check(pz.possessed && pz.top > pz.base, 'possessed taxi was not set up: ' + JSON.stringify(pz));
    await ev(() => window.__game.mission.car.damage(200));
    if (!check(await until(() => { const m = window.__game.mission; return m && m.ghost && m.ghost.state === 'stunned' && m.ghost.name === '택시 귀신'; }), 'possessed taxi did not release its ghost')) return;
    await until(() => document.getElementById('misO').textContent.includes('택시 귀신'), 60000);
    await shot('8-possessed');
    await ev(() => { window.__ghost = window.__game.mission.ghost; window.__game.endMission(false, 'test'); });
    const pz2 = await ev(() => ({ gone: !window.__game.ghosts.includes(window.__ghost), calm: !window.__taxi.possessed, top: window.__taxi.T.top }));
    check(pz2.gone && pz2.calm && pz2.top === pz.base, 'failed taxi mission did not clean up: ' + JSON.stringify(pz2));
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
