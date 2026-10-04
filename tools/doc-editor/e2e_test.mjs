// 라이트테이블 문서 편집기 E2E 점검 (Chromium)
//
// 실행: node tools/doc-editor/e2e_test.mjs
//   Node 18 이상과 playwright 패키지, Chromium이 필요하다.
//   playwright를 전역에 설치했다면 경로를 알려 준다:
//     PLAYWRIGHT_MODULE="$(npm root -g)/playwright/index.mjs" node tools/doc-editor/e2e_test.mjs
//   화면 캡처를 남기려면 SHOTS=저장폴더 를 함께 준다.
// 저장 기능은 파일 저장 창(File System Access API)을 끄고 내려받기 경로로 검사한다.
import { readFileSync, writeFileSync, mkdtempSync, mkdirSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { join } from 'node:path';
import { deflateSync } from 'node:zlib';

const { chromium } = await import(process.env.PLAYWRIGHT_MODULE || 'playwright');
const PAGE = process.env.EDITOR_URL || new URL('./index.html', import.meta.url).href;
const TMP = mkdtempSync(join(tmpdir(), 'lt-editor-'));
const SHOTS = process.env.SHOTS || '';
if (SHOTS) mkdirSync(SHOTS, { recursive: true });

const results = [];
const ok = (name, cond, info = '') => {
  results.push(!!cond);
  console.log(cond ? 'PASS' : 'FAIL', name, cond ? '' : String(info).slice(0, 300));
};
const shot = async (page, name) => { if (SHOTS) await page.screenshot({ path: join(SHOTS, name + '.png') }); };

// 테스트용 PNG (그라데이션)
function makePng(w, h) {
  const rows = Buffer.alloc((w * 3 + 1) * h);
  for (let y = 0; y < h; y++) {
    rows[y * (w * 3 + 1)] = 0;
    for (let x = 0; x < w; x++) { const o = y * (w * 3 + 1) + 1 + x * 3; rows[o] = (x * 3) & 255; rows[o + 1] = (y * 3) & 255; rows[o + 2] = (x + y) & 255; }
  }
  const crc = buf => { let c = ~0; for (const b of buf) { c ^= b; for (let k = 0; k < 8; k++) c = (c >>> 1) ^ (0xEDB88320 & -(c & 1)); } return ~c >>> 0; };
  const chunk = (t, d) => { const len = Buffer.alloc(4); len.writeUInt32BE(d.length); const td = Buffer.concat([Buffer.from(t), d]); const c = Buffer.alloc(4); c.writeUInt32BE(crc(td)); return Buffer.concat([len, td, c]); };
  const ihdr = Buffer.alloc(13); ihdr.writeUInt32BE(w, 0); ihdr.writeUInt32BE(h, 4); ihdr[8] = 8; ihdr[9] = 2;
  return Buffer.concat([Buffer.from([137, 80, 78, 71, 13, 10, 26, 10]), chunk('IHDR', ihdr), chunk('IDAT', deflateSync(rows)), chunk('IEND', Buffer.alloc(0))]);
}
const PNG = join(TMP, 'test.png');
writeFileSync(PNG, makePng(320, 200));
const PNG_B64 = readFileSync(PNG).toString('base64');

// 컨테이너에 로캘이 없으면 Chromium이 한글 내려받기 파일 이름을 'download'로 바꾸므로 UTF-8 로캘로 띄운다.
const browser = await chromium.launch({ env: { ...process.env, LANG: 'C.UTF-8', LC_ALL: 'C.UTF-8' } });
const ctx = await browser.newContext({ viewport: { width: 1440, height: 900 }, acceptDownloads: true });
await ctx.addInitScript(() => { window.showOpenFilePicker = undefined; window.showSaveFilePicker = undefined; });
const page = await ctx.newPage();
const errors = [];
page.on('pageerror', e => errors.push('pageerror: ' + e.message));
page.on('console', m => { if (m.type() === 'error' && !/Blocked script execution in 'about:srcdoc'/.test(m.text())) errors.push('console: ' + m.text()); });
const download = async (action) => {
  const [d] = await Promise.all([page.waitForEvent('download'), action()]);
  return { name: d.suggestedFilename(), buf: readFileSync(await d.path()) };
};
const visReady = () => page.waitForFunction(() => { try { return visDoc() && [...visDoc().images].every(i => i.complete); } catch { return false; } }, null, { timeout: 15000 });
const confirmIfAsked = async () => { await page.waitForTimeout(120); if (await page.locator('#dlg[open]').count()) await page.click('#dlg .btn.primary'); };

await page.goto(PAGE);
await page.waitForFunction(() => { try { return visDoc() && visDoc().images.length === 2 && [...visDoc().images].every(i => i.naturalWidth); } catch { return false; } }, null, { timeout: 15000 });
ok('시작: 예시 문서를 시각 편집으로 열고 이미지 2개 표시', true);
await shot(page, '01_boot');

/* ── 이미지 선택·크기 핸들·실행 취소 ── */
const vis = page.frameLocator('#vis');
await vis.locator('img').first().click();
await page.waitForTimeout(150);
ok('선택: 크기 핸들과 도구 막대 표시', await page.locator('#ov').isVisible());
ok('선택: 속성 패널 표시', await page.locator('#selBody').isVisible());
ok('선택: 이미지에 브라우저 선택 덮개 없음(커서만 뒤에 둠)', await page.evaluate(() => visDoc().getSelection().isCollapsed));
const w0 = await page.evaluate(() => visDoc().images[0].offsetWidth);
const hb = await page.locator('.ov-h[data-d="se"]').boundingBox();
await page.mouse.move(hb.x + 6, hb.y + 6);
await page.mouse.down();
await page.mouse.move(hb.x - 120, hb.y - 40, { steps: 8 });
await page.mouse.up();
await page.waitForTimeout(100);
const w1 = await page.evaluate(() => visDoc().images[0].offsetWidth);
ok('크기 핸들: 모서리를 끌어 비율 유지 축소', w1 < w0 - 80, `${w0} → ${w1}`);
await shot(page, '02_selected');
await page.click('#tbVis [data-vcmd="undo"]');
await page.waitForTimeout(100);
ok('실행 취소: 크기 되돌림', Math.abs(await page.evaluate(() => visDoc().images[0].offsetWidth) - w0) <= 1);
await page.click('#tbVis [data-vcmd="redo"]');
await page.waitForTimeout(100);
ok('다시 실행', Math.abs(await page.evaluate(() => visDoc().images[0].offsetWidth) - w1) <= 1);

/* ── 이미지 편집 창 ── */
await vis.locator('img').first().dblclick();
await page.waitForSelector('#ied[open]');
await page.waitForTimeout(200);
ok('편집 창: 두 번 클릭으로 열림', true);
const cur = () => page.evaluate(() => [E.cur.width, E.cur.height]);
const d0 = await cur();
await page.click('#cropTrim');
const trim = await page.evaluate(() => ({ ...E.crop }));
ok('자르기: 흰 여백 자동 감지', trim.w < d0[0] && trim.h < d0[1], JSON.stringify(trim));
await shot(page, '03_editor_crop');
await page.click('#cropApply');
const d1 = await cur();
ok('자르기: 적용', d1[0] === trim.w && d1[1] === trim.h, d1);
const ov = await page.locator('#iedOv').boundingBox();
await page.mouse.move(ov.x + ov.width * 0.1, ov.y + ov.height * 0.1);
await page.mouse.down();
await page.mouse.move(ov.x + ov.width * 0.6, ov.y + ov.height * 0.7, { steps: 6 });
await page.mouse.up();
const c2 = await page.evaluate(() => ({ ...E.crop }));
ok('자르기: 끌어서 새 영역 지정', c2.w > d1[0] * 0.4 && c2.w < d1[0] * 0.6, JSON.stringify(c2));
await page.click('#cropAspect [data-r="1"]');
const c3 = await page.evaluate(() => ({ ...E.crop }));
ok('자르기: 1:1 비율 고정', Math.abs(c3.w - c3.h) <= 1, JSON.stringify(c3));
await page.click('#cropAll');
await page.click('[data-tool="rotate"]');
await page.click('#rotR');
const d2 = await cur();
ok('회전: 오른쪽 90°', d2[0] === d1[1] && d2[1] === d1[0], d2);
await page.click('#rotL');
await page.locator('#rotA').fill('8');
await page.locator('#rotA').dispatchEvent('input');
await page.click('#rotApply');
const d3 = await cur();
ok('기울기 8°: 빈 모서리를 잘라 비율 유지', d3[0] < d1[0] && Math.abs(d3[0] / d3[1] - d1[0] / d1[1]) < 0.02, d3);
await page.click('#iedUndo');
const d4 = await cur();
ok('편집 창 실행 취소: 기울기 되돌림', d4[0] === d1[0] && d4[1] === d1[1], d4);
await page.click('[data-tool="adjust"]');
await page.click('#adjPresets [data-preset="mono"]');
await page.waitForTimeout(150);
await page.click('#adjApply');
const grayDiff = await page.evaluate(() => { const d = E.cur.getContext('2d').getImageData(0, 0, E.cur.width, E.cur.height).data; let m = 0; for (let i = 0; i < d.length; i += 4 * 97) m = Math.max(m, Math.abs(d[i] - d[i + 1]), Math.abs(d[i + 1] - d[i + 2])); return m; });
ok('보정: 흑백 프리셋 (R=G=B)', grayDiff <= 2, grayDiff);
await page.click('[data-tool="draw"]');
await page.click('#drawKinds [data-k="arrow"]');
const ob = await page.locator('#iedOv').boundingBox();
await page.mouse.move(ob.x + ob.width * 0.2, ob.y + ob.height * 0.8);
await page.mouse.down();
await page.mouse.move(ob.x + ob.width * 0.5, ob.y + ob.height * 0.4, { steps: 5 });
await page.mouse.up();
await page.click('#drawKinds [data-k="num"]');
await page.mouse.click(ob.x + ob.width * 0.7, ob.y + ob.height * 0.3);
await page.click('#drawKinds [data-k="text"]');
await page.mouse.click(ob.x + ob.width * 0.06, ob.y + ob.height * 0.06);
await page.waitForTimeout(50);
await page.keyboard.type('경보선 근접');
await page.keyboard.press('Enter');
ok('주석: 화살표·번호·글자', (await page.evaluate(() => E.draw.objs.map(o => o.t).join(','))) === 'arrow,num,text');
ok('주석: 미리보기 선이 점선으로 새지 않음', await page.evaluate(() => $('#iedOv').getContext('2d').getLineDash().length === 0));
await page.click('#drawKinds [data-k="select"]');
const nb = await page.evaluate(() => ({ x: E.draw.objs[1].x, y: E.draw.objs[1].y }));
await page.mouse.move(ob.x + ob.width * 0.7, ob.y + ob.height * 0.3);
await page.mouse.down();
await page.mouse.move(ob.x + ob.width * 0.75, ob.y + ob.height * 0.35, { steps: 4 });
await page.mouse.up();
const na = await page.evaluate(() => ({ x: E.draw.objs[1].x, y: E.draw.objs[1].y, sel: E.draw.sel }));
ok('주석: 선택 도구로 옮기기', na.sel === 1 && na.x > nb.x && na.y > nb.y, JSON.stringify([nb, na]));
await shot(page, '04_editor_draw');
await page.click('#drawApply');
await page.click('[data-tool="redact"]');
await page.click('#redModes [data-m="fill"]');
const rb = await page.locator('#iedOv').boundingBox();
await page.mouse.move(rb.x + rb.width * 0.05, rb.y + rb.height * 0.05);
await page.mouse.down();
await page.mouse.move(rb.x + rb.width * 0.25, rb.y + rb.height * 0.2, { steps: 4 });
await page.mouse.up();
const px = await page.evaluate(() => [...E.cur.getContext('2d').getImageData(Math.round(E.cur.width * 0.15), Math.round(E.cur.height * 0.12), 1, 1).data]);
ok('가리기: 칠하기', px[0] < 30 && px[1] < 30 && px[2] < 30, px);
await page.click('#redModes [data-m="mosaic"]');
await page.mouse.move(rb.x + rb.width * 0.6, rb.y + rb.height * 0.6);
await page.mouse.down();
await page.mouse.move(rb.x + rb.width * 0.9, rb.y + rb.height * 0.9, { steps: 4 });
await page.mouse.up();
ok('가리기: 모자이크', await page.evaluate(() => E.undo.length >= 5));
await page.click('[data-tool="resize"]');
await page.click('#rsPresets [data-p="0.5"]');
await page.click('#rsApply');
const d5 = await cur();
ok('크기: 50%', Math.abs(d5[0] - Math.round(d1[0] / 2)) <= 1, d5);
await page.click('[data-tool="export"]');
await page.click('#outFmt [data-f="image/jpeg"]');
await page.waitForFunction(() => /JPEG/.test(document.querySelector('#outEst').textContent), null, { timeout: 5000 });
ok('저장 형식: JPEG 예상 크기 표시', true);
await shot(page, '05_editor_export');
await page.click('#iedApply');
await page.waitForFunction(() => !document.querySelector('#ied').open);
await page.waitForTimeout(250);
ok('적용: 문서 이미지가 JPEG data URI로 바뀜', (await page.evaluate(() => visDoc().images[0].getAttribute('src').slice(0, 23))) === 'data:image/jpeg;base64,');
ok('적용: 편집한 픽셀 크기 반영', (await page.evaluate(() => [visDoc().images[0].naturalWidth, visDoc().images[0].naturalHeight])).join() === d5.join());
await vis.locator('img').first().dblclick();
await page.waitForSelector('#ied[open]');
await page.click('[data-tool="rotate"]');
await page.click('#rotR');
await page.click('#iedCancel');
await page.waitForSelector('#dlg[open]');
await page.click('#dlg .btn.primary');
await page.waitForFunction(() => !document.querySelector('#ied').open);
ok('취소: 확인 후 닫히고 문서는 그대로', (await page.evaluate(() => visDoc().images[0].naturalWidth)) === d5[0]);

/* ── 속성 패널 ── */
await vis.locator('img').nth(1).click();
await page.waitForTimeout(100);
await page.click('#insAlign [data-a="center"]');
ok('배치: 가운데', /display:\s*block.*margin:\s*8px auto/.test(await page.evaluate(() => visDoc().images[1].getAttribute('style'))));
await page.check('#insCapOn');
ok('캡션: figure·figcaption으로 감쌈', await page.evaluate(() => !!visDoc().images[1].closest('figure')?.querySelector('figcaption')));
await page.fill('#insAlt', '고객 정보 조회 화면 캡처 (가상 데이터)');
await page.waitForTimeout(500);
ok('대체 텍스트 입력', await page.evaluate(() => visDoc().images[1].alt === '고객 정보 조회 화면 캡처 (가상 데이터)'));
await page.fill('#insBorderW', '3'); await page.locator('#insBorderW').dispatchEvent('input');
await page.selectOption('#insShadow', 'm');
await page.fill('#insRadius', '12'); await page.locator('#insRadius').dispatchEvent('input');
const st = await page.evaluate(() => visDoc().images[1].getAttribute('style'));
ok('모양: 테두리·그림자·모서리', /border:\s*3px solid/.test(st) && /box-shadow/.test(st) && /border-radius:\s*12px/.test(st), st);
await page.uncheck('#insCapOn');
const unwrap = await page.evaluate(() => { const i = visDoc().images[1]; return { fig: !!i.closest('figure'), p: i.parentElement.tagName, style: i.getAttribute('style') }; });
ok('캡션 끄기: figure를 풀고 가운데 배치 유지', !unwrap.fig && unwrap.p === 'P' && /margin:\s*\d+px auto/.test(unwrap.style), JSON.stringify(unwrap));
const [chooser] = await Promise.all([page.waitForEvent('filechooser'), page.click('#insReplace')]);
await chooser.setFiles(PNG);
await page.waitForFunction(() => visDoc().images[1].naturalWidth === 320, null, { timeout: 5000 });
ok('교체: 새 이미지로 바꾸고 표시 너비 유지', /width:\s*480px/.test(await page.evaluate(() => visDoc().images[1].getAttribute('style'))));
const imgFile = await download(() => page.click('#insSave'));
ok('이미지 파일로 저장: PNG', imgFile.buf.slice(1, 4).toString() === 'PNG' && /\.png$/.test(imgFile.name), imgFile.name);
await page.click('#tabList');
await page.waitForTimeout(100);
ok('문서 이미지 목록', (await page.locator('#imgList li').count()) === 2);
await shot(page, '06_inspector_list');

/* ── 붙여넣기·끌어다 놓기·링크·표 ── */
await vis.locator('h1').click();
await page.keyboard.press('End');
const pasted = await page.evaluate(async b64 => {
  const bytes = Uint8Array.from(atob(b64), c => c.charCodeAt(0));
  const dt = new DataTransfer(); dt.items.add(new File([bytes], 'clip.png', { type: 'image/png' }));
  const n = visDoc().images.length;
  visDoc().body.dispatchEvent(new ClipboardEvent('paste', { clipboardData: dt, bubbles: true, cancelable: true }));
  for (let k = 0; k < 50 && visDoc().images.length === n; k++) await new Promise(r => setTimeout(r, 50));
  return visDoc().images.length - n;
}, PNG_B64);
ok('붙여넣기: 클립보드 이미지를 문서에 내장', pasted === 1);
await page.waitForTimeout(200);
ok('붙여넣기: 넣은 이미지를 바로 선택', await page.locator('#ov').isVisible());
await page.click('#tbVis [data-vcmd="undo"]');
await page.waitForTimeout(100);
ok('붙여넣기 실행 취소', (await page.evaluate(() => visDoc().images.length)) === 2);
const dropped = await page.evaluate(async b64 => {
  const bytes = Uint8Array.from(atob(b64), c => c.charCodeAt(0));
  const dt = new DataTransfer(); dt.items.add(new File([bytes], 'drop.png', { type: 'image/png' }));
  const p = visDoc().querySelector('p.note'), r = p.getBoundingClientRect();
  const n = visDoc().images.length;
  p.dispatchEvent(new DragEvent('drop', { dataTransfer: dt, bubbles: true, cancelable: true, clientX: r.left + 20, clientY: r.top + 10 }));
  for (let k = 0; k < 50 && visDoc().images.length === n; k++) await new Promise(r => setTimeout(r, 50));
  return visDoc().images.length - n;
}, PNG_B64);
ok('끌어다 놓기: 놓은 위치에 이미지 넣기', dropped === 1);
await vis.locator('h1').click({ position: { x: 4, y: 4 } });
await page.evaluate(() => { const r = visDoc().createRange(); r.selectNodeContents(visDoc().querySelector('h1')); const s = visDoc().getSelection(); s.removeAllRanges(); s.addRange(r); });
await page.keyboard.press('Control+k');
await page.waitForSelector('#dlg[open]');
await page.fill('#dlg input[type="url"]', 'https://example.com/report');
await page.click('#dlg .btn.primary');
await page.waitForTimeout(100);
ok('링크: Ctrl+K로 선택한 글자에 링크', (await page.evaluate(() => visDoc().querySelector('h1 a')?.getAttribute('href'))) === 'https://example.com/report');
await vis.locator('p.meta').click();
await page.click('#tbVis [data-vcmd="table"]');
await page.waitForSelector('#dlg[open]');
await page.click('#dlg .btn.primary');
await page.waitForTimeout(100);
ok('표 넣기', (await page.evaluate(() => visDoc().querySelectorAll('table').length)) === 2);

/* ── 일괄 최적화 ── */
await page.click('#tabList');
await page.click('#btnOptAll');
await page.waitForSelector('#dlg[open]');
await page.click('#dlg .btn.primary');
await page.waitForFunction(() => /바꿨습니다|그대로/.test(document.querySelector('#toasts').textContent), null, { timeout: 15000 });
ok('일괄 최적화 실행', true);

/* ── 소스 보기·분할 보기 ── */
await page.click('#views button:nth-child(2)');
await page.waitForTimeout(150);
const src = await page.locator('#src').inputValue();
ok('소스: data URI를 ⟦img:…⟧로 접어 표시', /⟦img:\d+ (PNG|JPEG|WebP) [\d.]+KB⟧/.test(src) && !/base64,[A-Za-z0-9+/]{500}/.test(src));
ok('소스: 시각 편집 결과 반영', src.includes('href="https://example.com/report"') && src.includes('고객 정보 조회 화면 캡처'));
await shot(page, '07_source');
await page.locator('#src').fill(src.replace('점검 메모</a></h1>', '점검 메모</a> (수정)</h1>').replace('점검 메모</h1>', '점검 메모 (수정)</h1>'));
await page.click('#views button:nth-child(3)');
await page.waitForTimeout(800);
ok('분할: 소스 수정이 미리보기에 반영', (await page.frameLocator('#pre').locator('h1').textContent()).includes('(수정)'));
await page.click('#views button:nth-child(1)');
await page.waitForTimeout(400);
ok('시각 편집으로 돌아가면 소스 수정과 이미지 유지', await page.evaluate(() => visDoc().querySelector('h1').textContent.includes('(수정)') && [...visDoc().images].every(i => i.naturalWidth > 0)));

/* ── 저장 결과물 ── */
await vis.locator('p.meta').click();
const saved = await download(() => page.keyboard.press('Control+s'));
const html = saved.buf.toString('utf8');
ok('저장: 파일 이름 유지', saved.name === '예시_리스크_점검_메모.html', saved.name);
ok('저장: doctype·내장 이미지 포함, 편집기 흔적 없음', html.startsWith('<!DOCTYPE html>') && /src="data:image\/(jpeg|png|webp);base64,/.test(html) && !/data-lt-|⟦img|contenteditable/.test(html));
ok('저장 후 수정 표시 해제', await page.locator('#dirtyMark').isHidden());

/* ── Markdown ── */
await page.click('#btnNew');
await page.click('[data-act="new-md"]');
await page.waitForTimeout(300);
ok('Markdown 새 문서', (await page.locator('#docKind').textContent()) === 'MD');
const ta = page.locator('#src');
await ta.click();
await page.keyboard.press('Control+End');
await page.keyboard.type('- 첫째');
await page.keyboard.press('Enter');
await page.keyboard.type('둘째');
await page.keyboard.press('Enter');
await page.keyboard.press('Enter');
await page.keyboard.type('목록 끝');
const mdv = await ta.inputValue();
ok('목록 자동 이어쓰기, 빈 항목에서 Enter로 목록 끝내기', mdv.endsWith('- 첫째\n- 둘째\n목록 끝'), JSON.stringify(mdv.slice(-30)));
await ta.fill(mdv + '\n\n**굵게**와 `코드`, [링크](https://example.com)\n\n> 인용문\n\n- [ ] 할 일\n- [x] 끝낸 일\n');
await page.waitForTimeout(400);
const pre = page.frameLocator('#pre');
ok('미리보기 렌더링', (await pre.locator('h1').first().textContent()) === '제목' && (await pre.locator('strong').count()) === 1 && (await pre.locator('blockquote').count()) === 1 && (await pre.locator('input[type=checkbox]').count()) === 2 && (await pre.locator('table').count()) === 1);
await ta.evaluate(t => { const i = t.value.indexOf('인용문'); t.focus(); t.setSelectionRange(i, i + 3); });
await page.click('#tbMd [data-mcmd="bold"]');
ok('도구 막대 굵게', (await ta.inputValue()).includes('**인용문**'));
await ta.evaluate(t => { t.focus(); t.setSelectionRange(t.value.length, t.value.length); });
await page.click('#tbMd [data-mcmd="image"]');
const [mdChooser] = await Promise.all([page.waitForEvent('filechooser'), page.click('#menuImg [data-act="img-file"]')]);
await mdChooser.setFiles(PNG);
await page.waitForTimeout(400);
const mdv2 = await ta.inputValue();
ok('이미지 넣기: 빈 줄을 두고 ![](⟦img⟧) 문단으로', /\n\n!\[\]\(⟦img:\d+ PNG [\d.]+KB⟧\)\n$/.test(mdv2), JSON.stringify(mdv2.slice(-50)));
await page.waitForTimeout(300);
ok('미리보기에 내장 이미지 표시', await pre.locator('img').first().evaluate(i => i.naturalWidth === 320));
await shot(page, '08_md_split');
await page.click('#btnMore');
const exp = await download(() => page.click('[data-act="export-html"]'));
const expHtml = exp.buf.toString('utf8');
ok('HTML로 내보내기', exp.name === '새 문서.html' && expHtml.includes('<title>제목</title>') && /<img src="data:image\/png;base64,/.test(expHtml) && !expHtml.includes('data-line') && expHtml.includes('Pretendard'), exp.name);
const mdFile = await download(() => page.click('#btnSave'));
ok('Markdown 저장: 이미지 데이터를 펼쳐서 저장', mdFile.buf.toString('utf8').includes('](data:image/png;base64,') && !mdFile.buf.toString('utf8').includes('⟦img'));

/* ── Markdown 변환 규칙 ── */
const cases = await page.evaluate(() => {
  const r = s => MD.render(s, { lines: false }).trim();
  return {
    setext: r('제목\n===\n\n부제\n---'),
    nested: r('1. 하나\n   - 가\n   - 나\n2. 둘'),
    start: r('3. 셋\n4. 넷'),
    table: r('| 왼 | 가운데 | 오른 |\n|:--|:--:|--:|\n| `a\\|b` | 2 | 3 |'),
    fence: r('```python\nprint("<x>")\n```'),
    ticks: r('`` a`b ``'),
    quote: r('> 바깥\n>> 안쪽'),
    html: r('<details>\n<summary>열기</summary>\n\n내용\n\n</details>'),
    refs: r('[보고서][r1]\n\n[r1]: https://example.com/a "제목"'),
    auto: r('주소 https://example.com/a_b_c 와 info@onelineai.com'),
    korean: r('**PLGD(Potential LGD)**는 손실률이다'),
    blank: r('확정: ______ 표시'),
    tilde: r('행간 1.5~1.6, ~~삭제~~'),
    br: r('첫 줄  \n둘째 줄'),
    escape: r('\\*별표\\* 와 <br> 태그'),
    js: r('[x](javascript:alert(1)) ![y](data:image/png;base64,AAAA)')
  };
});
ok('규칙: setext 제목', cases.setext === '<h1 id="제목">제목</h1>\n<h2 id="부제">부제</h2>', cases.setext);
ok('규칙: 중첩 목록', /<ol>\n<li>하나\n<ul>\n<li>가<\/li>\n<li>나<\/li>\n<\/ul><\/li>\n<li>둘<\/li>\n<\/ol>/.test(cases.nested), cases.nested);
ok('규칙: 번호 시작값', cases.start.startsWith('<ol start="3">'), cases.start);
ok('규칙: 표 정렬과 칸 안 \\|', cases.table.includes('<th style="text-align:center">가운데</th>') && cases.table.includes('<td style="text-align:left"><code>a|b</code></td>'), cases.table);
ok('규칙: 코드 블록 언어·이스케이프', cases.fence === '<pre><code class="language-python">print(&quot;&lt;x&gt;&quot;)\n</code></pre>', cases.fence);
ok('규칙: 백틱 두 개 코드', cases.ticks === '<p><code>a`b</code></p>', cases.ticks);
ok('규칙: 중첩 인용', (cases.quote.match(/<blockquote>/g) || []).length === 2, cases.quote);
ok('규칙: HTML 블록 통과', cases.html.includes('<details>') && cases.html.includes('<p>내용</p>'), cases.html);
ok('규칙: 참조 링크', cases.refs === '<p><a href="https://example.com/a" title="제목">보고서</a></p>', cases.refs);
ok('규칙: 맨 주소·이메일 자동 링크 (밑줄 강조 안 함)', cases.auto.includes('<a href="https://example.com/a_b_c">https://example.com/a_b_c</a>') && cases.auto.includes('<a href="mailto:info@onelineai.com">'), cases.auto);
ok('규칙: 한국어 조사 앞 굵게', cases.korean === '<p><strong>PLGD(Potential LGD)</strong>는 손실률이다</p>', cases.korean);
ok('규칙: 밑줄 빈칸은 강조 아님', cases.blank === '<p>확정: ______ 표시</p>', cases.blank);
ok('규칙: 물결표 범위 유지, 두 개는 취소선', cases.tilde === '<p>행간 1.5~1.6, <del>삭제</del></p>', cases.tilde);
ok('규칙: 공백 두 칸 줄바꿈', cases.br === '<p>첫 줄<br>\n둘째 줄</p>', cases.br);
ok('규칙: 이스케이프·인라인 HTML', cases.escape === '<p>*별표* 와 <br> 태그</p>', cases.escape);
ok('규칙: javascript 링크 차단, 이미지 data URI 허용', cases.js.includes('<a href="#">x</a>') && cases.js.includes('src="data:image/png;base64,AAAA"'), cases.js);

/* ── 인코딩·조각 HTML·스크립트 문서 ── */
writeFileSync(join(TMP, 'euckr.html'), Buffer.concat([Buffer.from('<html><head><meta charset="euc-kr"></head><body>'), Buffer.from([60, 112, 62, 199, 209, 177, 219, 32, 192, 206, 196, 218, 181, 249, 32, 200, 174, 192, 206, 60, 47, 112, 62]), Buffer.from('</body></html>')]));
await page.setInputFiles('#fileInput', join(TMP, 'euckr.html'));
await page.waitForFunction(() => D.name === 'euckr.html', null, { timeout: 5000 });
await visReady();
ok('인코딩: EUC-KR 자동 감지', (await page.evaluate(() => visDoc().body.textContent)).includes('한글 인코딩 확인') && (await page.locator('#stEnc').textContent()).includes('EUC-KR'));
ok('인코딩: meta charset을 utf-8로 교정', await page.evaluate(() => /charset="?utf-8/i.test(unfold(el.src.value))));
writeFileSync(join(TMP, 'frag.html'), '<p>조각 문서</p>\n');
await page.setInputFiles('#fileInput', join(TMP, 'frag.html'));
await page.waitForFunction(() => D.name === 'frag.html', null, { timeout: 5000 });
await visReady();
await vis.locator('p').click();
await page.keyboard.press('End');
await page.keyboard.type(' 추가');
await page.waitForTimeout(600);
const frag = await download(() => page.click('#btnSave'));
ok('조각 HTML: 골격을 덧붙이지 않고 저장', frag.buf.toString('utf8').trim() === '<p>조각 문서 추가</p>', frag.buf.toString('utf8'));
writeFileSync(join(TMP, 'script.html'), '<!DOCTYPE html><html><head><title>s</title></head><body><p id="x">원문</p><script>document.getElementById("x").textContent="스크립트 실행됨"</script></body></html>');
await page.setInputFiles('#fileInput', join(TMP, 'script.html'));
await page.waitForFunction(() => D.name === 'script.html', null, { timeout: 5000 });
await visReady();
ok('스크립트: 시각 편집에서 실행하지 않음', (await page.evaluate(() => visDoc().getElementById('x').textContent)) === '원문');
await vis.locator('#x').click();
await page.keyboard.type('!');
await page.waitForTimeout(600);
const scr = (await download(() => page.click('#btnSave'))).buf.toString('utf8');
ok('스크립트: 저장할 때는 그대로 남김', scr.includes('<script>document.getElementById("x")') && scr.includes('원문!'));

/* ── 임시 저장본 복구 ── */
await vis.locator('#x').click();
await page.keyboard.type('임시');
await page.waitForTimeout(2800);
await page.reload();
await page.waitForSelector('#banner:not([hidden])', { timeout: 8000 });
await page.click('#banner .btn.primary');
await page.waitForFunction(() => D.name === 'script.html', null, { timeout: 5000 });
await visReady();
ok('임시 저장본 복구', (await page.evaluate(() => visDoc().getElementById('x').textContent)).includes('임시'));
ok('콘솔 오류 없음', errors.length === 0, errors.join(' | '));

/* ── 좁은 화면 ── */
await page.click('#btnNew');
await page.click('[data-act="sample"]');
await confirmIfAsked();
await page.waitForFunction(() => D.sample && visDoc() && visDoc().images.length === 2, null, { timeout: 8000 });
await page.emulateMedia({ colorScheme: 'dark' });
await shot(page, '09_dark');
await page.setViewportSize({ width: 400, height: 860 });
await page.waitForTimeout(300);
ok('좁은 화면: 가로 넘침 없음', !(await page.evaluate(() => document.documentElement.scrollWidth > innerWidth)));
await shot(page, '10_mobile');
await vis.locator('img').first().dblclick();
await page.waitForSelector('#ied[open]');
await page.waitForTimeout(300);
ok('좁은 화면: 편집 창이 가로로 밀리지 않음', await page.evaluate(() => $('#ied').scrollLeft === 0 && $('.ied-grid').getBoundingClientRect().left === 0));
await shot(page, '11_mobile_editor');

await browser.close();
const failed = results.filter(r => !r).length;
console.log(`\n${results.length - failed}/${results.length} 통과`);
process.exitCode = failed ? 1 : 0;
