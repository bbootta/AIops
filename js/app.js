/* 상태 · UI 연결 · 저장 · PNG 내보내기 */
(function (NS) {
  'use strict';

  var G = NS.geom, D = NS.data, R = NS.render;
  var STORE = 'nailsim.looks';
  var ALL = G.FINGERS.map(function (f) { return f.id; });

  function designByName(name) {
    for (var i = 0; i < D.DESIGNS.length; i++) if (D.DESIGNS[i].name === name) return D.DESIGNS[i];
    return D.DESIGNS[0];
  }

  function defaultDesign() {
    var d = designByName('누드 글로시');   // 인덱스로 잡으면 프리셋을 추가할 때 조용히 어긋난다
    return {
      color: d.color, color2: d.color2, finish: d.finish,
      art: d.art, shape: d.shape, length: d.length, sheer: d.sheer || 1
    };
  }

  var state = {
    skin: 's2',
    backdrop: 'studio',
    mode: '2d',
    zoom: false,
    sync: true,
    selected: ALL.slice(),
    nails: {}
  };
  ALL.forEach(function (id) { state.nails[id] = defaultDesign(); });

  var el = {};
  ['stage', 'fingers', 'designs', 'palette', 'arts', 'finishes', 'shapes', 'skins',
    'backdrops', 'length', 'len-label', 'color1', 'color2', 'looks', 'look-name',
    'btn-zoom', 'btn-png', 'btn-reset', 'btn-all', 'btn-save', 'chk-sync',
    'btn-3d', 'stage-hint', 'stage-2d'
  ].forEach(function (id) { el[id] = document.getElementById(id); });

  /* 선택된 손가락 중 첫 번째 디자인을 컨트롤의 현재값으로 쓴다 */
  function current() {
    return state.nails[state.selected[0] || 'middle'];
  }

  /* 선택된 손가락(또는 전체)에 변경 적용 */
  function apply(patch) {
    var targets = state.sync ? ALL : state.selected;
    targets.forEach(function (id) {
      Object.keys(patch).forEach(function (k) { state.nails[id][k] = patch[k]; });
    });
    draw();
  }

  /* ── 렌더 ──
   * 2D 는 매번 SVG 문자열을 새로 만들고, 3D 는 캔버스를 그대로 두고 다시 그린다.
   * WebGL 컨텍스트는 브라우저가 개수를 제한하므로 한 번만 만들고 계속 쓴다 —
   * 모드를 오갈 때마다 새로 만들면 몇 번 만에 컨텍스트를 잃는다. */
  var gl3d = null;   // null = 아직 시도 안 함, false = 이 브라우저에서 불가

  function ensure3D() {
    if (gl3d === null) {
      gl3d = !!(NS.hand3d && NS.hand3d.init(el.stage, toggleFinger));
      if (gl3d) NS.hand3d.setRedraw(function () { NS.hand3d.draw(state); });
    }
    return gl3d;
  }

  function draw() {
    var use3d = state.mode === '3d' && ensure3D();
    if (!use3d) state.mode = '2d';
    el['stage-2d'].style.display = use3d ? 'none' : '';
    if (gl3d) NS.hand3d.canvas().style.display = use3d ? '' : 'none';

    if (use3d) {
      NS.hand3d.draw(state);
    } else {
      el['stage-2d'].innerHTML = R.renderSVG(state, { zoom: state.zoom });
      el['stage-2d'].querySelectorAll('.nail-hit').forEach(function (p) {
        p.addEventListener('click', function () { toggleFinger(p.dataset.finger); });
      });
    }
    syncControls();
  }

  /* 전체 적용 중에 손톱을 누르면 "이 손톱만 바꾸겠다"는 뜻으로 본다. */
  function toggleFinger(id) {
    if (state.sync) {
      state.sync = false;
      state.selected = [id];
    } else {
      var i = state.selected.indexOf(id);
      if (i >= 0) {
        if (state.selected.length > 1) state.selected.splice(i, 1);
      } else {
        state.selected.push(id);
      }
    }
    draw();
  }

  /* 컨트롤 상태를 현재 디자인에 맞춘다 */
  function syncControls() {
    var d = current();
    press(el.fingers, function (v) { return state.selected.indexOf(v) >= 0; });
    press(el.arts, function (v) { return v === d.art; });
    press(el.finishes, function (v) { return v === d.finish; });
    press(el.shapes, function (v) { return v === d.shape; });
    press(el.palette, function (v) { return v.toLowerCase() === d.color.toLowerCase(); });
    press(el.skins, function (v) { return v === state.skin; });
    press(el.backdrops, function (v) { return v === state.backdrop; });
    el.length.value = d.length;
    el['len-label'].textContent = G.LENGTHS[d.length].name;
    el.color1.value = d.color;
    el.color2.value = d.color2;
    el['btn-zoom'].setAttribute('aria-pressed', String(state.zoom));
    el['btn-3d'].setAttribute('aria-pressed', String(state.mode === '3d'));
    el['stage-hint'].textContent = state.mode === '3d'
      ? '드래그하면 돌려볼 수 있고, 휠로 확대합니다. 손톱을 누르면 그 손톱만 바꿔요'
      : '손톱을 누르면 그 손톱만 따로 바꿀 수 있어요';
    el['chk-sync'].checked = state.sync;
  }

  function press(container, isOn) {
    container.querySelectorAll('[data-val]').forEach(function (b) {
      b.setAttribute('aria-pressed', String(!!isOn(b.dataset.val)));
    });
  }

  /* ── UI 구성 ── */
  function chip(cls, val, label, title) {
    var b = document.createElement('button');
    b.type = 'button';
    b.className = cls;
    b.dataset.val = val;
    if (label) b.textContent = label;
    if (title) b.title = title;
    return b;
  }

  function buildUI() {
    G.FINGERS.forEach(function (f) { el.fingers.appendChild(chip('chip', f.id, f.name)); });
    el.fingers.addEventListener('click', function (e) {
      var b = e.target.closest('[data-val]');
      if (b) toggleFinger(b.dataset.val);
    });

    D.DESIGNS.forEach(function (d, i) {
      var b = chip('design', String(i), null, d.name);
      var dot = document.createElement('i');
      dot.style.background = 'linear-gradient(135deg,' + d.color2 + ' 0%,' + d.color + ' 55%)';
      b.appendChild(dot);
      b.appendChild(document.createTextNode(d.name));
      el.designs.appendChild(b);
    });
    el.designs.addEventListener('click', function (e) {
      var b = e.target.closest('[data-val]');
      if (!b) return;
      var d = D.DESIGNS[+b.dataset.val];
      apply({ color: d.color, color2: d.color2, finish: d.finish, art: d.art,
        shape: d.shape, length: d.length, sheer: d.sheer || 1 });
    });

    D.PALETTE.forEach(function (c) {
      var b = chip('swatch', c.hex, null, c.name);
      b.style.background = c.hex;
      el.palette.appendChild(b);
    });
    el.palette.addEventListener('click', function (e) {
      var b = e.target.closest('[data-val]');
      if (b) apply({ color: b.dataset.val });
    });

    D.ARTS.forEach(function (a) { el.arts.appendChild(chip('chip', a.id, a.name)); });
    el.arts.addEventListener('click', function (e) {
      var b = e.target.closest('[data-val]');
      if (b) apply({ art: b.dataset.val });
    });

    D.FINISHES.forEach(function (f) { el.finishes.appendChild(chip('chip', f.id, f.name)); });
    el.finishes.addEventListener('click', function (e) {
      var b = e.target.closest('[data-val]');
      if (b) apply({ finish: b.dataset.val });
    });

    Object.keys(G.SHAPES).forEach(function (k) {
      el.shapes.appendChild(chip('chip', k, G.SHAPES[k].name));
    });
    el.shapes.addEventListener('click', function (e) {
      var b = e.target.closest('[data-val]');
      if (b) apply({ shape: b.dataset.val });
    });

    D.SKINS.forEach(function (s) {
      var b = chip('swatch', s.id, null, s.name);
      b.style.background = s.base;
      el.skins.appendChild(b);
    });
    el.skins.addEventListener('click', function (e) {
      var b = e.target.closest('[data-val]');
      if (b) { state.skin = b.dataset.val; draw(); }
    });

    D.BACKDROPS.forEach(function (b) { el.backdrops.appendChild(chip('chip', b.id, b.name)); });
    el.backdrops.addEventListener('click', function (e) {
      var b = e.target.closest('[data-val]');
      if (b) { state.backdrop = b.dataset.val; draw(); }
    });

    el.length.addEventListener('input', function () { apply({ length: +el.length.value }); });
    el.color1.addEventListener('input', function () { apply({ color: el.color1.value }); });
    el.color2.addEventListener('input', function () { apply({ color2: el.color2.value }); });

    el['chk-sync'].addEventListener('change', function () {
      state.sync = el['chk-sync'].checked;
      if (state.sync) state.selected = ALL.slice();
      draw();
    });
    el['btn-all'].addEventListener('click', function () {
      state.sync = true;
      state.selected = ALL.slice();
      draw();
    });
    el['btn-3d'].addEventListener('click', function () {
      state.mode = state.mode === '3d' ? '2d' : '3d';
      draw();
      if (state.mode === '2d' && !gl3d) alert('이 브라우저에서는 WebGL을 쓸 수 없어 3D 보기를 열지 못했습니다.');
    });
    el['btn-zoom'].addEventListener('click', function () { state.zoom = !state.zoom; draw(); });
    el['btn-reset'].addEventListener('click', function () {
      ALL.forEach(function (id) { state.nails[id] = defaultDesign(); });
      state.sync = true;
      state.selected = ALL.slice();
      if (gl3d) NS.hand3d.reset();
      draw();
    });
    el['btn-png'].addEventListener('click', exportPNG);
    el['btn-save'].addEventListener('click', saveLook);
  }

  function download(blob) {
    var a = document.createElement('a');
    a.href = URL.createObjectURL(blob);
    a.download = 'nail-simulation.png';
    a.click();
    URL.revokeObjectURL(a.href);
  }

  /* ── PNG 내보내기 ── */
  function exportPNG() {
    if (state.mode === '3d' && gl3d) {
      NS.hand3d.draw(state);          // 캔버스 내용이 살아 있는 시점에 읽어야 한다
      NS.hand3d.canvas().toBlob(download);
      return;
    }
    var scale = 2;
    var svg = R.renderSVG(state, { zoom: state.zoom, selectable: false, scale: scale });
    var box = (state.zoom ? R.VIEW_ZOOM : R.VIEW_FULL).split(' ').map(Number);
    var img = new Image();
    img.onload = function () {
      var canvas = document.createElement('canvas');
      canvas.width = box[2] * scale;
      canvas.height = box[3] * scale;
      canvas.getContext('2d').drawImage(img, 0, 0, canvas.width, canvas.height);
      canvas.toBlob(download);
    };
    img.onerror = function () { alert('이미지를 만들 수 없습니다.'); };
    img.src = 'data:image/svg+xml;charset=utf-8,' + encodeURIComponent(svg);
  }

  /* ── 저장한 룩 ── */
  function readLooks() {
    try { return JSON.parse(localStorage.getItem(STORE)) || []; } catch (e) { return []; }
  }
  function writeLooks(list) {
    try { localStorage.setItem(STORE, JSON.stringify(list)); } catch (e) { /* 용량 초과 등은 무시 */ }
  }

  function saveLook() {
    var name = el['look-name'].value.trim() || '내 룩 ' + (readLooks().length + 1);
    var list = readLooks();
    list.push({ name: name, skin: state.skin, backdrop: state.backdrop, nails: state.nails });
    writeLooks(list);
    el['look-name'].value = '';
    renderLooks();
  }

  function renderLooks() {
    var list = readLooks();
    el.looks.innerHTML = '';
    if (!list.length) {
      var li = document.createElement('li');
      li.className = 'empty';
      li.textContent = '저장한 룩이 없습니다.';
      el.looks.appendChild(li);
      return;
    }
    list.forEach(function (look, i) {
      var li = document.createElement('li');
      var load = document.createElement('button');
      load.type = 'button';
      load.className = 'load';
      load.textContent = look.name;
      load.addEventListener('click', function () {
        state.skin = look.skin;
        state.backdrop = look.backdrop;
        ALL.forEach(function (id) {
          state.nails[id] = Object.assign(defaultDesign(), look.nails[id]);
        });
        draw();
      });
      var del = document.createElement('button');
      del.type = 'button';
      del.className = 'del';
      del.textContent = '삭제';
      del.addEventListener('click', function () {
        var l = readLooks();
        l.splice(i, 1);
        writeLooks(l);
        renderLooks();
      });
      li.appendChild(load);
      li.appendChild(del);
      el.looks.appendChild(li);
    });
  }

  buildUI();
  renderLooks();
  draw();
})(window.NailSim = window.NailSim || {});
