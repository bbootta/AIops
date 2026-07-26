'use strict';
// THREE·DOM을 모킹해 index.html의 게임 스크립트를 실제 실행하여 런타임 오류를 잡는 스모크 테스트.
// 실행: node minecraft/smoke-test.cjs  (구문검사가 못 잡는 미정의 참조/타입 오류 검출)
const fs = require('fs');
const path = require('path');

const html = fs.readFileSync(path.join(__dirname, 'index.html'), 'utf8');
const m = html.match(/<script type="module">([\s\S]*?)<\/script>/);
if (!m) { console.error('module script not found'); process.exit(2); }
const src = m[1].replace(/^import \* as THREE.*$/m, '');

function makeStub() {
  const fn = function () {};
  const P = new Proxy(fn, {
    get(t, prop) {
      if (prop === Symbol.toPrimitive) return () => 0;
      if (prop === Symbol.iterator) return () => ({ next: () => ({ done: true, value: undefined }) });
      if (typeof prop === 'symbol') return undefined;
      return P;
    },
    set() { return true; }, apply() { return P; }, construct() { return P; }, has() { return true; },
  });
  return P;
}
const P = makeStub();
const nn = (a) => (typeof a === 'number' ? a : 0);
class Vec3 {
  constructor(x = 0, y = 0, z = 0) { this.x = x; this.y = y; this.z = z; }
  set(x, y, z) { this.x = x; this.y = y; this.z = z; return this; }
  copy(v) { this.x = nn(v.x); this.y = nn(v.y); this.z = nn(v.z); return this; }
  add(v) { this.x += nn(v.x); this.y += nn(v.y); this.z += nn(v.z); return this; }
  sub(v) { this.x -= nn(v.x); this.y -= nn(v.y); this.z -= nn(v.z); return this; }
  addScaledVector(v, s) { this.x += nn(v.x) * s; this.y += nn(v.y) * s; this.z += nn(v.z) * s; return this; }
  multiplyScalar(s) { this.x *= s; this.y *= s; this.z *= s; return this; }
  normalize() { const l = Math.hypot(this.x, this.y, this.z) || 1; return this.multiplyScalar(1 / l); }
  lengthSq() { return this.x * this.x + this.y * this.y + this.z * this.z; }
  length() { return Math.hypot(this.x, this.y, this.z); }
  setScalar(s) { this.x = this.y = this.z = s; return this; }
  clone() { return new Vec3(this.x, this.y, this.z); }
  lookAt() { return this; }
}
class Vec2 { constructor(x = 0, y = 0) { this.x = x; this.y = y; } set(x, y) { this.x = x; this.y = y; return this; } }
// 카메라는 진짜 조준 방향을 돌려주는 최소 구현 — pickBlock/DDA가 실제로 지형을 맞혀
// 설치·채굴·발사 경로가 하니스에서 진짜로 실행되게 한다 (앞-아래 45도쯤 조준)
class Cam {
  constructor() { this.position = new Vec3(); this.rotation = { set() {}, order: '' }; this.quaternion = {}; this.fov = 75; this.aspect = 1; this.far = 300; }
  updateProjectionMatrix() {}
  lookAt() {}
  getWorldDirection(t) {
    t.x = 0.45; t.y = -0.85; t.z = 0.15;
    const l = Math.hypot(t.x, t.y, t.z);
    t.x /= l; t.y /= l; t.z /= l;
    return t;
  }
}
const THREE = new Proxy({}, { get(t, prop) { return prop === 'Vector3' ? Vec3 : prop === 'Vector2' ? Vec2 : prop === 'PerspectiveCamera' ? Cam : P; } });

