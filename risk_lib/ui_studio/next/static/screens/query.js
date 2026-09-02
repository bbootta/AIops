/* screens/query.js: 조회·컴포저 (정형 조회 · 비정형 UI). */
/* 규칙 (설계 사양 2.3·5장, 수용기준 A2·A7·A8·A12·A13·A14·A21, F15): */
/* - 조회·제안은 engine.js(RY)가 만든다. 화면은 계획·판정을 그리기만 한다. */
/* - 건수는 계획(plan.n_rows)·프레임(total)·서버 객체에서 읽고, 표시 행수를 */
/*   총계로 찍지 않는다. 잘린 프레임은 NG.ui.table/truncBadge 가 배지를 단다. */
/* - 출력 마스킹은 화면 단계에서만 걸리므로(F15) 제외 컬럼 수를 늘 공시한다. */
/* - 문자열은 NG.T/NG.TF 를 지나며 카탈로그는 i18n/ng_query.py 다. */
/*   원장 값·View 명·필드 한글명·계획 ID·지문·AST·차단 사유·엔진 문법 토큰 */
/*   (이상·초과·그리고·기여도·추이·카드·표)은 번역하지 않고 그대로 찍는다. */
/*   조회 문장을 번역하면 엔진이 다시 해석하지 못하기 때문이다. */
/* - 공용 도우미(renderForm·domainBrowser·almEvidence·almSources·judgeGlyph)는 */
/*   shared.js 만 정의한다. 여기서는 NG.shared 로 호출만 한다. */
(function(){
'use strict';
const NG=window.NG,U=NG.ui,CH=NG.charts,FR=NG.frame,el=U.el,ap=U.ap;
const T=NG.T,TF=NG.TF,fmt=NG.fmt,tx=NG.text,ST=U.simpleTable,NO=U.note,PL=U.pill;
/* base.css 가 section{display:none} 을 걸어 두어 펼친 카드는 div 로 만든다. */
function S(t){const c=el('div','card sec');ap(c,el('h3',null,T(t)));return c}
const MT=t=>el('div','meta',t);
/* 엔진 문법 토큰 (engine.js OPERATORS·CONJ·VIZ_KEYWORDS). 번역 대상이 아니다. */
const GT='초과',GE='이상',AND='그리고',VIZ={bar:'기여도',line:'추이',kpi:'카드',table:'표'};
/* 표시 규약: 막대 상위 n개, 카드 n장, 추이 점 n개. 규제값이 아니다. */
const TOPN=10,NKPI=4,NLINE=60,NUNIQ=50;
/* 화면·View 별 입력 문장. 재도색(언어·비상정지·실행 전환) 뒤에도 남는다. */
const MEM={};
const vk=c=>c.id+'|v', qk=(c,v)=>c.id+'|q|'+v.view_id;
/* engine.js 는 const RY 로 선언한다. 전역 렉시컬 바인딩이라 window.RY 에 없고 */
/* ctx.RY 가 null 로 온다. 식별자로 직접 집는다 (선언 전이면 null). */
function eng(c){return c.RY||(typeof RY!=='undefined'?RY:null)}

/* ---- View 와 필드 정책 ------------------------------------------------ */
function views(D){const vm=D.view_meta||{};return Object.keys(vm).map(k=>vm[k])
  .sort((a,b)=>(a.domain+a.view_name)<(b.domain+b.view_name)?-1:1)}
function opts(list,cur){return list.map(v=>({value:v.view_id,
  label:v.domain+' · '+v.view_name,raw:true,selected:v.view_id===cur}))}
function pickView(c,fb){const vm=c.D.view_meta||{},p=c.params.sel,m=MEM[vk(c)];
  const id=(p&&vm[p])?p:((m&&vm[m])?m:((fb&&vm[fb])?fb:Object.keys(vm)[0]));return vm[id]}
function masked(v){return (v.fields||[]).filter(f=>!f.permitted||f.masking!=='none')
  .map(f=>f.field_name)}
function usable(v){return (v.fields||[]).filter(f=>f.permitted&&f.masking==='none'&&f.min_aggregation===1)}
function numOf(fr,list){return !fr?[]:list.filter(f=>{const i=fr.columns.indexOf(f.field_name);
  return i>=0&&fr.rows.some(r=>typeof r[i]==='number')})}
function strOf(fr,list){return !fr?[]:list.filter(f=>{const i=fr.columns.indexOf(f.field_name);
  return i>=0&&fr.rows.some(r=>typeof r[i]==='string')&&spread(fr,i)})}
function spread(fr,i){const s={};let n=0;fr.rows.slice(0,NUNIQ).forEach(r=>{const k=String(r[i]);
  if(!s[k]){s[k]=1;n++}});return n>1}
/* 원장 컬럼 라벨은 카탈로그 값이라 raw 로 넣는다 (번역 금지). */
function col(f,n){const i=f?f.columns.indexOf(n):-1;
  return {key:n,label:i>=0?FR.colLabel(f,i):n,raw:true,phys:n}}
/* 출력 마스킹 (F15): 화면 단계에서만 컬럼을 뺀다. 엔진은 전량을 돌려준다. */
function maskFrame(f,hide){const keep=[];f.columns.forEach((c,i)=>{if(hide.indexOf(c)<0)keep.push(i)});
  if(keep.length===f.columns.length)return f;
  return {table:f.table,columns:keep.map(i=>f.columns[i]),labels:keep.map(i=>(f.labels||[])[i]),
    rows:f.rows.map(r=>keep.map(i=>r[i])),shown:f.shown,total:f.total}}
function maskNote(n){return MT(TF('표시 단계에서 마스킹 컬럼 {n}개를 제외했다. engine.execute 는 전체 컬럼을 반환한다.',{n:n}))}

function viewCard(c,v){
  const D=c.D,vw=(D.data||{}).ui_view,fp=(D.data||{}).ui_field_policy,card=S('조회 대상 View');
  ap(card,ST([col(vw,'view_id'),col(vw,'view_name'),col(vw,'domain'),col(vw,'table_ref'),col(vw,'row_limit')],
    [{view_id:v.view_id,view_name:v.view_name,domain:v.domain,table_ref:v.table_ref,row_limit:v.row_limit}],{}));
  const flds=v.fields||[],nAll=flds.length,nUse=usable(v).length,nMask=masked(v).length;
  ap(card,MT(T('승인 View 마스터')+' ui_view · '+T('필드 권한·마스킹 정책')+' ui_field_policy · '+
    TF('조건 가능 필드 {n}/{N} · 마스킹 필드 {m}',{n:nUse,N:nAll,m:nMask})+' · '+
    TF('행 상한 {n}',{n:v.row_limit})));
  const rows=flds.map(f=>({field_name:f.field_name,korean:f.korean,permitted:f.permitted,
    masking:f.masking,min_aggregation:f.min_aggregation,
    use:NG.shared.judgeGlyph((f.permitted&&f.masking==='none'&&f.min_aggregation===1)?'통과':'미통과')}));
  ap(card,ST([col(fp,'field_name'),col(fp,'korean'),col(fp,'permitted'),col(fp,'masking'),
    col(fp,'min_aggregation'),{key:'use',label:'조건 사용'}],rows,{}));
  ap(card,MT(TF('출처: {table}',{table:'ui_field_policy'})+' · '+TF('전량 {N}행',{N:fp?fp.total:0})));
  return card}
function guardNote(){return NO(T('Read-only · 조건·출력 마스킹')+' · '+
  T('마스킹은 조회 조건에는 엔진이, 출력 컬럼에는 화면만 적용한다. 화면 밖 데이터는 이 가드가 지키지 않는다.'),'warn')}

/* ══════════════ 정형 조회 ═════════════════════════════════════════════ */

/* 예시 문장. 원장(demo_queries)에 있는 것이 먼저 오고, 없는 View 는 필드 정책 */
/* 에서 만든다. 마지막 한 칸은 통제가 실제로 걸리는 차단 시연이다. */
function presets(D,v){
  const out=(D.demo_queries||[]).filter(q=>q.view_id===v.view_id)
    .map(q=>({q:q.utterance,label:q.utterance}));
  const fr=(D.data||{})[v.table_ref],nu=numOf(fr,usable(v));
  if(nu[0])out.push({q:nu[0].korean+' 0 '+GT,label:nu[0].korean+' 0 '+GT});
  if(nu[1]){const s=nu[0].korean+' 0 '+GE+' '+AND+' '+nu[1].korean+' 0 '+GE;out.push({q:s,label:s})}
  const mk=(v.fields||[]).filter(f=>!f.permitted||f.masking!=='none')[0];
  const b=mk?mk.korean:T('전부 다 보여줘');
  out.push({q:b,label:b+' · '+T('차단 시연')});
  return out}

function planCard(pane,c,v,utter){
  const D=c.D,RY=eng(c);pane.innerHTML='';
  const fr=(D.data||{})[v.table_ref];
  const p0=RY.compileQuery(utter,{viewId:v.view_id,asof:D.meta.asof,fields:v.fields||[],
    population:v.view_name});
  const res=fr?RY.execute(p0,fr,v.row_limit):{rows:[],columns:[],plan:p0};
  const p=res.plan,kill=c.killedFor(v.domain),card=el('div','card');
  const sv=[p.intent,p.asof,v.view_name,(p.conditions||[]).map(RY.describe).join(' ∧ ')||'-',p.policy];
  ap(card,ST([{key:'a',label:'01 의도'},{key:'b',label:'02 기준일'},{key:'c',label:'03 모집단'},
    {key:'d',label:'04 조건'},{key:'e',label:'05 정책'}],[sv],{numeric:false}));
  const m=el('div','meta');
  ap(m,TF('조회 지문 {hash} · 계획 {plan}',{hash:p.query_hash,plan:p.plan_id})+' · ',
    PL(kill?T('비상정지 (실행 차단)'):(p.status==='validated'?T('Read-only 실행'):T('차단')),
       kill?'blocked':(p.status==='validated'?'good':'bad')));
  ap(card,m,MT('AST: '+p.ast));
  if(p.block_reason)ap(card,NO(T('차단 사유')+' ('+tx(p.block_reason)+')','bad'));
  if(kill)ap(card,NO(T('Kill Switch가 걸려 있어 신규 조회를 실행하지 않는다. 진행 중이던 결정론적 계산은 완료 후 중단된다.'),'blocked'));
  if(p.status==='validated'&&!kill&&fr){
    const hide=masked(v),nH=hide.length,nS=res.rows.length;
    ap(card,el('h3',null,T('고정 컬럼 결과')+' · '+TF('모집단 {n}건',{n:p.n_rows})));
    ap(card,U.meter('조건 통과 (화면 내 행 기준)',p.n_rows,fr.shown,'neutral'));
    ap(card,U.table(maskFrame({table:fr.table,columns:res.columns,
      labels:res.columns.map(x=>FR.colLabel(fr,fr.columns.indexOf(x))),
      rows:res.rows,shown:nS,total:p.n_rows},hide),{title:null}));
    if(nH)ap(card,maskNote(nH));
    ap(card,MT(fr.shown<fr.total
      ?TF('화면에 실린 {n}행 범위에서 센 건수다. 원장 전량은 {N}행이다.',{n:fr.shown,N:fr.total})
      :TF('원장 전량 {N}행에서 센 건수다.',{N:fr.total})));
  }
  ap(pane,card)}

function structured(root,c){
  const D=c.D,RY=eng(c);
  ap(root,el('p',null,T('문장을 고치면 조회계획이 즉시 다시 만들어진다. 자연어는 승인된 스키마·필드·연산자·권한으로만 번역되며, 인식하지 못한 필드는 차단 사유로 남는다. 화면 열과 레이아웃은 고정이다.')));
  if(!RY){ap(root,NO(T('조회 엔진(engine.js)을 불러오지 못해 이 화면을 그릴 수 없다.'),'bad'));return}
  let v=pickView(c,((D.demo_queries||[])[0]||{}).view_id);
  if(!v){ap(root,NO(T('원장 행 없음'),'warn'));return}
  const card=S('조회 문장'),bar=el('div','toolbar');
  const sel=U.select(opts(views(D),v.view_id),val=>{const vm=D.view_meta||{};if(!vm[val])return;
    v=vm[val];MEM[vk(c)]=val;c.go(c.id,{sel:val},{replace:true});sync();run()});
  const inp=U.input({aria:T('조회 문장'),onInput:()=>{MEM[qk(c,v)]=inp.value;run()}});
  ap(bar,sel,inp);ap(card,bar);
  const chip=el('div'),meta=el('div'),pane=el('div'),info=el('div');
  ap(card,chip,meta);ap(root,card,pane,info);
  function sync(){
    chip.innerHTML='';meta.innerHTML='';info.innerHTML='';
    const ps=presets(D,v),first=ps[0]?ps[0].q:'',keep=MEM[qk(c,v)];
    ap(chip,U.chips(ps.map(x=>({value:x.q,label:x.label,raw:true})),
      val=>{inp.value=val;MEM[qk(c,v)]=val;run()}));
    inp.value=keep!=null?keep:first;inp.placeholder=first;
    ap(meta,MT(T('조회 문장은 engine.js 의 한국어 문법으로 해석한다. 이상·초과·이하·미만·그리고 같은 키워드는 화면 언어를 바꿔도 번역하지 않는다.')));
    ap(info,viewCard(c,v),guardNote())}
  function run(){planCard(pane,c,v,inp.value)}
  sync();run()}

/* ══════════════ 비정형 UI ═════════════════════════════════════════════ */

function prompts(D,v){
  const out=(D.demo_prompts||[]).filter(q=>q.view_id===v.view_id).map(q=>q.prompt);
  const fr=(D.data||{})[v.table_ref],us=usable(v),nu=numOf(fr,us),ct=strOf(fr,us);
  if(nu[0])out.push((ct[0]?ct[0].korean+' ':'')+nu[0].korean+' '+VIZ.bar);
  if(nu[0])out.push(nu[0].korean+' '+VIZ.line);
  if(nu[1])out.push(nu.slice(0,3).map(f=>f.korean).join(' ')+' '+VIZ.kpi);
  if(us[0])out.push(us.slice(0,3).map(f=>f.korean).join(' ')+' '+VIZ.table);
  return out}

/* 블록 격자. 순서는 프롬프트에 나온 대로다 (engine.compose 가 정한다). */
function blocks(box,c,pr,v){
  const D=c.D,fr=(D.data||{})[v.table_ref];
  if(!fr){ap(box,NO(T('원장 행 없음'),'warn'));return}
  const idx=FR.frameIdx(fr),lab=n=>FR.colLabel(fr,idx[n]),hide=masked(v);
  const want=pr.columns||[];
  const cols=want.filter(x=>(x in idx)&&hide.indexOf(x)<0);
  const nHid=want.filter(x=>hide.indexOf(x)>=0).length;
  const okSet=usable(v).map(f=>f.field_name);
  let numCol=cols.filter(x=>fr.rows.some(r=>typeof r[idx[x]]==='number'))[0],fb=false;
  if(!numCol){numCol=fr.columns.filter(x=>okSet.indexOf(x)>=0&&
    fr.rows.some(r=>typeof r[idx[x]]==='number'))[0];if(numCol)fb=true}
  const isLab=x=>x!==numCol&&fr.rows.some(r=>typeof r[idx[x]]==='string')&&spread(fr,idx[x]);
  const labCol=cols.filter(isLab)[0]||fr.columns.filter(isLab)[0];
  let rows=fr.rows.slice();
  if(numCol)rows.sort((a,b)=>(b[idx[numCol]]||0)-(a[idx[numCol]]||0));
  rows=rows.slice(0,pr.row_limit);
  /* 블록은 상한까지 자른 rows 로 그린다. 배지·표본 표기의 기준도 그 행수다. */
  const nRow=rows.length,base={shown:nRow,total:fr.total};
  const mark=nRow<fr.total?TF('표본 {n}/{N}',{n:nRow,N:fr.total}):TF('전량 {N}',{N:fr.total});
  const sub={table:fr.table,columns:cols,labels:cols.map(lab),
    rows:rows.map(r=>cols.map(x=>r[idx[x]])),total:fr.total,shown:nRow};
  const grid=el('div','blocks');
  (pr.blocks||[]).forEach(b=>{
    const viz=b[0],title=b[1],blk=el('div','blk viz-'+viz),head=el('div','blkhead');
    const ttl=el('span',null,title);if(numCol)ttl.title=numCol;
    ap(head,PL(viz),ttl,U.truncBadge(base));ap(blk,head);
    if(fb&&(viz==='bar'||viz==='line'))ap(blk,MT(TF('값 열이 문장에 없어 이 View 의 기본 값 열({col})로 그렸다. 다른 열은 문장에 이름을 적으면 된다.',{col:lab(numCol)})));
    if(viz==='kpi'){
      const g=el('div','grid');
      cols.slice(0,NKPI).forEach(x=>{const j=idx[x];
        const nums=rows.map(r=>r[j]).filter(y=>typeof y==='number'),nN=nums.length;
        if(nN){const sum=nums.reduce((s,y)=>s+y,0),mx=nums.reduce((s,y)=>y>s?y:s,nums[0]);
          ap(g,U.kpi({label:lab(x),raw:true,value:fmt.money(sum),delta:false,
            sub:TF('평균 {avg} · 최대 {max}',{avg:fmt.money(sum/nN),max:fmt.money(mx)})+
              ' · '+TF('{n}건',{n:nN})+' · '+mark}))}
        else ap(g,U.kpi({label:lab(x),raw:true,value:TF('{n}행',{n:nRow}),
          sub:T('건수')+' · '+mark,delta:false}))});
      ap(blk,g);blk.classList.add('viz-kpi')}
    else if(viz==='bar'&&numCol){
      const top=rows.slice(0,TOPN).map((r,i)=>({label:labCol?String(r[idx[labCol]]):'#'+(i+1),
        value:r[idx[numCol]]||0,phys:labCol}));
      if(nRow>TOPN){const rest=rows.slice(TOPN).reduce((s,r)=>s+(r[idx[numCol]]||0),0);
        top.push({label:TF('그 외 {n}건',{n:nRow-TOPN}),value:rest,tone:'warn'})}
      ap(blk,CH.barList(top))}
    else if(viz==='line'&&numCol)
      ap(blk,CH.areaLine(rows.slice(0,NLINE).map(r=>r[idx[numCol]]||0),{label:lab(numCol),title:title}));
    else if(viz==='bar'||viz==='line'){
      ap(blk,NO(TF('숫자 열이 없어 그리지 않는다. 문장에 값 열 이름({cols})을 적으면 그린다.',
        {cols:usable(v).slice(0,3).map(f=>f.korean).join(' · ')}),'warn'));
      blk.classList.add('viz-table')}
    else{ap(blk,U.table(sub,{title:null}));blk.classList.add('viz-table')}
    ap(grid,blk)});
  ap(box,grid);
  if(nHid)ap(box,maskNote(nHid));
  ap(box,MT(TF('원장 {table} · 화면 내 {n}행 / 원장 {N}행 · 정렬 {sort}',{table:fr.table,n:nRow,
    N:fr.total,sort:numCol?lab(numCol)+' · '+T('내림차순'):T('원장 순')})))}

function proposal(pane,c,v,text){
  const RY=eng(c);pane.innerHTML='';
  const pr=RY.compose(text,{viewId:v.view_id,fields:v.fields||[],rowLimit:v.row_limit});
  const st=c.state,app=st.approved||(st.approved={}),hist=st.history||(st.history={});
  const cur=app[v.view_id],done=!!(cur&&cur.proposal_id===pr.proposal_id);
  const kill=c.killedFor(v.domain),card=el('div','card'),g=NG.shared.judgeGlyph;
  const kt=T('Kill Switch가 걸려 있어 미리보기·승인을 실행하지 않는다.');
  ap(card,el('h3',null,pr.proposal_id+' · '+v.view_name));
  ap(card,ST([{key:'a',label:'필드 권한'},{key:'b',label:'스키마·단위'},
    {key:'c',label:'집계 최소단위'},{key:'d',label:'사람 적용승인'}],
    [[g(pr.field_policy_pass?'통과':'미통과'),g(pr.schema_pass?'통과':'미통과'),
      g(pr.aggregation_pass?'통과':'미통과'),g(done?'통과':'미통과')]],{}));
  const m=el('div','meta');ap(m,T('제안 레이아웃 '),el('span','num',pr.layout_text));ap(card,m);
  const hs=hist[v.view_id]||[],acts=el('div','toolbar');
  const box=el('div'),err=el('div','note bad');err.hidden=true;
  const draw=on=>{box.innerHTML='';
    if(kill){ap(box,NO(kt,'blocked'));return}
    if(!pr.all_pass){ap(box,NO(T('정책검증 미통과. 미리보기를 그리지 않는다.'),'warn'));return}
    ap(box,el('h3',null,on?T('승인 적용 화면'):T('미리보기 (운영 반영 전)')));
    blocks(box,c,pr,v)};
  ap(acts,U.button(T('미리보기 생성'),{onClick:()=>{err.hidden=true;draw(false)}}),
    U.button(T('승인 적용'),{primary:true,disabled:!pr.all_pass||kill,title:kill?kt:'',
      onClick:()=>{try{const a=RY.approve(pr,T('리스크관리부장'));
        (hist[v.view_id]=hist[v.view_id]||[]).push(app[v.view_id]||null);
        app[v.view_id]=a;proposal(pane,c,v,text)}
        catch(e){err.textContent=T('승인 거부')+' ('+String(e&&e.message)+')';err.hidden=false}}}),
    U.button('Rollback',{disabled:!hs.length,onClick:()=>{app[v.view_id]=hs.pop()||null;
      proposal(pane,c,v,text)}}));
  ap(card,acts);
  const sm=el('div','meta');
  ap(sm,PL(done?T('승인 적용 화면'):(pr.all_pass?T('미리보기 · 승인 대기'):T('정책 거부')),
    done?'good':(pr.all_pass?'warn':'bad')));
  ap(card,sm);
  const rej=pr.rejected_fields||[];
  if(rej.length)ap(card,NO(T('차단된 열')+' '+rej.join(', ')+' ('+T('미승인 필드는 레이아웃에 세울 수 없다')+')','bad'));
  else if(!pr.aggregation_pass)ap(card,NO(T('집계 최소단위 위반 (마스킹 필드를 행 단위 열로 세울 수 없다)'),'bad'));
  else if(!pr.schema_pass)ap(card,NO(T('승인된 열을 하나도 짚지 못했다. 아래 사용 가능한 열의 이름을 문장에 포함할 것'),'warn'));
  ap(card,err,box);ap(pane,card);draw(done)}

function adaptive(root,c){
  const D=c.D,RY=eng(c);
  ap(root,el('p',null,T('프롬프트를 고치면 레이아웃 제안이 즉시 바뀐다. 프롬프트는 UI 구성안만 만들 뿐 승인되지 않은 필드, 행 수준 개인정보, 규제산출 변경, 판단 확정은 하지 않는다. 세 검증을 모두 통과해야 사람이 승인할 수 있고, 승인 전에는 화면에 반영되지 않는다.')));
  if(!RY){ap(root,NO(T('조회 엔진(engine.js)을 불러오지 못해 이 화면을 그릴 수 없다.'),'bad'));return}
  let v=pickView(c,((D.demo_prompts||[])[0]||{}).view_id);
  if(!v){ap(root,NO(T('원장 행 없음'),'warn'));return}
  const card=S('프롬프트'),bar=el('div','toolbar');
  const sel=U.select(opts(views(D),v.view_id),val=>{const vm=D.view_meta||{};if(!vm[val])return;
    v=vm[val];MEM[vk(c)]=val;c.go(c.id,{sel:val},{replace:true});sync();run()});
  const ta=U.input({multiline:true,aria:T('프롬프트'),onInput:()=>{MEM[qk(c,v)]=ta.value;run()}});
  ta.rows=2;ap(bar,sel,ta);ap(card,bar);
  const chip=el('div'),meta=el('div'),pane=el('div'),info=el('div');
  ap(card,chip,meta);ap(root,card,pane,info);
  function sync(){
    chip.innerHTML='';meta.innerHTML='';info.innerHTML='';
    const ps=prompts(D,v),first=ps[0]||'',keep=MEM[qk(c,v)];
    ap(chip,U.chips(ps.map(x=>({value:x,label:x,raw:true})),
      val=>{ta.value=val;MEM[qk(c,v)]=val;run()}));
    ta.value=keep!=null?keep:first;ta.placeholder=first;
    ap(meta,MT(T('사용 가능한 열')+' '+usable(v).map(f=>f.korean).join(' · ')),
      MT(T('승인 View 마스터')+' ui_view · '+T('필드 권한·마스킹 정책')+' ui_field_policy · '+
        T('프롬프트는 engine.js 의 한국어 문법으로 해석한다. 기여도·추이·카드·표 같은 블록 키워드는 화면 언어를 바꿔도 번역하지 않는다.')));
    ap(info,viewCard(c,v),
      NO(T('승인자는 화면 가정값이며 원장에서 오지 않는다. 승인 상태는 실행(기관·기준일)마다 따로 남고 어느 원장에도 쓰지 않는다.'),'warn'),
      guardNote())}
  function run(){proposal(pane,c,v,ta.value)}
  sync();run()}

NG.screen("structured-query",{group:"조회·컴포저",sub:null,title:"정형 조회",build:structured});
NG.screen("adaptive-ui",{group:"조회·컴포저",sub:null,title:"비정형 UI",build:adaptive});
})();
