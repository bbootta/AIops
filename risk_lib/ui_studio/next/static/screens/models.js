// screens/models.js: the 모형 group (design spec 2.4). Eighteen screens:
// model-inventory, validation-schedule, model-risk, model-lifecycle,
// performance, calibration, migration, pd-estimate, lgd-estimate,
// ccf-estimate, capm-discount, defaulted-lgd, beel-plgd, irb-governance,
// lgd-ead-backtest, behaviour-model, nmd-core, behaviour-backtest.
// Only NG.ui, NG.charts, NG.shared and ctx are used. Authored Korean strings
// go through T/TF and live in the base catalogue or i18n/ng_models.py; ledger
// values, ledger column labels, ids, citations and check names are printed
// verbatim. Row counts come from frame.total and the x_ objects, never from
// rows.length as a total; browser-side counts are labelled as what they count.
(function(){
'use strict';
const NG=window.NG,U=NG.ui,C=NG.charts,SH=NG.shared,el=U.el,ap=U.ap,T=NG.T,TF=NG.TF,F=NG.fmt;
const FR=n=>{const d=NG.D.data;return (d&&d[n])||null};
const IX=f=>NG.frame.frameIdx(f);
const P=(v,d)=>F.pct(v,d==null?2:d);
const N2=(v,d)=>typeof v==='number'?v.toFixed(d==null?2:d):F.orDash(v);
const OD=v=>F.orDash(v);
// tone always from the single map: a boolean reads as the val_check vocabulary
const OK=b=>NG.tone('val_check.status',b?'PASS':'WARN');
const BAD=b=>NG.tone('val_check.status',b?'FAIL':'PASS');
const NRUN=()=>NG.tone('val_check.status','_not_run');
const ent=o=>Object.keys(o).map(k=>({label:k,value:o[k]}));
const uniq=a=>{const m={},o=[];a.forEach(x=>{const k=String(x);if(!m[k]){m[k]=1;o.push(x)}});return o};
const opts=v=>v.map(x=>({value:String(x),label:String(x),raw:true}));
function card(t){const c=el('div','card');if(t)ap(c,el('h3',null,T(t)));return c}
function put(root,t,child,m){const c=card(t);if(child)ap(c,child);if(m)ap(c,el('div','meta',T(m)));ap(root,c);return c}
function st(cols,rows,o){return U.simpleTable(cols,rows,o||{numeric:false})}
const RC=(rows,fn)=>{const c=rows.map(fn);return (r,k)=>c[k]};
const K=(l,v,s2,t,g)=>({label:l,value:v,sub:s2,tone:t,lineage:g});
function lead(root,s){ap(root,U.note(T(s),'neutral'))}
function miss(root,n){ap(root,U.note(T('원장에 없다')+' · '+n,'warn'))}
function src(f){return U.srcMeta(f)}
function led(root,n,o){const f=FR(n);if(!f)return null;const c=NG.cat(n);
  const x=U.table(f,Object.assign({title:(c&&c.korean)||n,raw:true},o||{}));ap(root,x);return x}
function bar(cb,vals){const b=el('div','toolbar');ap(b,U.select(opts(vals),cb));return b}
// 파생 표는 원장 라벨을 그대로 쓴다. 화면이 컬럼 이름을 새로 지으면 원장과
// 두 벌이 된다. fm 은 컬럼별 표기 코드(p 비율 · n 소수 · m 금액)이거나 행
// 전체를 받는 함수다.
function fx(c){const d=+c.slice(1);
  return c[0]==='p'?(v=>P(v,d)):c[0]==='n'?(v=>N2(v,d)):(v=>F.money(v))}
function proj(f,cols,fm,o){o=o||{};const i=IX(f),g=fm||{};
  const cs=cols.split(' ').map(x=>x.split(':'));
  const hd=cs.map(c=>({key:c[0],label:NG.frame.colLabel(f,i[c[0]]),raw:true,phys:c[0]}));
  return U.simpleTable(hd,(o.rows||f.rows).map(r=>cs.map(c=>{const h=g[c[0]];
    return h?h(r,i):(c[1]?fx(c[1])(r[i[c[0]]]):r[i[c[0]]])})),
    {numeric:o.numeric!==false,rowClass:o.rowClass})}
// 원장이 판정을 비워 두면 화면이 통과·미통과를 만들지 않는다
function judge(r,i){return SH.judgeGlyph(r[i.pass_flag]==null?(r[i.judgment_status]||T('미판정'))
  :(r[i.pass_flag]?'통과':'미통과'))}
function jcls(f){const i=IX(f);
  return RC(f.rows,r=>r[i.pass_flag]==null?'warn':(r[i.pass_flag]?null:'bad'))}
function review(root){ap(root,U.note(T('이 수치는 합성 포트폴리오를 파이프라인에 넣어 낸 산출이다. 쓰기 전에 소관 부서 검토를 거치고 결과는 승인 원장에 남는다.'),'synthetic'))}
function sources(root,names){SH.almSources(root,names.map(n=>{const c=NG.cat(n);
  return {name:c?c.korean:n,source:n,kind:c?c.product:T('카탈로그 외 · 엔진 산출')}}))}
function evid(root,names){SH.almEvidence(root,names.map(n=>{const f=FR(n);
  if(!f)return {ledger:n,rows:null};
  const i=IX(f),r=f.rows[0]||[],g=k=>i[k]==null?null:r[i[k]];
  return {ledger:n,rows:f.total,approved_on:g('approval_date')||g('approved_on'),
    evidence_status:g('evidence_status'),citation:g('citation')}}))}
// 코드 마스터가 정본이다. 등급 순서는 선언 순서이며 가나다순이 아니다
function codeOrder(tbl,col){const f=FR('rdm_code_master');if(!f)return null;
  const i=IX(f),want=tbl+'.'+col,a={},b={};let na=0,nb=0;
  f.rows.forEach(r=>{const s=r[i.code_set];
    if(s===want){a[r[i.code]]=r[i.sort_order];na++}
    else if(s===col){b[r[i.code]]=r[i.sort_order];nb++}});
  return na?a:(nb?b:null)}
function byCode(vals,tbl,col){const rk=codeOrder(tbl,col),o=vals.slice();
  if(rk)o.sort((x,y)=>(rk[x]==null?1e9:rk[x])-(rk[y]==null?1e9:rk[y]));
  return o}

// ── IRB 공통: 추정 실행 · 하한 원장 · MoC 구성요소 · 단계별 폭포 ──────
const IRBC=[['crm_estimation_run','추정 실행','segment exposure_class method observation_years min_observation_years meets_minimum moc_status floor_applied n_floor_binding unresolved_inputs next_review_due status',
  (r,i)=>r[i.meets_minimum]===null?'warn':(r[i.meets_minimum]?null:'bad')],
 ['crm_input_floor','입력 하한 원장','framework_version parameter exposure_class collateral_type floor_value:p3 floor_status evidence_status note',
  (r,i)=>r[i.floor_value]==null?'warn':null],
 ['crm_moc_component','MoC 구성요소','segment grade moc_driver point_estimate:n5 moc_amount:n5 moc_formula param_available',
  (r,i)=>r[i.param_available]?null:'warn']];
// 추정 실행·하한 원장·MoC 구성요소. 모수 칸은 원장 값이고 화면이 채우지 않는다
function irbCards(root,p){IRBC.forEach(x=>{const f=FR(x[0]);if(!f)return;
  const i=IX(f),rs=f.rows.filter(r=>String(r[i.parameter]).toUpperCase().indexOf(p)===0);
  if(!rs.length)return;
  const c=card(null);ap(c,el('h3',null,p+' '+T(x[1])));
  ap(c,proj(f,x[2],null,{rows:rs,rowClass:RC(rs,r=>x[3](r,i))}),src(f));
  ap(root,c)})}
// 원시추정 → 하한 → MoC → 최종. 단계값은 전부 원장 컬럼이다
function stages(root,f,rows,p,fmt){if(!rows.length)return;
  const i=IX(f),keys=rows.map(r=>String(r[i.segment])+(i.grade==null?'':' · '+r[i.grade]));
  let k=0;const c=card(null),pane=el('div'),tb=el('div','toolbar');
  ap(tb,U.select(keys.map((x,n)=>({value:String(n),label:x,raw:true})),v=>{k=+v;draw()}));
  ap(c,el('h3',null,TF('{p} 추정 단계',{p:p})),tb,pane,src(f));
  function draw(){pane.innerHTML='';const r=rows[k];if(!r)return;
    const raw=r[i.raw_estimate],sp=[];
    if(r[i.after_floor]!=null)sp.push({label:T('하한 적용'),delta:r[i.after_floor]-raw});
    if(i.seasoning_addon!=null&&r[i.seasoning_addon])sp.push({label:T('경과효과 가산'),delta:r[i.seasoning_addon]});
    if(r[i.after_moc]!=null&&r[i.after_floor]!=null)sp.push({label:T('MoC 가산'),delta:r[i.after_moc]-r[i.after_floor]});
    if(r[i.final_applied]!=null&&r[i.after_moc]!=null&&r[i.final_applied]!==r[i.after_moc])
      sp.push({label:T('기타 조정'),delta:r[i.final_applied]-r[i.after_moc]});
    ap(pane,C.waterfall(sp,raw,{title:TF('{p} 단계별 폭포',{p:p}),fmt:fmt,startLabel:T('원시추정'),
      note:T('하한 상태')+' '+OD(r[i.floor_status])+' · '+T('MoC 상태')+' '+OD(r[i.moc_status])+' · '+
        T('하한이 물었는가')+' '+(r[i.floor_binding]?T('예'):T('아니오'))}))}
  draw();ap(root,c)}

// ════════════════ 1. 모형 인벤토리 ════════════════════════════════════
function invAgg(){const f=FR('crm_model');if(!f)return null;
  const i=IX(f),dom={},tier={},own={},stat={};let over=0,uat=0;
  f.rows.forEach(r=>{dom[r[i.domain]]=(dom[r[i.domain]]||0)+1;
    const t='Tier '+r[i.tier];tier[t]=(tier[t]||0)+1;
    own[r[i.owner]]=(own[r[i.owner]]||0)+1;stat[r[i.status]]=(stat[r[i.status]]||0)+1;
    if(r[i.is_overdue])over++;if(r[i.status]!=='PROD')uat++});
  return {f:f,i:i,dom:dom,tier:tier,own:own,stat:stat,over:over,uat:uat,
    nd:Object.keys(dom).length,no:Object.keys(own).length}}
function inventory(root){const a=invAgg();if(!a)return miss(root,'crm_model');
  lead(root,'신용·시장·ALM·위기상황·기후·전사 모형이 한 원장에 있다. 기한이 지난 모형의 산출은 재검증 전까지 쓰지 않는다.');
  ap(root,U.kpiRow([
    K('등록 모형',F.int(a.f.total),T('원장 전량')),K('리스크 도메인',F.int(a.nd)),
    K('검증 기한 초과',F.int(a.over),null,BAD(a.over>0)),
    K('운영 전 (PROD 아님)',F.int(a.uat),null,OK(a.uat===0))]));
  const g=el('div','grid');
  ap(g,C.hbars(ent(a.dom).sort((x,y)=>y.value-x.value),{title:T('도메인별 모형 수'),money:false,src:a.f}),
    C.hbars(ent(a.tier).sort((x,y)=>x.label<y.label?-1:1),{title:T('등급(Tier)별 모형 수'),money:false}));
  ap(root,g);
  let pick='';const c=card('모형 카드'),pane=el('div'),tb=el('div','toolbar');
  ap(tb,U.select([{value:'',label:'전체 도메인'}].concat(opts(Object.keys(a.dom).sort())),
    v=>{pick=v;draw()}));
  ap(c,tb,pane);ap(root,c);
  function draw(){pane.innerHTML='';
    const rs=a.f.rows.filter(r=>!pick||r[a.i.domain]===pick),n=rs.length;
    ap(pane,el('div','meta',TF('선택한 도메인의 모형 {n}건 · 원장 전량 {N}건',{n:n,N:a.f.total})));
    ap(pane,proj(a.f,'model_id model_name domain tier status owner purpose',null,{rows:rs}),src(a.f))}
  draw()}
function invSum(){const a=invAgg();if(!a)return null;
  return {text:TF('등록 모형 {n}건 · 도메인 {d}종 · 검증 기한 초과 {o}건 · 운영 전 {u}건',
    {n:a.f.total,d:a.nd,o:a.over,u:a.uat}),tone:BAD(a.over>0)}}

// ════════════════ 2. 검증 일정 ═══════════════════════════════════════
function schedAgg(){const f=FR('crm_model');if(!f)return null;
  const i=IX(f),base=Date.parse(NG.D.meta.asof+'T00:00:00Z');
  const rem=r=>r[i.is_overdue]?-(r[i.days_overdue]||0)
    :Math.round((Date.parse(String(r[i.next_due])+'T00:00:00Z')-base)/86400000);
  const rows=f.rows.slice().sort((x,y)=>String(x[i.next_due])<String(y[i.next_due])?-1:1);
  let over=0,near=null;
  rows.forEach(r=>{if(r[i.is_overdue])over++;const v=rem(r);if(near==null||v<near)near=v});
  return {f:f,i:i,rows:rows,rem:rem,over:over,near:near}}
function schedule(root){const a=schedAgg();if(!a)return miss(root,'crm_model');
  const i=a.i;
  lead(root,'남은 일수는 원장의 차기 기한과 실행 기준일의 차이이고 지난 건은 원장의 검증 경과일을 쓴다.');
  ap(root,U.kpiRow([
    K('검증 기한 초과',F.int(a.over),null,BAD(a.over>0)),
    K('가장 임박한 기한까지 (일)',F.int(a.near)),
    K('등록 모형',F.int(a.f.total),T('원장 전량'))]));
  const g=el('div','grid');
  ap(g,C.hbars(a.rows.map(r=>({label:r[i.model_id],value:Math.max(a.rem(r),0),
    sub:r[i.is_overdue]?TF('기한 초과 {n}일',{n:r[i.days_overdue]}):String(r[i.next_due])+' · Tier '+r[i.tier],
    tone:r[i.is_overdue]?BAD(true):null})),{title:T('차기 검증까지 남은 일수'),money:false,src:a.f}));
  const bd={};a.rows.forEach(r=>{const d=r[i.domain],v=a.rem(r);if(bd[d]==null||v<bd[d])bd[d]=v});
  ap(g,C.hbars(Object.keys(bd).sort((x,y)=>bd[x]-bd[y]).map(k=>({label:k,value:Math.max(bd[k],0),
    sub:bd[k]<0?TF('경과 {n}일',{n:-bd[k]}):TF('{n}일 남음',{n:bd[k]}),
    tone:bd[k]<0?BAD(true):null})),{title:T('도메인별 가장 임박한 기한'),money:false}));
  ap(root,g);
  const c=card('검증 일정 (차기 기한 순)');
  ap(c,proj(a.f,'model_id domain tier last_validation next_due days_overdue owner',
    {days_overdue:(r,x)=>r[x.is_overdue]?U.badge(TF('기한 초과 {n}일',{n:r[x.days_overdue]}),BAD(true))
      :U.badge(T('기한 내'),OK(true))},{rows:a.rows}),src(a.f));
  ap(root,c);
  put(root,'의존 관계',proj(a.f,'model_id dependencies',null,{rows:a.rows}),
    '상류 모형이 바뀌면 하류 모형도 재검증 대상이다.');
  put(root,'알려진 한계',proj(a.f,'model_id known_limitations',null,{rows:a.rows}),
    '알려진 한계는 모형 원장 값이며 화면이 판단을 더하지 않는다.')}
function schedSum(){const a=schedAgg();if(!a)return null;
  return {text:TF('검증 기한 초과 {o}건 · 가장 임박한 기한까지 {d}일 · 등록 모형 {n}건',
    {o:a.over,d:a.near,n:a.f.total}),tone:BAD(a.over>0)}}

// ════════════════ 3. 모형리스크 ══════════════════════════════════════
function tierRows(a){const i=a.i,out=[];
  uniq(a.f.rows.map(r=>r[i.tier])).sort().forEach(t=>{
    const ms=a.f.rows.filter(r=>r[i.tier]===t);let sum=0,cnt=0,ov=0;
    ms.forEach(r=>{const s=Date.parse(String(r[i.last_validation])+'T00:00:00Z');
      const e=Date.parse(String(r[i.next_due])+'T00:00:00Z');
      if(!isNaN(s)&&!isNaN(e)){sum+=Math.round((e-s)/86400000);cnt++}
      if(r[i.is_overdue])ov++});
    out.push([t,ms.length,ms.map(r=>r[i.model_id]).join(' · '),cnt?Math.round(sum/cnt):null,ov])});
  return out}
function modelRisk(root){const a=invAgg();if(!a)return miss(root,'crm_model');
  lead(root,'등급이 검증 주기를 정하고 소유부서가 이행 주체다. 아래 주기는 원장 날짜의 차이이며 화면 상수가 아니다.');
  const tr=tierRows(a),g=el('div','grid');
  ap(g,C.hbars(tr.map(x=>({label:'Tier '+x[0],value:x[1],
    sub:x[3]==null?T('검증 주기 미상'):TF('검증 주기 {n}일 (원장 산출)',{n:x[3]}),
    tone:x[4]?BAD(true):null})),{title:T('등급별 모형 수와 검증 주기'),money:false,src:a.f}));
  ap(g,C.hbars(ent(a.own).sort((x,y)=>y.value-x.value),{title:T('소유부서별 모형 수'),money:false}));
  ap(root,g);
  put(root,'등급별 거버넌스 이행 상태',
    st(['등급','모형 수','해당 모형','검증 주기 (원장 산출·일)','기한 초과'],tr,
      {numeric:false,rowClass:(r,k)=>tr[k][4]?'bad':null}));
  const c=card('운영 상태 분포');
  ap(c,U.dotlist(Object.keys(a.stat).map(k=>({text:k+' · '+TF('{n}건',{n:a.stat[k]}),
    right:k==='PROD'?T('운영 중'):T('운영 전'),tone:k==='PROD'?OK(true):OK(false)}))));
  ap(c,U.note(T('운영 전 모형의 산출은 공표·제출에 쓰지 않는다. 상태는 원장 값이다.'),'neutral'));
  ap(root,c)}
function riskSum(){const a=invAgg();if(!a)return null;
  return {text:TF('Tier 1 모형 {n}건 · 소유부서 {d}곳 · 운영 전 {u}건 · 검증 기한 초과 {o}건',
    {n:a.tier['Tier 1']||0,d:a.no,u:a.uat,o:a.over}),tone:BAD(a.over>0)}}

// ════════════════ 4. 모형 수명주기 ═══════════════════════════════════
function lifecycle(root){const s=FR('gov_model_stage'),t=FR('gov_model_state'),x=FR('gov_model_transition');
  lead(root,'모형 단계 정의와 현재 단계, 그 사이의 전이 기록이다. 전이는 결정 주체와 승인 문서 참조를 남긴다.');
  if(!s&&!t&&!x)return miss(root,'gov_model_stage');
  if(s&&t){const si=IX(s),ti=IX(t),ord={},cnt={},ct={};
    s.rows.forEach(r=>{ord[r[si.stage]]=r[si.stage_order]});
    t.rows.forEach(r=>{cnt[r[ti.current_stage]]=(cnt[r[ti.current_stage]]||0)+1;
      ct[r[ti.control_status]]=(ct[r[ti.control_status]]||0)+1});
    const g=el('div','grid');
    ap(g,C.hbars(Object.keys(cnt).sort((p,q)=>(ord[p]==null?1e9:ord[p])-(ord[q]==null?1e9:ord[q]))
      .map(k=>({label:k,value:cnt[k],sub:ord[k]==null?T('단계 정의 없음'):TF('단계 순서 {n}',{n:ord[k]})})),
      {title:T('단계별 모형 수'),money:false,src:t}));
    ap(g,C.hbars(ent(ct).sort((p,q)=>q.value-p.value),{title:T('통제 판정 분포'),money:false}));
    ap(root,g)}
  if(x){const xi=IX(x);let no=0;
    x.rows.forEach(r=>{if(r[xi.evidence_ref]==null||r[xi.evidence_ref]==='')no++});
    ap(root,U.note(TF('전이 기록 원장 전량 {N}건 가운데 승인 문서 참조가 빈 건이 {n}건이다. 참조가 비면 증빙으로 쓰지 못한다.',
      {N:x.total,n:no}),no?BAD(true):OK(true)))}
  led(root,'gov_model_stage');led(root,'gov_model_state');led(root,'gov_model_transition')}

// ════════════════ 5. 변별력·안정성 ═══════════════════════════════════
function perfAgg(){const f=FR('crm_performance');if(!f)return null;
  const i=IX(f);let lo=null,nopsi=0;
  f.rows.forEach(r=>{const g=r[i.gini];if(g!=null&&(lo==null||g<lo))lo=g;if(r[i.psi]==null)nopsi++});
  return {f:f,i:i,lo:lo,nopsi:nopsi}}
function performance(root){const a=perfAgg();if(!a)return miss(root,'crm_performance');
  const i=a.i;
  lead(root,'변별력(Gini·KS)과 안정성(PSI)이다. 합격 기준은 2선 검증이 판정한다.');
  ap(root,U.kpiRow([
    K('성능 관측 세그먼트',F.int(a.f.total),T('원장 전량')),
    K('최저 변별력 (Gini)',N2(a.lo,4),null,a.lo==null?NRUN():null),
    K('안정성 지표 미산출',F.int(a.nopsi),null,a.nopsi?NRUN():OK(true))]));
  ap(root,C.hbars(a.f.rows.map(r=>({label:String(r[i.model_id])+' · '+r[i.segment],
    value:(r[i.gini]||0)*100,
    sub:'KS '+N2((r[i.ks]||0)*100,1)+' · PSI '+(r[i.psi]==null?T('미산출'):N2(r[i.psi],3))+' · '+TF('관측 {n}건',{n:r[i.n_obs]}),
    tone:r[i.gini]==null?NRUN():null})),
    {title:T('세그먼트별 변별력 Gini (%)'),money:false,fmt:v=>N2(v,2),src:a.f}));
  led(root,'crm_performance')}
function perfSum(){const a=perfAgg();if(!a)return null;
  return {text:TF('성능 관측 {n}건 · 최저 Gini {g} · 안정성 지표 미산출 {m}건',
    {n:a.f.total,g:N2(a.lo,4),m:a.nopsi}),tone:a.nopsi?NRUN():OK(true)}}

// ════════════════ 6. 등급 보정 ═══════════════════════════════════════
function calAgg(){const f=FR('crm_pd_calibration');if(!f)return null;
  const i=IX(f);let out=0;f.rows.forEach(r=>{if(!r[i.within_tolerance])out++});
  return {f:f,i:i,out:out}}
function calibration(root){const a=calAgg();if(!a)return miss(root,'crm_pd_calibration');
  const i=a.i;
  lead(root,'등급별 예측 PD 와 관측 부도율의 대조다. 허용범위 판정은 원장 컬럼이다.');
  const c=card('보정 상태');
  ap(c,U.meter('허용범위 내 등급',a.f.total-a.out,a.f.total,a.out?OK(false):OK(true)));
  ap(c,el('div','meta',TF('허용범위 밖 {n}건 · 원장 전량 {N}건',{n:a.out,N:a.f.total})),src(a.f));
  ap(root,c);
  ap(root,C.hbars(a.f.rows.slice(0,12).map(r=>({label:String(r[i.segment])+' · '+r[i.grade],
    value:r[i.oe_ratio]||0,
    sub:T('예측 PD')+' '+P(r[i.pd_predicted],2)+' · '+T('관측 부도율')+' '+P(r[i.dr_observed],2)+' · '+TF('차주 {n}',{n:r[i.n_obligors]}),
    tone:r[i.within_tolerance]?null:BAD(true)})),
    {title:T('등급별 관측/예측 비율 (1.0 이 완전 일치)'),money:false,fmt:v=>N2(v,3),src:a.f}));
  led(root,'crm_pd_calibration')}
function calSum(){const a=calAgg();if(!a)return null;
  return {text:TF('허용범위 밖 등급 {n}건 / 전체 {N}건',{n:a.out,N:a.f.total}),tone:BAD(a.out>0)}}

// ════════════════ 7. 등급 전이 ═══════════════════════════════════════
function migration(root){const f=FR('crm_rating_migration');if(!f)return miss(root,'crm_rating_migration');
  const i=IX(f);
  lead(root,'등급 이동행렬과 그 재료 원장이다. 행과 열은 코드 마스터 순서이며 대각선은 등급 유지다.');
  const segs=byCode(uniq(f.rows.map(r=>r[i.segment])),'crm_rating_migration','segment');
  let pick=segs[0];const c=card('전이행렬'),pane=el('div');
  ap(c,bar(v=>{pick=v;draw()},segs),pane);ap(root,c);
  function draw(){pane.innerHTML='';
    const rs=f.rows.filter(r=>r[i.segment]===pick),n=rs.length;
    const gs=byCode(uniq(rs.map(r=>r[i.from_grade]).concat(rs.map(r=>r[i.to_grade]))),
      'crm_rating_migration','from_grade');
    const cell={};let mx=0;
    rs.forEach(r=>{const k=r[i.from_grade]+'>'+r[i.to_grade];
      cell[k]=(cell[k]||0)+(r[i.share]||0);if(cell[k]>mx)mx=cell[k]});
    ap(pane,el('h4',null,T('등급 이동행렬')));
    const w=el('div','tw'),t=el('table'),th=el('thead'),tr=el('tr'),tb=el('tbody');
    ap(tr,el('th',null,T('시작 · 도착')));gs.forEach(g=>ap(tr,el('th','num',String(g))));
    ap(th,tr);ap(t,th);
    gs.forEach(x=>{const row=el('tr');ap(row,el('td',null,String(x)));
      gs.forEach(y=>{const v=cell[x+'>'+y],td=el('td','num',v==null?'-':P(v,1));
        if(v!=null){td.style.background='color-mix(in srgb, var(--accent) '+Math.round(6+50*v/(mx||1))+'%, transparent)';
          td.title=String(x)+' > '+String(y)+' · '+P(v,2)}
        if(x===y)td.style.boxShadow='inset 0 0 0 1px var(--accent)';
        ap(row,td)});
      ap(tb,row)});
    ap(t,tb);ap(w,t);ap(pane,w);
    ap(pane,el('div','meta',TF('세그먼트 {seg} · 전이 기록 {n}건 · 원장 전량 {N}건',{seg:pick,n:n,N:f.total})),src(f))}
  draw();
  led(root,'crm_rating_migration');led(root,'crm_pd_calibration');
  led(root,'crm_performance');led(root,'crm_lgd_component')}
function migSum(){const f=FR('crm_rating_migration');if(!f)return null;
  const i=IX(f),ns=uniq(f.rows.map(r=>r[i.segment])).length;
  return {text:TF('세그먼트 {s}종 · 전이 기록 원장 전량 {N}건',{s:ns,N:f.total}),tone:OK(true)}}

// ════════════════ 8. PD 추정 ═════════════════════════════════════════
const PD_T=['crm_pd_estimate','crm_pd_yearly_dr','crm_estimation_run','crm_estimation_param',
  'crm_input_floor','crm_moc_component','crm_irb_scope','crm_dev_sample'];
function pdEstimate(root){review(root);sources(root,PD_T);
  const f=FR('crm_pd_estimate');if(!f)return miss(root,'crm_pd_estimate');
  const i=IX(f);let bind=0,moc=0;
  f.rows.forEach(r=>{if(r[i.floor_binding])bind++;if(r[i.moc_amount]>0)moc++});
  lead(root,'등급별 장기평균 부도율과 연도별 실적이다. 하한과 MoC 적용 전후 값이 원장에 각각 있다.');
  ap(root,U.kpiRow([
    K('추정 등급 수',F.int(f.total),T('원장 전량')),
    K('하한이 문 등급',F.int(bind),null,OK(bind===0)),
    K('MoC 가산 등급',F.int(moc),null,moc?null:NRUN()),
    K('관측기간 (년)',N2((f.rows[0]||[])[i.observation_years],1))]));
  const rs=f.rows.slice().sort((x,y)=>String(x[i.grade])<String(y[i.grade])?-1:1);
  const cls=rs.map(r=>r[i.floor_binding]?'warn':null);
  put(root,'등급별 PD 추정',
    proj(f,'segment grade estimation_method n_obligors n_defaults raw_estimate:p3 floor_value:p3 floor_binding moc_amount:n5 final_applied:p3 exposure_amount:m',null,{rows:rs,rowClass:(r,k)=>cls[k]}));
  ap(root,C.hbars(rs.map(r=>({label:String(r[i.segment])+' · '+r[i.grade],
    value:(r[i.final_applied]||0)*100,sub:T('원시추정치')+' '+P(r[i.raw_estimate],3),
    tone:r[i.floor_binding]?OK(false):null})),
    {title:T('등급별 최종 적용 PD (%)'),money:false,fmt:v=>N2(v,3),src:f}));
  const y=FR('crm_pd_yearly_dr');
  if(y){const yi=IX(y),segs=uniq(y.rows.map(r=>r[yi.segment]));
    let pick=segs[0];const c=card('연도별 실적 부도율'),pane=el('div');
    ap(c,bar(v=>{pick=v;draw()},segs),pane,src(y));ap(root,c);
    function draw(){pane.innerHTML='';
      const sub=y.rows.filter(r=>r[yi.segment]===pick);
      const gs=uniq(sub.map(r=>r[yi.grade])).sort(),ys=uniq(sub.map(r=>r[yi.cohort_year])).sort();
      ap(pane,C.heat(gs.map(g=>ys.map(v=>{
        const r=sub.filter(x=>x[yi.grade]===g&&x[yi.cohort_year]===v)[0];
        return r?r[yi.default_rate]:null})),gs,ys,
        {title:T('등급 × 코호트연도 실적 부도율'),fmt:v=>P(v,2),
         note:T('추정표본 포함 여부는 원장 컬럼으로 구분한다.')}));
      const out=sub.filter(r=>r[yi.in_estimation_sample]===false),no=out.length;
      if(no)ap(pane,el('div','meta',TF('추정표본 제외 관측 {n}행 · 연도 {y}',
        {n:no,y:uniq(out.map(r=>r[yi.cohort_year])).join(' · ')})))}
    draw()}
  stages(root,f,rs,'PD',v=>P(v,4));
  irbCards(root,'PD');
  const ds=FR('crm_dev_sample');
  if(ds){const di=IX(ds),dc=ds.rows.map(r=>r[di.meets_minimum]===true?null:'bad');
    put(root,'개발표본과 최소 관측기간',
      proj(ds,'model_id segment observation_start observation_end observation_years min_observation_years meets_minimum n_obs n_default default_rate:p2 target_definition evidence_status',null,{rowClass:(r,k)=>dc[k]}))}
  evid(root,['crm_input_floor','crm_estimation_param','crm_irb_scope','crm_dev_sample'])}

// ════════════════ 9. LGD 추정 ════════════════════════════════════════
function lgdEstimate(root){
  const f=FR('crm_lgd_estimate');if(!f)return miss(root,'crm_lgd_estimate');
  const i=IX(f);
  lead(root,'세그먼트별 LGD 와 회수곡선, 관측중단의 영향을 본다. 회수곡선은 회수이력 원장 전량 집계다.');
  ap(root,U.kpiRow(f.rows.map(r=>K('최종 적용 LGD',P(r[i.final_applied],2),
    r[i.segment]+' · '+T('장기 부도가중평균')+' '+P(r[i.longrun_default_weighted_lgd],2),
    r[i.floor_binding]?OK(false):null))));
  const c1=put(root,'LGD 추정 (관측중단 처리 전후)',
    proj(f,'segment discount_rate:p2 discount_rate_status n_defaults n_closed n_censored lgd_excl_censored:p2 lgd_incl_censored:p2 censoring_impact:n4 downturn_lgd:p2 final_applied:p2 status',null));
  ap(c1,src(f));
  const R=NG.D.irb&&NG.D.irb.recovery_curve;
  if(R&&R.length){const sg=uniq(R.map(x=>x.segment));let pk=sg[0];
    const c=card('회수곡선'),pane=el('div');
    ap(c,bar(v=>{pk=v;draw()},sg),pane,el('div','meta',
      TF('회수이력 원장 전량 {r}행 · 부도건 {d}건 집계 (서버 집계)',
        {r:NG.D.irb.recovery_rows,d:NG.D.irb.recovery_defaults})));
    ap(root,c);
    function draw(){pane.innerHTML='';
      const u=R.filter(x=>x.segment===pk).slice().sort((a,b)=>a.month-b.month),nm=u.length;
      ap(pane,C.areaLine(u.map(x=>x.cum_recovery_rate*100),{label:T('누적 회수율 (%)'),
        dates:u.map(x=>x.month),fmt:v=>N2(v,2),title:T('부도 후 경과월별 누적 회수율')}));
      ap(pane,el('div','meta',TF('비용을 뺀 순회수를 부도시점 익스포저로 나눈 값이며 관측 {n}개월까지 있다.',{n:nm})))}
    draw()}
  const ob=FR('crm_default_observation');
  if(ob){const oi=IX(ob),m={};
    ob.rows.forEach(r=>{const k=r[oi.collateral_type]||T('(무담보)'),c=m[k]||{n:0,s:0,e:0};
      c.n+=1;c.s+=(r[oi.lgd_realized]||0);c.e+=(r[oi.lgd_estimated]||0);m[k]=c});
    const c=put(root,'담보유형별 실현 LGD 대 추정 LGD',
      st(['담보유형','부도건수','추정 평균','실현 평균','편의'],
        Object.keys(m).sort((x,y)=>m[y].n-m[x].n).map(k=>[k,m[k].n,P(m[k].e/m[k].n,2),
          P(m[k].s/m[k].n,2),N2(m[k].s/m[k].n-m[k].e/m[k].n,4)])),
      '편의는 실현에서 추정을 뺀 값이며 양수가 과소추정이다.');
    ap(c,src(ob))}
  const CE=NG.D.irb&&NG.D.irb.censoring;
  if(CE&&CE.length)put(root,'관측중단 현황',
    st(['세그먼트','관측상태','건수','부도시 익스포저'],
      CE.map(x=>[x.segment,x.status,x.n,F.money(x.ead)]),{numeric:false}));
  stages(root,f,f.rows,'LGD',v=>P(v,3));
  irbCards(root,'LGD');
  led(root,'crm_lgd_discount_rate')}

// ════════════════ 10. CCF 추정 ═══════════════════════════════════════
function ccfEstimate(root){
  const f=FR('crm_ccf_estimate');if(!f)return miss(root,'crm_ccf_estimate');
  const i=IX(f);
  lead(root,'상품유형별 CCF 실측과 적용값, 분모 이상치 건수, 추가 보수화 여부를 본다.');
  const nex=f.rows.filter(r=>r[i.extra_conservatism_required]).length;
  const tg=(((NG.D.x_screen_gate||{}).targets||{})['ccf-estimate']||[])[0];
  ap(root,U.kpiRow([
    K('CCF 실현치 (서버 집계)',tg?P(tg.reported,2):'-',tg?tg.korean:T('재계산 대상 아님'),null,'ccf_realised_mean'),
    K('추정 대상',F.int(f.total),T('원장 전량')),
    K('추가 보수화 필요',F.int(nex),null,OK(nex===0))]));
  const c1=put(root,'CCF 추정',
    proj(f,'segment ccf_type observation_design n_facilities n_valid raw_estimate:p2 floor_value:p2 floor_binding final_applied:p2 pd_ead_correlation:n3 extra_conservatism_required',
      null,{rowClass:RC(f.rows,r=>r[i.extra_conservatism_required]?'warn':null)}));
  const sum=k=>f.rows.reduce((a,r)=>a+(r[i[k]]||0),0);
  ap(c1,el('div','meta',T('분모 0 건수')+' '+F.int(sum('n_zero_denominator'))+' · '+T('분모 음수 건수')+' '+F.int(sum('n_negative_denominator'))+' · '+T('제외 건의 기준시 인출액 합계')+' '+F.money(sum('excluded_exposure_amount'))));
  ap(c1,el('div','meta',T('부도후 추가인출 반영처')+' '+OD((f.rows[0]||[])[i.post_default_drawdown_treatment])+' · '+T('자체추정 가능')+' '+OD((f.rows[0]||[])[i.self_estimation_allowed])),src(f));
  const dsg={};f.rows.forEach(r=>{const k=r[i.observation_design]||'-';dsg[k]=(dsg[k]||0)+1});
  const g=el('div','grid');
  ap(g,C.hbars(ent(dsg),{title:T('관측설계별 추정 건수'),money:false,src:f}));
  const b=FR('crm_ccf_backtest');
  if(b){const bi=IX(b);
    ap(g,C.hbars(b.rows.map(r=>({label:r[bi.ccf_type]+' · '+r[bi.grade_band],
      value:(r[bi.ccf_realized_mean]||0)*100,
      sub:T('적용 CCF')+' '+P(r[bi.ccf_applied],1)+' · '+T('편의')+' '+N2(r[bi.bias],4),
      tone:(r[bi.ccf_realized_mean]||0)>(r[bi.ccf_applied]||0)?OK(false):null})),
      {title:T('실측 CCF (%) · 적용값 대비'),money:false,fmt:v=>N2(v,2),src:b}));
    ap(root,g);
    put(root,'CCF 유형·등급별 실측 대 적용',
      proj(b,'ccf_type grade_band n_facilities drawn_at_ref:m undrawn_at_ref:m drawn_at_default:m ccf_realized_mean:p2 ccf_applied:p2 bias:n4 pass_flag',
        {pass_flag:judge},{rowClass:jcls(b)}),
      '판정 임계는 내부기준이며 crm_backtest_criteria 에 있다. 임계가 비면 판정하지 않는다.')}
  else ap(root,g);
  stages(root,f,f.rows,'CCF',v=>P(v,3));
  irbCards(root,'CCF');
  evid(root,['crm_ccf_estimate','crm_facility_drawdown_history','crm_estimation_param'])}

// ════════════════ 11. 회수 할인율 (CAPM) ═════════════════════════════
const CAPM_T=['crm_capm_observation','crm_capm_estimate','crm_lgd_discount_rate','crm_lgd_estimate'];
function capm(root){review(root);sources(root,CAPM_T);
  const e=FR('crm_capm_estimate');if(!e||!e.rows.length)return miss(root,'crm_capm_estimate');
  const ei=IX(e),r=e.rows[0],prem=r[ei.market_premium];
  lead(root,'회수 할인율의 관측·추정·승인·적용이다. 규정이 수준과 산식을 주지 않으므로 승인 기록이 함께 있어야 한다.');
  ap(root,U.kpiRow([
    K('무위험이자율',P(r[ei.riskfree_annual],4),T('관측 만기수익률 평균')),
    K('시장수익률(적용)',P(r[ei.market_return_applied],4),OD(r[ei.market_return_source])),
    K('시장위험프리미엄',P(prem,4),T('시장수익률에서 무위험이자율을 뺀 값'),
      (prem!=null&&prem<=0)?BAD(true):null),
    K('베타',N2(r[ei.beta],4),T('베타 표준오차')+' '+N2(r[ei.beta_stderr],4)),
    K('자기자본비용',P(r[ei.cost_of_equity],4),OD(r[ei.ke_status]),
      r[ei.cost_of_equity]==null?BAD(true):null)]));
  const o=FR('crm_capm_observation');
  if(o){const oi=IX(o);
    const pts=o.rows.filter(x=>x[oi.excess_market_return]!=null&&x[oi.excess_bank_return]!=null)
      .map(x=>({x:x[oi.excess_market_return]*100,y:x[oi.excess_bank_return]*100,label:String(x[oi.period])}));
    const np=pts.length,c=card('베타 회귀 (초과수익률 산점과 적합선)');
    ap(c,C.scatterXY(pts,{xLabel:T('시장 초과수익률 (백분율)'),yLabel:T('은행주 초과수익률 (백분율)'),
      fit:{slope:r[ei.beta],intercept:(r[ei.alpha]||0)*100},fmtX:v=>N2(v,1),fmtY:v=>N2(v,1)}));
    ap(c,proj(e,'n_observations estimation_period beta:n4 beta_stderr:n4 beta_tstat:n2 beta_r2:n4 alpha:n6',null));
    ap(c,el('div','meta',TF('파선은 추정 원장의 절편과 기울기로 그은 적합선이다. 관측 {n}개월.',{n:np})),
      U.truncBadge(o),src(o));
    ap(root,c)}
  const c3=card('근거와 산출 상태');
  ap(c3,proj(e,'rf_source beta_source market_return_source ke_status evidence_status citation reference_note',null));
  ap(c3,U.note(T('이 베타는 합성 관측으로 낸 추정치다. 은행 주가 계열이 원장에 없어 합성 표본으로 회귀했으며 실측 베타로 읽지 않는다.'),'synthetic'));
  ap(root,c3);
  const d=FR('crm_lgd_discount_rate');
  if(d){const di=IX(d);
    put(root,'회수유형별 할인율 (승인 기록 포함)',
      proj(d,'segment recovery_scope discount_rate:p4 basis evidence_status input_source approved_by approval_date',
        null,{rowClass:RC(d.rows,x=>String(x[di.approved_by]||'').indexOf('미승인')>=0?'warn':null)}));
    const c5=put(root,'타행 참고치와의 대비',
      st(['세그먼트','회수유형','적용 할인율','참고치','차이'],
        d.rows.map(x=>[x[di.segment],x[di.recovery_scope],P(x[di.discount_rate],4),
          P(x[di.reference_value],4),
          (x[di.discount_rate]==null||x[di.reference_value]==null)?'-'
            :N2((x[di.discount_rate]-x[di.reference_value])*100,4)])));
    ap(c5,el('div','meta',T('참고치 근거')+': '+OD((d.rows[0]||[])[di.reference_citation])))}
  const L=FR('crm_lgd_estimate');
  if(L){const li=IX(L);
    put(root,'할인율 적용 결과 (LGD 산출 상태)',
      proj(L,'segment discount_rate:p4 discount_rate_status raw_estimate:p2 status',null,
        {rowClass:RC(L.rows,x=>String(x[li.status]).indexOf('산출불가')>=0?'bad':null)}),
      '할인율이 비면 그 세그먼트 LGD 를 산출불가로 남긴다. 엔진이 조용히 기본값을 쓰지 않는다.')}
  evid(root,CAPM_T)}

// ════════════════ 12. 부도자산 LGD ═══════════════════════════════════
function defaultedLgd(root){
  const f=FR('crm_defaulted_lgd');if(!f)return miss(root,'crm_defaulted_lgd');
  const i=IX(f);
  lead(root,'부도자산의 예상손실 최적추정치(ELBE)와 부도자산 LGD 다. 충당금·상각 합계보다 작으면 입증 대상이 된다.');
  ap(root,U.kpiRow(f.rows.map(r=>K('예상손실 최적추정치',P(r[i.elbe],2),
    r[i.segment]+' · '+T('부도상태 건수')+' '+F.int(r[i.n_defaulted_open]),
    r[i.justification_required]?BAD(true):(r[i.lgd_in_default]==null?NRUN():null)))));
  const c1=put(root,'ELBE 와 개별충당금 · 부분상각 비교',
    proj(f,'segment n_defaulted_open elbe:p2 elbe_amount:m specific_provision:m partial_writeoff:m shortfall:m justification_required status',
      null,{rowClass:RC(f.rows,r=>r[i.justification_required]?'bad':null)}));
  ap(c1,el('div','meta',T('충당금 자료가 원장에 없으면 판정하지 않고 미판정으로 둔다.')),src(f));
  const ob=FR('crm_default_observation');
  if(ob){const oi=IX(ob);
    const op=ob.rows.filter(r=>r[oi.workout_complete]===false),no=op.length,m={};
    op.forEach(r=>{const k=r[oi.months_since_default];m[k]=(m[k]||0)+1});
    const ks=Object.keys(m).map(Number).sort((x,y)=>x-y);
    if(ks.length){const c=card('미종결 부도의 경과월 분포');
      ap(c,C.bars(ks.map(k=>({label:TF('{n}개월',{n:k}),value:m[k]})),{fmt:v=>F.int(v)}));
      ap(c,el('div','meta',TF('미종결 부도관측 {n}건의 부도 후 경과월 분포다.',{n:no})));
      ap(c,el('div','meta',T('산출방법')+': '+OD((f.rows[0]||[])[i.elbe_method])));
      ap(c,U.note(T('경과월별 BEEL 곡선과 분모 두 방식 대비는 BEEL·PLGD 화면에 있다.'),'neutral'),src(ob));
      ap(root,c)}
    put(root,'정상화(cure) 인식',
      st(['관측상태','건수','평균 실현 LGD'],
        uniq(ob.rows.map(r=>r[oi.censoring_status])).map(s=>{
          const u=ob.rows.filter(r=>r[oi.censoring_status]===s),n=u.length;
          return [s,n,P(u.reduce((a,r)=>a+(r[oi.lgd_realized]||0),0)/(n||1),2)]})))}
  put(root,'PLGD 는 어디에 있나',null,
    'PLGD 는 BEEL 분포의 극단값이며 곡선·분모 판정과 신뢰수준 민감도는 BEEL·PLGD 화면이 낸다. 신뢰수준이 승인 전이라 값은 비어 있다.')}

// ════════════════ 13. BEEL·PLGD ══════════════════════════════════════
const BEEL_T=['crm_beel_curve','crm_plgd','crm_plgd_sensitivity','crm_defaulted_lgd','crm_lgd_discount_rate'];
function beelPlgd(root){
  const c0=FR('crm_beel_curve'),p=FR('crm_plgd');
  if(!c0||!p)return miss(root,'crm_beel_curve');
  const ci=IX(c0),pi=IX(p),p0=p.rows[0],app=c0.rows.filter(x=>x[ci.is_applied_denominator]);
  lead(root,'경과월별 예상손실 최적추정치(BEEL) 곡선과 그 극단값인 PLGD 다. 조문 대응은 근거 칸에 있다.');
  ap(root,U.kpiRow([
    K('적용 분모',app.length?String(app[0][ci.beel_denominator]):'-',T('경과월과 곡선의 순위상관 부호로 판정')),
    K('DSF 반영형태',p0?OD(p0[pi.dsf_form]):'-',T('분포 분위수 대 평균의 변동계수 비교')),
    K('신뢰수준',p0?N2(p0[pi.confidence_q],2):'-',p0?OD(p0[pi.confidence_q_status]):'-',
      (p0&&p0[pi.confidence_q]==null)?NRUN():null),
    K('PLGD 산출 상태',p0?OD(p0[pi.status]):'-',T('값이 비면 신뢰수준이 승인되지 않은 것'),
      (p0&&p0[pi.plgd]==null)?BAD(true):null)]));
  const sg=uniq(c0.rows.map(x=>x[ci.segment])).sort();let pk=sg[0];
  const cc=card('경과월별 BEEL 곡선 (적용 분모)'),pane=el('div');
  ap(cc,bar(v=>{pk=v;draw()},sg),pane,src(c0));ap(root,cc);
  function draw(){pane.innerHTML='';
    const u=c0.rows.filter(x=>x[ci.segment]===pk&&x[ci.is_applied_denominator]&&x[ci.beel_mean]!=null)
      .slice().sort((x,y)=>x[ci.months_since_default]-y[ci.months_since_default]);
    if(!u.length){ap(pane,U.note(T('이 세그먼트의 적용 분모 곡선이 산출되지 않았다.'),NRUN()));return}
    const z=u[u.length-1];
    ap(pane,C.areaLine(u.map(x=>x[ci.beel_mean]*100),{label:T('BEEL 평균 (백분율)'),
      dates:u.map(x=>x[ci.months_since_default]),fmt:v=>N2(v,2),title:T('경과월별 BEEL 평균')}));
    ap(pane,el('div','meta',T('단조성 판정')+' '+OD(z[ci.monotonicity_verdict])+' · '+
      T('스피어만 상관')+' '+N2(z[ci.monotonicity_rho],4)+' · '+
      T('관측중단 처리 차이')+' '+N2(z[ci.censoring_impact],4)));
}
  draw();
  const key={};
  c0.rows.forEach(x=>{const k=x[ci.segment]+'|'+x[ci.beel_denominator],c=key[k];
    if(!c||x[ci.months_since_default]>c[ci.months_since_default])key[k]=x});
  const kr=Object.keys(key).sort().map(k=>key[k]);
  put(root,'분모 두 방식 대비',
    proj(c0,'segment beel_denominator is_applied_denominator monotonicity_verdict monotonicity_rho:n4 monotonicity_pvalue:n4 beel_mean:p2',
      null,{rows:kr,rowClass:RC(kr,x=>x[ci.is_applied_denominator]?'good':null)}),
    '분모가 부도시익스포저면 곡선이 경과월에 따라 올라가고 잔여익스포저면 분모도 줄어 무너지는 세그먼트가 생긴다. 판정은 원장 컬럼이다.');
  const S=FR('crm_plgd_sensitivity');
  if(S&&S.rows.length){const si=IX(S),c3=led(root,'crm_plgd_sensitivity');
    ap(c3,el('div','meta',T('충당금 산식')+': '+OD(S.rows[0][si.provision_basis])));
    ap(c3,U.note(T('어느 줄도 승인된 값이 아니다. 꼬리 관측이 적은 줄은 분위수가 표본 밖 순서통계량에 기댄다.'),'warn'))}
  const c4=put(root,'PLGD 대 ELBE',
    proj(p,'segment ead_at_default_open:m elbe:p2 plgd:p2 unexpected_loss_addon:n4 lgd_in_default:p2 dsf:n4 dsf_form status',
      null,{rowClass:RC(p.rows,x=>String(x[pi.status]).indexOf('산출불가')>=0?'warn':null)}));
  ap(c4,el('div','meta',T('부도자산 적용 LGD 의 근거')+': '+OD(p0?p0[pi.lgd_in_default_basis]:null)));
  const nf=p.rows.filter(x=>x[pi.insufficient_sample]).length;
  if(nf)ap(c4,U.note(TF('꼬리 표본이 모자란 세그먼트가 {n}건이다. 그 분위수는 관측에 기대지 않는다.',{n:nf}),'warn'));
  ap(c4,src(p));
  put(root,'개별충당금 · 부분상각 비교',
    proj(p,'segment elbe_amount:m elbe_amount_alt_denominator:m specific_provision:m partial_writeoff:m shortfall:m justification_required justification_ref',
      null,{rowClass:RC(p.rows,x=>x[pi.justification_required]==null?'warn':(x[pi.justification_required]?'bad':null))}));
  evid(root,BEEL_T)}

// ════════════════ 14. 모형 거버넌스 ══════════════════════════════════
function irbGov(root){
  lead(root,'실적 부도율과 추정 PD 의 대조, LGD 실적 대비, 대표성 지표, 점검 이력이다. 합격 임계는 내부기준이다.');
  const cr=led(root,'crm_backtest_criteria');
  if(cr)ap(cr,U.note(T('규정이 정한 값이 아니라 내부기준이다. 임계가 빈 항목은 미판정으로 둔다.'),'warn'));
  const b=FR('crm_backtest_result');
  if(b){const i=IX(b);
    put(root,'사후검증 (적용값 · 실측값 · 허용범위)',
      proj(b,'parameter segment grade backtest_year n_observations n_defaults estimated_value:n5 realised_value:n5 inside_range range_upper:n5 test_pass',
        {test_pass:judge},{rowClass:RC(b.rows,r=>r[i.inside_range]==null?'warn':(r[i.inside_range]?null:'bad'))}),
      '적용 추정값·실측값·허용범위 세 값을 한 행에서 본다.');
    const pd=b.rows.filter(r=>r[i.parameter]==='PD'&&r[i.grade]);
    if(pd.length)ap(root,C.hbars(pd.map(r=>({label:r[i.grade]+' · '+r[i.backtest_year],
      value:(r[i.realised_value]||0)*100,sub:T('추정치')+' '+P(r[i.estimated_value],3),
      tone:r[i.inside_range]===false?BAD(true):null})),
      {title:T('등급별 실측 부도율 (%) · 추정 대비'),money:false,fmt:v=>N2(v,3),src:b}))}
  const lb=FR('crm_lgd_backtest');
  if(lb)put(root,'LGD 사후검증',
    proj(lb,'segment_axis segment_value n_defaults n_censored lgd_estimated_mean:p2 lgd_realized_mean:p2 bias:n4 mae:n4 ci_low:n4 ci_high:n4 pass_flag',
      {pass_flag:judge},{rowClass:jcls(lb)}),
    '관측중단 처리규칙은 원장 컬럼이며 제외 건수를 함께 남긴다.');
  const rp=FR('crm_representativeness');
  if(rp){const i=IX(rp);
    const c=led(root,'crm_representativeness',{rowClass:RC(rp.rows,r=>r[i.judgment]==null?'warn':null)});
    ap(c,el('div','meta',T('임계가 승인 전이라 판정 칸이 비어 있다. 판정하지 않은 것을 문제 없음으로 두지 않는다.')))}
  led(root,'crm_sample_representativeness');
  const gv=FR('crm_model_governance');
  if(gv){const i=IX(gv);
    const c=led(root,'crm_model_governance',{rowClass:RC(gv.rows,r=>r[i.review_overdue]?'bad':null)});
    ap(c,el('div','meta',OD((gv.rows[0]||[])[i.citation])))}}

// ════════════════ 15. LGD·EAD 실측검증 ═══════════════════════════════
function lgdEadBt(root){
  const lb=FR('crm_lgd_backtest');if(!lb)return miss(root,'crm_lgd_backtest');
  const i=IX(lb);
  lead(root,'추정 LGD·CCF 와 실현값의 대조다. 편의와 관측중단 건수는 3선 재계산 대상이다.');
  const tg=((NG.D.x_screen_gate||{}).targets||{})['lgd-ead-backtest']||[];
  const tof=k=>tg.filter(t=>t.target===k)[0];
  const tb=tof('lgd_backtest_bias'),tc=tof('lgd_backtest_n_censored');
  let nf=0,nu=0;
  lb.rows.forEach(r=>{if(r[i.pass_flag]===false)nf++;if(r[i.pass_flag]==null)nu++});
  ap(root,U.kpiRow([
    K('LGD 편의 (서버 집계)',tb?N2(tb.reported,5):'-',tb?tb.korean:null,null,'lgd_backtest_bias'),
    K('관측중단 건수 (서버 집계)',tc?F.int(tc.reported):'-',tc?tc.korean:null,null,'lgd_backtest_n_censored'),
    K('LGD 검증 구간',F.int(lb.total),T('원장 전량')),
    K('미통과',F.int(nf),null,BAD(nf>0)),
    K('미판정',F.int(nu),null,nu?NRUN():OK(true))]));
  const ob=FR('crm_default_observation');
  if(ob){const oi=IX(ob);
    const pts=ob.rows.filter(r=>r[oi.lgd_realized]!=null&&r[oi.lgd_estimated]!=null)
      .map(r=>({x:r[oi.lgd_estimated],y:r[oi.lgd_realized],
        label:r[oi.exposure_id]+' · '+(r[oi.collateral_type]||T('(무담보)')),
        tone:r[oi.censoring_status]!=='회수종료'?'warn':null}));
    const np=pts.length,c=card('추정 LGD 대 실현 LGD (부도건별)');
    ap(c,C.scatter45(pts,{xLabel:T('추정 LGD'),yLabel:T('실현 LGD')}));
    ap(c,el('div','meta',TF('대각선 위쪽 점이 과소추정 건이며 주의 색은 미종결 관측이다. 관측 {n}건.',{n:np})),src(ob));
    ap(root,c)}
  const g=el('div','grid');
  ap(g,C.hbars(lb.rows.map(r=>({label:r[i.segment_axis]+' · '+r[i.segment_value],
    value:(r[i.bias]||0)*100,sub:T('평균절대오차')+' '+N2(r[i.mae],4),
    tone:r[i.pass_flag]==null?NRUN():(r[i.pass_flag]?null:BAD(true))})),
    {title:T('구간별 편의 (%p, 실현에서 추정을 뺀 값)'),money:false,fmt:v=>N2(v,2),src:lb}));
  const cb=FR('crm_ccf_backtest');
  if(cb){const bi=IX(cb);
    ap(g,C.hbars(cb.rows.map(r=>({label:r[bi.ccf_type]+' · '+r[bi.grade_band],
      value:(r[bi.ccf_realized_mean]||0)*100,sub:T('적용 CCF')+' '+P(r[bi.ccf_applied],1),
      tone:r[bi.pass_flag]===false?BAD(true):null})),
      {title:T('CCF 유형·등급별 실측 (%)'),money:false,fmt:v=>N2(v,2),src:cb}))}
  ap(root,g);
  put(root,'LGD 실측 검증',
    proj(lb,'segment_axis segment_value n_defaults n_censored lgd_estimated_mean:p2 lgd_realized_mean:p2 bias:n4 mae:n4 p_value:n4 pass_flag',
      {pass_flag:judge},{rowClass:jcls(lb)}),
    '판정 임계는 내부기준(crm_backtest_criteria)이며 규정값이 아니다.');
  if(cb)put(root,'CCF 실측 검증',
    proj(cb,'ccf_type grade_band n_facilities drawn_at_ref:m undrawn_at_ref:m drawn_at_default:m ccf_realized_mean:p2 ccf_applied:p2 bias:n4 pass_flag',
      {pass_flag:judge},{rowClass:jcls(cb)}),
    '관측중단 건은 검정 표본에서 빠지고 그 건수는 원장에 남는다.')}

// ════════════════ 16. 행동모형 추정 ══════════════════════════════════
const BHV_T=['alm_behaviour_model','alm_behaviour_backtest','alm_prepay_observation',
  'alm_early_redemption_observation','alm_prepay_scurve_param','alm_behaviour_param',
  'alm_behaviour_scenario_mult'];
function bhvModel(root){
  const f=FR('alm_behaviour_model');if(!f)return miss(root,'alm_behaviour_model');
  const i=IX(f);
  lead(root,'조기상환율과 중도해지율 모형의 추정 결과다. 수렴하지 못한 포트폴리오는 모수가 비어 있다.');
  let cv=0,fl=0,hd=0;
  f.rows.forEach(r=>{if(r[i.converged]===true)cv++;if(r[i.converged]===false)fl++;
    if(r[i.headline_estimate]!=null)hd++});
  ap(root,U.kpiRow([K('추정 대상',F.int(f.total),T('원장 전량')),
    K('수렴',F.int(cv),null,OK(cv>0)),K('수렴 실패',F.int(fl),null,BAD(fl>0)),
    K('헤드라인 채택',F.int(hd))]));
  const c1=put(root,'포트폴리오별 적합 모수',
    proj(f,'model portfolio_id estimation_method functional_form n_obs converged r_squared:n4 fit_status headline_estimate:n5 message evidence_status',
      null,{rowClass:RC(f.rows,r=>r[i.converged]===false?'bad':(r[i.converged]==null?'warn':null))}));
  ap(c1,src(f));
  const po=FR('alm_prepay_observation');
  if(po){const oi=IX(po),pf=uniq(po.rows.map(r=>r[oi.portfolio_id]));
    let pk=pf[0];const c=card('조기상환 관측'),pane=el('div');
    ap(c,bar(v=>{pk=v;draw()},pf),pane,src(po));ap(root,c);
    function draw(){pane.innerHTML='';
      const u=po.rows.filter(r=>r[oi.portfolio_id]===pk);
      ap(pane,C.scatterXY(u.map(r=>({x:r[oi.refi_incentive_bp],
        y:(r[oi.observed_cpr_annual]||0)*100,label:String(r[oi.obs_month])})),
        {xLabel:T('차환유인 (bp)'),yLabel:T('관측 CPR (%)'),fmtX:v=>N2(v,0),fmtY:v=>N2(v,1),
         title:T('차환유인 대 조기상환율'),
         note:T('차환유인이 커질수록 조기상환이 오르는 S 자 형태를 확인한다.')}));
      ap(pane,C.scatterXY(u.map(r=>({x:r[oi.wa_seasoning_months],
        y:(r[oi.observed_cpr_annual]||0)*100,label:String(r[oi.obs_month])})),
        {xLabel:T('가중평균 경과월수'),yLabel:T('관측 CPR (%)'),fmtX:v=>N2(v,0),fmtY:v=>N2(v,1),
         title:T('경과효과 램프'),note:T('대출이 오래될수록 조기상환이 늘어나는 구간을 본다.')}))}
    draw()}
  const eo=FR('alm_early_redemption_observation');
  if(eo){const ei=IX(eo),c=card('중도해지 관측');
    ap(c,C.scatterXY(eo.rows.map(r=>({x:r[ei.rate_gap_bp],y:(r[ei.observed_tdrr_annual]||0)*100,
      label:r[ei.portfolio_id]+' · '+r[ei.obs_month]})),
      {xLabel:T('금리차 (bp)'),yLabel:T('관측 해지율 (%)'),fmtX:v=>N2(v,0),fmtY:v=>N2(v,1),
       title:T('금리차 대 중도해지율'),
       note:T('위약금률이 높은 상품은 같은 금리차에서도 해지가 적다.')}));
    ap(c,src(eo));ap(root,c)}
  const sp=FR('alm_prepay_scurve_param');
  led(root,'alm_prepay_scurve_param');led(root,'alm_behaviour_scenario_mult');
  evid(root,BHV_T)}

// ════════════════ 17. 비만기성예금 코어 ══════════════════════════════
function nmdCore(root){
  const f=FR('alm_nmd_core_method_compare');if(!f)return miss(root,'alm_nmd_core_method_compare');
  const i=IX(f);
  lead(root,'코어비율을 세 추정방법으로 나란히 낸 결과다. 상한이 문 자리와 방법별 ΔEVE 영향을 본다.');
  const c1=put(root,'추정방법별 코어비율과 평균만기',
    proj(f,'nmd_category method is_headline base_balance:m core_ratio_raw:p2 core_ratio:p2 core_ratio_cap:p2 core_cap_binding avg_maturity_years:n2 maturity_cap_binding core_amount:m',
      null,{rowClass:RC(f.rows,r=>(r[i.core_cap_binding]||r[i.maturity_cap_binding])?'warn':null)}));
  ap(c1,el('div','meta',T('상한이 문 행은 원시추정이 상한을 넘어 상한으로 잘린 것이다.')),src(f));
  const ct=uniq(f.rows.map(r=>r[i.nmd_category])),mt=uniq(f.rows.map(r=>r[i.method]));
  ap(root,C.stackBars(mt.map(m=>({name:m,values:ct.map(c=>{
    const r=f.rows.filter(x=>x[i.nmd_category]===c&&x[i.method]===m)[0];
    return r?(r[i.core_ratio]||0)*100:0})})),ct,
    {title:T('방법별 코어비율 (%)'),fmt:v=>N2(v,1),
     note:T('같은 범주를 세 방법으로 추정한 값이며 누적이 아니다.')}));
  const ev=f.rows.filter(r=>r[i.delta_eve_proxy_krw]!=null);
  if(ev.length)ap(root,C.hbars(ev.map(r=>({label:r[i.nmd_category]+' · '+r[i.method],
    value:r[i.delta_eve_proxy_krw],
    sub:T('코어비율(상한 후)')+' '+P(r[i.core_ratio],1),
    tone:r[i.is_headline]?null:OK(false)})),
    {title:T('방법별 ΔEVE 영향 (동일 충격 기준)'),src:f}));
  const h=FR('alm_nmd_balance_history');
  if(h){const hi=IX(h),cs=uniq(h.rows.map(r=>r[hi.nmd_category]));
    let pk=cs[0];const c=card('잔액 관측과 전가율'),pane=el('div');
    ap(c,bar(v=>{pk=v;draw()},cs),pane,src(h));ap(root,c);
    function draw(){pane.innerHTML='';
      const u=h.rows.filter(r=>r[hi.nmd_category]===pk).slice()
        .sort((x,y)=>x[hi.obs_seq]-y[hi.obs_seq]),nm=u.length;
      ap(pane,C.areaLine(u.map(r=>r[hi.avg_balance]),{label:T('월중평잔'),
        dates:u.map(r=>r[hi.obs_month]),title:T('월중평잔 관측')}));
      const pt=u.filter(r=>r[hi.observed_pass_through]!=null),np=pt.length;
      if(np)ap(pane,C.areaLine(pt.map(r=>(r[hi.observed_pass_through]||0)*100),
        {label:T('관측 전가율 (%)'),height:150,fmt:v=>N2(v,2),
         dates:pt.map(r=>r[hi.obs_month]),title:T('관측 전가율')}));
      else ap(pane,U.note(T('이 범주는 전가율 관측이 원장에 없다.'),NRUN()));
      ap(pane,el('div','meta',TF('관측 {n}개월 · 전가율 관측 {p}개월',{n:nm,p:np})))}
    draw()}
  led(root,'alm_nmd_param');led(root,'kr_nmd_category');led(root,'alm_nii_result')}

// ════════════════ 18. 행동모형 백테스트 ══════════════════════════════
function bhvBacktest(root){
  const f=FR('alm_behaviour_backtest');if(!f)return miss(root,'alm_behaviour_backtest');
  const i=IX(f);
  lead(root,'표본외 실적 대비 예측이다. 합격 임계는 내부기준이며 임계가 비면 판정하지 않고 보류로 둔다.');
  let ot=0,bd=0,av=0;
  f.rows.forEach(r=>{if(r[i.is_out_of_time])ot++;
    if(String(r[i.judgement]).indexOf('미통과')>=0)bd++;if(r[i.approved_by])av++});
  ap(root,U.kpiRow([K('검증 대상',F.int(f.total),T('원장 전량')),
    K('표본외 검증',F.int(ot)),K('미통과',F.int(bd),null,BAD(bd>0)),
    K('승인 완료',F.int(av),null,av?OK(true):NRUN())]));
  const c1=led(root,'alm_behaviour_backtest',
    {rowClass:RC(f.rows,r=>String(r[i.judgement]).indexOf('미통과')>=0?'bad':'warn')});
  ap(c1,U.note(T('합격 임계는 내부기준이며 원장의 임계 근거 컬럼이 그 근거를 담는다.'),'warn'));
  const g=el('div','grid');
  ap(g,C.hbars(f.rows.map(r=>({label:r[i.model]+' · '+r[i.portfolio_id],value:r[i.mae_pp]||0,
    sub:T('표본내 MAE')+' '+N2(r[i.in_sample_mae_pp],3)+' · '+T('판정 임계')+' '+N2(r[i.threshold_mae_pp],3),
    tone:(r[i.threshold_mae_pp]!=null&&r[i.mae_pp]>r[i.threshold_mae_pp])?BAD(true):NRUN()})),
    {title:T('표본외 MAE (%p)'),money:false,fmt:v=>N2(v,4),src:f}));
  ap(g,C.hbars(f.rows.map(r=>({label:r[i.model]+' · '+r[i.portfolio_id],value:r[i.bias_pp]||0,
    sub:T('실적치 평균')+' '+N2(r[i.mean_actual_pp],3)+' · '+T('예측치 평균')+' '+N2(r[i.mean_predicted_pp],3),
    tone:(r[i.bias_pp]||0)<0?OK(false):null})),
    {title:T('편의 (%p, 실적에서 예측을 뺀 값)'),money:false,fmt:v=>N2(v,4),src:f}));
  ap(root,g);
}

// ── registration (group/sub/title equal the registry entry) ──────────
function S(id,sub,title,build,summary){
  NG.screen(id,{group:'모형',sub:sub,title:title,build:build,summary:summary})}
S('model-inventory',null,'모형 인벤토리',inventory,invSum);
S('validation-schedule','모형 인벤토리','검증 일정',schedule,schedSum);
S('model-risk','모형 인벤토리','모형리스크',modelRisk,riskSum);
S('model-lifecycle','모형 인벤토리','모형 수명주기',lifecycle);
S('performance','신용모형','변별력·안정성',performance,perfSum);
S('calibration','신용모형','등급 보정',calibration,calSum);
S('migration','신용모형','등급 전이',migration,migSum);
S('pd-estimate','내부등급법 추정','PD 추정',pdEstimate);
S('lgd-estimate','내부등급법 추정','LGD 추정',lgdEstimate);
S('ccf-estimate','내부등급법 추정','CCF 추정',ccfEstimate);
S('capm-discount','내부등급법 추정','회수 할인율',capm);
S('defaulted-lgd','내부등급법 추정','부도자산 LGD',defaultedLgd);
S('beel-plgd','내부등급법 추정','BEEL·PLGD',beelPlgd);
S('irb-governance','내부등급법 추정','모형 거버넌스',irbGov);
S('lgd-ead-backtest','내부등급법 추정','LGD·EAD 실측검증',lgdEadBt);
S('behaviour-model','고객행동모형','행동모형 추정',bhvModel);
S('nmd-core','고객행동모형','비만기성예금 코어',nmdCore);
S('behaviour-backtest','고객행동모형','행동모형 백테스트',bhvBacktest);
})();