function makeCtx() { return { fillRect() {}, set fillStyle(v) {}, get fillStyle() { return ''; }, set strokeStyle(v) {}, beginPath() {}, moveTo() {}, lineTo() {}, stroke() {}, drawImage() {}, clearRect() {}, fillText() {} }; }
function makeEl(tag) {
  const el = {
    tagName: tag, _h: {}, style: {}, width: 16, height: 16, title: '', disabled: false, textContent: '', innerHTML: '',
    classList: { add() {}, remove() {}, toggle() {}, contains() { return false; } },
    addEventListener(type, fn) { (this._h[type] = this._h[type] || []).push(fn); }, removeEventListener() {},
    appendChild(c) { (this.children = this.children || []).push(c); return c; }, getContext() { return makeCtx(); },
    getBoundingClientRect() { return { left: 0, top: 0, width: 100, height: 100 }; },
    cloneNode() { return makeEl(tag); }, scrollIntoView() {},
    requestPointerLock() { doc.pointerLockElement = el; fire(doc._h.pointerlockchange); }, focus() {}, click() {},
  };
  return el;
}
const elCache = {};
const doc = {
  _h: {}, pointerLockElement: null, body: makeEl('body'),
  getElementById(id) { return elCache[id] || (elCache[id] = makeEl('div')); },
  querySelector(sel) { return elCache[sel] || (elCache[sel] = makeEl('div')); },
  createElement(tag) { return makeEl(tag); },
  addEventListener(type, fn) { (this._h[type] = this._h[type] || []).push(fn); }, removeEventListener() {},
  exitPointerLock() { doc.pointerLockElement = null; fire(doc._h.pointerlockchange); },
};
const G = {};
const gAdd = (type, fn) => { (G[type] = G[type] || []).push(fn); };
const win = { innerWidth: 1280, innerHeight: 720, devicePixelRatio: 1, addEventListener: gAdd };
const navi = { maxTouchPoints: 0 };
const store = {};
const localStorage = { getItem(k) { return k in store ? store[k] : null; }, setItem(k, v) { store[k] = String(v); }, removeItem(k) { delete store[k]; } };
function fire(list, e) { if (list) for (const fn of list.slice()) fn(e || {}); }
function ev(extra) {
  return Object.assign({ preventDefault() {}, stopPropagation() {}, button: 0, code: '', key: '', deltaY: 1, movementX: 0, movementY: 0, clientX: 10, clientY: 10, identifier: 1, changedTouches: [{ identifier: 1, clientX: 10, clientY: 10 }] }, extra);
}

