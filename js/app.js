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
    zoom: false,
    sync: true,
    selected: ALL.slice(),
    nails: {}
  };
  ALL.forEach(function (id) { state.nails[id] = defaultDesign(); });

  var el = {};
  ['stage', 'fingers', 'designs', 'palette', 'arts', 'finishes', 'shapes', 'skins',
    'backdrops', 'length', 'len-label', 'color1', 'color2', 'looks', 'look-name',
    'btn-zoom', 'btn-png', 'btn-reset', 'btn-all', 'btn-save', 'chk-sync'
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

  /* ── 렌더 ── */
  function draw() {
    el.stage.innerHTML = R.renderSVG(state, { zoom: state.zoom });
    el.stage.querySelectorAll('.nail-hit').forEach(function (p) {
      p.addEventListener('click', function () { toggleFinger(p.dataset.finger); });
    });
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
    el['btn-zoom'].addEventListener('click', function () { state.zoom = !state.zoom; draw(); });
    el['btn-reset'].addEventListener('click', function () {
      ALL.forEach(function (id) { state.nails[id] = defaultDesign(); });
      state.sync = true;
      state.selected = ALL.slice();
      draw();
    });
    el['btn-png'].addEventListener('click', exportPNG);
    el['btn-save'].addEventListener('click', saveLook);
  }

  /* ── PNG 내보내기 ── */
  function exportPNG() {
    var scale = 2;
    var svg = R.renderSVG(state, { zoom: state.zoom, selectable: false, scale: scale });
    var box = (state.zoom ? R.VIEW_ZOOM : R.VIEW_FULL).split(' ').map(Number);
    var img = new Image();
    img.onload = function () {
      var canvas = document.createElement('canvas');
      canvas.width = box[2] * scale;
      canvas.height = box[3] * scale;
      canvas.getContext('2d').drawImage(img, 0, 0, canvas.width, canvas.height);
      canvas.toBlob(function (blob) {
        var a = document.createElement('a');
        a.href = URL.createObjectURL(blob);
        a.download = 'nail-simulation.png';
        a.click();
        URL.revokeObjectURL(a.href);
      });
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
