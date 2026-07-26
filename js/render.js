/* 상태 → SVG 문자열. 문자열로 만들기 때문에 PNG 내보내기에 그대로 재사용된다. */
(function (NS) {
  'use strict';

  var G = NS.geom, C = NS.color, D = NS.data;
  var VIEW_FULL = '158 202 528 404';   // 손가락 전체 + 손등 윗부분
  var VIEW_ZOOM = '196 216 456 296';   // 네일만 가까이
  var FRENCH_START = 0.68;             // 프렌치 팁이 시작되는 위치 (네일 길이 비율)

  function skinOf(id) {
    for (var i = 0; i < D.SKINS.length; i++) if (D.SKINS[i].id === id) return D.SKINS[i];
    return D.SKINS[2];
  }

  function prng(seed) {
    return function () { seed = (seed * 1103515245 + 12345) & 0x7fffffff; return seed / 0x7fffffff; };
  }

  /* ── defs ── */
  function skinDefs(sk) {
    return [
      // 손가락을 가로지르는 원통 음영. 살색을 덮어쓰지 않고 명암만 얹어야
      // 전체 조명·피부톤과 자연스럽게 합성된다.
      grad('skinCyl', 0, 0, 1, 0, [
        [0, '#00000063'], [0.05, '#0000004a'], [0.16, '#0000001c'],
        [0.30, '#ffffff4d'], [0.42, '#ffffff61'], [0.56, '#ffffff2b'],
        [0.72, '#00000016'], [0.88, '#00000044'], [0.965, '#0000006b'],
        [1, '#ffffff2e']   // 오른쪽 끝 림 라이트
      ]),
      // 손가락 끝으로 갈수록 도는 붉은 기 (y=0 이 끝)
      grad('skinTip', 0, 0, 0, 1, [
        [0, sk.warm], [0.18, sk.warm + '00'], [1, sk.warm + '00']
      ]),
      // 밑동에서 원통 음영을 평평한 살색으로 되돌린다 (손등과 이어지게)
      grad('baseFade', 0, 0, 0, 1, [
        [0, sk.base + '00'], [0.5, sk.base + 'b8'], [1, sk.base + 'ff']
      ]),
      // 손 전체 조명 방향 (왼쪽 위 → 오른쪽 아래)
      grad('globalLight', 0.1, 0, 0.92, 1, [
        [0, '#ffffff2b'], [0.34, '#ffffff00'], [0.7, '#0000000f'], [1, '#00000026']
      ]),
      blurFilter('soft1', 1.1), blurFilter('soft3', 3), blurFilter('soft6', 6),
      blurFilter('soft14', 14), blurFilter('soft22', 22),
      '<filter id="grain" x="0" y="0" width="100%" height="100%">' +
        '<feTurbulence type="fractalNoise" baseFrequency="0.9" numOctaves="3" stitchTiles="stitch"/>' +
        '<feColorMatrix type="saturate" values="0"/></filter>'
    ].join('');
  }

  /* 흐림 필터. 기본 필터 영역(bbox +10%)은 블러 반경보다 좁아서 잘린 자국이 남는다 —
   * 얇고 긴 도형일수록 심하므로 영역을 넉넉하게 잡는다. */
  function blurFilter(id, sd) {
    return '<filter id="' + id + '" x="-100%" y="-100%" width="300%" height="300%" ' +
      'filterUnits="objectBoundingBox"><feGaussianBlur stdDeviation="' + sd + '"/></filter>';
  }

  function grad(id, x1, y1, x2, y2, stops) {
    return '<linearGradient id="' + id + '" x1="' + x1 + '" y1="' + y1 + '" x2="' + x2 + '" y2="' + y2 + '">' +
      stops.map(function (s) { return stop(s[0], s[1]); }).join('') + '</linearGradient>';
  }
  function stop(o, c) {
    var col = c, op = '';
    if (col.length === 9) { op = ' stop-opacity="' + (parseInt(col.slice(7), 16) / 255).toFixed(2) + '"'; col = col.slice(0, 7); }
    return '<stop offset="' + o + '" stop-color="' + col + '"' + op + '/>';
  }

  /* 네일 1개에 필요한 defs (그라디언트 · 클립 · 패턴) */
  function nailDefs(fg, d) {
    var id = fg.id, out = [];
    var m = G.nailMetrics(fg, d);
    out.push('<clipPath id="clip-' + id + '"><path d="' + G.nailPath(fg, d, 0) + '"/></clipPath>');
    out.push(grad('bed-' + id, 0, 0, 1, 0, [[0, '#e8b6a6'], [0.45, '#f6d3c6'], [1, '#dfa695']]));

    var c = d.color, c2 = d.color2;
    if (d.finish === 'chrome') {
      out.push(grad('pol-' + id, 0, 0, 1, 0.15, [
        [0, C.darken(c, 0.5)], [0.10, C.lighten(c, 0.62)], [0.28, c],
        [0.5, C.darken(c, 0.34)], [0.68, C.lighten(c, 0.75)], [0.86, c], [1, C.darken(c, 0.52)]
      ]));
    } else if (d.art === 'ombre') {
      out.push(grad('pol-' + id, 0, 1, 0, 0, [
        [0, c2], [0.38, C.mix(c2, c, 0.45)], [0.72, c], [1, C.darken(c, 0.08)]
      ]));
    } else {
      out.push(grad('pol-' + id, 0, 1, 0, 0, [
        [0, C.lighten(c, 0.14)], [0.3, c], [0.82, c], [1, C.darken(c, 0.16)]
      ]));
    }
    // 폴리시 위에 얹는 원통 음영 (좌우 어두움)
    out.push(grad('polShade-' + id, 0, 0, 1, 0, [
      [0, '#000000'], [0.16, '#00000000'], [0.5, '#ffffff30'], [0.84, '#00000000'], [1, '#000000']
    ]));
    if (d.finish === 'pearl') {
      out.push(grad('pearl-' + id, 0.1, 1, 0.9, 0, [
        [0, '#ffd9ec99'], [0.35, '#dff3ff88'], [0.62, '#fff4d699'], [1, '#e2d9ff88']
      ]));
    }
    if (d.art === 'cateye') {
      out.push(grad('cat-' + id, 0.05, 0.1, 0.95, 0.9, [
        [0, C.darken(c, 0.42)], [0.34, C.darken(c, 0.12)],
        [0.5, C.lighten(c2, 0.25)], [0.66, C.darken(c, 0.12)], [1, C.darken(c, 0.45)]
      ]));
    }
    if (d.art === 'glitter' || d.art === 'tip') {
      out.push(glitterPattern('glit-' + id, c2, m));
    }
    return out.join('');
  }

  function glitterPattern(id, c2, m) {
    var r = prng(Math.round(m.hw * 977 + m.T * 31) || 7);
    var dots = [];
    var cols = ['#ffffff', C.lighten(c2, 0.35), '#ffe9b8', C.lighten(c2, 0.7)];
    for (var i = 0; i < 26; i++) {
      var x = r() * 18, y = r() * 18;
      var rad = 0.45 + r() * 1.15;
      dots.push('<circle cx="' + x.toFixed(2) + '" cy="' + y.toFixed(2) + '" r="' + rad.toFixed(2) +
        '" fill="' + cols[i % cols.length] + '" opacity="' + (0.45 + r() * 0.55).toFixed(2) + '"/>');
    }
    return '<pattern id="' + id + '" width="18" height="18" patternUnits="userSpaceOnUse">' + dots.join('') + '</pattern>';
  }

  /* ── 손 ── */
  function xform(fg) {
    return 'translate(' + fg.bx + ' ' + fg.by + ') rotate(' + fg.angle + ')';
  }
  function fingerGroup(fg, inner) {
    return '<g transform="' + xform(fg) + '">' + inner + '</g>';
  }
  /* clipPath 안에서는 <g> 가 무시된다 — 변환을 도형에 직접 걸어야 한다. */
  function fingerPathAbs(fg) {
    return '<path transform="' + xform(fg) + '" d="' + G.fingerPath(fg) + '"/>';
  }

  /* 손가락 원통 음영. 밑동에서는 baseFade 로 평평하게 되돌려 손등과 살이 이어져 보이게 한다 —
   * 손등을 별도 실루엣으로 위에 덮으면 벙어리장갑처럼 보인다. */
  function fingerShading(fg) {
    var p = G.fingerPath(fg), L = fg.len, out = [];
    out.push('<g clip-path="url(#fclip-' + fg.id + ')">');
    out.push('<path d="' + p + '" fill="url(#skinCyl)"/>');
    out.push('<path d="' + p + '" fill="url(#skinTip)" opacity="0.6"/>');
    // 밑동 음영 지우기. 전체 조명은 이 다음 단계에서 다시 얹으므로 이어짐이 끊기지 않는다.
    out.push('<rect x="' + (-fg.w0 * 1.3) + '" y="' + (-L * 0.26) + '" width="' + (fg.w0 * 2.6) +
      '" height="' + (L * 0.26 + G.BASE_OVERLAP + 6) + '" fill="url(#baseFade)"/>');
    // 관절 주름 — 짧고 흐리게. 길고 진하면 원통 이음새처럼 보인다.
    G.knuckleLines(fg).forEach(function (k) {
      out.push('<path d="M ' + (-k.w) + ' ' + k.y + ' Q 0 ' + (k.y + 6) + ' ' + k.w + ' ' + k.y +
        '" fill="none" stroke="#00000020" stroke-width="2" filter="url(#soft3)"/>');
    });
    // 길이 방향 하이라이트 + 손가락 끝 살 볼륨
    out.push('<ellipse cx="' + (-fg.w0 * 0.22) + '" cy="' + (-L * 0.52) + '" rx="' + (fg.w0 * 0.3) +
      '" ry="' + (L * 0.38) + '" fill="#ffffff" opacity="0.15" filter="url(#soft14)"/>');
    out.push('<ellipse cx="' + (-fg.w1 * 0.15) + '" cy="' + (-L * 0.93) + '" rx="' + (fg.w1 * 0.7) +
      '" ry="' + (L * 0.05) + '" fill="#ffffff" opacity="0.12" filter="url(#soft6)"/>');
    out.push('</g>');
    return out.join('');
  }

  function silhouette(order) {
    var parts = ['<path d="' + G.dorsumPath() + '"/>'];
    order.forEach(function (fg) { parts.push(fingerPathAbs(fg)); });
    return parts.join('');
  }

  function handShadow(order) {
    return '<g transform="translate(18 24)" filter="url(#soft22)" opacity="0.32" fill="#4b2b20">' +
      silhouette(order) + '</g>';
  }

  function handClip(order) {
    var out = ['<clipPath id="handClip">' + silhouette(order) + '</clipPath>'];
    order.forEach(function (fg) {
      var p = '<path d="' + G.fingerPath(fg) + '"/>';
      // 손가락 좌표계용 / 손 전체 좌표계용
      out.push('<clipPath id="fclip-' + fg.id + '">' + p + '</clipPath>');
      out.push('<clipPath id="fclip-' + fg.id + '-abs">' + fingerPathAbs(fg) + '</clipPath>');
    });
    return out.join('');
  }

  /* 손등 음영. 테두리가 생기는 채움 대신 흐린 덩어리만 써서 손가락과의 경계선을 만들지 않는다. */
  function dorsumShading(sk) {
    var out = [];
    // 힘줄 — 너클에서 손목 방향으로
    [[402, 512, 448, 742], [476, 494, 484, 748], [548, 506, 530, 744], [612, 552, 574, 736]].forEach(function (t) {
      out.push('<path d="M ' + t[0] + ' ' + t[1] + ' C ' + t[0] + ' ' + (t[1] + 80) + ' ' + t[2] + ' ' + (t[3] - 100) +
        ' ' + t[2] + ' ' + t[3] + '" fill="none" stroke="#ffffff1e" stroke-width="14" filter="url(#soft14)"/>');
    });
    // 너클 — 넓고 부드럽게. 작고 진하면 얼룩처럼 보인다.
    [[402, 506, 20], [476, 488, 21], [548, 502, 20], [612, 544, 17]].forEach(function (k) {
      out.push('<ellipse cx="' + k[0] + '" cy="' + k[1] + '" rx="' + (k[2] * 1.5) + '" ry="' + (k[2] * 1.1) +
        '" fill="#ffffff" opacity="0.24" filter="url(#soft14)"/>');
      out.push('<ellipse cx="' + k[0] + '" cy="' + (k[1] + k[2] * 1.9) + '" rx="' + (k[2] * 1.35) +
        '" ry="' + (k[2] * 0.9) + '" fill="#000000" opacity="0.06" filter="url(#soft14)"/>');
    });
    // 엄지 두덩 · 손등 중앙 볼륨 · 새끼손가락 쪽 측면 음영
    out.push('<ellipse cx="332" cy="656" rx="58" ry="64" fill="' + C.lighten(sk.light, 0.2) +
      '" opacity="0.4" filter="url(#soft22)"/>');
    out.push('<ellipse cx="466" cy="606" rx="98" ry="104" fill="#ffffff" opacity="0.13" filter="url(#soft22)"/>');
    out.push('<ellipse cx="642" cy="636" rx="30" ry="106" fill="' + C.darken(sk.dark, 0.25) +
      '" opacity="0.42" filter="url(#soft22)"/>');
    out.push('<ellipse cx="292" cy="700" rx="26" ry="52" fill="' + C.darken(sk.dark, 0.2) +
      '" opacity="0.3" filter="url(#soft22)"/>');
    // 손목 주름
    out.push('<path d="M 424 754 Q 512 776 612 750" fill="none" stroke="#00000022" stroke-width="4" filter="url(#soft6)"/>');
    return out.join('');
  }

  /* ── 네일 렌더 ── */
  function nail(fg, d, selected) {
    var m = G.nailMetrics(fg, d);
    var id = fg.id, hw = m.hw, T = m.T, yc = m.yc;
    var path = G.nailPath(fg, d, 0);
    var Y = function (r) { return -(yc + T * r); };
    var out = [];
    var bright = 1 - C.luma(d.color) * 0.42;   // 밝은 색일수록 하이라이트를 약하게

    // 네일 아래로 떨어지는 그림자 (연장 길이가 길면 더 진하게)
    out.push('<path d="' + G.nailPath(fg, d, -1.5) + '" transform="translate(2.5 3)" fill="#00000055" filter="url(#soft3)"/>');

    var g = ['<g clip-path="url(#clip-' + id + ')">'];
    g.push('<path d="' + path + '" fill="url(#bed-' + id + ')"/>');

    // 베이스 폴리시
    var baseFill = d.art === 'cateye' ? 'url(#cat-' + id + ')' : 'url(#pol-' + id + ')';
    g.push('<path d="' + path + '" fill="' + baseFill + '"/>');

    // 아트 레이어
    if (d.art === 'french' || d.art === 'tip') {
      var tipFill = d.art === 'tip' ? 'url(#glit-' + id + ')' : 'url(#polTip-' + id + ')';
      if (d.art === 'tip') g.push('<path d="' + smilePath(hw, yc, T, FRENCH_START) + '" fill="' + C.darken(d.color2, 0.05) + '" opacity="0.55"/>');
      g.push('<path d="' + smilePath(hw, yc, T, FRENCH_START) + '" fill="' + tipFill + '"/>');
      if (d.art === 'french') {
        g.push('<path d="' + smilePath(hw, yc, T, FRENCH_START) + '" fill="' + C.lighten(d.color2, 0.25) + '" opacity="0.35"/>');
        g.push('<path d="' + smileLine(hw, yc, T, FRENCH_START) + '" fill="none" stroke="#00000022" stroke-width="1" filter="url(#soft1)"/>');
      }
    }
    if (d.art === 'glitter') {
      g.push('<path d="' + path + '" fill="url(#glit-' + id + ')" opacity="0.95"/>');
      g.push('<path d="' + path + '" fill="' + d.color + '" opacity="0.18"/>');
    }

    // 마감
    if (d.finish === 'pearl') g.push('<path d="' + path + '" fill="url(#pearl-' + id + ')" opacity="0.5" style="mix-blend-mode:screen"/>');
    g.push('<path d="' + path + '" fill="url(#polShade-' + id + ')" opacity="' + (d.finish === 'matte' ? 0.15 : 0.4) + '"/>');

    if (d.finish === 'matte') {
      g.push('<path d="' + path + '" fill="#ffffff" opacity="0.04"/>');
      g.push('<ellipse cx="' + (-hw * 0.2) + '" cy="' + Y(0.6) + '" rx="' + hw * 0.75 + '" ry="' + T * 0.34 +
        '" fill="#ffffff" opacity="' + (0.08 * bright).toFixed(3) + '" filter="url(#soft6)"/>');
    } else {
      var s = (d.finish === 'chrome' ? 1.25 : 1) * bright;
      g.push('<ellipse cx="' + (-hw * 0.33) + '" cy="' + Y(0.55) + '" rx="' + hw * 0.34 + '" ry="' + T * 0.28 +
        '" fill="#ffffff" opacity="' + (0.42 * s).toFixed(3) + '" filter="url(#soft3)"/>');
      g.push('<ellipse cx="' + (-hw * 0.28) + '" cy="' + Y(0.78) + '" rx="' + hw * 0.14 + '" ry="' + T * 0.07 +
        '" fill="#ffffff" opacity="' + (0.85 * s).toFixed(3) + '" filter="url(#soft1)"/>');
      g.push('<ellipse cx="0" cy="' + Y(0.99) + '" rx="' + hw * 0.78 + '" ry="' + T * 0.05 +
        '" fill="#ffffff" opacity="' + (0.3 * s).toFixed(3) + '" filter="url(#soft3)"/>');
      g.push('<ellipse cx="' + (hw * 0.62) + '" cy="' + Y(0.38) + '" rx="' + hw * 0.17 + '" ry="' + T * 0.22 +
        '" fill="#ffffff" opacity="' + (0.16 * s).toFixed(3) + '" filter="url(#soft3)"/>');
    }

    // 큐티클 음영 + 자연 네일이 끝나는 선(프리엣지)
    g.push('<ellipse cx="0" cy="' + (-yc) + '" rx="' + hw * 0.95 + '" ry="' + Math.max(2.2, T * 0.07) +
      '" fill="#000000" opacity="0.3" filter="url(#soft3)"/>');
    if (m.ext > 3) {
      g.push('<path d="M ' + (-hw) + ' ' + (-(yc + m.bed)) + ' Q 0 ' + (-(yc + m.bed + hw * 0.3)) + ' ' + hw + ' ' + (-(yc + m.bed)) +
        '" fill="none" stroke="#ffffff" stroke-width="1.6" opacity="0.22" filter="url(#soft1)"/>');
    }
    g.push('</g>');
    out.push(g.join(''));

    // 테두리
    out.push('<path d="' + path + '" fill="none" stroke="' + C.darken(d.color, 0.45) + '" stroke-width="0.9" opacity="0.45"/>');

    if (selected) {
      out.push('<path d="' + G.nailPath(fg, d, -4.5) + '" fill="none" stroke="#c2185b" stroke-width="2" ' +
        'stroke-dasharray="5 4" opacity="0.95"/>');
    }
    return out.join('');
  }

  // 프렌치 스마일 라인 위쪽 영역 (네일 path로 클립되어 팁만 남는다)
  function smilePath(hw, yc, T, start) {
    var w = hw * 1.4, y0 = -(yc + T * start), y1 = -(yc + T * (start + 0.2)), top = -(yc + T * 1.4);
    return 'M ' + (-w) + ' ' + y0 + ' Q 0 ' + y1 + ' ' + w + ' ' + y0 + ' L ' + w + ' ' + top + ' L ' + (-w) + ' ' + top + ' Z';
  }
  function smileLine(hw, yc, T, start) {
    var w = hw * 1.4, y0 = -(yc + T * start), y1 = -(yc + T * (start + 0.2));
    return 'M ' + (-w) + ' ' + y0 + ' Q 0 ' + y1 + ' ' + w + ' ' + y0;
  }

  /* 프렌치 팁 색상 그라디언트는 defs에 따로 필요 */
  function tipDefs(fg, d) {
    if (d.art !== 'french') return '';
    return grad('polTip-' + fg.id, 0, 1, 0, 0, [
      [0, C.darken(d.color2, 0.06)], [0.5, d.color2], [1, C.lighten(d.color2, 0.2)]
    ]);
  }

  /* ── 배경 ── */
  function backdrop(kind) {
    if (kind === 'noir') {
      return '<defs><radialGradient id="bg" cx="0.42" cy="0.32" r="0.9">' +
        stop(0, '#3b3340') + stop(0.55, '#221d29') + stop(1, '#100e15') + '</radialGradient></defs>' +
        '<rect width="900" height="980" fill="url(#bg)"/>';
    }
    if (kind === 'blush') {
      return '<defs><radialGradient id="bg" cx="0.4" cy="0.3" r="0.95">' +
        stop(0, '#fdf2f4') + stop(0.6, '#f6dee3') + stop(1, '#e8c3cc') + '</radialGradient></defs>' +
        '<rect width="900" height="980" fill="url(#bg)"/>';
    }
    return '<defs><radialGradient id="bg" cx="0.4" cy="0.28" r="0.95">' +
      stop(0, '#fffaf6') + stop(0.55, '#f4e6dc') + stop(1, '#e2cec1') + '</radialGradient></defs>' +
      '<rect width="900" height="980" fill="url(#bg)"/>';
  }

  /* ── 전체 ── */
  function renderSVG(state, opts) {
    opts = opts || {};
    var sk = skinOf(state.skin);
    var fingers = G.FINGERS;
    var byId = {};
    fingers.forEach(function (f) { byId[f.id] = f; });

    // 오른쪽 → 왼쪽 순서로 그려야 손가락 그림자가 오른쪽 이웃에 얹힌다.
    var order = ['pinky', 'ring', 'middle', 'index', 'thumb'].map(function (i) { return byId[i]; });

    var defs = ['<defs>', skinDefs(sk), handClip(order)];
    fingers.forEach(function (fg) {
      defs.push(nailDefs(fg, state.nails[fg.id]), tipDefs(fg, state.nails[fg.id]));
    });
    defs.push('</defs>');

    var body = [];
    body.push(backdrop(state.backdrop));
    body.push(defs.join(''));
    body.push(handShadow(order));

    // 1) 손등과 손가락을 같은 평면 살색으로 한 덩어리로 칠한다 — 내부 경계선이 생기지 않게
    body.push('<g fill="' + sk.base + '">' + silhouette(order) + '</g>');

    // 2~6) 음영은 모두 손 실루엣 안쪽에만.
    // 손가락 원통 음영 → 전체 조명 → 손등 볼륨 순서. 조명을 나중에 얹어야
    // 밑동에서 평평하게 되돌린 부분이 손등과 같은 빛을 받아 이어져 보인다.
    body.push('<g clip-path="url(#handClip)">');
    order.forEach(function (fg) { body.push(fingerGroup(fg, fingerShading(fg))); });
    body.push('<rect width="900" height="980" fill="url(#globalLight)"/>');
    body.push(dorsumShading(sk));
    // 왼쪽 손가락이 오른쪽 이웃에 드리우는 그림자
    var rightOf = { thumb: 'index', index: 'middle', middle: 'ring', ring: 'pinky' };
    order.forEach(function (fg) {
      var nb = rightOf[fg.id];
      if (!nb) return;
      body.push('<g clip-path="url(#fclip-' + nb + '-abs)" transform="translate(12 7)" ' +
        'filter="url(#soft6)" opacity="0.3" fill="#40241b">' + fingerPathAbs(fg) + '</g>');
    });
    // 피부 질감
    body.push('<rect width="900" height="980" filter="url(#grain)" opacity="0.1" ' +
      'style="mix-blend-mode:overlay"/>');
    body.push('</g>');

    // 7) 네일. 선택 표시는 손톱별로 편집할 때만 (전체 적용 중이면 5개 다 테두리가 생겨 산만하다)
    var mark = opts.selectable !== false && !state.sync;
    order.forEach(function (fg) {
      body.push(fingerGroup(fg, nail(fg, state.nails[fg.id],
        mark && state.selected.indexOf(fg.id) >= 0)));
    });

    // 클릭 영역 (네일 위)
    if (opts.selectable !== false) {
      fingers.forEach(function (fg) {
        body.push(fingerGroup(fg, '<path class="nail-hit" data-finger="' + fg.id + '" d="' +
          G.nailPath(fg, state.nails[fg.id], -6) + '" fill="transparent"/>'));
      });
    }

    var view = opts.zoom ? VIEW_ZOOM : VIEW_FULL;
    // <img> 로 래스터화할 때는 고유 크기가 없으면 그려지지 않으므로 scale 이 오면 넣어준다.
    var size = '';
    if (opts.scale) {
      var b = view.split(' ');
      size = ' width="' + b[2] * opts.scale + '" height="' + b[3] * opts.scale + '"';
    }
    return scopeIds('<svg xmlns="http://www.w3.org/2000/svg" viewBox="' + view + '"' + size +
      ' preserveAspectRatio="xMidYMid meet" class="hand-svg">' + body.join('') + '</svg>');
  }

  /* 같은 문서에 SVG가 두 개 이상 있어도 id가 겹치지 않게 렌더마다 접두사를 붙인다. */
  var seq = 0;
  function scopeIds(svg) {
    var p = 'r' + (++seq) + '-';
    return svg.replace(/id="/g, 'id="' + p).replace(/url\(#/g, 'url(#' + p);
  }

  NS.render = { renderSVG: renderSVG, VIEW_FULL: VIEW_FULL, VIEW_ZOOM: VIEW_ZOOM };
})(window.NailSim = window.NailSim || {});