function runGame(saveJson, label, drive, opts) {
  opts = opts || {};
  for (const k in store) delete store[k];
  for (const k in G) delete G[k];
  for (const k in doc._h) delete doc._h[k];
  for (const k in elCache) delete elCache[k];
  doc.pointerLockElement = null;
  if (saveJson) store['mc_save_v5_s1'] = saveJson;
  const captured = {};
  let t = 0;
  const perf = { now: () => (t += 16.7) };
  // setTimeout은 동기 실행(부팅 지연·토스트 타이머가 테스트 안에서 즉시 돌도록)
  const syncTimeout = (fn) => { fn(); return 0; };
  const runner = new Function('THREE', 'document', 'window', 'navigator', 'localStorage', 'performance', 'requestAnimationFrame', 'setInterval', 'setTimeout', 'clearTimeout', 'addEventListener', 'console', src);
  runner(THREE, doc, win, navi, localStorage, perf, (fn) => { captured.loop = fn; }, () => 0, syncTimeout, () => {}, gAdd, console);
  const step = (n) => { for (let i = 0; i < n; i++) captured.loop(perf.now()); };
  step(2);
  fire(elCache['overlay'] && elCache['overlay']._h.click);
  if (!opts.noMove) {
    fire(G.keydown, ev({ code: 'KeyW', key: 'w' })); fire(G.keydown, ev({ code: 'KeyD', key: 'd' })); fire(G.keydown, ev({ code: 'ShiftLeft' }));
    step(10);
  }
  drive && drive({ step });
  fire(doc._h.mousedown, ev({ button: 0 })); step(3); fire(doc._h.mouseup, ev({ button: 0 }));
  for (let i = 0; i < 13; i++) { fire(G.wheel, ev({ deltaY: 1 })); fire(doc._h.mousedown, ev({ button: 2 })); fire(doc._h.mouseup, ev({ button: 2 })); }
  // 🎛 변신 핫키(Z/X/B/N/0) + Tab 픽커 + 아이콘 클릭 — 업적으로 실제 변신을 단언
  fire(G.keydown, ev({ code: 'KeyZ' })); step(2);
  if (!(store['mc_achv'] || '').includes('iron')) throw new Error('Z 핫키 변신 실패');
  fire(G.keydown, ev({ code: 'KeyZ' })); step(2);   // 같은 키 재입력 → 해제
  fire(G.keydown, ev({ code: 'KeyN' })); step(2);
  if (!(store['mc_achv'] || '').includes('witherform')) throw new Error('N 핫키 변신 실패');
  fire(G.keydown, ev({ code: 'KeyX' })); step(2);
  fire(G.keydown, ev({ code: 'Digit0' })); step(2); // 0 → 사람으로
  fire(G.keydown, ev({ code: 'Tab' })); step(2);    // 커서 풀고 아이콘 픽커 열기
  const chip3 = elCache['suitChip3']; if (chip3) fire(chip3._h.click, ev({}));
  if (!(store['mc_achv'] || '').includes('strange')) throw new Error('아이콘 클릭 변신 실패');
  step(2);
  fire(G.keydown, ev({ code: 'Digit0' })); step(2); // 다시 사람 상태로 되돌려 이후 시나리오 유지
  // 활 차지(R) → 발사, 먹기(Q)
  fire(G.keydown, ev({ code: 'KeyR' })); step(2); fire(G.keyup, ev({ code: 'KeyR' }));
  fire(G.keydown, ev({ code: 'KeyQ' }));
  // 🤖 변신 1단계(아이언): 펄서 연사 → 미사일 → 레이저 + 카메라 프리셋/줌
  fire(G.keydown, ev({ code: 'KeyG' })); step(3);
  fire(doc._h.mousedown, ev({ button: 0 })); step(8); fire(doc._h.mouseup, ev({ button: 0 }));
  fire(doc._h.mousedown, ev({ button: 2 })); step(8); fire(doc._h.mouseup, ev({ button: 2 }));
  fire(G.keydown, ev({ code: 'KeyR' })); step(6); fire(G.keyup, ev({ code: 'KeyR' }));
  fire(G.keydown, ev({ code: 'KeyF' })); step(4); // ✨ 광역 필살기 (슈트 중 F)
  for (let i = 0; i < 5; i++) { fire(G.keydown, ev({ code: 'KeyV' })); step(2); }
  fire(G.wheel, ev({ deltaY: 1 })); fire(G.wheel, ev({ deltaY: -1 })); step(3);
  // Alt+마우스 자유 궤도
  fire(G.keydown, ev({ code: 'AltLeft' }));
  fire(doc._h.mousemove, ev({ movementX: 40, movementY: 15 })); step(3);
  fire(G.keyup, ev({ code: 'AltLeft' }));
  // 🦾 변신 2단계(헐크버스터): 강화 펄서/미사일
  fire(G.keydown, ev({ code: 'KeyG' })); step(3);
  fire(doc._h.mousedown, ev({ button: 0 })); step(8); fire(doc._h.mouseup, ev({ button: 0 }));
  fire(doc._h.mousedown, ev({ button: 2 })); step(10); fire(doc._h.mouseup, ev({ button: 2 }));
  step(8);
  // 🔮 변신 3단계(닥터 스트레인지): 마법 미사일 → 순간이동 → 시간 정지 → 해제
  fire(G.keydown, ev({ code: 'KeyG' })); step(3);
  fire(doc._h.mousedown, ev({ button: 0 })); step(6); fire(doc._h.mouseup, ev({ button: 0 }));
  fire(doc._h.mousedown, ev({ button: 2 })); step(3); fire(doc._h.mouseup, ev({ button: 2 }));
  fire(G.keydown, ev({ code: 'KeyR' })); step(8); fire(G.keyup, ev({ code: 'KeyR' }));
  step(5);
  // 🌪 변신 4단계(위더 스톰): 폭발 스컬 연발 → 미사일 → 레이저 → 필살(스컬 폭풍) → 해제
  fire(G.keydown, ev({ code: 'KeyG' })); step(3);
  fire(doc._h.mousedown, ev({ button: 0 })); step(10); fire(doc._h.mouseup, ev({ button: 0 }));
  fire(doc._h.mousedown, ev({ button: 2 })); step(8); fire(doc._h.mouseup, ev({ button: 2 }));
  fire(G.keydown, ev({ code: 'KeyR' })); step(5); fire(G.keyup, ev({ code: 'KeyR' }));
  fire(G.keydown, ev({ code: 'KeyF' })); step(10);
  fire(G.keydown, ev({ code: 'KeyG' })); step(2);
  // 모바일 핫바 슬라이드
  const hb = elCache['hotbar']; if (hb) { fire(hb._h.touchstart, ev({})); fire(hb._h.touchmove, ev({ clientX: 80 })); }
  fire(G.keydown, ev({ code: 'KeyC' })); fire(G.keydown, ev({ code: 'KeyC' }));
  fire(G.keydown, ev({ code: 'KeyE' })); fire(G.keydown, ev({ code: 'KeyE' }));
  fire(G.keydown, ev({ code: 'KeyF' })); fire(G.keydown, ev({ code: 'KeyF' }));
  fire(G.keydown, ev({ code: 'KeyM' })); fire(G.keydown, ev({ code: 'KeyM' }));
  for (let n = 1; n <= 9; n++) fire(G.keydown, ev({ code: 'Digit' + n, key: String(n) }));
  // 설정 슬라이더/체크박스 핸들러 실행
  ['optSens', 'optVol', 'optView', 'optJoy'].forEach((id) => { const el = elCache[id]; if (el) { el.value = 30; fire(el._h.input); } });
  // 튜토리얼 말풍선 건너뛰기 경로
  const tut = elCache['tut']; if (tut) fire(tut._h.click);
  // 업적 패널 열기/닫기
  const ab = elCache['achvBtn']; if (ab) { fire(ab._h.click, ev({})); fire(ab._h.click, ev({})); }
  const mu = elCache['optMusic']; if (mu) { mu.checked = !mu.checked; fire(mu._h.change); }
  const fr = elCache['optFreeze']; if (fr) { fr.checked = false; fire(fr._h.change); }
  // 평화 모드 켜고 진행 (몬스터 소멸·허기 고정 경로), 자동 점프 토글
  const aj = elCache['optAutoJump']; if (aj) { aj.checked = true; fire(aj._h.change); }
  const pc = elCache['optPeace']; if (pc) { pc.checked = true; fire(pc._h.change); }
  step(30);
  if (pc) { pc.checked = false; fire(pc._h.change); }
  step(5); fire(G.keyup, ev({ code: 'KeyW' })); fire(G.blur);
  console.log(`  [${label}] OK`);
}

