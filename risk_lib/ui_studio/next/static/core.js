/* core.js: shell runtime of the next-gen studio (design spec 3, 5, 7).
   render.py emits const NAVGROUPS, TABS and NAV_DISPLAY above this line.
   Screens register later through NG.screen(id, def); builders are resolved
   lazily, so nothing here needs a registration at boot. Every string authored
   here is a Korean catalogue key passed through T(); ledger values, ids,
   digests, check names and citations are never translated. */
(function(){
'use strict';
const W=window,DOC=document;
const I18N=W.__RYNTA_I18N__||{map:{},default:'en',langs:['en','ko'],storage_key:'rynta-lang',debug:false};
const I18N_DEBUG=I18N.debug||(typeof location!=='undefined'&&/[?&]i18n=debug/.test(location.search));
const I18N_MISS=[],I18N_HIT=[];
const HANGUL=/[가-힣]/;
const LANG_KEY=I18N.storage_key||'rynta-lang',THEME_KEY='rynta-theme',NAV_KEY='rynta-nav';
const LANGS=I18N.langs||['en','ko'];
let LANG=I18N.default||'en';
function T(s){
  if(s==null)return s;
  const k=String(s);
  if(LANG==='ko'||!HANGUL.test(k))return k;
  const hit=I18N.map[k];
  if(hit!==undefined){if(I18N_HIT.indexOf(k)<0)I18N_HIT.push(k);return hit}
  if(I18N_MISS.indexOf(k)<0)I18N_MISS.push(k);
  return I18N_DEBUG?'⟦'+k+'⟧':k;
}
function fmtVar(v){return typeof v==='number'?fmt.num(v):(v==null?'-':String(v))}
function TF(key,vars){
  let s=T(key);vars=vars||{};
  Object.keys(vars).forEach(n=>{s=s.split('{'+n+'}').join(fmtVar(vars[n]))});
  return s;
}
/* prose hygiene at display time only; never applied to ledger cells */
function text(s){return s==null?'':String(s).replace(/[\u2014\u2013]/g,', ')}
const fmt={
  num:v=>typeof v==='number'?(Math.abs(v)>=1000?v.toLocaleString('ko-KR',{maximumFractionDigits:0}):v.toLocaleString('ko-KR',{maximumFractionDigits:6})):(v==null?'-':String(v)),
  int:v=>typeof v==='number'?Math.round(v).toLocaleString('ko-KR'):(v==null?'-':String(v)),
  money:v=>{if(typeof v!=='number')return fmt.orDash(v);const a=Math.abs(v);
    if(LANG==='ko'){if(a>=1e12)return (v/1e12).toFixed(1)+'조';if(a>=1e8)return (v/1e8).toFixed(0)+'억'}
    else{if(a>=1e12)return (v/1e12).toFixed(2)+'tn';if(a>=1e9)return (v/1e9).toFixed(2)+'bn';if(a>=1e6)return (v/1e6).toFixed(1)+'m'}
    return fmt.num(v)},
  pct:(v,d)=>typeof v==='number'?(v*100).toFixed(d==null?2:d)+'%':fmt.orDash(v),
  pp:(v,d)=>typeof v==='number'?((v>=0?'+':'')+v.toFixed(d==null?2:d)+'%p'):fmt.orDash(v),
  date:s=>s==null?'-':String(s),
  orDash:v=>(v==null||v==='')?'-':String(v)
};
/* ---- DOM helpers ---- */
const $=(s,r)=>(r||DOC).querySelector(s),$$=(s,r)=>Array.prototype.slice.call((r||DOC).querySelectorAll(s));
function el(tag,cls,txt){const e=DOC.createElement(tag);if(cls)e.className=cls;if(txt!=null)e.textContent=txt;return e}
function ap(p){for(let i=1;i<arguments.length;i++){const k=arguments[i];if(k!=null)p.appendChild(typeof k==='string'?DOC.createTextNode(k):k)}return p}
/* ---- runs and state ---- */
let RUNS=W.__RYNTA_RUNS__||{};
let D=W.__RYNTA__||RUNS[Object.keys(RUNS).sort().slice(-1)[0]]||{meta:{},data:{}};
const INSTS=W.__RYNTA_INSTS__||{};
const NAV=W.__RYNTA_NAV__||{groups:[],screens:[],aliases:{},labels:{},nav_display:{}};
const SCREENS={};NAV.screens.forEach(s=>{SCREENS[s.id]=s});
const GROUPS={};NAV.groups.forEach(g=>{GROUPS[g.label_ko]=g});
const NAVDISP=(typeof NAV_DISPLAY!=='undefined'&&NAV_DISPLAY)||NAV.nav_display||{};
function freshState(){return {killed:false,killScope:'전사',killReason:'',killConfirm:'',approved:{},history:{},labelOverrides:{}}}
const STATE=freshState(),BYRUN={};
function runKey(d){return ((d.meta&&d.meta.institution_code)||'-')+'|'+((d.meta&&d.meta.asof)||'-')}
function stashRun(){BYRUN[runKey(D)]=Object.assign({},STATE)}
/* per-run caches */
let TONE_IDX=null,CAT=null,FKI=null;
function resetIdx(){TONE_IDX=null;CAT=null;FKI=null;PAL.index=null}
/* ---- registry ---- */
const REG=new Map();
const CUR={id:null,params:{},missing:false};
function screen(id,def){REG.set(id,def||{});if(CUR.id===id&&CUR.missing&&SECTS[id]){SECTS[id].section.dataset.done='';activate(id,CUR.params,{})}}
/* ---- tone and glyph from D.x_severity ---- */
const GLYPH_DEF={good:'●',warn:'◆',bad:'✕',blocked:'⊘','not-run':'○',synthetic:'▧',explanatory:'≈',neutral:'·'};
const TONE_WORD={good:'양호',warn:'주의',bad:'불량',blocked:'차단','not-run':'미실행',synthetic:'합성',explanatory:'설명용',neutral:'중립'};
function toneIdx(){if(TONE_IDX)return TONE_IDX;TONE_IDX={};((D.x_severity&&D.x_severity.map)||[]).forEach(r=>{(TONE_IDX[r.source]=TONE_IDX[r.source]||{})[r.value]=r.tone});return TONE_IDX}
function tone(source,value){const s=toneIdx()[source];return (s&&s[String(value)])||'neutral'}
function glyphChar(t){const g=D.x_severity&&D.x_severity.glyphs;return (g&&g[t])||GLYPH_DEF[t]||GLYPH_DEF.neutral}
function glyph(t){t=t||'neutral';const s=el('span','glyph '+t,glyphChar(t));s.dataset.tone=t;s.setAttribute('role','img');s.setAttribute('aria-label',T(TONE_WORD[t]||t));return s}
function checkTone(c){if(c.is_identity)return 'neutral';if(/_not_run$/.test(String(c.check_name)))return tone('val_check.status','_not_run');if(c.status==='WARN'&&c.blocks_approval)return tone('val_check.status','WARN+blocks_approval');return tone('val_check.status',c.status)}
/* ---- frame helpers ---- */
const frame={
  frameIdx:f=>{const i={};((f&&f.columns)||[]).forEach((c,k)=>{i[c]=k});return i},
  frameObjects:f=>f?f.rows.map(r=>{const o={};f.columns.forEach((c,k)=>{o[c]=r[k]});return o}):[],
  frameOf:n=>(D.data&&D.data[n])||null,
  full:n=>{const f=D.data&&D.data[n];return (f&&f.shown===f.total)?f:null},
  colLabel:(f,i)=>{const p=f.columns[i];const o=f.table&&STATE.labelOverrides[f.table];return (o&&o[p])||(f.labels&&f.labels[i])||p},
  truncated:f=>!!f&&f.shown<f.total
};
function cat(name){if(!CAT){CAT={};(D.catalog||[]).forEach(c=>{CAT[c.name]=c})}return CAT[name]||null}
function fkOf(table){if(!FKI){FKI={};const xs=D.x_screens||{};Object.keys(xs).forEach(id=>{(xs[id].ledgers||[]).forEach(l=>{if(l.fk&&l.fk.length&&!FKI[l.table])FKI[l.table]=l.fk})})}return FKI[table]||[]}
/* ---- lineage ---- */
const lineage={
  of:id=>{const f=D.x_lineage&&D.x_lineage.figures&&D.x_lineage.figures[id];return f?Object.assign({figure_id:id},f):null},
  kpi:i=>{const m=D.x_lineage&&D.x_lineage.kpi_map;return (m&&m[i])?lineage.of(m[i]):null},
  byTarget:t=>{const fg=(D.x_lineage&&D.x_lineage.figures)||{};const k=Object.keys(fg).find(x=>fg[x].recalc_target===t);return k?lineage.of(k):null}
};
/* ---- ui primitives ---- */
function cell(v){return v==null?'-':(typeof v==='number'?fmt.num(v):String(v))}
function badge(txt,t){t=t||'neutral';const s=el('span','badge '+t);s.dataset.tone=t;ap(s,glyph(t),' '+txt);return s}
function pill(txt,t){const s=el('span','pill'+(t?' '+t:''),txt);if(t)s.dataset.tone=t;return s}
function note(txt,t){const d=el('div','note'+(t==='bad'?' bad':'')+(t?' '+t:''));if(t)d.dataset.tone=t;if(t&&t!=='neutral')ap(d,glyph(t),' ');ap(d,txt);return d}
function productChip(table){const c=table?cat(table):null,p=c?c.product:null;const s=el('span','chip prod',p||T('카탈로그 외 · 엔진 산출'));if(p)s.title=T('제품 코드');return s}
function truncBadge(f){const cut=f.shown<f.total;return badge(cut?TF('표본 {n}/{N}',{n:f.shown,N:f.total}):TF('전량 {N}',{N:f.total}),cut?'warn':'neutral')}
function srcMeta(f,extra){const p=[];if(f.table)p.push(T('원장')+' '+f.table);p.push(f.shown<f.total?TF('{shown}/{total}행',{shown:f.shown,total:f.total}):TF('전량 {N}행',{N:f.total}));if(extra)p.push(T(extra));return el('div','meta src',p.join(' · '))}
function input(o){o=o||{};const e=el(o.multiline?'textarea':'input','input');if(!o.multiline)e.type=o.type||'text';if(o.value!=null)e.value=o.value;if(o.placeholder)e.placeholder=o.placeholder;if(o.aria)e.setAttribute('aria-label',o.aria);['min','max','step'].forEach(k=>{if(o[k]!=null)e[k]=o[k]});if(o.onInput)e.oninput=()=>o.onInput(e.value,e);return e}
function button(txt,o){o=o||{};const b=el('button','btn'+(o.primary?' primary':''),txt);b.type='button';if(o.onClick)b.onclick=o.onClick;if(o.disabled)b.disabled=true;if(o.title)b.title=o.title;return b}
function select(options,onChange,cls){const s=el('select',cls||'sel');options.forEach(o=>{const x=typeof o==='string'?{value:o,label:o}:o;const op=el('option',null,x.raw?x.label:T(x.label));op.value=x.value;if(x.selected)op.selected=true;ap(s,op)});if(onChange)s.onchange=()=>onChange(s.value,s);return s}
function chips(items,onPick){const box=el('div','chips');items.forEach(t=>{const o=typeof t==='string'?{value:t,label:t}:t;const lb=o.raw?o.label:T(o.label);const b=el('button','chip'+(o.on?' on':''),lb);b.type='button';b.dataset.value=o.value;// 칩은 한 줄로 줄여 보인다. 줄인 글은 title 로 전문을 남긴다.
if(String(lb).length>20)b.title=String(lb);b.onclick=()=>{$$('.chip',box).forEach(c=>c.classList.remove('on'));b.classList.add('on');if(onPick)onPick(o.value,b)};ap(box,b)});return box}
function meter(label,num,den,t){const d=el('div','meter'+(t?' '+t:''));if(t)d.dataset.tone=t;const h=el('div','meta');ap(h,el('span',null,T(label)),el('span','num',fmt.num(num)+' / '+fmt.num(den)));const b=el('div','bar'),i=el('i');i.style.width=(den?Math.min(100,Math.abs(num)/den*100):0).toFixed(1)+'%';ap(b,i);ap(d,h,b);return d}
// 숫자 칸은 자릿수를 맞추려 줄바꿈을 막는다. 지문·체크명 나열처럼 숫자가
// 아닌 긴 값이 그 칸에 오면 잘리므로, 길이로 갈라 끊어 쓰게 한다.
function longVal(v){const t=String(v==null?'':v);return t.length>24}
function dotlist(items){const u=el('ul','list dots');items.forEach(x=>{const li=el('li');const t=x.tone||'neutral';li.dataset.tone=t;ap(li,glyph(t),' ',el('span','txt',x.text),x.right!=null?el('span','right'+(longVal(x.right)?' wrap':''),String(x.right)):null);if(x.onClick){li.tabIndex=0;li.classList.add('click');li.onclick=x.onClick;li.onkeydown=e=>{if(e.key==='Enter')x.onClick()}}ap(u,li)});return u}
function explanatory(root){const r=el('div','ribbon explanatory');ap(r,glyph('explanatory'),' '+T('설명용 산술 · 승인·제출값 아님'));root.classList.add('explanatory');root.insertBefore(r,root.firstChild);return r}
function errorCard(err){const c=el('div','card note bad error');c.dataset.tone='bad';ap(c,el('h3',null,T('화면 오류')),el('p',null,T('이 화면을 그리는 중 오류가 났다. 다른 화면은 영향이 없다.')),el('pre',null,String((err&&err.message)||err)));return c}
function section(title,o){o=o||{};let s;const h=el('h3',null,o.raw?title:T(title));
  if(o.folded){s=el('details','card sec');if(o.open)s.open=true;const sm=el('summary');ap(sm,h);ap(s,sm)}else{s=el('section','card sec');ap(s,h)}
  if(o.chips&&o.chips.length){const c=el('div','chips prods');o.chips.forEach(p=>ap(c,el('span','chip prod',p)));ap(s,c)}
  if(o.id)s.id=o.id;return s}
function simpleTable(cols,rows,o){o=o||{};const w=el('div','tw'),t=el('table'),th=el('thead'),tr=el('tr');
  const keys=cols.map(c=>typeof c==='string'?c:c.key),labs=cols.map(c=>typeof c==='string'?T(c):(c.raw?c.label:T(c.label)));
  const rr=rows.map(r=>Array.isArray(r)?r:keys.map(k=>r[k]));
  const isNum=keys.map((_,i)=>o.numeric!==false&&rr.some(r=>typeof r[i]==='number'));
  labs.forEach((l,i)=>{const h=el('th',isNum[i]?'num':null,l);const c=cols[i];if(c&&c.phys)h.title=c.phys;ap(tr,h)});ap(th,tr);ap(t,th);
  const tb=el('tbody');rr.forEach((r,ri)=>{const x=el('tr');if(o.rowClass){const c=o.rowClass(rows[ri],ri);if(c)x.className=c}
    r.forEach((v,i)=>{const td=el('td',isNum[i]?('num'+(longVal(v)?' wrap':'')):null);if(v instanceof Node)ap(td,v);else td.textContent=cell(v);ap(x,td)});
    if(o.onRow){x.tabIndex=0;x.classList.add('click');x.onclick=()=>o.onRow(rows[ri],ri);x.onkeydown=e=>{if(e.key==='Enter')o.onRow(rows[ri],ri)}}ap(tb,x)});
  ap(t,tb);ap(w,t);return w}
const PAGE=500;
function table(f,o){o=o||{};const card=el('div','card tbl');if(!f){ap(card,note(T('연결 원장 없음'),'warn'));return card}
  const head=el('div','trow');if(o.title)ap(head,el('h3',null,o.raw?o.title:T(o.title)));
  ap(head,productChip(o.product===undefined?f.table:o.product),truncBadge(f));ap(card,head,srcMeta(f));
  const nC=f.columns.length,vis=f.columns.map(()=>true);
  const isNum=f.columns.map((_,i)=>o.numeric!==false&&f.rows.some(r=>typeof r[i]==='number'));
  let sortCol=-1,sortDir=1,q='',limit=PAGE;
  const ctrl=el('div','tctrl');
  if(o.filter!==false){const inp=input({placeholder:T('열 필터'),aria:T('열 필터')});inp.oninput=()=>{q=inp.value.trim().toLowerCase();limit=PAGE;draw()};ap(ctrl,inp)}
  if(o.chooser!==false&&nC>12){const d=el('details','chooser');ap(d,el('summary',null,T('열 선택')));const ch=el('div','chips');
    f.columns.forEach((c,i)=>{const b=el('button','chip on',frame.colLabel(f,i));b.type='button';b.title=c;b.onclick=()=>{vis[i]=!vis[i];b.classList.toggle('on',vis[i]);draw()};ap(ch,b)});ap(d,ch);ap(ctrl,d)}
  ap(card,ctrl);const tw=el('div','tw'),foot=el('div','meta tfoot');ap(card,tw,foot);
  function view(){let idx=f.rows.map((_,i)=>i);
    if(q)idx=idx.filter(i=>f.rows[i].some((v,k)=>vis[k]&&v!=null&&String(v).toLowerCase().indexOf(q)>=0));
    if(sortCol>=0)idx.sort((a,b)=>{const x=f.rows[a][sortCol],y=f.rows[b][sortCol];if(x==null&&y==null)return 0;if(x==null)return 1;if(y==null)return -1;return (x<y?-1:x>y?1:0)*sortDir});
    return idx}
  function draw(){tw.innerHTML='';const t=el('table'),th=el('thead'),tr=el('tr');
    f.columns.forEach((c,i)=>{if(!vis[i])return;const lab=frame.colLabel(f,i),h=el('th',isNum[i]?'num':null,lab);if(lab!==c)h.title=c;
      h.setAttribute('aria-sort',sortCol===i?(sortDir>0?'ascending':'descending'):'none');h.tabIndex=0;
      const go=()=>{if(sortCol===i)sortDir=-sortDir;else{sortCol=i;sortDir=1}draw()};h.onclick=go;h.onkeydown=e=>{if(e.key==='Enter'||e.key===' '){e.preventDefault();go()}};ap(tr,h)});
    ap(th,tr);ap(t,th);const tb=el('tbody'),idx=view(),n=idx.length;
    idx.slice(0,limit).forEach(i=>{const r=f.rows[i],x=el('tr');if(o.rowClass){const c=o.rowClass(r,i);if(c)x.className=c}
      r.forEach((v,k)=>{if(vis[k])ap(x,el('td',isNum[k]?('num'+(longVal(v)?' wrap':'')):null,cell(v)))});
      x.tabIndex=0;const open=()=>o.onRow?o.onRow(r,i,f):drawer.row(f,i);x.onclick=open;x.onkeydown=e=>{if(e.key==='Enter')open()};ap(tb,x)});
    ap(t,tb);ap(tw,t);foot.innerHTML='';const bits=[];
    if(f.shown<f.total)bits.push(TF('미리보기 {n}행 / 전체 {N}행',{n:f.shown,N:f.total}));
    if(q)bits.push(TF('{n}행',{n:n}));ap(foot,bits.join(' · '));
    if(n>limit){const rest=n-limit;ap(foot,' ',button(TF('{n}건 더 보기',{n:rest}),{onClick:()=>{limit+=PAGE;draw()}}))}}
  draw();return card}
function kpi(o){o=o||{};const t=o.tone||'neutral',c=el('div','card kpi '+t);c.dataset.tone=t;
  ap(c,el('div','lab',o.raw?o.label:T(o.label)));const v=el('div','val');const vs=o.value==null?'-':String(o.value),vn=el('span','num',vs);if(vs.length>14)v.classList.add('xlong');else if(vs.length>8)v.classList.add('long');vn.title=vs;ap(v,glyph(t),vn);ap(c,v);
  if(o.sub)ap(c,el('div','sub',o.sub));
  if(o.delta!=null&&o.delta!==false)ap(c,el('div','sub delta',String(o.delta)));
  else if(o.delta!==false&&D.x_trend&&D.x_trend.single_period)ap(c,el('div','sub delta',T('단일 기간')));
  const ln=typeof o.lineage==='string'?lineage.of(o.lineage):(o.lineage||null);
  const st=o.badge||(ln&&(ln.gate_state||(ln.in_scope===false?'범위밖':null)));
  if(st)ap(c,badge(T(st),tone('recalc.state',st)));
  if(ln){const a=el('button','ln',T('계보')+' · '+(ln.figure_id||ln.label||''));a.type='button';a.onclick=e=>{e.stopPropagation();drawer.lineage(ln)};ap(c,a);c.classList.add('click');c.onclick=()=>drawer.lineage(ln)}
  return c}
function kpiRow(items,density){const g=el('div','kpis '+((density||'operator')==='committee'?'c4':'c6'));items.forEach(i=>ap(g,i instanceof Node?i:kpi(i)));return g}
function tabs(root,list,active){const bar=el('div','tabs'),pane=el('div','tabpane');bar.setAttribute('role','tablist');
  let cur=(active&&list.some(t=>t.key===active))?active:(list[0]&&list[0].key);
  function show(k,write){if(!list.some(t=>t.key===k))return;cur=k;
    $$('button',bar).forEach(b=>{const on=b.dataset.key===k;b.classList.toggle('on',on);b.setAttribute('aria-selected',on?'true':'false')});
    pane.innerHTML='';const t=list.find(x=>x.key===k);if(t)guard(()=>t.build(pane,ctxFor(CUR.id)),pane,CUR.id+'#'+k);
    if(write&&CUR.id){const p=Object.assign({},CUR.params);p.tab=k;CUR.params=p;writeHash(CUR.id,p,true)}}
  list.forEach(t=>{const b=el('button','tab',t.raw?t.title:T(t.title));b.type='button';b.dataset.key=t.key;b.setAttribute('role','tab');b.onclick=()=>show(t.key,true);ap(bar,b)});
  ap(root,bar,pane);if(cur)show(cur,false);return {show:show,current:()=>cur}}
/* ---- error boundary ---- */
function report(id,err,level){(W.__NG_ERRORS__=W.__NG_ERRORS__||[]).push({id:id,message:String((err&&err.message)||err),stack:(err&&err.stack)||''});(console[level]||console.error)('[NG] '+id+':',err)}
function guard(fn,root,label){try{return fn()}catch(err){report(label,err,'error');if(root)ap(root,errorCard(err));return undefined}}
/* ---- gate strip (spec 3.2) ---- */
function paintGate(){const g=$('#gatestrip');if(!g)return;g.innerHTML='';const x=D.x_gate;
  const seg=(cls,t,txt)=>{const b=el('button','gseg '+cls+' '+t);b.type='button';b.dataset.tone=t;ap(b,glyph(t),' '+txt);b.title=T('게이트 드로어 열기');b.onclick=()=>drawer.gate();ap(g,b);return b};
  if(!x){seg('l3','blocked',T('상시 독립검증 (3선)')+' '+T('3선 게이트 미확인')+' · '+T('게이트 객체 없음'));g.dataset.gateStatus='3선 게이트 미확인';g.dataset.tone='blocked';return}
  const s=x.self||{},i=x.independent||{},a=x.approvals||{},sub=x.submission||{},ov=x.overall||{};
  seg('l2',s.tone||'neutral',T('자체검증 (2선)')+' '+TF('PASS {pass} · WARN {warn} · FAIL {fail} · 규제미달 {blocks} · 미실행 {not_run} (항등식 {identity} 제외)',{pass:s.pass,warn:s.warn,fail:s.fail,blocks:s.blocks,not_run:s.not_run,identity:s.identity_excluded}));
  const st=i.ledger_present===false?T('3선 원장 행 없음'):(i.status||T('3선 게이트 미확인'));
  seg('l3',i.tone||'blocked',T('상시 독립검증 (3선)')+' '+TF('{status} ({request_id}) · {kind} · {dispatch}',{status:st,request_id:i.request_id||'-',kind:i.kind||'unknown',dispatch:dispatchWord(i)}));
  const nh=(a.holds||[]).length,at=a['반려']>0?'bad':a['대기']>0?'blocked':'good';
  seg('ap',at,T('결재')+' '+TF('결재 대기 {pending} · 승인 {approved} · 반려 {returned} · 보류 사유 {kinds}종 · 제출 {reviewed}/{total}',{pending:a['대기'],approved:a['승인'],returned:a['반려'],kinds:nh,reviewed:sub.reviewed,total:sub.total}));
  if(ov.status==='조건부'||(x.conditional&&x.conditional.required))seg('cond','warn',T('조건부 승인')+' · '+((x.conditional&&x.conditional.text)||''));
  g.dataset.gateStatus=i.ledger_present===false?'':(i.status||'3선 게이트 미확인');g.dataset.tone=ov.tone||'blocked'}
function dispatchWord(i){return i.dispatched===true?T('발신'):i.dispatched===false?T('미발신'):T('발신 미확인')}
/* ---- badge row and provenance header (spec 3.4) ---- */
function gateBadge(id){const row=el('div','badges');const sg=D.x_screen_gate||{};
  const checks=(sg.checks&&sg.checks[id])||[],targets=(sg.targets&&sg.targets[id])||[],scope=sg.scope&&sg.scope[id];
  const cw=el('div','brow l2');ap(cw,el('span','lab',T('이 화면의 2선 검증')));
  const nc=checks.length;
  if(!nc)ap(cw,el('span','meta',T('이 화면에 연결된 2선 검증이 없다')));
  else{const nf=checks.filter(c=>c.status==='FAIL').length,nw=checks.filter(c=>c.status==='WARN').length;
    ap(cw,el('span','meta',TF('2선 검증 {n}건 · FAIL {fail} · WARN {warn}',{n:nc,fail:nf,warn:nw})));
    checks.forEach(c=>{const b=badge(c.check_name+' '+c.status,checkTone(c));b.tabIndex=0;b.classList.add('click');b.title=text(c.detail);b.onclick=()=>drawer.check(c.check_name);b.onkeydown=e=>{if(e.key==='Enter')drawer.check(c.check_name)};ap(cw,b)})}
  ap(row,cw);const tw=el('div','brow l3');ap(tw,el('span','lab',T('이 화면의 3선 재계산 대상')));
  const nt=targets.length;
  if(!nt)ap(tw,el('span','meta',T('이 화면에 3선 재계산 대상이 없다')));
  else{const cnt=k=>targets.filter(t=>t.state===k).length;
    ap(tw,el('span','meta',TF('3선 대상 {n}건 · 일치 {matched} · 불일치 {mismatched} · 미보고 {unreported}',{n:nt,matched:cnt('일치'),mismatched:cnt('불일치'),unreported:cnt('미보고')})));
    targets.forEach(t=>{const b=badge(t.target+' '+T(t.state),tone('recalc.state',t.state));b.tabIndex=0;b.classList.add('click');b.title=(t.korean||'')+(t.citation?' · '+t.citation:'');
      const open=()=>{const ln=lineage.byTarget(t.target);if(ln)drawer.lineage(ln);else drawer.gate()};b.onclick=open;b.onkeydown=e=>{if(e.key==='Enter')open()};ap(tw,b)})}
  ap(row,tw);
  if(scope)ap(row,el('div','meta scope',TF('이 화면의 수치 {n}건이 RECALC_SCOPE 에 있고 {m}건은 재계산 대상 아님',{n:scope.in_scope,m:scope.out_of_scope})));
  return row}
function provHeader(id){const box=el('div','prov');const xs=(D.x_screens||{})[id];
  if(!xs){ap(box,el('div','meta',T('연결 원장 없음')));return box}
  const led=el('div','ledgers');ap(led,el('span','lab',T('연결 원장')));
  (xs.ledgers||[]).forEach(l=>{const b=el('button','chip ledger');b.type='button';
    ap(b,el('code',null,l.table),l.product?el('span','prod',l.product):null,el('span','cnt',l.shown<l.total?TF('표본 {n}/{N}',{n:l.shown,N:l.total}):TF('전량 {N}',{N:l.total})));
    const pk=(l.pk||[]).join(', ');b.title=(l.korean||'')+(pk?' · pk '+pk:'');b.onclick=()=>openTable(l.table);ap(led,b)});
  ap(box,led);const line=el('div','meta provline');
  if(xs.synthetic)ap(line,badge(T('합성데이터 · 합성 포트폴리오')+' · '+TF('시드 {seed}',{seed:D.meta.seed}),'synthetic'),' · ');
  const own=el('span','own');
  if(xs.ownership){own.textContent=T('소관 (UI 가정)')+' '+xs.ownership.role_name+(xs.ownership.org_unit?' · '+xs.ownership.org_unit:'');own.title=T('DOMAIN_ROLE_MAP 상수로 연결했다. 도메인과 역할을 잇는 원장 컬럼은 없다.')}
  else own.textContent=T('소관 미확인');
  ap(line,own,' · ',el('span','units',T('단위 범례')+': '+T('금액은 억원, 비율은 %, 변동은 %p 로 적는다')));ap(box,line);return box}
function openTable(name){drawer.open({title:name,tabs:[{label:'원장 표',build:r=>{const f=frame.frameOf(name);const c=cat(name);if(c)ap(r,el('div','meta',c.korean+' · '+c.product+' · '+c.grain));if(f)ap(r,table(f,{title:null}));else ap(r,note(T('원장 행 없음'),'warn'))}}]})}
function ledgerFold(id){const xs=(D.x_screens||{})[id];const led=((xs&&xs.ledgers)||[]).filter(l=>D.data&&D.data[l.table]);const n=led.length;if(!n)return null;
  const d=el('details','card fold ledgers'),sm=el('summary');ap(sm,el('h3',null,T('원장 표')),' ',el('span','meta',TF('{n}개',{n:n})));
  ap(d,sm,el('p','meta',T('이 화면의 원자료 원장이다. 값은 원문 그대로다.')));
  d.addEventListener('toggle',()=>{if(d.open&&!d.dataset.done){d.dataset.done='1';led.forEach(l=>guard(()=>ap(d,table(D.data[l.table],{title:l.korean||l.table,raw:true})),d,id+'#ledger:'+l.table))}});return d}
/* ---- drawer (spec 3.8) ---- */
const DR={ret:null};
const drawer={
  open(o){const a=$('#drawer');if(!a)return;a.innerHTML='';DR.ret=o.focusReturn||DOC.activeElement;
    const h=el('div','dhead');ap(h,el('h3',null,o.title||''));const x=button('×',{onClick:()=>drawer.close()});x.className='btn close';x.setAttribute('aria-label',T('드로어 닫기'));ap(h,x);
    const bar=el('div','tabs'),pane=el('div','dpane');bar.setAttribute('role','tablist');ap(a,h,bar,pane);
    const bs=(o.tabs||[]).map(t=>{const b=el('button','tab',T(t.label));b.type='button';b.setAttribute('role','tab');
      b.onclick=()=>{$$('button',bar).forEach(q=>{q.classList.toggle('on',q===b);q.setAttribute('aria-selected',q===b?'true':'false')});pane.innerHTML='';guard(()=>t.build(pane),pane,'drawer:'+t.label)};ap(bar,b);return b});
    a.hidden=false;DOC.body.classList.add('drawer-open');if(bs[o.active||0]){bs[o.active||0].onclick();bs[o.active||0].focus()}},
  close(){const a=$('#drawer');if(!a)return;a.hidden=true;a.innerHTML='';DOC.body.classList.remove('drawer-open');if(DR.ret&&DR.ret.focus&&DOC.contains(DR.ret))DR.ret.focus();DR.ret=null},
  row(f,k){const r=f&&f.rows[k];if(!r)return;drawer.open({title:(f.table||T('행 상세'))+' #'+(k+1),tabs:[{label:'원장 행',build:root=>{ap(root,el('div','meta',T('원장 값은 원문 그대로다')),rowDl(f,r),fkHops(f,r))}}]})},
  check(name){const f=frame.frameOf('val_check');if(!f)return;const i=frame.frameIdx(f);const k=f.rows.findIndex(r=>r[i.check_name]===name);if(k>=0)drawer.row(f,k)},
  lineage(ln){if(typeof ln==='string')ln=lineage.of(ln);
    if(!ln){drawer.open({title:T('계보'),tabs:[{label:'계보',build:r=>ap(r,note(T('계보 없음'),'warn'))}]});return}
    const fid=ln.figure_id||'';
    drawer.open({title:T('계보')+' · '+(ln.label||fid),tabs:[
      {label:'원장 행',build:r=>{ap(r,el('div','meta',fid+' · '+ln.table+(ln.column?' · '+ln.column:'')));const f=frame.frameOf(ln.table);
        if(!f){ap(r,note(T('원장 행 없음'),'warn'));return}const k=findRow(f,ln.pk||[]);
        if(k<0){ap(r,note(T('원장 행 없음')+(frame.truncated(f)?' · '+TF('표본 {n}/{N}',{n:f.shown,N:f.total}):''),'warn'));return}
        ap(r,rowDl(f,f.rows[k],ln.column),fkHops(f,f.rows[k]))}},
      {label:'2선',build:r=>{const f=frame.frameOf('val_check'),names=ln.check_names||[];if(!f||!names.length){ap(r,note(T('연결 검증 없음'),'neutral'));return}
        const i=frame.frameIdx(f),rows=f.rows.filter(x=>names.indexOf(x[i.check_name])>=0);
        ap(r,simpleTable(['검증 항목','상태','상세'],rows.map(x=>[x[i.check_name],badge(x[i.status],checkTone({check_name:x[i.check_name],status:x[i.status],is_identity:x[i.is_identity],blocks_approval:x[i.blocks_approval]})),text(x[i.detail])]),{}))}},
      {label:'3선',build:r=>{if(!ln.recalc_target){ap(r,note(T('3선 대상 아님')+(ln.in_scope===false?' · '+T('범위밖'):''),'neutral'));return}
        const g=D.x_gate||{},rc=g.recalc||{},row=(rc.rows||[]).find(x=>x.target===ln.recalc_target);if(!row){ap(r,note(T('미보고'),'not-run'));return}
        ap(r,badge(T(row.state),tone('recalc.state',row.state)),simpleTable(['항목','값'],[[T('재계산 대상'),row.target+' · '+(row.korean||'')],[T('보고값'),fmt.num(row.reported)],[T('재계산값'),row.recomputed==null?T('미보고'):fmt.num(row.recomputed)],[T('요청 ID'),(g.independent||{}).request_id||'-'],[T('응답 요청 ID'),rc.response_request_id||T('응답 없음')],['citation',row.citation||'-']],{}))}},
      {label:'근거',build:r=>{const a=ln.audit;if(!a){ap(r,note(T('감사 원장 행 없음'),'neutral'));return}
        ap(r,simpleTable(['항목','값'],[[T('수치 ID'),fid],[T('수치 라벨'),ln.label||'-'],[T('코드 모듈'),a.code_module||'-'],[T('코드 함수'),a.code_function||'-'],['citation',a.citation||'-']],{}))}},
      {label:'추이',build:r=>{const x=D.x_trend;if(!x||x.single_period||!(x.n_periods>1)){ap(r,note(T('추이 원장에 기간이 하나뿐이다'),'neutral'));return}
        const fl=(x.flags||[]).find(f=>f.metric===ln.recalc_target||f.label===ln.label);if(!fl){ap(r,note(T('기록 없음'),'neutral'));return}
        ap(r,simpleTable(['항목','값'],[[T('최신'),fmt.num(fl.latest)],[T('전기 대비'),fmt.num(fl.qoq)],[T('하한선'),fmt.num(fl.floor)],[T('방향'),fl.direction],[T('추이 상태'),fl.trend_state],[T('연속 위반'),fmt.num(fl.consecutive_breaches)]],{}))}}]})},
  gate(){const x=D.x_gate;drawer.open({title:T('게이트 상태'),tabs:[
    {label:'게이트 상태',build:r=>{if(!x){ap(r,note(T('게이트 객체 없음'),'blocked'));return}const i=x.independent||{},s=x.self||{},o=x.overall||{},rsp=i.response||null;
      ap(r,badge(T('전체 판정')+' '+(o.status||'-'),o.tone||'blocked'),' ',badge(o.blocks_approval?T('결재 차단'):T('결재 차단 아님'),o.blocks_approval?'blocked':'good'));
      ap(r,el('p','note',T('게이트는 fail-closed 다. 응답이 없으면 응답대기이며 결재할 수 없다.')));
      ap(r,simpleTable(['항목','값'],[[T('게이트 상태'),i.status||'-'],[T('종류'),i.kind||'-'],[T('요청 ID'),i.request_id||'-'],['run_id',i.run_id||'-'],[T('요청 대상'),i.requested_to||'-'],[T('브랜치'),i.branch||'-'],[T('헤드라인 지문'),i.headline_digest||'-'],[T('재계산 대상 수'),i.n_recalc_targets],[T('자체검증 FAIL 수'),i.n_self_fail],[T('자체검증 WARN 수'),i.n_self_warn],[T('발신'),dispatchWord(i)],[T('발신 디렉터리'),i.dispatch_dir||'-'],['reason',text(i.reason)],[T('응답'),rsp?rsp.verdict+' · '+rsp.request_id+' · '+rsp.run_id:T('응답 없음')],[T('검증자'),rsp?rsp.validated_by:'-'],[T('검증 시각'),rsp?rsp.validated_at:'-']],{}));
      ap(r,el('h4',null,T('자체검증 (2선)')),simpleTable(['항목','값'],[['PASS',s.pass],['WARN',s.warn],['FAIL',s.fail],[T('규제미달'),s.blocks],[T('미실행'),s.not_run],[T('항등식 제외'),s.identity_excluded]],{}));
      const bc=s.blocking_checks||[];ap(r,el('h4',null,T('차단 검증')));
      if(!bc.length)ap(r,el('div','meta',T('차단 검증 없음')));else ap(r,simpleTable(['검증 항목','상태','상세'],bc.map(c=>[c.check_name,badge(c.status,'bad'),text(c.detail)]),{}))}},
    {label:'보류 목록',build:r=>{const a=(x&&x.approvals)||{},h=a.holds||[],sv=a.segregation_violations||0;
      ap(r,badge(T('직무분리 위반')+' '+fmt.num(sv),sv>0?'bad':'good'),' ',badge(T('결정 분포')+' '+['대기','승인','반려'].map(k=>k+' '+fmt.num(a[k])).join(' · '),a['반려']>0?'bad':a['대기']>0?'blocked':'good'));
      if(!h.length){ap(r,note(T('없음'),'neutral'));return}
      ap(r,simpleTable(['보류 종류','보류 사유','건수','대상 유형'],h.map(k=>[badge(k.reason_kind,tone('hold.reason_kind',k.reason_kind)),text(k.reason_text),k.n,(k.subject_types||[]).join(', ')]),{}))}},
    {label:'제출 현황',build:r=>{const s=(x&&x.submission)||{};ap(r,simpleTable(['항목','값'],['draft','reviewed','approved','submitted','total'].map(k=>[k,s[k]]),{}));
      const bf=s.by_form||[];if(bf.length)ap(r,el('h4',null,T('서식별')),simpleTable(['form_id','상태','서식검증 실패','결재','직무분리 위반'],bf.map(f=>[f.form_id,badge(f.status,tone('reg_submission.status',f.status)),f.n_failed_checks,f.decision||'-',f.segregation_ok===false?glyph('bad'):glyph('good')]),{}))}},
    {label:'관련 화면',build:r=>{const u=el('div','links');['validation','decision-queue','approval-pack','capital-verdict'].filter(id=>SECTS[id]).forEach(id=>ap(u,button(screenTitle(id),{onClick:()=>{drawer.close();go(id)}})));ap(r,u)}}]})},
  shortcuts(){drawer.open({title:T('단축키 안내'),tabs:[{label:'단축키',build:r=>{
    ap(r,dotlist(['팔레트 열기 / 또는 Ctrl+K · 게이트 스트립 Alt+G · 단축키 안내 ?','그룹 안 이동 [ 와 ]','두 글자 단축키: 그룹 글자 다음 화면 글자','방향키로 이동, Enter 로 열기, Escape 로 닫기'].map(k=>({text:T(k),tone:'neutral'}))));
    const rows=[];NAV.groups.forEach(g=>{rows.push([g.chord,LANG==='ko'?g.label_ko:g.label_en]);NAV.screens.filter(s=>s.slug===g.slug).forEach(s=>rows.push([s.chord,screenTitle(s.id)]))});
    ap(r,simpleTable(['단축키','화면'],rows,{}))}}]})}
};
function rowDl(f,r,hl){const dl=el('dl','rowdl');f.columns.forEach((c,i)=>{const lab=frame.colLabel(f,i),dt=el('dt',null,lab);if(lab!==c)dt.title=c;const dd=el('dd',(typeof r[i]==='number'?'num':'')+(c===hl?' hl':''),cell(r[i]));ap(dl,dt,dd)});return dl}
function findRow(f,pk){const i=frame.frameIdx(f);return f.rows.findIndex(r=>pk.every(p=>{if(i[p.column]==null)return false;const v=p.value==null?D.meta.asof:p.value;return String(r[i[p.column]])===String(v)}))}
function fkHops(f,row){const fks=fkOf(f.table);if(!fks.length)return null;const box=el('div','fkhops');ap(box,el('div','lab',T('외래키 이동')));const i=frame.frameIdx(f);
  fks.forEach(fk=>{const cols=fk.column.split(', '),refs=fk.ref_column.split(', '),vals=cols.map(c=>row[i[c]]);
    const miss=rf=>drawer.open({title:fk.ref_table,tabs:[{label:'원장 행',build:r=>ap(r,note(T('참조 행 없음')+(rf&&frame.truncated(rf)?' · '+TF('표본 {n}/{N}',{n:rf.shown,N:rf.total}):''),'warn'))}]});
    ap(box,button(T('참조 행 열기')+' · '+fk.ref_table+'.'+fk.ref_column+' = '+vals.map(cell).join(', '),{onClick:()=>{const rf=frame.frameOf(fk.ref_table);if(!rf){miss(null);return}
      const ri=frame.frameIdx(rf),k=rf.rows.findIndex(x=>refs.every((c,j)=>String(x[ri[c]])===String(vals[j])));if(k<0)miss(rf);else drawer.row(rf,k)}}))});return box}
/* ---- router (spec 3.7) ---- */
const SECTS={},NODES=[];
function dec(s){try{return decodeURIComponent(s)}catch(e){return s}}
function parseHash(){const m=/^#\/([^\/?]*)\/?([^?]*)(?:\?(.*))?$/.exec(location.hash||'');const out={id:null,slug:null,params:{}};if(!m)return out;out.slug=dec(m[1]);out.id=m[2]?dec(m[2]):null;
  if(m[3])m[3].split('&').forEach(kv=>{if(!kv)return;const i=kv.indexOf('=');out.params[dec(i<0?kv:kv.slice(0,i))]=i<0?'':dec(kv.slice(i+1))});return out}
function link(id,params){const s=SCREENS[id];const q=Object.keys(params||{}).filter(k=>params[k]!=null&&params[k]!=='').map(k=>encodeURIComponent(k)+'='+encodeURIComponent(params[k])).join('&');return '#/'+(s?s.slug:'')+'/'+id+(q?'?'+q:'')}
function writeHash(id,params,replace){const h=link(id,params);try{history[replace?'replaceState':'pushState'](null,'',location.pathname+location.search+h)}catch(e){location.hash=h}}
function route(){return {id:CUR.id,params:Object.assign({},CUR.params)}}
function resolveLegacy(lab){return NAV.aliases[lab]||NAV.labels[lab]||null}
function runParams(p){return Object.assign({inst:D.meta.institution_code,asof:D.meta.asof},p||{})}
function go(id,params,o){o=o||{};if(!SECTS[id]){const alt=resolveLegacy(id);if(alt&&SECTS[alt])id=alt}
  const p=runParams(params),change=id!==CUR.id;writeHash(id,p,o.replace||!change);activate(id,p,{scroll:change})}
function screenTitle(id){const m=SCREENS[id];if(!m)return id;return LANG==='ko'?m.title_ko:m.title_en}
function navText(label,titleEn){return LANG==='ko'?(NAVDISP[label]||label):(titleEn||T(label))}
function crumb(id){const m=SCREENS[id]||{};const c=el('div','crumb');const g=GROUPS[m.group];const parts=[g?(LANG==='ko'?g.label_ko:g.label_en):(m.group||'')];if(m.sub)parts.push(navText(m.sub));parts.push(screenTitle(id));
  ap(c,el('span','lab',T('경로')+': '),parts.join(' > '));if(m.chord)ap(c,' · ',el('kbd',null,m.chord));return c}
function activate(id,params,o){o=o||{};let notice=null;params=params||{};
  if(!SECTS[id]){notice=T('알 수 없는 화면 주소다. 종합보고서로 이동했다.');id=TABS[0][2];writeHash(id,params,true)}
  if(params.inst&&INSTS[params.inst]&&params.inst!==D.meta.institution_code)setInst(params.inst,true);
  if(params.asof&&RUNS[params.asof]&&params.asof!==D.meta.asof)setRun(params.asof,true);
  const s=SECTS[id];CUR.id=id;CUR.params=params;
  Object.keys(SECTS).forEach(k=>{const x=SECTS[k],on=k===id;x.section.classList.toggle('on',on);x.button.classList.toggle('on',on);if(on)x.button.setAttribute('aria-current','page');else x.button.removeAttribute('aria-current')});
  expandTo(s.node);
  if(!s.section.dataset.done)buildSection(s);
  if(notice)s.section.insertBefore(note(notice,'warn'),s.section.firstChild);
  if(params.tab&&s.tabsApi)s.tabsApi.show(params.tab,false);
  if(params.fig){const ln=lineage.of(params.fig);if(ln)drawer.lineage(ln)}
  DOC.title='RYNTA · '+screenTitle(id)+' · '+(D.meta.institution_code||'-')+' · '+(D.meta.asof||'-');
  if(o.scroll)W.scrollTo({top:0});
  if(s.button.scrollIntoView)s.button.scrollIntoView({block:'nearest'})}
function ctxFor(id){const m=SCREENS[id]||{id:id};return {D:D,RUNS:RUNS,INSTS:INSTS,id:id,meta:Object.assign({ledgers:m.tables||[]},m),params:Object.assign({},CUR.params),T:T,TF:TF,text:text,fmt:fmt,frame:frame,lineage:lineage,tone:tone,glyph:glyph,gate:D.x_gate||null,state:STATE,RY:W.RY||null,LANG:LANG,ui:NG.ui,go:go,link:link,killedFor:killedFor,drawer:drawer}}
function buildSection(s){const id=s.id,sec=s.section;sec.innerHTML='';sec.dataset.done='1';CUR.missing=false;
  const m=SCREENS[id]||{},def=REG.get(id);
  ap(sec,crumb(id),el('h2',null,screenTitle(id)),gateBadge(id),provHeader(id));
  if(m.explanatory){const rb=el('div','ribbon explanatory');ap(rb,glyph('explanatory'),' '+T('설명용 산술 · 승인·제출값 아님'));sec.classList.add('explanatory');ap(sec,rb)}
  if(!def){CUR.missing=true;const e=new Error('module missing: '+id+' ('+(m.module||m.slug||'?')+')');report(id,e,'warn');ap(sec,errorCard(e));return}
  const ctx=ctxFor(id);
  if(def.summary)guard(()=>{const r=def.summary(ctx);if(r&&r.text){const a=el('div','aisum'+(r.tone?' '+r.tone:''));if(r.tone)a.dataset.tone=r.tone;a.title=T('결정론적 규칙 출력 · 같은 데이터면 같은 문장 · LLM 호출 없음');ap(a,el('span','aisum-tag',T('요약')),' ',glyph(r.tone||'neutral'),' ',text(r.text));ap(sec,a)}},sec,id+'#summary');
  const body=el('div','body');ap(sec,body);
  guard(()=>def.build(body,ctx),body,id);
  s.tabsApi=(def.tabs&&def.tabs.length)?tabs(body,def.tabs,CUR.params.tab):null;
  ap(sec,ledgerFold(id))}
/* ---- nav (spec 3.3) ---- */
let NAVST={},FILTER='';
function isOpen(n){return n.header.getAttribute('aria-expanded')==='true'}
function ancestorsOpen(n){return !n.parent||(ancestorsOpen(n.parent)&&isOpen(n.parent))}
function refreshNav(){NODES.forEach(n=>{if(FILTER){n.header.hidden=false;n.leaves.forEach(l=>{l.hidden=!leafMatch(l)});return}
  const show=ancestorsOpen(n)&&isOpen(n);n.header.hidden=!ancestorsOpen(n);n.leaves.forEach(l=>{l.hidden=!show})})}
function leafMatch(b){const s=SECTS[b.dataset.id]||{};return [b.dataset.ko,b.textContent,s.title_en||'',b.dataset.chord||''].join(' ').toLowerCase().indexOf(FILTER)>=0}
function setExpanded(n,on,persist){n.header.setAttribute('aria-expanded',on?'true':'false');refreshNav();if(persist){NAVST[n.key]=on;try{localStorage.setItem(NAV_KEY,JSON.stringify(NAVST))}catch(e){}}}
function expandTo(n){let x=n;while(x){if(!isOpen(x))setExpanded(x,true,false);x=x.parent}}
function buildNav(){const nav=$('nav'),main=$('main');if(!nav||!main)return;const byLabel={};TABS.forEach(t=>{byLabel[t[0]]=t});let idx=0;
  const filt=input({});filt.id='navfilter';filt.oninput=()=>{FILTER=filt.value.trim().toLowerCase();refreshNav()};ap(nav,filt);
  try{NAVST=JSON.parse(localStorage.getItem(NAV_KEY)||'{}')||{}}catch(e){NAVST={}}
  function leaf(label,depth,node){const t=byLabel[label];if(!t)return;const id=t[2],m=SCREENS[id]||{};
    const b=el('button','lvl'+depth);b.type='button';b.dataset.ko=label;b.dataset.id=id;if(m.chord)b.dataset.chord=m.chord;b.onclick=()=>go(id);
    const sec=el('section');sec.id='tab'+(idx++);sec.dataset.screen=id;ap(nav,b);ap(main,sec);node.leaves.push(b);
    SECTS[id]={id:id,section:sec,button:b,node:node,label:label,title_en:t[1],tabsApi:null}}
  function group(name,items,depth,parent){const h=el('div','navgroup'+(depth?' sub lvl'+depth:''));h.setAttribute('role','button');h.tabIndex=0;h.dataset.ko=name;
    const node={key:(parent?parent.key+'/':'')+name,header:h,leaves:[],parent:parent,name:name,depth:depth};NODES.push(node);
    h.setAttribute('aria-expanded',NAVST[node.key]===true?'true':'false');
    const tog=()=>setExpanded(node,!isOpen(node),true);h.onclick=tog;h.onkeydown=e=>{if(e.key==='Enter'||e.key===' '){e.preventDefault();tog()}};ap(nav,h);
    items.forEach(it=>{if(typeof it==='string')leaf(it,depth+1,node);else{const sub=it[0],kids=it[1];if(byLabel[sub]){leaf(sub,depth+1,node);kids.forEach(k=>leaf(k,depth+2,node))}else group(sub,kids,depth+1,node)}})}
  NAVGROUPS.forEach(g=>group(g[0],g[1],0,null));
  nav.onkeydown=e=>{const items=$$('[role=button],button',nav).filter(x=>!x.hidden);const k=items.indexOf(e.target);if(k<0)return;
    const mv=j=>{e.preventDefault();items[Math.max(0,Math.min(items.length-1,j))].focus()};
    if(e.key==='ArrowDown')mv(k+1);else if(e.key==='ArrowUp')mv(k-1);else if(e.key==='Home')mv(0);else if(e.key==='End')mv(items.length-1);
    else if(e.key==='ArrowRight'||e.key==='ArrowLeft'){const n=NODES.find(x=>x.header===e.target);if(n){e.preventDefault();setExpanded(n,e.key==='ArrowRight',true)}
      else if(e.key==='ArrowLeft'){const s=SECTS[e.target.dataset.id];if(s&&s.node){e.preventDefault();s.node.header.focus()}}}};
  relabelNav();refreshNav()}
function relabelNav(){NODES.forEach(n=>{const g=n.depth===0&&GROUPS[n.name];n.header.textContent=g?(LANG==='ko'?(NAVDISP[n.name]||n.name):g.label_en):navText(n.name);n.header.title=T(isOpen(n)?'그룹 접기':'그룹 펼치기')});
  Object.keys(SECTS).forEach(id=>{const s=SECTS[id],b=s.button;b.textContent=navText(s.label,s.title_en);b.title=(b.dataset.chord?b.dataset.chord+' · ':'')+(LANG==='ko'?s.title_en:s.label)});
  const nf=$('#navfilter');if(nf){nf.placeholder=T('화면 이름·영문명·단축키로 걸러낸다');nf.setAttribute('aria-label',T('화면 필터'))}}
/* ---- palette and chords ---- */
const PAL={index:null,open:false,sel:0,items:[],ret:null};
function palIndex(){if(PAL.index)return PAL.index;const ix=[];
  Object.keys(SECTS).forEach(id=>{const s=SECTS[id],m=SCREENS[id]||{},lg=(m.legacy||[]).join(' ');ix.push({kind:'화면',label:LANG==='ko'?s.label:s.title_en,sub:[LANG==='ko'?s.title_en:s.label,lg,m.chord||''].filter(Boolean).join(' · '),hay:[s.label,s.title_en,lg,m.chord||'',id].join(' ').toLowerCase(),chord:m.chord,run:()=>go(id)})});
  (D.catalog||[]).forEach(c=>ix.push({kind:'원장',label:c.name,sub:c.korean+' · '+c.product,hay:(c.name+' '+c.korean+' '+c.product).toLowerCase(),run:()=>openTable(c.name)}));
  const vc=frame.frameOf('val_check');if(vc){const i=frame.frameIdx(vc);vc.rows.forEach((r,k)=>ix.push({kind:'검증 항목',label:String(r[i.check_name]),sub:r[i.status]+' · '+(r[i.domain]||''),hay:String(r[i.check_name]).toLowerCase(),run:()=>drawer.row(vc,k)}))}
  const fg=(D.x_lineage&&D.x_lineage.figures)||{};Object.keys(fg).forEach(f=>ix.push({kind:'수치 ID',label:f,sub:fg[f].label||'',hay:(f+' '+(fg[f].label||'')).toLowerCase(),run:()=>drawer.lineage(lineage.of(f))}));
  (D.forms||[]).forEach(f=>ix.push({kind:'서식',label:f.form_no+' '+f.form_id,sub:f.form_name||'',hay:(f.form_no+' '+f.form_id+' '+f.form_name).toLowerCase(),run:()=>{const id=Object.keys(SECTS).find(x=>(SCREENS[x].tables||[]).indexOf('reg_submission')>=0&&SCREENS[x].slug==='reports');if(id)go(id,{sel:f.form_id})}}));
  Object.keys(RUNS).sort().forEach(a=>ix.push({kind:'명령',label:T('기준일 전환')+' '+a,sub:'',hay:('asof '+T('기준일 전환')+' '+a).toLowerCase(),run:()=>setRun(a)}));
  Object.keys(INSTS).forEach(c=>ix.push({kind:'명령',label:T('기관 전환')+' '+c,sub:'',hay:('inst '+T('기관 전환')+' '+c).toLowerCase(),run:()=>setInst(c)}));
  PAL.index=ix;return ix}
function palOpen(){const p=$('#palette');if(!p)return;p.innerHTML='';PAL.ret=DOC.activeElement;
  const inp=input({placeholder:T('화면·테이블·검증·수치·서식 검색'),aria:T('명령 팔레트')}),ul=el('ul','results');ul.setAttribute('role','listbox');
  ap(p,inp,ul,el('div','meta',T('방향키로 이동, Enter 로 열기, Escape 로 닫기')));p.hidden=false;PAL.open=true;
  const draw=()=>{const q=inp.value.trim().toLowerCase(),toks=q.split(/\s+/).filter(Boolean);let items=palIndex().filter(it=>toks.every(t=>it.hay.indexOf(t)>=0));
    if(/^[a-z]{2}$/.test(q))items=items.filter(it=>it.chord===q).concat(items.filter(it=>it.chord!==q));
    items=items.slice(0,30);PAL.items=items;PAL.sel=0;ul.innerHTML='';if(!items.length)ap(ul,el('li','meta',T('결과 없음')));
    items.forEach((it,k)=>{const li=el('li','pitem'+(k===0?' on':''));li.setAttribute('role','option');ap(li,el('span','kind',T(it.kind)),' ',el('span','lab',it.label),it.sub?el('span','meta',' '+it.sub):null);li.onclick=()=>{palClose();it.run()};ap(ul,li)})};
  inp.oninput=draw;inp.onkeydown=e=>{const n=PAL.items.length;
    if(e.key==='ArrowDown'||e.key==='ArrowUp'){e.preventDefault();if(!n)return;PAL.sel=(PAL.sel+(e.key==='ArrowDown'?1:n-1))%n;$$('li.pitem',ul).forEach((li,k)=>li.classList.toggle('on',k===PAL.sel))}
    else if(e.key==='Enter'){const it=PAL.items[PAL.sel];if(it){palClose();it.run()}}else if(e.key==='Escape'){e.stopPropagation();palClose()}};
  draw();inp.focus()}
function palClose(){const p=$('#palette');if(!p)return;p.hidden=true;p.innerHTML='';PAL.open=false;if(PAL.ret&&PAL.ret.focus&&DOC.contains(PAL.ret))PAL.ret.focus();PAL.ret=null}
let PEND=null,PENDT=null;
function inField(t){const n=((t&&t.tagName)||'').toLowerCase();return n==='input'||n==='select'||n==='textarea'||!!(t&&t.isContentEditable)}
function step(dir){const m=SCREENS[CUR.id];if(!m)return;const ids=TABS.map(t=>t[2]).filter(id=>SCREENS[id]&&SCREENS[id].slug===m.slug&&SECTS[id]);const k=ids.indexOf(CUR.id);if(k<0)return;go(ids[(k+dir+ids.length)%ids.length])}
function onKey(e){const k=e.key;
  if(k==='Escape'){if(PAL.open){palClose();return}const dr=$('#drawer');if(dr&&!dr.hidden){drawer.close();return}PEND=null;return}
  if(e.altKey&&k.toLowerCase()==='g'){e.preventDefault();const g=$('#gatestrip button')||$('#gatestrip');if(g)g.focus();return}
  if((e.ctrlKey||e.metaKey)&&k.toLowerCase()==='k'){e.preventDefault();if(PAL.open)palClose();else palOpen();return}
  if(e.ctrlKey||e.metaKey||e.altKey||PAL.open||inField(e.target))return;
  if(k==='/'){e.preventDefault();palOpen();return}
  if(k==='?'){e.preventDefault();drawer.shortcuts();return}
  if(k==='['||k===']'){e.preventDefault();step(k===']'?1:-1);return}
  if(/^[a-z]$/.test(k)){if(PEND){const two=PEND+k;PEND=null;clearTimeout(PENDT);const id=Object.keys(SCREENS).find(x=>SCREENS[x].chord===two);if(id&&SECTS[id]){e.preventDefault();go(id)}return}
    if(NAV.groups.some(g=>g.chord===k)){PEND=k;clearTimeout(PENDT);PENDT=setTimeout(()=>{PEND=null},2000)}}}
/* ---- kill guard (spec 3.1, two-field rule on engage and release) ---- */
const KILL={sync:null,mode:'engage'};
function killedFor(domain){return !!STATE.killed&&(STATE.killScope==='전사'||domain===STATE.killScope)}
function paintKill(){const kb=$('.kill');if(!kb)return;kb.classList.toggle('on',!!STATE.killed);kb.setAttribute('aria-pressed',STATE.killed?'true':'false');
  kb.textContent=STATE.killed?'Kill Switch 해제'+(LANG==='ko'?'':' · '+T('해제'))+(STATE.killScope==='전사'?'':' · '+STATE.killScope):T(kb.dataset.ko||'Kill Switch (화면 가드)');
  kb.title=STATE.killed?TF('범위: {scope}',{scope:STATE.killScope==='전사'?T('전사'):STATE.killScope}):'';if(KILL.sync)KILL.sync()}
function wireKill(){const kb=$('.kill'),bar=$('.killbar'),rin=$('#killreason'),cin=$('#killconfirm'),ksc=$('#killscope'),go=$('.killgo'),no=$('.killno');if(!kb||!bar||!rin||!cin||!go)return;
  const doms=['전사'].concat(Array.from(new Set(Object.values(D.view_meta||{}).map(v=>v.domain))).sort());
  if(ksc){ksc.innerHTML='';doms.forEach(d=>{const o=el('option',null,d==='전사'?T(d):d);o.value=d;o.dataset.ko=d;ap(ksc,o)})}
  const valid=()=>!!((rin.value||'').trim()&&(cin.value||'').trim());
  const sync=()=>{const rel=KILL.mode==='release';go.disabled=!valid();go.textContent=T(rel?'해제':'정지');
    const lab=$('label[for=killreason]');if(lab)lab.textContent=T(rel?'해제 사유 (필수)':'비상정지 사유 (필수)');if(ksc)ksc.disabled=rel;
    go.title=T(rel?'사유와 2차 확인자를 모두 채워야 해제할 수 있다':'사유와 2차 확인자를 모두 채워야 정지할 수 있다');
    if(ksc)$$('option',ksc).forEach(o=>{o.textContent=o.dataset.ko==='전사'?T(o.dataset.ko):o.dataset.ko})};
  const openBar=m=>{KILL.mode=m;bar.hidden=false;rin.value='';cin.value='';if(ksc&&m==='engage')ksc.value=STATE.killScope||'전사';sync();rin.focus()};
  const cancel=()=>{bar.hidden=true;KILL.mode='engage';sync();kb.focus()};
  const fire=()=>{if(!valid())return;const reason=rin.value.trim(),conf=cin.value.trim();
    if(KILL.mode==='engage'){STATE.killed=true;STATE.killScope=(ksc&&ksc.value)||'전사';STATE.killReason=reason;STATE.killConfirm=conf}
    else{STATE.killed=false;STATE.killReason='';STATE.killConfirm=''}
    bar.hidden=true;KILL.mode='engage';paintKill();repaintAll()};
  kb.onclick=()=>{if(!bar.hidden){cancel();return}openBar(STATE.killed?'release':'engage')};
  go.onclick=fire;if(no)no.onclick=cancel;
  [rin,cin].forEach(i=>{i.oninput=sync;i.onkeydown=e=>{if(e.key==='Enter'){e.preventDefault();fire()}if(e.key==='Escape'){e.stopPropagation();cancel()}}});
  KILL.sync=sync;paintKill()}
/* ---- i18n runtime ---- */
function paintStatic(){DOC.documentElement.lang=LANG;
  $$('[data-i18n]').forEach(e=>{if(e.dataset.ko===undefined)e.dataset.ko=e.textContent.trim();e.textContent=T(e.dataset.ko);
    if(e.title||e.dataset.koTitle!==undefined){if(e.dataset.koTitle===undefined)e.dataset.koTitle=e.title;e.title=T(e.dataset.koTitle)}});
  const nv=$('nav');if(nv)nv.setAttribute('aria-label',T('메뉴'));const dr=$('#drawer');if(dr)dr.setAttribute('aria-label',T('상세'));const pl=$('#palette');if(pl)pl.setAttribute('aria-label',T('명령 팔레트'));
  const lb=$('#langbtn');if(lb){lb.textContent=LANG==='en'?'한국어':'English';lb.title=T('언어 전환');lb.setAttribute('aria-label',lb.title)}
  paintThemeButton()}
function setLang(next){if(LANGS.indexOf(next)<0)return;LANG=next;try{localStorage.setItem(LANG_KEY,next)}catch(e){}
  PAL.index=null;paintStatic();paintKill();relabelNav();paintChips();paintGate();repaintAll()}
/* ---- theme ---- */
function systemDark(){return !!(W.matchMedia&&W.matchMedia('(prefers-color-scheme: dark)').matches)}
function currentTheme(){return DOC.documentElement.getAttribute('data-theme')||(systemDark()?'dark':'light')}
function paintThemeButton(){const b=$('#themebtn');if(!b)return;const t=currentTheme();b.setAttribute('aria-pressed',t==='dark'?'true':'false');b.setAttribute('aria-label',T('화면 밝기 전환')+' ('+t+')')}
function wireTheme(){const b=$('#themebtn');if(!b)return;
  b.onclick=()=>{const next=currentTheme()==='dark'?'light':'dark';DOC.documentElement.setAttribute('data-theme',next);try{localStorage.setItem(THEME_KEY,next)}catch(e){}paintThemeButton()};
  if(W.matchMedia){const mq=W.matchMedia('(prefers-color-scheme: dark)');const f=()=>{let st=null;try{st=localStorage.getItem(THEME_KEY)}catch(e){}if(!st)paintThemeButton()};if(mq.addEventListener)mq.addEventListener('change',f);else if(mq.addListener)mq.addListener(f)}
  paintThemeButton()}
/* ---- run switching (embedded runs only; never run_pipeline) ---- */
function instName(row){if(!row)return '';const a=LANG==='ko'?row.name_ko:row.name_en;return a||row.name_en||row.name_ko||row.institution_code||''}
function institutionRows(){const f=D.institution&&D.institution.tables&&D.institution.tables.inst_master;const rows=frame.frameObjects(f);
  const out=rows.length?rows:Object.keys(INSTS).map(c=>({institution_code:c}));out.forEach(r=>{r.loaded=Object.prototype.hasOwnProperty.call(INSTS,r.institution_code)});return out}
function paintChips(){const set=(s,t)=>{const e=$(s);if(e)e.textContent=t};const m=D.meta||{};
  set('#chip-run',m.run_id||'-');set('#chip-digest',T('지문')+' '+String(m.digest||'').slice(0,12));set('#chip-seed',T('시드')+' '+String(m.seed));
  set('#chip-rows',TF('테이블 {n}장 · {rows}행',{n:m.n_tables,rows:m.n_rows}));
  const ir=(D.institution&&D.institution.master_row)||{};set('#chip-inst',[ir.region,ir.institution_type,ir.data_origin].filter(x=>x!=null&&x!=='').join(' · '));
  const isel=$('#instsel');if(isel)$$('option',isel).forEach(o=>{const nm=instName({name_ko:o.dataset.nameKo||'',name_en:o.dataset.nameEn||'',institution_code:o.value});o.textContent=(nm&&nm!==o.value)?nm+' · '+o.value:o.value});
  const fa=$('#foot-asof');if(fa)fa.textContent=m.asof||'';const fs=$('#foot-seed');if(fs)fs.textContent=String(m.seed);
  const fw=$('#foot-write');if(fw){const f=frame.frameOf('agent_registry'),lab=fw.querySelector('[data-i18n]');let val='-';
    if(f){const i=frame.frameIdx(f);if(i.write_allowed!=null){const n=f.rows.filter(r=>r[i.write_allowed]===true||r[i.write_allowed]===1).length;val=n+'/'+f.shown+(f.shown<f.total?' ('+TF('표본 {n}/{N}',{n:f.shown,N:f.total})+')':'')}}
    fw.textContent='';if(lab)ap(fw,lab,' ');ap(fw,val)}
  if(CUR.id)DOC.title='RYNTA · '+screenTitle(CUR.id)+' · '+(m.institution_code||'-')+' · '+(m.asof||'-')}
function applyRun(next,quiet){stashRun();const kept=BYRUN[runKey(next)]||freshState();Object.keys(STATE).forEach(k=>{delete STATE[k]});Object.assign(STATE,kept);
  D=next;resetIdx();paintChips();paintKill();paintGate();
  Object.keys(SECTS).forEach(k=>{SECTS[k].section.dataset.done='';SECTS[k].section.innerHTML='';SECTS[k].tabsApi=null});
  CUR.params=Object.assign({},CUR.params,{inst:D.meta.institution_code,asof:D.meta.asof});
  if(!quiet&&CUR.id){writeHash(CUR.id,CUR.params,true);activate(CUR.id,CUR.params,{})}}
function fillAsof(want){const a=$('#asofsel');if(!a)return;a.innerHTML='';Object.keys(RUNS).sort().forEach(x=>{const o=el('option',null,x);o.value=x;ap(a,o)});a.value=want}
function setRun(a,quiet){if(!RUNS[a]||a===D.meta.asof)return;const s=$('#asofsel');if(s)s.value=a;applyRun(RUNS[a],quiet)}
function setInst(code,quiet){const runs=INSTS[code];if(!runs||code===D.meta.institution_code)return;RUNS=runs;
  const asofs=Object.keys(RUNS).sort(),want=asofs.indexOf(D.meta.asof)>=0?D.meta.asof:asofs[asofs.length-1];
  fillAsof(want);const s=$('#instsel');if(s)s.value=code;applyRun(RUNS[want],quiet)}
function repaintAll(){Object.keys(SECTS).forEach(k=>{const s=SECTS[k].section;s.dataset.done='';if(!s.classList.contains('on'))s.innerHTML='';SECTS[k].tabsApi=null});if(CUR.id)activate(CUR.id,CUR.params,{})}
/* ---- boot ---- */
function wireTopbar(){const tb=$('.topbar');if(!tb)return;const set=()=>DOC.documentElement.style.setProperty('--topbar-h',Math.round(tb.getBoundingClientRect().height)+'px');
  if(W.ResizeObserver)new ResizeObserver(set).observe(tb);else W.addEventListener('resize',set);set()}
function onHash(initial){const r=parseHash();let id=r.id;if(id&&!SECTS[id]){const alt=resolveLegacy(id);if(alt)id=alt}
  if(!id){const p=runParams({});id=TABS[0][2];writeHash(id,p,true);activate(id,p,{});return}
  if(id===CUR.id&&!initial){const p=r.params;CUR.params=p;const s=SECTS[id];if(p.tab&&s&&s.tabsApi)s.tabsApi.show(p.tab,false);if(p.fig){const ln=lineage.of(p.fig);if(ln)drawer.lineage(ln)}return}
  activate(id,r.params,{scroll:!initial})}
function boot(){let stored=null;try{stored=localStorage.getItem(LANG_KEY)}catch(e){}if(stored&&LANGS.indexOf(stored)>=0)LANG=stored;
  const lb=$('#langbtn');if(lb)lb.onclick=()=>setLang(LANG==='en'?'ko':'en');
  wireTheme();buildNav();
  const isel=$('#instsel');if(isel){isel.innerHTML='';institutionRows().filter(r=>r.loaded).forEach(r=>{const o=el('option',null,r.institution_code);o.value=r.institution_code;if(r.name_ko!=null)o.dataset.nameKo=r.name_ko;if(r.name_en!=null)o.dataset.nameEn=r.name_en;ap(isel,o)});isel.value=D.meta.institution_code;isel.onchange=()=>setInst(isel.value)}
  fillAsof(D.meta.asof);const asel=$('#asofsel');if(asel)asel.onchange=()=>setRun(asel.value);
  wireKill();paintStatic();paintKill();relabelNav();paintChips();paintGate();wireTopbar();
  DOC.addEventListener('keydown',onKey);W.addEventListener('hashchange',()=>onHash(false));
  /* first activation waits for the screens/*.js blocks that follow this one */
  const start=()=>onHash(true);if(DOC.readyState==='loading')DOC.addEventListener('DOMContentLoaded',start);else start()}
const NG={screen:screen,registry:REG,T:T,TF:TF,text:text,fmt:fmt,frame:frame,lineage:lineage,tone:tone,glyph:glyph,glyphChar:glyphChar,checkTone:checkTone,gateBadge:gateBadge,provHeader:provHeader,state:STATE,killedFor:killedFor,
  go:go,route:route,link:link,resolveLegacy:resolveLegacy,drawer:drawer,palette:{open:palOpen,close:palClose},openTable:openTable,cat:cat,fkOf:fkOf,
  ui:{section:section,kpi:kpi,kpiRow:kpiRow,table:table,simpleTable:simpleTable,badge:badge,pill:pill,note:note,truncBadge:truncBadge,srcMeta:srcMeta,meter:meter,dotlist:dotlist,chips:chips,select:select,input:input,button:button,explanatory:explanatory,errorCard:errorCard,tabs:tabs,el:el,ap:ap,productChip:productChip},
  runKey:runKey,setInst:setInst,setRun:setRun,applyRun:applyRun,setLang:setLang,wireTheme:wireTheme,repaintAll:repaintAll,paintChips:paintChips,paintGate:paintGate,ctx:ctxFor,screenTitle:screenTitle,nav:NAV,screens:SCREENS,shared:{},
  get D(){return D},get RUNS(){return RUNS},INSTS:INSTS,get LANG(){return LANG}};
W.NG=NG;
W.__I18N__={miss:I18N_MISS,hit:I18N_HIT,T:s=>T(s),lang:()=>LANG,set:l=>setLang(l)};
W.__NG_ERRORS__=W.__NG_ERRORS__||[];
W.runKey=runKey;W.setInst=setInst;W.setRun=setRun;W.setLang=setLang;W.wireTheme=wireTheme;W.repaintAll=repaintAll;
guard(boot,null,'boot');
})();
