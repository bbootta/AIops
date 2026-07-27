/* 3D 손 — WebGL2로 직접 그린다.
 *
 * 라이브러리를 쓰지 않는다. 이 프로젝트는 빌드 과정도 의존성도 없어야 하는데,
 * three.js 를 벤더링하면 그 성질이 깨진다. 형태 생성·행렬·셰이딩을 전부 여기서 한다.
 *
 * 좌표계: x 오른쪽, y 손끝 방향, z 손등 쪽(화면 밖). 단위는 cm.
 * 손등을 보고 있으므로 오른손이고 엄지가 왼쪽(-x)에 온다.
 */
(function (NS) {
  'use strict';

  var G = NS.geom, C = NS.color, D = NS.data;

  /* ── 벡터 · 행렬 ────────────────────────────────────────────────── */
  function add(a, b) { return [a[0] + b[0], a[1] + b[1], a[2] + b[2]]; }
  function sub(a, b) { return [a[0] - b[0], a[1] - b[1], a[2] - b[2]]; }
  function mul(a, s) { return [a[0] * s, a[1] * s, a[2] * s]; }
  function dot(a, b) { return a[0] * b[0] + a[1] * b[1] + a[2] * b[2]; }
  function cross(a, b) {
    return [a[1] * b[2] - a[2] * b[1], a[2] * b[0] - a[0] * b[2], a[0] * b[1] - a[1] * b[0]];
  }
  function norm(a) {
    var l = Math.hypot(a[0], a[1], a[2]) || 1;
    return [a[0] / l, a[1] / l, a[2] / l];
  }
  /* 로드리게스 회전 */
  function rotAxis(v, axis, deg) {
    var a = deg * Math.PI / 180, c = Math.cos(a), s = Math.sin(a), k = norm(axis);
    return add(add(mul(v, c), mul(cross(k, v), s)), mul(k, dot(k, v) * (1 - c)));
  }

  function perspective(fovy, asp, n, f) {
    var t = 1 / Math.tan(fovy * Math.PI / 360), o = new Float32Array(16);
    o[0] = t / asp; o[5] = t; o[10] = (f + n) / (n - f); o[11] = -1; o[14] = 2 * f * n / (n - f);
    return o;
  }
  function lookAt(eye, ctr, up) {
    var z = norm(sub(eye, ctr)), x = norm(cross(up, z)), y = cross(z, x), o = new Float32Array(16);
    o[0] = x[0]; o[1] = y[0]; o[2] = z[0];
    o[4] = x[1]; o[5] = y[1]; o[6] = z[1];
    o[8] = x[2]; o[9] = y[2]; o[10] = z[2];
    o[12] = -dot(x, eye); o[13] = -dot(y, eye); o[14] = -dot(z, eye); o[15] = 1;
    return o;
  }
  function mmul(a, b) {
    var o = new Float32Array(16);
    for (var i = 0; i < 4; i++) for (var j = 0; j < 4; j++) {
      var s = 0;
      for (var k = 0; k < 4; k++) s += a[k * 4 + j] * b[i * 4 + k];
      o[i * 4 + j] = s;
    }
    return o;
  }

  /* ── 메시 ──────────────────────────────────────────────────────────
   * 면 법선을 누적해 부드러운 법선을 만든다. 감기 방향을 손으로 맞추다 보면
   * 한 군데씩 뒤집히므로, 닫힌 메시의 부호 있는 부피로 검사해 자동으로 바로잡는다.
   */
  function Mesh() { this.p = []; this.uv = []; this.i = []; }
  Mesh.prototype.add = function (p, u, v) {
    this.p.push(p[0], p[1], p[2]);
    this.uv.push(u || 0, v || 0);
    return this.p.length / 3 - 1;
  };
  Mesh.prototype.tri = function (a, b, c) { this.i.push(a, b, c); };
  Mesh.prototype.quad = function (a, b, c, d) { this.i.push(a, b, c, a, c, d); };
  Mesh.prototype.at = function (k) { return [this.p[k * 3], this.p[k * 3 + 1], this.p[k * 3 + 2]]; };
  Mesh.prototype.merge = function (o) {
    var off = this.p.length / 3, i;
    for (i = 0; i < o.p.length; i++) this.p.push(o.p[i]);
    for (i = 0; i < o.uv.length; i++) this.uv.push(o.uv[i]);
    for (i = 0; i < o.i.length; i++) this.i.push(o.i[i] + off);
    return this;
  };
  /* 부피가 음수면 안팎이 뒤집힌 것이다.
   * 반드시 닫힌 덩어리 하나씩 따로 검사해야 한다 — 손가락 프레임은 손바닥과
   * 손잡이(handedness)가 반대라 감기 방향도 반대다. 여러 덩어리를 합친 뒤
   * 한 번에 검사하면 부피가 상쇄돼 뒤집힌 쪽을 못 잡는다. */
  Mesh.prototype.orient = function () {
    var vol = 0;
    for (var k = 0; k < this.i.length; k += 3) {
      vol += dot(this.at(this.i[k]), cross(this.at(this.i[k + 1]), this.at(this.i[k + 2])));
    }
    if (vol < 0) for (var m = 0; m < this.i.length; m += 3) {
      var t = this.i[m + 1]; this.i[m + 1] = this.i[m + 2]; this.i[m + 2] = t;
    }
    return this;
  };
  Mesh.prototype.normals = function () {
    var n = new Float32Array(this.p.length), k, m;
    for (k = 0; k < this.i.length; k += 3) {
      var a = this.i[k] * 3, b = this.i[k + 1] * 3, c = this.i[k + 2] * 3;
      var f = cross(
        [this.p[b] - this.p[a], this.p[b + 1] - this.p[a + 1], this.p[b + 2] - this.p[a + 2]],
        [this.p[c] - this.p[a], this.p[c + 1] - this.p[a + 1], this.p[c + 2] - this.p[a + 2]]
      );
      for (m = 0; m < 3; m++) {
        var o = this.i[k + m] * 3;
        n[o] += f[0]; n[o + 1] += f[1]; n[o + 2] += f[2];
      }
    }
    for (k = 0; k < n.length; k += 3) {
      var l = Math.hypot(n[k], n[k + 1], n[k + 2]) || 1;
      n[k] /= l; n[k + 1] /= l; n[k + 2] /= l;
    }
    return n;
  };


  /* ── 손 정의 ──────────────────────────────────────────────────────
   * splay = 밑동에서 벌어지는 각(+가 엄지 쪽), curl = 손끝으로 갈수록 손바닥
   * 쪽으로 감기는 총 각도, roll = 손가락 축을 중심으로 한 회전(손톱이 향하는 방향).
   * 엄지만 방향을 직접 준다 — 다른 손가락과 달리 손바닥 앞쪽으로 나와 있다.
   */
  var FINGERS = [
    { id: 'thumb',  base: [-3.15, -2.05, -0.50], dir: [-0.66, 0.73, -0.16], len: 6.3, r0: 1.02, r1: 0.76, curl: 16, roll: 58, bed: 1.62, sink: 2.3 },
    { id: 'index',  base: [-2.30, 4.35, 0.20], splay: 7,   len: 7.4, r0: 0.86, r1: 0.60, curl: 22, roll: -9, bed: 1.38, sink: 2.1 },
    { id: 'middle', base: [-0.77, 4.75, 0.25], splay: 1,   len: 8.1, r0: 0.89, r1: 0.62, curl: 20, roll: 0,  bed: 1.48, sink: 2.1 },
    { id: 'ring',   base: [0.76, 4.55, 0.20],  splay: -6,  len: 7.6, r0: 0.84, r1: 0.59, curl: 24, roll: 7,  bed: 1.38, sink: 2.1 },
    { id: 'pinky',  base: [2.22, 3.85, 0.10],  splay: -13, len: 5.9, r0: 0.73, r1: 0.52, curl: 26, roll: 15, bed: 1.10, sink: 1.9 }
  ];
  var IDS = FINGERS.map(function (f) { return f.id; });

  /* 관절에서 살짝 굵어진다 — 균일한 원뿔은 마네킹처럼 보인다 */
  function radiusAt(f, t) {
    var r = f.r0 + (f.r1 - f.r0) * t;
    return r * (1 + 0.035 * Math.exp(-Math.pow((t - 0.34) / 0.13, 2))
                  + 0.030 * Math.exp(-Math.pow((t - 0.68) / 0.12, 2)));
  }

  /* 스파인을 호 길이와 함께 샘플링한다. 손톱을 손끝에서부터 재려면 필요하다. */
  var SPINE_STEPS = 26;
  function buildSpine(f) {
    var dir = f.dir ? norm(f.dir) : norm(rotAxis([0, 1, 0], [0, 0, 1], f.splay));
    var p = f.base.slice(), out = [], s = 0, i;
    var step = f.len / SPINE_STEPS;
    for (i = 0; i <= SPINE_STEPS; i++) {
      var t = i / SPINE_STEPS;
      // 손가락 축을 가로지르는 축. 손가락은 이 축을 중심으로 손바닥 쪽으로 감긴다.
      var side = norm(cross([0, 0, 1], dir));
      var up = norm(cross(dir, side));
      if (f.roll) { side = norm(rotAxis(side, dir, f.roll * t)); up = norm(cross(dir, side)); }
      out.push({ p: p.slice(), t: dir.slice(), side: side, up: up, s: s, r: radiusAt(f, t) });
      if (i === SPINE_STEPS) break;
      p = add(p, mul(dir, step));
      s += step;
      dir = norm(rotAxis(dir, norm(cross([0, 0, 1], dir)), f.curl / SPINE_STEPS));
      // 밑동은 벌어지되 끝은 서로 모인다
      if (f.splay) dir = norm(rotAxis(dir, [0, 0, 1], -f.splay * 0.5 / SPINE_STEPS));
    }
    return out;
  }
  var SPINES = {};
  FINGERS.forEach(function (f) { SPINES[f.id] = buildSpine(f); });

  /* 호 길이 s 지점의 프레임. 손끝을 넘어가면(연장 손톱) 접선 방향으로 잇는다. */
  function sample(f, s) {
    var sp = SPINES[f.id], last = sp[sp.length - 1];
    if (s >= last.s) {
      return { p: add(last.p, mul(last.t, s - last.s)), t: last.t, side: last.side, up: last.up, r: last.r };
    }
    for (var i = 1; i < sp.length; i++) {
      if (sp[i].s >= s) {
        var a = sp[i - 1], b = sp[i], k = (s - a.s) / (b.s - a.s);
        return {
          p: add(a.p, mul(sub(b.p, a.p), k)),
          t: norm(add(a.t, mul(sub(b.t, a.t), k))),
          side: norm(add(a.side, mul(sub(b.side, a.side), k))),
          up: norm(add(a.up, mul(sub(b.up, a.up), k))),
          r: a.r + (b.r - a.r) * k
        };
      }
    }
    return sp[0];
  }

  /* ── 형태 = 부호거리장 ─────────────────────────────────────────────
   * 원기둥·타원체를 그대로 겹쳐 놓으면 교차선이 자국으로 남아 혹을 붙인 것처럼
   * 보인다. 손은 그런 경계가 없는 한 덩어리다. 그래서 부위마다 거리장을 정의하고
   * 부드럽게 합친 뒤(smin) 등위면을 뽑아 메시로 만든다.
   *
   * 이 장은 정확한 거리함수가 아니어도 된다 — 필요한 건 0 등위면의 위치이고,
   * 법선은 중심차분 기울기로 얻으므로 어떤 스칼라장이든 등위면에 수직으로 나온다.
   * 덕분에 z 를 늘려 납작한 단면을 만드는 것 같은 편법을 그냥 써도 된다.
   */
  function smin(a, b, k) {
    var h = Math.max(0, Math.min(1, 0.5 + 0.5 * (b - a) / k));
    return b + (a - b) * h - k * h * (1 - h);
  }
  /* 끝이 굵기가 다른 캡슐. zk 를 주면 z 방향으로 눌린 단면이 된다. */
  function segZ(x, y, z, a, b, ra, rb, zk) {
    var k = zk || 1;
    var bx = b[0] - a[0], by = b[1] - a[1], bz = (b[2] - a[2]) * k;
    var px = x - a[0], py = y - a[1], pz = (z - a[2]) * k;
    var dd = bx * bx + by * by + bz * bz;
    var h = dd > 1e-9 ? Math.max(0, Math.min(1, (px * bx + py * by + pz * bz) / dd)) : 0;
    var dx = px - bx * h, dy = py - by * h, dz = pz - bz * h;
    return Math.sqrt(dx * dx + dy * dy + dz * dz) - (ra + (rb - ra) * h);
  }
  function ell(x, y, z, c, r) {
    var qx = (x - c[0]) / r[0], qy = (y - c[1]) / r[1], qz = (z - c[2]) / r[2];
    return (Math.sqrt(qx * qx + qy * qy + qz * qz) - 1) * Math.min(r[0], Math.min(r[1], r[2]));
  }

  var ZFLAT = 2.75;   // 손등이 납작한 정도

  /* 손가락은 스파인을 캡슐 사슬로 근사한다. 손가락끼리는 붙으면 안 되므로
   * 각 손가락 안에서는 그냥 min 으로 잇고, 손 전체와 합칠 때만 부드럽게 뭉갠다. */
  var LIMBS = FINGERS.map(function (f) {
    var sp = SPINES[f.id], segs = [], i;
    var d0 = sp[0];
    var root = f.id === 'thumb' ? [-1.35, -4.60, -0.55] : add(d0.p, mul(d0.t, -f.sink));
    segs.push([root, sp[0].p, f.r0 * (f.id === 'thumb' ? 1.12 : 0.99), sp[0].r]);
    for (i = 0; i + 2 < sp.length; i += 2) segs.push([sp[i].p, sp[i + 2].p, sp[i].r, sp[i + 2].r]);
    var e = sp[sp.length - 1];
    segs.push([e.p, add(e.p, mul(e.t, e.r * 0.55)), e.r, e.r * 0.72]);
    // 중수골 — 너클 봉우리와 손등 능선이 여기서 나온다 (엄지는 두덩이 대신한다)
    var meta = f.id === 'thumb' ? null
      : [[f.base[0] * 0.26, -4.6, -0.15], [f.base[0], f.base[1] - 0.2, f.base[2] + 0.10], 0.42, f.r0 * 0.92];
    var box = [1e9, 1e9, 1e9, -1e9, -1e9, -1e9];
    segs.concat(meta ? [meta] : []).forEach(function (s) {
      [s[0], s[1]].forEach(function (p) {
        var r = Math.max(s[2], s[3]) + 1.1;
        for (var j = 0; j < 3; j++) {
          box[j] = Math.min(box[j], p[j] - r);
          box[j + 3] = Math.max(box[j + 3], p[j] + r);
        }
      });
    });
    return { segs: segs, meta: meta, box: box };
  });

  function field(x, y, z) {
    // 손바닥·손목 덩어리
    var d = segZ(x, y, z, [0, -7.4, -0.28], [0, -1.2, -0.12], 2.28, 2.80, ZFLAT);
    d = Math.min(d, segZ(x, y, z, [0, -1.2, -0.12], [0.08, 3.85, 0.18], 2.80, 3.05, ZFLAT));
    d = smin(d, ell(x, y, z, [-2.15, -1.45, -0.50], [1.18, 2.95, 1.05]), 0.95);   // 엄지 두덩
    d = smin(d, ell(x, y, z, [2.50, -2.00, -0.42], [0.88, 2.45, 0.90]), 0.95);    // 새끼 두덩

    for (var i = 0; i < LIMBS.length; i++) {
      var L = LIMBS[i], b = L.box;
      if (x < b[0] || y < b[1] || z < b[2] || x > b[3] || y > b[4] || z > b[5]) continue;
      var df = 1e9, j;
      for (j = 0; j < L.segs.length; j++) {
        var s = L.segs[j];
        df = Math.min(df, segZ(x, y, z, s[0], s[1], s[2], s[3]));
      }
      if (L.meta) df = smin(df, segZ(x, y, z, L.meta[0], L.meta[1], L.meta[2], L.meta[3]), 0.62);
      // 밑동에서만 크게 뭉갠다. 위쪽까지 크게 잡으면 손가락끼리 물갈퀴로 붙는다.
      var t = Math.max(0, Math.min(1, (6.0 - y) / 3.5));
      d = smin(d, df, 0.10 + 0.55 * t * t * (3 - 2 * t));
    }
    return d;
  }

  /* ── 등위면 뽑기 (surface nets) ───────────────────────────────────
   * 마칭 큐브의 256행 테이블 없이, 셀마다 꼭짓점 하나를 교차점 평균에 놓고
   * 부호가 바뀌는 격자 모서리마다 인접한 네 셀을 사각형으로 잇는다.
   * 코드가 훨씬 짧고 결과가 매끈해서 살에 어울린다.
   */
  var CORNER = [[0,0,0],[1,0,0],[1,1,0],[0,1,0],[0,0,1],[1,0,1],[1,1,1],[0,1,1]];
  var CEDGE = [[0,1],[1,2],[3,2],[0,3],[4,5],[5,6],[7,6],[4,7],[0,4],[1,5],[2,6],[3,7]];

  function surfaceNets(lo, hi, cell) {
    var nx = Math.ceil((hi[0] - lo[0]) / cell), ny = Math.ceil((hi[1] - lo[1]) / cell),
        nz = Math.ceil((hi[2] - lo[2]) / cell);
    var sx = nx + 1, sy = ny + 1, sz = nz + 1;
    var val = new Float32Array(sx * sy * sz), ix, iy, iz;
    for (iz = 0; iz < sz; iz++) for (iy = 0; iy < sy; iy++) for (ix = 0; ix < sx; ix++) {
      val[(iz * sy + iy) * sx + ix] = field(lo[0] + ix * cell, lo[1] + iy * cell, lo[2] + iz * cell);
    }
    var vid = new Int32Array(nx * ny * nz).fill(-1);
    var mesh = new Mesh(), c = new Float32Array(8), i;

    for (iz = 0; iz < nz; iz++) for (iy = 0; iy < ny; iy++) for (ix = 0; ix < nx; ix++) {
      var neg = 0;
      for (i = 0; i < 8; i++) {
        var o = CORNER[i];
        c[i] = val[((iz + o[2]) * sy + iy + o[1]) * sx + ix + o[0]];
        if (c[i] < 0) neg++;
      }
      if (neg === 0 || neg === 8) continue;
      var px = 0, py = 0, pz = 0, n = 0;
      for (i = 0; i < 12; i++) {
        var a = CEDGE[i][0], b = CEDGE[i][1];
        if ((c[a] < 0) === (c[b] < 0)) continue;
        var t = c[a] / (c[a] - c[b]);
        px += CORNER[a][0] + (CORNER[b][0] - CORNER[a][0]) * t;
        py += CORNER[a][1] + (CORNER[b][1] - CORNER[a][1]) * t;
        pz += CORNER[a][2] + (CORNER[b][2] - CORNER[a][2]) * t;
        n++;
      }
      vid[(iz * ny + iy) * nx + ix] = mesh.add([
        lo[0] + (ix + px / n) * cell, lo[1] + (iy + py / n) * cell, lo[2] + (iz + pz / n) * cell
      ], 0, -1);
    }

    function cellAt(x, y, z) {
      if (x < 0 || y < 0 || z < 0 || x >= nx || y >= ny || z >= nz) return -1;
      return vid[(z * ny + y) * nx + x];
    }
    function emit(a, b, c2, d, flip) {
      if (a < 0 || b < 0 || c2 < 0 || d < 0) return;
      if (flip) mesh.quad(a, d, c2, b); else mesh.quad(a, b, c2, d);
    }
    for (iz = 0; iz < sz; iz++) for (iy = 0; iy < sy; iy++) for (ix = 0; ix < sx; ix++) {
      var v0 = val[(iz * sy + iy) * sx + ix], s0 = v0 < 0;
      if (ix + 1 < sx && (val[(iz * sy + iy) * sx + ix + 1] < 0) !== s0) {
        emit(cellAt(ix, iy - 1, iz - 1), cellAt(ix, iy, iz - 1), cellAt(ix, iy, iz), cellAt(ix, iy - 1, iz), s0);
      }
      if (iy + 1 < sy && (val[(iz * sy + iy + 1) * sx + ix] < 0) !== s0) {
        emit(cellAt(ix - 1, iy, iz - 1), cellAt(ix, iy, iz - 1), cellAt(ix, iy, iz), cellAt(ix - 1, iy, iz), !s0);
      }
      if (iz + 1 < sz && (val[((iz + 1) * sy + iy) * sx + ix] < 0) !== s0) {
        emit(cellAt(ix - 1, iy - 1, iz), cellAt(ix, iy - 1, iz), cellAt(ix, iy, iz), cellAt(ix - 1, iy, iz), s0);
      }
    }
    return mesh.orient();
  }

  /* 살 셰이더가 쓸 uv: x = 손등 쪽인 정도, y = 손가락 길이비(관절 주름 위치).
   * 등위면에는 매개변수가 없으므로 가장 가까운 손가락 스파인에서 되찾는다. */
  function assignUV(mesh) {
    for (var v = 0; v < mesh.p.length / 3; v++) {
      var p = mesh.at(v), best = null, bd = 1e9;
      for (var i = 0; i < FINGERS.length; i++) {
        var sp = SPINES[FINGERS[i].id];
        for (var j = 0; j < sp.length; j++) {
          var q = sp[j], dx = p[0] - q.p[0], dy = p[1] - q.p[1], dz = p[2] - q.p[2];
          var d = dx * dx + dy * dy + dz * dz;
          if (d < bd) { bd = d; best = { q: q, t: j / (sp.length - 1) }; }
        }
      }
      // 손가락 표면에서 너무 멀면 주름을 넣지 않는다 (손바닥·손목)
      if (!best || Math.sqrt(bd) > best.q.r * 1.75) { mesh.uv[v * 2] = 0; mesh.uv[v * 2 + 1] = -1; continue; }
      mesh.uv[v * 2] = dot(norm(sub(p, best.q.p)), best.q.up);
      mesh.uv[v * 2 + 1] = best.t;
    }
    return mesh;
  }

  /* 법선은 장의 기울기에서 얻는다 — 면 법선을 평균 내는 것보다 훨씬 매끈하다 */
  function fieldNormals(mesh) {
    var n = new Float32Array(mesh.p.length), h = 0.02;
    for (var v = 0; v < mesh.p.length / 3; v++) {
      var x = mesh.p[v * 3], y = mesh.p[v * 3 + 1], z = mesh.p[v * 3 + 2];
      var g = norm([
        field(x + h, y, z) - field(x - h, y, z),
        field(x, y + h, z) - field(x, y - h, z),
        field(x, y, z + h) - field(x, y, z - h)
      ]);
      n[v * 3] = g[0]; n[v * 3 + 1] = g[1]; n[v * 3 + 2] = g[2];
    }
    return n;
  }

  function buildHand() {
    var m = surfaceNets([-8.5, -8.4, -2.4], [4.6, 14.4, 2.4], 0.125);
    m.gradNormals = fieldNormals(m);
    return assignUV(m);
  }
  /* ── 손톱 ──────────────────────────────────────────────────────────
   * 2D 쪽 SHAPES(모양별 절반 윤곽선)를 그대로 써서 윤곽을 만들고, 손가락 원통을
   * 감싸는 곡면 위에 얹는다. 그래서 모양·길이를 바꾸면 3D 형태도 실제로 바뀐다.
   */
  function outline(shape, samples) {
    var s = G.SHAPES[shape] || G.SHAPES.round;
    var ring = [], i;
    for (i = 0; i < s.pts.length; i++) ring.push([s.pts[i][0], s.pts[i][1]]);
    ring.push([0, 1]);
    for (i = s.pts.length - 1; i >= 0; i--) ring.push([-s.pts[i][0], s.pts[i][1]]);
    // 큐티클은 가운데가 살짝 파인 완만한 호로 닫는다.
    // 점 하나로 닫으면 손톱 밑동에 쐐기처럼 팬 자국이 남는다.
    var x0 = -s.pts[0][0], y0 = s.pts[0][1];
    for (i = 1; i < 8; i++) {
      var q = i / 8;
      ring.push([x0 * (1 - 2 * q), y0 - 0.05 * Math.sin(q * Math.PI)]);
    }
    // 길이를 따라 균등하게 다시 샘플링 — 뾰족한 팁도 촘촘히 잡힌다
    var seg = [], total = 0, k;
    for (k = 0; k < ring.length; k++) {
      var a = ring[k], b = ring[(k + 1) % ring.length];
      var d = Math.hypot(b[0] - a[0], (b[1] - a[1]) * 2.1);
      seg.push(d); total += d;
    }
    var out = [], acc = 0, want = 0, idx = 0, step = total / samples;
    for (k = 0; k < ring.length && out.length < samples; k++) {
      while (want <= acc + seg[k] && out.length < samples) {
        var u = seg[k] > 1e-9 ? (want - acc) / seg[k] : 0;
        var p0 = ring[k], p1 = ring[(k + 1) % ring.length];
        out.push([p0[0] + (p1[0] - p0[0]) * u, p0[1] + (p1[1] - p0[1]) * u]);
        want += step;
      }
      acc += seg[k];
      idx++;
    }
    while (out.length < samples) out.push(ring[0].slice());
    return out;
  }

  var NAIL_RINGS = 5, NAIL_SEG = 46;

  /* (xFrac, yFrac) → 3D. 손톱은 손가락보다 완만한 곡률로 휘어 있고,
   * 큐티클 쪽은 살 밑으로 살짝 잠긴다. */
  function nailPoint(f, m, x, y, lift) {
    var s = m.s0 + Math.max(0, y) * m.T;
    var fr = sample(f, s);
    var off = x * m.hw;
    var rn = fr.r * 1.35;                      // 손톱은 손가락 원통보다 조금 평평하다
    var h = Math.sqrt(Math.max(0, rn * rn - off * off)) - (rn - fr.r);
    // 큐티클(y<0.09)은 살 밑으로 잠겨야 스티커처럼 얹혀 보이지 않는다
    var sink = y < 0.09 ? (0.09 - Math.max(0, y)) / 0.09 : 0;
    h += lift - sink * 0.20 - 0.05 * y * y;    // 프리엣지는 끝이 살짝 내려온다
    return add(add(fr.p, mul(fr.side, off)), mul(fr.up, h));
  }

  function nailMetrics(f, design) {
    var sp = SPINES[f.id], len = sp[sp.length - 1].s;
    var bed = f.bed;
    var ext = bed * G.LENGTHS[design.length].ext / 1.06;
    return { hw: f.r1 * 0.70, bed: bed, T: bed + ext, s0: len - bed - f.r1 * 0.45 };
  }

  var THICK = 0.055;

  function nailMesh(f, design) {
    var m = nailMetrics(f, design);
    var ring = outline(design.shape, NAIL_SEG);
    var cx = 0, cy = 0, i, j;
    for (i = 0; i < ring.length; i++) { cx += ring[i][0]; cy += ring[i][1]; }
    cx /= ring.length; cy /= ring.length;

    var mesh = new Mesh(), top = [], bot = [];
    for (i = 0; i <= NAIL_RINGS; i++) {
      var k = 1 - i / NAIL_RINGS, rowT = [], rowB = [];
      for (j = 0; j < NAIL_SEG; j++) {
        var x = cx + (ring[j][0] - cx) * k, y = cy + (ring[j][1] - cy) * k;
        rowT.push(mesh.add(nailPoint(f, m, x, y, 0.05), x, y));
        rowB.push(mesh.add(nailPoint(f, m, x, y, 0.05 - THICK), x, y));
      }
      top.push(rowT); bot.push(rowB);
    }
    for (i = 0; i < NAIL_RINGS; i++) for (j = 0; j < NAIL_SEG; j++) {
      var n = (j + 1) % NAIL_SEG;
      mesh.quad(top[i][j], top[i][n], top[i + 1][n], top[i + 1][j]);
      mesh.quad(bot[i][j], bot[i + 1][j], bot[i + 1][n], bot[i][n]);
    }
    // 프리엣지 두께 — 손끝 밖으로 나간 부분은 옆면이 보인다
    for (j = 0; j < NAIL_SEG; j++) {
      var q = (j + 1) % NAIL_SEG;
      mesh.quad(top[0][j], bot[0][j], bot[0][q], top[0][q]);
    }
    return mesh.orient();
  }

  /* ── 셰이더 ── */
  var VS = [
    '#version 300 es',
    'in vec3 aPos; in vec3 aNrm; in vec2 aUV;',
    'uniform mat4 uMVP;',
    'out vec3 vPos; out vec3 vNrm; out vec2 vUV;',
    'void main(){ vPos=aPos; vNrm=aNrm; vUV=aUV; gl_Position=uMVP*vec4(aPos,1.0); }'
  ].join('\n');

  var COMMON = [
    'precision highp float;',
    'uniform vec3 uLight, uEye, uHi;',
    'in vec3 vPos; in vec3 vNrm; in vec2 vUV;',
    'out vec4 oCol;',
    'float hash(vec3 p){ return fract(sin(dot(p,vec3(12.9898,78.233,37.719)))*43758.5453); }'
  ].join('\n');

  /* 살: 감싸는 확산광 + 터미네이터의 혈색. 램버트만 쓰면 플라스틱이 된다. */
  var FS_SKIN = ['#version 300 es', COMMON,
    'uniform vec3 uBase, uShade, uBlood;',
    'void main(){',
    '  vec3 N=normalize(vNrm), L=normalize(uLight), V=normalize(uEye-vPos);',
    '  float nl=dot(N,L);',
    '  float diff=clamp((nl+0.34)/1.34,0.0,1.0);',
    '  vec3 col=mix(uShade,uBase,diff*diff*(3.0-2.0*diff));',
    '  float sss=exp(-abs(nl)*3.2);',            // 빛이 살 밑으로 퍼지는 띠
    '  col=mix(col,uBlood,sss*0.30);',
    '  col+=uShade*0.16*(1.0-diff);',            // 그늘 쪽 환경 바운스
    // 관절 주름. 사진에서 손을 손처럼 보이게 하는 가장 큰 단서다.
    // 손등 쪽은 가는 잔주름이 촘촘하고, 손바닥 쪽은 굵은 접힘선 하나로 간다.
    '  float t=vUV.y;',
    '  if(t>=0.0){',
    '    float dorsal=smoothstep(0.10,0.80,vUV.x);',
    '    float band=exp(-pow((t-0.345)/0.032,2.0))+exp(-pow((t-0.680)/0.028,2.0));',
    '    float fine=0.5+0.5*sin(t*430.0);',
    '    col*=1.0-band*(0.030+0.075*fine)*dorsal;',
    '    float fold=exp(-pow((t-0.325)/0.016,2.0))+exp(-pow((t-0.700)/0.014,2.0));',
    '    col*=1.0-fold*0.17*(1.0-dorsal);',
    '    col=mix(col,uBlood,smoothstep(0.86,1.0,t)*0.22);',  // 손끝 혈색
    '  }',
    '  vec3 H=normalize(L+V);',
    '  col+=uHi*pow(max(dot(N,H),0.0),24.0)*0.13;',
    '  col+=uHi*pow(1.0-max(dot(N,V),0.0),3.5)*0.22;',
    '  col*=0.978+hash(floor(vPos*52.0))*0.044;', // 살결
    '  oCol=vec4(pow(col,vec3(1.0/2.2)),1.0);',
    '}'].join('\n');

  var FS_NAIL = ['#version 300 es', COMMON,
    'uniform vec3 uC1,uC2,uBed; uniform int uArt,uFinish; uniform float uSheer,uSel;',
    'void main(){',
    '  vec3 N=normalize(vNrm), L=normalize(uLight), V=normalize(uEye-vPos);',
    '  float u=vUV.x, v=clamp(vUV.y,0.0,1.0);',
    '  vec3 base=uC1;',
    '  if(uArt==1) base=mix(uC1,uC2,smoothstep(0.68,0.75,v));',
    '  else if(uArt==2) base=mix(uC2,uC1,smoothstep(0.05,0.95,v));',
    '  else if(uArt==4){ float b=exp(-pow((u*0.8+(v-0.5)*1.1)/0.20,2.0));',
    '                    base=mix(uC1*0.72,uC2,b); }',
    '  if(uArt==3||(uArt==5&&v>0.70)){',
    '    float g=hash(floor(vec3(u*34.0,v*54.0,0.0)));',
    '    base=mix(base,uC2*1.25,step(0.86,g)*(0.55+0.45*hash(floor(vec3(v*54.0,u*34.0,3.0)))));',
    '  }',
    '  base=mix(uBed,base,uSheer);',
    '  if(uSheer<0.9){',                          // 루눌라 — 밑동의 반달
    '    base=mix(base,mix(base,vec3(1.0),0.45),smoothstep(0.16,0.03,v)*(1.0-uSheer));',
    '    base=mix(base,mix(base,vec3(1.0),0.55),smoothstep(0.86,0.98,v)*(1.0-uSheer));',
    '  }',
    '  float nl=dot(N,L);',
    '  vec3 col=base*(0.34+0.66*clamp((nl+0.25)/1.25,0.0,1.0));',
    '  vec3 H=normalize(L+V);',
    '  float f=pow(1.0-max(dot(N,V),0.0),3.0);',
    '  if(uFinish==3){',                          // 크롬 — 환경이 비쳐야 금속이다
    '    vec3 R=reflect(-V,N);',
    '    vec3 env=mix(vec3(0.07,0.06,0.08),vec3(0.96,0.97,1.0),smoothstep(-0.30,0.45,R.y));',
    '    env=mix(env,vec3(1.0,0.95,0.86),pow(max(R.y,0.0),7.0));',
    '    col=base*0.30+env*base*1.55;',
    '    col+=vec3(1.0)*pow(max(dot(N,H),0.0),170.0)*0.9;',
    '  } else if(uFinish==1){',                   // 매트
    '    col*=0.97+hash(floor(vPos*160.0))*0.06;',
    '    col+=uHi*pow(max(dot(N,H),0.0),7.0)*0.05;',
    '  } else {',
    '    if(uFinish==2){',                        // 펄 — 프레넬로 색이 돈다
    '      vec3 ir=0.5+0.5*cos(6.2831*(vec3(0.0,0.33,0.67)+f*1.5+v*0.6));',
    '      col=mix(col,col*0.72+ir*0.42,0.55);',
    '    }',
    '    col+=vec3(1.0)*pow(max(dot(N,H),0.0),96.0)*0.75;',
    '    col+=vec3(1.0)*f*0.10;',
    '  }',
    '  col+=vec3(0.85,0.25,0.45)*uSel*f*0.85;',   // 선택된 손톱 표시
    '  oCol=vec4(pow(col,vec3(1.0/2.2)),1.0);',
    '}'].join('\n');

  var FS_PICK = ['#version 300 es', 'precision highp float;',
    'uniform vec3 uC1;', 'in vec3 vPos; in vec3 vNrm; in vec2 vUV; out vec4 oCol;',
    'void main(){ oCol=vec4(uC1,1.0); }'].join('\n');

  var FS_BG = ['#version 300 es', 'precision highp float;',
    'uniform vec3 uC1,uC2; uniform vec2 uRes;',
    'in vec3 vPos; in vec3 vNrm; in vec2 vUV; out vec4 oCol;',
    'void main(){',
    '  vec2 q=gl_FragCoord.xy/uRes;',
    '  vec3 c=mix(uC2,uC1,smoothstep(0.0,1.0,q.y));',
    '  float d=length((q-vec2(0.46,0.58))*vec2(1.0,0.86));',
    '  oCol=vec4(c*(1.0-smoothstep(0.30,0.86,d)*0.30),1.0);',
    '}'].join('\n');

  /* ── GL ── */
  var gl = null, canvas = null, prog = {}, hand = null, nails = {}, bg = null;
  var orbit = { yaw: 0, pitch: 0, dist: 36 }, pickFB = null, pickTex = null, pickRB = null;
  var onPick = null, redraw = null;

  function compile(vs, fs) {
    function sh(type, src) {
      var s = gl.createShader(type);
      gl.shaderSource(s, src); gl.compileShader(s);
      if (!gl.getShaderParameter(s, gl.COMPILE_STATUS)) throw new Error(gl.getShaderInfoLog(s));
      return s;
    }
    var p = gl.createProgram();
    gl.attachShader(p, sh(gl.VERTEX_SHADER, vs));
    gl.attachShader(p, sh(gl.FRAGMENT_SHADER, fs));
    gl.bindAttribLocation(p, 0, 'aPos');
    gl.bindAttribLocation(p, 1, 'aNrm');
    gl.bindAttribLocation(p, 2, 'aUV');
    gl.linkProgram(p);
    if (!gl.getProgramParameter(p, gl.LINK_STATUS)) throw new Error(gl.getProgramInfoLog(p));
    return p;
  }

  function upload(mesh) {
    var vao = gl.createVertexArray();
    gl.bindVertexArray(vao);
    function buf(data, loc, n) {
      var b = gl.createBuffer();
      gl.bindBuffer(gl.ARRAY_BUFFER, b);
      gl.bufferData(gl.ARRAY_BUFFER, data, gl.STATIC_DRAW);
      gl.enableVertexAttribArray(loc);
      gl.vertexAttribPointer(loc, n, gl.FLOAT, false, 0, 0);
    }
    buf(new Float32Array(mesh.p), 0, 3);
    buf(mesh.gradNormals || mesh.normals(), 1, 3);
    buf(new Float32Array(mesh.uv), 2, 2);
    var ib = gl.createBuffer();
    gl.bindBuffer(gl.ELEMENT_ARRAY_BUFFER, ib);
    gl.bufferData(gl.ELEMENT_ARRAY_BUFFER, new Uint32Array(mesh.i), gl.STATIC_DRAW);
    gl.bindVertexArray(null);
    return { vao: vao, n: mesh.i.length };
  }

  function u(p, name) { return gl.getUniformLocation(p, name); }
  function rgb(hex) {
    var c = C.hex2rgb(hex);
    // sRGB → 대략적인 선형. 감마를 무시하면 명암이 탁해진다.
    return [Math.pow(c.r / 255, 2.2), Math.pow(c.g / 255, 2.2), Math.pow(c.b / 255, 2.2)];
  }
  function set3(p, name, hex) { gl.uniform3fv(u(p, name), rgb(hex)); }

  var BG = {
    studio: ['#fbf6f1', '#e4d3c6'],
    blush: ['#fdeef0', '#f0c9d2'],
    noir: ['#33292e', '#0d090b']
  };
  var ARTI = { none: 0, french: 1, ombre: 2, glitter: 3, cateye: 4, tip: 5 };
  var FINI = { gloss: 0, matte: 1, pearl: 2, chrome: 3 };

  function init(host, pickCb) {
    canvas = document.createElement('canvas');
    canvas.className = 'gl';
    host.appendChild(canvas);
    gl = canvas.getContext('webgl2', { antialias: true, preserveDrawingBuffer: true });
    if (!gl) return false;
    onPick = pickCb;
    prog.skin = compile(VS, FS_SKIN);
    prog.nail = compile(VS, FS_NAIL);
    prog.pick = compile(VS, FS_PICK);
    prog.bg = compile(VS, FS_BG);
    hand = upload(buildHand());

    var quad = new Mesh();
    quad.add([-1, -1, 0]); quad.add([3, -1, 0]); quad.add([-1, 3, 0]);
    quad.tri(0, 1, 2);
    bg = upload(quad);

    pickFB = gl.createFramebuffer();
    pickTex = gl.createTexture();
    pickRB = gl.createRenderbuffer();

    bindInput();
    return true;
  }

  function bindInput() {
    var drag = null;
    canvas.addEventListener('pointerdown', function (e) {
      drag = { x: e.clientX, y: e.clientY, yaw: orbit.yaw, pitch: orbit.pitch, moved: 0 };
      canvas.setPointerCapture(e.pointerId);
    });
    canvas.addEventListener('pointermove', function (e) {
      if (!drag) return;
      var dx = e.clientX - drag.x, dy = e.clientY - drag.y;
      drag.moved = Math.max(drag.moved, Math.abs(dx) + Math.abs(dy));
      orbit.yaw = drag.yaw + dx * 0.32;
      orbit.pitch = Math.max(-72, Math.min(72, drag.pitch + dy * 0.28));
      if (redraw) redraw();
    });
    canvas.addEventListener('pointerup', function (e) {
      var wasDrag = drag && drag.moved > 4;
      drag = null;
      if (!wasDrag && onPick) {
        var id = pick(e);
        if (id) onPick(id);
      }
    });
    canvas.addEventListener('wheel', function (e) {
      e.preventDefault();
      orbit.dist = Math.max(12, Math.min(60, orbit.dist * (1 + Math.sign(e.deltaY) * 0.09)));
      if (redraw) redraw();
    }, { passive: false });
  }

  function camera(state, asp) {
    var target = state.zoom ? [0, 9.6, 0] : [0, 3.4, 0];
    var dist = state.zoom ? Math.min(orbit.dist, 16) : orbit.dist;
    var eye = [0, 0, dist];
    eye = rotAxis(eye, [1, 0, 0], -orbit.pitch);
    eye = rotAxis(eye, [0, 1, 0], orbit.yaw);
    eye = add(target, eye);
    return { eye: eye, mvp: mmul(perspective(30, asp, 1, 200), lookAt(eye, target, [0, 1, 0])) };
  }

  function meshFor(fg, d) {
    var key = fg.id + '|' + d.shape + '|' + d.length;
    if (!nails[key]) nails[key] = upload(nailMesh(fg, d));
    return nails[key];
  }

  function resize() {
    var dpr = Math.min(window.devicePixelRatio || 1, 2);
    var w = Math.round(canvas.clientWidth * dpr), h = Math.round(canvas.clientHeight * dpr);
    if (w && h && (canvas.width !== w || canvas.height !== h)) { canvas.width = w; canvas.height = h; }
    return [canvas.width, canvas.height];
  }

  /* 손톱 하나를 그린다. cb 로 프로그램별 유니폼을 넣는다. */
  function drawNails(state, p, cam, perNail) {
    gl.useProgram(p);
    gl.uniformMatrix4fv(u(p, 'uMVP'), false, cam.mvp);
    gl.uniform3fv(u(p, 'uEye'), new Float32Array(cam.eye));
    gl.uniform3fv(u(p, 'uLight'), new Float32Array(norm([-0.66, 0.52, 0.44])));
    set3(p, 'uHi', '#fff6ee');
    FINGERS.forEach(function (fg, i) {
      var d = state.nails[fg.id];
      perNail(p, fg, d, i);
      var m = meshFor(fg, d);
      gl.bindVertexArray(m.vao);
      gl.drawElements(gl.TRIANGLES, m.n, gl.UNSIGNED_INT, 0);
    });
  }

  function draw(state) {
    var size = resize();
    var sk = null;
    D.SKINS.forEach(function (s) { if (s.id === state.skin) sk = s; });
    sk = sk || D.SKINS[2];
    var cam = camera(state, size[0] / size[1]);

    gl.bindFramebuffer(gl.FRAMEBUFFER, null);
    gl.viewport(0, 0, size[0], size[1]);
    gl.enable(gl.DEPTH_TEST);
    gl.disable(gl.CULL_FACE);
    gl.clear(gl.COLOR_BUFFER_BIT | gl.DEPTH_BUFFER_BIT);

    // 배경
    var pal = BG[state.backdrop] || BG.studio;
    gl.depthMask(false);
    gl.useProgram(prog.bg);
    gl.uniformMatrix4fv(u(prog.bg, 'uMVP'), false, new Float32Array([1,0,0,0, 0,1,0,0, 0,0,1,0, 0,0,0,1]));
    gl.uniform2f(u(prog.bg, 'uRes'), size[0], size[1]);
    set3(prog.bg, 'uC1', pal[0]);
    set3(prog.bg, 'uC2', pal[1]);
    gl.bindVertexArray(bg.vao);
    gl.drawElements(gl.TRIANGLES, bg.n, gl.UNSIGNED_INT, 0);
    gl.depthMask(true);

    // 손
    gl.useProgram(prog.skin);
    gl.uniformMatrix4fv(u(prog.skin, 'uMVP'), false, cam.mvp);
    gl.uniform3fv(u(prog.skin, 'uEye'), new Float32Array(cam.eye));
    gl.uniform3fv(u(prog.skin, 'uLight'), new Float32Array(norm([-0.66, 0.52, 0.44])));
    set3(prog.skin, 'uBase', sk.base);
    set3(prog.skin, 'uShade', sk.shade);
    set3(prog.skin, 'uBlood', sk.blood);
    set3(prog.skin, 'uHi', C.lighten(sk.light, 0.3));
    gl.bindVertexArray(hand.vao);
    gl.drawElements(gl.TRIANGLES, hand.n, gl.UNSIGNED_INT, 0);

    // 손톱
    var bed = C.mix(C.lighten(sk.base, 0.34), sk.blood, 0.24);
    drawNails(state, prog.nail, cam, function (p, fg, d) {
      set3(p, 'uC1', d.color);
      set3(p, 'uC2', d.color2);
      set3(p, 'uBed', bed);
      gl.uniform1i(u(p, 'uArt'), ARTI[d.art] || 0);
      gl.uniform1i(u(p, 'uFinish'), FINI[d.finish] || 0);
      gl.uniform1f(u(p, 'uSheer'), d.sheer == null ? 1 : d.sheer);
      gl.uniform1f(u(p, 'uSel'), (!state.sync && state.selected.indexOf(fg.id) >= 0) ? 1 : 0);
    });
    gl.bindVertexArray(null);
  }

  /* 손톱만 id 색으로 그려 읽는다 — 실루엣 그대로 맞아서 광선 검사보다 정확하다 */
  function pick(ev) {
    if (!pickState) return null;
    var size = [canvas.width, canvas.height];
    gl.bindTexture(gl.TEXTURE_2D, pickTex);
    gl.texImage2D(gl.TEXTURE_2D, 0, gl.RGBA8, size[0], size[1], 0, gl.RGBA, gl.UNSIGNED_BYTE, null);
    gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_MIN_FILTER, gl.NEAREST);
    gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_MAG_FILTER, gl.NEAREST);
    gl.bindRenderbuffer(gl.RENDERBUFFER, pickRB);
    gl.renderbufferStorage(gl.RENDERBUFFER, gl.DEPTH_COMPONENT16, size[0], size[1]);
    gl.bindFramebuffer(gl.FRAMEBUFFER, pickFB);
    gl.framebufferTexture2D(gl.FRAMEBUFFER, gl.COLOR_ATTACHMENT0, gl.TEXTURE_2D, pickTex, 0);
    gl.framebufferRenderbuffer(gl.FRAMEBUFFER, gl.DEPTH_ATTACHMENT, gl.RENDERBUFFER, pickRB);
    gl.viewport(0, 0, size[0], size[1]);
    gl.clearColor(0, 0, 0, 1);
    gl.clear(gl.COLOR_BUFFER_BIT | gl.DEPTH_BUFFER_BIT);
    gl.enable(gl.DEPTH_TEST);

    var cam = camera(pickState, size[0] / size[1]);
    // 손도 같이 그려야 손에 가려진 손톱이 집히지 않는다
    gl.useProgram(prog.pick);
    gl.uniformMatrix4fv(u(prog.pick, 'uMVP'), false, cam.mvp);
    gl.uniform3f(u(prog.pick, 'uC1'), 0, 0, 0);
    gl.bindVertexArray(hand.vao);
    gl.drawElements(gl.TRIANGLES, hand.n, gl.UNSIGNED_INT, 0);
    drawNails(pickState, prog.pick, cam, function (p, fg, d, i) {
      gl.uniform3f(u(p, 'uC1'), (i + 1) / 255, 0, 0);
    });

    var r = canvas.getBoundingClientRect();
    var px = Math.round((ev.clientX - r.left) / r.width * size[0]);
    var py = Math.round((1 - (ev.clientY - r.top) / r.height) * size[1]);
    var buf = new Uint8Array(4);
    gl.readPixels(px, py, 1, 1, gl.RGBA, gl.UNSIGNED_BYTE, buf);
    gl.bindFramebuffer(gl.FRAMEBUFFER, null);
    gl.bindVertexArray(null);
    return buf[0] > 0 && buf[0] <= IDS.length ? IDS[buf[0] - 1] : null;
  }

  var pickState = null;

  NS.hand3d = {
    init: init,
    draw: function (state) { pickState = state; draw(state); },
    setRedraw: function (fn) { redraw = fn; },
    canvas: function () { return canvas; },
    reset: function () { orbit.yaw = 0; orbit.pitch = 0; orbit.dist = 36; }
  };
})(window.NailSim = window.NailSim || {});
