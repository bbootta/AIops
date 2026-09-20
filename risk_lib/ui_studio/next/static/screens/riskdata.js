/* screens/riskdata.js: 리스크데이터 12화면 (RDM · 선행 원장 · 카탈로그·코드). */
/* 규칙 (설계 사양 2.5·5·6장, 수용기준 A7·A8·A12·A21·A23): */
/* - 건수·총계는 x_queue·x_screens·meta·frame.total 에서 읽는다. 화면이 센 */
/*   행수를 총계로 찍지 않는다. 잘린 프레임은 배지를 달고 차트를 그리지 않는다. */
/* - 색은 TN(원장 어휘, 값) 하나로만 정한다. 자체 색표는 만들지 않는다. */
/* - 원장 값·물리 테이블명·컬럼 한글명·코드·판정 문자열은 번역하지 않는다. */
/*   표 머리글은 카탈로그 한글명(raw), 툴팁은 물리명이다. */
/* - 공용 도우미(renderForm·domainBrowser·almEvidence·almSources·judgeGlyph)는 */
/*   shared.js 만 정의한다. 여기서는 NG.shared 로 부르기만 한다. */
(function(){
'use strict';
const NG=window.NG,U=NG.ui,CH=NG.charts,FR=NG.frame,el=U.el,ap=U.ap;
const T=NG.T,TF=NG.TF,fmt=NG.fmt,tx=NG.text,ST=U.simpleTable,NO=U.note;
const GRP='리스크데이터',TOP=14;
/* base.css 가 section{display:none} 을 걸어 두어 펼친 카드는 div 로 만든다. */
const MT=t=>el('div','meta',t),IX=FR.frameIdx,TN=NG.tone,NL=()=>U.table(null);
const SRCT=t=>TF('출처: {table}',{table:t});
const S=t=>{const c=el('div','card sec');ap(c,el('h3',null,T(t)));return c};
const G=(c,n)=>(c.D.data||{})[n]||null;
const CK=n=>{const r=NG.cat(n);return (r&&r.korean)||n};
const LEAD=(root,k)=>U.lead(root,k);
const SRC=names=>MT(T('연결 원장')+' '+names.join(' · '));
/* 표 머리글은 프레임 라벨(카탈로그 한글명)이고 툴팁이 물리 컬럼명이다. */
function col(f,k){const i=f?f.columns.indexOf(k):-1;
  return {key:k,label:i>=0?FR.colLabel(f,i):k,raw:true,phys:k}}
function tcard(c,n,o){o=o||{};o.title=CK(n);o.raw=true;return U.table(G(c,n),o)}
/* 축 집계는 전량 프레임에서만 한다. 표본이면 이유를 적고 그리지 않는다. */
function agg(f,ck,vk){const i=IX(f),m={},out=[];
  f.rows.forEach(r=>{const k=String(r[i[ck]]),v=vk==null?1:(typeof r[i[vk]]==='number'?r[i[vk]]:0);
    let e=m[k];if(!e){e=m[k]={label:k,value:0,n:0};out.push(e)}e.value+=v;e.n++});
  out.sort((a,b)=>Math.abs(b.value)-Math.abs(a.value));return out}
function sampled(f){return MT(TF('표본 {n}/{N}행',{n:f.shown,N:f.total})+' · '+SRCT(f.table))}
function chart(c,n,ttl,ck,vk,money){const f=G(c,n);
  if(!f)return NL();
  if(f.shown<f.total)return sampled(f);
  const it=agg(f,ck,vk).slice(0,TOP);
  if(vk!=null)it.forEach(x=>{x.sub=TF('{n}행',{n:x.n})});
  return CH.hbars(it,{title:T(ttl),money:money===true,src:f})}
/* 채택 전 세 방법의 합계 비교. 라벨은 카탈로그 컬럼 한글명 그대로다. */
function methodCmp(c,n,cols,ttl){const f=G(c,n);
  if(!f)return NL();
  if(f.shown<f.total)return sampled(f);
  const i=IX(f);
  const it=cols.map(k=>({label:FR.colLabel(f,i[k]),phys:k,
    value:f.rows.reduce((s,r)=>s+(typeof r[i[k]]==='number'?r[i[k]]:0),0)}));
  return CH.hbars(it,{title:T(ttl),src:f})}
/* 3선 재계산 대상. 판정·수치는 x_screen_gate.targets 에서 그대로 온다. */
function targets(c){const t=((c.D.x_screen_gate||{}).targets||{})[c.id]||[];
  if(!t[0])return null;
  const box=el('div','kpis c4');
  t.forEach(r=>ap(box,U.kpi({label:r.korean,raw:true,value:fmt.money(r.reported),
    sub:T('상시 독립검증 (3선) 재계산 대상')+' '+r.target+' · '+r.citation,
    tone:TN('recalc.state',r.state),badge:r.state,
    lineage:NG.lineage.byTarget(r.target)})));
  return box}

/* ══════════════ RDM (leaf-parent) ═══════════════════════════════════ */

/* 합성데이터 고지·소관 부서·검토를 화면 맨 위에 둔다. 이 화면의 수치가 원장 */
/* 그대로라서 실적 수치로 오인될 여지가 가장 크기 때문이다. */
function notice(root,c){const k=S('검토 안내');
  ap(k,NO(T('이 화면의 수치는 합성데이터를 파이프라인에 넣어 낸 산출이다. 실제 기관 수치가 아니며, 쓰기 전에 소관 부서의 검토를 거쳐야 한다. 검토 결과는 승인 원장에 남는다.'),'warn'));
  const o=((c.D.x_screens||{})[c.id]||{}).ownership,line=el('div','meta');
  if(o){line.title=T('DOMAIN_ROLE_MAP 상수로 연결했다. 도메인과 역할을 잇는 원장 컬럼은 없다.');
    ap(line,T('소관 부서')+' '+o.role_name+' · '+o.org_unit+' · '+T('소관 (UI 가정)'))}
  else ap(line,T('소관 부서')+' · '+T('소관 미확인'));
  ap(k,line,MT(T('합성데이터 · 합성 포트폴리오')+' · '+TF('시드 {seed}',{seed:c.D.meta.seed})));
  ap(root,k)}
/* 데이터 스튜어드 처리대장: 지금 붉은 것 · 막힌 것 · 달라진 것. */
function docket(root,c){const q=c.D.x_queue||{},dq=q.dq||{},rc=q.recon||{},
  ct=q.contracts||{},cm=q.canonical||{},ex=q.exceptions||{},box=S('데이터 스튜어드 처리대장');
  const nDq=(dq.fail_by_rule||[]).length,nRc=(rc.fail||[]).length,nCt=(ct.not_pass||[]).length;
  const nCm=cm.unmapped||0,tn=n=>TN('val_check.status',n?'FAIL':'PASS');
  const srv=n=>' · '+TF('전량 {N} (서버 집계)',{N:n});
  ap(box,MT(T('지금 붉은 것')),U.dotlist([
    {text:TF('데이터품질 실패 규칙 {n}종',{n:nDq})+srv(dq.total)+' · rdm_dq_result',tone:tn(nDq),
     onClick:()=>c.go('dq-recon')},
    {text:TF('대사 실패 {n}건',{n:nRc})+srv(rc.total)+' · rdm_reconciliation',tone:tn(nRc),
     onClick:()=>c.go('dq-recon')},
    {text:TF('원천 계약 미통과 {n}건',{n:nCt})+srv(ct.total)+' · rdm_source_contract',tone:tn(nCt),
     onClick:()=>c.go('sources')},
    {text:TF('표준코드 미매핑 {n}건',{n:nCm})+srv(cm.total)+' · rdm_canonical_map',tone:tn(nCm),
     onClick:()=>c.go('sources')}]));
  const blocked=(ex.by_source||[]).map(r=>({tone:'blocked',
    text:r.source_ledger+' · '+r.owner_role+' · '+TF('{n}건',{n:r.n}),onClick:()=>c.go('exceptions')}));
  (ex.by_due||[]).forEach(r=>blocked.push({tone:'warn',
    text:TF('기한 {d}일 이내 {n}건',{d:r.due_days,n:r.n})+' · gov_exception_action'}));
  const chg=c.D.changes,ci=IX(chg||{columns:[]});
  if(chg){const nBad=chg.rows.filter(r=>r[ci.deploy_allowed]===false).length;
    blocked.push({tone:tn(nBad),onClick:()=>c.go('changes'),
      text:TF('배포 불가 변경요청 {n}건',{n:nBad})+' · '+TF('전량 {N}행',{N:chg.total})+' · chg_change_request'})}
  ap(box,MT(T('막힌 것')),U.dotlist(blocked));
  const tr=c.D.x_trend||{};
  ap(box,MT(T('달라진 것')),U.dotlist([
    {text:TF('기간 {n}개',{n:tr.n_periods})+(tr.single_period?' · '+T('추이 원장에 기간이 하나뿐이다'):''),
     tone:tr.single_period?'not-run':'neutral'},
    {text:T('추이 원장은 헤드라인 지표만 싣는다. 원장 전량의 기간 비교는 이 화면에서 하지 않는다.'),tone:'neutral'}]));
  ap(root,box)}
function rdm(root,c){
  notice(root,c);docket(root,c);
  LEAD(root,'원천 계약부터 표준 매핑, 버전형 가공, 다차원 집계, DQ·대사, 승인 스냅샷까지 원장으로 통제한다. 아래 목록은 이 부문 카탈로그 전량이며, 고른 원장의 입도·기본키·외래키·차트·미리보기를 오른쪽에 편다.');
  NG.shared.domainBrowser(root,'PRD-RDM',{tables:c.meta.tables||[]})}

/* ══════════════ 원천·계약 ═══════════════════════════════════════════ */

function sources(root,c){
  LEAD(root,'원천 시스템과의 인터페이스 계약, 수신 스냅샷, 표준코드 매핑을 원장으로 통제한다. 계약 위반은 적재 전에 차단된다.');
  ap(root,chart(c,'rdm_source_contract','원천 시스템별 수신 행수','source_system','actual_rows',false));
  const sc=G(c,'rdm_source_contract'),si=IX(sc||{columns:[]});
  ap(root,tcard(c,'rdm_source_contract',{rowClass:r=>TN('val_check.status',r[si.status])}));
  ap(root,tcard(c,'rdm_snapshot'));
  const cm=G(c,'rdm_canonical_map'),mi=IX(cm||{columns:[]});
  ap(root,tcard(c,'rdm_canonical_map',{rowClass:r=>r[mi.status]==='mapped'?null:'bad'}));
  /* 미매핑 코드는 변경요청 원장에서 같은 코드를 쓰는 CHG 로 잇는다. */
  const chg=c.D.changes,gi=IX(chg||{columns:[]}),items=[];
  if(cm)cm.rows.forEach(r=>{if(r[mi.status]==='mapped')return;
    const code=String(r[mi.source_code]);
    const hit=chg?chg.rows.filter(x=>String(x[gi.change_id]).indexOf(code)>=0):[];
    const id=hit[0]?String(hit[0][gi.change_id]):null;
    items.push({tone:id?'blocked':'bad',right:id||T('기록 없음'),onClick:id?()=>c.go('changes'):null,
      text:r[mi.domain]+' · '+code+' · '+r[mi.source_system]})});
  const box=S('표준코드 매핑');
  ap(box,items[0]?U.dotlist(items):NO(T('미매핑 코드가 없다'),'good'));
  U.hint(box,'미매핑 코드는 산출 모집단에서 빠지고 대사에도 걸리지 않는다. 표준 코드가 생겨야 산출에 들어간다.');
  ap(box,SRC(['rdm_canonical_map','chg_change_request']));
  ap(root,box)}

/* ══════════════ DQ·대사 ═════════════════════════════════════════════ */

function dqRecon(root,c){
  LEAD(root,'DQ 규칙과 판정, 원천·산출 대사를 한 화면에서 본다. 실패는 예외·조치 큐로 넘어간다.');
  const q=c.D.x_queue||{},dq=q.dq||{},rc=q.recon||{};
  const box=S('데이터품질 판정');
  const fbr=(dq.fail_by_rule||[]),nfr=fbr.length;
  if(nfr)ap(box,CH.hbars(fbr.map(r=>({label:String(r.rule),value:r.n,
    tone:TN('val_check.status','FAIL')})),{title:T('실패 규칙별 건수'),money:false}));
  else ap(box,U.meter('데이터품질 실패 판정',0,dq.total,'good'));
  ap(box,MT(TF('실패 규칙 {n}종',{n:nfr})+' · '+TF('전량 {N} (서버 집계)',{N:dq.total})+
    ' · '+SRCT('rdm_dq_result')));
  const dr=G(c,'rdm_dq_result');
  if(dr&&dr.shown<dr.total)ap(box,sampled(dr));
  ap(root,box);
  ap(root,chart(c,'rdm_reconciliation','대사 판정별 건수','status',null,false));
  ap(root,tcard(c,'rdm_dq_rule'));
  ap(root,tcard(c,'rdm_dq_result'));
  const rf=G(c,'rdm_reconciliation'),ri=IX(rf||{columns:[]});
  ap(root,tcard(c,'rdm_reconciliation',{rowClass:r=>TN('val_check.status',r[ri.status])}));
  /* 실패 대사는 예외·조치 원장의 같은 키 행으로 잇는다. */
  const ex=G(c,'gov_exception_action'),xi=IX(ex||{columns:[]}),bad=[];
  if(rf)rf.rows.forEach(r=>{if(r[ri.status]==='PASS')return;
    const key=String(r[ri.recon_id]);
    const k=ex?ex.rows.findIndex(x=>String(x[xi.source_key])===key):-1;
    bad.push({tone:'bad',right:k>=0?String(ex.rows[k][xi.exception_id]):T('기록 없음'),
      text:key+' · '+r[ri.axis]+' · '+r[ri.downstream],
      onClick:k>=0?()=>c.drawer.row(ex,k):()=>c.go('exceptions')})});
  const bx=S('실패 대사와 예외·조치 연결');
  ap(bx,bad[0]?U.dotlist(bad):NO(T('실패한 대사가 없다'),'good'));
  ap(bx,MT(TF('전량 {N} (서버 집계)',{N:rc.total})),SRC(['rdm_reconciliation','gov_exception_action']));
  ap(root,bx)}

/* ══════════════ 예외·조치 ═══════════════════════════════════════════ */

/* 정렬은 색조 순서(불량 먼저)로만 한다. 원장 어휘를 화면이 다시 등급 매기지 */
/* 않기 위해서다. 색조는 x_severity 가 준다. */
const TONE_ORD=['bad','blocked','warn','not-run','synthetic','neutral','good'];
const rank=t=>TONE_ORD.indexOf(t);
function exceptions(root,c){
  LEAD(root,'대사·DQ·IPV 세 원장의 미해소 예외가 표준 조치·담당·기한이 붙은 하나의 큐로 모인다. 종결은 사람 승인 후에만 한다.');
  const ex=(c.D.x_queue||{}).exceptions||{},rows=ex.rows||[],nr=rows.length;
  const st={},so=[];
  rows.forEach(r=>{let e=st[r.status];if(!e){e=st[r.status]={label:r.status,value:0,
    tone:TN('exception.status',r.status)};so.push(e)}e.value++});
  const box=S('예외 상태 분포');
  ap(box,CH.bars(so,{title:T('상태별 건수'),fmt:v=>fmt.int(v),
    note:T('자동상계 금지 · 종결은 사람 승인 후')}));
  ap(box,CH.bars((ex.by_severity||[]).map(r=>({label:r.severity,value:r.n,
    tone:TN('exception.severity',r.severity)})),{title:T('심각도별 건수'),fmt:v=>fmt.int(v)}));
  ap(box,MT(TF('전량 {N} (서버 집계)',{N:ex.total})+' · '+SRCT('gov_exception_action')));
  if(nr<ex.total)ap(box,U.truncBadge({shown:nr,total:ex.total}));
  ap(root,box);
  const f=G(c,'gov_exception_action'),fi=IX(f||{columns:[]});
  const ord=rows.slice().sort((a,b)=>
    (rank(TN('exception.severity',a.severity))-rank(TN('exception.severity',b.severity)))||
    (a.due_days-b.due_days));
  const data=ord.map(r=>({exception_id:r.exception_id,source_ledger:r.source_ledger,
    source_key:r.source_key,severity:U.badge(r.severity,TN('exception.severity',r.severity)),
    owner_role:r.owner_role,status:U.badge(r.status,TN('exception.status',r.status)),
    due_days:r.due_days,finding:tx(r.finding),action:tx(r.action)}));
  const qb=S('예외·조치 큐');
  ap(qb,ST(['exception_id','source_ledger','source_key','severity','owner_role','status',
    'due_days','finding','action'].map(k=>col(f,k)),data,{onRow:(row,i)=>{
      const k=f?f.rows.findIndex(x=>String(x[fi.exception_id])===String(ord[i].exception_id)):-1;
      if(k>=0)c.drawer.row(f,k)}}));
  ap(qb,MT(SRCT('gov_exception_action')));
  ap(root,qb);
  const pf=G(c,'gov_alert_policy'),pi=IX(pf||{columns:[]});
  ap(root,tcard(c,'gov_alert_policy',{rowClass:r=>r[pi.blocks_submission]?'bad':null}));
  ap(root,NO(T('경보는 제출을 막을 수 있다. 자동으로 상계하거나 종결하지 않는다. 종결은 담당 역할의 승인이 원장에 남은 뒤다.'),'warn'));
  ap(root,SRC(['gov_exception_action','gov_alert_policy']))}

/* ══════════════ 표 중심 화면 (담보·집계·선행 원장) ══════════════════ */

const PLAIN={
 collateral:{lead:'담보·보증·차주 재무 원장이다. 신용위험경감과 LGD 의 원천이며, 적격 판정은 원장 컬럼 그대로 읽는다.',
   ch:[['rdm_collateral','담보유형별 평가액','collateral_type','market_value',true],
       ['rdm_guarantee','보증유형별 보증액','protection_type','guaranteed_amount',true]],
   tb:['rdm_collateral','rdm_guarantee','rdm_obligor_financial']},
 aggregates:{lead:'도메인마다 집계 축과 필요 컬럼이 다르므로 집계 결과를 원장으로 고정했다. 축이 다른 다섯 원장을 한 화면에서 본다.',
   ch:[['agg_credit_exposure','자산군별 익스포저 (신용 축)','asset_class','ead',true],
       ['agg_alm_exposure','리프라이싱 구간별 익스포저 (ALM 축)','repricing_bucket','ead',true]],
   tb:['agg_credit_exposure','agg_market_exposure','agg_operational_loss','agg_alm_exposure','agg_stress_exposure'],
   foot:'신용·ALM 집계의 EAD 합은 익스포저 원장 rdm_exposure 총계와 같다. 대사 판정은 rdm_reconciliation 원장에 남으며 화면이 다시 계산하지 않는다.'},
 funds:{lead:'모펀드 마스터와 편입자산·운용지침을 분리해 LTA·MBA 를 둘 다 산출한다. 정보가 모자라면 fallback 이며, 채택 방법과 사유는 원장에 남는다.',
   cmp:['rwa_fund_result',['rwa_lta','rwa_mba','rwa_fallback'],'채택 전 세 방법 합계'],
   ch:[['rwa_fund_result','산출방법별 채택 위험가중자산','adopted_method','adopted_rwa',true],
       ['rdm_fund_holding','자산군별 편입 시가','asset_class','market_value',true]],
   tb:['rdm_fund_master','rdm_fund_holding','rdm_fund_mandate','rwa_fund_result']},
 derivatives:{lead:'거래 마스터와 기초자산(다리)을 분리해 SA-CCR EAD 와 시장리스크 민감도를 둘 다 낸다. 기초자산 자산군이 감독계수 키가 된다.',
   ch:[['rdm_derivative_master','거래상대방별 명목','counterparty','notional',true],
       ['rdm_derivative_underlying','자산군별 다리 명목','asset_class','leg_notional',true]],
   tb:['rdm_derivative_master','rdm_derivative_underlying','rdm_netting_set','mkt_derivative_sensitivity']},
 securitisation:{lead:'딜 마스터와 트렌치·기초자산 풀을 분리해 세 방법을 모두 산출하고 규정 계층으로 채택한다. 채택 방법·하한 적용 여부는 원장 컬럼 그대로다.',
   cmp:['rwa_sec_result',['rwa_sa','rwa_erba','rwa_irba'],'채택 전 세 방법 합계'],
   ch:[['rwa_sec_result','딜별 채택 위험가중자산','deal_name','adopted_rwa',true],
       ['rdm_sec_tranche','트렌치별 보유액','tranche_name','holding_amount',true]],
   tb:['rdm_sec_master','rdm_sec_tranche','rdm_sec_pool','rwa_sec_result']}};
function plain(root,c){const p=PLAIN[c.id];
  LEAD(root,p.lead);
  const t=targets(c);if(t)ap(root,t);
  if(p.cmp)ap(root,methodCmp(c,p.cmp[0],p.cmp[1],p.cmp[2]));
  (p.ch||[]).forEach(x=>ap(root,chart(c,x[0],x[1],x[2],x[3],x[4])));
  if(c.id==='securitisation')ap(root,floorLine(c));
  (p.tb||[]).forEach(n=>ap(root,tcard(c,n)));
  if(p.foot)ap(root,NO(T(p.foot),'neutral'));
  ap(root,SRC(p.tb))}
/* 위험가중 하한이 실제로 걸린 트렌치 수. 하한값은 원장 컬럼에서 읽는다. */
function floorLine(c){const f=G(c,'rwa_sec_result');if(!f)return NL();
  const i=IX(f),hit=f.rows.filter(r=>r[i.floor_applied]===true),nf=hit.length;
  const lv=hit[0]?fmt.pct(hit[0][i.adopted_rw_floor]):T('미산출');
  return MT(TF('위험가중 하한 적용 트렌치 {n}건',{n:nf})+' · '+
    (f.shown<f.total?TF('표본 {n}/{N}행',{n:f.shown,N:f.total}):TF('전량 {N}행',{N:f.total}))+
    ' · '+T('하한')+' '+lv+' · '+SRCT('rwa_sec_result'))}

/* ══════════════ 데이터모델 ══════════════════════════════════════════ */

function catFrame(c,prod){const rows=(c.D.catalog||[]).filter(r=>!prod||r.product===prod)
  .map(r=>[r.name,r.korean,r.product,r.grain,r.columns,r.pk,r.fk,r.rows,r.materialised]);
  const n=rows.length;
  return {table:null,columns:['name','korean','product','grain','columns','pk','fk','rows','materialised'],
    labels:[T('테이블'),T('한글명'),T('부문'),T('그레인'),T('컬럼'),T('기본키'),T('외래키'),T('행'),T('실체화')],
    rows:rows,shown:n,total:prod?n:(c.D.meta.n_tables||n)}}
function catTab(root,c){const D=c.D;
  ap(root,MT(TF('정규 테이블 {n}장 · 컬럼 {c}개 · 실체화 {r}행',
    {n:D.meta.n_tables,c:D.meta.n_columns,r:D.meta.n_rows})));
  let pick='';const pane=el('div');
  ap(root,U.chips([{value:'',label:'전체 부문',on:true}].concat(
    (D.domains||[]).map(p=>({value:p,label:p,raw:true}))),v=>{pick=v;draw()}),pane);
  function draw(){pane.innerHTML='';
    ap(pane,U.table(catFrame(c,pick),{title:'정규 데이터모델 카탈로그',product:null}))}
  draw();
  ap(root,U.table(D.views,{title:CK('ui_view'),raw:true}));
  }
function useTab(root,c){const xs=c.D.x_screens||{},m={},order=[];
  Object.keys(xs).forEach(id=>{(xs[id].ledgers||[]).forEach(l=>{
    let e=m[l.table];if(!e){e=m[l.table]={t:l.table,k:l.korean,s:[],shown:l.shown,total:l.total};order.push(e)}
    if(e.s.indexOf(id)<0)e.s.push(id)})});
  const rows=order.map(e=>[e.t,e.k,e.s.join(' · '),e.shown,e.total]),n=rows.length;
  ap(root,U.table({table:null,columns:['table','korean','screens','shown','total'],
    labels:[T('테이블'),T('한글명'),T('화면'),T('표시 행수'),T('원장 행수')],
    rows:rows,shown:n,total:n},{title:'원장→화면',product:null}))}
function figTab(root,c){const fg=(c.D.x_lineage||{}).figures||{},asof=c.D.meta.asof;
  const rows=Object.keys(fg).map(k=>{const f=fg[k],a=f.audit||{};
    return [k,f.table,f.column,(f.pk||[]).map(p=>p.column+'='+(p.value==null?asof:p.value)).join(' · '),
      (f.check_names||[]).join(' · '),f.recalc_target||'-',T(f.gate_state),
      a.code_module?a.code_module+'.'+a.code_function:'-',a.citation||'-']}),n=rows.length;
  ap(root,U.table({table:null,columns:['figure_id','table','column','pk','check_names','recalc_target','gate_state','code','citation'],
    labels:[T('수치 식별자'),T('테이블'),T('컬럼'),T('기본키'),T('검증 항목'),T('재계산 대상'),T('판정'),T('코드 모듈'),T('규정 근거')],
    rows:rows,shown:n,total:n},{title:'수치→원장',product:null}));
  const rc=(c.D.x_gate||{}).recalc||{},rr=rc.rows||[];
  ap(root,S('상시 독립검증 (3선) 재계산 대상'));
  ap(root,ST([{key:'target',label:'재계산 대상'},{key:'korean',label:'한글명'},
    {key:'state',label:'판정'},{key:'citation',label:'규정 근거'}],
    rr.map(r=>({target:r.target,korean:r.korean,citation:r.citation,
      state:U.badge(T(r.state),TN('recalc.state',r.state))})),{}))}
function dataModel(root,c){
  LEAD(root,'정규 데이터모델 카탈로그와 그 쓰임이다. 카탈로그는 테이블·컬럼·입도·기본키의 정본이고, 각 View 의 필드 권한과 마스킹 정책이 조회 가능 범위를 결정한다.')}

/* ══════════════ 코드 마스터 ═════════════════════════════════════════ */

/* 세션 재정의는 실행별로 따로 담는다. 정본은 카탈로그이고 화면은 제안까지만 */
/* 만든다. 화면에서 바꾼 순서가 산출물에 들어가면 그건 조작이다. */
const ORD={};
function codeMaster(root,c){
  LEAD(root,'정렬·표시의 정본을 코드그룹 단위로 관리한다. 왼쪽에서 그룹을 고르면 오른쪽에 그 그룹의 코드가 순서대로 뜬다. 순서 재정의는 이 화면 안에서만 적용되고, 정본 변경은 카탈로그 수정 제안으로만 한다.');
  const f=G(c,'rdm_code_master');
  if(!f){ap(root,NL());return}
  const i=IX(f),gm={},names=[];
  f.rows.forEach(r=>{const g=String(r[i.code_set]);let e=gm[g];
    if(!e){e=gm[g]={n:0,src:String(r[i.source_table])};names.push(g)}e.n++});
  names.sort();
  let sel=names[0];const key=g=>c.D.meta.run_id+'|'+g;
  const wrap=el('div','split'),left=el('div','card'),right=el('div','card');
  ap(wrap,left,right);ap(root,wrap);
  const nG=names.length;
  const q=U.input({type:'search',placeholder:T('그룹명 검색'),aria:T('그룹명 검색'),onInput:()=>fill()});
  const list=el('div','list');
  ap(left,el('h3',null,T('코드그룹')+' '+TF('{n}종',{n:nG})),q,list,
    MT(TF('전량 {N}행',{N:f.total})+' · '+SRCT('rdm_code_master')));
  function fill(){list.innerHTML='';const kw=(q.value||'').trim().toLowerCase();
    names.forEach(g=>{if(kw&&g.toLowerCase().indexOf(kw)<0)return;
      const b=el('button');b.type='button';ap(b,g,el('small'));
      ap(b.lastChild,TF('코드 {n}개',{n:gm[g].n})+' · '+gm[g].src+(ORD[key(g)]?' · '+T('재정의됨'):''));
      if(g===sel)b.classList.add('on');
      b.onclick=()=>{sel=g;fill();codes()};ap(list,b)})}
  function current(){const o=ORD[key(sel)];if(o)return o.slice();
    return f.rows.filter(r=>String(r[i.code_set])===sel)
      .sort((a,b)=>a[i.sort_order]-b[i.sort_order]).map(r=>String(r[i.code]))}
  function codes(){right.innerHTML='';
    ap(right,el('h3',null,T('코드')+' · '+sel),
      MT(T('출처')+' '+gm[sel].src+' · '+T('정렬은 카탈로그 선언 순서를 따른다')));
    const cur=current(),last=cur.length-1;
    ap(right,ST([{key:'k',label:'순서'},{key:'code',label:'코드'},{key:'mv',label:'이동'}],
      cur.map((code,k)=>{const up=U.button('↑',{disabled:k===0,onClick:()=>{
          const c2=cur.slice(),p=c2[k-1];c2[k-1]=c2[k];c2[k]=p;ORD[key(sel)]=c2;codes();fill()}});
        const dn=U.button('↓',{disabled:k===last,onClick:()=>{
          const c2=cur.slice(),p=c2[k+1];c2[k+1]=c2[k];c2[k]=p;ORD[key(sel)]=c2;codes();fill()}});
        const box=el('div','row');ap(box,up,dn);
        return {k:k,code:code,mv:box}}),{}));
    const kill=c.killedFor('A · 리스크데이터'),bar=el('div','toolbar'),out=el('pre','mono');
    out.style.whiteSpace='pre-wrap';
    ap(bar,U.button(T('세션에 적용'),{primary:true,disabled:kill,onClick:()=>{ORD[key(sel)]=current();codes();fill()}}),
      U.button(T('재정의 지우기'),{onClick:()=>{delete ORD[key(sel)];codes();fill()}}),
      U.button(T('정본 변경 제안'),{disabled:kill,onClick:()=>{
        out.textContent=JSON.stringify({proposal:T('코드 마스터 순서 변경'),code_set:sel,
          from:f.rows.filter(r=>String(r[i.code_set])===sel)
            .sort((a,b)=>a[i.sort_order]-b[i.sort_order]).map(r=>String(r[i.code])),
          to:ORD[key(sel)]||null,source_table:gm[sel].src,
          apply_path:'risk_lib/datamodel/catalog.py',
          note:T('정본은 카탈로그다. 세션 재정의는 이 화면을 벗어나면 사라진다.')},null,2)}}));
    ap(right,bar);
    if(kill)ap(right,NO(T('비상정지 (실행 차단)'),'blocked'));
    ap(right,out)}
  fill();codes()}

/* ══════════════ 코드 매핑 ═══════════════════════════════════════════ */

const YN=v=>U.pill(T(v?'대상':'제외'),v?'good':null);
function matrix(root,c,mode){
  const acct=mode==='account';
  const bm=G(c,acct?'rdm_account_master':'rdm_product_master');
  const a=G(c,acct?'crm_code_scope':'mkt_code_scope'),b=G(c,acct?'alm_code_scope':'opr_code_scope');
  if(!bm||!a||!b){ap(root,NL());return}
  const mi=IX(bm),ai=IX(a),bi=IX(b);
  const kc=acct?'account_code':'product_code',aBy={},bBy={};
  a.rows.forEach(r=>{aBy[String(r[ai[kc]])]=r});
  b.rows.forEach(r=>{bBy[String(r[bi[kc]])]=r});
  const V=(r,ix,k)=>r?r[ix[k]]:null;
  const ks=acct?['account_code','account_name','in_scope','asset_class','approach','rw_range',
      'ccf_type','ccf_rate','n_exposures','ead_total','irrbb_scope','liquidity_scope','lcr_category','lcr_factor']
    :['product_code','product_name','book','in_scope','frtb_class','trade_kind','n_trades',
      'ead_total','in_scope','event_mapping','n_events','capital_method'];
  const cols=ks.map(k=>col(k in mi?bm:(k in ai?a:b),k));
  const rows=bm.rows.map(r=>{const code=String(r[mi[kc]]),x=aBy[code],y=bBy[code],o={};
    cols.forEach(cc=>{const k=cc.key;
      o[k]=k in mi?r[mi[k]]:(k in ai?V(x,ai,k):V(y,bi,k))});
    o[kc]=code;
    if(acct){o.in_scope=YN(V(x,ai,'in_scope'));o.irrbb_scope=YN(V(y,bi,'irrbb_scope'));
      o.liquidity_scope=YN(V(y,bi,'liquidity_scope'))}
    else{o.in_scope=YN(V(x,ai,'in_scope'))}
    return o});
  const card=S('엔진 연계 매트릭스');
  if(!acct){/* 상품 축은 시장·운영이 같은 컬럼명을 써서 두 번째 대상여부를 따로 담는다. */
    cols[8]={key:'opr_scope',label:FR.colLabel(b,bi.in_scope),raw:true,phys:'in_scope'};
    rows.forEach((o,k)=>{o.opr_scope=YN(V(bBy[String(bm.rows[k][mi[kc]])],bi,'in_scope'))})}
  ap(card,ST(cols,rows,{}));
  U.hint(card,'대상여부는 특성에서 규칙으로 파생된다. 신용환산율·위험가중 범위는 산출 엔진 상수, 모집단은 익스포저 원장, 적용률은 산출 원장에서 읽는다.');
  ap(card,SRC(acct?['rdm_account_master','crm_code_scope','alm_code_scope']
    :['rdm_product_master','mkt_code_scope','opr_code_scope']));
  ap(root,card)}
function codeMap(root,c){
  LEAD(root,'계정·상품 코드가 어느 리스크의 모집단에 들어가는지의 매핑이다. 매핑이 없으면 그 코드는 모든 산출에서 빠지고 대사에도 걸리지 않는다.');
  let mode=c.params.sel==='product'?'product':'account';
  const bar=el('div','toolbar'),pane=el('div');
  ap(bar,U.select([{value:'account',label:'계정코드 축',selected:mode==='account'},
    {value:'product',label:'상품코드 축',selected:mode==='product'}],v=>{mode=v;draw()}));
  ap(root,bar,pane);
  function draw(){pane.innerHTML='';matrix(pane,c,mode);proposal(pane,c)}
  draw()}
function proposal(root,c){const card=S('대상여부 예외 제안'),bar=el('div','toolbar');
  const code=U.input({placeholder:T('코드'),aria:T('코드')});
  const scope=U.select(['crm_code_scope','alm_code_scope','mkt_code_scope','opr_code_scope']
    .map(v=>({value:v,label:v,raw:true})));
  const to=U.select([{value:'true',label:'대상'},{value:'false',label:'제외'}]);
  const why=U.input({placeholder:T('사유'),aria:T('사유')});
  const err=NO(T('코드와 사유는 둘 다 있어야 한다'),'bad');err.hidden=true;
  const out=el('pre','mono');out.style.whiteSpace='pre-wrap';
  const kill=c.killedFor('A · 리스크데이터');
  ap(bar,code,scope,to,why,U.button(T('예외 제안 생성'),{primary:true,disabled:kill,onClick:()=>{
    err.hidden=true;out.textContent='';
    if(!(code.value||'').trim()||!(why.value||'').trim()){err.hidden=false;return}
    out.textContent=JSON.stringify({proposal:T('코드 대상여부 예외'),code:code.value.trim(),
      scope_ledger:scope.value,to_in_scope:to.value==='true',reason:why.value.trim(),
      apply_path:'risk_lib/datamodel/code_scope.py',
      procedure:[T('규칙 또는 예외 등재'),T('파이프라인 재실행'),T('자체검증 (2선)'),T('상시 독립검증 (3선) 재요청')],
      note:T('화면 매트릭스는 규칙 파생이다. 예외도 코드가 돼야 산출에 반영된다.')},null,2)}}));
  ap(card,bar,err);
  if(kill)ap(card,NO(T('비상정지 (실행 차단)'),'blocked'));
  ap(card,out);ap(root,card)}

/* ══════════════ 등록 ════════════════════════════════════════════════ */

NG.screen('rdm',{group:GRP,sub:null,title:'RDM',build:rdm});
NG.screen('sources',{group:GRP,sub:'RDM',title:'원천·계약',build:sources});
NG.screen('dq-recon',{group:GRP,sub:'RDM',title:'DQ·대사',build:dqRecon});
NG.screen('exceptions',{group:GRP,sub:'RDM',title:'예외·조치',build:exceptions});
NG.screen('collateral',{group:GRP,sub:'RDM',title:'담보·보증',build:plain});
NG.screen('aggregates',{group:GRP,sub:'RDM',title:'집계 원장',build:plain});
NG.screen('funds',{group:GRP,sub:'선행 원장',title:'집합투자증권',build:plain});
NG.screen('derivatives',{group:GRP,sub:'선행 원장',title:'파생상품',build:plain});
NG.screen('securitisation',{group:GRP,sub:'선행 원장',title:'유동화',build:plain});
NG.screen('data-model',{group:GRP,sub:'카탈로그·코드',title:'데이터모델',build:dataModel,
  tabs:[{key:'catalog',title:'카탈로그',build:catTab},
        {key:'usage',title:'원장→화면',build:useTab},
        {key:'figures',title:'수치→원장',build:figTab}]});
NG.screen('code-master',{group:GRP,sub:'카탈로그·코드',title:'코드 마스터',build:codeMaster});
NG.screen('code-map',{group:GRP,sub:'카탈로그·코드',title:'코드 매핑',build:codeMap});
})();
