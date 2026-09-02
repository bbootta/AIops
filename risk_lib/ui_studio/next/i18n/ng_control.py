"""통제센터 화면 모듈(screens/control.js)의 문자열 카탈로그.

콕핏·의사결정 큐·마감 워크플로·시뮬레이션·한도관리·거액 설정·거액 분석이
직접 쓴 한국어만 담는다. 셸 카탈로그(i18n_next.MESSAGES_NEXT)와 기존
i18n.py 에 이미 있는 어휘는 여기 다시 적지 않는다.

다른 화면 모듈이 이미 등록한 키(예: 역스트레스 임계 심도 는 ng_reports)는
여기 다시 적지 않는다. 병합 사전이 하나이므로 조회는 그대로 된다.

여기 없는 것: 원장 값과 원장 어휘(대기·승인·반려, 규정, 미승인, 무명고객,
완결·검토, 진행가능·차단, PASS·WARN·FAIL, unresolved), 카탈로그 라벨,
물리 테이블·컬럼명, 규정 인용, 실행 ID·요청 ID·지문, 검증명, 수치 ID.
그 값들은 화면이 T() 를 태우지 않고 원문 그대로 찍는다.
"""

from risk_lib.ui_studio.next.i18n_next import _t

MESSAGES: dict[str, dict[str, str]] = {}

