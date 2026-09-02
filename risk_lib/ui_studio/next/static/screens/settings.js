/* screens/settings.js: 설정 3화면 (설정 · 기관 설정 · 산출 방법론). */
/* 규칙 (설계 사양 2.10·5·6장, 수용기준 A8·A12·A17·A21): */
/* - 화면은 계산기가 아니다. 표시명 재정의와 기준일 전환만 세션에 적용되고, */
/*   서식번호 매핑과 방법론 변경은 제안서만 만든다. 적용은 코드 반영 + */
/*   파이프라인 재실행 + 검증 두 층이며 화면이 산출을 바꾸지 않는다. */
/* - 건수·총계는 서버 객체(x_gate·프레임 total)에서 읽는다. */
/* - 색은 NG.tone(원장 어휘, 값) 하나로만 정한다. 자체 색표는 없다. */
(function(){
'use strict';
const NG=window.NG,U=NG.ui,CH=NG.charts,FR=NG.frame,el=U.el,ap=U.ap;
const T=NG.T,TF=NG.TF,fmt=NG.fmt,TN=NG.tone,IX=FR.frameIdx;
const GRP='설정',SUB='⚙ 설정';
/* base.css 가 section{display:none} 이라 펼친 카드는 div 로 만든다. */
const MT=t=>el('div','meta',t);
const CARD=(cls,ttl)=>{const c=el('div','card '+cls);ap(c,el('h3',null,T(ttl)));return c};
const LEAD=(root,k)=>ap(root,el('p','lead',T(k)));
const G=(c,n)=>(c.D.data||{})[n]||null;
/* 표 제목은 카탈로그 한글명 그대로다. 원장 어휘는 번역하지 않는다. */
const CK=n=>{const r=NG.cat(n);return (r&&r.korean)||n};
/* 언어 전환은 build 를 다시 부른다. 모듈 적재 시점에 번역을 굳히지 않는다. */
const KILL=()=>T('비상정지 (실행 차단)');
const BAD=(n,msg)=>{n.textContent='';ap(n,NG.glyph('bad'),' '+msg);n.hidden=false};

/* ══════════════ 설정 (leaf-parent) ═══════════════════════════════════ */

/* 실은 실행. 기준일 전환 대상과 각 실행의 게이트 스냅샷이다. */
function runRegistry(root,c){
  const box=CARD('set-runs','실은 실행 (기준일 전환 대상)');
  ap(box,MT(T('기준일 전환은 미리 산출해 실은 실행 사이의 전환이다. 새 기준일은 run_pipeline 재실행으로만 생긴다. 화면이 즉석에서 만들 수 없다. 게이트 열은 각 실행을 산출한 시점의 스냅샷이며, 이후 3선 응답은 반영되지 않는다.')));
  const R=c.RUNS||{},ks=Object.keys(R).sort(),n=ks.length;
  const rows=ks.map(function(a){
    const p=R[a]||{},m=p.meta||{},g=p.x_gate||{},iv=g.independent||{},s=g.self||{};
    const st=iv.status||T('미확인');
    return [a,m.run_id,m.institution_code,String(m.digest||'').slice(0,12),m.seed,
      fmt.orDash(iv.request_id),U.badge(st,TN('independent.status',st)),
      'PASS '+fmt.int(s.pass)+' · WARN '+fmt.int(s.warn)+' · FAIL '+fmt.int(s.fail)+
      ' · '+T('미실행')+' '+fmt.int(s.not_run)];
  });
  ap(box,U.simpleTable(['기준일','실행 ID','기관코드','산출 지문','시드','3선 요청',
    '게이트','자체검증(2선)'],rows,{numeric:false}));
  ap(box,MT(TF('기준일 전환 대상 {n}개',{n:n})));
  ap(root,box,U.table(G(c,'val_independent_request'),
    {title:CK('val_independent_request'),raw:true}));
}

/* 컬럼 표시명 재정의. 세션 한정이며 물리명은 열 머리 툴팁으로 남는다. */
function labelSettings(root,c){
  const box=CARD('set-labels','컬럼 표시명 매핑');
  ap(box,MT(T('정본은 데이터모델 카탈로그(ColumnSpec.korean)다. 여기서 바꾼 표시명은 이 세션의 화면에만 적용되며, 영구 반영은 카탈로그 수정으로 한다. 물리명은 항상 열 머리글 툴팁으로 남는다.')));
  const names=Object.keys(c.D.data||{}).sort(),bar=el('div','toolbar'),pane=el('div');
  if(!names[0]){ap(box,U.note(T('원장 행 없음'),'warn'));ap(root,box);return}
  ap(bar,U.select(names.map(x=>({value:x,label:x,raw:true})),v=>draw(v)));
  ap(box,bar,pane);
  function draw(nm){
    pane.innerHTML='';
    const f=(c.D.data||{})[nm];if(!f)return;
    const ovr=(NG.state.labelOverrides||{})[nm]||{},inputs={};
    const rows=f.columns.map(function(col,i){
      const inp=U.input({value:ovr[col]||'',placeholder:T('(카탈로그 표시명 사용)'),aria:col});
      inputs[col]=inp;
      return [el('span','mono',col),(f.labels&&f.labels[i])||col,inp]});
    ap(pane,U.simpleTable(['물리명','카탈로그 표시명','세션 재정의'],rows,{numeric:false}));
    const acts=el('div','toolbar');
    ap(acts,U.button(T('세션에 적용'),{primary:true,onClick:function(){
      const m={};Object.keys(inputs).forEach(function(k){
        const v=inputs[k].value.trim();if(v)m[k]=v});
      if(Object.keys(m)[0])NG.state.labelOverrides[nm]=m;
      else delete NG.state.labelOverrides[nm];
      NG.repaintAll()}}),
      U.button(T('재정의 지우기'),{onClick:function(){
        delete NG.state.labelOverrides[nm];NG.repaintAll()}}));
    ap(pane,acts,U.srcMeta(f));
  }
  draw(names[0]);
  ap(root,box);
}

/* FINES 서식번호 형식. 배포 코드는 B/BA/BF + 숫자 3~5자리(+ -가지번호), 내부 */
/* 관리 서식은 RM-####. B10101·B11101 처럼 5자리 숫자부가 실재한다. */
const FORM_RE=/^(?:B[AF]?\d{3,5}(?:-\d+)?|RM-\d{4})$/;
/* 중복 비교는 표시문자열이 아니라 코드로 한다. "RM-6401 (내부관리)" 처럼 */
/* 접미사가 붙은 값을 그대로 키로 쓰면 "RM-6401" 입력이 검사를 지나간다. */
const formKey=s=>String(s).split(' ')[0];

function formMap(root,c){
  const box=CARD('set-formmap','서식번호 매핑 (내부 코드 ↔ 금감원 배포 서식번호)');
  ap(box,MT(T('서식번호는 제출본을 식별한다. 이 화면은 매핑 변경 제안서만 만들고, 적용은 risk_lib/regulatory/form_ids.py 반영 후 파이프라인 재실행으로 한다.')));
  const forms=c.D.forms||[],used={};
  forms.forEach(function(f){used[formKey(f.form_no)]=f.form_id});
  const nOff=forms.filter(f=>f.official).length,nAll=forms.length;
  ap(box,MT(TF('서식 {n}종',{n:nAll})+' · '+TF('배포본 확정 {n}종',{n:nOff})+
    ' · '+TF('내부 배정 {n}종',{n:nAll-nOff})));
  const bar=el('div','toolbar');
  const sel=U.select(forms.map(f=>({value:f.form_id,
    label:f.form_id+' · '+f.form_no+' · '+f.form_name,raw:true})));
  const inp=U.input({placeholder:T('새 서식번호'),aria:T('새 서식번호')});
  ap(bar,sel,inp);
  const err=U.note('','bad');err.hidden=true;
  const out=el('pre','mono');out.style.whiteSpace='pre-wrap';
  ap(bar,U.button(T('변경 제안 생성'),{primary:true,onClick:function(){
    err.hidden=true;out.textContent='';
    const fid=sel.value,v=inp.value.trim(),cur=forms.find(f=>f.form_id===fid);
    function stop(msg){BAD(err,msg)}
    if(c.killedFor())return stop(KILL());
    if(!v)return stop(T('바꿀 서식번호를 적는다'));
    if(!FORM_RE.test(v))return stop(TF('{no} 는 형식 위반이다 (B/BA/BF+숫자(-가지) 또는 RM-####)',{no:v}));
    const own=used[formKey(v)];
    if(own)return stop(TF('{no} 는 {fid} 가 이미 사용한다',{no:v,fid:own}));
    out.textContent=JSON.stringify({proposal:T('서식번호 매핑 변경'),
      asof:c.D.meta.asof,run_id:c.D.meta.run_id,
      change:{form_id:fid,from:cur?cur.form_no:null,to:v},
      apply_path:'risk_lib/regulatory/form_ids.py',
      procedure:[T('코드 반영'),T('파이프라인 재실행'),T('자체검증(2선) FAIL 0 확인'),
        T('상시 독립검증 (3선) 재요청'),T('게이트 통과 후 결재')],
      note:T('화면에는 적용되지 않는다. 서식번호는 제출 지문에 포함된다.')},null,2)}}));
  ap(box,bar,err,out,U.table(G(c,'reg_form'),{title:CK('reg_form'),raw:true}));
  ap(root,box);
}

function settingsScreen(root,c){
  LEAD(root,'표시명·기준일 전환은 세션 안에서 즉시 적용된다(산출값 무관). 서식번호 매핑과 시나리오 파라미터는 산출물의 정체를 바꾸므로 화면에서 적용하지 않는다. 변경 제안서를 만들고, 적용은 코드 반영 + 파이프라인 재실행 + 검증 두 층(자체검증·독립검증)을 다시 거친다.');
  runRegistry(root,c);labelSettings(root,c);formMap(root,c);
  const box=CARD('set-elsewhere','다른 화면에 있는 설정');
  ap(box,MT(T('시나리오 파라미터는 위기상황 그룹의 시나리오 설정 화면에, 시장 포트폴리오 구성은 시장 그룹의 포트폴리오 설정 화면에 있다.')));
  const bar=el('div','toolbar');
  ap(bar,U.button(T('시나리오 설정'),{onClick:()=>c.go('scenario')}),
    U.button(T('포트폴리오 설정'),{onClick:()=>c.go('portfolio-setup')}));
  ap(box,bar);ap(root,box);
}

/* ══════════════ 기관 설정 ════════════════════════════════════════════ */

const IT=(c,n)=>((c.D.institution||{}).tables||{})[n]||null;
function instPairs(c,n){
  const f=IT(c,n);if(!f)return null;
  const i=IX(f),hit=f.rows.find(r=>r[i.institution_code]===c.D.meta.institution_code);
  if(!hit)return null;
  return f.columns.map((col,k)=>[FR.colLabel(f,k),hit[k]]);
}
function institutionScreen(root,c){
  LEAD(root,'기관 전환은 미리 산출해 실은 실행 사이의 전환이다. 화면은 다른 기관의 산출을 만들지 못하며, 새 기관 산출은 파이프라인 재실행으로만 생긴다. 보고통화가 기관마다 다르고 환율 근거가 없어 통화 환산을 하지 않았으므로 기관 간 금액은 비교하거나 합산하지 않는다.');
  const mr=(c.D.institution||{}).master_row||{};
  const cur=CARD('inst-current','선택 기관');
  const chips=el('div','chips');
  ap(chips,U.pill(c.D.meta.institution_code));
  if(mr.data_origin)ap(chips,U.pill(mr.data_origin,TN('data_origin',mr.data_origin)));
  if(mr.evidence_status)ap(chips,U.pill(mr.evidence_status));
  ap(cur,chips);
  const m=instPairs(c,'inst_master'),p=instPairs(c,'inst_profile');
  if(m)ap(cur,el('h4',null,T('기관 원장 (inst_master)')),
    U.simpleTable(['항목','값'],m,{numeric:false}));
  if(p)ap(cur,el('h4',null,T('기관 프로파일 (inst_profile)')),
    U.simpleTable(['항목','값'],p,{numeric:false}));
  if(!m&&!p)ap(cur,U.note(T('선택 기관의 원장 행이 payload 에 없다'),'warn'));
  ap(cur,MT(T('데이터 출처가 합성인 기관은 실존 기관의 수치가 아니라 업권 유형의 공개된 성격을 모수로 옮긴 가상 기관이다. 국내 표본 기관의 실명과 규모 구분은 근거가 없어 채우지 않았고 근거 상태를 미확인으로 두었다.')));
  ap(root,cur);
  const reg=CARD('inst-runs','기관별 실린 산출');
  ap(reg,MT(T('선택기에는 산출이 실린 기관만 올라간다. 원장에 있어도 산출이 실리지 않은 기관은 고를 수 없다. 실린 기준일은 그 기관에 실린 실행의 기준일 전량이다.')));
  const f=IT(c,'inst_master');
  if(f){const i=IX(f);
    ap(reg,U.simpleTable(['기관코드','기관명','권역','유형','규제체계','보고통화',
      '데이터 출처','실린 기준일'],f.rows.map(function(r){
        const code=r[i.institution_code],rr=(c.INSTS||{})[code],org=r[i.data_origin];
        return [code,fmt.orDash(r[i.name_ko]||r[i.name_en]),r[i.region],
          r[i.institution_type],r[i.regulatory_regime],r[i.currency],
          U.pill(String(org),TN('data_origin',org)),
          rr?Object.keys(rr).sort().join(' · '):T('산출 미적재')]}),{numeric:false}),
      U.srcMeta(f));
    const mix=IT(c,'inst_portfolio_mix');
    if(mix&&mix.shown>=mix.total){const j=IX(mix);
      const mine=mix.rows.filter(r=>r[j.institution_code]===c.D.meta.institution_code);
      if(mine[0])ap(reg,CH.bars(mine.map(r=>({label:String(r[j.asset_class]),
        value:r[j.n_exposures]})),{title:T('선택 기관 자산군별 익스포저 건수'),
        src:mix,fmt:fmt.int}));}}
  ap(root,reg);
  [['기관 원장','inst_master'],['기관 프로파일 원장','inst_profile'],
   ['기관별 자산군 구성','inst_portfolio_mix'],['기관별 국가 구성','inst_country_mix'],
   ['라벨 어휘집','intl_label_lexicon']].forEach(function(x){
    const fx=IT(c,x[1]);
    ap(root,fx?U.table(fx,{title:x[0]}):U.note(T(x[0])+' · '+x[1],'warn'))});
}

/* ══════════════ 산출 방법론 (설명용 산술) ════════════════════════════ */

/* 방법 선택은 산출값을 바꾼다. 화면은 제안서만 만들고, 원장에 세 방법 결과가 */
/* 이미 있으므로 방법을 바꿨을 때의 차이는 재계산 없이 그대로 읽는다. */
const FUND={cls:'set-method-fund',table:'rwa_fund_result',
  title:'집합투자증권 (LTA · MBA · Fallback, CRE60)',adopted:'adopted_rwa',
  col:{look_through:'rwa_lta',mandate:'rwa_mba',fallback:'rwa_fallback'},
  opts:[['as_is','원장 채택값 (정보 가용성 기준)'],['look_through','전건 LTA 강제 (CRE60.5)'],
    ['mandate','전건 MBA 강제 (CRE60.7)'],['fallback','전건 Fallback 1250% (CRE60.9)']],
  note:'LTA 는 편입자산을 직접 보유한 것처럼, MBA 는 운용지침 한도까지 투자했다고 가정한다. 정보가 부족하면 Fallback 1250% 다.'};
const SEC={cls:'set-method-sec',table:'rwa_sec_result',
  title:'유동화 (SEC-IRBA · ERBA · SA, CRE40.41 계층)',adopted:'adopted_rwa',
  col:{irba:'rwa_irba',erba:'rwa_erba',sa:'rwa_sa'},
  opts:[['as_is','원장 채택값 (CRE40.41 계층)'],['irba','전건 SEC-IRBA (가능한 건만)'],
    ['erba','전건 SEC-ERBA (등급 있는 건만)'],['sa','전건 SEC-SA']],
  note:'계층은 IRBA · ERBA · SA 순이다(CRE40.41). 위험가중 하한은 15%, STC 선순위는 10% 다(CRE44.5).'};

function methodCard(root,c,S){
  const box=CARD(S.cls,S.title),f=G(c,S.table);
  if(!f){ap(box,U.note(T('연결 원장 없음')+' · '+S.table,'warn'));ap(root,box);return}
  const i=IX(f),bar=el('div','toolbar'),pane=el('div');
  ap(bar,U.select(S.opts.map(o=>({value:o[0],label:o[1]})),v=>draw(v)));
  ap(box,bar,pane);
  /* 산출 불가(등급 없음 등)를 0 으로 채우지 않는다. 채우면 자본이 사라지고 */
  /* 그 사실이 화면 어디에도 남지 않는다. 채택값을 유지하고 건수를 적는다. */
  function total(pick){let s=0,skip=0;
    f.rows.forEach(function(r){const a=r[i[S.adopted]]||0;
      if(pick==='as_is'){s+=a;return}
      const v=r[i[S.col[pick]]];
      if(typeof v!=='number'||Number.isNaN(v)){skip++;s+=a}else s+=v});
    return {sum:s,skip:skip}}
  function draw(pick){
    pane.innerHTML='';
    const base=total('as_is').sum,alt=total(pick),d=alt.sum-base;
    const tn=d>0?'bad':d<0?'good':'neutral';
    ap(pane,U.kpiRow([
      U.kpi({label:'원장 채택 위험가중자산',value:fmt.money(base),tone:'neutral',delta:false,
        sub:T('원장 컬럼')+' '+S.adopted}),
      U.kpi({label:'선택 방법 위험가중자산',value:fmt.money(alt.sum),tone:tn,delta:false}),
      U.kpi({label:'차이',value:fmt.money(d),tone:tn,delta:false,
        sub:base?fmt.pct(d/base,1)+' '+T('(채택 대비)'):null})],c.meta.density));
    if(alt.skip)ap(pane,U.note(TF('산출 불가 {n}건은 채택값을 유지했다',{n:alt.skip}),'warn'));
    if(f.shown>=f.total)ap(pane,CH.bars(S.opts.map(o=>({label:T(o[1]),
      value:o[0]==='as_is'?base:total(o[0]).sum})),
      {title:T('위험가중자산 (세 방법·채택값)'),src:f,fmt:fmt.money,
       note:T('원장에 이미 있는 방법별 결과를 그대로 더한 값이다. 재계산이 아니다.')}));
    else ap(pane,MT(T('차트는 전량 프레임에서만 그린다')));
    ap(pane,U.table(f),MT(T(S.note)));
  }
  draw('as_is');
  ap(root,box);
}

const PATHS=[['fund','집합투자증권','risk_lib/datamodel/funds.py'],
  ['sec','유동화','risk_lib/datamodel/securitisation.py'],
  ['ccr','파생 (SA-CCR)','risk_lib/ccr.py']];

function methodProposal(root,c){
  const box=CARD('set-method-proposal','방법론 변경 제안');
  const bar=el('div','toolbar');
  const sel=U.select(PATHS.map(p=>({value:p[0],label:p[1]})));
  const why=U.input({placeholder:T('변경 사유 (필수)'),aria:T('변경 사유 (필수)')});
  const err=U.note('','bad');err.hidden=true;
  const out=el('pre','mono');out.style.whiteSpace='pre-wrap';
  ap(bar,sel,why,U.button(T('제안 생성'),{primary:true,onClick:function(){
    err.hidden=true;out.textContent='';
    const hit=PATHS.find(p=>p[0]===sel.value),v=why.value.trim();
    function stop(msg){BAD(err,msg)}
    if(c.killedFor())return stop(KILL());
    if(!v)return stop(T('변경 사유는 필수다'));
    out.textContent=JSON.stringify({proposal:T('산출 방법론 변경'),
      domain:T(hit[1]),reason:v,asof:c.D.meta.asof,run_id:c.D.meta.run_id,
      apply_path:hit[2],
      procedure:[T('방법론 코드 반영'),T('파이프라인 재실행'),T('자체검증(2선) FAIL 0 확인'),
        T('상시 독립검증 (3선) 재요청'),T('게이트 통과 후 결재')],
      note:T('화면은 원장에 이미 있는 대안 값을 보여줄 뿐 산출을 바꾸지 않는다.')},null,2)}}));
  ap(box,MT(T('방법론 변경은 산출 지문을 바꾸므로 상시 독립검증 (3선) 재요청 대상이다.')),
    bar,err,out);
  ap(root,box);
}

function methodologyScreen(root,c){
  LEAD(root,'집합투자증권(CRE60)과 유동화(CRE40)는 여러 산출 방법이 규정에 함께 있고, 어느 것을 쓸지는 정보 가용성과 정책이 정한다. 원장에 세 방법 결과가 모두 있으므로 방법을 바꿨을 때의 차이를 재계산 없이 본다. 화면은 값을 바꾸지 않고, 적용은 코드 반영 + 재실행 + 자체검증·상시 독립검증을 거친다.');
  methodCard(root,c,FUND);methodCard(root,c,SEC);methodProposal(root,c);
}

NG.screen('settings',{group:GRP,sub:null,title:'설정',build:settingsScreen});
NG.screen('institution',{group:GRP,sub:SUB,title:'기관 설정',build:institutionScreen});
NG.screen('methodology',{group:GRP,sub:SUB,title:'산출 방법론',build:methodologyScreen});
})();
