/* screens/control.js: 통제센터 (콕핏 · 의사결정 큐 · 마감 워크플로 · 시뮬레이션 · */
/* 한도관리 · 거액 설정 · 거액 분석). */
/* 규칙 (설계 사양 5장, 수용기준 A7·A8·A12·A18·A21·A23): */
/* - 건수·합계는 서버 집계 객체(D.x_*)에서만 읽는다. 프레임의 행수를 총계로 */
/* 찍지 않는다. 표본 프레임은 NG.ui.table / NG.ui.truncBadge 가 배지를 단다. */
/* - 톤은 TN(출처, 값) 하나에서만 나온다. 이 파일에는 톤 사전이 없다. */
/* - 문자열은 전부 NG.T / NG.TF 를 지나며 카탈로그는 i18n/ng_control.py 다. */
/* 원장 값·검증명·인용·식별자·지문은 번역하지 않고 원문 그대로 찍는다. */
/* - 원장 산문(사유·상세·발견사항)은 NG.text() 를 지나 긴 대시를 정리한다. */
/* - 공용 도우미(renderForm·domainBrowser·almEvidence·almSources·judgeGlyph)는 */
/* shared.js 만 정의한다. 여기서는 NG.shared 로 호출만 한다. */
(function(){
'use strict';
const NG=window.NG,U=NG.ui,CH=NG.charts,FR=NG.frame,el=U.el,ap=U.ap;
const T=NG.T,TF=NG.TF,fmt=NG.fmt,tx=NG.text;
const ST=U.simpleTable,TB=U.table,BG=U.badge,NO=U.note,M=fmt.money,P=fmt.pct,NI=fmt.int,TN=NG.tone;
/* 카드. base.css 가 section{display:none} 을 걸어 두어 NG.ui.section 의 */
/* 비접힘 분기(section.card.sec)는 화면에 보이지 않는다. 접힘 카드만 */
/* NG.ui.section(details)을 쓰고, 펼친 카드는 같은 .card>h3 마크업을 직접 만든다. */
function CD(root,t,o){const c=S(t,o);ap(root,c);return c}
function S(t,o){o=o||{};if(o.folded)return U.section(t,o);
const c=el('div','card sec');ap(c,el('h3',null,o.raw?t:T(t)));return c}
const FOF=n=>FR.frameOf(n);
const IX=f=>FR.frameIdx(f);
const nz=v=>(typeof v==='number'&&isFinite(v))?v:0;
const cnt=n=>TF('{n}건',{n:n});
const srv=n=>TF('전량 {N} (서버 집계)',{N:n});
const sv=v=>TN('limit.severity',v);
const dv=v=>fmt.orDash(v),MT=t=>el('div','meta',t),SP=t=>el('span','meta',t);
const DL=U.dotlist,K=U.kpi,KR=U.kpiRow,BT=U.button,CP=U.chips,MR=U.meter,IN=U.input,SL=U.select;
/* 원장 표 제목은 카탈로그 한국어 라벨을 원문 그대로 쓴다. 카탈로그 라벨은 번역 대상이 아니다. */
function tt(name,o){const k=NG.cat(name)||{};return Object.assign({title:k.korean||name,raw:true},o||{})}
/* 금액 입력 칸의 표시 단위와 목록·분포의 표시 개수. 규제값이 아니라 표시 규약이다. */
const EOK=1e8,TOPN=6,BINS=8,PCTN=v=>fmt.num(v)+'%';
/* 접힌 카드는 열 때 그린다. 콕핏이 두 화면 높이를 넘지 않게 하는 장치다. */
function lazy(sec,fn){sec.addEventListener('toggle',()=>{if(sec.open&&!sec.dataset.built){sec.dataset.built='1';fn(sec)}});return sec}
/* 프레임의 부분집합. 컬럼·라벨·원장명·전체 행수를 그대로 물려주므로 */
/* 표본 배지가 서버 전체 행수 기준으로 붙는다. */
function subFrame(f,rows){const n=rows.length;return {table:f.table,columns:f.columns,labels:f.labels,rows:rows,shown:n,total:f.total}}
function agg(f,kc,sc,extra){const i=IX(f),ks=[],a={};
f.rows.forEach(r=>{const k=r[i[kc]];if(ks.indexOf(k)<0){ks.push(k);a[k]={n:0,amt:0,x:r[i[extra]]}}a[k].n+=1;a[k].amt+=nz(r[i[sc]])});
return ks.map(k=>extra?[k,a[k].n,a[k].amt,a[k].x]:[k,a[k].n,a[k].amt])}

/* ══════════════ 콕핏 ══════════════════════════════════════════════════ */

/* 인사이트: 원장·서버 집계에서 규칙으로 뽑은 줄. 게이트 줄은 언제나 있다. */
function insights(c){
const D=c.D,g=D.x_gate||{},xc=D.x_capital||{},xq=D.x_queue||{},xl=D.x_limits||{},xe=D.x_evidence||{};
const s=g.self||{},iv=g.independent||{},ov=g.overall||{},out=[];
out.push({tone:ov.tone||'blocked',onClick:()=>c.drawer.gate(),text:T('전체 판정')+' '+dv(ov.status)+' · '+T('상시 독립검증 (3선)')+' '+dv(iv.status)+' ('+dv(iv.request_id)+') · '+T('자체검증 (2선)')+' '+TF('PASS {pass} · WARN {warn} · FAIL {fail} · 규제미달 {blocks} · 미실행 {not_run} (항등식 {identity} 제외)',{pass:s.pass,warn:s.warn,fail:s.fail,blocks:s.blocks,not_run:s.not_run,identity:s.identity_excluded})});
(s.blocking_checks||[]).forEach(k=>out.push({tone:NG.checkTone({check_name:k.check_name,status:k.status,blocks_approval:true}),text:k.check_name+' '+k.status+' ('+dv(k.domain)+')',onClick:()=>c.drawer.check(k.check_name)}));
const tiers=(xc.tiers||[]).map(t=>t.label+' '+P(t.ratio,2)+' / '+T('소요')+' '+P(t.required,2)+' '+fmt.pp(nz(t.surplus)*100));
if(tiers.length)out.push({tone:xc.tone||'neutral',onClick:()=>c.go('capital-verdict'),text:T('구속 계층')+' '+dv(xc.binding_tier)+' · '+tiers.join(' · ')+(xc.mda_zone?' · '+T('MDA 구간 진입'):'')});
if(nz(xc.n_fail_quarters))out.push({tone:xc.tone||'warn',text:T('스트레스 경로')+' '+TF('미통과 분기 {n}건',{n:xc.n_fail_quarters})});
const ts=xl.two_sources||{};
if(ts.law)out.push({tone:NG.checkTone(ts.check||{}),onClick:()=>c.go('limits'),text:twoSrc(ts)});
const pf=(xl.populations||{}).limits_full;
if(pf){const nb=nz(pf.breach)+nz(pf.critical);
out.push({tone:sv(nb?'BREACH':(nz(pf.warn)?'WARN':'OK')),onClick:()=>c.go('limits'),text:T('한도 소진')+' '+srv(pf.total)+' · '+T('위반')+' '+NI(nb)+' · '+T('경보')+' '+NI(pf.warn)+' · '+T('한도 내')+' '+NI(pf.ok)})}
const ex=xq.exceptions||{};
if(nz(ex.total))out.push({tone:TN('exception.severity',(ex.by_severity&&ex.by_severity[0])?ex.by_severity[0].severity:''),onClick:()=>c.go('exceptions'),text:T('예외 스트림')+' '+srv(ex.total)+' · '+(ex.by_severity||[]).map(v=>v.severity+' '+NI(v.n)).join(' · ')+' · '+(ex.by_source||[]).map(v=>v.source_ledger+' '+NI(v.n)).join(' · ')});
const rc=(g.recalc||{}).counts||{};
out.push({tone:TN('recalc.state',rc['불일치']?'불일치':(rc['미보고']?'미보고':'일치')),onClick:()=>c.go('validation'),text:T('재계산 커버리지')+' · '+T('일치')+' '+NI(rc['일치'])+' · '+T('불일치')+' '+NI(rc['불일치'])+' · '+T('미보고')+' '+NI(rc['미보고'])});
(xq.close_blockers||[]).forEach(b=>out.push({tone:TN('close_gate.decision',b.kind),onClick:()=>c.go('close-workflow'),text:T('마감 차단 요인')+' · '+tx(b.detail)}));
if(nz(xe.total))out.push({tone:TN('evidence_node.status',xe.complete===xe.total?'완결':'검토'),text:T('증빙 계보 완결')+' '+NI(xe.complete)+' / '+NI(xe.total)});
return out;
}
/* 동일차주 두 산출을 한 줄에 나란히 적는다. 한쪽만 적지 않는다. */
function twoSrc(ts){
const law=ts.law||{},eng=ts.engine;
return T('원장')+' '+dv(law.framework)+' ('+dv(law.basis)+') '+T('위반')+' '+cnt(nz(law.n_breach))+' · '+T('한도엔진')+' ('+(eng?dv(eng.basis):T('미산출'))+') '+T('위반')+' '+(eng?cnt(nz(eng.n_breach)):T('미산출'))+' · '+dv(ts.state);
}
/* 실린 실행을 나란히 놓는다. 지문이 갈리면 같은 기준일이라도 다른 산출이다. */
function runTb(c){
const ks=Object.keys(c.RUNS).sort();
return ST(['기준일','실행 식별','헤드라인 지문','원장 행수','3선 게이트'],ks.map(k=>{const p=c.RUNS[k],m=p.meta||{};return [k,dv(m.run_id),dv(m.digest).slice(0,16),m.n_rows,dv((p.independent||{}).status)]}));
}
function evDr(c,n){
const RUNS=c.RUNS,ks=Object.keys(RUNS).sort(),digests=[];
ks.forEach(k=>{const dg=(RUNS[k].meta||{}).digest;if(digests.indexOf(dg)<0)digests.push(dg)});
const nk=ks.length,nd=digests.length;
c.drawer.open({title:n.node_id+' · '+n.stage,tabs:[{label:'판정 근거',build:r=>{
ap(r,ST(['항목','값'],[[T('단계'),n.stage],[T('내용'),n.label],[T('출처 원장'),dv(n.ref)],[T('상태'),BG(dv(n.status),TN('evidence_node.status',n.status))]]));
ap(r,el('h4',null,T('실행 간 대조')),runTb(c),MT(TF('{n}개',{n:nk})+' · '+TF('{n}종',{n:nd})));
}}]});
}
function cockpit(root,c){
const D=c.D,g=D.x_gate||{},xc=D.x_capital||{},xq=D.x_queue||{},xe=D.x_evidence||{},xl=D.x_limits||{},sim=D.sim||{};
 /* (1) 여섯 수치 카드 */
const KN=(D.x_kpi&&D.x_kpi.numeric)||{};
ap(root,KR((D.kpis||[]).map((k,i)=>K({label:k.label,
  value:(KN[i]&&KN[i].kind==='money')?NG.fmt.money(KN[i].value):k.value,
  sub:tx(k.sub),tone:k.tone||'neutral',lineage:NG.lineage.kpi(i)})),c.meta.density));
 /* (2) 인사이트 리본 */
const r1=el('div','cols2');ap(root,r1);
const rib=S('인사이트 (한계 위반·미해소 예외·검증 상태)');ap(r1,rib);
ap(rib,DL(insights(c)),MT(T('결정론적 규칙 출력 · 같은 데이터면 같은 문장 · LLM 호출 없음')));

 /* (3) 위기상황 자본비율 경로 */
const sp=xc.stress_path||[];
if(sp.length){
const scen=[];sp.forEach(r=>{if(scen.indexOf(r.scenario)<0)scen.push(r.scenario)});
const box=S('스트레스 경로'),pane=el('div');ap(r1,box);let cur=scen[0];
ap(box,CP(scen.map(s=>({value:s,label:s,raw:true,on:s===cur})),v=>{cur=v;draw()}),pane);
const req=sim.required||{};
function draw(){
pane.innerHTML='';
const rows=sp.filter(r=>r.scenario===cur),labs=rows.map(r=>r.quarter);
const line=(k,nm)=>({name:nm,values:rows.map(r=>r[k])});
const nfail=rows.filter(r=>r.passes===false).length,bind=[];
rows.forEach(r=>{if(bind.indexOf(r.binding)<0)bind.push(r.binding)});
ap(pane,CH.multiLine([line('cet1_ratio','CET1'),line('tier1_ratio','Tier1'),line('total_ratio','Total')],labs,{title:T('스트레스 경로')+' · '+cur,fmt:v=>P(v,2),hatch:rows.map(r=>r.passes===false),rules:[{value:req.cet1,label:'CET1 '+T('소요 자본 선')},{value:req.tier1,label:'Tier1'},{value:req.total,label:'Total'}],note:TF('미통과 분기 {n}건',{n:nfail})+' · '+T('구속')+' '+bind.join(' · ')+' · '+T('원장')+' st_capital_path'}));
}
draw();
}
 /* (4)(5) 역스트레스와 한도 소진 상위 */
const two=el('div','cols2');
const rv=D.reverse_stress;
if(rv){
const b=S('역스트레스'),t=rv.resilient?'good':'bad',mins=sim.minimums||{};
ap(b,MR('임계 심도',Math.min(nz(rv.critical_severity),1),1,t));
ap(b,MT(T('임계 심도')+' '+fmt.num(rv.critical_severity)+' · '+dv(rv.metric)+' · '+T('목표')+' '+P(rv.target_ratio,2)+' · '+T('최저 기준')+' '+P(mins[rv.metric],2)+' · '+T('현행')+' '+P(rv.base_ratio,2)));
ap(b,MT(T('함의 국내총생산 충격')+' '+P(rv.implied_gdp_shock,2)+' · '+T('함의 부도시손실률 가산')+' '+fmt.pp(nz(rv.implied_lgd_addon)*100)+' · '+T('수렴')+' '+(rv.converged?T('통과'):T('미통과'))));
ap(b,K({label:'역스트레스 임계 심도',value:fmt.num(rv.critical_severity),tone:t,delta:false,lineage:'reverse_stress.severity'}));
ap(two,b);
}
const lf=D.limits;
if(lf){
const i=IX(lf),b=S('한도 소진 상위');
ap(b,MT(T('위반 보고 (차주 버킷 포함)')),U.truncBadge(lf));
ap(b,CH.barList(lf.rows.slice().sort((a,b2)=>nz(b2[i.utilisation])-nz(a[i.utilisation])).slice(0,TOPN).map(r=>({
label:r[i.limit]+' · '+r[i.bucket],value:nz(r[i.utilisation])*100,tone:sv(r[i.severity]),sub:T('심각도')+' '+dv(r[i.severity])})),{money:false,fmt:PCTN}));
ap(b,MT(twoSrc(xl.two_sources||{})));
ap(two,b);
}
ap(root,two);
 /* (6) 예외 스트림 */
const ex=xq.exceptions||{};
const r3=el('div','cols3');ap(root,r3);
const bx=S('예외 스트림');ap(r3,bx);
ap(bx,MT(srv(ex.total)),DL((ex.rows||[]).slice(0,TOPN).map(r=>({tone:TN('exception.severity',r.severity),text:r.exception_id+' · '+tx(r.finding)+' · '+dv(r.owner_role),right:dv(r.status)+' · '+T('기한 (일)')+' '+NI(r.due_days),onClick:()=>c.go('exceptions')}))));
ap(bx,BT(T('예외·조치'),{onClick:()=>c.go('exceptions')}));

 /* (7)(8) 표준방법 구성과 통제 진행 */
const grid=el('div','cols2');
const sa=FOF('rwa_sa_bucket');
if(sa){const i=IX(sa);
ap(grid,CH.hbars(sa.rows.map(r=>({label:r[i.asset_class]+' · RW '+P(r[i.risk_weight],0),value:r[i.rwa],sub:T('익스포저')+' '+M(r[i.ead])})).sort((a,b)=>b.value-a.value).slice(0,7),{title:T('위험가중자산 구성 (표준방법)'),src:sa}))}
const ctl=S('통제 진행 (증빙·대사·검증)'),s2=g.self||{},rec=xq.recon||{},dq=xq.dq||{};
const nrf=(rec.fail||[]).length;
ap(ctl,MR('증빙 계보 완결',xe.complete,xe.total,TN('evidence_node.status',xe.complete===xe.total?'완결':'검토')));
ap(ctl,MR('대사 통과',nz(rec.total)-nrf,rec.total,TN('val_check.status',nrf?'FAIL':'PASS')));
ap(ctl,MR('자체검증 (2선)',s2.pass,s2.total,s2.tone));
ap(ctl,MT(T('DQ 실패 (규칙별)')+' '+srv(dq.total)));
ap(grid,ctl);ap(root,grid);
 /* (9) 의사결정 큐 요약 */
const apv=g.approvals||{},sub=g.submission||{},holds=apv.holds||[],nk=holds.length;
const dq2=S('의사결정 큐');ap(r3,dq2);
ap(dq2,MT(TF('결재 대기 {pending} · 승인 {approved} · 반려 {returned} · 보류 사유 {kinds}종 · 제출 {reviewed}/{total}',{pending:apv['대기'],approved:apv['승인'],returned:apv['반려'],kinds:nk,reviewed:sub.reviewed,total:sub.total})));
ap(dq2,DL(holds.map(h=>({tone:TN('hold.reason_kind',h.reason_kind),text:h.reason_kind+' · '+tx(h.reason_text)+' · '+(h.subject_types||[]).join(', '),right:cnt(h.n),onClick:()=>c.go('decision-queue')}))));
ap(dq2,BT(T('의사결정 큐'),{onClick:()=>c.go('decision-queue')}));

 /* (10) 증빙 계보 7단계 */
const nodes=(xe.nodes||[]).map(n=>(xe.n6&&n.node_id==='N6')?{node_id:n.node_id,stage:n.stage,ref:n.ref,label:xe.n6.label,status:xe.n6.status}:n);
const fl=S('증빙 계보 · 7단계 (단계를 누르면 상세)');ap(r3,fl);
ap(fl,DL(nodes.map(n=>({tone:TN('evidence_node.status',n.status),text:n.node_id+' · '+n.stage+' · '+n.label,right:dv(n.status)+' · '+dv(n.ref),onClick:()=>evDr(c,n)}))));

 /* (11) 원장 표 (접힘) */
const led=CD(root,'원장 표 (콕핏 근거)',{folded:true});
lazy(led,box=>{
const rc=D.reconciliation;
if(D.evidence_edges)ap(box,TB(D.evidence_edges,tt('gov_evidence_edge')));
if(rc){const i=IX(rc);ap(box,TB(rc,tt('rdm_reconciliation',{rowClass:r=>TN('val_check.status',r[i.status])==='bad'?'bad':null})))}
if(D.contracts)ap(box,TB(D.contracts,tt('rdm_source_contract')));
if(D.approvals)ap(box,TB(D.approvals,tt('gov_approval')));
if(D.form_checks)ap(box,TB(D.form_checks,tt('reg_form_check')));
ap(box,el('h4',null,T('실행 간 대조')),runTb(c));
});

}

/* ══════════════ 의사결정 큐 ══════════════════════════════════════════ */

function decisionQueue(root,c){
const D=c.D,g=D.x_gate||{},xq=D.x_queue||{},xcl=D.x_close||{};
const apv=g.approvals||{},sub=g.submission||{},holds=xq.holds||[];
ap(root,el('p','lead',T('결재를 막는 것과 그것을 푸는 조치를 한자리에 모은다')+'. '+T('건수는 서버 집계이고 아래 표본 행은 확인용이다')));
 /* (1) 보류 */
const nk=holds.length;
const hb=CD(root,'보류');
ap(hb,MT(TF('{n}종',{n:nk})+' · '+T('결재')+' '+srv(apv.total)));
if(!nk)ap(hb,NO(T('큐가 비어 있다'),'good'));
holds.forEach(h=>{
const t=TN('hold.reason_kind',h.reason_kind),card=el('div','card');
const head=el('div','trow');
ap(head,BG(h.reason_kind,t),' ',el('b',null,tx(h.reason_text)),' ',BG(cnt(h.n),t));
ap(card,head,MT(T('대상 유형')+' '+((h.subject_types||[]).join(', ')||T('없음'))));
const ck=h.checks||[];
if(ck.length)ap(card,ST(['검증 항목','상태','상세','판정 근거'],ck.map(k=>[k.check_name,BG(k.status,NG.checkTone(k)),tx(k.detail),dv(k.domain)]),{onRow:(x,j)=>c.drawer.check(ck[j].check_name)}));
const ub=h.unblock;
if(ub)ap(card,ST(['경보 유형','연동 조치','담당 역할','SLA (일)','제출 차단'],[[dv(ub.alert_type),tx(ub.bound_action),dv(ub.owner_role),NI(ub.sla_days),ub.blocks_submission?T('제출 차단'):T('없음')]]));
else ap(card,NO(T('담당 미확인, 일치하는 gov_alert_policy 행 없음'),'blocked'));
ap(hb,card);
});

 /* (2) 결재 분포 */
const db=CD(root,'결정 분포');
ap(db,MT(T('결재')+' '+srv(apv.total)));
ap(db,DL(['대기','승인','반려'].map(k=>({tone:TN('gov_approval.decision',k),text:k,right:NI(apv[k])+' / '+NI(apv.total)}))));
const bs=apv.by_subject_type||{};
ap(db,MT(T('대상 유형별')+' '+Object.keys(bs).map(k=>k+' '+NI(bs[k])).join(' · ')));
ap(db,BG(T('직무분리 위반')+' '+NI(apv.segregation_violations),nz(apv.segregation_violations)?'bad':'good'));

 /* (3) 예외 */
const ex=xq.exceptions||{},eb=CD(root,'예외');
ap(eb,MT(srv(ex.total)+' · '+T('심각도별')+' '+(ex.by_severity||[]).map(v=>v.severity+' '+NI(v.n)).join(' · ')+' · '+T('기한별')+' '+(ex.by_due||[]).map(v=>TF('{n}일',{n:v.due_days})+' '+NI(v.n)).join(' · ')+' · '+T('출처별')+' '+(ex.by_source||[]).map(v=>v.source_ledger+' '+NI(v.n)+' ('+v.owner_role+')').join(' · ')));
ap(eb,ST(['예외 식별자','출처 원장','심각도','상태','담당 역할','기한 (일)','발견 사항','조치'],(ex.rows||[]).map(r=>[r.exception_id,r.source_ledger+' · '+r.source_key,BG(r.severity,TN('exception.severity',r.severity)),BG(r.status,TN('exception.status',r.status)),dv(r.owner_role),NI(r.due_days),tx(r.finding),tx(r.action)])));
ap(eb,BT(T('예외·조치'),{onClick:()=>c.go('exceptions')}));
 /* (4) 제출 분포 */
const sb=CD(root,'제출 현황');
ap(sb,DL(['draft','reviewed','approved','submitted'].map(k=>({tone:TN('reg_submission.status',k),text:k,right:NI(sub[k])+' / '+NI(sub.total)}))),MT(T('원장')+' reg_submission · '+srv(sub.total)));
 /* (5) 마감 차단 */
const cb=CD(root,'마감 차단 요인'),iss=(xcl.issues||[]).filter(x=>x.stage==='마감');
ap(cb,DL(iss.map(x=>({tone:TN('close_gate.decision',x.kind),text:x.stage+' · '+tx(x.detail),right:x.kind,onClick:()=>c.go('close-workflow')}))));
if(!iss.length)ap(cb,NO(T('큐가 비어 있다'),'good'));
ap(cb,BT(T('마감 워크플로'),{onClick:()=>c.go('close-workflow')}));

 /* (6) 심각도·톤 매핑 */
const mp=CD(root,'심각도·톤 매핑',{folded:true});
lazy(mp,box=>{
ap(box,ST(['출처 어휘','값','톤','표시 기호'],((D.x_severity||{}).map||[]).map(r=>[r.source,r.value,r.tone,NG.glyph(r.tone)])));
ap(box,MT(T('원장')+' x_severity · '+T('화면은 자기 톤 사전을 두지 않는다')));
});

}

/* ══════════════ 마감 워크플로 ════════════════════════════════════════ */

function tkDr(c,t){
c.drawer.open({title:t.task_id+' · '+t.task_name,tabs:[{label:'판정 근거',build:r=>{
ap(r,ST(['항목','값'],[[T('순서'),t.sequence],[T('단계 레인'),t.phase],[T('과업명'),t.task_name],[T('선행 과업'),dv(t.predecessors)],[T('담당 역할'),dv(t.owner_role)],[T('수행 에이전트'),dv(t.agent_ref)],[T('승인 필요'),t.requires_approval?T('승인 필요'):T('없음')],[T('기한 (영업일)'),t.due_business_days],[T('증빙 유형'),T(t.evidence_kind)],[T('증빙 테이블'),dv(t.evidence_table)],[T('증빙 행수'),t.evidence_rows],[T('이행 상태'),BG(dv(t.status),TN('close_task.status',t.status))],[T('게이트 판정'),BG(dv(t.decision),TN('close_gate.decision',t.decision))],[T('차단 요인'),dv(t.blocked_by)],[T('판정 사유'),tx(t.reason)]]));
const f=FOF(t.evidence_table);
if(f)ap(r,TB(f));
else ap(r,NO(T('원장 행 없음'),'warn'));
}}]});
}
function closeWorkflow(root,c){
const D=c.D,xcl=D.x_close||{},tasks=xcl.tasks||[],st=xcl.statements||{},g=D.x_gate||{};
ap(root,el('p','lead',T('마감 과업과 게이트 판정을 단계 레인으로 세운다. 판정과 사유는 게이트 원장 값이다')));
const phases=[];tasks.forEach(t=>{if(phases.indexOf(t.phase)<0)phases.push(t.phase)});
const board=el('div','board');board.style.gridTemplateColumns='repeat('+phases.length+',minmax(0,1fr))';
phases.forEach(p=>{
const col=el('div'),ul=el('ul');
const mine=tasks.filter(t=>t.phase===p),nmine=mine.length;
ap(col,el('h3',null,p));
mine.forEach(t=>{
const li=el('li'),tn=TN('close_task.status',t.status);
ap(li,NG.glyph(tn),el('b',null,t.task_id),el('span','txt',t.task_name),BG(dv(t.decision),TN('close_gate.decision',t.decision)));
li.tabIndex=0;li.classList.add('click');
li.onclick=()=>tkDr(c,t);li.onkeydown=e=>{if(e.key==='Enter')tkDr(c,t)};
ap(ul,li)});
ap(col,ul,MT(T('과업')+' '+cnt(nmine)));
ap(board,col)});
const bb=CD(root,'마감 보드');
ap(bb,board,MT(T('원장')+' opr_close_task · opr_close_gate · '+T('행 클릭으로 상세를 연다')));

const tb=CD(root,'과업');
ap(tb,ST(['과업','과업명','담당 역할','수행 에이전트','기한 (영업일)','증빙 유형','증빙 행수','이행 상태','게이트 판정','판정 사유'],tasks.map(t=>[t.task_id,t.task_name,dv(t.owner_role),dv(t.agent_ref),t.due_business_days,T(t.evidence_kind),t.evidence_rows,BG(dv(t.status),TN('close_task.status',t.status)),BG(dv(t.decision),TN('close_gate.decision',t.decision)),tx(t.reason)]),{onRow:(x,j)=>tkDr(c,tasks[j])}));

 /* 마감 단계 이슈 */
const ib=CD(root,'마감 단계 이슈'),iss=(xcl.issues||[]).filter(x=>x.stage==='마감');
ap(ib,DL(iss.map(x=>({tone:TN('close_gate.decision',x.kind),text:x.stage+' · '+tx(x.detail),right:x.kind}))));
const fr=FOF('gov_run_issue');
if(fr)ap(ib,TB(fr));

 /* 고정 문장 */
const sb=CD(root,'구조적 미완');
const sm=g.submission||{};
if(st.cl12_structural)ap(sb,NO(T('CL-12 는 합성 파이프라인에서 구조적으로 미완이다. reg_submission.status 가 submitted 에 이르지 않는다.')+' · '+T('제출 건수')+' '+NI(st.submitted_count)+' / '+srv(sm.total),'warn'));
if(st.conditional_asymmetry)ap(sb,NO(T('조건부는 CL-10 을 완료하지만 CL-11 은 ConditionalApproval 기록이 있어야 풀린다. 어느 원장에도 그 기록은 없다.'),'warn'));
ap(sb,MT(T('3선 게이트')+' '+dv((g.independent||{}).status)+' · '+T('결재')+' '+srv((g.approvals||{}).total)));

}

/* ══════════════ 시뮬레이션 (설명용 산술) ═════════════════════════════ */

/* 비율 칸과 금액 칸을 한 쌍으로 묶는다. 증감액이 원본이고 비율은 거기서 만든다. */
function linked(label,base,onChange){
const st={delta:0,source:'비율'},wrap=el('div','row');
const lab=SP(label);lab.style.minWidth='150px';
const tag=U.pill(T('비율')+' · '+T('입력'));
const pi=IN({type:'number',step:'0.5',value:'0',aria:label,onInput:v=>{
st.delta=base*(parseFloat(v)||0)/100;st.source='비율';ai.value=(st.delta/EOK).toFixed(0);paint();onChange()}});
const ai=IN({type:'number',step:'100',value:'0',aria:label,onInput:v=>{
st.delta=(parseFloat(v)||0)*EOK;st.source='금액';pi.value=base?(st.delta/base*100).toFixed(3):'0';paint();onChange()}});
pi.style.flex='0 0 88px';ai.style.flex='0 0 116px';
function paint(){tag.textContent=T(st.source)+' · '+T('입력');tag.className='pill'+(st.delta?' warn':'')}
st.refresh=()=>{pi.value=base?(st.delta/base*100).toFixed(3):'0';ai.value=(st.delta/EOK).toFixed(0);paint()};
ap(wrap,lab,pi,SP('%'),ai,SP(T('억원')),tag,SP(T('기준')+' '+M(base)));
st.wrap=wrap;st.base=base;
return st;
}
function simulation(root,c){
const D=c.D,Sm=D.sim;
if(!Sm||!Sm.components){ap(root,NO(T('시뮬레이션 기준값이 payload 에 없다. 화면을 그리지 않는다.'),'bad'));return}
ap(root,el('p','lead',T('자본비율 항등식의 설명용 산술이다. 위험가중자산과 자본을 움직여 비율 반응을 본다. 재계산이 아니며 승인·제출값 아님')));
const comps=Sm.components,inputs={};
let redraw=()=>{};
const box=CD(root,'입력');
const total=linked(T('위험가중자산 합계'),Sm.internal_total,()=>{
comps.forEach(x=>{inputs[x.key].delta=Sm.internal_total?total.delta*x.value/Sm.internal_total:0;inputs[x.key].refresh()});
redraw()});
ap(box,total.wrap);
const cb=el('div');cb.style.cssText='border-left:2px solid var(--hairline);padding-left:12px;margin:6px 0';
comps.forEach(x=>{inputs[x.key]=linked(x.label,x.value,()=>{
total.delta=comps.reduce((a,y)=>a+inputs[y.key].delta,0);total.refresh();redraw()});
ap(cb,inputs[x.key].wrap)});
const std=linked(T('표준방법 산출 합 (하한 분모)'),Sm.standardised_total,()=>redraw());
ap(cb,std.wrap);ap(box,cb);
const cap={cet1:linked('CET1',Sm.capital.cet1,()=>redraw()),at1:linked('AT1',Sm.capital.at1,()=>redraw()),t2:linked('T2',Sm.capital.t2,()=>redraw())};
ap(box,cap.cet1.wrap,cap.at1.wrap,cap.t2.wrap);
const lev=linked(T('익스포저 측정치'),Sm.leverage.exposure_measure,()=>redraw());
ap(box,lev.wrap);
const bar=el('div','toolbar'),saved=[];
ap(bar,BT(T('이 조정안 저장'),{onClick:()=>{saved.push(state());redraw()}}),BT(T('입력 초기화'),{onClick:()=>{[total,std,lev,cap.cet1,cap.at1,cap.t2].concat(comps.map(x=>inputs[x.key])).forEach(x=>{x.delta=0;x.source='비율';x.refresh()});redraw()}}));
ap(box,bar);
const pane=el('div');ap(root,pane);
function state(){
const parts=comps.map(x=>({key:x.key,label:x.label,base:x.value,now:x.value+inputs[x.key].delta}));
const internal=parts.reduce((a,x)=>a+x.now,0),sd=Sm.standardised_total+std.delta;
const floorAmt=nz(Sm.floor_pct)*sd,addOn=Math.max(0,floorAmt-internal),rwa=internal+addOn;
const cet1=Sm.capital.cet1+cap.cet1.delta,at1=Sm.capital.at1+cap.at1.delta,t2=Sm.capital.t2+cap.t2.delta;
const tier1=cet1+at1,tot=tier1+t2,exp=Sm.leverage.exposure_measure+lev.delta;
return {parts:parts,internal:internal,std:sd,floorAmt:floorAmt,addOn:addOn,binding:addOn>0,rwa:rwa,cet1:cet1,at1:at1,t2:t2,tier1:tier1,total:tot,exposure:exp,ratios:{cet1:rwa?cet1/rwa:0,tier1:rwa?tier1/rwa:0,total:rwa?tot/rwa:0},leverage:exp?tier1/exp:0}}
const TIERS=[['cet1','CET1'],['tier1','Tier1'],['total','Total']];
function draw(){
pane.innerHTML='';
const s=state(),req=Sm.required||{},min=Sm.minimums||{};
ap(pane,KR(TIERS.map(p=>{const k=p[0],cur=s.ratios[k];
const before=(k==='cet1'?Sm.capital.cet1:k==='tier1'?Sm.capital.cet1+Sm.capital.at1:Sm.capital.cet1+Sm.capital.at1+Sm.capital.t2)/Sm.final_total;
return K({label:p[1],raw:true,value:P(cur,2),delta:false,tone:cur>=req[k]?'good':(cur>=min[k]?'warn':'bad'),sub:T('현행')+' '+P(before,2)+' · '+T('소요')+' '+P(req[k],2)+' · '+T('잉여')+' '+fmt.pp((cur-req[k])*100)})}).concat([K({label:'레버리지',value:P(s.leverage,2),delta:false,tone:s.leverage>=Sm.leverage.required?'good':'bad',sub:T('현행')+' '+P(Sm.leverage.ratio,2)+' · '+T('소요')+' '+P(Sm.leverage.required,2)})]),c.meta.density));
const bufTotal=Object.keys(Sm.buffers||{}).reduce((a,k)=>a+nz(Sm.buffers[k]),0);
const zone=k=>s.ratios[k]>=req[k]?T('요구 충족'):(s.ratios[k]>=min[k]?T('완충자본 잠식'):T('최저비율 미달'));
const rc=S('요구비율 층과 도달 구간');
ap(rc,ST(['계층','조정 후 비율','최저 기준','버퍼','소요','잉여','구간'],TIERS.map(p=>[p[1],P(s.ratios[p[0]],2),P(min[p[0]],2),P(bufTotal,2),P(req[p[0]],2),fmt.pp((s.ratios[p[0]]-req[p[0]])*100),zone(p[0])])));
ap(rc,ST(['버퍼','비율'],Object.keys(Sm.buffers||{}).map(k=>[k,P(Sm.buffers[k],2)])));
ap(rc,MT(T('완충자본 잠식 구간은 최저비율은 넘었으나 요구비율에 못 미치며 배당·성과급이 제한된다')));
ap(pane,rc);
const fc=S('산출하한 (output floor)');
ap(fc,ST(['항목','값'],[[T('내부산출 합'),M(s.internal)],[T('표준방법 산출 합'),M(s.std)],[T('하한 비율'),P(Sm.floor_pct,1)],[T('하한 금액'),M(s.floorAmt)],[T('산출하한 가산액'),M(s.addOn)],[T('최종 위험가중자산'),M(s.rwa)],[T('하한이 무는가'),s.binding?T('구속'):T('없음')]]));
if(s.binding)ap(fc,NO(T('하한이 물어 내부산출을 더 줄여도 최종 위험가중자산이 줄지 않는다'),'warn'));
ap(pane,fc);
const cc=S('구성요소별 조정');
ap(cc,ST(['구성요소','기준','조정 후','증감','비중','입력'],s.parts.map(p=>[p.label,M(p.base),M(p.now),M(p.now-p.base),P(s.internal?p.now/s.internal:0,1),T(inputs[p.key].source)])));
ap(pane,cc);
  /* 파급효과 */
const rip=[];
const so=Sm.single_obligor;
if(so&&so.threshold_value!=null){const b4=nz(so.threshold_value)*(Sm.capital.cet1+Sm.capital.at1);
rip.push([dv(so.limit_id)+' ('+dv(so.threshold_formula)+')',M(b4),M(nz(so.threshold_value)*s.tier1),M(nz(so.threshold_value)*s.tier1-b4),dv(so.evidence_status)])}
if(Sm.icaap){const av=Sm.icaap.available_capital+cap.cet1.delta+cap.at1.delta+cap.t2.delta;
rip.push([T('내부자본 가용자본'),M(Sm.icaap.available_capital),M(av),M(av-Sm.icaap.available_capital),T('원장')+' icaap']);
rip.push([T('내부자본 여유'),M(Sm.icaap.buffer),M(av-Sm.icaap.ec),M(av-Sm.icaap.ec-Sm.icaap.buffer),T('원장')+' icaap'])}
if(Sm.irrbb&&Sm.irrbb.delta_eve!=null){const b4=Math.abs(Sm.irrbb.delta_eve)/(Sm.capital.cet1+Sm.capital.at1);
const af=s.tier1?Math.abs(Sm.irrbb.delta_eve)/s.tier1:0;
rip.push([T('금리리스크 경제적가치 변동 / 기본자본')+' ('+dv(Sm.irrbb.basis)+' · '+dv(Sm.irrbb.scenario)+')',P(b4,2),P(af,2),fmt.pp((af-b4)*100),T('원장')+' alm_irrbb_result'])}
const rp=S('파급효과');
ap(rp,ST(['연동 항목','현행','조정 후','변화','출처'],rip));
ap(rp,NO(T('내부자본 소요액과 금리리스크 아웃라이어 판정은 모형·원장 값이며 이 화면이 다시 계산하지 않는다'),'neutral'));
ap(pane,rp);
  /* 목표 역산 */
const gs=S('목표 역산'),gb=el('div','toolbar'),gout=el('div');
let key='cet1',tgt=nz(req.cet1)*100;
const sel=SL(TIERS.map(p=>({value:p[0],label:p[1]})),v=>{key=v;goal()});
const ti=IN({type:'number',step:'0.1',value:tgt.toFixed(1),aria:T('목표'),onInput:v=>{tgt=parseFloat(v)||0;goal()}});
ti.style.flex='0 0 100px';
ap(gb,SP(T('대상 비율')),sel,SP(T('목표')+' (%)'),ti);
ap(gs,gb,gout);
function goal(){
gout.innerHTML='';
const capv=key==='cet1'?s.cet1:key==='tier1'?s.tier1:s.total,g2=tgt/100;
if(g2<=0){ap(gout,NO(T('목표 비율을 입력한다'),'neutral'));return}
const needRwa=capv/g2,needCap=g2*s.rwa;
ap(gout,ST(['방법','필요 수준','현재 대비 증감','판정'],[[T('위험가중자산으로 맞추기'),M(needRwa),M(needRwa-s.rwa),needRwa<s.floorAmt?T('하한이 물어 도달 불가'):T('도달 가능')],[T('자본으로 맞추기'),M(needCap),M(needCap-capv),T('도달 가능')]]));
if(needRwa<s.floorAmt)ap(gout,NO(T('위험가중자산 축소만으로는 하한 금액 아래로 갈 수 없어 해가 꺾인다')+' · '+M(needRwa)+' < '+M(s.floorAmt),'warn'));
}
goal();ap(pane,gs);
  /* 2축 민감도 */
const steps=[];for(let k=-2;k<=2;k++)steps.push(k*0.05);
const mat=steps.map(dr=>steps.map(dc=>{
const i2=s.internal*(1+dr),r2=i2+Math.max(0,s.floorAmt-i2);
return r2?(s.cet1*(1+dc))/r2:0}));
const labs=steps.map(x=>fmt.pp(x*100));
const hc=S('2축 민감도 (보통주자본비율)');
ap(hc,CH.heat(mat,labs.map(x=>'RWA '+x),labs.map(x=>'CET1 '+x),{title:T('2축 민감도 (보통주자본비율)'),fmt:v=>P(v,2),note:T('경계선이 요구비율 등고선이며 산출하한은 각 칸에서 다시 적용된다')}));
ap(pane,hc);
if(saved.length){
const keys=[['CET1 '+T('비율'),x=>P(x.ratios.cet1,2)],['Tier1 '+T('비율'),x=>P(x.ratios.tier1,2)],['Total '+T('비율'),x=>P(x.ratios.total,2)],[T('레버리지'),x=>P(x.leverage,2)],[T('최종 위험가중자산'),x=>M(x.rwa)],[T('산출하한 가산액'),x=>M(x.addOn)],['CET1',x=>M(x.cet1)],['Tier1',x=>M(x.tier1)],['Total',x=>M(x.total)]];
const cols=[{key:'k',label:'항목'}].concat(saved.map((x,i)=>({key:'c'+i,label:T('조정안')+' '+NI(i+1),raw:true})));
const sc=S('조정안 비교');
ap(sc,ST(cols,keys.map(p=>[p[0]].concat(saved.map(p[1])))));
ap(sc,MT(T('이 실행에서만 유지되며 원장에 기록되지 않는다')));
ap(pane,sc)}
}
redraw=draw;draw();
const bs=CD(root,'기준값의 출처');
ap(bs,ST(['항목','값'],[[T('내부산출 합'),M(Sm.internal_total)],[T('표준방법 산출 합'),M(Sm.standardised_total)],[T('하한 비율'),P(Sm.floor_pct,1)],[T('최종 위험가중자산'),M(Sm.final_total)],['CET1',M(Sm.capital.cet1)],[T('익스포저 측정치'),M(Sm.leverage.exposure_measure)]]),MT(T('원장')+' cap_stack · lim_limit_definition · alm_irrbb_result'));
const ld=FOF('lim_limit_definition');
if(ld)ap(bs,TB(ld,tt('lim_limit_definition')));
const ir=FOF('alm_irrbb_result');
if(ir)ap(bs,TB(ir,tt('alm_irrbb_result')));

}

/* ══════════════ 한도관리 ═════════════════════════════════════════════ */

function dimLabels(){
const d=FOF('lim_limit_definition'),m={};
if(d){const i=IX(d);d.rows.forEach(r=>{m[r[i.scope_key]]=r[i.limit_type]})}
return m;
}
function limits(root,c){
const D=c.D,xl=D.x_limits||{},ts=xl.two_sources||{},pop=xl.populations||{};
const f=D.limits_full||D.limits;
ap(root,el('p','lead',T('차주·업종·국가·자산군·등급 다차원 한도와 소진율이다. 경보 구간의 경계는 한도 엔진의 심각도 어휘가 정한다. 한도 근거와 승인 기록은 정의 원장에서 읽는다')));
 /* (1) 동일차주 두 산출 */
const law=ts.law||{},eng=ts.engine,ck=ts.check||{};
const b1=CD(root,'동일차주 두 산출');
ap(b1,ST(['출처','체계','분모 기준','위반','근거'],[[T('원장'),dv(law.framework),dv(law.basis),cnt(nz(law.n_breach)),dv(law.citation)],[T('한도엔진'),T('한도 엔진 결과'),eng?dv(eng.basis):T('미산출'),eng?cnt(nz(eng.n_breach)):T('미산출'),eng?dv(eng.source):'-']]));
ap(b1,BG(dv(ts.state),NG.checkTone(ck)));
if(ck.check_name)ap(b1,ST(['검증 항목','상태','상세'],[[ck.check_name,BG(dv(ck.status),NG.checkTone(ck)),tx(ck.detail)]],{onRow:()=>c.drawer.check(ck.check_name)}));
ap(b1,MT(T('분모기준이 달라 두 산출이 어긋난다. 두 수치는 언제나 함께 적는다')));

 /* (2) 모집단 카드 */
const pf=pop.limits_full||{},pl=pop.limits||{},nb=nz(pf.breach)+nz(pf.critical),nd=(pf.dimensions||[]).length;
ap(root,KR([K({label:'한도',value:NI(pf.total),sub:T('원장')+' limits_full · '+T('위반 보고 (차주 버킷 포함)')+' '+NI(pl.total),tone:'neutral',delta:false}),K({label:'위반',value:NI(nb),tone:sv(nb?'BREACH':'OK'),delta:false,sub:'BREACH '+NI(pf.breach)+' · CRITICAL '+NI(pf.critical)}),K({label:'경보',value:NI(pf.warn),tone:sv(nz(pf.warn)?'WARN':'OK'),delta:false,sub:'WARN'}),K({label:'한도 내',value:NI(pf.ok),tone:sv('OK'),delta:false,sub:'OK'}),K({label:'차원',value:NI(nd),tone:'neutral',delta:false,sub:(pf.dimensions||[]).join(' · ')})],c.meta.density));
 /* (3) 한도 정의 */
const d=FOF('lim_limit_definition');
if(d){const i=IX(d),nap=d.rows.filter(r=>!r[i.approved_on]).length;
const bd=CD(root,'한도 정의');
ap(bd,TB(d,{title:null,rowClass:r=>r[i.basis]==='규정'?null:'warn'}));
if(nap)ap(bd,NO(T('승인일이 비어 있는 한도')+' '+cnt(nap)+' · '+T('승인 기록 없이는 이 한도로 낸 위반 판정을 결재에 올릴 수 없다'),'warn'));
}
else ap(root,NO(T('한도 정의')+' · '+T('원장 행 없음'),'bad'));
if(!f){ap(root,NO(T('원장 행 없음'),'bad'));return}
const i=IX(f),lab=dimLabels(),L=k=>lab[k]||k;
const head=r=>nz(r[i.threshold])-nz(r[i.exposure]);
 /* (4) 차원별 잔여한도 */
const byDim={},dims=[];
f.rows.forEach(r=>{const k=r[i.dimension];if(dims.indexOf(k)<0){dims.push(k);byDim[k]={n:0,exp:0,th:0,head:0,max:0}}
const cur=byDim[k];cur.n+=1;cur.exp+=nz(r[i.exposure]);cur.th+=nz(r[i.threshold]);cur.head+=head(r);
if(nz(r[i.utilisation])>cur.max)cur.max=nz(r[i.utilisation])});
const bh=CD(root,'잔여한도');
ap(bh,U.truncBadge(f));
ap(bh,CH.barList(dims.map(k=>({label:L(k),value:byDim[k].head,sub:T('버킷 수')+' '+NI(byDim[k].n)+' · '+T('최대 소진율')+' '+P(byDim[k].max,1)}))));
ap(bh,CH.barList(f.rows.slice().sort((a,b)=>head(a)-head(b)).slice(0,14).map(r=>({
label:L(r[i.dimension])+' · '+r[i.bucket],value:head(r),tone:sv(r[i.severity]),sub:T('소진율')+' '+P(r[i.utilisation],1)}))));
ap(bh,MT(T('잔여한도는 한도액에서 익스포저를 뺀 값이며 음수가 위반이다. 버킷 정의가 달라 차원 간에 더하지 않는다')));

 /* (5) 소진율 분포 */
const us=f.rows.map(r=>nz(r[i.utilisation])),lo=Math.min.apply(null,us),hi=Math.max.apply(null,us);
const step=(hi-lo)/BINS||1,bins=[];
for(let k=0;k<BINS;k++){
const a=lo+step*k,b=k===BINS-1?hi:lo+step*(k+1);
const inb=f.rows.filter(r=>nz(r[i.utilisation])>=a&&(k===BINS-1?nz(r[i.utilisation])<=b:nz(r[i.utilisation])<b));
const worst=inb.reduce((x,y)=>nz(y[i.utilisation])>nz(x[i.utilisation])?y:x,inb[0]);
bins.push({lo:a,hi:b,n:inb.length,tone:worst?sv(worst[i.severity]):undefined})}
const bu=CD(root,'소진율 분포');
ap(bu,CH.histogram(bins,{title:T('소진율 분포'),fmt:v=>P(v,0),note:T('구간 톤은 그 구간 최고 소진율 행의 심각도 어휘를 따른다')+' · '+srv(pf.total)}));

 /* (6) 차원별 드릴다운 */
const bd2=CD(root,'차원별 드릴다운'),pane=el('div');
let dim=dims[0];
ap(bd2,CP(dims.map(k=>({value:k,label:L(k),raw:true,on:k===dim})),v=>{dim=v;drill()}),pane);
const ex=FOF('rdm_exposure'),ob=FOF('rdm_obligor');
const obIdx={};
if(ob){const oi=IX(ob);ob.rows.forEach(r=>{obIdx[r[oi.obligor_id]]={sector:r[oi.sector],country:r[oi.country],asset_class:r[oi.asset_class]}})}
function drill(){
pane.innerHTML='';
const sub=f.rows.filter(r=>r[i.dimension]===dim).sort((a,b)=>nz(b[i.utilisation])-nz(a[i.utilisation]));
ap(pane,CH.bars(sub.map(r=>({label:r[i.bucket],value:nz(r[i.utilisation])*100,tone:sv(r[i.severity])})),{title:L(dim)+' · '+T('소진율')+' (%)',fmt:PCTN}));
ap(pane,ST(['버킷','익스포저','한도','잔여','소진율','심각도'],sub.map(r=>[r[i.bucket],r[i.exposure],r[i.threshold],head(r),P(r[i.utilisation],1),BG(dv(r[i.severity]),sv(r[i.severity]))])));
if(ex&&sub.length){
const xi=IX(ex),cpane=el('div');let bkt=sub[0][i.bucket];
ap(pane,CP(sub.map(r=>({value:r[i.bucket],label:r[i.bucket],raw:true,on:r[i.bucket]===bkt})),v=>{bkt=v;contrib()}),cpane);
function contrib(){
cpane.innerHTML='';
const keyOf=r=>{if(dim==='asset_class')return r[xi.asset_class];if(dim==='rating')return r[xi.rating];
const o=obIdx[r[xi.obligor_id]];return o?o[dim]:null};
const rows=ex.rows.filter(r=>keyOf(r)===bkt),nrow=rows.length;
if(!nrow){ap(cpane,NO(T('이 버킷을 채우는 익스포저를 원장에서 찾지 못했다. 축 컬럼이 원장에 없다'),'warn'));return}
const m={},ids=[];
rows.forEach(r=>{const k=r[xi.obligor_id];if(ids.indexOf(k)<0){ids.push(k);m[k]={ead:0,n:0,rating:r[xi.rating]}}
m[k].ead+=nz(r[xi.ead]);m[k].n+=1});
const tot=rows.reduce((a,r)=>a+nz(r[xi.ead]),0);
const top=ids.sort((a,b)=>m[b].ead-m[a].ead).slice(0,10);
ap(cpane,CH.hbars(top.map(k=>({label:k,value:m[k].ead,sub:T('등급')+' '+dv(m[k].rating)+' · '+cnt(m[k].n)+' · '+T('비중')+' '+P(tot?m[k].ead/tot:0,1)})),{title:bkt+' · '+T('상위 기여 차주'),src:ex}));
ap(cpane,MT(T('버킷 내 익스포저')+' '+cnt(nrow)+' · EAD '+M(tot)+' · '+(ob?(ob.shown<ob.total?TF('표본 {n}/{N}행',{n:ob.shown,N:ob.total}):TF('전량 {N}행',{N:ob.total})):T('원장 행 없음'))+' · rdm_obligor'));
}
contrib();
}
}
drill();
if(dims.indexOf('obligor_id')<0)ap(root,NO(T('동일차주 축은 한도 소진 원장에 없다. 차주 단위 한도는 거액 분석에서 본다'),'neutral'));
 /* (7) 단일 버킷 증감 (설명용) */
const bs=CD(root,'한도 시뮬레이션');
U.explanatory(bs);
const srows=f.rows.slice().sort((a,b)=>nz(b[i.utilisation])-nz(a[i.utilisation]));
const sbar=el('div','toolbar'),sout=el('div');
let pick=0,add=0;
const ssel=SL(srows.map((r,k)=>({value:String(k),label:L(r[i.dimension])+' · '+r[i.bucket],raw:true})),v=>{pick=parseInt(v,10)||0;sim()});
const sin=IN({type:'number',step:'100',value:'0',aria:T('익스포저 증감'),onInput:v=>{add=(parseFloat(v)||0)*EOK;sim()}});
sin.style.flex='0 0 120px';
ap(sbar,SP(T('버킷')),ssel,SP(T('익스포저 증감')+' ('+T('억원')+')'),sin);
ap(bs,sbar,sout);
function sim(){
sout.innerHTML='';
const r=srows[pick];if(!r)return;
const e2=nz(r[i.exposure])+add,u2=nz(r[i.threshold])?e2/nz(r[i.threshold]):0;
ap(sout,ST(['항목','현행','조정 후'],[[T('익스포저'),M(r[i.exposure]),M(e2)],[T('한도'),M(r[i.threshold]),M(r[i.threshold])],[T('잔여'),M(head(r)),M(nz(r[i.threshold])-e2)],[T('소진율'),P(r[i.utilisation],1),P(u2,1)]]));
if(u2>=1)ap(sout,NO(T('이 증감이면 해당 한도를 넘긴다'),'bad'));
ap(sout,MT(T('기본자본 연동 한도는 자본이 바뀌면 한도 자체가 움직인다. 그 연동은 시뮬레이션에서 본다')));
}
sim();
 /* (8) 추이 */
const xt=D.x_trend||{},bt=S('소진율 추이');
if(!(nz(xt.n_periods)>1))ap(bt,NO(T('단일 기간, 추이 없음')+' · '+T('추이 원장에 기간이 하나뿐이다')+' · '+T('기간 수')+' '+NI(xt.n_periods)+' · '+T('추이 원장 경로')+' '+(xt.ledger_path||T('원장 경로 없음')),'neutral'));
else{const flags=xt.flags||[];
ap(bt,ST(['최신','전기 대비','하한선','방향','추이 상태','연속 위반'],flags.map(x=>[fmt.num(x.latest),fmt.num(x.qoq),fmt.num(x.floor),dv(x.direction),dv(x.trend_state),NI(x.consecutive_breaches)])))}
ap(root,bt);
 /* (9) 관리체계 요구사항 */
const gv=FOF('kr_irrbb_governance');
if(gv)ap(root,TB(gv,tt('kr_irrbb_governance')));
 /* (10) 위반 조치 원장 */
const ba=xl.breach_action_ledger||{},bb=S('위반 조치');
ap(bb,NO(TF('위반 조치 원장({name})이 없다',{name:ba.name||'lim_breach_action'})+' · '+T('원인·대응책·담당·기한을 담는 수기입력 원장이 필요하다')+' · '+T('위반')+' '+cnt(nb),'bad'));
ap(bb,ST(['필요 컬럼'],(ba.fields||[]).map(x=>[x])));
ap(root,bb);
 /* 한도 소진 원장 */
ap(root,TB(f,{title:'한도 소진',rowClass:r=>{const t=sv(r[i.severity]);return t==='good'?null:t}}));
}
function limitsSummary(c){
const pf=((c.D.x_limits||{}).populations||{}).limits_full;
if(!pf)return null;
const nb=nz(pf.breach)+nz(pf.critical);
return {tone:nb?'bad':(nz(pf.warn)?'warn':'good'),text:TF('한도 {total}건',{total:pf.total})+' · '+(nb?T('위반')+' '+NI(nb):T('위반 없음'))+' · '+T('경보')+' '+NI(pf.warn)+' · '+srv(pf.total)};
}

/* ══════════════ 거액 설정 ════════════════════════════════════════════ */

function evidenceItems(name){
const f=FOF(name);if(!f)return [];
const i=IX(f),ks=[],out=[];
f.rows.forEach(r=>{const k=String(r[i.evidence_status]);
if(ks.indexOf(k)<0){ks.push(k);out.push({ledger:name,rows:0,evidence_status:r[i.evidence_status],approved_on:r[i.approved_at]!==undefined?r[i.approved_at]:r[i.approved_on],citation:r[i.citation]})}
out[ks.indexOf(k)].rows+=1});
return out;
}
function lexSetting(root,c){
const D=c.D,f=FOF('lex_setting');
ap(root,el('p','lead',T('거액익스포져 산출의 설정 원장이다. 한도율·보고기준·판정 임계·면제정책이 체계별로 있고 항목마다 근거와 근거 판정이 붙는다')));
const xs=(D.x_screens||{})[c.id]||{},ow=xs.ownership,own=el('div','meta own');
if(ow){own.textContent=T('소관 (UI 가정)')+' '+ow.role_name+' · '+ow.org_unit;
own.title=T('DOMAIN_ROLE_MAP 상수로 연결했다. 도메인과 역할을 잇는 원장 컬럼은 없다.')}
else own.textContent=T('소관 미확인');
ap(root,own);
const src=el('div');
NG.shared.almSources(src,[{name:T('거액 설정'),source:'lex_setting',kind:T('설정 원장')},{name:T('총액한도'),source:'lex_aggregate',kind:T('집계 원장')}]);
ap(root,src);
if(!f){ap(root,NO(T('원장 행 없음'),'bad'));return}
const i=IX(f),fws=[];
f.rows.forEach(r=>{if(fws.indexOf(r[i.framework])<0)fws.push(r[i.framework])});
let fw=fws[0];
const box=CD(root,'설정 원장 (체계별)'),pane=el('div');
ap(box,CP(fws.map(x=>({value:x,label:x,raw:true,on:x===fw})),v=>{fw=v;draw()}),pane);
function draw(){
pane.innerHTML='';
const rows=f.rows.filter(r=>r[i.framework]===fw);
ap(pane,TB(subFrame(f,rows),{title:null,rowClass:r=>{
const t=TN('evidence_node.status',r[i.evidence_status]);return t!=='neutral'?t:(r[i.evidence_status]==='미확인'?'blocked':null)}}));
const blank=rows.filter(r=>r[i.param_value]==null),nbl=blank.length;
if(nbl)ap(pane,NO(T('값이 비어 있는 설정')+' '+cnt(nbl)+' · '+blank.map(r=>r[i.param_code]).join(' · ')+' · '+T('1차자료 미확인이거나 규정이 값을 주지 않는 항목이며 산출되지 않는다'),'warn'));
const un=rows.filter(r=>!r[i.approved_by]||String(r[i.approved_by]).indexOf('미승인')>=0),nun=un.length;
if(nun)ap(pane,NO(T('승인란이 채워지지 않은 설정')+' '+cnt(nun)+' · '+T('승인 전에는 이 설정으로 낸 산출을 결재에 올릴 수 없다'),'neutral'));
const ov=rows.filter(r=>r[i.is_overridden]===true),nov=ov.length;
ap(pane,MT(T('수기조정')+' '+cnt(nov)+' · '+T('원장')+' lex_setting'));
}
draw();
const ag=FOF('lex_aggregate');
if(ag)ap(root,TB(ag,{title:'총액한도'}));
 /* 설정 변경 제안 (원장에 쓰지 않는다) */
const ed=CD(root,'설정 변경 제안'),props=[],out=el('div');
ap(ed,NO(T('설정 변경은 승인 대상이다. 이 화면은 제안서만 만들고 값을 바꾸지 않는다'),'neutral'));
const codes=[];f.rows.forEach(r=>{if(codes.indexOf(r[i.param_code])<0)codes.push(r[i.param_code])});
let code=codes[0],val='',why='',ev='';
const eb=el('div','toolbar');
ap(eb,SP(T('설정항목')),SL(codes.map(x=>({value:x,label:x,raw:true})),v=>{code=v}),SP(T('제안 값')),IN({value:'',aria:T('제안 값'),onInput:v=>{val=v}}),SP(T('사유')),IN({value:'',aria:T('사유'),onInput:v=>{why=v}}),SP(T('증빙')),IN({value:'',aria:T('증빙'),onInput:v=>{ev=v}}),BT(T('제안서 만들기'),{primary:true,onClick:()=>{
out.innerHTML='';
const dm=c.meta.domains||[];
if((dm.length?dm:['']).some(x=>c.killedFor(x))){ap(out,NO(T('비상정지 (실행 차단)'),'blocked'));return}
if(!val.trim()||!why.trim()||!ev.trim()){ap(out,NO(T('제안 값과 사유와 증빙이 모두 필요하다'),'bad'));return}
const cur=f.rows.find(r=>r[i.param_code]===code&&r[i.framework]===fw);
props.push([fw,code,cur&&cur[i.param_value]!=null?String(cur[i.param_value]):T('값 없음'),val.trim(),why.trim(),ev.trim()]);
ap(out,ST(['체계','설정항목','현재값','제안 값','사유','증빙'],props));
ap(out,NO(T('이 항목을 바꾸면 한도율·소진율·보고대상·연결그룹·귀속·총액한도가 다시 산출된다. 재실행이 필요하다'),'neutral'));
ap(out,MT(T('이 실행에서만 유지되며 원장에 기록되지 않는다')))}}));
ap(ed,eb,out);
const ev2=el('div');
NG.shared.almEvidence(ev2,evidenceItems('lex_setting').concat(evidenceItems('lex_aggregate')));
ap(root,ev2);
}

/* ══════════════ 거액 분석 ════════════════════════════════════════════ */

function lexAnalysis(root,c){
const D=c.D,L=D.lex,xl=D.x_limits||{},ts=xl.two_sources||{};
ap(root,el('p','lead',T('체계별 소진과 보고대상, 대체, 연결그룹, 면제, look-through 귀속을 본다. 화면에는 표본이 실리고 순위·분포·합계는 전량 집계다')));
if(!L||!L.frameworks||!L.frameworks.length){ap(root,NO(T('거액익스포져 집계가 payload 에 없다'),'bad'));return}
ap(root,MT(twoSrc(ts)+' · '+L.frameworks.map(x=>x.framework+' ('+x.denominator_basis+')').join(' · ')));
 /* 체계 대비 */
const cmp=CD(root,'체계 대비');
ap(cmp,ST(['체계','집계단위','분모 기준','분모','한도율','한도액','포지션 수','보고대상','위반','산입액 합','면제액 합','근거'],L.frameworks.map(x=>[x.framework,x.aggregation_unit,x.denominator_basis,x.denominator_amount,x.limit_pct==null?T('값 없음'):P(x.limit_pct,2),x.limit_amount,x.n_positions,x.n_reportable,x.n_breach,x.sum_included,x.sum_exempt,x.limit_citation]),{rowClass:x=>nz(x.n_breach)?'bad':null}));
ap(cmp,NO(T('분모가 다른 체계는 같은 익스포저에서 다른 비율을 낸다. 두 비율을 더하거나 비교하지 않는다'),'neutral'));

const ag=FOF('lex_aggregate');
if(ag){const ai=IX(ag);
ap(root,TB(ag,{title:'총액한도',rowClass:r=>r[ai.breach]?'bad':null}))}
 /* 체계별 소진 */
const fws=L.frameworks.map(x=>x.framework);
let fw=fws[0];
const box=CD(root,'체계별 소진'),pane=el('div');
ap(box,CP(fws.map(x=>({value:x,label:x,raw:true,on:x===fw})),v=>{fw=v;draw()}),pane);
function draw(){
pane.innerHTML='';
const meta=L.frameworks.find(x=>x.framework===fw)||{},top=(L.top||{})[fw];
if(top){
const ti=IX(top);
ap(pane,CH.bars(top.rows.map(r=>({label:r[ti.group_id],value:nz(r[ti.utilisation])*100,tone:r[ti.breach]?sv('BREACH'):(r[ti.reportable]?sv('WARN'):sv('OK'))})),{title:T('상위 익스포저 소진율 (%)'),fmt:PCTN,note:TF('모집단 {N}행 중 상위 {n}',{N:meta.n_positions,n:top.total})}));
ap(pane,TB(top,{title:null,rowClass:r=>r[ti.breach]?'bad':(r[ti.reportable]?'warn':null)}));
}
ap(pane,CH.histogram((meta.histogram||[]).map(h=>({lo:h.lower,hi:h.upper==null?h.lower:h.upper,n:h.n,tone:h.upper==null?sv('BREACH'):undefined})),{title:T('소진율 분포'),fmt:v=>P(v,0),note:T('마지막 칸이 한도를 넘긴 포지션이다')+' · '+srv(meta.n_positions)}));
}
draw();
 /* 보장제공자 */
if(L.providers&&L.providers.length){
const pc=CD(root,'신용위험경감 대체로 익스포저를 받은 보장제공자');
ap(pc,ST(['보장제공자','대체 유입액','연결 건수','자체 포지션 최대 소진율','한도 위반'],L.providers.map(x=>[x.provider,x.substituted_in,x.n_links,x.max_utilisation==null?T('값 없음'):P(x.max_utilisation,1),x.breach==null?'-':(x.breach?T('위반'):'')]),{rowClass:x=>x.breach?'bad':null}));
ap(pc,MT(T('대체는 익스포저를 보장제공자로 옮긴다. 옮겨 받은 쪽의 한도 초과는 그 제공자 포지션 행에서 읽는다')));
}
 /* 대체 전후 */
const sb=FOF('lex_substitution');
if(sb){const si=IX(sb),inel=sb.rows.filter(r=>r[si.substituted_amount]===0).length;
const c2=CD(root,'대체 전후');
ap(c2,TB(sb,{title:null,rowClass:r=>r[si.maturity_mismatch_eligible]?null:'warn'}));
ap(c2,MT(T('대체가 인정되지 않은 건')+' '+cnt(inel)+' · '+T('사유는 적격 사유 컬럼에 있다')));
}
 /* 연결그룹 */
if(L.groups&&L.groups.basis){
const gc=CD(root,'연결그룹 구성');
ap(gc,ST(['연결 근거','거래상대방 수'],L.groups.basis.map(x=>[x.basis,x.n])));
ap(gc,MT(T('그룹')+' '+srv(L.groups.n_groups)+' · '+T('2개사 이상')+' '+NI(L.groups.n_multi)+' · '+T('경제적 상호의존 평가 대상')+' '+cnt(L.groups.n_review)));
if(L.groups.top)ap(gc,TB(L.groups.top));
}
 /* look-through */
const lt=FOF('lex_lookthrough');
if(lt){const li=IX(lt);
const c3=CD(root,'look-through 귀속');
ap(c3,ST(['귀속 유형','건수','귀속액'],agg(lt,'attribution_type','attributed_amount')));
const unk=lt.rows.filter(r=>r[li.attribution_type]==='무명고객'),nunk=unk.length;
if(nunk)ap(c3,NO(T('기초자산을 식별하지 못한 잔여는 무명고객 버킷으로 귀속된다')+' · '+cnt(nunk)+' · '+M(unk.reduce((a,r)=>a+nz(r[li.attributed_amount]),0)),'warn'));
ap(c3,MT(T('귀속 임계')+' '+M(lt.rows[0][li.threshold_amount])+' · '+dv(lt.rows[0][li.citation])));
ap(c3,TB(lt))}
 /* 면제 */
const exm=FOF('lex_exemption');
if(exm){
const c4=CD(root,'면제');
ap(c4,ST(['면제 유형','건수','면제액','근거'],agg(exm,'exemption_type','exempt_amount','basis')));
ap(c4,MT(T('면제액은 한도 산입에서 빠진 금액이며 측정액과 산입액의 차이다')))}
 /* 익스포저 유형별 측정액 */
if(L.measure&&L.measure.length){
const mc=CD(root,'익스포저 유형별 측정액');
ap(mc,CH.bars(L.measure.map(x=>({label:x.exposure_type,value:x.measured})),{title:T('익스포저 유형별 측정액'),fmt:v=>M(v)}));
ap(mc,ST(['익스포저 유형','측정액','총액','건수'],L.measure.map(x=>[x.exposure_type,x.measured,x.gross,x.n])));
const em=FOF('lex_exposure_measure');
if(em)ap(mc,MT(T('원장')+' lex_exposure_measure · '+(em.shown<em.total?TF('표본 {n}/{N}행',{n:em.shown,N:em.total}):TF('전량 {N}행',{N:em.total}))));
}
const ev=el('div');
NG.shared.almEvidence(ev,evidenceItems('lex_setting').concat(evidenceItems('lex_aggregate'),evidenceItems('lex_lookthrough')));
ap(root,ev);
}

NG.screen('cockpit',{group:'통제센터',sub:null,title:'콕핏',build:cockpit});
NG.screen('decision-queue',{group:'통제센터',sub:null,title:'의사결정 큐',build:decisionQueue});
NG.screen('close-workflow',{group:'통제센터',sub:null,title:'마감 워크플로',build:closeWorkflow});
NG.screen('simulation',{group:'통제센터',sub:null,title:'시뮬레이션',build:simulation});
NG.screen('limits',{group:'통제센터',sub:'한도·거액',title:'한도관리',build:limits,summary:limitsSummary});
NG.screen('lex-setting',{group:'통제센터',sub:'한도·거액',title:'거액 설정',build:lexSetting});
NG.screen('lex-analysis',{group:'통제센터',sub:'한도·거액',title:'거액 분석',build:lexAnalysis});
})();