let fails = 0;
try {
  runGame(null, 'A: 새 게임(오버월드)', ({ step }) => {
    step(90); // 마을 활성화(1초 주기) 대기
    const achv = store['mc_achv'] || '[]';
    if (!achv.includes('village')) throw new Error('스폰 근처 마을 미생성 (achv=' + achv + ')');
    const texts = ((elCache['toasts'] && elCache['toasts'].children) || []).map((e) => e.textContent || '');
    const line = texts.find((t) => t.includes('마을 발견'));
    if (!line) throw new Error('마을 토스트 없음: ' + JSON.stringify(texts));
    const m = line.match(/주민 (\d+)명 · 가축 (\d+)마리/);
    if (!m || +m[1] < 1 || +m[2] < 1) throw new Error('주민/가축이 안 생김: ' + line);
    console.log('  [A] 🏘 마을 생성 + ' + line.replace(/^.*🏘 /, '🏘 ') + ' 확인됨');
  });
} catch (e) { fails++; console.log('  [A] FAIL:', (e && e.stack) || e); }
const saveB = JSON.stringify({
  curDim: 'overworld',
  dims: {
    overworld: { edits: [['0,11,0', 3], ['0,12,0', 30]], pos: { x: 0.5, y: 12, z: 0.5, yaw: 0, pitch: 0 }, crops: [] },
    nether: { edits: [['0,10,0', 31], ['0,12,0', 31], ['0,14,0', 31], ['0,16,0', 31]], pos: null, crops: [] },
  },
  slot: 0, health: 8, hunger: 4, inv: { 12: 9, 105: 5, 100: 3 }, tools: { pickaxe: true, bow: true }, dayTime: 50,
});
try {
  runGame(saveB, 'B: 포탈→네더 전이', ({ step }) => {
    step(120);
    const clock = elCache['clock'] && elCache['clock'].textContent;
    if (!/네더/.test(clock || '')) throw new Error('네더 전이 미발생 (clock="' + clock + '")');
    console.log('  [B] 🔥 빨간 포탈 → 네더 전이 확인됨');
    // 네더 스폰에 미리 깔아 둔 보라 포탈(31)로 → 보이드 (색=목적지 확인)
    step(320);
    const achvRaw = store['mc_achv'] || '[]';
    if (!achvRaw.includes('void')) throw new Error('보라 포탈 → 보이드 전이 미발생 (achv=' + achvRaw + ')');
    console.log('  [B] 🌌 보라 포탈 → 보이드 전이 확인됨');
  }, { noMove: true });
} catch (e) { fails++; console.log('  [B] FAIL:', (e && e.stack) || e); }

