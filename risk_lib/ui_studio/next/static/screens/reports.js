// screens/reports.js: the 보고서 group (design spec 2.1).
// exec-report, approval-pack, headline-trend, capital-verdict, reg-forms.
// Only NG.ui, NG.charts, NG.shared and the shell contract are used. Every
// authored Korean string is a catalogue key of i18n/ng_reports.py or of the
// shell sections (ng_frag, ng_gate, ng_capital, ng_pack, ng_trend, ng_queue,
// ng_close, ng_shell); ledger values, ids, digests, check names, form codes
// and citations are printed verbatim and never translated. Counts come from
// the D.x_* server objects, never from rows.length.
(function(){
'use strict';
const NG=window.NG,U=NG.ui,C=NG.charts,el=U.el,ap=U.ap,T=NG.T,TF=NG.TF,PR=NG.text,F=NG.fmt;
const D=()=>NG.D,A=o=>o||{};
const MAXROW=7;

// ── small helpers ────────────────────────────────────────────────────
// base.css hides every bare <section> that is not the active screen, so the
// card sections here are the folded (details) form of NG.ui.section, opened.
function sec(root,title){const s=U.section(title,{folded:true,open:true});ap(root,s);return s}
function meta(s){return el('div','meta',s)}
function kv(rows){return U.simpleTable(['항목','값'],rows,{})}
function h4(s){return el('h4',null,T(s))}
function toneOfCount(n){return NG.tone('val_check.status',n?'FAIL':'PASS')}
// citation of the figure whose check_names carry this check (x_lineage)
function citeOf(name){const fg=A(A(D().x_lineage).figures),ks=Object.keys(fg);let out='-';
  for(let i=0;i<ks.length;i++){const f=fg[ks[i]];
    if((f.check_names||[]).indexOf(name)>=0&&f.audit&&f.audit.citation){out=f.audit.citation;break}}
  return out}
// payload prose: <b> dropped, <a href> resolved to a screen by its legacy
// label, everything else printed as text through NG.text (long dashes gone)
const RE_TAG=/<a href="[^"]*">([^<]*)<\/a>|<\/?b>/g;
function prose(s){const t=PR(s),out=el('span','prose');let last=0,m;RE_TAG.lastIndex=0;
  while((m=RE_TAG.exec(t))!==null){
    if(m.index>last)ap(out,t.slice(last,m.index));
    if(m[1]!=null){const lab=m[1].replace(/^[\s→]+/,''),id=NG.resolveLegacy(lab);
      ap(out,id?U.button(lab,{onClick:()=>NG.go(id)}):el('span','meta',lab))}
    last=RE_TAG.lastIndex}
  ap(out,t.slice(last));return out}
function proseList(items,grade){const u=el('ul','proselist');
  items.forEach(t=>{const li=el('li');
    const m=grade?/^\[([A-Z]+)\]\s*/.exec(t):null;
    if(m)ap(li,U.badge(m[1],NG.tone('kri.grade',m[1])),' ');
    ap(li,prose(m?t.slice(m[0].length):t));ap(u,li)});
  return u}
function boardCol(titleKey,items,moreId){const c=el('div');ap(c,el('h3',null,T(titleKey)));
  ap(c,U.dotlist(items.slice(0,MAXROW)));
  const n=items.length-MAXROW;
  if(n>0){const b=U.button(TF('{n}건 더 보기',{n:n}),{onClick:()=>NG.go(moreId)});b.classList.add('more');ap(c,b)}
  return c}
function dispatchWord(i){return i.dispatched===true?T('발신'):i.dispatched===false?T('미발신'):T('발신 미확인')}

// ════════════════════════════════════════════════════════════════════
// 1. exec-report (종합보고서). A5 pins this function name and signature.
// ════════════════════════════════════════════════════════════════════
function executiveReport(root){
  const d=D(),E=A(d.executive),X=A(d.x_capital),g=A(d.x_gate);
  execBoard(root,d,E,X,g);
  execKpis(root,d);
  execProse(root,E);
  execKri(root,E,d);
  execStack(root,X,d);
  execAttr(root,E);
  execSevere(root,A(E.facts),X);
  execLinks(root);
}
function execBoard(root,d,E,X,g){
  const b=el('div','board'),q=A(d.x_queue),tr=A(d.x_trend),self=A(g.self);
  // column A: 현재 적색
  const ca=[],amber=[];
  // RED KRIs lead; AMBER KRIs trail so that the blocking checks, the limit
  // population and the stress quarters stay inside the seven visible lines
  (E.kris||[]).forEach(k=>{const t={text:k.name+' '+k.actual_text+' · '+k.threshold_text,right:k.grade,
    tone:NG.tone('kri.grade',k.grade)};
    if(k.grade==='RED')ca.push(t);else if(k.grade==='AMBER')amber.push(t)});
  (self.blocking_checks||[]).forEach(c=>ca.push({text:c.check_name+' '+c.status+' · '+citeOf(c.check_name),
    tone:NG.checkTone(c),onClick:()=>NG.drawer.check(c.check_name)}));
  const lf=A(A(A(d.x_limits).populations).limits_full),nb=(lf.breach||0)+(lf.critical||0);
  ca.push({text:TF('한도 위반 {n}건 (전량 {N}건 서버 집계)',{n:nb,N:lf.total}),tone:toneOfCount(nb),onClick:()=>NG.go('limits')});
  const nq=X.n_fail_quarters||0;
  ca.push({text:TF('위기상황 미통과 분기 {n}건',{n:nq}),tone:nq?A(X).tone||'bad':'good',onClick:()=>NG.go('capital-verdict')});
  amber.forEach(t=>ca.push(t));
  // column B: 차단과 이유 (kpis[4] and kpis[5] lead, then the gate and holds)
  const cb=[],kp=d.kpis||[];
  [4,5].forEach(i=>{const k=kp[i];if(!k)return;const ln=NG.lineage.kpi(i);
    cb.push({text:k.label+' '+k.value+(k.sub?' · '+k.sub:''),tone:k.tone||'neutral',
      onClick:ln?()=>NG.drawer.lineage(ln):null})});
  const ov=A(g.overall);
  cb.push({text:T('전체 판정')+' '+(ov.status||'-')+' · '+T(ov.blocks_approval?'결재 차단':'결재 차단 아님'),
    tone:ov.tone||'neutral',onClick:()=>NG.drawer.gate()});
  (q.holds||[]).forEach(h=>{const ub=h.unblock;
    const act=ub?[ub.alert_type,PR(ub.bound_action),ub.owner_role,ub.sla_days!=null?T('SLA (일)')+' '+F.int(ub.sla_days):null].filter(Boolean).join(' · ')
      :T('담당 미확인, 일치하는 gov_alert_policy 행 없음');
    cb.push({text:PR(h.reason_text)+' · '+TF('{n}건',{n:h.n})+' · '+act,
      tone:NG.tone('hold.reason_kind',h.reason_kind),onClick:()=>NG.go('decision-queue')})});
  // column C: 변화 (기간 대비)
  const cc=[];
  if(!(tr.n_periods>1))cc.push({text:T('추이 원장에 기간이 하나뿐이다'),tone:'not-run',onClick:()=>NG.go('headline-trend')});
  else (tr.flags||[]).forEach(fl=>cc.push({text:(fl.label||fl.metric)+' '+F.num(fl.latest)+' · '+T('전기 대비')+' '+F.num(fl.qoq)
      +' · '+T('하한선')+' '+F.num(fl.floor)+' · '+TF('연속 위반 {n}',{n:fl.consecutive_breaches}),
    right:fl.trend_state,tone:NG.tone('trend.state',fl.trend_state)}));
  ap(b,boardCol('현재 적색',ca,'decision-queue'),boardCol('차단과 이유',cb,'decision-queue'),
    boardCol('변화 (기간 대비)',cc,'headline-trend'));
  ap(root,b);
}
function execKpis(root,d){
  const s=sec(root,'헤드라인 지표'),items=[];
  const KN=(d.x_kpi&&d.x_kpi.numeric)||{};
  (d.kpis||[]).slice(0,4).forEach((k,i)=>items.push(U.kpi({label:k.label,
    value:(KN[i]&&KN[i].kind==='money')?F.money(KN[i].value):k.value,sub:NG.kpiSub(i,k.sub),
    tone:k.tone||'neutral',lineage:NG.lineage.kpi(i)})));
  ap(s,U.kpiRow(items,'committee'));
}
function execProse(root,E){
  const br=E.briefing||[],ac=E.actions||[];
  if(br.length){const s=sec(root,'CRO 브리핑');ap(s,proseList(br,false))}
  if(ac.length){const s=sec(root,'CRO 액션 (즉시·단기 조치)');ap(s,proseList(ac,true))}
}
function execKri(root,E,d){
  const ks=E.kris||[],nk=ks.length;if(!nk)return;
  const s=sec(root,'KRI 스코어카드 (위험선호체계)'),tr=A(d.x_trend);
  U.hint(s,'RED 는 board 한계 위반, AMBER 는 management 한계, WATCH 는 operational 조기경보, GREEN 은 한계 이내다');
  ap(s,C.kriCards(ks,{arrows:(tr.n_periods>1)?(tr.flags||[]):null}));
  const cnt=x=>{let n=0;ks.forEach(k=>{if(k.grade===x)n++});return n};
  ap(s,meta(TF('RED {red} · AMBER {amber} · WATCH {watch} · GREEN {green} · 전체 {total}',
    {red:cnt('RED'),amber:cnt('AMBER'),watch:cnt('WATCH'),green:cnt('GREEN'),total:nk})));
  U.hint(s,'임계는 RAF 원장에서 온다');
}
function execStack(root,X,d){
  const f=NG.frame.frameOf('cap_stack');let rows=X.tiers||[];
  if(!rows.length&&f)rows=NG.frame.frameObjects(f).map(r=>({label:r.tier,amount:null,
    instrument:r.tier,instrument_amount:r.amount,ratio:r.ratio,
    required:r.required,surplus:r.surplus,tone:'neutral'}));
  if(!rows.length)return;
  const s=sec(root,'자본 스택 (계층별 요구 대비 여유)');
  ap(s,C.bars(rows.map(r=>({label:r.label,value:r.ratio,tone:r.tone})),
    {title:T('자본 계층')+' · '+T('비율'),fmt:v=>F.pct(v),src:f||null,note:T('요구 대비 여유는 표에 있다')}));
  ap(s,U.simpleTable(['계층','누적 금액','구성 상품','상품 금액','비율','소요','잉여'],
    rows.map(r=>[r.label,F.orDash(r.amount==null?null:F.money(r.amount)),r.instrument||'-',
    F.orDash(r.instrument_amount==null?null:F.money(r.instrument_amount)),F.pct(r.ratio),
    F.pct(r.required),U.badge(F.pp(r.surplus*100,3),r.tone||'neutral')]),{}));
  U.hint(s,'비율은 그 상품까지 누적한 자본의 비율이고, 상품 금액은 그 계층에 더해지는 금액이다. 누적 금액은 상품 금액을 누적한 값이다');
  const sh=[];rows.forEach(r=>{if(r.surplus<0)sh.push(r.label)});
  if(sh.length)ap(s,U.note(T('요구 미달 계층')+': '+sh.join(' · ')+' · '+T('배당·성과급 제한 대상'),'bad'));
}
function rwaScreen(g){const k=String(g||'');return k.indexOf('시장')>=0?'market-rwa':k.indexOf('운영')>=0?'op-rwa':'credit-rwa'}
function execAttr(root,E){
  const at=E.attribution||[],atd=E.attribution_detail||[];if(!at.length)return;
  const s=sec(root,'위험가중자산 귀속 (구성요소별 비중)');
  const src=atd.length?atd.map(x=>({group:x.group,label:x.label,value:x.value}))
    :at.map(x=>({group:x.component,label:x.component,value:x.rwa}));
  ap(s,C.treemap(src,{title:T('구성요소'),fmt:v=>F.money(v),
    note:T('묶음은 최종 RWA 구성요소이고 그 안은 원장 축이다. 합계는 공표 RWA 와 같다.'),
    onCell:it=>NG.go(rwaScreen(it.group||it.label))}));
  const nts=[];atd.forEach(x=>{if(x.note&&nts.indexOf(x.note)<0)nts.push(x.note)});
  if(nts.length)ap(s,meta(nts.join(' / ')));
}
function execSevere(root,facts,X){
  const sv=A(facts.sev),s=sec(root,'심각 시나리오 (자본 저점)');
  ap(s,U.dotlist([
    {text:T('CET1 저점')+' '+F.pct(sv.trough)+' ('+(sv.trough_q||'-')+')',tone:sv.first_breach?'bad':'good'},
    {text:T('종료 시점 CET1')+' '+F.pct(sv.end),tone:'neutral'},
    {text:sv.first_breach?T('최초 침범')+' '+sv.first_breach+' · '+T('침범 비율')+' '+(sv.breach_ratio||'-'):T('요구 비율 침범 없음'),
      tone:sv.first_breach?'bad':'good'},
    {text:T('역스트레스 임계 심도')+' '+F.num(facts.rev_severity),tone:'neutral'},
    {text:TF('위기상황 미통과 분기 {n}건',{n:X.n_fail_quarters}),tone:X.n_fail_quarters?X.tone||'bad':'good'},
    {text:'CET1 '+F.pct(facts.cet1)+' · '+T('잉여')+' '+F.pp(facts.cet1_surplus_pp,3),tone:'neutral'},
    {text:'LCR '+F.pct(facts.lcr)+' · NSFR '+F.pct(facts.nsfr),tone:'neutral'}]));
}
function execLinks(root){
  const s=sec(root,'다음 화면'),r=el('div','row');
  [['결재 패키지','approval-pack'],['자본 판정','capital-verdict'],['헤드라인 추이','headline-trend'],
   ['의사결정 큐','decision-queue']].forEach(x=>ap(r,U.button(T(x[0]),{onClick:()=>NG.go(x[1])})));
  ap(s,r);
}

// ════════════════════════════════════════════════════════════════════
// 2. approval-pack (결재 패키지). Print first, never green while the
//    third line is 응답대기 or 부적합.
// ════════════════════════════════════════════════════════════════════
function approvalPack(root){
  const d=D(),g=A(d.x_gate),iv=A(g.independent),self=A(g.self),rc=A(g.recalc),
    apv=A(g.approvals),sb=A(g.submission),m=A(d.meta);
  packIdentity(root,m,iv);
  packVerdict(root,self,iv,g);
  packHolds(root,apv);
  packChecks(root,self);
  packRecalc(root,rc);
  packConditional(root,A(g.conditional),iv);
  packDecisions(root,apv);
  packSubmission(root,sb);
  packSignature(root,sb);
  packAims(root);
}
function packIdentity(root,m,iv){
  const s=sec(root,'실행 식별');
  ap(s,kv([[T('기관'),m.institution_code],[T('기준일'),m.asof],[T('실행 ID'),m.run_id],
    [T('지문'),m.digest],[T('시드'),m.seed],
    [T('IV 문서 실행 ID (meta.run_id 와 다름)'),iv.run_id||'-'],
    [T('요청 ID'),iv.request_id||'-'],[T('요청 대상'),iv.requested_to||'-'],[T('브랜치'),iv.branch||'-'],
    [T('헤드라인 지문'),iv.headline_digest||'-']]));
}
function packVerdict(root,self,iv,g){
  const s=sec(root,'결재 상신 판정');
  ap(s,U.dotlist([
    {text:T('자체검증 (2선)')+' PASS '+F.int(self.pass)+' · WARN '+F.int(self.warn)+' · FAIL '+F.int(self.fail),
      tone:self.tone||'neutral'},
    {text:T('상시 독립검증 (3선)')+' '+(iv.status||'-')+' ('+(iv.request_id||'-')+')',tone:iv.tone||'neutral',
      onClick:()=>NG.drawer.gate()}]));
  ap(s,meta(TF('PASS {pass} · WARN {warn} · FAIL {fail} · 규제미달 {blocks} · 미실행 {not_run} (항등식 {identity} 제외)',
    {pass:self.pass,warn:self.warn,fail:self.fail,blocks:self.blocks,not_run:self.not_run,identity:self.identity_excluded})));
  const rsp=iv.response||null;
  ap(s,meta([T('종류')+' '+(iv.kind||'-'),T('발신 상태')+' '+dispatchWord(iv),
    T('발신 디렉터리')+' '+(iv.dispatch_dir||'-'),
    T('응답 요청 ID')+' '+(rsp?rsp.request_id:T('응답 없음'))].join(' · ')));
  if(iv.reason)ap(s,meta(T('사유')+': '+PR(iv.reason)));
  const ov=A(g.overall);
  ap(s,U.note(T(ov.blocks_approval?'결재 상신 불가':'결재 상신 가능')+' · '+T('3선이 응답대기 또는 부적합이면 이 패키지는 결재에 올릴 수 없다'),
    ov.tone||'neutral'));
  U.hint(s,'게이트는 fail-closed 다. 응답이 없으면 응답대기이며 결재할 수 없다.');
}
function packHolds(root,apv){
  const s=sec(root,'보류 사유 (중복 제거)'),hs=apv.holds||[];
  if(!hs.length){ap(s,meta(T('보류 사유가 없다')));return}
  ap(s,U.simpleTable(['보류 종류','보류 사유','건수','대상 유형'],hs.map(h=>[
    U.badge(h.reason_kind,NG.tone('hold.reason_kind',h.reason_kind)),PR(h.reason_text),h.n,
    (h.subject_types||[]).join(', ')]),{}));
}
function packChecks(root,self){
  const s=sec(root,'차단 검증'),bc=self.blocking_checks||[];
  if(!bc.length){ap(s,meta(T('차단 검증 없음')));return}
  ap(s,U.simpleTable(['검증 항목','상태','검증 도메인','상세','규정 근거'],bc.map(c=>[c.check_name,
    U.badge(c.status,NG.checkTone(c)),c.domain||'-',PR(c.detail),citeOf(c.check_name)]),
    {onRow:c=>NG.drawer.check(c.check_name)}));
}
function packRecalc(root,rc){
  const s=sec(root,'재계산 커버리지'),cc=A(rc.counts);
  ap(s,U.simpleTable([{label:'일치'},{label:'불일치'},{label:'미보고'},{label:'이전 요청 응답'}],
    [[cc['일치'],cc['불일치'],cc['미보고'],cc.stale]],{}));
  ap(s,meta(T('응답 요청 ID')+' '+(rc.response_request_id||T('응답 없음'))));
  ap(s,recalcTable(rc.rows||[]));
}
function recalcTable(rows){
  return U.simpleTable(['재계산 대상','보고값','재계산값','판정','규정 근거'],rows.map(r=>[
    r.target+(r.korean?' · '+r.korean:''),F.num(r.reported),
    r.recomputed==null?T('미보고'):F.num(r.recomputed),
    U.badge(T(r.state),NG.tone('recalc.state',r.state)),r.citation||'-']),{});
}
const CA_FIELDS=['승인자 (approver)','잔여위험 (residual_risk)','후속조건 (conditions)','이행기한 (due_date)',
  '배포 범위 (scope)','수용한 지적 (findings_accepted)'];
function packConditional(root,cd,iv){
  const s=sec(root,'조건부 승인 기록');
  ap(s,meta(T(cd.required?'조건부 승인 필요':'조건부 승인 불필요')+' · '+(iv.status||'-')));
  if(cd.text)ap(s,U.note(T('조건부 승인 기록 필요: ConditionalApproval 필드를 담는 카탈로그 원장이 없고, 스튜디오는 파일 기록을 읽지 않는다'),
    cd.required?'warn':'neutral'));
  ap(s,U.simpleTable(['항목','값'],CA_FIELDS.map(k=>[T(k),T('기록 없음')]),{}));
  U.hint(s,'결재 책임자가 잔여위험·후속조건·이행기한·배포 범위를 기록해야 통과한다');
  ap(s,meta(T('원장 기록 상태')+' '+(cd.ledger_record==null?T('기록 없음'):String(cd.ledger_record))
    +' · '+T(cd.file_record_read?'파일 기록을 읽었다':'파일 기록을 읽지 않는다')));
}
function packDecisions(root,apv){
  const s=sec(root,'결정 분포');
  ap(s,U.simpleTable([{label:'대기',raw:true},{label:'승인',raw:true},{label:'반려',raw:true},{label:'전체'}],
    [[apv['대기'],apv['승인'],apv['반려'],apv.total]],{}));
  const bst=A(apv.by_subject_type),ks=Object.keys(bst);
  ap(s,h4('대상 유형별'));
  ap(s,U.simpleTable(['대상 유형','건수'],ks.map(k=>[k,bst[k]]),{}));
  ap(s,meta(T('직무분리 위반')+' '+F.int(apv.segregation_violations)));
}
function packSubmission(root,sb){
  const s=sec(root,'제출 현황');
  ap(s,U.simpleTable([{label:'draft',raw:true},{label:'reviewed',raw:true},{label:'approved',raw:true},
    {label:'submitted',raw:true},{label:'전체'}],[[sb.draft,sb.reviewed,sb.approved,sb.submitted,sb.total]],{}));
  ap(s,h4('서식별'));
  ap(s,U.simpleTable(['form_id','상태','서식검증 실패','결재','작성자','검토자','승인자',
    {label:'segregation_ok',raw:true},'지문'],
    (sb.by_form||[]).map(f=>[f.form_id,U.badge(f.status,NG.tone('reg_submission.status',f.status)),
      f.n_failed_checks,U.badge(f.decision||'-',NG.tone('gov_approval.decision',f.decision)),
      f.prepared_by,f.reviewed_by,f.approved_by,
      f.segregation_ok===false?NG.glyph('bad'):String(f.segregation_ok),f.digest]),{}));
}
function packSignature(root,sb){
  const s=sec(root,'서명란 (미서명)'),bf=sb.by_form||[];
  const uq=k=>{const o=[];bf.forEach(f=>{const v=f[k];if(v&&o.indexOf(v)<0)o.push(v)});return o.join(' · ')||'-'};
  const un=()=>U.badge(T('미서명'),'not-run');
  ap(s,U.simpleTable(['역할','결재선 (원장 값)','상태'],[
    [T('작성자'),uq('prepared_by'),un()],
    [T('검토자'),uq('reviewed_by'),un()],
    [T('승인자'),uq('approved_by'),un()]],{}));
  U.hint(s,'서명 없음. 결재선은 원장 값이며 화면은 서명을 만들지 않는다.');
}
function packAims(root){
  const s=sec(root,'AIMS §8-2 자동확정 금지 목록');
  ap(s,el('p',null,T('에이전트는 신용등급·여신승인, 가격·거래, PD·LGD·EAD 등 핵심 위험파라미터, ECL·충당금·회계전표, RWA·NCR·BIS 비율, 감독제출·공시, 경영조치, 운영코드·모형 배포를 자동확정하지 않는다.')));
  U.hint(s,'내보내기는 인쇄만 가능하다. 샌드박스가 다운로드를 막는다.');
  U.hint(s,'AIMS §5 A.9.2 결재선을 그대로 옮겼고 서명은 비워 둔다');
}

// ════════════════════════════════════════════════════════════════════
// 3. headline-trend (헤드라인 추이). One institution, no synthetic history.
// ════════════════════════════════════════════════════════════════════
function colSeries(f,name){const i=(A(f).columns||[]).indexOf(name);
  return i<0?null:(A(f).rows||[]).map(r=>r[i])}
function headlineTrend(root){
  const d=D(),x=A(d.x_trend),g=A(d.x_gate),iv=A(g.independent),m=A(d.meta);
  const s=sec(root,'추이 원장 상태'),dm=x.digest_matches_latest;
  const dmState=dm===true?'일치':dm===false?'불일치':'미보고';
  ap(s,U.dotlist([
    {text:T('추이 원장 경로')+': '+(x.ledger_path||T('원장 경로 없음')),tone:x.ledger_path?'neutral':'not-run'},
    {text:T('기간 수')+' '+F.int(x.n_periods||0),tone:(x.n_periods>1)?'neutral':'not-run'},
    {text:T('헤드라인 지문')+' '+(iv.headline_digest||'-')+' · '
      +(dm===true?T('현재 요청의 헤드라인 지문이 최신 스냅샷 지문과 같다')
        :dm===false?T('현재 요청의 헤드라인 지문이 최신 스냅샷 지문과 다르다'):T('비교 불가')),
      tone:NG.tone('recalc.state',dmState)},
    {text:T('원장은 validation_summary 건수를 담지만 게이트 이력은 없어 게이트 전이는 표시할 수 없다'),tone:'not-run'}]));
  ap(s,meta(T('한 기관만 싣는다')+' · '+(m.institution_code||'-')+' · '+(m.asof||'-')
    +' · '+T('합성 이력은 싣지 않는다')));
  if(x.n_periods>1)trendSeries(root,x);else trendSnapshot(root,g);
}
function trendSeries(root,x){
  const s=sec(root,'추이 지표'),labels=x.periods||[];
  (x.flags||[]).forEach(fl=>{const v=colSeries(x.frame,fl.metric);if(!v)return;
    ap(s,C.multiLine([{name:fl.label||fl.metric,values:v}],labels,
      {title:(fl.label||fl.metric),fmt:q=>F.num(q),rules:[{value:fl.floor,label:T('하한선')}]}))});
  ap(s,U.simpleTable(['지표','최신','전기 대비','하한선','방향','추이 상태','연속 위반'],
    (x.flags||[]).map(fl=>[fl.label||fl.metric,F.num(fl.latest),F.num(fl.qoq),F.num(fl.floor),fl.direction,
      U.badge(T(fl.trend_state),NG.tone('trend.state',fl.trend_state)),fl.consecutive_breaches]),{}));
  const qy=A(x.qoq_yoy),ks=Object.keys(qy);
  if(ks.length){ap(s,h4('전기 대비'));
    ap(s,U.simpleTable(['지표','전기 대비','전년 대비'],ks.map(k=>[k,F.num(A(qy[k]).qoq),F.num(A(qy[k]).yoy)]),{}))}
  const cols=(A(x.frame).columns||[]);
  if(cols.length){ap(s,h4('기간별 검증 요약'));
    ap(s,U.simpleTable(cols.map(c=>({label:c,raw:true})),A(x.frame).rows||[],{}))}
}
function trendSnapshot(root,g){
  const s=sec(root,'헤드라인 스냅샷 (현재 실행)');
  ap(s,U.note(T('단일 기간, 추이 없음'),'not-run'));
  ap(s,recalcTable(A(A(g.recalc).rows)||[]));
  U.hint(s,'현재 실행의 헤드라인 수치다. 기간이 하나뿐이라 차트를 그리지 않는다.');
  U.hint(s,'게이트 전이 없음 (이력 미보존)');
}

// ════════════════════════════════════════════════════════════════════
// 4. capital-verdict (자본 판정). x_capital rendered once.
// ════════════════════════════════════════════════════════════════════
function capitalVerdict(root){
  const d=D(),X=A(d.x_capital),E=A(d.executive),sim=A(d.sim);
  capHead(root,X);
  capTiers(root,X);
  capBuffers(root,X);
  capLeverage(root,X);
  capStress(root,X,A(sim.required)||X.required);
  capChecks(root,X);
  capTargets(root,X);
  capKri(root,X,E);
}
function capHead(root,X){
  const s=sec(root,'판정'),items=[
    {text:T('구속 계층')+' '+(X.binding_tier||'-'),tone:X.tone||'neutral'},
    {text:TF('미통과 분기 {n}건',{n:X.n_fail_quarters}),tone:X.n_fail_quarters?X.tone||'bad':'good',
      onClick:()=>NG.go('stress')}];
  if(X.mda_zone)items.push({text:T('MDA 구간 진입')+' · '+T('배당·성과급 제한 대상'),tone:X.tone||'bad'});
  ap(s,U.dotlist(items));
  U.hint(s,'구속 계층은 잉여가 가장 작은 계층이다. 요구치는 최저 기준에 완충자본을 더한 값이다.');
}
function tierTarget(l){const s=String(l);return s.indexOf('CET1')>=0?'cet1_ratio':s.indexOf('Total')>=0?'total_ratio':null}
function capTiers(root,X){
  const s=sec(root,'자본 계층'),rows=X.tiers||[];
  ap(s,U.simpleTable(['계층','누적 금액','구성 상품','상품 금액','비율','소요','잉여','상태'],
    rows.map(r=>[r.label,F.money(r.amount),r.instrument||'-',
    F.orDash(r.instrument_amount==null?null:F.money(r.instrument_amount)),
    F.pct(r.ratio),F.pct(r.required),F.pp(r.surplus*100,3),U.badge(T(r.surplus<0?'부족':'잉여'),r.tone||'neutral')]),
    {onRow:r=>{const t=tierTarget(r.label),ln=t?NG.lineage.byTarget(t):null;
      if(ln)NG.drawer.lineage(ln);else NG.drawer.gate()}}));
  U.hint(s,'비율은 그 상품까지 누적한 자본의 비율이고, 상품 금액은 그 계층에 더해지는 금액이다. 누적 금액은 상품 금액을 누적한 값이다');
  ap(s,meta(TF('출처: {table}',{table:'cap_stack'})));
}
function capBuffers(root,X){
  const s=sec(root,'버퍼'),b=A(X.buffers),mn=A(X.minimums),rq=A(X.required);
  ap(s,U.simpleTable(['항목','값'],[
    [T('자본보전'),F.pct(b.capital_conservation)],[T('경기대응'),F.pct(b.countercyclical)],
    [T('시스템적 중요 은행'),F.pct(b.dsib)]],{}));
  ap(s,h4('최저 기준'));
  ap(s,U.simpleTable([{label:'계층'},{label:'최저 기준'},{label:'소요'}],
    [['CET1',F.pct(mn.cet1),F.pct(rq.cet1)],['Tier1',F.pct(mn.tier1),F.pct(rq.tier1)],
     ['Total',F.pct(mn.total),F.pct(rq.total)]],{}));
  if(X.mda_zone)ap(s,U.note(T('MDA 구간 진입')+' · '+T('배당·성과급 제한 대상'),X.tone||'bad'));
}
function capLeverage(root,X){
  const s=sec(root,'레버리지'),lv=A(X.leverage);
  ap(s,kv([[T('비율'),F.pct(lv.ratio)],[T('소요'),F.pct(lv.required)],
    [T('익스포저 측정치'),F.money(lv.exposure_measure)]]));
}
function capStress(root,X,req){
  const s=sec(root,'스트레스 경로 (분기별 자본비율)'),rows=X.stress_path||[];
  if(!rows.length){ap(s,meta(T('원장 행 없음')));return}
  const scn=[];rows.forEach(r=>{if(scn.indexOf(r.scenario)<0)scn.push(r.scenario)});
  const box=el('div');
  ap(s,U.chips(scn.map((v,i)=>({value:v,label:v,raw:true,on:i===scn.length-1})),v=>drawStress(box,rows,req,v)));
  ap(s,box);
  drawStress(box,rows,req,scn[scn.length-1]);
  ap(s,U.simpleTable(['시나리오','분기','충격 심도','CET1','Tier1','Total','구속','통과'],rows.map(r=>[r.scenario,r.quarter,
    F.num(r.severity),F.pct(r.cet1_ratio),F.pct(r.tier1_ratio),F.pct(r.total_ratio),r.binding,
    U.badge(T(r.passes?'통과':'미통과'),NG.tone('val_check.status',r.passes?'PASS':'FAIL'))]),{}));
}
function drawStress(box,rows,req,scn){
  box.innerHTML='';
  const rs=[];rows.forEach(r=>{if(r.scenario===scn)rs.push(r)});
  const labels=rs.map(r=>r.quarter),R=A(req),rules=[];
  if(R.cet1!=null)rules.push({value:R.cet1,label:'CET1 '+T('소요')});
  if(R.tier1!=null)rules.push({value:R.tier1,label:'Tier1 '+T('소요')});
  if(R.total!=null)rules.push({value:R.total,label:'Total '+T('소요')});
  ap(box,C.multiLine([{name:'CET1',values:rs.map(r=>r.cet1_ratio)},
    {name:'Tier1',values:rs.map(r=>r.tier1_ratio)},{name:'Total',values:rs.map(r=>r.total_ratio)}],labels,
    {title:T('스트레스 경로')+' · '+scn,fmt:v=>F.pct(v),rules:rules,hatch:rs.map(r=>r.passes===false),
     note:T('빗금 친 분기는 요구치 미달이다')}));
}
function capChecks(root,X){
  const s=sec(root,'이 화면의 2선 검증'),bc=X.blocking_checks||[];
  if(!bc.length){ap(s,meta(T('차단 검증 없음')));return}
  ap(s,U.simpleTable(['검증 항목','상태','상세','규정 근거'],bc.map(c=>[c.check_name,
    U.badge(c.status,NG.checkTone(c)),PR(c.detail),citeOf(c.check_name)]),
    {onRow:c=>NG.drawer.check(c.check_name)}));
}
function capTargets(root,X){
  const s=sec(root,'이 화면의 3선 재계산 대상');
  ap(s,recalcTable(X.targets||[]));
  ap(s,meta(T('세 상태는 일치·불일치·미보고이며, 응답 요청 ID 가 어긋난 항목은 이전 요청 응답이다')));
}
function capKri(root,X,E){
  const s=sec(root,'CET1 등급 (KRI)'),gr=X.kri_cet1_grade;
  const row=el('div','row');ap(row,U.badge(gr||'-',NG.tone('kri.grade',gr)));
  (E.kris||[]).forEach(k=>{if(k.name&&k.name.indexOf('CET1')>=0)
    ap(row,el('span','meta',k.name+' '+k.actual_text+' · '+k.threshold_text))});
  ap(s,row);
  U.hint(s,'임계는 RAF 원장에서 온다');
}

// ════════════════════════════════════════════════════════════════════
// 5. reg-forms (감독보고). Absorbs the legacy 감독보고 screen.
// ════════════════════════════════════════════════════════════════════
function regForms(root){
  const d=D(),forms=d.forms||[],byf={};
  (A(A(d.x_gate).submission).by_form||[]).forEach(f=>{byf[f.form_id]=f});
  ap(root,U.note(T('금융감독원 배포 기준 업무보고서다. 라인마다 산식·규정근거·산출 모듈을 남긴다.'),'neutral'));
  
  const wrap=el('div','split'),list=el('div','list'),pane=el('div');
  const sel=A(NG.route().params).sel;let cur=null,first=null;
  forms.forEach(f=>{
    if(f.section!==cur){cur=f.section;ap(list,el('div','listsec',cur))}
    const b=el('button');b.type='button';
    ap(b,f.form_no+' '+f.form_name,el('small',null,f.form_id+' · '+f.frequency+' · '
      +TF('라인 {n}행',{n:f.n_lines})+' · '+TF('검증 {n}건 · 실패 {k}건',{n:f.n_checks,k:f.n_failed})));
    b.onclick=()=>pick(b,f);
    ap(list,b);
    if((sel&&f.form_id===sel)||(!sel&&!first))first=[b,f]});
  function pick(b,f){Array.prototype.forEach.call(list.children,x=>{if(x.classList)x.classList.remove('on')});
    b.classList.add('on');NG.shared.renderForm(pane,f);ap(pane,formStatus(f,byf[f.form_id]))}
  ap(wrap,list,pane);ap(root,wrap);
  if(first)pick(first[0],first[1]);
  formChecks(root,d);
}
function formStatus(f,row){
  const c=U.section('제출·결재 상태',{folded:true,open:true});
  if(!row){U.hint(c,'이 서식의 제출·결재 원장 행이 없다');return c}
  const r=el('div','row');
  ap(r,U.badge(row.status,NG.tone('reg_submission.status',row.status)),
    U.badge(row.decision||'-',NG.tone('gov_approval.decision',row.decision)),
    U.badge(TF('서식검증 실패 {n}건',{n:row.n_failed_checks}),toneOfCount(row.n_failed_checks)),
    row.segregation_ok===false?U.badge(T('직무분리 위반'),'bad'):null);
  ap(c,r);
  ap(c,kv([[T('작성자'),row.prepared_by],[T('검토자'),row.reviewed_by],[T('승인자'),row.approved_by],
    [T('지문'),row.digest]]));
  ap(c,meta(TF('출처: {table}',{table:'reg_submission · gov_approval'})));
  return c;
}
function formChecks(root,d){
  const s=sec(root,'서식 자체 대사'),fc=d.form_checks;
  if(!fc){ap(s,meta(T('원장 행 없음')));return}
  const i=NG.frame.frameIdx(fc);
  ap(s,U.table(fc,{title:null,rowClass:r=>r[i.status]==='FAIL'?'bad':null}));
  U.hint(s,'FAIL 행은 붉게 칠한다. 건수는 서버 집계이고 표본 행은 확인용이다.');
}

// ── registration ────────────────────────────────────────────────────
NG.screen('exec-report',{group:'보고서',sub:null,title:'종합보고서',build:executiveReport});
NG.screen('approval-pack',{group:'보고서',sub:null,title:'결재 패키지',build:approvalPack});
NG.screen('headline-trend',{group:'보고서',sub:null,title:'헤드라인 추이',build:headlineTrend});
NG.screen('capital-verdict',{group:'보고서',sub:null,title:'자본 판정',build:capitalVerdict});
NG.screen('reg-forms',{group:'보고서',sub:null,title:'감독보고',build:regForms});
})();
