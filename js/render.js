/* 상태 → SVG 문자열. 문자열로 만들기 때문에 PNG 내보내기에 그대로 재사용된다. */
(function (NS) {
  'use strict';

  var G = NS.geom, C = NS.color, D = NS.data;
  var VIEW_FULL = '150 196 546 424';   // 손가락 전체 + 손등 윗부분 + 엄지
  var VIEW_ZOOM = '192 212 468 306';   // 네일만 가까이
  var FRENCH_START = 0.7;             // 프렌치 팁이 시작되는 위치 (네일 길이 비율)

  /* 살의 하이라이트 색은 피부톤에서 뽑아야 한다. 모든 톤에 고정된 흰색을 쓰면
   * 어두운 톤에서 재를 뿌린 것처럼 창백한 줄무늬가 생긴다. (네일 광택은 폴리시
   * 표면의 반사라 흰색이 맞으므로 거기엔 그대로 흰색을 쓴다.) */
  function hiOf(sk) { return C.lighten(sk.light, 0.3); }
  /* 가장 깊은 그림자는 순수한 붉은 갈색이 아니라 채도가 살짝 빠진다 */
  function deepOf(sk) { return C.mix(sk.shade, '#4a3f46', 0.28); }

  function skinOf(id) {
    for (var i = 0; i < D.SKINS.length; i++) if (D.SKINS[i].id === id) return D.SKINS[i];
    return D.SKINS[2];
  }

  function prng(seed) {
    return function () { seed = (seed * 1103515245 + 12345) & 0x7fffffff; return seed / 0x7fffffff; };
  }

  /* ── defs ── */
  function skinDefs(sk) {
    var HI = hiOf(sk);
    return [
      // 손가락을 가로지르는 원통 음영. 살색을 덮어쓰지 않고 명암만 얹어야
      // 전체 조명·피부톤과 자연스럽게 합성된다. 그늘은 검정이 아니라 sk.shade —
      // 검정으로 어둡게 하면 채도가 빠져 밀랍/송장처럼 된다.

      // 손끝 혈색 (y=0 이 끝) — 살짝이 아니라 확실히 붉게
      grad('skinTip', 0, 0, 0, 1, [
        [0, sk.blood + 'b0'], [0.07, sk.warm + '8c'], [0.2, sk.warm + '3d'],
        [0.3, sk.warm + '00'], [1, sk.warm + '00']
      ]),
      // 밑동에서 원통 음영을 평평한 살색으로 되돌린다 (손등과 이어지게)
      grad('baseFade', 0, 0, 0, 1, [
        [0, sk.base + '00'], [0.5, sk.base + 'b8'], [1, sk.base + 'ff']
      ]),
      // 손 전체 조명 방향 (왼쪽 위 → 오른쪽 아래). 그늘 쪽도 따뜻하게.
      grad('globalLight', 0.1, 0, 0.92, 1, [
        [0, HI + '2b'], [0.34, HI + '00'], [0.7, sk.shade + '14'], [1, sk.shade + '2e']
      ]),
      blurFilter('soft1', 1.1), blurFilter('soft3', 3), blurFilter('soft6', 6),
      blurFilter('soft14', 14), blurFilter('soft22', 22),
      // 저주파 색 얼룩 — 부위마다 붉은 기가 다른 게 살처럼 보이는 핵심.
      // 회색 노이즈만 얹으면 피부가 아니라 잡음이 된다.
      noiseFill('mottle', sk.blood, 0.013, 4, 1.5, 0.52, 13),
      noiseFill('mottleWarm', sk.warm, 0.026, 3, 1.4, 0.52, 29),
      noiseFill('mottleFine', sk.blood, 0.19, 3, 1.4, 0.55, 61),
      // 고주파 — 모공/살결
      noiseFill('pores', sk.shade, 0.95, 2, 1.35, 0.53, 5),
      noiseFill('poresHi', HI, 1.15, 2, 1.3, 0.52, 41),
      noiseFill('matteGrain', '#8a8a8a', 1.6, 2, 1.3, 0.5, 77)
    ].join('');
  }

  /* 터뷸런스를 알파로만 쓰고 색은 고정해, 지정한 색의 얼룩을 만든다.
   * fractalNoise 값은 0.5 근처에 몰려 있으므로 aScale/aCut 을 그 분포에 맞춰야 한다 —
   * 여유를 크게 잡으면 알파가 전부 0으로 잘려 아무것도 안 보인다. */
  function noiseFill(id, color, freq, octaves, aScale, aCut, seed) {
    var c = C.hex2rgb(color);
    return '<filter id="' + id + '" x="0" y="0" width="100%" height="100%" ' +
      'color-interpolation-filters="sRGB">' +
      '<feTurbulence type="fractalNoise" baseFrequency="' + freq + '" numOctaves="' + octaves +
      '" seed="' + seed + '" stitchTiles="stitch"/>' +
      '<feColorMatrix type="matrix" values="' +
      '0 0 0 0 ' + (c.r / 255).toFixed(4) + ' ' +
      '0 0 0 0 ' + (c.g / 255).toFixed(4) + ' ' +
      '0 0 0 0 ' + (c.b / 255).toFixed(4) + ' ' +
      aScale + ' 0 0 0 ' + (-aCut) + '"/></filter>';
  }

  /* 월드 광원은 하나(왼쪽 위)다. 손가락은 저마다 다른 각도로 돌아가 있으므로
   * 원통 음영을 손가락 로컬 좌표계에 그대로 걸면 엄지가 다른 방향에서 조명받는
   * 것처럼 보인다. 손가락 축에 수직인 방향과 광원 방향의 내적으로 밝은 쪽을 정한다. */
  var LIGHT = [-0.55, -0.83];   // 광원 방향 (SVG 좌표: y 는 아래로)
  var LIGHT_Z = 0.55;           // 보는 쪽으로 향하는 성분

  function hex2(v) {
    var n = Math.max(0, Math.min(255, Math.round(v * 255)));
    return (n < 16 ? '0' : '') + n.toString(16);
  }

  function cylGradient(id, fg, sk) {
    var HI = hiOf(sk);
    // 어두운 톤은 같은 알파로도 대비가 약해 형태가 묻힌다
    var boost = 1 + (1 - C.luma(sk.base)) * 0.55;
    var a = (fg.angle + (fg.bend || 0) * 0.4) * Math.PI / 180;
    // 손가락을 가로지르는 방향(로컬 +x)이 월드에서 향하는 쪽
    var cl = Math.cos(a) * LIGHT[0] + Math.sin(a) * LIGHT[1];
    var bounceCol = C.mix(sk.warm, HI, 0.4);
    var us = [-1, -0.94, -0.85, -0.7, -0.5, -0.25, 0, 0.25, 0.5, 0.7, 0.85, 0.94, 1];
    var stops = us.map(function (u) {
      var nz = Math.sqrt(Math.max(0, 1 - u * u));
      var diffuse = Math.max(0, u * cl + nz * LIGHT_Z);
      var edge = Math.pow(nz, 0.42);                              // 실루엣 쪽 감쇠
      var bounce = Math.pow(Math.max(0, -(u * cl)), 1.6) * 0.3 * nz;
      var lit = diffuse * edge + bounce;
      var off = ((u + 1) / 2).toFixed(3);
      var mid = 0.44;
      if (lit > mid) return [off, HI + hex2((lit - mid) * 1.7 * boost)];
      if (bounce > 0.07) return [off, bounceCol + hex2((mid - lit) * 0.8)];
      return [off, sk.shade + hex2((mid - lit) * 1.2)];
    });
    return grad(id, 0, 0, 1, 0, stops);
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
  function nailDefs(fg, d, sk) {
    var id = fg.id, out = [];
    var m = G.nailMetrics(fg, d);
    out.push('<clipPath id="clip-' + id + '"><path d="' + G.nailPath(fg, d, 0) + '"/></clipPath>');
    var mm = G.nailMetrics(fg, d), ww = fg.w0 * 2;
    var split = -(mm.yc + mm.T * 0.76);
    out.push('<clipPath id="sideclip-' + id + '"><rect x="' + (-ww) + '" y="' + split +
      '" width="' + (ww * 2) + '" height="' + (Math.abs(split) + G.BASE_OVERLAP + 40) + '"/></clipPath>');
    // 테두리용 길이 방향 그라디언트 (y=0 이 팁 쪽)
    out.push(grad('rim-' + id, 0, 0, 0, 1, [
      [0, C.lighten(d.color, 0.85)], [0.12, C.lighten(d.color, 0.5)],
      [0.3, C.darken(d.color, 0.4)], [1, C.darken(d.color, 0.45)]
    ]));
    // 네일 플레이트는 반투명해서 아래 혈관 색이 비친다. 프리엣지는 살에서 떨어져
    // 나온 부분이라 불투명한 흰빛이 된다.
    // 네일 베드는 피부톤에 따라 달라진다. 고정 분홍을 쓰면 어두운 톤에서 흰 얼룩이 된다.
    var warmth = 0.22 + (1 - C.luma(sk.base)) * 0.22;
    var bedMid = C.mix(C.lighten(sk.base, 0.34), sk.blood, warmth);
    var bedEdge = C.mix(bedMid, sk.warm, 0.42);
    out.push(grad('bed-' + id, 0, 0, 1, 0, [[0, bedEdge], [0.42, bedMid], [1, C.darken(bedEdge, 0.05)]]));
    // 프리엣지(살에서 떨어져 나온 구간)만 불투명한 흰빛. 연장이 없으면 거의 없다.
    var fe = Math.max(0.06, Math.min(0.42, m.ext / Math.max(1, m.T)));
    var feCol = C.lighten(sk.base, 0.72);   // 프리엣지: 살에서 떨어져 불투명한 흰빛
    var feA = Math.round(90 + fe * 300).toString(16);
    // 길이 방향: 가운데 베드가 가장 붉고 큐티클 쪽은 루눌라로 옅어진다
    out.push(grad('bedBlood-' + id, 0, 0, 0, 1, [
      [0, sk.blood + '00'], [0.35, sk.blood + '2e'], [0.62, sk.blood + '3d'],
      [0.88, sk.blood + '14'], [1, sk.blood + '00']
    ]));
    out.push(grad('bedLen-' + id, 0, 0, 0, 1, [
      [0, feCol + (feA.length < 2 ? '0' + feA : feA)],
      [fe * 0.55, feCol + '80'],
      [Math.min(0.95, fe + 0.06), '#f2c3b400'],
      [1, '#f2c3b400']
    ]));

    var c = d.color, c2 = d.color2;
    if (d.finish === 'chrome') {
      // 크롬은 환경이 비친다. 길이 방향으로 수평선(밝은 하늘 / 어두운 땅)을 넣어야
      // 금속처럼 보인다.
      out.push(grad('chromeEnv-' + id, 0, 0, 0, 1, [
        [0, C.lighten(c, 0.8) + 'cc'], [0.34, C.lighten(c, 0.35) + '66'],
        [0.46, '#00000000'], [0.6, C.darken(c, 0.55) + '73'], [1, C.darken(c, 0.35) + '4d']
      ]));
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
      [0, '#3a1a0dcc'], [0.16, '#3a1a0d00'], [0.5, '#fff6ec36'],
      [0.84, '#3a1a0d00'], [1, '#3a1a0dcc']
    ]));
    if (d.finish === 'pearl') {
      out.push(grad('pearl-' + id, 0.12, 1, 0.88, 0, [
        [0, '#ffd0e8a8'], [0.24, '#d9f0ff9e'], [0.46, '#fff6d0b3'],
        [0.68, '#e6d4ff9e'], [0.86, '#d4fff08f'], [1, '#ffdcefa8']
      ]));
    }
    if (d.art === 'cateye') {
      out.push(grad('cat-' + id, 0.08, 0.12, 0.92, 0.88, [
        [0, C.darken(c, 0.5)], [0.3, C.darken(c, 0.22)], [0.43, C.mix(c, c2, 0.45)],
        [0.5, C.lighten(c2, 0.18)], [0.57, C.mix(c, c2, 0.45)],
        [0.7, C.darken(c, 0.22)], [1, C.darken(c, 0.52)]
      ]));
    }
    if (d.art === 'glitter' || d.art === 'tip') {
      out.push(glitterPattern('glit-' + id, c2, m));
    }
    return out.join('');
  }

  /* 글리터. 같은 크기의 점을 흩으면 물방울 무늬가 된다 — 대부분은 아주 잘고
   * 소수만 크게, 밝기 편차도 크게 줘야 반짝임으로 읽힌다. */
  function glitterPattern(id, c2, m) {
    var r = prng(Math.round(m.hw * 977 + m.T * 31) || 7);
    var dots = [];
    var cols = ['#ffffff', C.lighten(c2, 0.4), '#fff0c8', C.lighten(c2, 0.75), '#ffe4f2'];
    for (var i = 0; i < 90; i++) {
      var x = r() * 14, y = r() * 14;
      var big = r() > 0.88;
      var rad = big ? 0.7 + r() * 0.7 : 0.16 + r() * 0.32;
      dots.push('<circle cx="' + x.toFixed(2) + '" cy="' + y.toFixed(2) + '" r="' + rad.toFixed(2) +
        '" fill="' + cols[i % cols.length] + '" opacity="' + ((big ? 0.7 : 0.3) + r() * 0.3).toFixed(2) + '"/>');
    }
    // 큰 반짝임 몇 개 — 사방으로 뻗는 십자
    for (var k = 0; k < 3; k++) {
      var sx = r() * 14, sy = r() * 14, sl = 1.3 + r() * 1.1;
      dots.push('<path d="M ' + (sx - sl).toFixed(2) + ' ' + sy.toFixed(2) + ' L ' + (sx + sl).toFixed(2) +
        ' ' + sy.toFixed(2) + ' M ' + sx.toFixed(2) + ' ' + (sy - sl).toFixed(2) + ' L ' + sx.toFixed(2) +
        ' ' + (sy + sl).toFixed(2) + '" stroke="#ffffff" stroke-width="0.35" opacity="0.85"/>');
    }
    return '<pattern id="' + id + '" width="14" height="14" patternUnits="userSpaceOnUse">' + dots.join('') + '</pattern>';
  }

  /* ── 손 ── */
  function xform(fg) {
    return 'translate(' + fg.bx + ' ' + fg.by + ') rotate(' + fg.angle + ')';
  }
  function fingerGroup(fg, inner) {
    return '<g transform="' + xform(fg) + '">' + inner + '</g>';
  }
  /* 네일은 손가락이 휜 만큼 같이 돌아야 손끝에 얹힌다. */
  /* 손톱은 손가락이 휜 만큼 같이 돌고, 손가락마다 아주 살짝 다르게 기울어 있다
   * (손가락 롤). 다섯 개가 정확히 정면을 향하면 붙여놓은 것처럼 보인다. */
  var NAIL_ROLL = { thumb: -5, index: -2, middle: 0, ring: 1.5, pinky: 3 };
  function nailGroup(fg, d, inner) {
    var a = G.nailBend(fg, d) + (NAIL_ROLL[fg.id] || 0);
    return fingerGroup(fg, '<g transform="rotate(' + a.toFixed(2) + ')">' + inner + '</g>');
  }
  /* clipPath 안에서는 <g> 가 무시된다 — 변환을 도형에 직접 걸어야 한다. */
  function fingerPathAbs(fg) {
    return '<path transform="' + xform(fg) + '" d="' + G.fingerPath(fg) + '"/>';
  }

  /* 손가락 원통 음영. 밑동에서는 baseFade 로 평평하게 되돌려 손등과 살이 이어져 보이게 한다 —
   * 손등을 별도 실루엣으로 위에 덮으면 벙어리장갑처럼 보인다. */
  function fingerShading(fg, sk, d) {
    var p = G.fingerPath(fg), L = fg.len, out = [], HI = hiOf(sk);
    out.push('<g clip-path="url(#fclip-' + fg.id + ')">');
    out.push('<path d="' + p + '" fill="url(#skinCyl-' + fg.id + ')"/>');
    out.push('<path d="' + p + '" fill="url(#skinTip)" opacity="0.85"/>');
    // 밑동 음영 지우기. 전체 조명은 이 다음 단계에서 다시 얹으므로 이어짐이 끊기지 않는다.
    out.push('<rect x="' + (-fg.w0 * 1.3) + '" y="' + (-L * 0.26) + '" width="' + (fg.w0 * 2.6) +
      '" height="' + (L * 0.26 + G.BASE_OVERLAP + 6) + '" fill="url(#baseFade)"/>');

    G.knuckleLines(fg).forEach(function (k, i) {
      out.push('<g transform="rotate(' + k.bend.toFixed(2) + ')">');
      // 관절에 도는 혈색 — 핏기의 절반은 여기서 나온다
      out.push('<ellipse cx="0" cy="' + k.y + '" rx="' + (k.w * 1.5) + '" ry="' + (k.w * 1.1) +
        '" fill="' + sk.blood + '" opacity="' + (i ? 0.16 : 0.2) + '" filter="url(#soft14)"/>');
      // 주름은 한 줄이 아니라 잔주름 여러 줄. 한 줄이면 원통 이음새처럼 보인다.
      out.push(knuckleWrinkles(fg, k, sk, i));
      out.push('</g>');
    });

    // 길이 방향 잔주름 — 살결은 관절에만 있는 게 아니다
    var rr = prng(fg.id.charCodeAt(1) * 17 + 5);
    for (var q = 0; q < 6; q++) {
      var qx = (rr() - 0.5) * fg.w0 * 1.5;
      var qy = -L * (0.2 + rr() * 0.6);
      var qh = L * (0.06 + rr() * 0.1);
      out.push('<path d="M ' + qx.toFixed(1) + ' ' + qy.toFixed(1) + ' Q ' +
        (qx + (rr() - 0.5) * 4).toFixed(1) + ' ' + (qy + qh / 2).toFixed(1) + ' ' +
        (qx + (rr() - 0.5) * 5).toFixed(1) + ' ' + (qy + qh).toFixed(1) +
        '" fill="none" stroke="' + sk.shade + '" stroke-opacity="' + (0.05 + rr() * 0.05).toFixed(3) +
        '" stroke-width="0.8" filter="url(#soft1)"/>');
    }

    // 길이 방향 하이라이트 + 손가락 끝 살 볼륨 (휜 축을 따라간다)
    out.push('<ellipse transform="rotate(' + G.bendAt(fg, 0.52).toFixed(2) + ')" cx="' +
      (-fg.w0 * 0.22) + '" cy="' + (-L * 0.52) + '" rx="' + (fg.w0 * 0.3) +
      '" ry="' + (L * 0.38) + '" fill="' + HI + '" opacity="0.17" filter="url(#soft14)"/>');
    out.push('<ellipse transform="rotate(' + G.bendAt(fg, 0.93).toFixed(2) + ')" cx="0" cy="' +
      (-L * 0.955) + '" rx="' + (fg.w1 * 0.85) + '" ry="' + (L * 0.05) +
      '" fill="' + sk.blood + '" opacity="0.3" filter="url(#soft6)"/>');
    out.push('<ellipse transform="rotate(' + G.bendAt(fg, 0.93).toFixed(2) + ')" cx="' +
      (-fg.w1 * 0.22) + '" cy="' + (-L * 0.93) + '" rx="' + (fg.w1 * 0.5) +
      '" ry="' + (L * 0.045) + '" fill="' + HI + '" opacity="0.2" filter="url(#soft6)"/>');
    // 좁고 밝은 광택대 — 피부는 완전 무광이 아니다
    out.push('<ellipse transform="rotate(' + G.bendAt(fg, 0.58).toFixed(2) + ')" cx="' +
      (-fg.w0 * 0.34) + '" cy="' + (-L * 0.58) + '" rx="' + (fg.w0 * 0.17) +
      '" ry="' + (L * 0.3) + '" fill="' + HI + '" opacity="0.19" filter="url(#soft6)"/>');
    // 손톱을 감싸는 살 능선(큐티클·측면 네일폴드). 손톱이 스티커처럼 얹힌 게 아니라
    // 살에 파묻혀 보이게 한다. 살이 있는 곳에만 있어야 하므로 손가락으로 클립된
    // 이 그룹 안에서 그린다 — 손끝 밖으로 나간 연장 부분에는 살 능선이 없다.
    out.push('<g transform="rotate(' + (G.nailBend(fg, d) + (NAIL_ROLL[fg.id] || 0)).toFixed(2) + ')" ' +
      'clip-path="url(#foldclip-' + fg.id + ')">');
    out.push('<path d="' + G.nailPath(fg, d, -3.4) + '" fill="none" stroke="' + HI +
      '" stroke-opacity="0.4" stroke-width="3" filter="url(#soft3)"/>');
    out.push('<path d="' + G.nailPath(fg, d, -1.1) + '" fill="none" stroke="' +
      C.mix(sk.shade, sk.blood, 0.5) + '" stroke-opacity="0.13" stroke-width="1.3" filter="url(#soft1)"/>');
    // 손톱 양옆 살은 조금 더 밝고 붉다 (손톱이 눌러 혈색이 모인다)
    out.push('<path d="' + G.nailPath(fg, d, -5) + '" fill="none" stroke="' +
      C.mix(sk.blood, hiOf(sk), 0.45) + '" stroke-opacity="0.22" stroke-width="4" filter="url(#soft3)"/>');
    // 손톱 옆 그루브 — 손톱과 살 사이의 얕은 골
    out.push('<path d="' + G.nailPath(fg, d, -2.2) + '" fill="none" stroke="' + sk.shade +
      '" stroke-opacity="0.1" stroke-width="2.6" filter="url(#soft3)"/>');
    out.push('</g>');

    out.push('</g>');
    return out.join('');
  }

  /* 관절 주름. 실제 손은 가는 가로 주름이 촘촘히 겹치고 세로 주름이 살짝 얽힌다.
   * 굵고 진하게 그으면 손가락에 해시태그를 새긴 것처럼 보이므로, 아주 옅고 짧게
   * 여러 줄 깔고 전체를 한 번 흐린다. 사진에서도 이 주름은 "선"이 아니라 질감이다. */
  function knuckleWrinkles(fg, k, sk, jointIndex) {
    var r = prng(fg.id.charCodeAt(0) * 31 + fg.id.length * 7 + jointIndex * 101 + 3);
    var HI = hiOf(sk);
    var band = k.w * 0.95;          // 주름이 모여 있는 띠의 높이
    var maxHalf = k.w * 0.72;       // 실루엣 가장자리까지 닿지 않게
    var out = [];
    // 관절 부위 자체가 살짝 어둡다 — 주름만으로는 띠로 읽히지 않는다
    out.push('<ellipse cx="0" cy="' + k.y + '" rx="' + (k.w * 1.25) + '" ry="' + (band * 1.1) +
      '" fill="' + sk.shade + '" opacity="0.075" filter="url(#soft6)"/>');
    out.push('<g filter="url(#soft1)">');

    // 주름 띠 위쪽으로 접힌 살의 밝은 능선
    out.push('<path d="M ' + (-maxHalf) + ' ' + (k.y - band * 0.85) + ' Q 0 ' +
      (k.y - band * 0.85 + 4) + ' ' + maxHalf + ' ' + (k.y - band * 0.85) +
      '" fill="none" stroke="' + HI + '" stroke-opacity="0.2" stroke-width="3.5"/>');

    var n = 12;
    for (var i = 0; i < n; i++) {
      var f = i / (n - 1) - 0.5;
      var y = k.y + f * band * 1.7 + (r() - 0.5) * 2;
      var half = maxHalf * (0.45 + r() * 0.5) * (1 - Math.abs(f) * 0.5);
      var xo = (r() - 0.5) * k.w * 0.45;
      var sag = 1.5 + r() * 3;
      var op = (0.11 + r() * 0.13) * (1 - Math.abs(f) * 0.5);
      out.push('<path d="M ' + (xo - half).toFixed(1) + ' ' + y.toFixed(1) +
        ' Q ' + xo.toFixed(1) + ' ' + (y + sag).toFixed(1) + ' ' + (xo + half).toFixed(1) + ' ' + y.toFixed(1) +
        '" fill="none" stroke="' + sk.shade + '" stroke-opacity="' + op.toFixed(3) +
        '" stroke-width="' + (0.8 + r() * 0.45).toFixed(2) + '"/>');
    }

    // 가로 주름 사이를 짧게 잇는 세로 주름 — 길면 격자무늬가 되어버린다
    for (var j = 0; j < 4; j++) {
      var cx = (r() - 0.5) * k.w * 1.1;
      var cy = k.y + (r() - 0.5) * band * 0.9;
      var h = band * (0.14 + r() * 0.16);
      out.push('<path d="M ' + cx.toFixed(1) + ' ' + (cy - h).toFixed(1) +
        ' Q ' + (cx + (r() - 0.5) * 3).toFixed(1) + ' ' + cy.toFixed(1) +
        ' ' + (cx + (r() - 0.5) * 3).toFixed(1) + ' ' + (cy + h).toFixed(1) +
        '" fill="none" stroke="' + sk.shade + '" stroke-opacity="' + (0.07 + r() * 0.07).toFixed(3) +
        '" stroke-width="0.75"/>');
    }
    out.push('</g>');
    return out.join('');
  }

  /* 손톱을 감싸는 살은 자연 네일이 살에 붙어 있는 구간에만 있다. 프리엣지(손끝 밖으로
   * 자란 부분) 주위에는 살이 없으므로 그 위로는 능선을 그리지 않는다. */
  function foldClip(fg) {
    var d = { shape: 'oval', length: 0 };   // 폴드 범위는 길이와 무관하게 자연 네일 기준
    var m = G.nailMetrics(fg, d);
    var w = fg.w0 * 2;
    var cut = -(m.yc + m.bed * 0.92);
    return '<clipPath id="foldclip-' + fg.id + '"><rect x="' + (-w) + '" y="' + cut +
      '" width="' + (w * 2) + '" height="' + (Math.abs(cut) + G.BASE_OVERLAP + 40) + '"/></clipPath>';
  }

  function silhouette(order) {
    var parts = ['<path d="' + G.dorsumPath() + '"/>'];
    order.forEach(function (fg) { parts.push(fingerPathAbs(fg)); });
    return parts.join('');
  }

  /* 그림자는 한 겹이면 스티커를 띄운 것처럼 보인다. 접지에 가까운 진한 그림자와
   * 멀리 퍼지는 옅은 그림자를 겹쳐야 손이 공간 안에 놓인 것으로 읽힌다. */
  function handShadow(order) {
    var sil = silhouette(order);
    return '<g transform="translate(34 46)" filter="url(#soft22)" opacity="0.16" fill="#4a2718">' +
      sil + '</g>' +
      '<g transform="translate(13 17)" filter="url(#soft14)" opacity="0.2" fill="#53291a">' +
      sil + '</g>' +
      '<g transform="translate(5 6)" filter="url(#soft6)" opacity="0.16" fill="#4a2214">' +
      sil + '</g>';
  }

  function handClip(order, sk) {
    var out = ['<clipPath id="handClip">' + silhouette(order) + '</clipPath>'];
    order.forEach(function (fg) {
      var p = '<path d="' + G.fingerPath(fg) + '"/>';
      // 손가락 좌표계용 / 손 전체 좌표계용
      out.push('<clipPath id="fclip-' + fg.id + '">' + p + '</clipPath>');
      out.push(cylGradient('skinCyl-' + fg.id, fg, sk));
      out.push('<clipPath id="fclip-' + fg.id + '-abs">' + fingerPathAbs(fg) + '</clipPath>');
      out.push(foldClip(fg));
    });
    return out.join('');
  }

  /* 손등 음영. 테두리가 생기는 채움 대신 흐린 덩어리만 써서 손가락과의 경계선을 만들지 않는다. */
  function dorsumShading(sk) {
    var out = [], HI = hiOf(sk);
    // 힘줄 — 너클에서 손목 방향. 밝은 능선 + 옆의 골을 쌍으로 넣어야 튀어나와 보인다.
    [[402, 512, 448, 742], [476, 494, 484, 748], [548, 506, 530, 744], [612, 552, 574, 736]].forEach(function (t) {
      var d = 'M ' + t[0] + ' ' + t[1] + ' C ' + t[0] + ' ' + (t[1] + 80) + ' ' + t[2] + ' ' +
        (t[3] - 100) + ' ' + t[2] + ' ' + t[3];
      out.push('<g transform="translate(-5 0)"><path d="' + d + '" fill="none" stroke="' + sk.shade +
        '" stroke-opacity="0.08" stroke-width="9" filter="url(#soft14)"/></g>');
      out.push('<path d="' + d + '" fill="none" stroke="' + HI +
        '" stroke-opacity="0.16" stroke-width="12" filter="url(#soft14)"/>');
      out.push('<g transform="translate(7 0)"><path d="' + d + '" fill="none" stroke="' + sk.shade +
        '" stroke-opacity="0.1" stroke-width="10" filter="url(#soft14)"/></g>');
    });
    // 엄지·검지 사이 첫 번째 등쪽 근육(first dorsal interosseous) 볼륨
    out.push('<ellipse cx="392" cy="556" rx="30" ry="44" fill="' + HI +
      '" opacity="0.14" filter="url(#soft22)" transform="rotate(-18 392 556)"/>');
    // 너클 피부는 주변보다 약간 거칠고 어둡다
    [[402, 506, 20], [476, 488, 21], [548, 502, 20], [612, 544, 17]].forEach(function (k) {
      out.push('<ellipse cx="' + k[0] + '" cy="' + k[1] + '" rx="' + (k[2] * 1.6) + '" ry="' + (k[2] * 1.2) +
        '" fill="' + sk.shade + '" opacity="0.05" filter="url(#soft6)"/>');
    });
    // 너클 — 넓고 부드럽게. 작고 진하면 얼룩처럼 보인다.
    [[402, 506, 20], [476, 488, 21], [548, 502, 20], [612, 544, 17]].forEach(function (k) {
      out.push('<ellipse cx="' + k[0] + '" cy="' + k[1] + '" rx="' + (k[2] * 1.5) + '" ry="' + (k[2] * 1.1) +
        '" fill="' + HI + '" opacity="0.26" filter="url(#soft14)"/>');
      out.push('<ellipse cx="' + k[0] + '" cy="' + (k[1] + k[2] * 0.15) + '" rx="' + (k[2] * 0.42) +
        '" ry="' + (k[2] * 0.3) + '" fill="' + sk.shade + '" opacity="0.1" filter="url(#soft6)"/>');
      out.push('<ellipse cx="' + k[0] + '" cy="' + (k[1] + k[2] * 1.9) + '" rx="' + (k[2] * 1.35) +
        '" ry="' + (k[2] * 0.9) + '" fill="' + sk.shade + '" opacity="0.09" filter="url(#soft14)"/>');
    });
    // 손등 정맥 — 흐리고 옅게. 이게 없으면 손등이 밀랍판처럼 남는다.
    var vein = C.mix(sk.shade, '#3f5f74', 0.6);
    [
      'M 428 484 C 424 522 434 560 442 600 C 446 630 444 664 440 700',
      'M 498 468 C 496 508 502 552 500 604 C 499 640 502 672 506 704',
      'M 568 488 C 564 524 553 562 546 602 C 542 634 542 668 544 700',
      'M 498 516 C 476 526 456 522 440 510',
      'M 502 556 C 524 566 542 562 556 550',
      'M 458 596 C 480 606 512 608 540 600'
    ].forEach(function (d, i) {
      out.push('<path d="' + d + '" fill="none" stroke="' + vein + '" stroke-opacity="' +
        (i > 2 ? 0.1 : 0.15) + '" stroke-width="' + (i > 2 ? 4 : 6.5) +
        '" stroke-linecap="round" filter="url(#soft6)"/>');
    });
    // 너클 사이 중수골 사이 골
    [[440, 540], [514, 542], [582, 556]].forEach(function (v) {
      out.push('<ellipse cx="' + v[0] + '" cy="' + v[1] + '" rx="9" ry="30" fill="' + sk.shade +
        '" opacity="0.07" filter="url(#soft14)"/>');
    });
    // 엄지 두덩 · 손등 중앙 볼륨 · 새끼손가락 쪽 측면 음영
    out.push('<ellipse cx="332" cy="656" rx="58" ry="64" fill="' + C.lighten(sk.light, 0.2) +
      '" opacity="0.4" filter="url(#soft22)"/>');
    out.push('<ellipse cx="466" cy="606" rx="98" ry="104" fill="' + HI + '" opacity="0.15" filter="url(#soft22)"/>');
    out.push('<ellipse cx="642" cy="636" rx="30" ry="106" fill="' + C.darken(sk.dark, 0.25) +
      '" opacity="0.42" filter="url(#soft22)"/>');
    out.push('<ellipse cx="292" cy="700" rx="26" ry="52" fill="' + C.darken(sk.dark, 0.2) +
      '" opacity="0.3" filter="url(#soft22)"/>');
    // 손목 주름
    out.push('<ellipse cx="500" cy="720" rx="150" ry="90" fill="' + sk.warm +
      '" opacity="0.14" filter="url(#soft22)"/>');
    out.push('<path d="M 424 754 Q 512 776 612 750" fill="none" stroke="' + sk.shade +
      '" stroke-opacity="0.16" stroke-width="4" filter="url(#soft6)"/>');

    // 물갈퀴 골 바닥의 앰비언트 오클루전 — 골 주변 살이 어두워야 골이 깊어 보인다
    [[440, 524, 15], [514, 526, 15], [582, 542, 13], [378, 516, 13]].forEach(function (w) {
      out.push('<ellipse cx="' + w[0] + '" cy="' + w[1] + '" rx="' + w[2] + '" ry="' + (w[2] * 1.5) +
        '" fill="' + deepOf(sk) + '" opacity="0.24" filter="url(#soft6)"/>');
    });
    // 손가락이 손등에 드리우는 그림자 (밑동 오른쪽 아래)
    [[410, 520, 26], [484, 502, 27], [556, 516, 26], [618, 556, 22]].forEach(function (k) {
      out.push('<ellipse cx="' + (k[0] + k[2] * 0.45) + '" cy="' + (k[1] + k[2] * 1.1) + '" rx="' + (k[2] * 1.6) +
        '" ry="' + (k[2] * 0.95) + '" fill="' + sk.shade + '" opacity="0.075" filter="url(#soft22)"/>');
    });
    return out.join('');
  }

  /* ── 네일 렌더 ── */
  function nail(fg, d, sk, selected) {
    var m = G.nailMetrics(fg, d);
    var id = fg.id, hw = m.hw, T = m.T, yc = m.yc;
    var path = G.nailPath(fg, d, 0);
    var Y = function (r) { return -(yc + T * r); };
    var out = [];
    var bright = 1 - C.luma(d.color) * 0.42;   // 밝은 색일수록 하이라이트를 약하게

    // 네일 아래로 떨어지는 그림자
    out.push('<path d="' + G.nailPath(fg, d, -1.5) + '" transform="translate(1.6 2)" fill="#4a1f10" opacity="0.26" filter="url(#soft3)"/>');

    var g = ['<g clip-path="url(#clip-' + id + ')">'];
    g.push('<path d="' + path + '" fill="url(#bed-' + id + ')"/>');
    // 루눌라 — 밑동의 옅은 반달. 엄지가 가장 크고 소지는 거의 없다.
    var lun = { thumb: 1, index: 0.75, middle: 0.7, ring: 0.55, pinky: 0.25 }[id] || 0.6;
    if (lun > 0.3) {
      g.push('<ellipse cx="0" cy="' + (-(yc + T * 0.02)) + '" rx="' + (hw * 0.62 * lun) +
        '" ry="' + (Math.max(3, m.bed * 0.18) * lun) + '" fill="' + C.lighten(sk.base, 0.78) + '" opacity="' +
        (0.8 * lun).toFixed(2) + '" filter="url(#soft3)"/>');
    }
    g.push('<path d="' + path + '" fill="url(#bedBlood-' + id + ')"/>');
    // 프리엣지: 손끝 밖으로 나온 구간은 흰빛으로
    g.push('<path d="' + path + '" fill="url(#bedLen-' + id + ')"/>');

    // 베이스 폴리시. sheer 가 1보다 작으면 아래 베드(루눌라·프리엣지)가 비친다 —
    // 실제 네일 플레이트가 반투명한 것과 같다.
    var baseFill = d.art === 'cateye' ? 'url(#cat-' + id + ')' : 'url(#pol-' + id + ')';
    g.push('<path d="' + path + '" fill="' + baseFill + '"' +
      (d.sheer && d.sheer < 1 ? ' opacity="' + d.sheer + '"' : '') + '/>');

    // 아트 레이어
    if (d.art === 'french' || d.art === 'tip') {
      var tipFill = d.art === 'tip' ? 'url(#glit-' + id + ')' : 'url(#polTip-' + id + ')';
      if (d.art === 'tip') g.push('<path d="' + smilePath(hw, yc, T, FRENCH_START) + '" fill="' + C.darken(d.color2, 0.05) + '" opacity="0.55"/>');
      g.push('<path d="' + smilePath(hw, yc, T, FRENCH_START) + '" fill="' + tipFill + '" opacity="0.94"/>');
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
    if (d.finish === 'chrome') g.push('<path d="' + path + '" fill="url(#chromeEnv-' + id + ')"/>');
    if (d.finish === 'pearl') g.push('<path d="' + path + '" fill="url(#pearl-' + id + ')" opacity="0.5" style="mix-blend-mode:screen"/>');
    g.push('<path d="' + path + '" fill="url(#polShade-' + id + ')" opacity="' +
      (d.finish === 'matte' ? 0.15 : (d.sheer && d.sheer < 0.6 ? 0.55 : 0.4)) + '"/>');

    if (d.finish === 'matte') {
      g.push('<path d="' + path + '" fill="#ffffff" opacity="0.03"/>');
      g.push('<rect x="' + (-hw * 1.5) + '" y="' + Y(1.3) + '" width="' + (hw * 3) +
        '" height="' + (T * 1.5) + '" filter="url(#matteGrain)" opacity="0.22" ' +
        'style="mix-blend-mode:overlay"/>');
      g.push('<ellipse cx="' + (-hw * 0.2) + '" cy="' + Y(0.6) + '" rx="' + hw * 0.75 + '" ry="' + T * 0.34 +
        '" fill="#ffffff" opacity="' + (0.08 * bright).toFixed(3) + '" filter="url(#soft6)"/>');
    } else {
      var s = (d.finish === 'chrome' ? 1.25 : 1) * bright;
      // 넓게 퍼진 반사 + 그 안의 창문 모양 반사. 젤은 부드러운 덩어리가 아니라
      // 광원의 형태가 비친다.
      g.push('<ellipse cx="' + (-hw * 0.33) + '" cy="' + Y(0.55) + '" rx="' + hw * 0.4 + '" ry="' + T * 0.3 +
        '" fill="#ffffff" opacity="' + (0.22 * s).toFixed(3) + '" filter="url(#soft3)"/>');
      g.push('<path d="' + windowGloss(hw, yc, T, -0.36, 0.56, 0.2, 0.24) +
        '" fill="#ffffff" opacity="' + (0.46 * s).toFixed(3) + '" filter="url(#soft1)"/>');
      g.push('<path d="' + windowGloss(hw, yc, T, 0.42, 0.34, 0.11, 0.14) +
        '" fill="#ffffff" opacity="' + (0.2 * s).toFixed(3) + '" filter="url(#soft3)"/>');
      g.push('<ellipse cx="' + (-hw * 0.28) + '" cy="' + Y(0.78) + '" rx="' + hw * 0.12 + '" ry="' + T * 0.06 +
        '" fill="#ffffff" opacity="' + (0.9 * s).toFixed(3) + '" filter="url(#soft1)"/>');
      g.push('<ellipse cx="0" cy="' + Y(0.99) + '" rx="' + hw * 0.78 + '" ry="' + T * 0.05 +
        '" fill="#ffffff" opacity="' + (0.3 * s).toFixed(3) + '" filter="url(#soft3)"/>');
      g.push('<ellipse cx="' + (hw * 0.62) + '" cy="' + Y(0.38) + '" rx="' + hw * 0.17 + '" ry="' + T * 0.22 +
        '" fill="#ffffff" opacity="' + (0.16 * s).toFixed(3) + '" filter="url(#soft3)"/>');
    }

    // 큐티클 음영 + 자연 네일이 끝나는 선(프리엣지)
    g.push('<ellipse cx="0" cy="' + (-yc) + '" rx="' + hw * 0.95 + '" ry="' + Math.max(2.2, T * 0.07) +
      '" fill="#54240f" opacity="0.26" filter="url(#soft3)"/>');
    // 자연 네일이 끝나는 선은 시어일 때만 보인다. 불투명 폴리시는 이 경계를 덮는다 —
    // 그냥 그리면 모든 손톱에 가로 이음선이 생긴다.
    if (m.ext > 3 && (d.sheer || 1) < 0.75) {
      g.push('<path d="M ' + (-hw) + ' ' + (-(yc + m.bed)) + ' Q 0 ' + (-(yc + m.bed + hw * 0.3)) + ' ' + hw + ' ' + (-(yc + m.bed)) +
        '" fill="none" stroke="' + C.lighten(sk.base, 0.7) + '" stroke-width="1.6" opacity="0.28" filter="url(#soft1)"/>');
    }
    g.push('</g>');
    out.push(g.join(''));

    // 자연 네일의 세로 미세 융선 (폴리시가 두꺼우면 묻힌다)
    if (!d.sheer || d.sheer < 0.6) {
      var nr = prng(Math.round(hw * 131 + T));
      var ridges = [];
      for (var v = 0; v < 7; v++) {
        var vx = (nr() - 0.5) * hw * 1.5;
        ridges.push('<path d="M ' + vx.toFixed(1) + ' ' + (-(yc + T * 0.08)) + ' L ' +
          (vx + (nr() - 0.5) * 2).toFixed(1) + ' ' + (-(yc + T * 0.92)) +
          '" stroke="' + (v % 2 ? sk.shade : C.lighten(sk.base, 0.8)) + '" stroke-opacity="' +
          (0.05 + nr() * 0.05).toFixed(3) + '" stroke-width="' + (0.8 + nr()).toFixed(2) + '" fill="none"/>');
      }
      g.push('<g filter="url(#soft1)" clip-path="url(#clip-' + id + ')">' + ridges.join('') + '</g>');
    }

    // 손톱 측면은 네일 그루브 쪽으로 살짝 파여 있다
    g.push('<path d="' + path + '" fill="none" stroke="' + C.darken(d.color, 0.35) +
      '" stroke-opacity="0.3" stroke-width="3" filter="url(#soft3)"/>');

    // 배경이 네일 아래 테두리에 비친다 (젤은 반사가 강하다)
    if (d.finish !== 'matte') {
      g.push('<path d="' + G.nailPath(fg, d, 1.6) + '" fill="none" stroke="' + C.lighten(sk.light, 0.4) +
        '" stroke-opacity="0.3" stroke-width="1.8" clip-path="url(#sideclip-' + id + ')" filter="url(#soft1)"/>');
    }

    // 큐티클: 살이 손톱 밑동을 살짝 덮는다. 손톱 위에 살색으로 얹어야 "박혀 있는" 느낌이 난다.
    out.push('<ellipse cx="0" cy="' + (-(yc - hw * 0.05)) + '" rx="' + (hw * 0.9) +
      '" ry="' + Math.max(2.4, m.bed * 0.1) + '" fill="' + C.mix(sk.base, sk.warm, 0.3) +
      '" opacity="' + (m.ext > 20 ? 0.6 : 0.75) + '" filter="url(#soft1)"/>');
    out.push('<ellipse cx="0" cy="' + (-(yc + hw * 0.16)) + '" rx="' + (hw * 0.82) +
      '" ry="' + Math.max(1.6, m.bed * 0.06) + '" fill="' + sk.shade +
      '" opacity="0.16" filter="url(#soft1)"/>');

    // 테두리: 밑동·측면은 어둡고 팁 끝은 네일 두께가 빛을 받아 밝다. 두 개를 각각
    // 클립해 그리면 경계에서 단이 보이므로 길이 방향 그라디언트 하나로 칠한다.
    out.push('<path d="' + path + '" fill="none" stroke="url(#rim-' + id + ')" stroke-width="1" ' +
      'opacity="0.6" filter="url(#soft1)"/>');

    if (selected) {
      out.push('<path d="' + G.nailPath(fg, d, -4.5) + '" fill="none" stroke="#c2185b" stroke-width="2" ' +
        'stroke-dasharray="5 4" opacity="0.95"/>');
    }
    return out.join('');
  }

  /* 광원(창문)이 젤 표면에 비친 모양. 모서리가 둥근 사각형 — 타원 얼룩보다 젤답다. */
  function windowGloss(hw, yc, T, cxr, cyr, wr, hr) {
    var cx = hw * cxr, cy = -(yc + T * cyr);
    var w = hw * wr, h = T * hr, r = Math.min(w, h) * 0.55;
    return 'M ' + (cx - w + r) + ' ' + (cy - h) +
      ' L ' + (cx + w - r) + ' ' + (cy - h) + ' Q ' + (cx + w) + ' ' + (cy - h) + ' ' + (cx + w) + ' ' + (cy - h + r) +
      ' L ' + (cx + w) + ' ' + (cy + h - r) + ' Q ' + (cx + w) + ' ' + (cy + h) + ' ' + (cx + w - r) + ' ' + (cy + h) +
      ' L ' + (cx - w + r) + ' ' + (cy + h) + ' Q ' + (cx - w) + ' ' + (cy + h) + ' ' + (cx - w) + ' ' + (cy + h - r) +
      ' L ' + (cx - w) + ' ' + (cy - h + r) + ' Q ' + (cx - w) + ' ' + (cy - h) + ' ' + (cx - w + r) + ' ' + (cy - h) + ' Z';
  }

  // 프렌치 스마일 라인 위쪽 영역 (네일 path로 클립되어 팁만 남는다)
  function smilePath(hw, yc, T, start) {
    var w = hw * 1.4, y0 = -(yc + T * start), y1 = -(yc + T * (start + 0.28)), top = -(yc + T * 1.4);
    return 'M ' + (-w) + ' ' + y0 + ' Q 0 ' + y1 + ' ' + w + ' ' + y0 + ' L ' + w + ' ' + top + ' L ' + (-w) + ' ' + top + ' Z';
  }
  function smileLine(hw, yc, T, start) {
    var w = hw * 1.4, y0 = -(yc + T * start), y1 = -(yc + T * (start + 0.28));
    return 'M ' + (-w) + ' ' + y0 + ' Q 0 ' + y1 + ' ' + w + ' ' + y0;
  }

  /* 프렌치 팁 색상 그라디언트는 defs에 따로 필요 */
  function tipDefs(fg, d) {
    if (d.art !== 'french') return '';
    return grad('polTip-' + fg.id, 0, 1, 0, 0, [
      [0, C.darken(d.color2, 0.06)], [0.5, d.color2], [1, C.lighten(d.color2, 0.2)]
    ]);
  }

  /* 배경 비네트 — 사진은 테두리가 미세하게 떨어진다 */
  function vignette(kind) {
    var c = kind === 'noir' ? '#000000' : '#6b4a38';
    return '<defs><radialGradient id="vig" cx="0.46" cy="0.4" r="0.78">' +
      stop(0, c + '00') + stop(0.62, c + '00') + stop(1, c + (kind === 'noir' ? '8c' : '3d')) +
      '</radialGradient></defs><rect width="900" height="980" fill="url(#vig)"/>';
  }

  /* ── 배경 ── */
  function backdrop(kind) {
    if (kind === 'noir') {
      return '<defs><radialGradient id="bg" cx="0.42" cy="0.3" r="0.92">' +
        stop(0, '#413848') + stop(0.5, '#251f2c') + stop(0.82, '#141118') +
        stop(1, '#0b0a0f') + '</radialGradient></defs>' +
        '<rect width="900" height="980" fill="url(#bg)"/>';
    }
    if (kind === 'blush') {
      return '<defs><radialGradient id="bg" cx="0.4" cy="0.28" r="0.98">' +
        stop(0, '#fef5f6') + stop(0.45, '#f8e3e7') + stop(0.8, '#eecdd4') +
        stop(1, '#e0bcc6') + '</radialGradient></defs>' +
        '<rect width="900" height="980" fill="url(#bg)"/>';
    }
    return '<defs><radialGradient id="bg" cx="0.4" cy="0.26" r="0.98">' +
      stop(0, '#fffcf8') + stop(0.42, '#f6e9df') + stop(0.78, '#e8d6c9') +
      stop(1, '#d6c6bd') + '</radialGradient></defs>' +
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

    var defs = ['<defs>', skinDefs(sk), handClip(order, sk)];
    fingers.forEach(function (fg) {
      defs.push(nailDefs(fg, state.nails[fg.id], sk), tipDefs(fg, state.nails[fg.id]));
    });
    defs.push('</defs>');

    var body = [];
    body.push(backdrop(state.backdrop));
    body.push(defs.join(''));
    body.push(handShadow(order));

    // 0) 물갈퀴 깊은 곳의 그림자. 손 실루엣이 대부분 덮고, 손가락 사이 틈에만 남는다 —
    // 틈으로 밝은 배경이 보이면 손이 오려낸 종이처럼 읽힌다.
    // 블러를 크게 주면 틈 밖으로 새어 배경에 검은 구름이 생긴다 — 작고 얕게.
    body.push('<g fill="' + deepOf(sk) + '" opacity="0.55">');
    [[440, 508, 7, 20], [514, 510, 7, 20], [582, 526, 6, 17], [376, 504, 6, 17]].forEach(function (w) {
      body.push('<ellipse cx="' + w[0] + '" cy="' + w[1] + '" rx="' + w[2] + '" ry="' + w[3] +
        '" filter="url(#soft3)"/>');
    });
    body.push('</g>');

    // 1) 손등과 손가락을 같은 평면 살색으로 한 덩어리로 칠한다 — 내부 경계선이 생기지 않게
    body.push('<g fill="' + sk.base + '">' + silhouette(order) + '</g>');

    // 2~6) 음영은 모두 손 실루엣 안쪽에만.
    // 손가락 원통 음영 → 전체 조명 → 손등 볼륨 순서. 조명을 나중에 얹어야
    // 밑동에서 평평하게 되돌린 부분이 손등과 같은 빛을 받아 이어져 보인다.
    body.push('<g clip-path="url(#handClip)">');
    order.forEach(function (fg) {
      body.push(fingerGroup(fg, fingerShading(fg, sk, state.nails[fg.id])));
    });
    body.push('<rect width="900" height="980" fill="url(#globalLight)"/>');
    body.push(dorsumShading(sk));
    // 왼쪽 손가락이 오른쪽 이웃에 드리우는 그림자
    var rightOf = { thumb: 'index', index: 'middle', middle: 'ring', ring: 'pinky' };
    order.forEach(function (fg) {
      var nb = rightOf[fg.id];
      if (!nb) return;
      body.push('<g clip-path="url(#fclip-' + nb + '-abs)" transform="translate(12 7)" ' +
        'filter="url(#soft6)" opacity="0.3" fill="' + sk.shade + '">' + fingerPathAbs(fg) + '</g>');
    });
    // 실루엣 안쪽 테두리를 살짝 어둡게 — 사진의 형태 감쇠. 없으면 스티커처럼 납작하다.
    body.push('<g clip-path="url(#handClip)">');
    body.push('<g filter="url(#soft6)" fill="none" stroke="' + sk.shade + '" stroke-opacity="0.16" ' +
      'stroke-width="6">' + silhouette(order) + '</g>');
    body.push('<g filter="url(#soft6)" fill="none" stroke="' + sk.shade + '" stroke-opacity="0.26" ' +
      'stroke-width="7" transform="translate(4 5)">' + silhouette(order) + '</g>');
    body.push('</g>');
    // 배경에서 되돌아오는 바운스 라이트 (아래쪽 테두리)
    body.push('<g clip-path="url(#handClip)"><g filter="url(#soft6)" fill="none" stroke="' +
      C.lighten(sk.light, 0.5) + '" stroke-opacity="0.14" stroke-width="2.6" ' +
      'transform="translate(-3 -5)">' + silhouette(order) + '</g></g>');

    // 피부 질감 — 색 얼룩(저주파) 위에 모공(고주파). 순서와 블렌드가 중요하다.
    body.push('<rect width="900" height="980" filter="url(#mottle)" opacity="0.34" ' +
      'style="mix-blend-mode:multiply"/>');
    body.push('<rect width="900" height="980" filter="url(#mottleWarm)" opacity="0.4" ' +
      'style="mix-blend-mode:soft-light"/>');
    body.push('<rect width="900" height="980" filter="url(#mottleFine)" opacity="0.1" ' +
      'style="mix-blend-mode:multiply"/>');
    body.push('<rect width="900" height="980" filter="url(#pores)" opacity="0.2" ' +
      'style="mix-blend-mode:multiply"/>');
    body.push('<rect width="900" height="980" filter="url(#poresHi)" opacity="0.16" ' +
      'style="mix-blend-mode:screen"/>');
    body.push('</g>');

    // 7) 네일. 선택 표시는 손톱별로 편집할 때만 (전체 적용 중이면 5개 다 테두리가 생겨 산만하다)
    var mark = opts.selectable !== false && !state.sync;
    order.forEach(function (fg) {
      var d = state.nails[fg.id];
      body.push(nailGroup(fg, d, nail(fg, d, sk, mark && state.selected.indexOf(fg.id) >= 0)));
    });

    // 클릭 영역 (네일 위)
    if (opts.selectable !== false) {
      fingers.forEach(function (fg) {
        var d = state.nails[fg.id];
        body.push(nailGroup(fg, d, '<path class="nail-hit" data-finger="' + fg.id + '" d="' +
          G.nailPath(fg, d, -6) + '" fill="transparent"/>'));
      });
    }

    body.push(vignette(state.backdrop));

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
