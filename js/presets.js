/* 피부톤 · 컬러 팔레트 · 마감 · 아트 · 추천 디자인 프리셋 + 색상 유틸 */
(function (NS) {
  'use strict';

  /* ── 색상 유틸 ── */
  function hex2rgb(h) {
    h = String(h).replace('#', '');
    if (h.length === 3) h = h[0] + h[0] + h[1] + h[1] + h[2] + h[2];
    var n = parseInt(h, 16);
    return { r: (n >> 16) & 255, g: (n >> 8) & 255, b: n & 255 };
  }
  function rgb2hex(c) {
    var v = function (x) { return Math.max(0, Math.min(255, Math.round(x))).toString(16).padStart(2, '0'); };
    return '#' + v(c.r) + v(c.g) + v(c.b);
  }
  function mix(a, b, t) {
    var x = hex2rgb(a), y = hex2rgb(b);
    return rgb2hex({ r: x.r + (y.r - x.r) * t, g: x.g + (y.g - x.g) * t, b: x.b + (y.b - x.b) * t });
  }
  function lighten(c, t) { return mix(c, '#ffffff', t); }
  function darken(c, t) { return mix(c, '#000000', t); }
  function luma(c) { var x = hex2rgb(c); return (0.299 * x.r + 0.587 * x.g + 0.114 * x.b) / 255; }

  /* ── 피부톤 ──
   * shade = 그늘색. 살의 그늘은 중성 회색이 아니라 붉은 갈색이다. 검정으로 어둡게
   *   하면 채도가 빠져 송장처럼 보이므로 음영은 전부 이 색으로 넣는다.
   * blood = 관절·손끝에 도는 혈색(subsurface). 핏기를 만드는 색.
   */
  var SKINS = [
    { id: 's1', name: '라이트',    base: '#f7d5c0', dark: '#dda284', light: '#fff1e7', warm: '#ef9d87', blood: '#e2705c', shade: '#8d3d24' },
    { id: 's2', name: '아이보리',  base: '#f2caab', dark: '#d3946b', light: '#fee9d7', warm: '#e89275', blood: '#d8654e', shade: '#83351d' },
    { id: 's3', name: '내추럴',    base: '#e3b189', dark: '#bb7c4f', light: '#f7dabd', warm: '#d47a58', blood: '#bf5539', shade: '#6d2a13' },
    { id: 's4', name: '탠',        base: '#c98d57', dark: '#985d33', light: '#e7b98b', warm: '#b55c3c', blood: '#a34526', shade: '#57200c' },
    { id: 's5', name: '딥',        base: '#8d5734', dark: '#5e3119', light: '#b57e54', warm: '#843c20', blood: '#772f16', shade: '#3d1608' },
    { id: 's6', name: '에스프레소', base: '#5f3822', dark: '#3b1e0f', light: '#895535', warm: '#5a2913', blood: '#52210f', shade: '#261005' }
  ];

  var BACKDROPS = [
    { id: 'studio', name: '스튜디오' },
    { id: 'blush',  name: '블러시' },
    { id: 'noir',   name: '누아르' }
  ];

  /* ── 컬러 팔레트 ── */
  var PALETTE = [
    { name: '내추럴 누드',   hex: '#e9b8a3' },
    { name: '밀키 화이트',   hex: '#f7f1ea' },
    { name: '피치 베이지',   hex: '#e3ac92' },
    { name: '모카',          hex: '#a9765f' },
    { name: '코코아',        hex: '#6f4536' },
    { name: '체리 레드',     hex: '#c9243f' },
    { name: '버건디',        hex: '#7c1c33' },
    { name: '코랄',          hex: '#f4735f' },
    { name: '핫핑크',        hex: '#e2467f' },
    { name: '베이비 핑크',   hex: '#f3bcc9' },
    { name: '라벤더',        hex: '#b5a3d8' },
    { name: '바이올렛',      hex: '#6d4b9e' },
    { name: '스카이',        hex: '#9cc4e0' },
    { name: '네이비',        hex: '#26375e' },
    { name: '민트',          hex: '#9bd4c0' },
    { name: '올리브',        hex: '#7f8b5c' },
    { name: '머스터드',      hex: '#dfa63a' },
    { name: '오렌지',        hex: '#ef7a2b' },
    { name: '그레이',        hex: '#9a9a9f' },
    { name: '차콜',          hex: '#3a3a40' },
    { name: '실버',          hex: '#cfd4da' },
    { name: '샴페인 골드',   hex: '#dcc08a' }
  ];

  var FINISHES = [
    { id: 'gloss', name: '글로시' },
    { id: 'matte', name: '매트' },
    { id: 'pearl', name: '펄' },
    { id: 'chrome', name: '크롬' }
  ];

  var ARTS = [
    { id: 'none',   name: '단색' },
    { id: 'french', name: '프렌치' },
    { id: 'ombre',  name: '옴브레' },
    { id: 'glitter', name: '글리터' },
    { id: 'cateye', name: '마그네틱' },
    { id: 'tip',    name: '팁 글리터' }
  ];

  /* ── 추천 디자인 (색 + 마감 + 아트 + 모양 + 길이) ── */
  var DESIGNS = [
    { name: '클래식 프렌치', color: '#eec1ac', color2: '#fffaf5', finish: 'gloss', art: 'french', shape: 'squoval', length: 1 },
    { name: '밀키 젤',       color: '#f7f1ea', color2: '#ffffff', finish: 'gloss', art: 'none',   shape: 'round',  length: 0 },
    { name: '누드 글로시',   color: '#e9b8a3', color2: '#fff3ea', finish: 'gloss', art: 'none',   shape: 'oval',   length: 1 },
    { name: '체리 레드',     color: '#c9243f', color2: '#7c1020', finish: 'gloss', art: 'none',   shape: 'almond', length: 2 },
    { name: '버건디 매트',   color: '#7c1c33', color2: '#4a0e1e', finish: 'matte', art: 'none',   shape: 'coffin', length: 2 },
    { name: '핑크 옴브레',   color: '#e2467f', color2: '#fdf0f4', finish: 'gloss', art: 'ombre',  shape: 'almond', length: 2 },
    { name: '라벤더 크롬',   color: '#b5a3d8', color2: '#efe7ff', finish: 'chrome', art: 'none',  shape: 'almond', length: 2 },
    { name: '실버 미러',     color: '#cfd4da', color2: '#ffffff', finish: 'chrome', art: 'none',  shape: 'coffin', length: 3 },
    { name: '글리터 파티',   color: '#8d2f57', color2: '#ffd9a8', finish: 'gloss', art: 'glitter', shape: 'stiletto', length: 3 },
    { name: '샴페인 팁',     color: '#f0dfd2', color2: '#dcc08a', finish: 'pearl', art: 'tip',    shape: 'squoval', length: 1 },
    { name: '마그네틱 그레이', color: '#7d818c', color2: '#e2e6ee', finish: 'pearl', art: 'cateye', shape: 'oval', length: 1 },
    { name: '네이비 젤',     color: '#26375e', color2: '#8fa6cd', finish: 'gloss', art: 'none',   shape: 'square', length: 1 },
    { name: '민트 매트',     color: '#9bd4c0', color2: '#ffffff', finish: 'matte', art: 'none',   shape: 'squoval', length: 1 },
    { name: '코코아 아몬드', color: '#6f4536', color2: '#c79b7f', finish: 'gloss', art: 'none',   shape: 'almond', length: 1 }
  ];

  NS.data = {
    SKINS: SKINS, BACKDROPS: BACKDROPS, PALETTE: PALETTE,
    FINISHES: FINISHES, ARTS: ARTS, DESIGNS: DESIGNS
  };
  NS.color = { hex2rgb: hex2rgb, rgb2hex: rgb2hex, mix: mix, lighten: lighten, darken: darken, luma: luma };
})(window.NailSim = window.NailSim || {});