# ── 화면 머리말 ──────────────────────────────────────────────────────
_t("ng_control",
   '결재를 막는 것과 그것을 푸는 조치를 한자리에 모은다'
   '||What blocks sign-off and the action that clears it, in one place',
   '마감 과업과 게이트 판정을 단계 레인으로 세운다. 판정과 사유는 게이트 원장 값이다'
   '||Close tasks and gate determinations in phase lanes. Determinations and reasons are gate ledger values',
   '자본비율 항등식의 설명용 산술이다. 위험가중자산과 자본을 움직여 비율 반응을 본다. 재계산이 아니며 승인·제출값 아님'
   '||Explanatory arithmetic on the capital ratio identity. Move risk weighted assets and capital and watch the ratio respond. Not a recalculation and not an approved or submitted value',
   '차주·업종·국가·자산군·등급 다차원 한도와 소진율이다. 경보 구간의 경계는 한도 엔진의 심각도 어휘가 정한다. 한도 근거와 승인 기록은 정의 원장에서 읽는다'
   '||Multi-dimensional limits and utilisation by borrower, sector, country, asset class and rating. The warning band boundary is set by the severity vocabulary of the limit engine. The basis and approval record of a limit are read from the definition ledger',
   '거액익스포져 산출의 설정 원장이다. 한도율·보고기준·판정 임계·면제정책이 체계별로 있고 항목마다 근거와 근거 판정이 붙는다'
   '||The setup ledger behind the large exposure calculation. Limit ratios, reporting thresholds, determination thresholds and exemption policy are held per framework, and every item carries its basis and evidence status',
   '체계별 소진과 보고대상, 대체, 연결그룹, 면제, look-through 귀속을 본다. 화면에는 표본이 실리고 순위·분포·합계는 전량 집계다'
   '||Utilisation and reportable status per framework, substitution, connected groups, exemptions and look-through attribution. The screen carries a sample while rankings, distributions and totals are aggregated over the full population',
   # ── 콕핏 ────────────────────────────────────────────────────────────
   '증빙 계보 완결||Evidence lineage complete',
   '실행 간 대조||Comparison across runs',
   '원장 행수||Ledger rows',
   '원장 표 (콕핏 근거)||Ledger tables behind the cockpit',
   '임계 심도||Critical severity',
   '함의 국내총생산 충격||Implied GDP shock',
   '함의 부도시손실률 가산||Implied LGD add-on',
   '위반 보고 (차주 버킷 포함)||Breach report incl. obligor buckets',
   '한도 소진||Limit utilisation',
   '한도 내||Within limit',
   '한도엔진||Limit engine',
   '한도 엔진 결과||Limit engine result',
   # ── 의사결정 큐 · 마감 워크플로 ──────────────────────────────────────
   '{n}일||{n} days',
   '예외 식별자||Exception id',
   '이행 상태||Task status',
   '판정 사유||Determination reason',
   '수행 에이전트||Agent',
   '화면은 자기 톤 사전을 두지 않는다||The screen keeps no tone map of its own',
   # ── 시뮬레이션 (설명용 산술) ─────────────────────────────────────────
   '내부산출 합||Internal calculation total',
   '표준방법 산출 합||Standardised approach total',
   '하한 비율||Floor ratio',
   '하한 금액||Floor amount',
   '산출하한 가산액||Output floor add-on',
   '최종 위험가중자산||Final risk weighted assets',
   '하한이 무는가||Does the floor bind',
   '하한이 물어 내부산출을 더 줄여도 최종 위험가중자산이 줄지 않는다'
   '||The floor binds, so cutting the internal calculation further does not reduce final risk weighted assets',
   '요구 충족||Requirement met',
   '완충자본 잠식||Buffer erosion',
   '최저비율 미달||Below the minimum ratio',
   '완충자본 잠식 구간은 최저비율은 넘었으나 요구비율에 못 미치며 배당·성과급이 제한된다'
   '||The buffer erosion band is above the minimum ratio but below the required ratio, and dividends and bonuses are restricted there',
   '비중||Share',
   '내부자본 가용자본||ICAAP available capital',
   '내부자본 여유||ICAAP headroom',
   '금리리스크 경제적가치 변동 / 기본자본||IRRBB change in economic value over Tier 1',
   '내부자본 소요액과 금리리스크 아웃라이어 판정은 모형·원장 값이며 이 화면이 다시 계산하지 않는다'
   '||The internal capital requirement and the IRRBB outlier determination are model and ledger values, and this screen does not recompute them',
   '대상 비율||Target ratio',
   '목표||Target',
   '목표 비율을 입력한다||Enter a target ratio',
   '위험가중자산으로 맞추기||Meet it through risk weighted assets',
   '자본으로 맞추기||Meet it through capital',
   '도달 가능||Reachable',
   '하한이 물어 도달 불가||Not reachable, the floor binds',
   '위험가중자산 축소만으로는 하한 금액 아래로 갈 수 없어 해가 꺾인다'
   '||Shrinking risk weighted assets alone cannot go below the floor amount, so the solution kinks here',
   '경계선이 요구비율 등고선이며 산출하한은 각 칸에서 다시 적용된다'
   '||The boundary is the required ratio contour and the output floor is reapplied in every cell',
   '조정안||Adjustment',
   '조정안 비교||Adjustments compared',
   '시뮬레이션 기준값이 payload 에 없다. 화면을 그리지 않는다.'
   '||The simulation base figures are not in the payload. The screen is not drawn.',
   # ── 한도관리 ────────────────────────────────────────────────────────
   '동일차주 두 산출||Single borrower, two calculations',
   '분모기준이 달라 두 산출이 어긋난다. 두 수치는 언제나 함께 적는다'
   '||The two calculations disagree because the denominator basis differs. Both figures are always printed together',
   '승인 기록 없이는 이 한도로 낸 위반 판정을 결재에 올릴 수 없다'
   '||Without an approval record, a breach determination made with this limit cannot be submitted for sign-off',
   '잔여한도는 한도액에서 익스포저를 뺀 값이며 음수가 위반이다. 버킷 정의가 달라 차원 간에 더하지 않는다'
   '||Headroom is the limit amount minus the exposure and a negative value is a breach. Bucket definitions differ, so headroom is never added across dimensions',
   '구간 톤은 그 구간 최고 소진율 행의 심각도 어휘를 따른다'
   '||A band takes its tone from the severity vocabulary of its highest utilisation row',
   '상위 기여 차주||Largest contributing borrowers',
   '버킷 내 익스포저||Exposures in the bucket',
   '이 버킷을 채우는 익스포저를 원장에서 찾지 못했다. 축 컬럼이 원장에 없다'
   '||No exposure filling this bucket was found in the ledger. The axis column is not in the ledger',
   '동일차주 축은 한도 소진 원장에 없다. 차주 단위 한도는 거액 분석에서 본다'
   '||The single borrower axis is not in the limit utilisation ledger. Borrower level limits are seen on the large exposure analysis screen',
   '익스포저 증감||Exposure change',
   '이 증감이면 해당 한도를 넘긴다||This change would breach that limit',
   '기본자본 연동 한도는 자본이 바뀌면 한도 자체가 움직인다. 그 연동은 시뮬레이션에서 본다'
   '||A Tier 1 linked limit moves with capital itself. That coupling is seen on the simulation screen',
   '위반 조치 원장({name})이 없다||The breach remediation ledger ({name}) does not exist',
   '원인·대응책·담당·기한을 담는 수기입력 원장이 필요하다'
   '||A manually entered ledger holding cause, remedy, owner and due date is needed',
   '필요 컬럼||Columns required',
   '한도 {total}건||{total} limits',
   '위반 없음||No breach',
   # ── 거액 설정 · 거액 분석 ────────────────────────────────────────────
   '설정 원장||Setup ledger',
   '설정항목||Parameter',
   '값이 비어 있는 설정||Setup parameters with an empty value',
   '1차자료 미확인이거나 규정이 값을 주지 않는 항목이며 산출되지 않는다'
   '||The primary source is unverified or the regulation gives no value, and the item is not calculated',
   '승인란이 채워지지 않은 설정||Setup parameters with an empty approver',
   '승인 전에는 이 설정으로 낸 산출을 결재에 올릴 수 없다'
   '||Before approval, a calculation made with this setup cannot be submitted for sign-off',
   '수기조정||Manual override',
   '설정 변경은 승인 대상이다. 이 화면은 제안서만 만들고 값을 바꾸지 않는다'
   '||A setup change requires approval. This screen drafts a proposal only and changes no value',
   '제안 값||Proposed value',
   '현재값||Current value',
   '제안 값과 사유와 증빙이 모두 필요하다||The proposed value, the reason and the evidence are all required',
   '이 항목을 바꾸면 한도율·소진율·보고대상·연결그룹·귀속·총액한도가 다시 산출된다. 재실행이 필요하다'
   '||Changing this item recalculates limit ratios, utilisation, reportable status, connected groups, attribution and the aggregate limit. A rerun is required',
   '거액익스포져 집계가 payload 에 없다||The large exposure aggregate is not in the payload',
   '체계 대비||Frameworks side by side',
   '분모 기준||Denominator basis',
   '분모가 다른 체계는 같은 익스포저에서 다른 비율을 낸다. 두 비율을 더하거나 비교하지 않는다'
   '||Frameworks with different denominators give different ratios on the same exposure. The two ratios are never added or compared',
   '모집단 {N}행 중 상위 {n}||top {n} of a population of {N} rows',
   '마지막 칸이 한도를 넘긴 포지션이다||The last band holds the positions over the limit',
   '대체는 익스포저를 보장제공자로 옮긴다. 옮겨 받은 쪽의 한도 초과는 그 제공자 포지션 행에서 읽는다'
   '||Substitution moves the exposure to the protection provider. Whether the receiving side is over its limit is read from that provider position row',
   '대체가 인정되지 않은 건||Substitutions not recognised',
   '사유는 적격 사유 컬럼에 있다||The reason is in the eligibility reason column',
   '2개사 이상||Two or more members',
   '경제적 상호의존 평가 대상||Subject to economic interdependence review',
   '기초자산을 식별하지 못한 잔여는 무명고객 버킷으로 귀속된다'
   '||The residual whose underlying assets could not be identified is attributed to the unknown client bucket',
   '귀속 임계||Attribution threshold',
   '면제액은 한도 산입에서 빠진 금액이며 측정액과 산입액의 차이다'
   '||The exempt amount is what was left out of the limit inclusion and equals the measured amount minus the included amount',
   '익스포저 유형||Exposure type',
   '총액||Gross amount',
   into=MESSAGES)
