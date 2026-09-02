// screens/alm.js: ALM·유동성 여덟 화면 (ALM · 금리리스크 · 국내 금리리스크 ·
// 현금흐름 원장 · 유동성 사다리 · 유동성리스크 · 생존기간 · ALM 계수 원장).
//
// 규칙 (설계 사양 2.7·5·6장, 수용기준 A7·A8·A12·A21):
// - 이 파일에는 충격폭·계수·상한·버킷 경계·유출률 같은 수치 리터럴을 두지
// 않는다. 전부 원장 컬럼과 x_ 서버 객체에서 읽는다.
// - 연결 원장 목록·모집단·소관은 셸(provHeader)이 x_screens 로 그린다. 이
// 모듈은 같은 표를 다시 그리지 않고 화면 고유의 고지만 적는다.
// - 건수·총계는 frame.total 과 x_ 객체가 낸다. 잘린 프레임은 근거 집계에서
// 빼고 뺐다는 사실을 적는다. 화면이 센 행수를 총계로 찍지 않는다.
// - 색은 NG.tone(어휘, 값) 하나로만 정한다. x_severity 에 어휘가 없는 값
// (LCR 대사 상태·근거 판정)은 색을 붙이지 않고 값만 적는다.
// - 표 머리글은 카탈로그 라벨(CL·CS)이라 번역하지 않는다. 저자가 쓴 문장만
// T·TF 로 지나고 i18n/ng_alm.py 에 있다.
// - 공용 도우미(almEvidence·domainBrowser)는 shared.js 만 정의한다.
(function(){
'use strict';
const NG=window.NG,U=NG.ui,CH=NG.charts,FR=NG.frame,el=U.el,ap=U.ap;
const T=NG.T,TF=NG.TF,TX=NG.text,fmt=NG.fmt,TN=NG.tone,IX=FR.frameIdx;
const M=fmt.money,P=fmt.pct,N=fmt.num,IT=fmt.int,OD=fmt.orDash;
const GRP='ALM·유동성',SUB='ALM';
/* base.css 가 section{display:none} 이라 펼친 카드는 div 로 만든다. */
const MT=t=>el('div','meta',t),MK=k=>MT(T(k));
const CARD=t=>{const c=el('div','card');if(t)ap(c,el('h3',null,T(t)));return c};
const G=(c,n)=>(c.D.data||{})[n]||null;
const CK=n=>{const r=NG.cat(n);return (r&&r.korean)||n};
const LEAD=(root,k)=>ap(root,el('p','lead',T(k)));
// 컬럼 표시명은 카탈로그 라벨이다. raw 로 넘겨 번역을 타지 않게 하고 물리명을
// th.title 에 남긴다.
const CL=(f,k)=>FR.colLabel(f,IX(f)[k]);
const C=(f,k)=>({label:CL(f,k),raw:true,phys:k});
const CS=(f,s)=>s.split(' ').map(k=>C(f,k));
const ST=(cols,rows,o)=>U.simpleTable(cols,rows,o||{numeric:false});
const RAW=v=>({value:String(v),label:String(v),raw:true});
const NOL=root=>ap(root,U.note(T('연결 원장 없음'),'warn'));
/* 원장 표는 등록된 tables 순서 그대로다. 화면이 목록을 다시 적지 않는다. */
function ledgers(root,c,names){(names||c.meta.tables||[]).forEach(n=>
  ap(root,U.table(G(c,n),{title:CK(n),raw:true})))}
function uniq(f,k){const i=IX(f)[k],o=[];
  f.rows.forEach(r=>{if(o.indexOf(r[i])<0)o.push(r[i])});return o}
function sum(rows,i){let s=0;rows.forEach(r=>{if(typeof r[i]==='number')s+=r[i]});return s}
/* 축 집계. 첫 행(r)을 함께 들고 있어야 대표 컬럼을 원장에서 읽는다. */
function grp(list,kf,vf){const m=[],ix={};
  list.forEach(r=>{const k=kf(r);let e=ix[k];
    if(!e){e=ix[k]={k:k,n:0,v:0,r:r};m.push(e)}
    e.n++;if(vf)e.v+=vf(r)||0});
  return m}
/* 시나리오 순서는 정의 원장이 정한다. 정의에 없는 값(무충격 기준선)이 앞이다. */
function scenOrder(c,list){const d=G(c,'alm_scenario_def'),ord=d?uniq(d,'scenario'):[];
  return list.slice().sort((a,b)=>ord.indexOf(a)-ord.indexOf(b))}
/* 버킷 순서는 seq 컬럼이다. 라벨 문자열로 정렬하면 10y+ 가 1-2y 앞에 온다. */
function bks(f,rows){const i=IX(f);
  return grp(rows,r=>r[i.bucket]).sort((a,b)=>a.r[i.seq]-b.r[i.seq]).map(x=>x.r[i.bucket])}
function picker(root,label,vals,init,fn){const b=el('div','row');
  ap(b,el('span','meta',label),U.select(vals.map(v=>{const o=RAW(v);
    if(v===init)o.selected=true;return o}),fn));
  ap(root,b);return b}
/* 3선 재계산 대상. 판정·수치는 x_screen_gate.targets 그대로다. */
const RATIO={lcr:1,nsfr:1,irrbb_worst_pct_tier1:1},DAYS={survival_days:1};
function tval(t,v){if(v==null)return '-';
  if(RATIO[t])return P(v);if(DAYS[t])return TF('{n}일',{n:v});return M(v)}
function targets(root,c){const ts=((c.D.x_screen_gate||{}).targets||{})[c.id]||[];
  if(!ts[0])return;
  const box=el('div','kpis c4');
  ts.forEach(r=>ap(box,U.kpi({label:r.korean,raw:true,value:tval(r.target,r.reported),
    sub:T('상시 독립검증 (3선) 재계산 대상')+' '+r.target+' · '+TX(String(r.citation)),
    tone:TN('recalc.state',r.state),badge:r.state,lineage:NG.lineage.byTarget(r.target)})));
  ap(root,box)}
// 근거 판정 분포. evidence_status 컬럼을 가진 전량 프레임만 센다. 표본
// 프레임에서 센 건수는 모집단으로 오독되므로 세지 않고 이름만 적는다.
function evidence(root,c,names){const items=[],skip=[];
  (names||c.meta.tables||[]).forEach(n=>{const f=G(c,n);if(!f)return;const i=IX(f);
    if(i.evidence_status===undefined)return;
    if(f.shown<f.total){skip.push(n);return}
    grp(f.rows,r=>r[i.evidence_status]).forEach(e=>items.push({ledger:n,rows:e.n,
      evidence_status:e.r[i.evidence_status],
      approved_on:i.approved_on===undefined?null:e.r[i.approved_on],
      citation:i.citation===undefined?null:TX(String(e.r[i.citation]))}))});
  NG.shared.almEvidence(root,items);
  if(skip[0])ap(root,MT(T('표본 프레임이라 근거 판정을 세지 않은 원장')+' '+skip.join(' · ')))}

/* ══════════════ ALM (leaf-parent) ═══════════════════════════════════ */

// LCR 대사. 세 자리(항목 원장·유출입 원장·결과 원장)의 합계를 나란히 두고
// 상태·상한 출처·허용오차를 x_lcr 이 낸 그대로 적는다. 대사 상태 어휘는
// x_severity 에 없으므로 색을 붙이지 않는다.
function lcrLine(root,c){const x=c.D.x_lcr;if(!x)return;
  const k=CARD('LCR 대사 (원장 합계 대 결과 원장)');
  ap(k,U.note(T('대사 판정')+' '+x.state+(x.reason?' · '+TX(String(x.reason)):'')));
  ap(k,ST(['대사 대상','원장','고유동성자산','총유출','인정 유입','LCR'],[
    [T('항목 원장 합계'),'alm_lcr_item',M(x.item.hqla),M(x.item.outflow),M(x.item.inflow_capped),P(x.item.lcr)],
    [T('유출입 원장 합계'),'alm_lcr_flow · '+x.flow.scenario,M(x.flow.hqla),M(x.flow.outflow),M(x.flow.inflow_capped),P(x.flow.lcr)],
    [T('결과 원장'),'alm_result',M(x.result.numerator),M(x.result.denominator),'-',P(x.result.lcr)]]));
  ap(k,MT(T('차이')+' · '+T('항목 원장 합계')+' / '+T('유출입 원장 합계')+' '+M(x.diff_item_flow)+
    ' · '+T('분자')+' '+M(x.diff_item_result_num)+' · '+T('분모')+' '+M(x.diff_item_result_den)));
  ap(k,MT(T('적용 상한')+' cap_l2b '+P(x.caps.l2b,0)+' · cap_l2 '+P(x.caps.l2,0)+
    ' · cap_inflow '+P(x.caps.inflow,0)+' · '+T('출처')+' '+x.caps.source));
  ap(k,MT(T('허용오차')+' '+x.tolerance.method+' · rel_tol '+x.tolerance.rel_tol));
  ap(root,k)}
function almHome(root,c){
  LEAD(root,'항목별 잔액·적용률·가중 후 금액까지 분해해 규제 비율의 원인을 추적한다.');
  targets(root,c);
  lcrLine(root,c);
  const f=FR.full('alm_lcr_item');
  if(f){const i=IX(f);
    ap(root,CH.hbars(f.rows.map(r=>({label:r[i.section]+' · '+r[i.category],
      value:Math.abs(r[i.weighted]),sub:CL(f,'factor')+' '+P(r[i.factor],0),
      tone:r[i.section]==='OUTFLOW'?'warn':undefined})).sort((a,b)=>b.value-a.value),
      {title:T('유동성커버리지비율 구성 (가중 후 금액)'),src:f}))}
  ap(root,MK('아래는 이 부문 카탈로그 전량이다. 고른 원장의 입도·기본키·외래키·차트·미리보기가 오른쪽에 열린다.'));
  NG.shared.domainBrowser(root,'PRD-ALM',{tables:c.meta.tables||[]});
}

/* ══════════════ 금리리스크 (IRRBB) ══════════════════════════════════ */

// 헤드라인 기준(계약/행동조정)은 종합 원장의 IRRBB_EVE 분자와 맞는 쪽이다.
// 화면이 따로 고르면 콕핏·종합보고서와 다른 기준을 그린다.
function headBasis(f,i,c){const cand=f.rows.filter(r=>r[i.is_worst]);
  if(!cand[0])return f.rows[0][i.basis];
  const a=G(c,'alm_result');
  if(a){const ai=IX(a),row=a.rows.find(r=>String(r[ai.metric]).indexOf('IRRBB_EVE')>=0);
    if(row&&row[ai.numerator]!=null){const nu=Math.abs(row[ai.numerator]);
      const gap=r=>Math.abs(Math.abs(r[i.delta_eve])-nu);
      return cand.reduce((x,r)=>gap(r)<gap(x)?r:x,cand[0])[i.basis]}}
  return cand[0][i.basis]}
const worstOf=(rows,i)=>rows.reduce((a,r)=>
  Math.abs(r[i.delta_eve])>Math.abs(a[i.delta_eve])?r:a,rows[0]);
// 아웃라이어 판정은 산출 원장 컬럼이다. 화면이 임계를 다시 적어 판정하면
// 원장과 화면이 서로 다른 판정을 갖게 된다.
function outlier(root,c,kpi){
  const f=G(c,'alm_irrbb_result');if(!f)return;const i=IX(f);
  const FAIL=rows=>rows.filter(r=>r[i.outlier_test_pass]===false).length;
  if(kpi){const box=el('div','kpis c4');
    uniq(f,'basis').forEach(b=>{const s=f.rows.filter(r=>r[i.basis]===b);
      const w=worstOf(s,i),nf=FAIL(s),nt=s.length;
      ap(box,U.kpi({label:b+' · '+CL(f,'delta_eve_to_tier1'),raw:true,
        value:P(w[i.delta_eve_to_tier1]),tone:nf?'bad':'good',
        sub:w[i.scenario]+' · '+CL(f,'delta_eve')+' '+M(w[i.delta_eve])+' · '+
          CL(f,'tier1')+' '+M(w[i.tier1])+' · '+TF('판정 미통과 {n}/{t} 시나리오',{n:nf,t:nt})}))});
    ap(root,box)}
  const nf=FAIL(f.rows),nt=f.rows.length,w=worstOf(f.rows,i),r0=f.rows[0];
  const k=CARD('아웃라이어 판정');
  ap(k,U.note(TF('판정 미통과 {n}/{t} 시나리오',{n:nf,t:nt})+' · '+
    TF('최대는 {b} 기준 {s}',{b:w[i.basis],s:w[i.scenario]})+' · '+
    CL(f,'delta_eve_to_tier1')+' '+P(w[i.delta_eve_to_tier1]),nf?'bad':'good'));
  const J=v=>NG.shared.judgeGlyph(v==null?null:(v?'통과':'미통과'));
  ap(k,ST(CS(f,'basis scenario delta_eve delta_eve_to_tier1 delta_nii is_worst outlier_test_pass'),
    f.rows.map(r=>[r[i.basis],r[i.scenario],M(r[i.delta_eve]),P(r[i.delta_eve_to_tier1]),
      M(r[i.delta_nii]),r[i.is_worst]?T('최대'):'',J(r[i.outlier_test_pass])])));
  const duty=f.rows.find(r=>r[i.outlier_duty]!=null);
  if(duty)ap(k,U.note(CL(f,'outlier_duty')+': '+TX(String(duty[i.outlier_duty])),'warn'));
  ap(k,MT(CL(f,'framework_version')+' '+r0[i.framework_version]+' ('+r0[i.framework_status]+') · '+
    T('충격 출처')+' '+r0[i.shock_source]+' · '+CL(f,'evidence_status')+' '+r0[i.evidence_status]));
  ap(k,MT(TX(String(r0[i.citation]))),U.srcMeta(f));
  ap(root,k)}
// 충격폭 고지. 프록시 대용과 공란을 화면 위쪽에 적는다. 공란은 두 종류다.
// 폐지된 계정에는 충격표가 없어 비어 있고, 그 외는 1차자료 미확인이다.
function shockDisc(root,c){
  const p=G(c,'alm_rate_shock_param');if(!p)return;const i=IX(p);
  const k=CARD('충격폭의 근거');
  const px=p.rows.filter(r=>r[i.proxy_for_ccy]!=null);
  if(px[0])ap(k,U.note(T('프록시 대용')+' '+px.map(r=>r[i.ccy]+' '+r[i.shock_type]+' '+
    N(r[i.shock_bp])+'bp → '+r[i.proxy_for_ccy]).join(' · ')+'. '+
    T('그 통화의 ΔEVE는 자기 계정 충격폭으로 낸 값이 아니다.'),'bad'));
  const empty=p.rows.filter(r=>r[i.shock_bp]==null);
  const dead=empty.filter(r=>r[i.status]==='폐지'),unk=empty.filter(r=>r[i.status]!=='폐지');
  if(dead[0]){const nd=dead.length;
    ap(k,U.note(TF('폐지 계정 {v} 의 충격폭 {n}칸이 비어 있다. 그 체계에는 통화별 금리충격표가 없다. 이력 보존용이며 산출에 쓰지 않는다.',
      {v:grp(dead,r=>r[i.framework_version]).map(x=>x.k).join(' · '),n:nd})))}
  if(unk[0])ap(k,U.note(TF('충격폭 공란 {v}. 1차자료를 확인하지 못했으므로 값을 지어 채우지 않는다.',
    {v:unk.map(r=>r[i.framework_version]+' '+r[i.ccy]+' '+r[i.shock_type]).join(' · ')}),'bad'));
  ap(k,U.table(p,{title:null}));
  ap(root,k)}
function irrbb(root,c){
  LEAD(root,'은행계정 금리리스크(IRRBB). 6개 금리충격의 ΔEVE와 평행충격 ΔNII를 계약기준·행동조정 두 벌로 낸다. 충격폭의 근거 상태를 화면 위에 함께 적는다.');
  targets(root,c);
  const f=G(c,'alm_irrbb_result');
  if(!f){NOL(root);return}
  const i=IX(f);
  outlier(root,c,false);
  shockDisc(root,c);
  const bases=uniq(f,'basis'),scens=scenOrder(c,uniq(f,'scenario'));
  const at=(b,s)=>f.rows.find(x=>x[i.basis]===b&&x[i.scenario]===s);
  const hc=CARD('계약기준 대 행동조정 (기본자본 대비 ΔEVE)');
  ap(hc,CH.heat(bases.map(b=>scens.map(s=>{const r=at(b,s);
    return r?r[i.delta_eve_to_tier1]:null})),bases,scens,{fmt:v=>P(v),src:f}));
  ap(hc,MK('부호는 원장 그대로다. 음수가 경제적가치 감소다. 계약기준은 비만기예금 전액이 최단 버킷에 있고, 행동조정은 코어를 상한 안에서 장기로 슬로팅한 결과다.'));
  ap(root,hc);
  const pane=el('div');
  picker(root,CL(f,'basis'),bases,headBasis(f,i,c),v=>draw(v));
  ap(root,pane);
  function draw(b){pane.innerHTML='';
    const rows=scens.map(s=>at(b,s)).filter(Boolean);
    if(!rows[0])return;
    const w=rows.find(r=>r[i.is_worst])||rows[0],t1=w[i.tier1];
    const dec=Math.max(-w[i.delta_eve],0),ps=w[i.outlier_test_pass];
    ap(pane,U.kpiRow([
      {label:CL(f,'is_worst'),raw:true,value:w[i.scenario],sub:b+' · is_worst',tone:'warn'},
      {label:CL(f,'delta_eve'),raw:true,value:M(w[i.delta_eve]),
       sub:CL(f,'margin_treatment')+' '+w[i.margin_treatment],tone:w[i.delta_eve]<0?'bad':'good'},
      {label:CL(f,'delta_eve_to_tier1'),raw:true,value:P(w[i.delta_eve_to_tier1]),
       sub:CL(f,'tier1')+' '+M(t1),tone:w[i.delta_eve_to_tier1]<0?'bad':'good',
       lineage:NG.lineage.byTarget('irrbb_worst_pct_tier1')},
      {label:CL(f,'outlier_test_pass'),raw:true,sub:'outlier_test_pass',
       value:ps==null?T('미판정'):(ps?T('통과'):T('미통과')),
       tone:ps==null?'warn':(ps?'good':'bad')}],c.meta.density));
    ap(pane,CH.gauge(dec,t1,{title:T('ΔEVE 감소 대 기본자본(Tier1)'),fmt:M,src:f,
      tone:dec?'bad':'good',
      note:TF('감소액 {a} / 기본자본 {b} = {p}',{a:M(dec),b:M(t1),p:t1?P(dec/t1):'-'})+'. '+
        T('감소가 아닌 시나리오는 0으로 둔다. 아웃라이어 판정 기준값은 원장에 없다.')}));
    ap(pane,CH.bars(rows.map(r=>({label:r[i.scenario],value:r[i.delta_eve],
      tone:r[i.delta_eve]<0?'bad':'good'})),
      {title:T('시나리오별 ΔEVE')+' · '+b,fmt:M,src:f,
       note:T('막대 높이는 절대값이고 색이 부호다. 붉은색이 경제적가치 감소.')}));
    const pv=G(c,'alm_irrbb_bucket_pv');
    if(pv){const pi=IX(pv);
      const sb=pv.rows.filter(r=>r[pi.basis]===b&&r[pi.scenario]===w[i.scenario]);
      if(sb[0])ap(pane,CH.waterfall(bks(pv,sb).map(x=>({label:x,
        delta:sum(sb.filter(r=>r[pi.bucket]===x),pi.delta_pv)})),sum(sb,pi.pv_base),
        {title:T('버킷별 현재가치 효과')+' · '+w[i.scenario]+' · '+b,fmt:M,
         startLabel:CL(pv,'pv_base'),src:pv,
         note:T('시작은 충격 전 순현재가치이고 각 막대는 그 버킷의 충격 전후 차이다. 자산과 부채를 합한 순액이다.')+
           ' '+CL(pv,'margin_treatment')+' '+sb[0][pi.margin_treatment]}))}
    const ni=G(c,'alm_nii_result');
    if(ni){const xi=IX(ni),box=el('div'),n0=ni.rows[0];
      ap(box,CH.bars(ni.rows.map(r=>({label:r[xi.scenario],value:r[xi.delta_nii],
        tone:r[xi.delta_nii]<0?'bad':'good'})),{title:T('ΔNII (평행충격)'),fmt:M,src:ni}));
      const d=G(c,'alm_scenario_def');
      const nn=d?d.rows.filter(r=>r[IX(d).applies_to_nii]).length:null;
      ap(box,MT(CL(ni,'horizon_years')+' '+N(n0[xi.horizon_years])+' · '+
        n0[xi.balance_sheet_assumption]+' · '+CL(ni,'margin_treatment')+' '+n0[xi.margin_treatment]+
        (nn==null?'':' · '+TF('정의 원장이 ΔNII 대상으로 표시한 시나리오 {n}개',{n:nn}))));
      ap(box,MK('ΔNII에는 산출기준(계약·행동조정) 축이 없다. 재가격 시뮬레이션이라 EVE 현금흐름을 재활용하지 않는다.'));
      ap(box,MT(TX(String(n0[xi.citation]))));
      ap(pane,box)}}
  draw(headBasis(f,i,c));
  // 리프라이싱 갭은 금리 재설정 축이다. 잔존만기 축(만기 사다리)은 유동성
  // 사다리 화면에 있다. 두 축을 한 화면에 두면 같은 사다리로 오독된다.
  ledgers(root,c);
  evidence(root,c);
}

/* ══════════════ 국내 금리리스크 [별표 9-1] ══════════════════════════ */

// 산출 통화는 버킷 현재가치 원장에 실제로 나타난 통화다. 화면에 통화를 적어
// 두면 포트폴리오가 바뀌어도 화면만 옛 통화를 그린다.
function krCcy(c){const b=G(c,'alm_irrbb_bucket_pv');if(!b)return null;
  const i=IX(b),m=grp(b.rows,r=>r[i.ccy],r=>Math.abs(r[i.delta_pv]||0));
  m.sort((a,b2)=>b2.v-a.v);return m[0]?m[0].k:null}
function krFramework(root,c){
  const p=G(c,'alm_rate_shock_param');if(!p)return;const i=IX(p);
  const fl=G(c,'alm_post_shock_floor'),fi=fl?IX(fl):null;
  const ccys=uniq(p,'ccy').slice().sort(),home=krCcy(c);
  const cur=ccys.indexOf(home)>=0?home:ccys[0];
  const k=CARD('금리충격 계정 대비 (통화별 <표5>)'),pane=el('div');
  picker(k,T('통화'),ccys,cur,v=>draw(v));
  ap(k,pane,U.srcMeta(p));
  ap(k,MK('상태·시행일·대체 계정·근거 판정은 전부 충격폭 원장 컬럼이다. 어느 계정이 산출에 쓰였는지는 아래 산출 결과의 적용 계정 칸에 있다.'));
  function draw(v){pane.innerHTML='';const rows=[];
    uniq(p,'framework_version').forEach(fv=>{
      const s=p.rows.filter(r=>r[i.framework_version]===fv&&r[i.ccy]===v);
      if(!s[0])return;
      const bp=t=>{const x=s.find(r=>r[i.shock_type]===t);
        return x&&x[i.shock_bp]!=null?N(x[i.shock_bp])+'bp':'-'};
      const f0=fl?fl.rows.find(r=>r[fi.framework_version]===fv):null;
      rows.push([fv,s[0][i.status],s[0][i.effective_from],OD(s[0][i.effective_to]),
        OD(s[0][i.superseded_by]),bp('parallel'),bp('short'),bp('long'),
        f0?(f0[fi.floor_on_bp]==null?'-':N(f0[fi.floor_on_bp])+'bp'):T('미등재'),
        f0?f0[fi.evidence_status]:'-',s[0][i.evidence_status]])});
    ap(pane,ST(CS(p,'framework_version status effective_from effective_to superseded_by')
      .concat(['평행','단기','장기','충격후 하한','하한 근거','충격폭 근거']),rows));
    const dead=p.rows.filter(r=>r[i.status]==='폐지'&&r[i.ccy]===v);
    if(dead[0])ap(pane,MT(T('폐지 계정의 근거')+' '+TX(String(dead[0][i.source_ref]))))}
  draw(cur);
  ap(root,k)}
function krGap(root,c){
  const f=G(c,'alm_repricing_gap');if(!f)return;const i=IX(f);
  const rows=f.rows.slice().sort((a,b)=>a[i.seq]-b[i.seq]);
  const k=CARD('금리개정(리프라이싱) 갭 (<표2> 만기구간)');
  ap(k,CH.bars(rows.map(r=>({label:r[i.bucket],value:r[i.gap],
    tone:r[i.gap]<0?'bad':undefined})),{title:CL(f,'gap'),fmt:M,src:f,
    note:T('막대는 구간별 자산에서 부채를 뺀 값이다. 음수는 부채가 먼저 재설정되는 구간이다.')}));
  ap(k,CH.bars(rows.map(r=>({label:r[i.bucket],value:r[i.cumulative_gap],
    tone:r[i.cumulative_gap]<0?'bad':undefined})),{title:CL(f,'cumulative_gap'),fmt:M}));
  ap(k,U.table(f,{title:null}));
  const tb=G(c,'alm_time_bucket');
  if(tb){const ti=IX(tb),nb=tb.rows.length;
    ap(k,MT(CL(tb,'framework_version')+' '+tb.rows[0][ti.framework_version]+' · '+
      TF('{n}구간',{n:nb})+' · '+TX(String(tb.rows[0][ti.citation]))))}
  ap(root,k)}
function krNmd(root,c){
  const p=G(c,'alm_nmd_param');
  if(p){const i=IX(p),cap=(v,m)=>(v!=null&&m!=null&&v>=m)?' '+T('상한 적용'):'';
    const k=CARD('비만기성예금 범주별 코어 (<표3> 상한)');
    ap(k,ST(CS(p,'nmd_category korean core_ratio core_ratio_cap avg_maturity_years avg_maturity_cap_years slotting_method non_core_bucket_label evidence_status'),
      p.rows.map(r=>[r[i.nmd_category],r[i.korean],
        P(r[i.core_ratio])+cap(r[i.core_ratio],r[i.core_ratio_cap]),P(r[i.core_ratio_cap]),
        N(r[i.avg_maturity_years])+cap(r[i.avg_maturity_years],r[i.avg_maturity_cap_years]),
        N(r[i.avg_maturity_cap_years]),r[i.slotting_method],r[i.non_core_bucket_label],
        r[i.evidence_status]])));
    ap(k,MK('비핵심예금은 익일물로 보아 최단 구간에 배분한다. 배분방법·비코어 구간은 원장 컬럼이며 화면이 정하지 않는다.'),U.srcMeta(p));
    ap(root,k)}
  const g=G(c,'kr_nmd_category');
  if(g){const gi=IX(g),k=CARD('범주 판정 (제8항 가)');
    ap(k,U.table(g,{title:null}),MT(T('규칙 적용 근거')+' '+TX(String(g.rows[0][gi.citation]))));
    ap(root,k)}}
function krRetail(root,c){
  const cr=G(c,'kr_retail_criteria');
  if(cr){const i=IX(cr),k=CARD('소매 판정 기준 (제9항·제10항)');
    ap(k,U.table(cr,{title:null}),MT(TX(String(cr.rows[0][i.citation]))));
    ap(root,k)}
  const f=G(c,'kr_retail_behavioural_scope');if(!f)return;const i=IX(f);
  const k=CARD('행동옵션 표준화 적합도 판정');
  if(f.shown<f.total){ap(k,MK('표본 프레임이라 차트를 그리지 않는다'));ap(root,k);return}
  const m=grp(f.rows,r=>r[i.behaviour_class]+' · '+(r[i.in_scope]?T('대상'):T('제외'))+
    ' · '+OD(r[i.treatment]),r=>r[i.notional]);
  m.sort((a,b)=>b.v-a.v);
  ap(k,ST(['행동유형 · 대상여부 · 처리','건수',C(f,'notional')],
    m.map(x=>[x.k,IT(x.n),M(x.v)])));
  const ex=grp(f.rows.filter(r=>!r[i.in_scope]&&r[i.excluded_reason]!=null),
    r=>r[i.excluded_reason]);
  if(ex[0])ap(k,MT(CL(f,'excluded_reason')+' '+
    ex.map(x=>x.k+' '+TF('{n}건',{n:x.n})).join(' · ')));
  ap(k,U.srcMeta(f));
  ap(root,k)}
function krAuto(root,c){
  const f=G(c,'kr_auto_option_param');if(!f)return;
  const k=CARD('자동금리옵션 계수 (제11항)');
  ap(k,U.table(f,{title:null}));
  ap(k,U.note(T('옵션 계약 인벤토리(계약별 종류·행사금리·내재변동성) 원장이 저장소에 없어 재평가를 산출하지 않는다. 계수만 등재돼 있고 ΔEVE 에 옵션 리스크가 더해지지 않았다.'),'warn'));
  ap(k,MT(TX(String(f.rows[0][IX(f).citation]))));
  ap(root,k)}
function krGov(root,c){
  const f=G(c,'kr_irrbb_governance');if(!f)return;const i=IX(f);
  const V=v=>v==null?T('미판정'):(v?T('요건 이행'):T('요건 미이행'));
  const k=CARD('관리체계 이행 (제15항~제20항)');
  ap(k,ST(CS(f,'requirement_code clause requirement responsible_body frequency_text min_count_per_year count_in_period last_fulfilled_date is_fulfilled verdict_reason'),
    f.rows.map(r=>[r[i.requirement_code],r[i.clause],TX(String(r[i.requirement])),
      r[i.responsible_body],OD(r[i.frequency_text]),OD(r[i.min_count_per_year]),
      OD(r[i.count_in_period]),OD(r[i.last_fulfilled_date]),V(r[i.is_fulfilled]),
      OD(r[i.verdict_reason])])),U.srcMeta(f));
  ap(root,k)}
function krDisc(root,c){
  const t6=G(c,'disc_irrbb_table6');
  if(t6){const i=IX(t6),k=CARD('<표6> 금리리스크 수준 공시');
    ap(k,U.table(t6,{title:null}));
    const bl=t6.rows.filter(r=>r[i.value]==null&&r[i.blank_reason]!=null),nb=bl.length;
    if(nb)ap(k,U.note(TF('공란 {n}칸',{n:nb})+' · '+CL(t6,'blank_reason')+' '+
      grp(bl,r=>r[i.blank_reason]).map(x=>TX(String(x.k))+' '+TF('{n}칸',{n:x.n})).join(' · '),'warn'));
    const adj=t6.rows.filter(r=>r[i.is_adjustable]===false).length;
    if(adj)ap(k,MT(TF('이 양식은 자체 조정이 금지된 칸 {n}개를 포함한다 (제22항 나).',{n:adj})));
    ap(root,k)}
  const q=G(c,'disc_irrbb_table7_qualitative');
  if(q){const i=IX(q),k=CARD('<표7> 정성공시 8항목');
    ap(k,ST(CS(q,'item_no item_name is_optional is_disclosed input_by approved_by approved_date is_approved'),
      q.rows.map(r=>[r[i.item_no],r[i.item_name],
        r[i.is_optional]?T('선택 항목'):T('필수 항목'),
        r[i.is_disclosed]?T('공시 작성'):T('공시 미작성'),
        OD(r[i.input_by]),OD(r[i.approved_by]),OD(r[i.approved_date]),
        r[i.is_approved]?T('공시 승인'):T('공시 미승인')])),U.srcMeta(q));
    ap(root,k)}
  const qn=G(c,'disc_irrbb_table7_quantitative');
  if(qn){const k=CARD('<표7> 정량공시');ap(k,U.table(qn,{title:null}));ap(root,k)}}
function krIrrbb(root,c){
  LEAD(root,'국내 감독기준 [별표 9-1] 금리리스크 산출기준으로 낸 은행계정 금리리스크다. 측정지표는 ΔEVE 와 ΔNII 이고, 아웃라이어 판정 분모는 기본자본이다. 충격폭·만기구간·상한은 전부 원장에서 오며 화면은 다시 계산하지 않는다.');
  ap(root,MK('BCBS 계정으로 낸 산출은 금리리스크 화면에 있다. 두 화면은 같은 엔진을 쓰되 적용 계정이 다르므로 섞어 읽지 않는다.'));
  targets(root,c);
  outlier(root,c,true);
  krFramework(root,c);
  krGap(root,c);
  krNmd(root,c);
  krRetail(root,c);
  krAuto(root,c);
  krGov(root,c);
  krDisc(root,c);
  evidence(root,c);
}

/* ══════════════ 현금흐름 원장 ═══════════════════════════════════════ */

function cashflow(root,c){
  LEAD(root,'ALM 현금흐름 원장. 계약 현금흐름과 행동조정 현금흐름을 나란히 둔다.조정액(adjustment_cf)이 컬럼으로 있으므로 어느 모형이 얼마를 움직였는지 원장에서 조인된다.');
  ap(root,MK('계약·행동조정 현금흐름은 계약 단위라 화면에는 표본만 실린다. 그림은 버킷 집계 원장과, 파이프라인이 행동조정 원장 전량을 집계한 기여도로 그린다.'));
  const f=G(c,'alm_cashflow_bucket');
  if(!f){NOL(root);return}
  const i=IX(f);
  const scens=scenOrder(c,uniq(f,'scenario')),sides=uniq(f,'side'),bases=uniq(f,'basis');
  let sc=scens[0],sd=sides[0],bs=bases[bases.length-1];
  picker(root,T('시나리오'),scens,sc,v=>{sc=v;draw()});
  picker(root,CL(f,'side'),sides,sd,v=>{sd=v;draw()});
  picker(root,CL(f,'basis'),bases,bs,v=>{bs=v;draw()});
  const pane=el('div');ap(root,pane);
  function draw(){pane.innerHTML='';
    const s=f.rows.filter(r=>r[i.scenario]===sc&&r[i.side]===sd);
    if(!s[0])return;
    const ks=bks(f,s);
    const val=(b,x,col)=>{const r=s.find(y=>y[i.basis]===b&&y[i.bucket]===x);
      return r?(r[col]||0):0};
    const c1=CARD('계약 현금흐름 대 행동조정 현금흐름');
    ap(c1,CH.multiLine(bases.map(b=>({name:b,values:ks.map(x=>val(b,x,i.total_cf))})),
      ks,{fmt:M,src:f}));
    ap(c1,MK('두 선이 겹치는 버킷은 행동가정이 걸리지 않은 곳이다. 비만기예금은 계약 기준에서 전액이 최단 버킷에 있고, 행동 기준에서 코어가 장기로 퍼진다.'));
    ap(pane,c1);
    ap(pane,CH.stackBars([
      {name:CL(f,'principal_cf'),values:ks.map(x=>val(bs,x,i.principal_cf))},
      {name:CL(f,'interest_cf_ex_margin'),values:ks.map(x=>val(bs,x,i.interest_cf_ex_margin))},
      {name:CL(f,'margin_cf'),values:ks.map(x=>val(bs,x,i.margin_cf))}],ks,
      {title:T('현금흐름 구성')+' · '+bs+' · '+sd,fmt:M,src:f,
       note:T('ΔEVE는 상업마진을 제외하고 ΔNII는 포함한다. 그래서 마진을 별도 컬럼으로 담는다.')}));
    const A=c.D.alm&&c.D.alm.behaviour_contrib;
    if(A){const ai=IX(A),rows=A.rows.filter(r=>r[ai.scenario]===sc);
      if(rows[0]){const c3=CARD('행동모형별 조정액');
        ap(c3,CH.bars(rows.map(r=>({label:r[ai.behaviour_model],value:r[ai.adjustment_cf],
          tone:r[ai.adjustment_cf]<0?'bad':'good'})),
          {title:T('행동조정액 (행동에서 계약을 뺀 값)')+' · '+sc,fmt:M}));
        ap(c3,ST(CS(A,'behaviour_model adjustment_cf principal_cf n_contracts n_rows'),
          rows.map(r=>[r[ai.behaviour_model],M(r[ai.adjustment_cf]),M(r[ai.principal_cf]),
            IT(r[ai.n_contracts]),IT(r[ai.n_rows])])));
        ap(c3,ap(el('div','meta'),U.productChip(null),' ',
          TF('원장 {t} 전량 집계 {r}행 · 계약 {k}건',{t:c.D.alm.behaviour_source,
            r:c.D.alm.behaviour_rows,k:c.D.alm.behaviour_contracts})+' · '+
          T('조정액은 원장 adjustment_cf 를 그대로 더한 값이다.')));
        ap(pane,c3)}}}
  draw();
  ledgers(root,c);
  evidence(root,c);
}

/* ══════════════ 유동성 사다리 ═══════════════════════════════════════ */

function ladder(root,c){
  LEAD(root,'만기 사다리. 버킷별 유입·유출과 누적갭, 반대매매가능자산을 본다. 계약기준과 행동조정을 토글로 바꾼다.');
  ap(root,MK('만기 사다리는 잔존만기 축이다. 리프라이싱 축과 다른 축이며, 10년 변동금리 대출은 최단 버킷에서 금리가 재설정되지만 그 기간에 현금화되지 않는다. 두 축을 한 원장으로 합치면 유동성비율 분자가 구조적으로 부풀려진다.'));
  const f=G(c,'alm_maturity_ladder');
  if(!f){NOL(root);return}
  const i=IX(f);
  const scens=scenOrder(c,uniq(f,'scenario')),bases=uniq(f,'basis');
  let sc=scens[0],bs=bases[0];
  picker(root,T('시나리오'),scens,sc,v=>{sc=v;draw()});
  picker(root,CL(f,'basis'),bases,bs,v=>{bs=v;draw()});
  const pane=el('div');ap(root,pane);
  function draw(){pane.innerHTML='';
    const all=f.rows.filter(r=>r[i.scenario]===sc),s=all.filter(r=>r[i.basis]===bs);
    if(!s[0])return;
    const ks=bks(f,s),at=(b,x)=>all.find(r=>r[i.basis]===b&&r[i.bucket]===x);
    const c1=el('div','card');
    ap(c1,CH.heat([ks.map(x=>{const r=at(bs,x);return r?r[i.inflow]:null}),
      ks.map(x=>{const r=at(bs,x);return r?r[i.outflow]:null})],
      [CL(f,'inflow'),CL(f,'outflow')],ks,
      {title:T('버킷별 유입·유출')+' · '+bs+' · '+sc,fmt:M,src:f}));
    ap(c1,CH.bars(ks.map(x=>{const r=at(bs,x);
      return {label:x,value:r?r[i.net_gap]:0,tone:(r&&r[i.net_gap]<0)?'bad':'good'}}),
      {title:T('버킷별 순갭 (유입 − 유출)'),fmt:M}));
    ap(pane,c1);
    const c2=CARD('누적갭 (계약기준 대 행동조정)');
    ap(c2,CH.multiLine(bases.map(b=>({name:b,values:ks.map(x=>{
      const r=at(b,x);return r?r[i.cumulative_gap]:null})})),ks,{fmt:M,src:f}));
    ap(c2,MK('계약기준은 비만기예금 전액이 최단 버킷에서 빠져나간다고 본다. 계약상 만기가 없어 계약기준에서는 최조기 유출을 가정하고, 행동조정에서는 코어 부분을 장기 버킷에 남긴다.'));
    ap(pane,c2);
    const cbc=sum(s,i.counterbalancing_capacity);
    const worst=s.reduce((a,r)=>Math.min(a,r[i.cumulative_gap]),0),rest=cbc+Math.min(worst,0);
    ap(pane,U.kpiRow([
      {label:CL(f,'counterbalancing_capacity'),raw:true,value:M(cbc),
       sub:T('전 버킷 합계')+' · counterbalancing_capacity'},
      {label:'최대 누적부족',value:M(worst),sub:CL(f,'cumulative_gap')+' · '+T('최저점'),
       tone:worst<0?'bad':'good'},
      {label:'차감 후 잔량',value:M(rest),tone:rest<0?'bad':'good',
       sub:T('두 원장 컬럼의 합 (소진 경로는 생존기간 화면이 낸다)')}],c.meta.density))}
  draw();
  ledgers(root,c);
}

/* ══════════════ 유동성리스크 (LCR·NSFR) ═════════════════════════════ */

function lcrWalk(root,c){
  const f=G(c,'alm_lcr_flow'),g=G(c,'alm_lcr_factor');
  if(!f||!g)return;
  const i=IX(f),gi=IX(g),by={};
  g.rows.forEach(r=>{by[r[gi.section]+'|'+r[gi.category]]=r});
  const k=CARD('유동성커버리지비율 (항목별 잔액 × 계수 = 가중액)');
  ap(k,ST(CS(f,'section category balance factor weighted factor_source')
    .concat(['근거 판정',C(g,'citation_bcbs'),C(g,'citation_kr')]),
    f.rows.map(r=>{const q=by[r[i.section]+'|'+r[i.category]];
      return [r[i.section],r[i.category],M(r[i.balance]),P(r[i.factor],1),M(r[i.weighted]),
        TX(String(r[i.factor_source])),r[i.evidence_status],
        q?TX(String(q[gi.citation_bcbs])):'-',q?TX(String(q[gi.citation_kr])):'-']})),
    U.srcMeta(f));
  const rec=uniq(f,'section').map(s=>[T('구분 소계')+' · '+s,
    M(sum(f.rows.filter(r=>r[i.section]===s),i.weighted)),'alm_lcr_flow']);
  const a=G(c,'alm_result');
  if(a){const ai=IX(a),row=a.rows.find(r=>r[ai.metric]==='LCR');
    if(row){rec.push([CL(a,'numerator'),M(row[ai.numerator]),'alm_result'],
      [CL(a,'denominator'),M(row[ai.denominator]),'alm_result'],
      [row[ai.metric],P(row[ai.value],1),CL(a,'minimum')+' '+P(row[ai.minimum],0)])}}
  ap(k,ST(['항목','금액','출처'],rec));
  ap(k,MK('구분 소계와 비율 분자·분모가 어긋나면 그 차이가 상한 조정액이다.'));
  ap(root,k)}
// 상한이 문 자리. 계수는 상한 원장에서 읽고 적용은 엔진이 한다. 화면은 어느
// 상한이 물었는지만 대조한다.
function lcrCaps(root,c){
  const f=G(c,'alm_lcr_flow'),g=G(c,'alm_lcr_factor');
  if(!f||!g)return;
  const i=IX(f),gi=IX(g),secs=uniq(f,'section');
  const caps=g.rows.filter(r=>secs.indexOf(r[gi.section])<0);
  if(!caps[0])return;
  const W=rs=>sum(rs,i.weighted),hq=f.rows.filter(r=>/^level_/.test(String(r[i.category])));
  const SPEC={
    cap_l2b:{w:'Level 2B / HQLA',b:()=>W(hq),a:()=>W(hq.filter(r=>/2b/.test(String(r[i.category]))))},
    cap_l2:{w:'Level 2 / HQLA',b:()=>W(hq),a:()=>W(hq.filter(r=>/2a|2b/.test(String(r[i.category]))))},
    cap_inflow:{w:'INFLOW / OUTFLOW',
      b:()=>W(f.rows.filter(r=>/유출/.test(String(r[i.section])))),
      a:()=>W(f.rows.filter(r=>/유입/.test(String(r[i.section]))))}};
  const rows=[],unk=[];
  caps.forEach(r=>{const s=SPEC[r[gi.category]];
    if(!s){unk.push(String(r[gi.category]));return}
    const lim=(r[gi.factor]||0)*s.b(),act=s.a();
    rows.push([r[gi.category],s.w,P(r[gi.factor],0),M(lim),M(act),
      act>lim?T('구속'):T('미구속'),TX(String(r[gi.citation_bcbs]))])});
  const k=CARD('상한 (어느 상한이 물었는가)');
  ap(k,ST([C(g,'category'),'대상',C(g,'factor'),'상한액','산출액','판정','BCBS 근거'],rows),
    U.srcMeta(g));
  if(unk[0])ap(k,U.note(T('대조 규칙이 없는 상한')+' '+unk.join(' · ')+'. '+
    T('원장에는 있으나 화면이 대상 집계를 정하지 못한다.'),'warn'));
  ap(k,MK('상한액은 상한 원장의 계수를 대상 집계에 곱한 값이다. 실제 적용은 엔진 (risk_lib/alm/lcr.py)이 하고 화면은 구속 여부만 표시한다.'));
  ap(root,k)}
// 등재됐지만 산출에 들어가지 않은 항목. 분모에 아예 없는 유출 항목은 적어
// 두지 않으면 없던 일이 된다.
function lcrMissing(root,c){
  const f=G(c,'alm_lcr_flow'),g=G(c,'alm_lcr_factor');
  if(!f||!g)return;
  const i=IX(f),gi=IX(g),secs=uniq(f,'section'),used={};
  f.rows.forEach(r=>{used[r[i.section]+'|'+r[i.category]]=1});
  const miss=g.rows.filter(r=>secs.indexOf(r[gi.section])>=0&&
    !used[r[gi.section]+'|'+r[gi.category]]);
  if(!miss[0])return;
  const k=CARD('계수 원장에 등재됐으나 산출에 들어가지 않은 항목');
  ap(k,ST(CS(g,'section category factor source').concat(['근거 판정',C(g,'citation_bcbs')]),
    miss.map(r=>[r[gi.section],r[gi.category],P(r[gi.factor],1),r[gi.source],
      r[gi.evidence_status],TX(String(r[gi.citation_bcbs]))])),U.srcMeta(g));
  ap(k,MK('담보부조달·파생 유출·등급하락 트리거처럼 원천 원장이 없어 산출하지 못한 항목이다. 등재해 두지 않으면 분모에 없다는 사실 자체가 보이지 않는다.'));
  ap(root,k)}
function nsfrCard(root,c){
  const f=G(c,'alm_nsfr_item'),g=G(c,'alm_nsfr_factor');
  if(!f)return;const i=IX(f);
  const k=CARD('순안정자금조달비율 (항목별 금액 × 계수 = 가중액)');
  ap(k,CH.bars(uniq(f,'section').map(s=>({label:s,
    value:sum(f.rows.filter(r=>r[i.section]===s),i.weighted)})),
    {title:T('구분별 가중 후 금액'),fmt:M,src:f}));
  ap(k,ST(CS(f,'section category amount factor weighted maturity_band')
    .concat(['근거 판정',C(f,'citation')]),
    f.rows.map(r=>[r[i.section],r[i.category],M(r[i.amount]),P(r[i.factor],1),
      M(r[i.weighted]),r[i.maturity_band],r[i.evidence_status],TX(String(r[i.citation]))])));
  const a=G(c,'alm_result');
  if(a){const ai=IX(a),row=a.rows.find(r=>r[ai.metric]==='NSFR');
    if(row)ap(k,MT(row[ai.metric]+' '+P(row[ai.value],1)+' ('+CL(a,'numerator')+' '+
      M(row[ai.numerator])+' / '+CL(a,'denominator')+' '+M(row[ai.denominator])+') · '+
      CL(a,'minimum')+' '+P(row[ai.minimum],0)+' · alm_result'))}
  if(g){const gi=IX(g),nul=g.rows.filter(r=>r[gi.factor]==null);
    if(nul[0])ap(k,U.note(T('계수 공란')+' '+
      nul.map(r=>r[gi.section]+' '+r[gi.category]).join(' · ')+'. '+
      T('국내 채택값을 확인하지 못해 비워 두었고, 그 항목은 산출에 들어가지 않는다.'),'bad'))}
  ap(root,k)}
function liquidity(root,c){
  LEAD(root,'유동성비율 상세. 항목별 잔액 × 계수 = 가중액, 상한이 문 자리, 계수의 출처와 근거 판정까지 한 화면에 둔다.');
  targets(root,c);
  lcrLine(root,c);
  lcrWalk(root,c);
  lcrCaps(root,c);
  lcrMissing(root,c);
  nsfrCard(root,c);
  ledgers(root,c);
  evidence(root,c);
}

/* ══════════════ 생존기간 ════════════════════════════════════════════ */

function survival(root,c){
  LEAD(root,'생존기간. 스트레스별 반대매매가능자산 소진 경로다. LCR 30일은 최소 시계이며 내부 스트레스는 더 긴 구간을 본다.');
  targets(root,c);
  const f=G(c,'alm_survival_path');
  if(!f){NOL(root);return}
  const i=IX(f),scens=uniq(f,'scenario'),days=uniq(f,'day').slice().sort((a,b)=>a-b);
  const at=(s,d)=>f.rows.find(x=>x[i.scenario]===s&&x[i.day]===d);
  const c1=CARD('스트레스별 반대매매가능자산 잔량 경로');
  ap(c1,CH.multiLine(scens.map(s=>({name:s,values:days.map(d=>{
    const r=at(s,d);return r?r[i.cbc_remaining]:null})})),
    days.map(d=>d%10?'':String(d)),{fmt:M,src:f}));
  ap(c1,MK('가로축은 일자다. 선이 0을 뚫는 날이 소진일이고, 그 이전까지가 생존기간이다.'));
  ap(root,c1);
  const p=G(c,'alm_liquidity_stress_param'),pi=p?IX(p):null;
  const hz=s=>{if(!p)return null;const r=p.rows.find(x=>x[pi.stress_scenario]===s);
    return r?r[pi.horizon_days]:null};
  const c2=CARD('시나리오별 소진일');
  const rows=scens.map(s=>{
    const path=f.rows.filter(x=>x[i.scenario]===s).slice().sort((a,b)=>a[i.day]-b[i.day]);
    const brk=path.find(x=>x[i.survived]===false),nd=path.length,last=path[nd-1];
    return [s,brk?TF('{n}일차 소진',{n:brk[i.day]}):T('관측 구간 내 미소진'),
      TF('{n}일',{n:last[i.day]}),M(last[i.cbc_remaining]),M(last[i.net_outflow_cum]),
      hz(s)==null?'-':TF('{n}일',{n:hz(s)})]});
  ap(c2,ST([C(f,'scenario'),'소진','관측 마지막','최종 잔량','누적 순유출','원장 시계'],
    rows),U.srcMeta(f));
  ap(c2,MK('생존기간 목표에는 규정값이 없다. 이사회가 정하고 승인한다. 그래서 이 화면은 경로와 소진일만 내고 합격·불합격을 판정하지 않는다.'));
  ap(root,c2);
  if(p){const c3=CARD('스트레스 유출률 (시나리오 × 항목)');
    ap(c3,U.table(p,{title:null}));
    const gone=uniq(p,'stress_scenario').filter(s=>scens.indexOf(s)<0);
    if(gone[0])ap(c3,U.note(TF('경로가 없는 스트레스 {s}',{s:gone.join(' · ')})+'. '+
      T('유출률이 원장에서 비어 있어(근거 미확인) 엔진이 산출을 건너뛰었다. 0으로 채우지 않는다.'),'warn'));
    ap(root,c3)}
  evidence(root,c);
}

/* ══════════════ ALM 계수 원장 ═══════════════════════════════════════ */

/* 승인 이력. 수기입력 원장은 입력자·승인자·승인일이 채워져야 결재 대상이다. */
function approval(root,c){
  const KEY=['input_source','entered_by','approved_by','approved_on'],rows=[];
  (c.meta.tables||[]).forEach(n=>{const f=G(c,n);if(!f)return;const i=IX(f);
    let any=false;KEY.forEach(x=>{if(i[x]!==undefined)any=true});
    if(!any)return;
    const nr=f.rows.length;
    rows.push([n,IT(nr)].concat(KEY.map(x=>{if(i[x]===undefined)return '-';
      const nk=f.rows.filter(r=>r[i[x]]!=null).length;return IT(nk)+' / '+IT(nr)})))});
  const k=CARD('수기입력 원장의 승인 상태 (기입된 행 / 전체 행)');
  ap(k,ST(['원장','행수','입력 출처','입력자','승인자','승인일'],rows));
  ap(k,MK('조기상환율·중도해지율 기준값은 규제가 주지 않는다. 은행 자체추정과 감독 승인 기록이 근거가 된다. 이 원장들은 수기입력이며, 승인란이 비어 있는 동안에는 그 값으로 결재를 올릴 수 없다.'));
  ap(root,k)}
function blanks(root,c){
  const rows=[];
  (c.meta.tables||[]).forEach(n=>{const f=G(c,n);if(!f)return;
    const nr=f.rows.length;
    f.columns.forEach((col,x)=>{const nn=f.rows.filter(r=>r[x]==null).length;
      if(nn)rows.push([n,col,FR.colLabel(f,x),IT(nn)+' / '+IT(nr)])})});
  const k=CARD('빈칸 재고 (어느 원장의 어느 칸이 비어 있는가)');
  ap(k,ST(['원장','컬럼','표시명','빈칸 / 행수'],rows));
  ap(k,MK('값을 확인하지 못한 칸은 기본값으로 채우지 않는다. 엔진은 그 조정을 건너뛰고 경고를 남기며, 화면은 이 목록으로 그 사실을 드러낸다.'));
  ap(root,k)}
function paramScreen(root,c){
  LEAD(root,'ALM 계수·수기입력 모수. 입력자·승인자·승인일과 근거 판정을 함께 본다. 확인하지 못한 값은 비워 두고, 비어 있다는 사실을 화면에 표시한다.');
  approval(root,c);
  blanks(root,c);
  evidence(root,c);
  ledgers(root,c);
}

/* ══════════════ 등록 ════════════════════════════════════════════════ */

const DEF=[['alm',null,'ALM',almHome],['irrbb',SUB,'금리리스크',irrbb],
  ['kr-irrbb',SUB,'국내 금리리스크',krIrrbb],['cashflow',SUB,'현금흐름 원장',cashflow],
  ['ladder',SUB,'유동성 사다리',ladder],['liquidity',SUB,'유동성리스크',liquidity],
  ['survival',SUB,'생존기간',survival],['alm-params',SUB,'ALM 계수 원장',paramScreen]];
DEF.forEach(d=>NG.screen(d[0],{group:GRP,sub:d[1],title:d[2],build:d[3]}));
})();
