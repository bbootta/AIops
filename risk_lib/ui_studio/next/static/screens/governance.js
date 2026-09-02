/* screens/governance.js: 검증·거버넌스 11화면 (검증 · 요건 추적 · 에이전트 ·
   비상정지 · 변경 · 오버레이 · 변경통제 · 접근통제 · AI 거버넌스 · 감사추적 ·
   조회 거버넌스).
   규칙 (설계 사양 2.9·5·6장, 수용기준 A7·A8·A12·A13·A18·A21):
   - 건수·총계는 서버 집계(D.x_gate·x_close·x_audit·frame.total)에서만 읽는다.
     화면이 센 행수를 총계로 찍지 않는다. 표본 프레임은 배지를 달고 차트를
     그리지 않는다.
   - 톤은 TN(출처 어휘, 값) 하나에서만 나온다. 이 파일에는 톤 사전이 없다.
     x_severity 에 어휘가 없는 값(요건 상태·조회계획 상태·이슈 종류)은 색을
     붙이지 않고 값만 적는다.
   - 표 머리글은 카탈로그 한글명(CL)이고 원장 값·검증명·인용·식별자·지문은
     원문 그대로다. 저자가 쓴 문장만 T·TF 를 지난다.
   - 공용 도우미(renderForm·domainBrowser·almEvidence·almSources·judgeGlyph)는
     shared.js 만 정의한다. */
