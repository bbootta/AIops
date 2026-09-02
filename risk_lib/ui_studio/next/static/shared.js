/* shared.js: helpers used by more than one screens module (design spec 3.10,
   shared_contracts.ng_api.shared). Loaded after charts.js and before every
   screens/*.js; exposed as NG.shared.*. Only NG.ui and NG.charts are used
   (contract only). Every authored string is a Korean catalogue key passed
   through T(); ledger values, table names, physical column names, catalog
   labels, citations and form codes are printed verbatim. No screens/*.js may
   define a function with any of these five names (A21). */
(function(){
'use strict';
const NG=window.NG,U=NG.ui,el=U.el,ap=U.ap,T=NG.T,TF=NG.TF,fmt=NG.fmt;
const D=()=>NG.D;
const raw=v=>(v==null||v==='')?'-':String(v);
function th(tr,lab,phys,num){const h=el('th',num?'num':null,T(lab));if(phys)h.title=phys;ap(tr,h);return h}
function tbl(){const w=el('div','tw'),t=el('table'),hd=el('thead'),tr=el('tr'),tb=el('tbody');ap(hd,tr);ap(t,hd,tb);ap(w,t);return {w,tr,tb}}
/* ---- renderForm(root, form, {showSub}) ----
   Form detail for reg-forms, market-rwa, op-rwa. Clears root like the legacy
   pane and draws one card: header [form_no] form_name, meta line, an
   internal-code badge when the form number is not the issued one, then the
   line table (code, name indented by level, level, unit, value, formula,
   citation, module). Subtotal lines get tr.sub; showSub false drops them.
   Ratio units are shown as percent with four decimals, as the legacy did. */
function renderForm(root,form,o){o=o||{};root.innerHTML='';const f=form||{},c=el('div','card form');
  const h=el('h3',null,'['+raw(f.form_no)+'] '+raw(f.form_name));if(!f.official)ap(h,' ',U.badge(T('내부 배정'),'warn'));ap(c,h);
  ap(c,el('div','meta',[raw(f.section),T('내부 ID')+' '+raw(f.form_id),T('제출주기')+' '+raw(f.frequency),T('근거')+' '+raw(f.citation)].join(' · ')));
  const {w,tr,tb}=tbl();
  th(tr,'코드','code');th(tr,'항목','name');th(tr,'단계','level',true);th(tr,'단위','unit');th(tr,'값','value',true);th(tr,'산식','formula');th(tr,'규정 근거','citation');th(tr,'코드 모듈','module');
  (f.lines||[]).forEach(ln=>{if(ln.subtotal&&o.showSub===false)return;
    const x=el('tr',ln.subtotal?'sub':null),lv=ln.level||0;x.dataset.level=lv;
    let v=ln.value;v=ln.unit==='ratio'&&typeof v==='number'?fmt.pct(v,4):typeof v==='number'?fmt.num(v):raw(v);
    const nm=el('td',null,raw(ln.name));nm.style.paddingLeft=(8+lv*16)+'px';
    ap(x,el('td',null,raw(ln.code)),nm,el('td','num',fmt.int(lv)),el('td',null,raw(ln.unit)),el('td','num',v),el('td',null,raw(ln.formula)),el('td',null,raw(ln.citation)),el('td',null,raw(ln.module)));ap(tb,x)});
  ap(c,w);ap(root,c);return c}
/* ---- domainBrowser(root, product, {tables, docket}) ----
   Catalog browser for the domain screens (rdm, credit, credit-rwa, ecl,
   market, oprisk, alm). Lists every D.catalog row of the product (catalog
   order), then the x_screens ledgers of the active screen that carry the
   product, then the extra table names, deduplicated by name. Every physical
   table name is printed in the list (A8 census). Picking a row draws the
   detail card: grain, pk, fk hops, product chip, autoChart (charts.js refuses
   truncated frames itself; the reason is printed here) and the preview table
   with catalog labels and th.title physical names. docket, when given, is a
   node (or a function of the box) placed above the browser. */
function domainBrowser(root,product,o){o=o||{};const d=D(),catRows=d.catalog||[],seen={},rows=[];
  const add=(name,c,l)=>{if(!name||seen[name])return;seen[name]=1;const f=d.data&&d.data[name];
    rows.push({name:name,korean:(c&&c.korean)||(l&&l.korean)||null,product:(c&&c.product)||(l&&l.product)||null,grain:c?c.grain:null,pk:c?c.pk:(l&&l.pk?l.pk.join(', '):null),
      cols:c?c.columns:(f?f.columns.length:null),total:c?c.rows:(l?l.total:(f?f.total:null)),cat:c})};
  catRows.forEach(c=>{if(c.product===product)add(c.name,c,null)});
  const xs=(d.x_screens||{})[NG.route().id];((xs&&xs.ledgers)||[]).forEach(l=>{if(l.product===product||(o.tables||[]).indexOf(l.table)>=0)add(l.table,NG.cat(l.table),l)});
  (o.tables||[]).forEach(n=>add(n,NG.cat(n),null));
  const box=el('div','domain');box.dataset.product=product||'';
  if(o.docket)ap(box,typeof o.docket==='function'?o.docket(box):o.docket);
  const prods=[];rows.forEach(r=>{const p=r.product||'';if(prods.indexOf(p)<0)prods.push(p)});
  let pick='';const list=el('div','list'),pane=el('div','pane');
  const nT=rows.length,nR=rows.reduce((s,r)=>s+(r.total||0),0);
  const head=el('div','trow');ap(head,el('span','lab',T('연결 원장')),' ',el('span','meta',TF('테이블 {n}장 · {rows}행',{n:nT,rows:nR})));
  if(prods.length>1)ap(head,U.chips([{value:'',label:'전체',on:true}].concat(prods.map(p=>({value:p,label:p||T('카탈로그 외 · 엔진 산출'),raw:true}))),v=>{pick=v;fill()}));
  else ap(head,el('span','chip prod',product||T('카탈로그 외 · 엔진 산출')));
  ap(box,head);const split=el('div','split');ap(split,list,pane);ap(box,split);ap(root,box);
  function detail(r){pane.innerHTML='';const c=el('div','card dom');const h=el('h3');ap(h,(r.korean?r.korean+' · ':''),el('code',null,r.name),' ',U.productChip(r.cat?r.name:null));ap(c,h);
    if(r.grain)ap(c,el('div','meta',T('입도')+' ('+r.grain+')'));
    const fk=NG.fkOf(r.name).map(k=>k.column+' → '+k.ref_table+'.'+k.ref_column).join(' · ');
    ap(c,el('div','meta',[T('기본키')+' '+raw(r.pk),T('외래키')+' '+(fk||'-'),T('컬럼')+' '+fmt.int(r.cols)].join(' · ')));
    const f=(d.previews&&d.previews[r.name])||(d.data&&d.data[r.name]);
    if(!f){ap(c,U.note(T('원장 행 없음'),'warn'));ap(pane,c);return}
    const full=NG.frame.full(r.name),ch=full?NG.charts.autoChart(full,{name:r.name,korean:r.korean||r.name}):null;
    if(ch){const cb=el('div','chartbox');ap(cb,ch);ap(c,cb)}
    else if(!full){const src=(d.data&&d.data[r.name])||f;ap(c,el('div','meta',T('차트는 전량 프레임에서만 그린다')+' · '+TF('표본 {n}/{N}행',{n:src.shown,N:src.total})))}
    ap(c,U.table(f,{title:null}));ap(pane,c)}
  function fill(){list.innerHTML='';let first=null;rows.forEach(r=>{if(pick&&(r.product||'')!==pick)return;
    const b=el('button');b.type='button';ap(b,r.korean||r.name,el('small'));const s=b.lastChild;
    ap(s,el('code',null,r.name),' · '+TF('{n}행',{n:r.total||0})+(r.cols!=null?' · '+T('컬럼')+' '+fmt.int(r.cols):''));
    b.onclick=()=>{Array.prototype.forEach.call(list.children,x=>x.classList.remove('on'));b.classList.add('on');detail(r)};ap(list,b);if(!first)first=b});
    if(first)first.click();else{pane.innerHTML='';ap(pane,U.note(T('연결 원장 없음'),'warn'))}}
  fill();return box}
/* evidence_status tone: the single tone map first (evidence_node.status
   vocabulary); 미확인 is an unknown, so it is blocked (spec 4.5); an empty
   cell is not run; anything else stays neutral and is printed verbatim. */
function evTone(v){if(v==null||v==='')return 'not-run';const t=NG.tone('evidence_node.status',v);return t!=='neutral'?t:(v==='미확인'?'blocked':'neutral')}
/* ---- almEvidence(root, items) ----
   items: [{ledger, rows, approved_on, evidence_status, citation}]. One card:
   ledger name, row count, approval date, evidence status badge, citation.
   Missing rows (null) print as -, never as 0. */
function almEvidence(root,items){const c=el('div','card evidence');ap(c,el('h3',null,T('근거 상태 (원장 evidence_status 그대로)')));
  const {w,tr,tb}=tbl();th(tr,'원장','ledger');th(tr,'행수','rows',true);th(tr,'승인일','approved_on');th(tr,'근거 판정','evidence_status');th(tr,'규정 근거','citation');
  (items||[]).forEach(it=>{const t=evTone(it.evidence_status),x=el('tr',t==='neutral'||t==='good'?null:t);x.dataset.tone=t;
    const ld=el('td'),ev=el('td');ap(ld,el('code',null,raw(it.ledger)));ap(ev,U.badge(it.evidence_status==null||it.evidence_status===''?T('값 없음'):String(it.evidence_status),t));
    ap(x,ld,el('td','num',it.rows==null?'-':fmt.int(it.rows)),el('td',null,raw(it.approved_on)),ev,el('td',null,raw(it.citation)));ap(tb,x)});
  ap(c,w,el('div','meta',T('미확인은 1차자료를 확인하지 못한 값이다. 엔진은 그 조정을 건너뛰고 원장은 칸을 비워 둔다. 화면도 채우지 않는다.')));ap(root,c);return c}
/* ---- almSources(root, items) ----
   items: [{name, source, kind}]. 계수 출처 card: name, source (a catalog
   table gets its Korean label beside the physical name), kind. */
function almSources(root,items){const c=el('div','card sources');ap(c,el('h3',null,T('계수 출처')));
  const {w,tr,tb}=tbl();th(tr,'명칭','name');th(tr,'출처','source');th(tr,'종류','kind');
  (items||[]).forEach(it=>{const x=el('tr'),s=el('td'),cat=NG.cat(it.source);ap(s,el('code',null,raw(it.source)),cat?' '+cat.korean:null);
    ap(x,el('td',null,raw(it.name)),s,el('td',null,raw(it.kind)));ap(tb,x)});
  ap(c,w);ap(root,c);return c}
/* ---- judgeGlyph(value) ----
   Glyph plus word. Tone from NG.tone('judge', value) when the tone map has a
   judge vocabulary; until it does, 통과 is good, 미통과 is bad and any other
   status text (a judgement that was not made) is not run. Only the two
   catalogued words are translated; a ledger status is printed verbatim. */
const JUDGE={'통과':'good','미통과':'bad'};
function judgeGlyph(v){const s=el('span','judge');let t,word;
  if(v==null||v===''){t='not-run';word=T('값 없음')}
  else{t=NG.tone('judge',v);if(t==='neutral')t=JUDGE[v]||'not-run';word=JUDGE[v]?T(v):String(v)}
  s.dataset.tone=t;s.classList.add(t);ap(s,NG.glyph(t),' '+word);return s}
Object.assign(NG.shared,{renderForm,domainBrowser,almEvidence,almSources,judgeGlyph});
})();