// C: 네더에 직접 입장(귀환 포탈 없음) 후 장시간 구동 — 적 스폰/추격/크리퍼 자폭·거미 벽타기 경로 실행
const saveC = JSON.stringify({
  curDim: 'nether',
  dims: { overworld: { edits: [], pos: null, crops: [] }, nether: { edits: [], pos: null, crops: [] } },
  slot: 5, hotbar: [1, 2, 3, 10, 20, 26, 27, 28, 29],
  health: 10, inv: { 26: 6, 27: 3, 28: 3, 29: 3 }, tools: {}, dayTime: 50,
});
try {
  runGame(saveC, 'C: 네더 장시간(적 AI + TNT 4종)', ({ step }) => {
    // 공용: 슬롯 선택 → 설치 → 캐서 점화 → 도화선 대기, 업적으로 폭발을 단언
    // (직전 폭발 크레이터로 낙하 중일 수 있어 안정화 후 재시도)
    const bomb = (digit, id, fuseSteps) => {
      fire(G.keydown, ev({ code: 'Digit' + digit, key: String(digit) }));
      for (let a = 0; a < 6; a++) {
        if ((store['mc_achv'] || '').includes(id)) return true;
        step(50); // 착지·안정화
        fire(doc._h.mousedown, ev({ button: 2 })); fire(doc._h.mouseup, ev({ button: 2 })); step(2);
        fire(doc._h.mousedown, ev({ button: 0 })); step(26); fire(doc._h.mouseup, ev({ button: 0 }));
        step(fuseSteps);
      }
      return (store['mc_achv'] || '').includes(id);
    };
    if (!bomb(6, 'tnt', 130)) throw new Error('TNT 폭발 미발생 (achv=' + (store['mc_achv'] || '[]') + ')');
    console.log('  [C] TNT 설치→점화→대폭발 확인됨');
    if (!bomb(7, 'meganuke', 210)) throw new Error('슈퍼 TNT 폭발 미발생');
    console.log('  [C] 💥 슈퍼 TNT 12500% 폭발 확인됨');
    if (!bomb(8, 'lightning', 170)) throw new Error('번개 TNT 폭발 미발생');
    console.log('  [C] ⚡ 번개 TNT 낙뢰 확인됨');
    if (!bomb(9, 'quake', 300)) throw new Error('지진 TNT 폭발 미발생');
    console.log('  [C] 🌋 지진 TNT 충격파 확인됨');
    // 🐷 네더 스폰 믹스의 피글린 — 첫 조우 업적으로 스폰 경로를 단언
    for (let i = 0; i < 80 && !(store['mc_achv'] || '').includes('piglin'); i++) step(40);
    if (!(store['mc_achv'] || '').includes('piglin')) throw new Error('피글린 스폰 미발생 (achv=' + (store['mc_achv'] || '[]') + ')');
    console.log('  [C] 🐷 피글린 스폰 확인됨');
    step(250);
  }, { noMove: true });
} catch (e) { fails++; console.log('  [C] FAIL:', (e && e.stack) || e); }