(function(){
'use strict';
const NG=window.NG,U=NG.ui,CH=NG.charts,FR=NG.frame,el=U.el,ap=U.ap;
const T=NG.T,TF=NG.TF,fmt=NG.fmt,tx=NG.text,TN=NG.tone;
const TB=U.table,ST=U.simpleTable,BG=U.badge,NO=U.note,DL=U.dotlist,BT=U.button;
const IN=U.input,SL=U.select,CP=U.chips,MR=U.meter,NI=fmt.int,dv=fmt.orDash;
const GRP='검증·거버넌스';
const IX=f=>FR.frameIdx(f);
const MT=t=>el('div','meta',t);
const G=(c,n)=>(c.D.data||{})[n]||null;
/* 카탈로그 한글명·컬럼 라벨은 번역 대상이 아니다. 원문 그대로 머리글로 쓴다. */
const CK=n=>{const r=NG.cat(n);return (r&&r.korean)||n};
const CL=(f,k)=>f?FR.colLabel(f,IX(f)[k]):k;
/* 표 머리글: 카탈로그 라벨은 번역하지 않고 물리 컬럼명을 title 로 단다. */
const HL=(f,k)=>({label:CL(f,k),raw:true,phys:k});
const cnt=n=>TF('{n}건',{n:n});
const srv=n=>TF('전량 {N} (서버 집계)',{N:n});
const LEAD=(root,k)=>ap(root,el('p','lead',T(k)));
/* base.css 가 section{display:none} 이라 펼친 카드는 div 로 만든다. */
function CD(root,t,o){o=o||{};const c=el('div','card sec');ap(c,el('h3',null,o.raw?t:T(t)));ap(root,c);return c}
function FOLD(root,t,fn){const d=U.section(t,{folded:true});
  d.addEventListener('toggle',()=>{if(d.open&&!d.dataset.done){d.dataset.done='1';fn(d)}});ap(root,d);return d}
function tcard(c,n,o){const f=G(c,n),node=TB(f,Object.assign({title:CK(n),raw:true},o||{}));
  if(f&&f.total===0)ap(node,NO(T('없음'),'neutral'));return node}
function tset(root,c,names){names.forEach(n=>ap(root,tcard(c,n)))}
/* 프레임의 부분집합. 원장명·전체 행수를 물려주므로 표본 배지가 서버 전체
   행수 기준으로 붙는다. */
function sub(f,rows){const n=rows.length;return {table:f.table,columns:f.columns,labels:f.labels,rows:rows,shown:n,total:f.total}}
function agg(f,key){const i=IX(f)[key],ks=[],m={};
  f.rows.forEach(r=>{const k=String(r[i]);if(m[k]==null){m[k]=0;ks.push(k)}m[k]++});
  return ks.map(k=>({label:k,value:m[k]}))}
/* 분포 막대는 전량 프레임에서만 그린다. 표본이면 이유를 적는다. */
function distBars(f,key,title,src){if(!f)return null;
  if(f.shown<f.total)return MT(T('차트는 전량 프레임에서만 그린다')+' · '+TF('표본 {n}/{N}행',{n:f.shown,N:f.total}));
  const it=agg(f,key);if(!it.length)return null;
  if(src)it.forEach(x=>{x.tone=TN(src,x.label)});
  return CH.bars(it,{title:T(title),src:f,fmt:NI})}
/* 참 값의 수. 표본 프레임이면 배지를 함께 단다. */
function flagLine(f,col,extra){if(!f)return null;const i=IX(f)[col];let n=0;
  f.rows.forEach(r=>{if(r[i])n++});
  const d=el('div','meta');ap(d,el('code',null,col),' ',CL(f,col),' ',NI(n)+'/'+NI(f.total));
  if(f.shown<f.total)ap(d,' ',U.truncBadge(f));
  if(extra)ap(d,' · '+extra);return d}

/* ══════════════ 검증 (2선·3선 두 층) ═════════════════════════════════ */

function validation(root,c){
const D=c.D,g=D.x_gate||{},s=g.self||{},iv=g.independent||{},rc=g.recalc||{};
const av=g.approvals||{},sb=g.submission||{},cn=g.conditional||{},xt=D.x_trend||{},ind=D.independent||{};
LEAD(root,'검증은 두 층이다. 자체검증(2선)은 같은 코드·같은 가정으로 점검하고, 상시 독립검증(3선)은 개발조직과 분리된 적합성검증 팀에이전트가 다시 계산한다. 2선 PASS만으로는 결재할 수 없다.');
const vf=FR.full('val_check')||G(c,'val_check'),vi=vf?IX(vf):{};
const tf=G(c,'val_independent_target');

/* (1) 도켓: 지금 적색인 것 */
const red=CD(root,'현재 적색');
ap(red,MT(T('자체검증 (2선)')+' '+TF('PASS {pass} · WARN {warn} · FAIL {fail} · 규제미달 {blocks} · 미실행 {not_run} (항등식 {identity} 제외)',
  {pass:s.pass,warn:s.warn,fail:s.fail,blocks:s.blocks,not_run:s.not_run,identity:s.identity_excluded})+' · '+srv(s.total)));
const bck=s.blocking_checks||[];
ap(red,bck.length?DL(bck.map(k=>({tone:NG.checkTone({check_name:k.check_name,status:k.status,blocks_approval:true}),
  text:k.check_name+' '+k.status+' · '+dv(k.domain)+' · '+tx(k.detail),right:T('결재 차단'),
  onClick:()=>c.drawer.check(k.check_name)}))):NO(T('차단 검증 없음'),'good'));
const nrn=vf?vf.rows.filter(r=>String(r[vi.check_name]).indexOf('_not_run')>=0):[];
ap(red,MT(T('미실행')+' '+NI(s.not_run)+' · '+(nrn.map(r=>r[vi.check_name]).join(', ')||T('없음'))));
const idn=vf?vf.rows.filter(r=>r[vi.is_identity]):[];
ap(red,MT(T('항등식 (통제 아님)')+' '+NI(s.identity_excluded)+' · '+T('집계에서 제외한다')));
if(idn.length)ap(red,ST([HL(vf,'check_name'),HL(vf,'status'),HL(vf,'detail')],
  idn.map(r=>[r[vi.check_name],r[vi.status],tx(r[vi.detail])]),{onRow:r=>c.drawer.check(r[0])}));
ap(red,MT(T('독립 재계산 대상')+' · '+T('미보고')+' '+NI((rc.counts||{})['미보고'])+' / '+NI(iv.n_recalc_targets)));

/* (2) 도켓: 무엇이 막고 있는가 */
const bl=CD(root,'차단'),rp=iv.response,hk=(av.holds||[]).length;
ap(bl,DL([
 {tone:iv.tone||'blocked',right:dv(iv.run_id),onClick:()=>c.drawer.gate(),
  text:T('상시 독립검증 (3선)')+' '+TF('{status} ({request_id}) · {kind} · {dispatch}',
    {status:dv(iv.status),request_id:dv(iv.request_id),kind:dv(iv.kind),dispatch:iv.dispatched?T('발신'):T('미발신')})},
 {tone:rp?'warn':'blocked',text:T('응답')+' '+(rp?dv(rp.request_id)+' · '+dv(rp.run_id)+' · '+dv(rp.verdict)+' · '+dv(rp.validated_by):T('응답 없음'))},
 {tone:cn.required?'warn':'neutral',text:(cn.required?T('조건부 승인 필요'):T('조건부 승인 불필요'))+' · '+T('조건부 승인 기록')+' '+(cn.ledger_record?dv(cn.ledger_record):T('기록 없음'))},
 {tone:av.segregation_violations?'bad':'good',text:T('직무분리 위반')+' '+NI(av.segregation_violations)},
 {tone:'neutral',text:TF('결재 대기 {pending} · 승인 {approved} · 반려 {returned} · 보류 사유 {kinds}종 · 제출 {reviewed}/{total}',
   {pending:av['대기'],approved:av['승인'],returned:av['반려'],kinds:hk,reviewed:sb.reviewed,total:sb.total})}
]));
/* 마감 과업은 이 화면의 원장(요청·결재·제출)을 증빙으로 삼는 것만 고른다. */
const lt=(((D.x_screens||{})[c.id]||{}).ledgers||[]).map(l=>l.table);
const tk=((D.x_close||{}).tasks||[]).filter(t=>lt.indexOf(t.evidence_table)>=0);
ap(bl,ST(['과업','단계 레인','상태','게이트 판정','차단 요인','사유'],
  tk.map(t=>[t.task_id+' · '+t.task_name,t.phase,BG(dv(t.status),TN('close_task.status',t.status)),
    BG(dv(t.decision),TN('close_gate.decision',t.decision)),dv(t.blocked_by),tx(t.reason)])));

/* (3) 도켓: 지난 실행 대비 달라진 것 */
const ch=CD(root,'달라진 것');
ap(ch,MT(xt.single_period?T('단일 기간')+' · '+T('추이 원장에 기간이 하나뿐이다'):TF('기간 {n}개',{n:xt.n_periods})));

/* (4) 3선 게이트: 요청 원장 12컬럼과 응답 식별자 */
const gc=CD(root,'상시 독립검증 (3선) 게이트');
const grow=el('div','trow');
ap(grow,BG(dv(iv.status),iv.tone||'blocked'),' ',BG(dv(iv.kind),iv.tone||'blocked'),
  ' ',BG(iv.dispatched?T('발신'):T('미발신'),iv.dispatched?'good':'blocked'));ap(gc,grow);
ap(gc,TB(G(c,'val_independent_request'),{title:CK('val_independent_request'),raw:true}));
ap(gc,ST(['항목','값'],[
  [T('요청 ID'),dv(iv.request_id)],[T('요청 대상'),dv(iv.requested_to)],[T('브랜치'),dv(iv.branch)],
  [T('헤드라인 지문'),dv(iv.headline_digest)],[T('발신 디렉터리'),dv(iv.dispatch_dir)],
  [T('응답 요청 ID'),rp?dv(rp.request_id):T('응답 없음')],[T('실행 ID'),rp?dv(rp.run_id):T('응답 없음')],
  [T('판정'),rp?dv(rp.verdict):T('응답 없음')],[T('검증자'),rp?dv(rp.validated_by):T('응답 없음')],
  [T('검증 시각'),rp?dv(rp.validated_at):T('응답 없음')]]));
ap(gc,MT(T('요청과 응답의 식별자가 다르면 이전 요청에 대한 응답이다')),
  NO(T('이 판정은 화면을 산출한 실행 시점의 스냅샷이다. 이후 도착한 3선 응답이나 판정 변경은 이 화면에 반영되지 않는다. 현재 상태의 정본은 저장소 게이트(check_gate)다.'),'neutral'),
  NO(tx(dv(iv.reason))+' · '+T('게이트는 fail-closed 다. 응답이 없으면 응답대기이며 결재할 수 없다.'),iv.tone||'blocked'));

/* (5) 2선 집계 */
const sc=CD(root,'자체검증 (2선)');
const items=[{label:'PASS',value:s.pass,tone:TN('val_check.status','PASS')},
  {label:'WARN',value:s.warn,tone:TN('val_check.status','WARN')},
  {label:'FAIL',value:s.fail,tone:TN('val_check.status','FAIL')},
  {label:T('미실행'),value:s.not_run,tone:'not-run'},
  {label:T('항등식 제외'),value:s.identity_excluded,tone:'neutral'}];
ap(sc,CH.bars(items,{title:T('자체검증 (2선)'),fmt:NI,src:vf,note:srv(s.total)}));
ap(sc,MR('결재 차단',s.blocks,s.total,s.blocks?'bad':'good'));

/* (6) 독립 재계산 대상: 세 상태와 인용 */
const rt=CD(root,'독립 재계산 대상');
const rows=rc.rows||[],ct=rc.counts||{};
ap(rt,MT(TF('3선 대상 {n}건 · 일치 {matched} · 불일치 {mismatched} · 미보고 {unreported}',
  {n:iv.n_recalc_targets,matched:ct['일치'],mismatched:ct['불일치'],unreported:ct['미보고']})+
  ' · '+T('응답 요청 ID')+' '+dv(rc.response_request_id)));
ap(rt,CP(rows.map(r=>({value:r.target,label:r.target,raw:true})),v=>{
  const ln=NG.lineage.byTarget(v);if(ln)c.drawer.lineage(ln)}));
ap(rt,ST([HL(tf,'target'),HL(tf,'korean'),HL(tf,'reported'),HL(tf,'recomputed'),HL(tf,'matched'),{label:T('상태'),raw:true},HL(tf,'citation')],
  rows.map(r=>[r.target,r.korean,fmt.num(r.reported),fmt.num(r.recomputed),String(r.matched),
    BG(r.state,TN('recalc.state',r.state)),r.citation]),
  {onRow:r=>{const ln=NG.lineage.byTarget(r[0]);if(ln)c.drawer.lineage(ln)}}));

/* (7) 자체검증 원장: 상태·차단·항등식 걸러 보기 */
const vc=CD(root,'자체검증 (2선) 결과 (같은 코드·같은 가정)');
if(vf){
 const pane=el('div');
 const pick={ALL:()=>true,BLOCK:r=>!!r[vi.blocks_approval],IDENT:r=>!!r[vi.is_identity]};
 function drawV(v){pane.innerHTML='';
  const rs=(!v||v==='ALL')?vf.rows:vf.rows.filter(pick[v]||(r=>String(r[vi.status])===v));
  ap(pane,TB(sub(vf,rs),{title:CK('val_check'),raw:true,
    rowClass:r=>NG.checkTone({check_name:r[vi.check_name],status:r[vi.status],
      is_identity:r[vi.is_identity],blocks_approval:r[vi.blocks_approval]}),
    onRow:r=>c.drawer.check(r[vi.check_name])}))}
 ap(vc,CP([{value:'ALL',label:'전체 상태',on:true},{value:'FAIL',label:'FAIL',raw:true},
   {value:'WARN',label:'WARN',raw:true},{value:'PASS',label:'PASS',raw:true},
   {value:'BLOCK',label:'결재 차단'},{value:'IDENT',label:'항등식 (통제 아님)'}],drawV),pane);
 drawV('ALL');
}else ap(vc,NO(T('원장 행 없음'),'warn'));

/* (8) 3선이 도전해야 할 가정 */
FOLD(root,'3선이 도전해야 할 가정',box=>{
 const lst=ind.assumptions||[],n=lst.length,pane=el('div');
 function drawA(v){pane.innerHTML='';const kw=String(v||'').trim().toLowerCase();
  const rs=lst.filter(x=>!kw||String(x).toLowerCase().indexOf(kw)>=0),m=rs.length;
  ap(pane,MT(cnt(m)),DL(rs.map(x=>({tone:'neutral',text:tx(x)}))))}
 ap(box,MT(cnt(n)+' · '+T('원장')+' · '+T('독립검증 요청 패키지')),
   IN({placeholder:T('가정 검색'),aria:T('가정 검색'),onInput:drawA}),pane);
 if(!n)ap(box,NO(T('가정 목록이 비어 있다. 독립검증 요청 패키지가 만들어지지 않았다.'),'bad'));
 drawA('')});

/* (9) 조건부 승인 기록 */
const cc=CD(root,'조건부 승인 기록');
ap(cc,BG(cn.required?T('조건부 승인 필요'):T('조건부 승인 불필요'),cn.required?'warn':'neutral'));
ap(cc,cn.required?NO(T('조건부 승인 기록 필요: ConditionalApproval 필드를 담는 카탈로그 원장이 없고, 스튜디오는 파일 기록을 읽지 않는다'),'warn')
  :MT(T('판정이 조건부일 때만 기록을 요구한다')));

/* (10) 톤 매핑 */
FOLD(root,'심각도·톤 매핑',box=>{
 ap(box,ST(['출처 어휘','값','톤','표시 기호'],((D.x_severity||{}).map||[]).map(r=>[r.source,r.value,r.tone,NG.glyph(r.tone)])));
 ap(box,MT(T('원장')+' x_severity · '+T('화면은 자기 톤 사전을 두지 않는다')))});
}

/* ══════════════ 요건 추적 ═══════════════════════════════════════════ */

/* 요건 한 줄. 증빙 목록이 비면 값 없음 표시를 둔다. 이 줄은 표 호출 밖에서 만든다. */
function reqRow(r){const td=el('div');ap(td,el('div','mono',r.id),el('div',null,r.title));
 const evs=r.evidence||[],n=evs.length,ev=el('div');
 evs.forEach(e=>{ap(ev,U.pill(e.kind+' · '+e.ref),' ')});
 if(!n)ap(ev,el('span','meta','-'));
 return [td,r.sector,r.priority,U.pill(r.status,TN('req_trace.status',r.status)),ev,tx(r.note||'')]}
function reqTrace(root,c){
const R=c.D.req_trace||{},cv=R.coverage||{},rows=R.rows||[];
LEAD(root,'RYNTA v9.6.0 업무요건정의서 Level 1 요건 131건을 이 하네스의 실재 증빙(모듈·원장·화면·테스트)에 대조한다. 증빙 참조는 tests/test_req_trace.py 가 실재를 검증한 것만 싣는다. 미반영 요건도 그대로 표시한다.');
const st=['반영','부분','미반영'];
/* 요건 상태는 x_severity 에 어휘가 없다. 색을 붙이지 않고 값만 적는다. */
ap(root,U.kpiRow(st.map(k=>U.kpi({label:k,value:NI(cv[k]),delta:false,
  tone:TN('req_trace.status',k),sub:fmt.pct(cv.n?cv[k]/cv.n:0,0)+' / '+cnt(cv.n)}))
  .concat([U.kpi({label:'검증된 증빙 참조',value:NI(cv.n_evidence),delta:false,sub:T('원장')+' req_trace'})]),c.meta.density));
const c0=CD(root,'커버리지');
ap(c0,CH.bars(st.map(k=>({label:T(k),value:cv[k]})),{title:T('커버리지'),fmt:NI,note:cnt(cv.n)}));
ap(c0,MR('반영',cv['반영'],cv.n,TN('req_trace.status','반영')));
ap(c0,MT(T('이 화면의 상태 어휘는 x_severity 에 없다. 색을 붙이지 않고 값만 적는다.')));
ap(c0,MT(dv(cv.source)+' · SHA-256 '+dv(cv.source_sha256)));
const bar=el('div','toolbar');let fSt='',fPr='',kw='';
const areas=[];rows.forEach(r=>{const a=String(r.id).split('-')[0];if(areas.indexOf(a)<0)areas.push(a)});
areas.sort();
const pane=el('div','card');
function drawR(){pane.innerHTML='';
 const rs=rows.filter(r=>(!fSt||r.status===fSt)&&(!fPr||String(r.id).indexOf(fPr+'-')===0)&&
   (!kw||(r.id+' '+r.title).toLowerCase().indexOf(kw)>=0));
 const n=rs.length;
 ap(pane,el('h3',null,TF('요건 {n}건',{n:n})));
 ap(pane,ST(['요건','업권','우선순위','상태','증빙 (검증됨)','비고'],rs.map(reqRow))) }
ap(bar,SL([{value:'',label:'전체 상태'}].concat(st.map(x=>({value:x,label:x}))),v=>{fSt=v;drawR()}),
  SL([{value:'',label:'전체 영역'}].concat(areas.map(x=>({value:x,label:x,raw:true}))),v=>{fPr=v;drawR()}),
  IN({placeholder:T('ID·제목 검색'),aria:T('ID·제목 검색'),onInput:v=>{kw=String(v).trim().toLowerCase();drawR()}}));
ap(root,bar,pane);drawR();
}

/* ══════════════ 에이전트 ════════════════════════════════════════════ */

function agentOps(root,c){
LEAD(root,'계획·등록도구·데이터범위·승인·로그를 확인한다. 사람의 승인을 받기 전 에이전트는 조회 전용 또는 제안 전용이며, 운영 반영 권한(write_allowed)은 전 에이전트가 거짓이다.');
const rg=G(c,'agent_registry'),ac=G(c,'agent_activity'),ks=G(c,'agent_killswitch');
const a=CD(root,'에이전트 레지스트리 · 최소 권한');
ap(a,flagLine(rg,'write_allowed',T('사람 승인 전에는 운영 반영 권한을 켜지 않는다')));
const bb=distBars(rg,'mode','권한 모드별 에이전트 수');if(bb)ap(a,bb);
ap(a,tcard(c,'agent_registry'));
const b=CD(root,'활동 원장 (주체·도구·출력·게이트)');
if(ac){const i=IX(ac);
 let last=null;ac.rows.forEach(r=>{if(!last||r[i.seq]>last[i.seq])last=r});
 if(last)ap(b,ST([HL(ac,'seq'),HL(ac,'actor'),HL(ac,'tool'),HL(ac,'output'),HL(ac,'gate')],
   [[last[i.seq],last[i.actor],last[i.tool],tx(String(last[i.output])),BG(dv(last[i.gate]),TN('agent.gate',last[i.gate]))]]));
 ap(b,MT(T('최종 인간 게이트 행은 활동 원장의 마지막 순번이다')));
 ap(b,DL(agg(ac,'gate').map(x=>({tone:TN('agent.gate',x.label),text:x.label,right:NI(x.value)}))));
 ap(b,tcard(c,'agent_activity',{rowClass:r=>TN('agent.gate',r[i.gate])}))}
const k=CD(root,'범위형 비상정지 이력');
if(ks){const i=IX(ks);let miss=0;ks.rows.forEach(r=>{if(r[i.confirmed_by]==null)miss++});
 ap(k,BG(T('2차 확인 미완료')+' '+NI(miss)+'/'+NI(ks.total),miss?'blocked':'good'));
 ap(k,tcard(c,'agent_killswitch',{rowClass:r=>r[i.confirmed_by]==null?'blocked':null}))}
ap(k,NO(T('안전중지는 진행 중 결정론적 계산을 마치고 신규 도구 호출을 차단한다. 중요 범위는 독립된 2차 확인이 필요하다.'),'neutral'));
ap(k,BT(T('비상정지'),{onClick:()=>c.go('kill-guard')}));
}

/* ══════════════ 비상정지 (화면 가드) ════════════════════════════════ */

function killGuard(root,c){
const st=c.state,ks=G(c,'agent_killswitch'),on=!!st.killed;
LEAD(root,'이 가드는 화면 안의 조회와 제안만 막는다. 런타임이나 원장에 아무 사건도 쓰지 않는다. AIMS AIG-009 는 런타임 정지를 오케스트레이션 계층에 둔다.');
const s0=CD(root,'현재 상태');
ap(s0,DL([
 {tone:on?'blocked':'good',text:T('현재 상태'),right:on?T('발동 중'):T('미발동')},
 {tone:'neutral',text:T('범위'),right:on?dv(st.killScope):T('없음')},
 {tone:'neutral',text:T('발동 사유'),right:st.killReason||T('기록 없음')},
 {tone:'neutral',text:T('2차 확인자'),right:st.killConfirm||T('기록 없음')}]));
ap(s0,NO(T('화면 전용 범위다 (AIG-009). 운영 킬스위치 원장 agent_killswitch 와는 별개다.'),'neutral'));
ap(s0,MT(T('이 실행에서만 유지되며 원장에 기록되지 않는다')));
/* 발동·해제는 머리말 표시줄과 같은 상태·같은 두 칸 규칙을 쓴다. */
const f0=CD(root,'비상정지 발동 · 해제');
const rin=IN({placeholder:T(on?'해제 사유 (필수)':'비상정지 사유 (필수)'),aria:T('사유'),onInput:sync});
const cin=IN({placeholder:T('2차 확인자 (필수)'),aria:T('2차 확인자'),onInput:sync});
const go=BT(T(on?'해제':'정지'),{primary:true,disabled:true,onClick:fire});
go.title=T(on?'사유와 2차 확인자를 모두 채워야 해제할 수 있다':'사유와 2차 확인자를 모두 채워야 정지할 수 있다');
function sync(){go.disabled=!(String(rin.value).trim()&&String(cin.value).trim())}
function fire(){if(go.disabled)return;
 const doc=document,kb=doc.querySelector('.kill'),bar=doc.querySelector('.killbar');
 const r=doc.getElementById('killreason'),cf=doc.getElementById('killconfirm'),gg=doc.querySelector('.killgo');
 if(!kb||!bar||!r||!cf||!gg)return;
 if(!bar.hidden)kb.click();
 kb.click();
 r.value=rin.value;cf.value=cin.value;
 if(r.oninput)r.oninput();if(cf.oninput)cf.oninput();
 gg.click()}
const tb=el('div','toolbar');ap(tb,rin,cin,go);ap(f0,tb);
ap(f0,MT(T('이 화면에서 발동·해제하면 머리말 표시줄과 같은 상태를 쓴다. 사유와 2차 확인자를 모두 채워야 한다.')));
const kc=CD(root,'범위형 비상정지 이력');
if(ks){const i=IX(ks);let miss=0;ks.rows.forEach(r=>{if(r[i.confirmed_by]==null)miss++});
 ap(kc,BG(T('2차 확인 미완료')+' '+NI(miss)+'/'+NI(ks.total),miss?'blocked':'good'));
 ap(kc,MT(T('두 번째 확인자가 없는 행은 2차 확인이 남아 있다')));
 ap(kc,tcard(c,'agent_killswitch',{rowClass:r=>r[i.confirmed_by]==null?'blocked':null}))}
}

/* ══════════════ 변경 (리스크 변경 팩토리) ═══════════════════════════ */

function changes(root,c){
LEAD(root,'신규 익스포저·상품·규정·데이터 변경의 영향을 분석하고 계산·보고서를 매핑하며 통제된 브랜치와 테스트를 작성한다. 자동배포하지 않는다.');
const cr=G(c,'chg_change_request'),rt=G(c,'chg_regression_test'),cm=G(c,'rdm_canonical_map');
const a=CD(root,'변경 요청');
ap(a,flagLine(cr,'deploy_allowed',T('배포는 화면이 아니라 파이프라인 재실행이 한다')));
ap(a,tcard(c,'chg_change_request'));
ap(root,tcard(c,'chg_impact_map'));
const b=CD(root,'회귀테스트 매트릭스');
const bb=distBars(rt,'status','회귀테스트 상태별 건수');if(bb)ap(b,bb);
ap(b,tcard(c,'chg_regression_test'));
const m=CD(root,'표준코드 매핑 (미매핑은 산출 누락으로 직결)');
if(cm){const i=IX(cm);let un=0;cm.rows.forEach(r=>{if(!r[i.canonical_code])un++});
 ap(m,BG(CL(cm,'canonical_code')+' · '+T('기록 없음')+' '+NI(un)+'/'+NI(cm.total),un?'warn':'good'))}
ap(m,tcard(c,'rdm_canonical_map'));
}

/* ══════════════ 오버레이 (사람이 덮어쓴 값) ═════════════════════════ */

function overlay(root,c){
const D=c.D,av=(D.x_gate||{}).approvals||{},dom=(c.meta.domains||[])[0];
LEAD(root,'엔진 산출값을 사람이 덮어쓴 기록(수동조정 원장)과 새 오버레이 제안. 전 건이 사유·증빙·승인자·만료일을 갖는다. 이 화면은 값을 바꾸지 않는다. 제안서를 만들고, 적용은 원장 등재 + 파이프라인 재실행 + 검증 두 층을 거친다.');
const f=G(c,'aig_adjustment'),pv=G(c,'gov_approval');
const c0=CD(root,'수동조정 원장');
if(f){const i=IX(f);
 ap(c0,CH.bars(f.rows.map(r=>({label:String(r[i.adjustment_id])+' · '+String(r[i.figure_id]),value:r[i.delta]})),
   {title:T('수동조정 증감'),src:f,fmt:fmt.money}));
 /* 상위 승인자는 원장 컬럼이고, 결재 판정은 4-Eyes 원장에서 찾는다. */
 const pi=pv?IX(pv):{};
 ap(c0,ST([HL(f,'adjustment_id'),HL(f,'figure_id'),HL(f,'senior_approval'),HL(f,'status'),{label:T('결재'),raw:true}],
   f.rows.map(r=>{const id=r[i.adjustment_id];
     const hit=pv?pv.rows.filter(x=>String(x[pi.subject_id])===String(id))[0]:null;
     return [id,r[i.figure_id],r[i.senior_approval]==null?T('기록 없음'):r[i.senior_approval],r[i.status],
       hit?BG(dv(hit[pi.decision]),TN('gov_approval.decision',hit[pi.decision])):T('기록 없음')]})));
 const bst=av.by_subject_type||{},ks=Object.keys(bst);
 ap(c0,MT(T('결재')+' '+srv(av.total)+' · '+T('대상 유형별')+' '+ks.map(k=>k+' '+NI(bst[k])).join(' · ')));
 if(pv&&pv.shown<pv.total)ap(c0,NO(T('결재 기록을 표본에서 찾지 못했다. 4-Eyes 원장이 표본이라 조정 식별자로 잇지 못한 행이 있다.'),'warn'));
 ap(c0,tcard(c,'aig_adjustment'))}
/* 엔진 산출 프레임(table 없음)은 카탈로그 밖 칩을 그대로 단다. */
ap(root,TB(D.adjustments,{title:T('수동조정 원장 (엔진 결합 · 사유·증빙 포함)'),raw:true}));
const p=el('div','card sec set-overlay');ap(p,el('h3',null,T('새 오버레이 제안')));ap(root,p);
if(c.killedFor(dom)){ap(p,NO(T('비상정지 (실행 차단)'),'blocked'));return}
const sel=SL((D.kpis||[]).map(k=>({value:k.label,label:k.label+' · '+k.value,raw:true})));
const val=IN({placeholder:T('수정값'),aria:T('수정값')});
const why=IN({placeholder:T('사유 (필수, 데이터 지연·일회성 사건·모형 한계 등)'),aria:T('사유')});
const ev=IN({placeholder:T('증빙 참조 (필수, 문서번호·티켓)'),aria:T('증빙 참조')});
const err=el('div','note bad');err.hidden=true;
const out=el('pre','mono');
const gen=BT(T('오버레이 제안 생성'),{primary:true,onClick:()=>{
 err.hidden=true;out.textContent='';
 if(!String(why.value).trim()||!String(ev.value).trim()){err.textContent=T('사유와 증빙 참조는 필수다');err.hidden=false;return}
 if(!String(val.value).trim()){err.textContent=T('수정값이 비어 있다');err.hidden=false;return}
 const k=(D.kpis||[]).filter(x=>x.label===sel.value)[0]||{};
 out.textContent=JSON.stringify({proposal:T('수동조정(오버레이)'),asof:D.meta.asof,run_id:D.meta.run_id,
   target:k.label,engine_value:k.value,proposed_value:String(val.value).trim(),
   reason:String(why.value).trim(),evidence_ref:String(ev.value).trim(),
   apply_path:'risk_lib/adjustments.py',
   procedure:[T('원장 등재(승인자·만료일 포함)'),T('4-Eyes 승인'),T('파이프라인 재실행'),
     T('자체검증(2선)'),T('독립검증(3선) 재요청')],
   note:T('화면 값은 바뀌지 않는다.')},null,2)}});
const bar=el('div','toolbar');ap(bar,sel,val,why,ev);
ap(p,bar,gen,err,out);
ap(p,MT(T('적용 경로는 원장 등재 → 4-Eyes 승인 → 파이프라인 재실행 → 2선 → 3선 재요청이다. 화면은 제안서만 만든다.')));
}

/* ══════════════ 통제: 변경통제 ══════════════════════════════════════ */

function changeControl(root,c){
LEAD(root,'모형·산출 변경이 정책에서 실행까지 지나는 다섯 원장이다. 요청이 영향대상을 달고 게이트를 통과해야 실행 기록이 남는다.');
const gt=G(c,'gov_change_gate'),gi=gt?IX(gt):{};
tset(root,c,['gov_change_policy','gov_change_request','gov_change_impact']);
ap(root,tcard(c,'gov_change_gate',{rowClass:r=>TN('change_gate.decision',r[gi.decision])}));
if(gt&&gt.total===0)ap(root,MT(T('변경 배포 게이트 원장에 행이 없다. 배포 판정이 아직 없다는 뜻이다.')));
ap(root,tcard(c,'gov_change_control'));
}

/* ══════════════ 통제: 접근통제·직무분리 ═════════════════════════════ */

function accessSod(root,c){
const av=(c.D.x_gate||{}).approvals||{};
LEAD(root,'누가 무엇을 볼 수 있는지와 그 판정 기록이다. 직무분리 상충은 역할 조합으로 판정하고 필드 단위 마스킹은 별도 정책 원장이 든다.');
const s0=CD(root,'직무분리 위반');
ap(s0,BG(T('직무분리 위반')+' '+NI(av.segregation_violations)+'/'+NI(av.total),av.segregation_violations?'bad':'good'));
ap(s0,MT(T('결재')+' '+srv(av.total)+' · '+T('원장')+' gov_approval'));
const ad=G(c,'gov_access_decision');
const bb=distBars(ad,'decision','접근 판정별 건수');if(bb)ap(s0,bb);
const sd=G(c,'gov_sod_conflict'),si=sd?IX(sd):{};
tset(root,c,['gov_user_role','gov_role_permission']);
ap(root,tcard(c,'gov_sod_conflict',{rowClass:r=>TN('exception.severity',r[si.severity])}));
tset(root,c,['gov_access_decision','ui_field_policy']);
}

/* ══════════════ 통제: AI 거버넌스 ═══════════════════════════════════ */

function aiGovernance(root,c){
LEAD(root,'에이전트가 무엇을 받고 무엇을 냈는지, 전송 전 무엇을 가렸는지, 사람이 무엇을 손댔는지를 남기는 원장이다 (ISO/IEC 42001).');
const tr=G(c,'aig_agent_trace'),ti=tr?IX(tr):{};
const a=CD(root,'프롬프트·도구·출력 로그');
const bb=distBars(tr,'phase','단계별 추적 기록 수');if(bb)ap(a,bb);
if(tr)ap(a,DL(agg(tr,'gate').map(x=>({tone:TN('agent.gate',x.label),text:x.label,right:NI(x.value)}))));
ap(a,MT(T('단계 값은 x_severity 에 어휘가 없어 색을 붙이지 않는다. 게이트만 톤을 받는다.')));
ap(a,tcard(c,'aig_agent_trace',{rowClass:r=>TN('agent.gate',r[ti.gate])}));
tset(root,c,['aig_redaction_rule','aig_adjustment']);
ap(root,MT(T('수동조정 원장')+' · '+T('이 화면은 읽기만 한다. 제안은 오버레이 화면이 만든다.')));
}

/* ══════════════ 통제: 실행·감사추적 ═════════════════════════════════ */

function auditTrail(root,c){
const D=c.D,xa=D.x_audit||{},run=xa.run||{},ur=G(c,'gov_unified_run');
LEAD(root,'실행 하나가 남기는 식별자와 그 실행의 근거다. 감사기록은 해시체인이라 중간을 고치면 뒤가 어긋난다.');
const a=CD(root,'통합 실행 원장');
ap(a,ST(['항목','값'],[
 [CL(ur,'run_id'),dv(run.run_id)],[CL(ur,'asof'),dv(run.asof)],[CL(ur,'seed'),dv(run.seed)],
 [CL(ur,'code_revision'),dv(run.code_revision)],
 [CL(ur,'n_domains_built'),NI(run.n_domains_built)+' / '+NI(run.n_domains_declared)],
 [CL(ur,'n_tables'),NI(run.n_tables)],[CL(ur,'n_rows'),NI(run.n_rows)],
 [CL(ur,'run_fingerprint'),dv(run.run_fingerprint)],
 [CL(ur,'is_complete'),BG(String(run.is_complete),run.is_complete?'good':'blocked')]]));
ap(a,MT(T('실행이 완결이 아니면 산출물은 부분이다. 판정은 원장 값 그대로다.')));
ap(a,tcard(c,'gov_unified_run'));
const b=CD(root,'감사기록 해시체인');
const cb=el('div','trow');ap(cb,el('code',null,'chain_ok'),' ',
  BG(T('해시체인 연속')+' '+String(xa.chain_ok),xa.chain_ok?'good':'bad'));ap(b,cb);
ap(b,MT(T('기록 수')+' '+srv(xa.n_records)+' · '+T('첫 불연속')+' '+(xa.first_break_seq==null?T('없음'):NI(xa.first_break_seq))));
ap(b,tcard(c,'gov_audit_chain'));
const ri=G(c,'gov_run_issue');
const s0=CD(root,'실행 통제 이슈');
const bb=distBars(ri,'kind','이슈 종류별 건수');if(bb)ap(s0,bb);
if(ri){const i=IX(ri);
 ap(s0,DL(agg(ri,'stage').map(x=>({tone:'neutral',text:x.label,right:NI(x.value)}))));
 ap(s0,ST([HL(ri,'stage'),HL(ri,'seq'),HL(ri,'kind'),HL(ri,'detail')],
   ri.rows.map(r=>[r[i.stage],r[i.seq],r[i.kind],tx(String(r[i.detail]))])));
 if(ri.total===0)ap(s0,MT(T('이슈 없음')))}
ap(s0,MT(T('이슈 종류는 x_severity 에 어휘가 없어 색을 붙이지 않는다.')));
const v=CD(root,'산출 근거 원장');
ap(v,MT(T('계보 드로어의 근거 탭이 이 원장을 읽는다.')));
ap(v,tcard(c,'val_audit_ledger',{onRow:r=>{const ln=NG.lineage.of(String(r[0]));if(ln)c.drawer.lineage(ln)}}));
tset(root,c,['int_engine_adapter','int_engine_io']);
}

/* ══════════════ 통제: 조회 거버넌스 ═════════════════════════════════ */

function queryGovernance(root,c){
LEAD(root,'화면이 무엇을 조회할 수 있는지 정하는 원장이다. 승인된 View 밖은 조회되지 않고, 자연어 조회는 계획으로 남은 뒤 사람이 적용을 승인한다.');
ap(root,tcard(c,'ui_view'));
const qp=G(c,'ui_query_plan'),qi=qp?IX(qp):{};
const a=CD(root,'자연어 조회계획');
const bb=distBars(qp,'status','조회계획 상태별 건수');if(bb)ap(a,bb);
if(qp){const blk=qp.rows.filter(r=>r[qi.block_reason]!=null);let nb=0;blk.forEach(()=>{nb++});
 ap(a,MT(CL(qp,'block_reason')+' '+NI(nb)+'/'+NI(qp.total)));
 if(blk.length)ap(a,ST([HL(qp,'plan_id'),HL(qp,'view_id'),HL(qp,'status'),HL(qp,'block_reason')],
   blk.map(r=>[r[qi.plan_id],r[qi.view_id],r[qi.status],tx(String(r[qi.block_reason]))])));
 ap(a,MT(T('조회계획 상태는 x_severity 에 어휘가 없어 색을 붙이지 않는다.')))}
ap(a,tcard(c,'ui_query_plan'));
const lp=G(c,'ui_layout_proposal'),li=lp?IX(lp):{};
const b=CD(root,'비정형 레이아웃 제안');
if(lp)ap(b,flagLine(lp,'human_approved',T('사람이 승인한 제안만 적용한다')));
ap(b,tcard(c,'ui_layout_proposal'));
}

/* ══════════════ 등록 ════════════════════════════════════════════════ */

const DEF=[['validation',null,'검증',validation],['req-trace','검증','요건 추적',reqTrace],
  ['agents',null,'에이전트',agentOps],['kill-guard',null,'비상정지',killGuard],
  ['changes',null,'변경',changes],['overlay',null,'오버레이',overlay],
  ['change-control','통제','변경통제',changeControl],
  ['access-sod','통제','접근통제·직무분리',accessSod],
  ['ai-governance','통제','AI 거버넌스',aiGovernance],
  ['audit-trail','통제','실행·감사추적',auditTrail],
  ['query-governance','통제','조회 거버넌스',queryGovernance]];
DEF.forEach(d=>NG.screen(d[0],{group:GRP,sub:d[1],title:d[2],build:d[3]}));
})();
