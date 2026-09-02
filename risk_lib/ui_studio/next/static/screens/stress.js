/* screens/stress.js: 위기상황·ICAAP 6화면 */
/* (위기상황 · 거시지표 모니터링 · 시나리오 설정 · 역스트레스 · ICAAP 인벤토리 · 경영조치·제출) */
/* 규칙 (설계 사양 2.8·5·6장, 수용기준 A7·A8·A12·A21): */
/* - 총계는 프레임 total 과 x_ 서버 객체에서 읽는다. 화면이 센 행수를 총계로 찍지 않는다. */
/* - 색은 NG.tone(원장 어휘, 값) 하나로만 정한다. x_severity 에 어휘가 없는 값 */
/*   (요구치 충족·중요성 등급·이탈 경보)은 색을 붙이지 않고 값만 적는다. */
/* - 표 머리글은 카탈로그 한글명이고 단계명·산식·투입값·인용·시나리오명은 원장 값 */
/*   그대로다. 저자가 쓴 문장만 T·TF 로 지난다. */
/* - 공용 도우미(renderForm·domainBrowser·almEvidence·almSources·judgeGlyph)는 */
/*   shared.js 만 정의한다. */
(function(){
'use strict';
const NG=window.NG,U=NG.ui,CH=NG.charts,FR=NG.frame,el=U.el,ap=U.ap;
const T=NG.T,TF=NG.TF,fmt=NG.fmt,IX=FR.frameIdx;
const GRP='위기상황·ICAAP',SUB='위기상황';
const MT=t=>el('div','meta',t);
const NO=(t,tn)=>U.note(t,tn);
const G=(c,n)=>(c.D.data||{})[n]||null;
const CK=n=>{const r=NG.cat(n);return (r&&r.korean)||n};
/* 컬럼 한글명은 카탈로그 라벨이다. 번역하지 않고 그대로 쓴다. */
const CL=(f,k)=>FR.colLabel(f,IX(f)[k]);
const CO=(f,k)=>({key:k,label:CL(f,k),raw:true,phys:k});
/* base.css 가 section{display:none} 이라 펼친 카드는 div 로 만든다. */
const SQ=(k,x)=>{const c=el('div','card sec');ap(c,el('h3',null,T(k)+(x?' · '+x:'')));return c};
const LEAD=(root,k)=>ap(root,el('p','lead',T(k)));
function tcard(c,n,o){o=o||{};o.title=CK(n);o.raw=true;return U.table(G(c,n),o)}
/* 단위는 추적표의 unit 컬럼 값이다. 화면이 단위를 정하지 않는다. */
function uv(v,u){if(v==null)return '-';if(u==='KRW')return fmt.money(v);
  if(u==='ratio')return fmt.pct(v,2);return fmt.num(v)}
function uniq(f,col){const i=IX(f)[col],out=[];
  f.rows.forEach(r=>{if(out.indexOf(r[i])<0)out.push(r[i])});return out}
/* 3선 재계산 대상. 판정·수치는 x_screen_gate.targets 그대로다. */
function tgt(c,fv){
  const rows=((c.D.x_screen_gate||{}).targets||{})[c.id]||[];
  if(!rows[0])return null;
  return U.kpiRow(rows.map(r=>U.kpi({label:r.korean,raw:true,value:fv(r.reported),
    sub:T('상시 독립검증 (3선) 재계산 대상')+' '+r.target+' · '+r.citation,
    tone:NG.tone('recalc.state',r.state),badge:r.state,
    lineage:NG.lineage.byTarget(r.target)})),c.meta.density)}

/* ══════════════ 위기상황 (leaf-parent) ══════════════════════════════ */
/* 단계명은 추적표 step 컬럼의 값이다. 조회 키로만 쓰고 번역하지 않는다. */
const CET1='보통주자본비율',PASS='요구치 충족';
const CMP=['충격 심도 (severity)','PD (충격 후)','LGD (충격 후)','충당금 전입',
  '트레이딩 손익 합계','운영손실 (연간)','당기순이익','위험가중자산 합계',
  '유동성커버리지비율',CET1,'총자본비율',PASS];
const PROP=['트레이딩 손익 합계','ΔEVE','내부손실승수 (ILM)','유동성커버리지비율',
  '당기순이익','산출하한 증가분'];
function pick(f){const i=IX(f);return (s,q,st)=>{
  const r=f.rows.find(x=>x[i.scenario]===s&&x[i.quarter]===q&&x[i.step]===st);
  return r?r[i.value]:null}}
/* 자본비율 경로. 요구선은 sim.required, 빗금은 추적표의 요구치 충족 값이다. */
function pathChart(c,f,sc){
  const scen=uniq(f,'scenario'),quar=uniq(f,'quarter'),v=pick(f);
  const req=((c.D.sim||{}).required)||{};
  return CH.multiLine(scen.map(s=>({name:s,values:quar.map(q=>v(s,q,CET1))})),quar,{
    title:T('보통주자본비율 경로 · 심각도별'),fmt:x=>fmt.pct(x,2),src:f,
    hatch:sc?quar.map(q=>v(sc,q,PASS)===0):null,
    rules:[{value:req.cet1,label:'CET1 '+T('소요 자본 선')}],
    note:T('빗금 친 분기는 요구치 미달이다')})}

function stressMain(root,c){
  const f=G(c,'st_calc_trace');
  if(!f){ap(root,NO(T('연결 원장 없음'),'warn'));return}
  const i=IX(f),v=pick(f),xc=c.D.x_capital||{};
  LEAD(root,'14개 충격 축(신용 5 · 시장 4 · 운영 1 · 유동성 2 · 수익 2)이 같은 심도에서 동시에 발동하고, 신용파라미터 → 신용RWA → 시장 → 은행계정금리 → 운영 → 유동성 → 손익 → 자본 → RWA합계 → 비율 → 판정으로 전이되는 전 과정을 심각도별·분기별로 펼친다. 각 단계는 산식·투입값·규정 근거를 함께 가지며, 마지막 단계 값은 스트레스 경로 결과와 정확히 일치한다.');
  const tg=tgt(c,x=>fmt.pct(x,2));if(tg)ap(root,tg);
  const scen=uniq(f,'scenario'),quar=uniq(f,'quarter'),fold={};
  const unit=st=>{const r=f.rows.find(x=>x[i.step]===st);return r?r[i.unit]:null};
  const cite=st=>{const r=f.rows.find(x=>x[i.step]===st);return r?r[i.citation]:''};
  /* 저점 분기 = 선택 시나리오의 보통주자본비율 최솟값 분기 */
  function trough(s){let b=null,bv=null;
    f.rows.forEach(r=>{if(r[i.scenario]===s&&r[i.step]===CET1&&(bv===null||r[i.value]<bv)){
      bv=r[i.value];b=r[i.quarter]}});return b}
  let sc=scen[scen.length-1],q=trough(sc)||quar[0];
  const sel=U.select(quar.map(x=>({value:x,label:x,raw:true,selected:x===q})),x=>{q=x;draw()});
  const bar=el('div','toolbar');
  ap(bar,U.chips(scen.map(s=>({value:s,label:s,raw:true,on:s===sc})),
      x=>{sc=x;q=trough(sc)||quar[0];sel.value=q;draw()}),
    sel,U.button(T('저점 분기로'),{onClick:()=>{q=trough(sc)||q;sel.value=q;draw()}}));
  ap(root,bar);
  const pane=el('div');ap(root,pane);
  const cols=[CO(f,'seq'),CO(f,'step'),{key:'val',label:CL(f,'value'),raw:true,phys:'value'},
    CO(f,'unit'),CO(f,'formula'),CO(f,'inputs'),CO(f,'citation')];
  function draw(){
    pane.innerHTML='';
    const cmp=SQ('심각도 비교',q);
    ap(cmp,U.simpleTable([{key:'s',label:CL(f,'scenario'),raw:true,phys:'scenario'}].concat(
        CMP.map((st,k)=>({key:'v'+k,label:st,raw:true}))),
      scen.map(s=>{const o={s:s};CMP.forEach((st,k)=>{o['v'+k]=uv(v(s,q,st),unit(st))});return o}),
      {numeric:false}),U.srcMeta(f));
    ap(pane,cmp,pathChart(c,f,sc));
    if(xc.n_fail_quarters!=null)ap(pane,MT(TF('미통과 분기 {n}건',{n:xc.n_fail_quarters})+
      ' · '+T('구속 계층')+' '+String(xc.binding_tier)));
    const pr=SQ('전이 단계',sc+' · '+q);
    ap(pr,U.kpiRow(PROP.map(st=>U.kpi({label:st,raw:true,value:uv(v(sc,q,st),unit(st)),
      sub:cite(st),delta:false})),c.meta.density));
    ap(pane,pr);
    const steps=f.rows.filter(r=>r[i.scenario]===sc&&r[i.quarter]===q)
      .sort((a,b)=>a[i.seq]-b[i.seq]);
    const blocks=[];steps.forEach(r=>{if(blocks.indexOf(r[i.block])<0)blocks.push(r[i.block])});
    blocks.forEach((bk,bi)=>{
      const rows=steps.filter(r=>r[i.block]===bk),n=rows.length,card=el('div','card');
      const h=el('button','blockhead');h.type='button';
      ap(h,el('span','bnum',('0'+(bi+1)).slice(-2)),' '+bk,el('small',null,TF('{n}단계',{n:n})));
      h.onclick=()=>{fold[bk]=!fold[bk];draw()};
      ap(card,h);
      if(!fold[bk]){
        ap(card,U.simpleTable(cols,rows.map(r=>({seq:r[i.seq],step:r[i.step],
          val:uv(r[i.value],r[i.unit]),unit:r[i.unit],formula:r[i.formula],
          inputs:r[i.inputs],citation:r[i.citation]})),{numeric:false}));
        /* 충격 축 정의는 이 블록의 원장이다. app.py 에서는 데이터모델 탭에만 있었다. */
        if(bk==='충격축')ap(card,tcard(c,'st_shock_axis'));}
      ap(pane,card)});
    const nb=blocks.length,ns=steps.length;
    ap(pane,MT(TF('블록 {n}개 · 단계 {m}개',{n:nb,m:ns})));}
  draw();
  ap(root,NO(T('자본은 세후이익 변화로 롤포워드되며(증분 ECL은 이미 이익에 반영돼 있다), 산출하한 분모도 함께 충격받는다. 추적표의 값은 스트레스 경로 결과와 정확히 일치한다.')));
  const cp=G(c,'st_capital_path');
  if(cp){const ci=IX(cp);ap(root,tcard(c,'st_capital_path',{rowClass:r=>r[ci.passes]?null:'bad'}))}}

/* ══════════════ 거시지표 모니터링 ═══════════════════════════════════ */
/* 지표명·부문·출처·움직이는 축은 지표 마스터 원장의 값이다. 번역하지 않는다. */
function mfmt(v,u){return v==null?'-':fmt.num(v)+(u&&u!=='지수'?u:'')}
function macroMon(root,c){
  const M=c.D.macro;
  if(!M){ap(root,NO(T('연결 원장 없음'),'warn'));return}
  const obs=M.observations,mst=M.master,oi=IX(obs);
  ap(root,el('p','lead',TF('통합위기상황분석 시나리오의 입력이 되는 거시·금융지표 {n}종이다. 부문별 최근값과 이탈 경보, 계열 추이, 그리고 시나리오 가정값이 어느 지표의 어떤 값에서 나왔는지를 같은 원장에서 읽는다.',{n:mst.total})));
  const mix=Object.keys(M.basis_mix||{}).map(k=>k+' '+TF('{n}행',{n:M.basis_mix[k]})).join(' · ');
  ap(root,MT(TF('값의 근거는 {mix} 이다. 이 환경은 외부 통계로 나가는 통신이 막혀 있어 실측 피드가 없다. 출처 기관과 통계표 코드는 실제 계열을 가리키므로, 피드가 열리면 관측치만 교체하면 된다.',{mix:mix})));
  const nal=M.alerts.length,nlk=M.links.length;
  const scens=[];M.links.forEach(x=>{if(scens.indexOf(x.scenario)<0)scens.push(x.scenario)});
  const nsc=scens.length;
  ap(root,U.kpiRow([
    U.kpi({label:'모니터링 지표',value:TF('{n}종',{n:mst.total}),sub:'rdm_macro_indicator_master',delta:false}),
    U.kpi({label:'관측치',value:TF('{n}행',{n:obs.total}),sub:'macro_indicator',delta:false}),
    U.kpi({label:'이탈 경보',value:TF('{n}종',{n:nal}),sub:TF('임계 |z| {z} 이상',{z:M.z_threshold}),delta:false}),
    U.kpi({label:'시나리오 연결',value:TF('{n}종',{n:nsc}),sub:TF('{n}행',{n:nlk})+' · macro_scenario_link',delta:false})],
    c.meta.density));
  /* 1. 이탈 경보 */
  const ac=SQ('이탈 경보 (최근 관측이 자기 계열의 평소 범위를 벗어난 지표)');
  if(!nal)ap(ac,MT(T('원장 행 없음')));
  else ap(ac,U.simpleTable([CO(obs,'name'),CO(obs,'category'),CO(obs,'period'),
      {key:'v',label:CL(obs,'value'),raw:true,phys:'value'},{key:'z',label:'z',raw:true},
      {key:'d',label:CL(mst,'drives'),raw:true,phys:'drives'}],
    M.alerts.map(a=>({name:a.name,category:a.category,period:a.period,
      v:mfmt(a.value,a.unit),z:fmt.num(a.z),d:a.drives})),{numeric:false}));
  ap(ac,MT(T('임계는 계열 자신의 표준편차다. 수준·단위가 지표마다 달라 절대값 임계를 두면 환율만 계속 걸린다.')));
  ap(root,ac);
  /* 2. 부문별 최근값 */
  const tc=SQ('부문별 지표 (최근값)');
  ap(tc,U.simpleTable([CO(obs,'name'),CO(obs,'category'),
      {key:'v',label:CL(obs,'value'),raw:true,phys:'value'},
      {key:'y',label:CL(obs,'yoy'),raw:true,phys:'yoy'},CO(obs,'period'),CO(obs,'freq'),
      CO(obs,'source'),CO(obs,'source_code'),{key:'d',label:CL(mst,'drives'),raw:true,phys:'drives'}],
    M.latest.map(x=>({name:x.name,category:x.category,v:mfmt(x.value,x.unit),
      y:x.yoy==null?'-':fmt.pct(x.yoy,2),period:x.period,freq:x.freq,source:x.source,
      source_code:x.source_code,d:x.drives})),{numeric:false}));
  ap(tc,MT(T('전년동기대비는 1년 전 값 대비 비율 변화다. 수준이 %인 지표도 같은 기준으로 계산한다.')),U.srcMeta(obs));
  ap(root,tc);
  /* 3. 계열 추이 */
  const sc=SQ('계열 추이'),spane=el('div');
  const ssel=U.select(M.latest.map(x=>({value:x.indicator_id,label:x.category+' · '+x.name,raw:true})),()=>ser());
  const stb=el('div','toolbar');ap(stb,ssel);ap(sc,stb,spane);
  function ser(){
    spane.innerHTML='';
    const id=ssel.value,m=M.latest.find(x=>x.indicator_id===id);
    const rows=obs.rows.filter(r=>r[oi.indicator_id]===id),np=rows.length;
    if(!m||!np){ap(spane,MT(T('원장 행 없음')));return}
    ap(spane,CH.multiLine([{name:m.name,values:rows.map(r=>r[oi.value])}],
      rows.map(r=>r[oi.period]),{title:T('계열 추이')+' · '+m.name+' ('+m.unit+')',
      fmt:x=>mfmt(x,m.unit),src:obs}));
    ap(spane,MT(TF('{n}기 · 주기 {freq} · 최근값 {v} · 전년동기대비 {yoy} · 출처 {src} {code} · 근거 {basis} · 움직이는 축 {drives}',
      {n:np,freq:m.freq,v:mfmt(m.value,m.unit),yoy:m.yoy==null?'-':fmt.pct(m.yoy,2),
       src:m.source,code:m.source_code,basis:m.basis,drives:m.drives})));
    const al=M.alerts.find(a=>a.indicator_id===id);
    if(al)ap(spane,NO(TF('이탈 경보. 최근값이 직전 구간 평균에서 표준편차의 {z}배만큼 떨어져 있다.',{z:al.z})));}
  ser();ap(root,sc);
  /* 4. 시나리오 연결 */
  const lc=SQ('시나리오 연결 (가정값이 어느 지표에서 나왔나)');
  ap(lc,MT(T('시나리오 가정값은 최근 관측값에 배수와 그 지표의 분기 변동성을 곱해 더한 값이다. 배수를 표준편차 단위로 두는 이유는, 수준이 다른 지표를 같은 비율로 때리면 환율과 실업률이 같은 충격을 받은 셈이 되기 때문이다.')));
  const lk=G(c,'macro_scenario_link'),shk=G(c,'st_macro_scenario_shock');
  let scen=scens[scens.length-1];
  const lpane=el('div');
  ap(lc,U.chips(scens.map(s=>({value:s,label:s,raw:true,on:s===scen})),x=>{scen=x;links()}),lpane);
  function links(){
    lpane.innerHTML='';
    const rows=M.links.filter(x=>x.scenario===scen),nr=rows.length;
    const moved=rows.filter(x=>x.sigma!=null&&x.sigma!==0)
      .sort((a,b)=>Math.abs(b.sigma)-Math.abs(a.sigma)),nm=moved.length;
    if(nm)ap(lpane,CH.hbars(moved.map(x=>({label:x.name,value:x.sigma,
      sub:mfmt(x.latest,x.unit)+' → '+mfmt(x.scenario_value,x.unit)})),
      {title:T('충격 배수 (표준편차 단위, 음수는 하락, 양수는 상승)'),money:false,fmt:x=>fmt.num(x)}));
    else{const nu=rows.filter(x=>x.sigma==null).length;
      ap(lpane,MT(nu?TF('배수가 원장에 없는 지표 {n}종. 값을 채우지 않는다.',{n:nu})
        :T('충격 없음. 관측값을 그대로 가정값으로 쓴다.')))}
    ap(lpane,U.simpleTable([{key:'name',label:CL(lk,'name'),raw:true,phys:'name'},
        {key:'l',label:CL(lk,'latest'),raw:true,phys:'latest'},
        {key:'s',label:CL(lk,'scenario_value'),raw:true,phys:'scenario_value'},
        {key:'k',label:CL(lk,'shock'),raw:true,phys:'shock'},
        {key:'g',label:CL(shk,'multiplier'),raw:true,phys:'multiplier'},
        {key:'d',label:CL(lk,'drives'),raw:true,phys:'drives'}],
      rows.map(x=>({name:x.name,l:mfmt(x.latest,x.unit),s:mfmt(x.scenario_value,x.unit),
        k:mfmt(x.shock,x.unit),g:x.sigma==null?'-':fmt.num(x.sigma),d:x.drives})),{numeric:false}));
    ap(lpane,MT(TF('{s} {n}행',{s:scen,n:nr})));}
  links();ap(root,lc);
  ap(root,tcard(c,'macro_scenario_link'),tcard(c,'st_macro_scenario_shock'));
  ap(root,tcard(c,'rdm_macro_indicator_master'));
  ap(root,MT(T('지표 목록·출처 코드·움직이는 축은 마스터 원장이 정한다. 화면과 엔진이 같은 원장을 읽으므로 지표를 늘리면 두 곳이 함께 바뀐다.')));}

/* ══════════════ 시나리오 설정 ═══════════════════════════════════════ */
function scenarioSet(root,c){
  const f=G(c,'st_calc_trace');
  if(!f){ap(root,NO(T('연결 원장 없음'),'warn'));return}
  const i=IX(f),card=el('div','card set-scenario');
  ap(card,el('h3',null,T('위기상황 시나리오 설정 (충격 축 파라미터)')));
  /* 축별 단위충격은 산식 문자열에서 읽는다. 추적표가 정본이고, 여기 따로 적으면 두 벌이 갈라진다. */
  const axes=[],seen={};
  f.rows.forEach(r=>{
    if(r[i.block]!=='충격축'||seen[r[i.step]])return;
    seen[r[i.step]]=1;
    const m=/단위충격\(([-0-9.]+)\s*([^)]+)\)/.exec(String(r[i.formula]||''));
    axes.push({step:r[i.step],unit:m?m[2]:r[i.unit],base:m?parseFloat(m[1]):null})});
  const na=axes.length;
  ap(card,MT(TF('충격 축 {n}종의 단위충격과 심도 구조를 편집해 변경 제안서를 만든다. 화면은 재계산하지 않는다. 시나리오 파라미터는 RWA·비율·판정 전체에 전이되므로, 적용은 파이프라인 재실행과 검증 두 층을 다시 거쳐야 한다.',{n:na})));
  const inputs={};
  ap(card,U.simpleTable([{key:'step',label:CL(f,'step'),raw:true,phys:'step'},
      {key:'unit',label:CL(f,'unit'),raw:true,phys:'unit'},
      {key:'base',label:'현행 단위충격'},{key:'in',label:'제안 단위충격'}],
    axes.map(a=>{const inp=U.input({placeholder:T('유지'),aria:a.step});inputs[a.step]=inp;
      return {step:a.step,unit:a.unit,base:a.base==null?'-':fmt.num(a.base),in:inp}}),
    {numeric:false}));
  /* 심도는 분기마다 다르고 정점까지 선형 상승한다. 정점(최대) 심도를 뽑는다. */
  const scen=uniq(f,'scenario'),peak={};
  scen.forEach(s=>{let mx=null;
    f.rows.forEach(x=>{if(x[i.scenario]===s&&/심도/.test(String(x[i.step]))&&typeof x[i.value]==='number')
      mx=(mx===null||x[i.value]>mx)?x[i.value]:mx});peak[s]=mx});
  ap(card,MT(T('시나리오별 정점 심도')+' '+scen.map(s=>s+' '+(peak[s]==null?'-':fmt.num(peak[s]))).join(' · ')+
    ' · '+T('분기별 심도는 정점까지 선형 상승한다')));
  const KDOM='E · 통합위기상황분석',kill=c.killedFor(KDOM);
  const err=el('div','note bad');err.hidden=true;
  const out=el('pre','mono');out.style.whiteSpace='pre-wrap';
  const acts=el('div','toolbar');
  ap(acts,U.button(T('변경 제안 생성'),{primary:true,disabled:kill,onClick:()=>{
    err.hidden=true;out.textContent='';
    if(c.killedFor(KDOM)){err.textContent=T('비상정지 (실행 차단)');err.hidden=false;return}
    const changes=[],bad=[];
    axes.forEach(a=>{
      const raw=String(inputs[a.step].value||'').trim();
      if(!raw)return;
      if(!/^-?[0-9]+(?:\.[0-9]+)?$/.test(raw)){bad.push(a.step+": '"+raw+"' ("+T('숫자가 아니다')+')');return}
      changes.push({axis:a.step,unit:a.unit,from:a.base,to:parseFloat(raw)})});
    const nbad=bad.length,nch=changes.length;
    if(nbad){err.textContent=T('검증 실패')+' ('+bad.join(' · ')+')';err.hidden=false;return}
    if(!nch){err.textContent=T('변경된 축이 없다');err.hidden=false;return}
    out.textContent=JSON.stringify({proposal:T('위기상황 시나리오 충격 축 변경'),
      asof:c.D.meta.asof,run_id:c.D.meta.run_id,changes:changes,
      impact:[T('신용파라미터부터 판정까지 전 단계'),T('업무보고서 위기상황 서식'),
        T('자본계획·회복계획 연계 경보')],
      apply_path:'risk_lib/stress/axes.py',
      procedure:[T('코드 반영'),T('파이프라인 재실행'),T('자체검증(2선) FAIL 0 확인'),
        T('독립검증(3선) 재요청'),T('게이트 통과 후 결재')],
      note:T('화면은 재계산하지 않는다')},null,2)}}));
  ap(card,acts,err,out);
  if(kill)ap(card,NO(T('비상정지 (실행 차단)'),'blocked'));
  ap(root,card);
  ap(root,pathChart(c,f,null));
  ap(root,MT(T('경로는 현행 파라미터의 산출 결과다. 제안은 이 경로를 바꾸지 않는다.')));}

/* ══════════════ 역스트레스 ══════════════════════════════════════════ */
function reverseStress(root,c){
  const r=c.D.reverse_stress;
  if(!r){ap(root,NO(T('연결 원장 없음'),'warn'));return}
  LEAD(root,'자본 임계를 뚫는 충격 심도를 역산한다. 값은 파이프라인 산출이며 화면에서 계산하지 않는다.');
  const tg=tgt(c,x=>fmt.num(x));if(tg)ap(root,tg);
  const mins=((c.D.sim||{}).minimums)||{},met=String(r.metric).toUpperCase();
  ap(root,U.kpiRow([
    U.kpi({label:'대상 지표',value:met,sub:T('임계 비율')+' '+fmt.pct(r.target_ratio,2),delta:false}),
    U.kpi({label:'현행 비율',value:fmt.pct(r.base_ratio,2),
      sub:T('최저 기준')+' '+fmt.pct(mins[r.metric],2),delta:false}),
    U.kpi({label:'임계 심도',value:fmt.num(r.critical_severity),
      sub:T('수렴 여부')+' '+(r.converged?T('수렴'):T('미수렴')),delta:false}),
    U.kpi({label:'파열점 비율',value:fmt.pct(r.ratio_at_break,3),delta:false}),
    U.kpi({label:'함의 국내총생산 충격',value:fmt.pct(r.implied_gdp_shock,2),delta:false})],
    c.meta.density));
  ap(root,U.meter(T('임계 심도'),Math.min(r.critical_severity,1),1));
  ap(root,MT(T('기준값의 출처')+' reverse_stress · sim.minimums'));
  /* 엔진 산출이라 원장 표가 없다. table=null 이므로 카탈로그 외 칩이 붙는다. */
  const rows=[[T('수렴 여부'),r.converged?T('수렴'):T('미수렴')],
    [T('임계 심도'),fmt.num(r.critical_severity)],
    [T('파열점 비율'),fmt.pct(r.ratio_at_break,3)],
    [T('파열점 위험가중자산'),fmt.money(r.rwa_at_break)],
    [T('파열점 기대신용손실'),fmt.money(r.ecl_at_break)],
    [T('함의 국내총생산 충격'),fmt.pct(r.implied_gdp_shock,2)],
    [T('함의 부도시손실률 가산'),fmt.pp(r.implied_lgd_addon*100)]];
  const nr=rows.length;
  ap(root,U.table({table:null,columns:['item','value'],labels:[T('항목'),T('값')],
    rows:rows,shown:nr,total:nr},{title:'파열점의 산출 상태',filter:false}));
  ap(root,NO(T('심도 1.0 미만에서 임계가 뚫리면(임계 심도 < 1) 심각 시나리오보다 약한 충격에도 요구비율을 지키지 못한다는 뜻이다. 자본계획·회복계획 연계 대상.')));
  ap(root,MT(T('역산은 자본 임계 비율을 목표로 심도를 이분 탐색해 얻는다. 파열점의 위험가중자산과 기대신용손실은 그 심도에서의 산출값이며, 함의 충격은 그 심도를 거시 축으로 환산한 값이다.')));}

/* ══════════════ ICAAP 인벤토리 ══════════════════════════════════════ */
function icaap(root,c){
  LEAD(root,'리스크를 빠짐없이 세우고 중요성을 판정해 내부자본에 잇는 원장이다.');
  const ic=((c.D.sim||{}).icaap)||{};
  ap(root,U.kpiRow([
    U.kpi({label:'내부자본 가용자본',value:fmt.money(ic.available_capital),delta:false}),
    U.kpi({label:'내부자본 소요액',value:fmt.money(ic.ec),delta:false}),
    U.kpi({label:'내부자본 여유',value:fmt.money(ic.buffer),delta:false}),
    U.kpi({label:'내부자본 소진율',value:fmt.pct(ic.utilisation,2),delta:false})],c.meta.density));
  ap(root,CH.gauge(ic.ec,ic.available_capital,{title:T('내부자본 소진율'),fmt:x=>fmt.money(x)}));
  ap(root,MT(T('소진율은 소요액을 가용자본으로 나눈 값이며 모형 산출이다. 이 화면은 다시 계산하지 않는다.')));
  ap(root,tcard(c,'icaap_risk_taxonomy'),tcard(c,'icaap_materiality'),
    tcard(c,'icaap_materiality_policy'),tcard(c,'icaap_capital_map'));
  ap(root,MT(T('중요성 등급은 판정 정책 원장의 축과 기준값, 그리고 중요 판정 최소 초과 축 수로 결정된다. 등급이 자본 매핑의 부과 구분을 정하고, 잠정 사유가 남은 행은 매핑이 확정되지 않은 것이다.')));}

/* ══════════════ 경영조치·제출 ═══════════════════════════════════════ */
function actions(root,c){
  LEAD(root,'위기상황에서 무엇을 발동하기로 했는지와 실제 발동 기록, 그리고 감독 제출 이력이다.');
  const sub=((c.D.x_gate||{}).submission)||{},ks=['draft','reviewed','approved','submitted'];
  const box=el('div','chips');
  ks.forEach(k=>ap(box,U.badge(k+' '+fmt.int(sub[k]),NG.tone('reg_submission.status',k))));
  ap(box,U.badge(TF('전량 {N}',{N:sub.total}),'neutral'));
  ap(root,box);
  ap(root,CH.bars(ks.map(k=>({label:k,value:sub[k]})),
    {title:T('제출 상태 분포'),fmt:x=>fmt.int(x),note:T('상태별 건수는 x_gate.submission 서버 집계다')}));
  ap(root,NO(T('합성 파이프라인은 submitted 를 부여하지 않는다. 제출 상태는 마감 워크플로의 제출 단계에서만 바뀐다.')));
  const bar=el('div','toolbar');
  ap(bar,U.button(T('마감 워크플로'),{onClick:()=>c.go('close-workflow')}));
  ap(root,bar);
  ap(root,tcard(c,'st_action_playbook'),tcard(c,'st_management_action'),tcard(c,'reg_submission'));
  ap(root,MT(T('발동표는 발동 지표와 임계, 승인 주체와 소요 기간을 정한다. 발동 기록은 시나리오·분기별로 임계를 미달한 사실과 그 사유를 남기며, 자본효과 가정이 없는 조치는 경로에 반영하지 않는다.')));}

NG.screen('stress',{group:GRP,sub:null,title:'위기상황',build:stressMain});
NG.screen('macro',{group:GRP,sub:SUB,title:'거시지표 모니터링',build:macroMon});
NG.screen('scenario',{group:GRP,sub:SUB,title:'시나리오 설정',build:scenarioSet});
NG.screen('reverse-stress',{group:GRP,sub:SUB,title:'역스트레스',build:reverseStress});
NG.screen('icaap',{group:GRP,sub:SUB,title:'ICAAP 인벤토리',build:icaap});
NG.screen('actions',{group:GRP,sub:SUB,title:'경영조치·제출',build:actions});
})();