// D: 모바일(터치) — 핫바가 전체 아이템을 담고, 9칸 밖의 💥 슈퍼 TNT도 눌러서 쓸 수 있는지
const saveD = JSON.stringify({
  curDim: 'nether',
  dims: { overworld: { edits: [], pos: null, crops: [] }, nether: { edits: [], pos: null, crops: [] } },
  slot: 0, health: 10, inv: { 27: 5 }, tools: {}, dayTime: 50,
});
navi.maxTouchPoints = 1; // isTouch → 모바일 UI 경로
try {
  runGame(saveD, 'D: 모바일 전체 아이템 핫바', ({ step }) => {
    const slots = (elCache['hotbar'] && elCache['hotbar'].children) || [];
    if (slots.length < 20) throw new Error('모바일 핫바에 아이템이 다 없음: ' + slots.length);
    const i = slots.findIndex((el) => (el.title || '').includes('슈퍼 TNT'));
    if (i < 9) throw new Error('슈퍼 TNT가 9칸 안에 있어 검증 의미 없음 (idx=' + i + ')');
    fire(slots[i]._h.click, ev({})); // 칸을 눌러 선택 (슬라이드로 도달하는 자리)
    for (let a = 0; a < 6 && !(store['mc_achv'] || '').includes('meganuke'); a++) {
      step(50);
      fire(elCache['btnPlace']._h.touchstart, ev({})); step(2);
      fire(elCache['btnBreak']._h.touchstart, ev({})); step(26); fire(elCache['btnBreak']._h.touchend, ev({}));
      step(210);
    }
    if (!(store['mc_achv'] || '').includes('meganuke')) throw new Error('모바일에서 슈퍼 TNT 사용 실패');
    console.log('  [D] 📱 9칸 밖 슈퍼 TNT 선택→설치→폭발 확인됨 (핫바 ' + slots.length + '칸)');
  }, { noMove: true });
} catch (e) { fails++; console.log('  [D] FAIL:', (e && e.stack) || e); }
navi.maxTouchPoints = 0;

