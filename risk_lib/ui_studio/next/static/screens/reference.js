/* screens/reference.js: (참고) 그룹 1화면 (상업성). */
/* 규칙 (설계 사양 2.11·5·6장, 수용기준 A8·A12·A21): */
/* - 이 화면은 사업성 산출이다. 규제 산출물이 아니므로 제출 지문에도, 3선 */
/*   재계산 범위에도 들어가지 않는다. 그 경계를 첫 문단에 적는다. */
/* - 모든 금액은 D.commercial 의 프레임 값 그대로다. 화면이 다시 계산하지 */
/*   않고, 표시 총계는 프레임의 total (U.table 이 붙이는 배지) 뿐이다. */
/* - commercial.* 프레임은 table=None 이라 U.table 이 '카탈로그 외 · 엔진 */
/*   산출' 칩을 붙인다. 차트에는 src 를 넘기지 않고 U.srcMeta 를 직접 단다. */
/*   (charts.descOf 가 table 없는 프레임에서 원장명을 비워 찍기 때문이다.) */
/* - 이중계상 판정 색은 x_severity 의 val_check.status 어휘로만 정한다. */
(function(){
'use strict';
const NG=window.NG,U=NG.ui,CH=NG.charts,el=U.el,ap=U.ap,T=NG.T,IX=NG.frame.frameIdx;
/* 표 제목은 요건 코드(COM-00n)를 그대로 달고 다닌다. 코드는 번역하지 않는다. */
const TBL=[['패키지 견적 (COM-002·003·004·005)','quotes'],
  ['ROI 편익 (항목별 1회 계상, COM-007)','roi'],
  ['가정 원장 (COM-001·006)','assumptions'],
  ['GTM Funnel 단계 정의 (COM-008)','funnel']];
/* 차트는 전량 프레임에서만 그린다. 출처 줄은 상자 안에 직접 단다 (프레임에
   원장명이 없어 charts 의 src 경로가 원장명을 비워 찍기 때문이다). */
const CHART=(f,make)=>{
  if(f.shown<f.total)return U.srcMeta(f);
  const node=make();if(node)ap(node,U.srcMeta(f));return node};

function build(root,c){
  const C=c.D.commercial||{},dc=C.double_counting||[],q=C.quotes,r=C.roi;
  U.lead(root,'사업성 산출. 규제 산출물이 아니다. 제출 지문·독립검증 대상에 넣지 않으며 모든 금액은 가정 원장에서 계산으로만 나온다. 전부 합성 가정이며 실제 견적은 계약 가정으로 교체된다.');
  ap(root,
    el('p','meta',T('이 화면의 수치에는 수치 ID가 없다. 계보 드로어와 3선 재계산 범위(RECALC_SCOPE) 배지는 규제 산출물에만 붙는다.')));
  /* COM-007. 같은 가정을 두 편익이 계상하면 목록이 그대로 나온다. */
  ap(root,U.note(dc[0]?T('ROI 이중계상 발견 (COM-007)')+' '+dc.map(NG.text).join(' · ')
    :T('ROI 이중계상 검증 통과. 편익 항목마다 출처 가정이 하나씩이다 (COM-007)'),
    c.tone('val_check.status',dc[0]?'FAIL':'PASS')));
  if(q&&q.rows[0]){
    const i=IX(q),best=q.rows.reduce((a,x)=>x[i.payback_years]<a[i.payback_years]?x:a);
    /* 브라우저에서 고른 값이라 어느 모집단에서 골랐는지 배지로 같이 적는다. */
    ap(root,ap(U.note(c.TF('회수기간 최단 {name} {years}년',
      {name:best[i.name],years:best[i.payback_years]}),'neutral'),' ',U.truncBadge(q)),
      CHART(q,()=>CH.stackBars([{name:q.labels[i.build_cost],values:q.rows.map(x=>x[i.build_cost])},
        {name:q.labels[i.lifecycle_annual],values:q.rows.map(x=>x[i.lifecycle_annual])}],
        q.rows.map(x=>x[i.name]),
        {title:T('패키지별 1년차 대가 구성'),fmt:c.fmt.money,
         note:T('가정 원장에서 계산으로만 나온 금액이며 승인·제출값이 아니다')})));
  }
  if(r&&r.rows[0]){
    const j=IX(r);
    ap(root,CHART(r,()=>CH.bars(r.rows.map(x=>({label:x[j.description],value:x[j.annual_value]})),
      {title:T('ROI 연 편익 (편익 항목별)'),fmt:c.fmt.money,
       note:T('연 편익은 가정 원장의 값을 항목별로 한 번만 계상한 결과다')})));
  }
  TBL.forEach(p=>ap(root,U.table(C[p[1]],{title:p[0]})));
}

NG.screen("commercial",{group:"(참고)",sub:null,title:"상업성",build:build});
})();
