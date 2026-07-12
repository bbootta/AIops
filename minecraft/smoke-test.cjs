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
const THREE = new Proxy({}, { get(t, prop) { return prop === 'Vector3' ? Vec3 : prop === 'Vector2' ? Vec2 : P; } });

function makeCtx() { return { fillRect() {}, set fillStyle(v) {}, get fillStyle() { return ''; }, set strokeStyle(v) {}, beginPath() {}, moveTo() {}, lineTo() {}, stroke() {}, drawImage() {}, clearRect() {}, fillText() {} }; }
function makeEl(tag) {
  const el = {
    tagName: tag, _h: {}, style: {}, width: 16, height: 16, title: '', disabled: false, textContent: '', innerHTML: '',
    classList: { add() {}, remove() {}, toggle() {}, contains() { return false; } },
    addEventListener(type, fn) { (this._h[type] = this._h[type] || []).push(fn); }, removeEventListener() {},
    appendChild(c) { return c; }, getContext() { return makeCtx(); },
    getBoundingClientRect() { return { left: 0, top: 0, width: 100, height: 100 }; },
    cloneNode() { return makeEl(tag); },
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
  const runner = new Function('THREE', 'document', 'window', 'navigator', 'localStorage', 'performance', 'requestAnimationFrame', 'setInterval', 'addEventListener', 'console', src);
  runner(THREE, doc, win, navi, localStorage, perf, (fn) => { captured.loop = fn; }, () => 0, gAdd, console);
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
  // 활 차지(R) → 발사, 먹기(Q)
  fire(G.keydown, ev({ code: 'KeyR' })); step(2); fire(G.keyup, ev({ code: 'KeyR' }));
  fire(G.keydown, ev({ code: 'KeyQ' }));
  // 🤖 변신 1단계(아이언): 펄서 연사 → 미사일 → 레이저 + 카메라 프리셋/줌
  fire(G.keydown, ev({ code: 'KeyG' })); step(3);
  fire(doc._h.mousedown, ev({ button: 0 })); step(8); fire(doc._h.mouseup, ev({ button: 0 }));
  fire(doc._h.mousedown, ev({ button: 2 })); step(8); fire(doc._h.mouseup, ev({ button: 2 }));
  fire(G.keydown, ev({ code: 'KeyR' })); step(6); fire(G.keyup, ev({ code: 'KeyR' }));
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
try { runGame(null, 'A: 새 게임(오버월드)'); } catch (e) { fails++; console.log('  [A] FAIL:', (e && e.stack) || e); }
const saveB = JSON.stringify({
  curDim: 'overworld',
  dims: { overworld: { edits: [['0,11,0', 3], ['0,12,0', 16]], pos: { x: 0.5, y: 12, z: 0.5, yaw: 0, pitch: 0 }, crops: [] }, nether: { edits: [], pos: null, crops: [] } },
  slot: 0, health: 8, hunger: 4, inv: { 12: 9, 105: 5, 100: 3 }, tools: { pickaxe: true, bow: true }, dayTime: 50,
});
try {
  runGame(saveB, 'B: 포탈→네더 전이', ({ step }) => {
    step(120);
    const clock = elCache['clock'] && elCache['clock'].textContent;
    if (!/네더/.test(clock || '')) throw new Error('네더 전이 미발생 (clock="' + clock + '")');
    console.log('  [B] 네더 전이 확인됨');
  }, { noMove: true });
} catch (e) { fails++; console.log('  [B] FAIL:', (e && e.stack) || e); }

// C: 네더에 직접 입장(귀환 포탈 없음) 후 장시간 구동 — 적 스폰/추격/크리퍼 자폭·거미 벽타기 경로 실행
const saveC = JSON.stringify({
  curDim: 'nether',
  dims: { overworld: { edits: [], pos: null, crops: [] }, nether: { edits: [], pos: null, crops: [] } },
  slot: 0, health: 10, inv: {}, tools: {}, dayTime: 50,
});
try {
  runGame(saveC, 'C: 네더 장시간(적 AI)', ({ step }) => { step(800); }, { noMove: true });
} catch (e) { fails++; console.log('  [C] FAIL:', (e && e.stack) || e); }

console.log(fails ? `\nSMOKE FAILED (${fails})` : '\nSMOKE PASSED');
process.exit(fails ? 1 : 0);