// E: ⚔ 공성전 — 금색 포탈로 입장, 웨이브 스폰, 공성군이 성벽/코어를 실제로 공격하는지
const saveE = JSON.stringify({
  curDim: 'overworld',
  dims: { overworld: { edits: [['0,11,0', 3], ['0,12,0', 32]], pos: { x: 0.5, y: 12, z: 0.5, yaw: 0, pitch: 0 }, crops: [] } },
  slot: 2, health: 10, inv: {}, tools: {}, dayTime: 50,
});
try {
  runGame(saveE, 'E: ⚔ 공성전(금색 포탈)', ({ step }) => {
    step(120);
    const clock = () => (elCache['clock'] && elCache['clock'].textContent) || '';
    if (!/공성전/.test(clock())) throw new Error('공성전 맵 진입 실패 (clock="' + clock() + '")');
    console.log('  [E] ⚔ 금색 포탈 → 공성전 맵 진입 확인됨');
    let peak = 0, wave = 0;
    for (let i = 0; i < 60; i++) {
      step(30);
      const m = clock().match(/(\d+)웨이브 · 적 (\d+)/);
      if (m) { wave = +m[1]; peak = Math.max(peak, +m[2]); }
      if (peak >= 95) break;
    }
    if (wave < 1 || peak < 95) throw new Error('100마리 웨이브 미출현 (최대 ' + peak + '명, clock="' + clock() + '")');
    console.log(`  [E] ⚔ ${wave}웨이브 · 공성군 ${peak}명 동시 출현 확인됨`);
    // 성벽까지 진군해 성벽/코어를 때리는지 (코어 체력 감소 또는 성벽 블록 파괴)
    const coreOf = () => { const h = (elCache['health'] && elCache['health'].innerHTML) || ''; const c = h.match(/🏰[^0-9]*(\d+)/); return c ? +c[1] : -1; };
    const core0 = coreOf();
    if (core0 < 100) throw new Error('코어 체력 표시 이상: ' + core0);
    let hit = false;
    for (let i = 0; i < 60 && !hit; i++) { step(60); hit = coreOf() < core0; }
    if (!hit) throw new Error('공성군이 코어를 공격하지 못함 (core=' + coreOf() + ')');
    console.log('  [E] 🏰 공성군이 성벽을 뚫고 코어를 공격함 확인됨 (코어 ' + coreOf() + ')');
    // 코어가 무너지면 잃는 것 없이 1웨이브부터 재시작되는지 (소프트락 방지)
    let reset = false;
    for (let i = 0; i < 120 && !reset; i++) { step(60); reset = /0웨이브/.test(clock()) && coreOf() === core0; }
    if (!reset) throw new Error('코어 함락 후 재시작 실패 (clock="' + clock() + '", core=' + coreOf() + ')');
    let again = false;
    for (let i = 0; i < 40 && !again; i++) { step(60); again = /[1-9]웨이브 · 적 [1-9]/.test(clock()); }
    if (!again) throw new Error('재시작 후 웨이브 미시작 (clock="' + clock() + '")');
    console.log('  [E] 🔁 코어 함락 → 성 복구 → 다음 웨이브 재개 확인됨');
  }, { noMove: true });
} catch (e) { fails++; console.log('  [E] FAIL:', (e && e.stack) || e); }

// F: 🌪 거대 위더 스톰 — 밤의 오버월드에서 등장(난수 고정으로 분기 강제)하고 대형 광선을 쏘는지
const saveF = JSON.stringify({
  curDim: 'overworld',
  dims: { overworld: { edits: [], pos: null, crops: [] } },
  slot: 3, health: 10, inv: {}, tools: {}, dayTime: 130,
});
try {
  runGame(saveF, 'F: 🌪 거대 위더 스톰', ({ step }) => {
    const realRandom = Math.random;
    Math.random = () => 0.02; // 보스 등장 분기를 강제 (등장 확률 7% → 위더 30%)
    step(400);
    Math.random = realRandom;
    const name = (elCache['bossName'] && elCache['bossName'].textContent) || '';
    if (!/위더 스톰/.test(name)) throw new Error('위더 스톰 미등장 (boss="' + name + '")');
    if (!/거대/.test(name)) throw new Error('거대화 미적용 (boss="' + name + '")');
    console.log('  [F] 🌪 거대 위더 스톰 등장 확인됨 (' + name + ')');
    const toasted = () => ((elCache['toasts'] && elCache['toasts'].children) || []).map((e) => e.textContent || '');
    let beam = false;
    for (let i = 0; i < 40 && !beam; i++) { step(60); beam = toasted().some((t) => /광선/.test(t)); }
    if (!beam) throw new Error('대형 광선 미발사');
    step(180); // 광선 지속 중 지형 파괴·피해 경로 실행
    console.log('  [F] 💜 대형 광선 발사 확인됨 (굵기 8칸)');
  }, { noMove: true });
} catch (e) { fails++; console.log('  [F] FAIL:', (e && e.stack) || e); }

console.log(fails ? `\nSMOKE FAILED (${fails})` : '\nSMOKE PASSED');
process.exit(fails ? 1 : 0);
