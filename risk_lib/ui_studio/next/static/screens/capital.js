/* screens/capital.js: 자본·RWA 16화면 (신용 · 시장 · 운영 · 건전성). */
/* 규칙 (설계 사양 2.6·5·6장, 수용기준 A7·A8·A12·A21): */
/* - 건수·총계는 x_queue·x_close·x_screen_gate·frame.total 에서 읽는다. 화면이 */
/*   센 행수를 총계로 찍지 않는다. 잘린 프레임은 차트를 그리지 않고 이유를 적는다. */
/* - 색은 TN(원장 어휘, 값) 하나로만 정한다. x_severity 에 어휘가 없는 값(조기경보 */
/*   단계 경보·주의·관찰)은 색을 붙이지 않는다. 자체 색표는 만들지 않는다. */
/* - 표 머리글·차트 라벨은 카탈로그 한글명(CL)이고 원장 값·인용·서식 코드는 */
/*   원문 그대로다. 저자가 쓴 문장만 T·TF 로 지난다. */
/* - 공용 도우미(renderForm·domainBrowser)는 shared.js 만 정의한다. */
(function(){
'use strict';
const NG=window.NG,U=NG.ui,CH=NG.charts,FR=NG.frame,el=U.el,ap=U.ap;
const T=NG.T,TF=NG.TF,fmt=NG.fmt,TN=NG.tone,IX=FR.frameIdx;
const GRP='자본·RWA',TOP=12;
/* base.css 가 section{display:none} 이라 펼친 카드는 div 로 만든다. */
const MT=t=>el('div','meta',t);
const S=t=>{const c=el('div','card sec');ap(c,el('h3',null,T(t)));return c};
const G=(c,n)=>(c.D.data||{})[n]||null;
const CK=n=>{const r=NG.cat(n);return (r&&r.korean)||n};
const LEAD=(root,k)=>{ap(root,el('p','lead',T(k)))};
/* 컬럼 한글명은 카탈로그 라벨이다. 번역하지 않고 그대로 쓴다. */
const CL=(f,k)=>FR.colLabel(f,IX(f)[k]);
function tcard(c,n,o){o=o||{};o.title=CK(n);o.raw=true;return U.table(G(c,n),o)}
function why(f){return MT(T('차트는 전량 프레임에서만 그린다')+' · '+
  TF('표본 {n}/{N}행',{n:f.shown,N:f.total}))}
/* 축 집계는 전량 프레임에서만 한다. ck 는 컬럼명 하나 또는 여럿이다. */
function agg(f,ck,vk){const i=IX(f),ks=[].concat(ck),m={},out=[];
  f.rows.forEach(r=>{const k=ks.map(x=>String(r[i[x]])).join(' · ');
    const v=vk==null?1:(typeof r[i[vk]]==='number'?r[i[vk]]:0);
    let e=m[k];if(!e){e=m[k]={label:k,value:0,n:0};out.push(e)}e.value+=v;e.n++});
  out.sort((a,b)=>Math.abs(b.value)-Math.abs(a.value));return out}
function sumOf(f,k){const i=IX(f)[k];let s=0;
  f.rows.forEach(r=>{if(typeof r[i]==='number')s+=r[i]});return s}
function hb(c,n,ttl,ck,vk,money){const f=G(c,n);
  if(!f)return U.table(null);
  if(f.shown<f.total)return why(f);
  const it=agg(f,ck,vk);
  if(vk!=null)it.forEach(x=>{x.sub=TF('{n}행',{n:x.n})});
  return CH.hbars(it.slice(0,TOP),{title:T(ttl),money:money!==false,src:f})}
/* 3선 재계산 대상. 판정·수치는 x_screen_gate.targets 그대로다. */
function targets(c){const t=((c.D.x_screen_gate||{}).targets||{})[c.id]||[];
  if(!t[0])return null;
  const box=el('div','kpis c4');
  t.forEach(r=>ap(box,U.kpi({label:r.korean,raw:true,value:fmt.money(r.reported),
    sub:T('상시 독립검증 (3선) 재계산 대상')+' '+r.target+' · '+r.citation,
    tone:TN('recalc.state',r.state),badge:r.state,
    lineage:NG.lineage.byTarget(r.target)})));
  return box}

/* ══════════════ 신용 (leaf-parent) · 조기경보 ════════════════════════ */

/* 조기경보 단계(경보·주의·관찰)는 x_severity 에 어휘가 없다. 색을 붙이면 */
/* 화면이 자체 색표를 만드는 것이므로 값만 적는다. */
function ews(root,c,full){
  ap(root,hb(c,'crm_ews_signal','조기경보 단계별 익스포저(EAD)','level','ead',true));
  const f=FR.full('crm_ews_signal');
  if(f)ap(root,CH.bars(agg(f,'signal',null),
    {title:T('조기경보 신호 유형별 건수'),src:f,fmt:fmt.int}));
  if(full)ap(root,tcard(c,'crm_ews_signal'));
}
function credit(root,c){
  LEAD(root,'등급·PD/LGD/EAD·부도/회수 품질·담보배분·조기경보를 연결한다.');
  ews(root,c,false);
  ap(root,MT(T('아래 목록은 이 부문 카탈로그 전량이다. 고른 원장의 입도·기본키·외래키·차트·미리보기를 오른쪽에 편다.')));
  NG.shared.domainBrowser(root,'PRD-CRM',{tables:c.meta.tables||[]});
}
function ewsScreen(root,c){
  LEAD(root,'차주 단위 조기경보 신호와 단계, 권고 조치. 에이전트가 순위를 제안하고 사람이 결정한다.');
  ews(root,c,true);
}

/* ══════════════ 신용 RWA ════════════════════════════════════════════ */

function creditRwa(root,c){
  LEAD(root,'표준방법 구간별·내부등급법 PD 구간별로 분해해 업무보고서 라인과 같은 입도로 둔다.');
  const t=targets(c);if(t)ap(root,t);
  const sa=FR.full('rwa_sa_bucket');
  if(sa){const i=IX(sa);
    ap(root,CH.hbars(sa.rows.map(r=>({label:r[i.asset_class]+' · '+
      CL(sa,'risk_weight')+' '+fmt.pct(r[i.risk_weight],0),value:r[i.rwa],
      sub:CL(sa,'ead')+' '+fmt.money(r[i.ead])})).sort((a,b)=>b.value-a.value),
      {title:T('위험가중자산 구성 (표준방법 자산군×위험가중치)'),src:sa}))}
  const ib=FR.full('rwa_irb_pool');
  if(ib){const i=IX(ib);
    ap(root,CH.hbars(ib.rows.map(r=>({label:r[i.asset_class]+' · PD '+r[i.pd_band],
      value:r[i.rwa],sub:CL(ib,'rw_average')+' '+fmt.pct(r[i.rw_average],0)}))
      .sort((a,b)=>b.value-a.value).slice(0,10),
      {title:T('내부등급법 풀별 위험가중자산 (PD 구간)'),src:ib}))}
  /* 출력하한: 내부모형·표준방법·하한 적용 후를 같은 축에서 본다. */
  const of=FR.full('rwa_output_floor');
  if(of&&of.rows[0]){const i=IX(of),r=of.rows[0];
    ap(root,CH.bars(['internal_rwa','standardised_rwa','floored_rwa']
      .map(k=>({label:CL(of,k),value:r[i[k]]})),
      {title:T('하한 적용 전후 위험가중자산'),src:of,fmt:fmt.money,
       note:CL(of,'floor_pct')+' '+fmt.pct(r[i.floor_pct],1)+' · '+
         CL(of,'binding')+' '+String(r[i.binding])+' · '+
         CL(of,'uplift')+' '+fmt.money(r[i.uplift])}))}
  ap(root,tcard(c,'rwa_result'),tcard(c,'rwa_output_floor'));
  const box=S('카탈로그 귀속');
  ap(box,MT(T('시장·운영 위험가중자산 원장(rwa_market_component · rwa_operational_bi)도 카탈로그에서는 PRD-RWA 다. 화면은 시장 RWA · 운영 RWA 에 두었고 제품 코드 칩은 카탈로그 값 그대로 붙는다.')),
    U.productChip('rwa_market_component'),U.productChip('rwa_operational_bi'));
  ap(root,box);
  NG.shared.domainBrowser(root,'PRD-RWA',{tables:c.meta.tables||[]});
}

/* ══════════════ ECL ═════════════════════════════════════════════════ */

function ecl(root,c){
  LEAD(root,'Stage 전이·SICR 트리거·충당금 증감 브리지를 분해한다.');
  const t=targets(c);if(t)ap(root,t);
  ap(root,hb(c,'ecl_result','기대신용손실 구성 (단계별)','stage','ecl',true));
  /* 충당금 증감 브리지: 기초 잔액에서 단계별 증감을 쌓아 기말로 간다. */
  const br=FR.full('ecl_provision_bridge');
  if(br&&br.rows[0]){const i=IX(br),rs=br.rows.slice().sort((a,b)=>a[i.seq]-b[i.seq]);
    const last=rs[rs.length-1];
    ap(root,CH.waterfall(rs.slice(1).map(r=>({label:String(r[i.step]),delta:r[i.amount]})),
      rs[0][i.amount],{title:T('충당금 증감 브리지'),startLabel:String(rs[0][i.step]),
      src:br,fmt:fmt.money,note:CL(br,'cumulative')+' '+
        fmt.money(last[i.cumulative])}))}
  ap(root,tcard(c,'ecl_stage_transition'),tcard(c,'ecl_sicr_trigger_stat'));
  NG.shared.domainBrowser(root,'PRD-ECL',{tables:c.meta.tables||[]});
}

/* ══════════════ 시장 (leaf-parent) · 백테스팅 · IPV ═════════════════ */

function backtestCharts(root){const f=FR.full('mkt_backtest_exception');
  if(!f)return null;
  const k=el('div','card');ap(k,CH.pnlChart(f));ap(root,k,CH.calheat(f));return f}
/* 미해소 IPV: 경과일 상위. 색은 예외·조치 원장의 심각도에서만 온다. */
function ipvOpen(root,c){const f=FR.full('mkt_ipv');
  if(!f)return;
  const i=IX(f),ex=exIdx(c);
  const open=f.rows.filter(r=>r[i.is_break]),n=open.length;
  ap(root,CH.hbars(open.slice().sort((a,b)=>b[i.days_open]-a[i.days_open]).slice(0,8)
    .map(r=>{const e=ex[String(r[i.trade_id])];
      return {label:r[i.trade_id]+' · '+r[i.source],value:r[i.days_open],
        tone:e?TN('exception.severity',e.severity):null,
        sub:CL(f,'diff')+' '+fmt.money(r[i.diff])+' · '+CL(f,'limit')+' '+
          fmt.money(r[i.limit])}}),
    {title:T('독립가격검증(IPV) 미해소 (경과일 상위)'),money:false,src:f}));
  ap(root,MT(TF('미해소 {n}건',{n:n})+' · '+TF('전량 {N}행',{N:f.total})+' · '+
    T('경과일은 원장 days_open 이며 5일 초과는 상위보고 대상이다')));
}
function exIdx(c){const m={},q=(c.D.x_queue||{}).exceptions||{};
  (q.rows||[]).forEach(r=>{if(r.source_ledger==='mkt_ipv')m[String(r.source_key)]=r});
  return m}
function exCard(root,c){const q=(c.D.x_queue||{}).exceptions||{};
  const mine=(q.rows||[]).filter(r=>r.source_ledger==='mkt_ipv'),n=mine.length;
  const box=S('예외·조치 연결');
  ap(box,n?U.dotlist(mine.map(r=>({tone:TN('exception.severity',r.severity),
    text:r.exception_id+' · '+r.source_key+' · '+NG.text(r.finding),
    right:r.status,onClick:()=>c.go('exceptions')}))):
    U.note(T('가격검증에서 넘어간 예외가 없다'),'good'));
  ap(box,MT(TF('가격검증 예외 {n}건',{n:n})+' · '+
    TF('전량 {N} (서버 집계)',{N:q.total})+' · gov_exception_action'));
  ap(root,box)}
function market(root,c){
  LEAD(root,'벤치마크 가격·시장데이터 계보·위험요소·ES·백테스팅을 연결한다.');
  backtestCharts(root);
  ipvOpen(root,c);
  NG.shared.domainBrowser(root,'PRD-MKT',{tables:c.meta.tables||[]});
}
function ipv(root,c){
  LEAD(root,'거래 원장, 위험요소 매핑, 독립가격검증 결과. 미해소 5일 초과는 상위보고 대상이다.');
  ipvOpen(root,c);exCard(root,c);
  const f=G(c,'mkt_ipv'),i=IX(f||{columns:[]});
  ap(root,tcard(c,'mkt_ipv',{rowClass:r=>r[i.is_break]?'warn':null}),
    tcard(c,'mkt_trade'),tcard(c,'mkt_risk_factor'));
}
function backtest(root,c){
  LEAD(root,'일별 손익과 VaR 경계의 실측 대조. 예외는 신호등 구간 판정으로 이어진다.');
  const f=backtestCharts(root);
  if(f){const i=IX(f),n=f.rows.filter(r=>r[i.exception]).length;
    ap(root,U.dotlist(agg(f,'zone',null).map(z=>({text:CL(f,'zone')+' '+z.label,
      right:TF('{n}행',{n:z.value})})).concat([{text:CL(f,'exception'),
      right:TF('{n}행',{n:n}),tone:n?'warn':'good'}]))) }
  ap(root,tcard(c,'mkt_backtest_exception'));
}
function varEs(root,c){
  LEAD(root,'과거시뮬레이션 VaR·ES 산출 원장. 백테스팅·소요자기자본의 원천이다.');
  const f=FR.full('mkt_var_es');
  if(f){const i=IX(f);
    ap(root,CH.hbars(f.rows.map(r=>({label:r[i.measure]+' · '+fmt.pct(r[i.confidence],1),
      value:r[i.value],sub:CL(f,'horizon_days')+' '+fmt.int(r[i.horizon_days])+' · '+
        CL(f,'method')+' '+r[i.method]})),{title:T('측정치별 금액'),src:f}))}
  ap(root,tcard(c,'mkt_var_es'));
}

/* ══════════════ 시장 RWA · 포트폴리오 ═══════════════════════════════ */

function form(root,c,id){const f=(c.D.forms||[]).find(x=>x.form_id===id);
  if(!f){ap(root,U.note(T('서식이 payload 에 없다')+' '+id,'warn'));return}
  const p=el('div');NG.shared.renderForm(p,f);ap(root,p)}
function marketRwa(root,c){
  LEAD(root,'시장리스크 소요자기자본 서식(B2326)과 그 원천인 VaR·ES 원장. 서식 라인마다 산식·규정 근거가 붙어 있다.');
  form(root,c,'BR-05');
  const f=FR.full('rwa_market_component');
  if(f){const i=IX(f);
    ap(root,CH.hbars(f.rows.map(r=>({label:r[i.risk_class],value:r[i.rwa],
      sub:CL(f,'capital')+' '+fmt.money(r[i.capital])})).sort((a,b)=>b.value-a.value),
      {title:T('위험군별 위험가중자산'),src:f}))}
  ap(root,tcard(c,'rwa_market_component'),
    U.table(G(c,'mkt_var_es'),{title:'VaR·ES 원장'}));
}
function mktPortfolio(root,c){
  LEAD(root,'포지션 원장을 포트폴리오 × 위험군으로 편 상세. 규제 표(위험군 집계)와 같은 원장·같은 산식에서 나오며, VaR·ES 열은 자본비중 비례배분(내부기준)이라 독립 재계산이 아니다.');
  ap(root,hb(c,'mkt_portfolio_capital','포트폴리오별 위험가중자산',
    ['portfolio_id','risk_class'],'rwa'));
  ap(root,hb(c,'mkt_var_es_portfolio','포트폴리오별 VaR·ES 배분',
    ['measure','portfolio_id'],'value'));
  ap(root,tcard(c,'mkt_position'),tcard(c,'mkt_portfolio_capital'),
    tcard(c,'mkt_var_es_portfolio'));
}
function portfolioSetup(root,c){
  LEAD(root,'포트폴리오 구분과 배분 가중치의 정본. 가중치는 위험군별 합 1.0·전부 양수이며, 포지션 원장·트레이딩북 배정이 전부 이 설정을 따른다. 값은 합성 설정이라 실기관 적용 시 운용 지침으로 교체된다.');
  const f=FR.full('mkt_portfolio');
  if(f){const i=IX(f),ks=['share_interest_rate','share_equity','share_fx'];
    ap(root,CH.stackBars(ks.map(k=>({name:CL(f,k),values:f.rows.map(r=>r[i[k]])})),
      f.rows.map(r=>String(r[i.portfolio_id])),
      {title:T('포트폴리오별 위험군 배분 가중치'),fmt:v=>fmt.pct(v,0),
       note:CL(f,'var_limit_share')+' · '+CL(f,'evidence_status')+' '+
         String(f.rows[0][i.evidence_status])}))}
  ap(root,tcard(c,'mkt_portfolio'),tcard(c,'mkt_trade'));
}

/* ══════════════ 운영 (leaf-parent) · 손실·회수 · KRI ════════════════ */

/* KRI 판정은 원장 값(green·amber·red)이고 색은 kri.grade 어휘로만 정한다. */
function kriList(root,c){const f=G(c,'opr_kri');
  if(!f)return;
  const i=IX(f),box=S('핵심리스크지표(KRI) 상태');
  ap(box,U.dotlist(f.rows.map(r=>({text:r[i.kri_name],
    tone:TN('kri.grade',String(r[i.status]).toUpperCase()),
    right:fmt.num(r[i.value])+' / '+CL(f,'threshold_red')+' '+fmt.num(r[i.threshold_red])}))),
    U.srcMeta(f));
  ap(root,box)}
function oprisk(root,c){
  LEAD(root,'내·외부 사건·회수·KRI·PSMOR 원칙 매핑을 연결한다. 매핑이며 준수 인증이 아니다.');
  ap(root,hb(c,'opr_loss_event','운영손실 순손실 구성 (사건유형별)','event_type','net_loss'));
  const cp=FR.full('opr_capital');
  if(cp){const i=IX(cp);
    ap(root,CH.bars(cp.rows.map(r=>({label:CL(cp,'method')+' '+r[i.method],
      value:r[i.rwa]})),{title:T('산출방법별 위험가중자산'),src:cp,fmt:fmt.money,
      note:T('채택 방법과 서식 라인은 운영 RWA 화면에 있다')}))}
  kriList(root,c);
  /* 마감 과제·게이트는 운영리스크 원장이지만 판정은 마감 워크플로에서 한다. */
  const tk=((c.D.x_close||{}).tasks)||[],nt=tk.length;
  const done=tk.filter(t=>t.status==='완료').length;
  const box=S('마감 워크플로 연결');
  ap(box,U.dotlist([{text:T('마감 과제')+' · opr_close_task · opr_close_gate',
    right:fmt.int(done)+' / '+fmt.int(nt),onClick:()=>c.go('close-workflow'),
    tone:TN('close_task.status',done<nt?'미완료':'완료')}]),
    MT(T('과제 상태와 게이트 판정은 마감 워크플로 화면이 원장 그대로 싣는다')));
  ap(root,box);
  NG.shared.domainBrowser(root,'PRD-OPR',{tables:c.meta.tables||[]});
}
function lossRecovery(root,c){
  LEAD(root,'내·외부 손실사건, 회수, 운영리스크 소요자본. 총손실 → 적격회수 → 순손실 순서로 읽는다.');
  ap(root,hb(c,'opr_loss_event','운영손실 순손실 구성 (사건유형별)','event_type','net_loss'));
  const f=FR.full('opr_loss_event');
  if(f){const g=sumOf(f,'gross_loss'),rc=sumOf(f,'recovery');
    ap(root,CH.waterfall([{label:CL(f,'recovery'),delta:-rc}],g,
      {title:T('총손실에서 순손실까지'),startLabel:CL(f,'gross_loss'),src:f,
       fmt:fmt.money,note:CL(f,'net_loss')+' '+fmt.money(sumOf(f,'net_loss'))}))}
  const rv=G(c,'opr_recovery');
  ap(root,tcard(c,'opr_loss_event'));
  if(rv&&rv.shown<rv.total)ap(root,why(rv));
  ap(root,tcard(c,'opr_recovery'),tcard(c,'opr_capital'));
}
function kriControl(root,c){
  LEAD(root,'핵심리스크지표와 통제 원장, 그리고 경보가 떴을 때 무엇을 해야 하는지의 정책 바인딩.');
  const f=FR.full('opr_control');
  if(f)ap(root,CH.bars(agg(f,'evidence_status',null).map(x=>({label:x.label,
    value:x.value,tone:TN('evidence_node.status',x.label)})),
    {title:T('통제 증빙 상태'),src:f,fmt:fmt.int}));
  kriList(root,c);
  const pi=IX(G(c,'gov_alert_policy')||{columns:[]});
  ap(root,tcard(c,'opr_kri'),tcard(c,'opr_control'),
    tcard(c,'gov_alert_policy',{rowClass:r=>r[pi.blocks_submission]?'warn':null}));
}
function opRwa(root,c){
  LEAD(root,'운영리스크 소요자기자본 서식(BA2325-1)과 산출방법별 자본·위험가중자산 원장.');
  const f=FR.full('opr_capital');
  if(f){const i=IX(f);
    ap(root,CH.hbars(f.rows.map(r=>({label:CL(f,'method')+' '+r[i.method],
      value:r[i.rwa],sub:CL(f,'capital')+' '+fmt.money(r[i.capital])})),
      {title:T('산출방법별 위험가중자산'),src:f}))}
  const bi=FR.full('rwa_operational_bi');
  if(bi){const i=IX(bi);
    ap(root,CH.bars(bi.rows.map(r=>({label:String(r[i.component]),value:r[i.amount]})),
      {title:T('사업지표(BI) 구성요소별 금액'),src:bi,fmt:fmt.money}))}
  form(root,c,'BR-06');
  ap(root,tcard(c,'opr_capital'),tcard(c,'rwa_operational_bi'));
}

/* ══════════════ NCR·건전성 ══════════════════════════════════════════ */

function ncr(root,c){
  LEAD(root,'순자본비율(NCR) 구성과 증권 건전성 원장. 은행 BIS 비율과 분모·분자·규정 근거가 다르다.');
  ap(root,hb(c,'ncr_component','NCR 구성요소별 금액',['category','component'],'amount'));
  /* 첫 분류(원장 행 순서)의 구성요소를 누계로 편다. 분류 이름은 원장 값이다. */
  const nf=FR.full('ncr_component');
  if(nf&&nf.rows[0]){const i=IX(nf),c0=String(nf.rows[0][i.category]);
    const rs=nf.rows.filter(r=>String(r[i.category])===c0);
    ap(root,CH.waterfall(rs.slice(1).map(r=>({label:String(r[i.component]),
      delta:r[i.amount]})),rs[0][i.amount],
      {title:TF('{cat} 구성요소 누계',{cat:c0}),startLabel:String(rs[0][i.component]),
       src:nf,fmt:fmt.money}))}
  const nc=G(c,'ncr_component');
  if(nc)ap(root,MT(T('근거 조항은 원장 값이라 번역하지 않는다')+' · '+
    CL(nc,'citation')));
  const li=IX(G(c,'pru_liquidity_ratio')||{columns:[]});
  const oi=IX(G(c,'pru_ownership_limit')||{columns:[]});
  const pi=IX(G(c,'pru_prompt_action')||{columns:[]});
  const bad=TN('val_check.status','FAIL');
  ap(root,tcard(c,'ncr_component'),tcard(c,'pru_balance_sheet'),
    tcard(c,'pru_income_statement'),
    tcard(c,'pru_liquidity_ratio',{rowClass:r=>r[li.passes]?null:bad}),
    tcard(c,'pru_ownership_limit',{rowClass:r=>r[oi.passes]?null:bad}),
    tcard(c,'pru_camel'),
    tcard(c,'pru_prompt_action',{rowClass:r=>r[pi.triggered]?bad:null}));
  ap(root,MT(T('재무상태·손익·소유한도·경영실태·적기시정조치는 이 화면이 유일한 자리다. 예전에는 데이터모델 카탈로그 탭에서만 볼 수 있었다.')));
}

/* ══════════════ 등록 ════════════════════════════════════════════════ */

const DEF=[['credit',null,'신용',credit],['ews','신용','조기경보',ewsScreen],
  ['credit-rwa','신용','신용 RWA',creditRwa],['ecl','신용','ECL',ecl],
  ['market',null,'시장',market],['ipv','시장','가격검증·IPV',ipv],
  ['backtest','시장','백테스팅',backtest],['var-es','시장','VaR·ES',varEs],
  ['market-rwa','시장','시장 RWA',marketRwa],
  ['market-portfolio','시장','시장 포트폴리오',mktPortfolio],
  ['portfolio-setup','시장','포트폴리오 설정',portfolioSetup],
  ['oprisk',null,'운영',oprisk],['loss-recovery','운영','손실·회수',lossRecovery],
  ['kri-control','운영','KRI·통제',kriControl],['op-rwa','운영','운영 RWA',opRwa],
  ['ncr','건전성','NCR·건전성',ncr]];
DEF.forEach(d=>NG.screen(d[0],{group:GRP,sub:d[1],title:d[2],build:d[3]}));
})();
