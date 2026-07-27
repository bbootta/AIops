/* 손 · 네일 기하 정의 (SVG 좌표계, viewBox 0 0 900 980)
 *
 * 손등을 정면에서 본 포즈. 각 손가락은 기준점(bx,by)·기울기(angle)·길이(len)·
 * 반폭(w0=밑, w1=끝)으로 정의하고, 실제 path는 여기서 생성한다.
 * 손가락 내부 좌표계: translate(bx,by) rotate(angle) 안에서 (x, -y)
 * → x는 손가락을 가로지르는 축, y는 밑에서 끝으로 향하는 축.
 */
(function (NS) {
  'use strict';

  /* bend = 끝으로 갈수록 휘는 각도(도). 밑동은 부챗살처럼 벌어져도 끝은 서로
   * 모이는 게 편안한 손 모양이다. 곧고 나란한 막대 다섯 개는 마네킹처럼 보인다. */
  var FINGERS = [
    { id: 'thumb',  name: '엄지', bx: 330, by: 676, angle: -46,  len: 206, w0: 33,   w1: 26.5, bend: 14 },
    { id: 'index',  name: '검지', bx: 402, by: 496, angle: -11,  len: 228, w0: 28,   w1: 21.2, bend: 6 },
    { id: 'middle', name: '중지', bx: 476, by: 474, angle: -1,   len: 252, w0: 29,   w1: 21.9, bend: 1.5 },
    { id: 'ring',   name: '약지', bx: 548, by: 488, angle: 9,    len: 231, w0: 27.5, w1: 20.7, bend: -5 },
    { id: 'pinky',  name: '소지', bx: 612, by: 540, angle: 19,   len: 180, w0: 23.5, w1: 18.0, bend: -9 }
  ];

  /* 밑동을 원점으로 deg 만큼 회전 (손가락 좌표계) */
  function rot(x, y, deg) {
    var a = deg * Math.PI / 180, c = Math.cos(a), s = Math.sin(a);
    return [x * c - y * s, x * s + y * c];
  }

  /* 손등 실루엣. 너클(봉우리 / 물갈퀴 골) → 새끼손가락 쪽 측면 → 손목·팔목(화면 밖) →
   * 엄지 두덩(thenar) → 엄지·검지 사이 물갈퀴. 손바닥 길이:너클 폭 ≈ 1.05 로 맞췄다. */
  var DORSUM = [
    [636, 552], [648, 602], [646, 656], [634, 706],
    [616, 748], [604, 812], [598, 900], [594, 1000],
    [432, 1000], [428, 900], [424, 812], [414, 752],
    [376, 742], [330, 734], [296, 714], [280, 682], [288, 648], [310, 618],
    [338, 596], [358, 566], [370, 534], [376, 512],
    [388, 484], [402, 472], [420, 490], [432, 512], [440, 522], [448, 512],
    [460, 486], [476, 454], [494, 490], [507, 514], [514, 524], [522, 512],
    [534, 480], [548, 468], [564, 496], [576, 528], [582, 540], [590, 528],
    [601, 512], [612, 510], [626, 528]
  ];

  /* Catmull-Rom → 3차 베지어. 유기적인 실루엣을 점 목록으로 편집할 수 있게 해준다.
   * 같은 점을 연달아 넣으면 그 지점이 뾰족해진다(스퀘어/코핀/스틸레토 팁에 사용). */
  function smooth(pts, closed, tension) {
    var t = (tension == null ? 1 : tension) / 6;
    var n = pts.length;
    var at = function (i) {
      if (closed) return pts[(i + n) % n];
      return pts[Math.max(0, Math.min(n - 1, i))];
    };
    var d = ['M ' + f(pts[0][0]) + ' ' + f(pts[0][1])];
    var last = closed ? n : n - 1;
    for (var i = 0; i < last; i++) {
      var p0 = at(i - 1), p1 = at(i), p2 = at(i + 1), p3 = at(i + 2);
      var c1 = [p1[0] + (p2[0] - p0[0]) * t, p1[1] + (p2[1] - p0[1]) * t];
      var c2 = [p2[0] - (p3[0] - p1[0]) * t, p2[1] - (p3[1] - p1[1]) * t];
      d.push('C ' + f(c1[0]) + ' ' + f(c1[1]) + ' ' + f(c2[0]) + ' ' + f(c2[1]) +
             ' ' + f(p2[0]) + ' ' + f(p2[1]));
    }
    if (closed) d.push('Z');
    return d.join(' ');
  }

  function f(v) { return Math.round(v * 100) / 100; }

  function dorsumPath() { return smooth(DORSUM, true, 1); }

  /* 손가락 폭 프로파일: [길이비, 보정계수]. 밑에서 끝으로 가늘어지면서
   * 두 관절에서 살짝 볼륨이 붙는다 — 균일한 원통처럼 보이지 않게. */
  var PROFILE = [
    [0, 1.0], [0.15, 1.005], [0.32, 1.02], [0.43, 0.995],
    [0.58, 1.015], [0.70, 0.99], [0.82, 0.965], [0.9, 0.925]
  ];
  var BASE_OVERLAP = 54;   // 손등에 파묻히는 길이

  /* 손가락 실루엣 — 손가락 그룹 좌표계 기준.
   * 길이비 t 지점을 bend*t 만큼 밑동 기준으로 돌려 완만한 호를 만든다. */
  function fingerPath(fg) {
    var L = fg.len;
    var w = function (t, k) { return (fg.w0 + (fg.w1 - fg.w0) * t) * k; };
    var at = function (x, t) { return rot(x, -t * L, bendAt(fg, t)); };
    var left = [], right = [];
    PROFILE.forEach(function (p) {
      var x = w(p[0], p[1]);
      left.push(at(-x, p[0]));
      right.push(at(x, p[0]));
    });
    var we = w(0.9, 0.925);
    var pts = left.concat(
      [at(-we * 0.62, 0.975), at(0, 1), at(we * 0.62, 0.975)],
      right.reverse()
    );
    return smooth(pts, false, 1) +
      ' L ' + f(fg.w0) + ' ' + BASE_OVERLAP + ' L ' + f(-fg.w0) + ' ' + BASE_OVERLAP + ' Z';
  }

  function bendAt(fg, t) { return (fg.bend || 0) * t; }

  /* 네일은 손톱이 얹히는 지점의 휘어진 각도를 그대로 따라간다. */
  function nailBend(fg, design) {
    var m = nailMetrics(fg, design);
    return bendAt(fg, (m.yc + m.T * 0.5) / fg.len);
  }

  /* 손가락 관절 주름 — 첫째·둘째 관절. 손가락마다 위치를 조금씩 흩어
   * 다섯 개가 똑같이 찍히지 않게 한다. */
  function knuckleLines(fg) {
    var L = fg.len;
    var w = function (t) { return fg.w0 + (fg.w1 - fg.w0) * t; };
    var j = ((fg.id.charCodeAt(0) * 7) % 9 - 4) / 100;   // -0.04 ~ +0.04
    return [0.37 + j, 0.66 - j].map(function (t, i) {
      return { t: t, y: -t * L, w: w(t) * (i ? 0.58 : 0.62), bend: bendAt(fg, t) };
    });
  }

  /* ── 네일 ──────────────────────────────────────────────────────────
   * 모양 정의: 왼쪽 절반 점 목록. x는 hw(반폭) 배수, y는 T(전체 길이) 배수.
   * 큐티클(y=0)에서 시작해 팁(0,1)까지. 오른쪽은 미러링.
   */
  var SHAPES = {
    round:    { name: '라운드', pts: [[-0.86, 0.02], [-0.99, 0.30], [-1.00, 0.62], [-0.88, 0.87], [-0.52, 0.98]] },
    oval:     { name: '오벌',   pts: [[-0.86, 0.02], [-0.99, 0.32], [-0.97, 0.62], [-0.79, 0.88], [-0.44, 0.99]] },
    squoval:  { name: '스퀘어라운드', pts: [[-0.86, 0.02], [-0.99, 0.28], [-1.00, 0.64], [-0.99, 0.88], [-0.86, 0.985], [-0.52, 1.0]] },
    square:   { name: '스퀘어', pts: [[-0.86, 0.02], [-0.99, 0.28], [-1.00, 0.66], [-1.00, 0.94], [-0.97, 1.0], [-0.97, 1.0], [-0.5, 1.0]] },
    almond:   { name: '아몬드', pts: [[-0.86, 0.02], [-0.99, 0.30], [-0.93, 0.58], [-0.68, 0.80], [-0.36, 0.93], [-0.12, 0.99]] },
    stiletto: { name: '스틸레토', pts: [[-0.86, 0.02], [-0.99, 0.26], [-0.85, 0.50], [-0.58, 0.72], [-0.30, 0.88], [-0.09, 0.975], [-0.02, 1.0], [-0.02, 1.0]] },
    coffin:   { name: '코핀',   pts: [[-0.86, 0.02], [-0.99, 0.28], [-0.96, 0.56], [-0.74, 0.80], [-0.55, 0.955], [-0.50, 1.0], [-0.50, 1.0]] }
  };

  var LENGTHS = [
    { name: '짧게', ext: 0.0 },
    { name: '보통', ext: 0.34 },
    { name: '길게', ext: 0.66 },
    { name: '아주 길게', ext: 1.00 }
  ];

  /* 손가락 + 디자인 → 네일 배치 정보 (그룹 좌표계) */
  /* 손톱 비율은 손가락마다 다르다. 엄지는 폭에 비해 짧고(가로로 넓은 손톱),
   * 소지는 전체가 작다. 다섯 개를 같은 비율로 그리면 붙여놓은 것처럼 보인다. */
  var NAIL_ASPECT = { thumb: 1.62, index: 2.12, middle: 2.18, ring: 2.12, pinky: 1.95 };

  function nailMetrics(fg, design) {
    var hw = fg.w1 * 0.78;             // 네일 반폭. 사진처럼 양옆에 살이 보이게 손끝보다 좁다
    var bed = hw * (NAIL_ASPECT[fg.id] || 2.12);   // 자연 네일(네일 베드) 길이
    var ext = bed * LENGTHS[design.length].ext / 1.06;  // 연장 길이
    var T = bed + ext;
    var yc = fg.len - fg.w1 * 0.30 - bed;   // 큐티클 위치 (밑에서부터의 거리)
    return { hw: hw, bed: bed, T: T, yc: yc, ext: ext };
  }

  /* 네일 외곽 path — 그룹 좌표계. inset>0 이면 안쪽으로 축소(림/그림자용). */
  function nailPath(fg, design, inset) {
    var m = nailMetrics(fg, design);
    var s = SHAPES[design.shape] || SHAPES.round;
    var hw = m.hw - (inset || 0);
    var T = m.T - (inset || 0) * 1.4;
    var yc = m.yc + (inset || 0) * 0.7;

    // 완전한 좌우 대칭은 인공적이다. 손가락마다 한쪽을 아주 조금 넓힌다.
    var skew = 1 + (((design.shape || '').length + fg.id.charCodeAt(0)) % 5 - 2) * 0.012;
    var half = s.pts.map(function (p) { return [p[0] * hw * skew, -(yc + p[1] * T)]; });
    var ring = half.slice();
    ring.push([0, -(yc + T)]);
    for (var i = half.length - 1; i >= 0; i--) ring.push([-half[i][0] / (skew * skew), half[i][1]]);
    ring.push([0, -(yc - hw * 0.09)]);   // 큐티클 중앙이 살짝 아래로 파인다
    return smooth(ring, true, 1);
  }

  NS.geom = {
    FINGERS: FINGERS,
    SHAPES: SHAPES,
    LENGTHS: LENGTHS,
    BASE_OVERLAP: BASE_OVERLAP,
    dorsumPath: dorsumPath,
    fingerPath: fingerPath,
    knuckleLines: knuckleLines,
    nailPath: nailPath,
    nailMetrics: nailMetrics,
    nailBend: nailBend,
    bendAt: bendAt,
    smooth: smooth,
    f: f
  };
})(window.NailSim = window.NailSim || {});
