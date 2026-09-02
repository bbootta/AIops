/* RYNTA next: charts.js (design_spec 4.5, shared_contracts.ng_api.charts).

   Inline SVG only. Every chart root is <svg role=img> with <title>, <desc>
   (ledger and rows aggregated) and aria-label. Colours come from tokens
   through var(--token); the primary series is --accent, secondary series are
   --ink-70 with distinct dash patterns and end labels; semantic tokens carry
   status only. Hatch patterns for --bad and --synthetic live in one <defs>
   block inserted once into the body. Requirement rules are labelled dashed
   lines whose values come from the caller (sim, ledger), never literals.
   Frame-based charts (autoChart, pnlChart, calheat) refuse truncated frames
   and return null; autoChart captions read 축 ... · 원장 전량 N행.

   Every primitive returns a wrapper <div class=chart> holding the svg, an
   optional legend, note and a table toggle (node.svg points at the svg).
   Exposed as NG.charts.* and as globals with the same names. Depends only
   on the public contract of core.js (NG.T, NG.TF, NG.fmt, NG.frame,
   NG.ui.simpleTable, NG.ui.srcMeta, NG.ui.badge). */
(function(){
'use strict';
const NS='http://www.w3.org/2000/svg';
const NG=window.NG=window.NG||{};
const T=s=>NG.T?NG.T(s):s;
const F=()=>NG.fmt||{};
const fnum=v=>v==null?'-':(typeof v==='number'?(F().num?F().num(v):String(v)):String(v));
const fint=v=>v==null?'-':(F().int?F().int(v):fnum(v));
const fmoney=v=>v==null?'-':(F().money?F().money(v):fnum(v));
const fpct=(v,d)=>v==null?'-':(F().pct?F().pct(v,d):fnum(v));
const TF=(k,v)=>NG.TF?NG.TF(k,v):T(k).replace(/\{(\w+)\}/g,(m,n)=>n in v?(typeof v[n]==='number'?fint(v[n]):String(v[n])):m);
const mk=(tag,cls,txt)=>{const e=document.createElement(tag);if(cls)e.className=cls;if(txt!=null)e.textContent=txt;return e};
const sn=(p,tag,attrs,txt)=>{const e=document.createElementNS(NS,tag);for(const k in attrs)e.setAttribute(k,attrs[k]);if(txt!=null)e.textContent=txt;p.appendChild(e);return e};
const tip=(e,t)=>{const x=document.createElementNS(NS,'title');x.textContent=t;e.appendChild(x);return e};
/* Label geometry. SVG text cannot be measured before it is in the document,
   so widths are estimated from the 11px chart face (--fs-meta): tabular
   digits and latin advance just under 7px, CJK is full width. Every label
   with a slot is trimmed to that slot and every gutter is sized from the
   labels it must hold, so nothing is painted outside the viewBox. */
const EMW=6.8,UPW=7.8,CJKW=11,ELL='…';
const wide=c=>c>='\u1100'&&(c<='\u115f'||(c>='\u2e80'&&c<='\ua4cf')||(c>='\uac00'&&c<='\ud7a3')||(c>='\uf900'&&c<='\ufaff')||(c>='\ufe30'&&c<='\ufe6f')||(c>='\uff00'&&c<='\uff60')||(c>='\uffe0'&&c<='\uffe6'));
function textW(s,k){s=String(s==null?'':s);let w=0;
  for(let i=0;i<s.length;i++){const c=s[i];w+=wide(c)?CJKW:(c>='A'&&c<='Z'?UPW:EMW)}
  return w*(k||1)}
function fitW(s,px,k){s=String(s==null?'':s);
  if(textW(s,k)<=px)return s;
  const room=px-textW(ELL,k);let w=0,i=0;
  for(;i<s.length;i++){const d=textW(s[i],k);if(w+d>room)break;w+=d}
  return i>0?s.slice(0,i)+ELL:''}
/* an end label keeps its number whole; the name in front of it gives way */
function endLabel(name,val,px){const v=String(val);
  if(!name)return fitW(v,px);
  const room=px-textW(v)-EMW;
  return room<EMW*2?fitW(v,px):fitW(name,room)+' '+v}
/* a rotated category label runs down and to the left of its anchor: no wider
   than the room under the baseline, nor than the anchor's own offset */
function rotCap(deg,room,lx0){const r=deg*Math.PI/180;
  return Math.max(EMW*3,Math.min(room/Math.sin(r),lx0/Math.cos(r)))}
/* One rule for every axis tick and value label: at most SIG significant
   digits are painted. NG.fmt (through the caller's fmt) stays the only
   formatter and keeps the unit and the scale, so the rule reads the number
   it printed and hands the same fmt a value rounded at that digit. Ledger
   cells, tooltips and the table toggle keep the caller's full precision. */
const SIG=4,NUMRE=/(-?[0-9][0-9,]*)\.([0-9]+)/;
function keepDec(m){const i=m[1].replace(/[^0-9]/g,'').replace(/^0+/,'');
  return i?Math.max(0,SIG-i.length):/^0*/.exec(m[2])[0].length+SIG}
function labelFmt(fm){return v=>{const s=fm(v);
  if(typeof v!=='number'||!isFinite(v))return s;
  const m=NUMRE.exec(s);if(!m)return s;
  const k=keepDec(m);if(m[2].length<=k)return s;
  const mant=Number(m[1].replace(/,/g,'')+'.'+m[2]);
  const s2=mant?fm(v*(Number(mant.toFixed(k))/mant)):s,m2=NUMRE.exec(s2);
  if(!m2||m2[2].length<=k)return s2;
  return s2.replace(NUMRE,k?m2[1]+'.'+m2[2].slice(0,k):m2[1])}}
/* the left gutter holds the widest tick label; gridAt trims to what it got */
const AXPAD=8;
function axisAt(pairs,fl,min,W){const p=pairs.map(q=>[q[0],fl(q[1])]);
  const w=Math.max.apply(null,p.map(q=>textW(q[1])));
  return {pairs:p,pL:Math.max(min,Math.min(Math.round(W*0.3),Math.ceil(w)+AXPAD))}}
const num=x=>typeof x==='number'&&isFinite(x);
const idx=f=>{const o={};f.columns.forEach((c,i)=>{o[c]=i});return o};
const colLabel=(f,i)=>NG.frame&&NG.frame.colLabel?NG.frame.colLabel(f,i):((f.labels&&f.labels[i])||f.columns[i]);
const curD=()=>NG.D||(typeof D!=='undefined'?D:null)||window.__RYNTA__||null;
const TONE_WORD={good:'양호',warn:'주의',bad:'불량',blocked:'차단','not-run':'미실행',synthetic:'합성',neutral:'중립'};
const GLYPH={good:'●',warn:'◆',bad:'✕',blocked:'⊘','not-run':'○',synthetic:'▧',explanatory:'≈'};
const DASH=['','6 3','2 3','9 3 2 3'];
const HATCH={bad:'url(#ng-hatch-bad)',synthetic:'url(#ng-hatch-synthetic)'};
const INK='fill:var(--ink)';

/* full frame from the active run; null when the frame is a sample */
function fullFrame(name){
  const fr=NG.frame;
  if(fr&&fr.full){const f=fr.full(name);if(f)return f}
  const D=curD(),f=D&&D.data&&D.data[name];
  return f&&f.shown>=f.total?f:null;
}
function srcMeta(f){
  if(NG.ui&&NG.ui.srcMeta)return NG.ui.srcMeta(f);
  return mk('div','meta',T('원장')+' '+f.table+' · '+TF('{shown}/{total}행',{shown:f.shown,total:f.total}));
}
function toneOf(src,v){
  if(NG.tone)return NG.tone(src,v);
  const D=curD(),m=D&&D.x_severity&&D.x_severity.map;
  const hit=m&&m.find(x=>x.source===src&&x.value===v);
  return hit?hit.tone:'neutral';
}
/* glyph paired with its word; aria-label carries the word */
function toneGlyph(tone){
  const D=curD(),g=(D&&D.x_severity&&D.x_severity.glyphs)||GLYPH;
  const w=T(TONE_WORD[tone]||TONE_WORD.neutral);
  const s=mk('span','glyph '+tone,(g[tone]||GLYPH.neutral||'○')+' '+w);
  s.setAttribute('aria-label',w);
  return s;
}
/* one defs block for the hatch patterns (--bad, --synthetic) */
function ensureDefs(){
  if(!document.body||document.getElementById('ng-chart-defs'))return;
  const s=document.createElementNS(NS,'svg');
  s.id='ng-chart-defs';s.setAttribute('aria-hidden','true');s.setAttribute('focusable','false');
  s.style.cssText='position:absolute;width:0;height:0;overflow:hidden';
  const d=sn(s,'defs',{});
  [['bad','--bad'],['synthetic','--synthetic']].forEach(([k,tok])=>{
    const p=sn(d,'pattern',{id:'ng-hatch-'+k,width:6,height:6,patternUnits:'userSpaceOnUse',patternTransform:'rotate(45)'});
    sn(p,'rect',{width:6,height:6,fill:'var(--panel)'});
    sn(p,'rect',{width:2.5,height:6,fill:'var('+tok+')'})});
  document.body.insertBefore(s,document.body.firstChild);
}
function fillOf(it){
  if(it.tone==='synthetic')return HATCH.synthetic;
  if(it.hatch)return HATCH[it.hatch]||HATCH.bad;
  return 'var(--'+(it.tone||'accent')+')';
}
function descOf(o,n){
  const f=o&&o.src&&o.src.columns?o.src:null;
  if(f){const part=f.shown<f.total?TF('표본 {n}/{N}행',{n:f.shown,N:f.total}):TF('전량 {N}행',{N:f.total});
    return T('원장')+' '+f.table+' · '+part}
  return (o&&o.desc)||TF('{n}건',{n:n||0});
}
function svgRoot(w,h,title,desc){
  ensureDefs();
  const s=document.createElementNS(NS,'svg');
  s.setAttribute('viewBox',`0 0 ${w} ${h}`);s.setAttribute('role','img');
  s.setAttribute('width','100%');s.setAttribute('preserveAspectRatio','xMidYMid meet');
  s.style.cssText='display:block;width:100%;max-width:'+w+'px;height:auto';
  const t=title||desc||T('표');
  sn(s,'title',{},t);sn(s,'desc',{},desc||t);
  s.setAttribute('aria-label',t);
  return s;
}
/* three hairline gridlines with --muted labels; baseline in --ink */
function gridAt(s,x1,x2,pairs,baseY){
  pairs.forEach(([y,lab])=>{
    sn(s,'line',{x1,x2,y1:y,y2:y,class:'gridline',stroke:'var(--hairline)','stroke-width':1});
    sn(s,'text',{x:x1-6,y:y+4,'text-anchor':'end',class:'axis'},fitW(lab,x1-8))});
  if(baseY!=null)sn(s,'line',{x1,x2,y1:baseY,y2:baseY,class:'base',stroke:'var(--ink)','stroke-width':1});
}
function simpleTable(cols,rows){
  if(NG.ui&&NG.ui.simpleTable)return NG.ui.simpleTable(cols,rows,{numeric:false});
  const w=mk('div','tw'),t=mk('table'),h=mk('tr');
  cols.forEach(c=>h.appendChild(mk('th',null,c)));t.appendChild(mk('thead')).appendChild(h);
  const b=mk('tbody');rows.forEach(r=>{const tr=mk('tr');r.forEach(v=>tr.appendChild(mk('td',null,v==null?'-':String(v))));b.appendChild(tr)});
  t.appendChild(b);w.appendChild(t);return w;
}
/* button that swaps the svg for NG.ui.simpleTable of the same items */
function tableToggle(svg,items){
  const tbl=Array.isArray(items)?{cols:[T('항목'),T('값')],rows:items.map(x=>[x.label,x.text!=null?x.text:fnum(x.value)])}:items;
  const b=mk('button','btn small',T('표 보기'));
  b.type='button';b.setAttribute('aria-pressed','false');
  let node=null;
  b.onclick=()=>{
    if(node){node.replaceWith(svg);node=null;b.textContent=T('표 보기');b.setAttribute('aria-pressed','false');return}
    node=simpleTable(tbl.cols,tbl.rows);svg.replaceWith(node);
    b.textContent=T('차트 보기');b.setAttribute('aria-pressed','true')};
  return b;
}
function legend(items){
  const w=mk('div','legend');
  items.forEach(it=>{
    const r=mk('span');
    const sw=mk('i');
    if(it.dash!=null)sw.style.cssText='height:0;border:0;border-top:2px '+(it.dash?'dashed':'solid')+' '+(it.color||'var(--ink-70)');
    else sw.style.background=it.hatch?'var(--hatch-'+it.hatch+')':(it.color||'var(--'+(it.tone||'accent')+')');
    if(it.opacity!=null)sw.style.opacity=it.opacity;
    r.appendChild(sw);r.appendChild(mk('span',null,it.name));w.appendChild(r)});
  return w;
}
function box(svg,o,tbl,lg){
  const b=mk('div','chart');b.svg=svg;
  if(o.title)b.appendChild(mk('div','ttl',o.title));
  b.appendChild(svg);
  if(lg&&lg.length>1)b.appendChild(legend(lg));
  if(o.note)b.appendChild(mk('div','meta',o.note));
  const foot=mk('div','row');
  if(tbl)foot.appendChild(tableToggle(svg,tbl));
  if(o.src&&o.src.columns)foot.appendChild(srcMeta(o.src));
  if(foot.firstChild)b.appendChild(foot);
  return b;
}
function series2(i){return i===0?'var(--accent)':'var(--ink-70)'}
const opac=j=>[1,0.7,0.45,0.28,0.18][j%5];

/* ── bars: items [{label, value, tone?, hatch?}] ─────────────────────── */
function bars(items,o={}){
  const n=items.length,W=680,H=230,pB=n>7?64:34,pT=16,pR=10,fm=o.fmt||fnum,fl=labelFmt(fm);
  const max=Math.max(...items.map(x=>Math.abs(x.value)||0),0)||1,ih=H-pB-pT;
  const A=axisAt([1/3,2/3,1].map(f=>[pT+ih*(1-f),max*f]),fl,60,W),pL=A.pL;
  const s=svgRoot(W,H,o.title||T('막대'),descOf(o,n));
  gridAt(s,pL,W-pR,A.pairs,H-pB);
  const gap=(W-pL-pR)/(n||1),bw=gap*0.66,rot=n>7;
  const cap=rot?rotCap(32,pB-18,pL+gap/2):gap-4;
  items.forEach((it,i)=>{
    const h=Math.abs(it.value||0)/max*ih,x=pL+i*gap+(gap-bw)/2,y=H-pB-h;
    const r=tip(sn(s,'rect',{x,y,width:bw,height:Math.max(h,1),fill:fillOf(it)}),it.label+': '+fm(it.value));
    if(o.onBar){r.style.cursor='pointer';r.onclick=()=>o.onBar(it)}
    const lx=x+bw/2,ly=H-pB+14;
    const lb=sn(s,'text',{x:lx,y:ly,'text-anchor':rot?'end':'middle'},fitW(it.label,cap));
    if(rot)lb.setAttribute('transform',`rotate(-32 ${lx} ${ly})`);
    if(n<=14)sn(s,'text',{x:lx,y:y-3,'text-anchor':'middle',style:INK},fl(it.value))});
  return box(s,o,{cols:[T('항목'),T('값')],rows:items.map(x=>[x.label,fm(x.value)])});
}
/* ── hbars: div.card with barList and srcMeta ─────────────────────────── */
function barList(items,{money=true,fmt}={}){
  const fm=fmt||(money?fmoney:fnum),w=mk('div','barlist');
  const max=Math.max(...items.map(x=>Math.abs(x.value)||0),0)||1;
  items.forEach(it=>{
    const r=mk('div','brow');
    r.style.cssText='display:grid;grid-template-columns:minmax(0,1fr) auto;gap:2px 8px;align-items:center;padding:3px 0';
    const l=mk('span',null,it.label);if(it.phys)l.title=it.phys;
    const v=mk('span','num',fm(it.value));v.style.textAlign='right';
    r.appendChild(l);r.appendChild(v);
    const b=mk('div','bar'+(it.tone?' '+it.tone:''));b.style.gridColumn='1/-1';
    const i=mk('i');i.style.width=(Math.abs(it.value||0)/max*100).toFixed(1)+'%';
    if(it.tone==='synthetic')i.style.background='var(--hatch-synthetic)';
    b.appendChild(i);r.appendChild(b);
    if(it.sub){const sb=mk('div','meta',it.sub);sb.style.cssText='grid-column:1/-1;margin:0';r.appendChild(sb)}
    w.appendChild(r)});
  return w;
}
function hbars(items,{title,src,money=true,fmt}={}){
  const c=mk('div','card');
  if(title)c.appendChild(mk('h3',null,title));
  c.appendChild(barList(items,{money,fmt}));
  if(src)c.appendChild(src.nodeType?src:srcMeta(src));
  return c;
}
/* ── stackBars: series [{name, values[]}], labels[] ─────────────────── */
function stackBars(series,labels,o={}){
  const n=labels.length,W=680,H=240,pB=n>7?64:34,pT=16,pR=10,fm=o.fmt||fnum,fl=labelFmt(fm);
  const totals=labels.map((_,i)=>series.reduce((a,se)=>a+(num(se.values[i])?se.values[i]:0),0));
  const max=Math.max(...totals,0)||1,ih=H-pB-pT;
  const A=axisAt([1/3,2/3,1].map(f=>[pT+ih*(1-f),max*f]),fl,60,W),pL=A.pL;
  const s=svgRoot(W,H,o.title||T('막대'),descOf(o,n));
  gridAt(s,pL,W-pR,A.pairs,H-pB);
  const gap=(W-pL-pR)/(n||1),bw=gap*0.62,rot=n>7;
  const cap=rot?rotCap(32,pB-18,pL+gap/2):gap-4;
  labels.forEach((lb,i)=>{
    let acc=0;
    series.forEach((se,j)=>{
      const v=num(se.values[i])?se.values[i]:0;if(!v)return;
      const h=v/max*ih,y=H-pB-((acc+v)/max)*ih;
      tip(sn(s,'rect',{x:pL+i*gap+(gap-bw)/2,y,width:bw,height:Math.max(h,1),fill:'var(--accent)','fill-opacity':opac(j),stroke:'var(--bg)','stroke-width':1}),lb+' · '+se.name+': '+fm(v));
      acc+=v});
    const lx=pL+i*gap+gap/2,ly=H-pB+14;
    const t=sn(s,'text',{x:lx,y:ly,'text-anchor':rot?'end':'middle'},fitW(lb,cap));
    if(rot)t.setAttribute('transform',`rotate(-32 ${lx} ${ly})`)});
  const lg=series.map((se,j)=>({name:se.name,opacity:opac(j)}));
  return box(s,o,{cols:[T('항목')].concat(series.map(se=>se.name)),rows:labels.map((lb,i)=>[lb].concat(series.map(se=>fm(se.values[i]))))},lg);
}
/* ── treemap: squarified, two-level when group present ───────────────── */
function squarify(data,rect){
  const out=[],items=data.filter(x=>x.v>0);let cur={...rect};
  const worst=(row,side,scale)=>{const a=row.reduce((t,x)=>t+x.v,0)*scale;const mx=Math.max(...row.map(x=>x.v))*scale,mn=Math.min(...row.map(x=>x.v))*scale;return Math.max(side*side*mx/(a*a),(a*a)/(side*side*mn))};
  while(items.length&&cur.w>0.5&&cur.h>0.5){
    const rest=items.reduce((t,x)=>t+x.v,0)||1,scale=cur.w*cur.h/rest,side=Math.min(cur.w,cur.h);
    let row=[items.shift()];
    while(items.length&&worst(row.concat(items[0]),side,scale)<=worst(row,side,scale))row.push(items.shift());
    const area=row.reduce((t,x)=>t+x.v,0)*scale,horiz=cur.w>=cur.h,thick=area/side;
    let off=0;
    row.forEach(x=>{const len=x.v*scale/thick;
      out.push(horiz?{...x,x:cur.x,y:cur.y+off,w:thick,h:len}:{...x,x:cur.x+off,y:cur.y,w:len,h:thick});off+=len});
    if(horiz){cur.x+=thick;cur.w-=thick}else{cur.y+=thick;cur.h-=thick}}
  return out;
}
function treemap(items,o={}){
  const n=items.length,W=680,H=360,fm=o.fmt||fnum,fl=labelFmt(fm);
  const s=svgRoot(W,H,o.title||T('표'),descOf(o,n));
  const total=items.reduce((t,x)=>t+(x.value>0?x.value:0),0)||1;
  const groups=[];items.forEach(x=>{const g=x.group==null?null:String(x.group);let e=groups.find(q=>q.key===g);if(!e){e={key:g,v:0,items:[]};groups.push(e)}e.v+=x.value>0?x.value:0;e.items.push(x)});
  const two=groups.length>1||groups[0].key!=null;
  const cell=(c,it,gi)=>{
    const hi=gi%2===0,fill='var(--accent)';
    const r=tip(sn(s,'rect',{x:c.x+1,y:c.y+1,width:Math.max(c.w-2,0.5),height:Math.max(c.h-2,0.5),fill,'fill-opacity':hi?0.72:0.36,stroke:'var(--bg)','stroke-width':1}),it.label+': '+fm(it.value)+' ('+fpct(it.value/total,1)+')');
    if(o.onCell){r.style.cursor='pointer';r.onclick=()=>o.onCell(it)}
    const st=hi?'fill:var(--on-accent)':INK;
    if(c.w>34&&c.h>16)sn(s,'text',{x:c.x+5,y:c.y+14,style:st},fitW(it.label,c.w-10));
    if(c.w>34&&c.h>30)sn(s,'text',{x:c.x+5,y:c.y+27,style:st},fitW(fl(it.value),c.w-10))};
  if(!two)squarify(items.map(x=>({v:x.value,it:x})),{x:0,y:0,w:W,h:H}).forEach(c=>cell(c,c.it,0));
  else squarify(groups.map(g=>({v:g.v,g})),{x:0,y:0,w:W,h:H}).forEach((gc,gi)=>{
    sn(s,'rect',{x:gc.x,y:gc.y,width:gc.w,height:gc.h,fill:'none',stroke:'var(--ink)','stroke-width':1.5});
    const head=gc.h>40?16:0;
    if(head)sn(s,'text',{x:gc.x+4,y:gc.y+12,style:INK+';font-weight:650'},fitW(gc.g.key,gc.w-8));
    squarify(gc.g.items.map(x=>({v:x.value,it:x})),{x:gc.x+2,y:gc.y+head+2,w:gc.w-4,h:gc.h-head-4}).forEach(c=>cell(c,c.it,gi))});
  const lg=two?groups.map((g,gi)=>({name:g.key+' · '+fpct(g.v/total,1),opacity:gi%2===0?0.72:0.36})):null;
  const cols=two?[T('기준'),T('항목'),T('값')]:[T('항목'),T('값')];
  return box(s,o,{cols,rows:items.map(x=>two?[x.group,x.label,fm(x.value)]:[x.label,fm(x.value)])},lg);
}
/* ── heat: matrix[row][col] ──────────────────────────────────────────── */
function heat(matrix,rowLabels,colLabels,o={}){
  const nc=colLabels.length,nr=rowLabels.length,fm=o.fmt||fnum,fl=labelFmt(fm);
  const cw=Math.max(38,Math.min(76,560/(nc||1))),ch=22,pL=120,pT=28;
  const W=pL+cw*nc+8,H=pT+ch*nr+8;
  const flat=matrix.flat().filter(num);
  const max=Math.max(...flat,0)||1,min=Math.min(...flat,0);
  const s=svgRoot(W,H,o.title||T('표'),descOf(o,nr*nc));
  colLabels.forEach((c,j)=>sn(s,'text',{x:pL+j*cw+cw/2,y:pT-8,'text-anchor':'middle'},fitW(c,cw-4)));
  rowLabels.forEach((r,i)=>{
    sn(s,'text',{x:pL-6,y:pT+i*ch+15,'text-anchor':'end'},fitW(r,pL-8));
    colLabels.forEach((c,j)=>{
      const v=matrix[i][j],t=num(v)?(max===min?0.5:(v-min)/(max-min)):0;
      tip(sn(s,'rect',{x:pL+j*cw+1,y:pT+i*ch+1,width:cw-2,height:ch-2,fill:'var(--accent)','fill-opacity':(0.08+0.82*t).toFixed(3)}),r+' × '+c+': '+fm(v));
      if(num(v)&&cw>=48)sn(s,'text',{x:pL+j*cw+cw/2,y:pT+i*ch+15,'text-anchor':'middle',style:t>0.55?'fill:var(--on-accent)':INK},fitW(fl(v),cw-4))})});
  return box(s,o,{cols:[T('항목')].concat(colLabels),rows:rowLabels.map((r,i)=>[r].concat(colLabels.map((c,j)=>fm(matrix[i][j]))))});
}
/* ── waterfall: steps [{label, delta}] from start ────────────────────── */
function waterfall(steps,start,o={}){
  const W=680,H=240,pB=steps.length>5?64:34,pT=16,pR=10,fm=o.fmt||fnum,fl=labelFmt(fm);
  let acc=start;const pts=[{label:o.startLabel||T('기준'),v:start,d:null}];
  steps.forEach(st=>{acc+=st.delta;pts.push({label:st.label,v:acc,d:st.delta})});
  const n=pts.length,max=Math.max(...pts.map(p=>p.v),start,0),min=Math.min(...pts.map(p=>p.v),0),span=(max-min)||1;
  const ih=H-pB-pT,Y=v=>H-pB-((v-min)/span)*ih;
  const A=axisAt([1/3,2/3,1].map(f=>[Y(min+span*f),min+span*f]),fl,64,W),pL=A.pL;
  const s=svgRoot(W,H,o.title||T('표'),descOf(o,n));
  gridAt(s,pL,W-pR,A.pairs,Y(0));
  const gap=(W-pL-pR)/n,bw=gap*0.6,rot=n>6;
  const cap=rot?rotCap(30,pB-18,pL+gap/2):gap-4;
  pts.forEach((p,i)=>{
    const x=pL+i*gap+(gap-bw)/2,y0=p.d==null?Y(0):Y(p.v-p.d),y1=Y(p.v);
    const tone=p.d==null?'accent':(p.d>=0?'good':'bad');
    tip(sn(s,'rect',{x,y:Math.min(y0,y1),width:bw,height:Math.max(Math.abs(y1-y0),1.5),fill:'var(--'+tone+')'}),p.label+': '+fm(p.v)+(p.d==null?'':' ('+(p.d>=0?'+':'')+fm(p.d)+')'));
    if(i<n-1)sn(s,'line',{x1:x+bw,x2:x+gap,y1,y2:y1,class:'gridline',stroke:'var(--hairline)','stroke-dasharray':'2 2'});
    const lx=x+bw/2,ly=H-pB+14;
    const lb=sn(s,'text',{x:lx,y:ly,'text-anchor':rot?'end':'middle'},fitW(p.label,cap));
    if(rot)lb.setAttribute('transform',`rotate(-30 ${lx} ${ly})`)});
  return box(s,o,{cols:[T('항목'),T('값')],rows:pts.map(p=>[p.label,fm(p.v)+(p.d==null?'':' ('+(p.d>=0?'+':'')+fm(p.d)+')')])});
}
/* ── gauge: value against max, semantic tone only ────────────────────── */
function gauge(value,max,o={}){
  const W=240,H=140,cx=120,cy=118,R=92,r=64,fm=o.fmt||fnum,fl=labelFmt(fm);
  const frac=Math.max(0,Math.min(1,max?value/max:0));
  const s=svgRoot(W,H,o.title||T('값'),descOf(o,1));
  const arc=(f,fill)=>{
    const a0=Math.PI,a1=Math.PI+f*Math.PI,P=(ra,an)=>[cx+ra*Math.cos(an),cy+ra*Math.sin(an)];
    const [x0,y0]=P(R,a0),[x1,y1]=P(R,a1),[x2,y2]=P(r,a1),[x3,y3]=P(r,a0);
    return sn(s,'path',{d:`M${x0},${y0} A${R},${R} 0 0,1 ${x1},${y1} L${x2},${y2} A${r},${r} 0 0,0 ${x3},${y3} Z`,fill})};
  arc(1,'var(--tint-ink)');
  if(frac>0)tip(arc(frac,'var(--'+(o.tone||'accent')+')'),fm(value)+' / '+fm(max));
  sn(s,'text',{x:cx,y:cy-14,'text-anchor':'middle',style:INK+';font-size:22px;font-weight:650'},fitW(fl(value),W-8,2));
  sn(s,'text',{x:cx,y:cy+2,'text-anchor':'middle'},fitW(fl(max),W-8));
  return box(s,o,{cols:[T('항목'),T('값')],rows:[[T('값'),fm(value)],[T('기준'),fm(max)]]});
}
/* ── kriCards: no sparkline; arrows only from x_trend flags ──────────── */
function kriCards(kris,{arrows=null}={}){
  const g=mk('div','grid');
  kris.forEach(k=>{
    const tone=toneOf('kri.grade',k.grade),c=mk('div','card kri '+tone);
    c.style.borderLeft='3px solid var(--'+tone+')';
    const hd=mk('div','row');hd.style.justifyContent='space-between';
    hd.appendChild(mk('span','meta',k.category));
    const bd=NG.ui&&NG.ui.badge?NG.ui.badge(k.grade,tone):mk('span','badge '+tone,k.grade);
    hd.appendChild(bd);c.appendChild(hd);
    c.appendChild(mk('div','lab',k.name));
    const v=mk('div','val',k.actual_text);v.style.color='var(--'+tone+')';c.appendChild(v);
    c.appendChild(mk('div','meta',k.threshold_text));
    const fl=arrows&&arrows.find(x=>x.label===k.name||x.metric===k.name);
    if(fl&&fl.trend_state){
      const up=fl.qoq>0,flat=!fl.qoq;
      const a=mk('div','meta '+(fl.trend_state==='악화'?'bad':fl.trend_state==='개선'?'good':''),(flat?'→':up?'↗':'↘')+' '+T(fl.trend_state));
      a.title=T('전기 대비');c.appendChild(a)}
    g.appendChild(c)});
  return g;
}
/* ── multiLine: category or date axis, rules, hatch bands, end labels ── */
function multiLine(series,labels,o={}){
  const n=labels.length,W=900,H=260,pL=64,pR=110,pT=16,pB=30,fm=o.fmt||fnum;
  const rules=o.rules||[],hatch=o.hatch||[];
  const all=series.flatMap(se=>se.values).filter(num).concat(rules.map(r=>r.value).filter(num));
  // 0 을 억지로 담으면 8~11% 대의 비율 계열이 위쪽 20% 에 뭉쳐 요구선과의 차이가
  // 보이지 않는다. 바닥이 0 에 가까울 때만 0 을 담고, 아니면 자료 범위에 여백을
  // 준다. 음수가 있으면 0 은 자연히 범위 안이다. (손익 차트는 0 선 자체가 판정
  // 기준이라 그쪽은 0 을 계속 담는다.)
  let lo=Math.min(...all),hi=Math.max(...all);
  if(lo>0&&lo<hi*0.15)lo=0;
  const pad=((hi-lo)||Math.abs(hi)||1)*0.08;
  const max=hi+pad,min=lo-pad,span=(max-min)||1,ih=H-pT-pB;
  const X=k=>pL+k*(W-pL-pR)/Math.max(n-1,1),Y=v=>H-pB-((v-min)/span)*ih,gap=(W-pL-pR)/Math.max(n-1,1);
  const s=svgRoot(W,H,o.title||T('추이'),descOf(o,n));
  labels.forEach((lb,k)=>{if(!hatch[k])return;
    tip(sn(s,'rect',{x:X(k)-gap/2,y:pT,width:gap,height:ih,fill:HATCH.bad,'fill-opacity':0.26}),String(lb)+' · '+T('미통과'))});
  gridAt(s,pL,W-pR,[1/3,2/3,1].map(f=>[Y(min+span*f),fm(min+span*f)]),Y(min));
  rules.forEach(r=>{if(!num(r.value))return;const y=Y(r.value),col='var(--'+(r.tone||'ink')+')';
    sn(s,'line',{x1:pL,x2:W-pR,y1:y,y2:y,stroke:col,'stroke-width':1.2,'stroke-dasharray':'6 4'});
    sn(s,'text',{x:pL+4,y:y-4,style:'fill:'+col},(r.label||'')+' '+fm(r.value))});
  series.forEach((se,i)=>{
    const col=series2(i),dash=se.dash!=null?se.dash:(se.dotted?'2 3':DASH[i%DASH.length]);
    const pts=se.values.map((v,k)=>num(v)?X(k).toFixed(1)+','+Y(v).toFixed(1):null).filter(Boolean).join(' ');
    const pl=sn(s,'polyline',{points:pts,fill:'none',stroke:col,'stroke-width':i===0?2:1.6,'stroke-linejoin':'round'});
    if(dash)pl.setAttribute('stroke-dasharray',dash);
    let last=-1;se.values.forEach((v,k)=>{if(num(v))last=k});
    if(last>=0){sn(s,'circle',{cx:X(last),cy:Y(se.values[last]),r:3,fill:col});
      sn(s,'text',{x:X(last)+7,y:Y(se.values[last])+4,style:'fill:'+col},endLabel(se.name,fm(se.values[last]),pR-11))}});
  const step=Math.max(1,Math.ceil(n/8));
  labels.forEach((lb,k)=>{if(k%step&&k!==n-1)return;sn(s,'text',{x:X(k),y:H-8,'text-anchor':'middle'},fitW(lb,gap*step))});
  const lg=series.map((se,i)=>({name:se.name,color:series2(i),dash:se.dash!=null?se.dash:(se.dotted?'2 3':DASH[i%DASH.length])}));
  return box(s,o,{cols:[T('항목')].concat(series.map(se=>se.name)),rows:labels.map((lb,k)=>[lb].concat(series.map(se=>fm(se.values[k]))))},lg);
}
/* ── areaLine: one series with area fill ─────────────────────────────── */
function areaLine(values,o={}){
  const n=values.length,W=920,H=o.height||190,pL=60,pR=90,pT=14,pB=22,fm=o.fmt||fmoney;
  const vs=values.filter(num),max=Math.max(...vs,0),min=Math.min(...vs,0),span=(max-min)||1,ih=H-pT-pB;
  const X=k=>pL+k*(W-pL-pR)/Math.max(n-1,1),Y=v=>H-pB-((v-min)/span)*ih;
  const s=svgRoot(W,H,o.title||o.label||T('추이'),descOf(o,n));
  gridAt(s,pL,W-pR,[1/3,2/3,1].map(f=>[Y(min+span*f),fm(min+span*f)]),Y(min));
  const pts=values.map((v,k)=>num(v)?X(k).toFixed(1)+','+Y(v).toFixed(1):null).filter(Boolean);
  if(pts.length){
    sn(s,'polygon',{points:X(0).toFixed(1)+','+Y(min).toFixed(1)+' '+pts.join(' ')+' '+X(n-1).toFixed(1)+','+Y(min).toFixed(1),fill:'var(--accent)','fill-opacity':0.12});
    sn(s,'polyline',{points:pts.join(' '),fill:'none',stroke:'var(--accent)','stroke-width':2});
    let last=-1;values.forEach((v,k)=>{if(num(v))last=k});
    sn(s,'circle',{cx:X(last),cy:Y(values[last]),r:4,fill:'var(--accent)'});
    sn(s,'text',{x:X(last)+8,y:Y(values[last])+4,style:INK+';font-weight:650'},(o.label?o.label+' ':'')+fm(values[last]))}
  const d=o.dates||[];
  [0,Math.floor((n-1)/2),n-1].forEach(k=>{if(k>=0&&d[k]!=null)sn(s,'text',{x:X(k),y:H-6,'text-anchor':k===0?'start':k===n-1?'end':'middle'},String(d[k]))});
  return box(s,o,{cols:[T('기간'),o.label||T('값')],rows:values.map((v,k)=>[d[k]!=null?d[k]:k+1,fm(v)])});
}
/* ── scatterXY: one circle per point, fit line stroke-dasharray='5 4' ── */
function scatterXY(points,o={}){
  const n=points.length,W=560,H=330,pL=60,pB=44,pT=28,pR=14;
  const xs=points.map(p=>p.x),ys=points.map(p=>p.y);
  const x0=Math.min(...xs,0),x1=Math.max(...xs,0)||1,y0=Math.min(...ys,0),y1=Math.max(...ys,0)||1;
  const sx=v=>pL+(x1===x0?0.5:(v-x0)/(x1-x0))*(W-pL-pR),sy=v=>H-pB-(y1===y0?0.5:(v-y0)/(y1-y0))*(H-pB-pT);
  const fx=o.fmtX||fnum,fy=o.fmtY||fnum;
  const s=svgRoot(W,H,o.title||((o.yLabel||'y')+' · '+(o.xLabel||'x')),descOf(o,n));
  gridAt(s,pL,W-pR,[1/3,2/3,1].map(f=>[sy(y0+(y1-y0)*f),fy(y0+(y1-y0)*f)]),sy(y0));
  [0,1/3,2/3,1].forEach(f=>{const xv=x0+(x1-x0)*f;sn(s,'text',{x:sx(xv),y:H-pB+14,'text-anchor':'middle'},fx(xv))});
  points.forEach(p=>tip(sn(s,'circle',{cx:sx(p.x),cy:sy(p.y),r:3,fill:'var(--'+(p.tone||'accent')+')','fill-opacity':0.6}),(p.label?p.label+' · ':'')+fx(p.x)+' → '+fy(p.y)));
  const fit=o.fit;
  if(fit&&num(fit.slope)&&num(fit.intercept))
    sn(s,'line',{x1:sx(x0),y1:sy(fit.intercept+fit.slope*x0),x2:sx(x1),y2:sy(fit.intercept+fit.slope*x1),stroke:'var(--ink-70)','stroke-width':1.4,'stroke-dasharray':'5 4'});
  if(o.xLabel)sn(s,'text',{x:W/2,y:H-6,'text-anchor':'middle'},o.xLabel);
  if(o.yLabel)sn(s,'text',{x:4,y:12},o.yLabel);
  return box(s,o,{cols:[T('항목'),o.xLabel||'x',o.yLabel||'y'],rows:points.map((p,i)=>[p.label!=null?p.label:i+1,fx(p.x),fy(p.y)])});
}
/* ── scatter45: ratios on both axes with the identity line ───────────── */
function scatter45(points,o={}){
  const n=points.length,W=520,H=380,pad=52,pT=28;
  const X=v=>pad+Math.max(0,Math.min(1,v))*(W-pad-14),Y=v=>H-pad-Math.max(0,Math.min(1,v))*(H-pad-pT);
  const s=svgRoot(W,H,o.title||((o.yLabel||'y')+' · '+(o.xLabel||'x')),descOf(o,n));
  gridAt(s,X(0),X(1),[1/3,2/3,1].map(f=>[Y(f),fpct(f,0)]),Y(0));
  [0,1/3,2/3,1].forEach(f=>sn(s,'text',{x:X(f),y:H-pad+14,'text-anchor':'middle'},fpct(f,0)));
  sn(s,'line',{x1:X(0),y1:Y(0),x2:X(1),y2:Y(1),stroke:'var(--ink-70)','stroke-width':1,'stroke-dasharray':'5 4'});
  points.forEach(p=>tip(sn(s,'circle',{cx:X(p.x),cy:Y(p.y),r:2.8,fill:'var(--'+(p.tone||'accent')+')','fill-opacity':0.62}),(p.label?p.label+' · ':'')+fpct(p.x,1)+' → '+fpct(p.y,1)));
  if(o.xLabel)sn(s,'text',{x:W/2,y:H-6,'text-anchor':'middle'},o.xLabel);
  if(o.yLabel)sn(s,'text',{x:4,y:12},o.yLabel);
  return box(s,o,{cols:[T('항목'),o.xLabel||'x',o.yLabel||'y'],rows:points.map((p,i)=>[p.label!=null?p.label:i+1,fpct(p.x,2),fpct(p.y,2)])});
}
/* ── pnlChart: mkt_backtest_exception, full frame only ───────────────── */
function pnlChart(f){
  if(!f||f.shown<f.total)return null;
  const i=idx(f),rows=f.rows.slice().sort((a,b)=>String(a[i.obs_date]).localeCompare(String(b[i.obs_date])));
  const n=rows.length,W=920,H=220,pL=70,pR=14,pT=14,pB=24;
  const pnl=rows.map(r=>r[i.pnl]),neg=rows.map(r=>-r[i.var_99]),all=pnl.concat(neg).filter(num);
  const max=Math.max(...all,0),min=Math.min(...all,0),span=(max-min)||1,ih=H-pT-pB;
  const X=k=>pL+k*(W-pL-pR)/Math.max(n-1,1),Y=v=>H-pB-((v-min)/span)*ih;
  const title=T('일별 손익 대 VaR 경계 (99%)');
  const s=svgRoot(W,H,title,descOf({src:f},n));
  gridAt(s,pL,W-pR,[1/3,2/3,1].map(g=>[Y(min+span*g),fmoney(min+span*g)]),Y(0));
  const line=(vs,col,dash,w)=>{const pl=sn(s,'polyline',{points:vs.map((v,k)=>X(k).toFixed(1)+','+Y(v).toFixed(1)).join(' '),fill:'none',stroke:col,'stroke-width':w});if(dash)pl.setAttribute('stroke-dasharray',dash)};
  line(pnl,'var(--accent)','',1.8);line(neg,'var(--bad)','5 3',1.4);
  let nEx=0;
  rows.forEach((r,k)=>{if(!r[i.exception])return;nEx++;
    tip(sn(s,'circle',{cx:X(k),cy:Y(r[i.pnl]),r:3.5,fill:'var(--bad)'}),String(r[i.obs_date])+' · '+fmoney(r[i.pnl])+' · '+T('예외'))});
  [0,n-1].forEach(k=>{if(k>=0)sn(s,'text',{x:X(k),y:H-6,'text-anchor':k?'end':'start'},String(rows[k][i.obs_date]))});
  const lg=[{name:colLabel(f,i.pnl),color:'var(--accent)',dash:''},{name:'−'+colLabel(f,i.var_99),color:'var(--bad)',dash:'5 3'},{name:T('예외')+' '+TF('{n}건',{n:nEx}),tone:'bad'}];
  return box(s,{title,note:T('실선 손익 · 점선 −VaR (점선 아래 손익이 백테스팅 예외다)'),src:f},
    {cols:[colLabel(f,i.obs_date),colLabel(f,i.pnl),colLabel(f,i.var_99),colLabel(f,i.exception)],rows:rows.map(r=>[r[i.obs_date],fmoney(r[i.pnl]),fmoney(r[i.var_99]),r[i.exception]?T('예외'):'-'])},lg);
}
/* ── calheat: one square per observation day, exceptions in --bad ───── */
function calheat(f){
  if(!f||f.shown<f.total)return null;
  const i=idx(f),c=mk('div','card');
  c.appendChild(mk('h3',null,T('백테스팅 예외 달력')));
  const wrap=mk('div');wrap.style.cssText='display:flex;flex-wrap:wrap;gap:3px';
  let nEx=0;
  f.rows.slice().sort((a,b)=>String(a[i.obs_date]).localeCompare(String(b[i.obs_date]))).forEach(r=>{
    const ex=!!r[i.exception];if(ex)nEx++;
    const d=mk('span');
    d.title=String(r[i.obs_date])+' · '+colLabel(f,i.pnl)+' '+fmoney(r[i.pnl])+' · '+colLabel(f,i.var_99)+' '+fmoney(r[i.var_99])+(ex?' · '+T('예외'):'')+(r[i.zone]!=null?' · '+String(r[i.zone]):'');
    d.style.cssText='width:11px;height:11px;border:1px solid var(--hairline);background:'+(ex?'var(--bad)':'var(--tint-ink)');
    wrap.appendChild(d)});
  c.appendChild(wrap);
  c.appendChild(mk('div','meta',T('예외')+' '+TF('{n}건',{n:nEx})+' / '+TF('{n}행',{n:f.total})));
  c.appendChild(srcMeta(f));
  return c;
}
/* ── histogram: bins [{lo, hi, n}] ───────────────────────────────────── */
function histogram(bins,o={}){
  const n=bins.length,W=680,H=220,pL=60,pB=34,pT=16,pR=10,fm=o.fmt||fnum;
  const max=Math.max(...bins.map(b=>b.n||0),0)||1,ih=H-pB-pT;
  const s=svgRoot(W,H,o.title||T('구간'),descOf(o,bins.reduce((t,b)=>t+(b.n||0),0)));
  gridAt(s,pL,W-pR,[1/3,2/3,1].map(f=>[pT+ih*(1-f),fint(Math.round(max*f))]),H-pB);
  const bw=(W-pL-pR)/(n||1),step=Math.max(1,Math.ceil(n/8));
  bins.forEach((b,i)=>{
    const h=(b.n||0)/max*ih,x=pL+i*bw;
    tip(sn(s,'rect',{x:x+0.5,y:H-pB-h,width:Math.max(bw-1,0.5),height:Math.max(h,0.5),fill:fillOf(b)}),fm(b.lo)+' ~ '+fm(b.hi)+': '+fint(b.n));
    if(i%step===0)sn(s,'text',{x,y:H-pB+14,'text-anchor':'middle'},fm(b.lo))});
  if(n)sn(s,'text',{x:W-pR,y:H-pB+14,'text-anchor':'end'},fm(bins[n-1].hi));
  return box(s,o,{cols:[T('구간'),T('건수')],rows:bins.map(b=>[fm(b.lo)+' ~ '+fm(b.hi),fint(b.n)])});
}
/* ── autoChart: one ledger drawn from its spec, full frame only ──────── */
const PREF=[/^rwa$|_rwa$|^rwa_/i,/^ead|_ead$/i,/exposure_amount|^amount$|_amount$/i,
  /^balance$|_balance$/i,/^ecl$|_ecl$/i,/loss$/i,/notional/i,/^value$|_value$/i,
  /ratio$|share$/i,/^n_|count$/i];
const SKIP=/(_id|asof|date|digest|hash|note|detail|reason)$/i;
function autoChart(f,r){
  /* a preview drawn as a distribution misreads the ledger: the full frame
     from D.data is used, and a truncated frame is refused (null) */
  const full=fullFrame(r.name);
  if(full)f=full;else if(!f||f.shown<f.total)return null;
  if(!f||!f.rows||f.rows.length<2)return null;
  const cols=f.columns,rows=f.rows;
  const isNum=i=>rows.some(x=>num(x[i]));
  const uniq=i=>new Set(rows.map(x=>x[i])).size;
  let cat=-1;
  for(let i=0;i<cols.length;i++){if(isNum(i)||SKIP.test(cols[i]))continue;const u=uniq(i);if(u>=2&&u<=24){cat=i;break}}
  if(cat<0)return null;
  const nums=cols.map((c,i)=>i).filter(i=>isNum(i)&&!SKIP.test(cols[i]));
  let val=-1;
  for(const rx of PREF){const hit=nums.find(i=>rx.test(cols[i]));if(hit!=null){val=hit;break}}
  if(val<0&&nums.length)val=nums[0];
  if(val<0)return null;
  const uCat=uniq(cat);let grp=-1;
  for(let i=0;i<cols.length;i++){if(i===cat||isNum(i)||SKIP.test(cols[i]))continue;const u=uniq(i);if(u>=2&&u<=8&&u<uCat){grp=i;break}}
  const agg=new Map();
  rows.forEach(x=>{const g=grp>=0?String(x[grp]):null,k=String(x[cat]),v=num(x[val])?x[val]:0;
    const key=g==null?k:g+'\u001f'+k,e=agg.get(key);
    if(e)e.value+=v;else agg.set(key,{group:g,label:k,value:v})});
  const items=[...agg.values()].filter(x=>x.value!==0).sort((a,b)=>Math.abs(b.value)-Math.abs(a.value));
  const nItems=items.length;
  if(nItems<2)return null;
  const L=i=>colLabel(f,i),axis=grp>=0?L(grp)+' > '+L(cat):L(cat);
  const note=T('축')+' '+axis+' × '+L(val)+' · '+T('원장 전량')+' '+TF('{n}행',{n:f.total});
  const o={title:r.korean+' · '+L(val),note,src:f,fmt:PREF.slice(0,8).some(rx=>rx.test(cols[val]))&&!/ratio$|share$/i.test(cols[val])?fmoney:fnum};
  if(items.every(x=>x.value>0)&&nItems<=24)return treemap(items,o);
  return bars(items.slice(0,14),o);
}
/* ── DOMAIN_CHARTS: headline chart per product, full frames only ────── */
function groupSum(f,keyCol,valCol){
  const i=idx(f),m=new Map();
  f.rows.forEach(r=>{const k=r[i[keyCol]],e=m.get(k)||{key:k,sum:0,n:0};e.sum+=num(r[i[valCol]])?r[i[valCol]]:0;e.n++;m.set(k,e)});
  return [...m.values()].sort((a,b)=>b.sum-a.sum);
}
const DOMAIN_CHARTS={
  'PRD-RWA':root=>{
    const sa=fullFrame('rwa_sa_bucket');
    if(sa){const i=idx(sa);root.appendChild(hbars(sa.rows.map(r=>({label:r[i.asset_class]+' · RW '+fpct(r[i.risk_weight],0),value:r[i.rwa],sub:'EAD '+fmoney(r[i.ead])})).sort((a,b)=>b.value-a.value),
      {title:T('위험가중자산 구성 (표준방법 자산군×위험가중치)'),src:sa}))}
    const irb=fullFrame('rwa_irb_pool');
    if(irb){const i=idx(irb);root.appendChild(hbars(irb.rows.map(r=>({label:r[i.asset_class]+' · PD '+r[i.pd_band],value:r[i.rwa],sub:'RW '+fpct(r[i.rw_average],0)})).sort((a,b)=>b.value-a.value).slice(0,10),
      {title:T('내부등급법 풀별 위험가중자산 (PD 구간)'),src:irb}))}},
  'PRD-MKT':root=>{
    const bt=fullFrame('mkt_backtest_exception');
    if(bt){const c=mk('div','card');c.appendChild(pnlChart(bt));root.appendChild(c);root.appendChild(calheat(bt))}},
  'PRD-ECL':root=>{
    const f=fullFrame('ecl_result');if(!f)return;
    root.appendChild(hbars(groupSum(f,'stage','ecl').map(x=>({label:'Stage '+x.key,value:x.sum,sub:TF('{n}건',{n:x.n}),tone:x.key===3?'bad':x.key===2?'warn':undefined})),
      {title:T('기대신용손실 구성 (단계별)'),src:f}))},
  'PRD-CRM':root=>{
    const f=fullFrame('crm_ews_signal');if(!f)return;
    root.appendChild(hbars(groupSum(f,'level','ead').map(x=>({label:T('조기경보')+' '+x.key,value:x.sum,sub:TF('{n}건',{n:x.n}),tone:x.key==='경보'?'bad':x.key==='주의'?'warn':undefined})),
      {title:T('조기경보 단계별 익스포저(EAD)'),src:f}))},
  'PRD-ALM':root=>{
    const f=fullFrame('alm_lcr_item');if(!f)return;const i=idx(f);
    root.appendChild(hbars(f.rows.map(r=>({label:r[i.section]+' · '+r[i.category],value:Math.abs(r[i.weighted]),sub:'× '+fpct(r[i.factor],0),tone:r[i.section]==='OUTFLOW'?'warn':undefined})).sort((a,b)=>b.value-a.value),
      {title:T('유동성커버리지비율 구성 (가중 후 금액)'),src:f}))},
  'PRD-OPR':root=>{
    const f=fullFrame('opr_loss_event');if(!f)return;
    root.appendChild(hbars(groupSum(f,'event_type','net_loss').map(x=>({label:x.key,value:x.sum,sub:TF('{n}건',{n:x.n})})),
      {title:T('운영손실 순손실 구성 (사건유형별)'),src:f}))},
};
const API={bars,hbars,barList,stackBars,treemap,heat,waterfall,gauge,kriCards,multiLine,areaLine,scatterXY,scatter45,pnlChart,calheat,histogram,legend,tableToggle,autoChart,toneGlyph,fullFrame,PREF,DOMAIN_CHARTS};
NG.charts=API;
Object.assign(window,API);
})();
