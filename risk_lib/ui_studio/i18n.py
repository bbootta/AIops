"""화면 문자열 카탈로그. 한국어·영어 두 벌.

**왜 원장이 아니라 코드 카탈로그인가.** UI 라벨은 리스크 데이터가 아니다.
파이프라인이 산출하는 값도 아니고 승인 대상도 아니다. 원장에 넣으면 화면을
고칠 때마다 원장 스키마와 빌더가 따라 움직여야 하고, 규제 원장에 번역문이
섞인다. 그래서 코드 카탈로그에 둔다.

**원장에서 오는 값은 번역하지 않는다.** 차주명·등급·서식 항목명·컬럼 표시명은
원장(ColumnSpec.korean, reg_form_line.line_label 등)이 정본이다. 번역하면
화면의 이름과 원장의 이름이 갈라져 감사 추적이 끊긴다. 화면은 원문을 그대로
쓰고, 필요하면 이 카탈로그에서 온 영문 병기를 괄호로 덧붙인다.

**규정 조문 인용은 번역하지 않는다.** `은행업감독규정 제26조`, `[별표 9-1]`,
`CRE52` 같은 표기는 원문 그대로 둔다. 조문 번호를 옮기면 근거를 되짚을 수
없다. 영문 설명이 필요하면 괄호로 병기한다.

조회는 **한국어 원문 → 영문**이다. 화면 소스에 이미 한국어가 적혀 있고 그
문자열이 그대로 키 노릇을 한다. 아래 카탈로그는 키마다 ko·en 두 값을 갖고,
`ko_to_en()` 이 조회용 사전을 만든다. 등록되지 않은 문자열은 영문 화면에서
한국어로 떨어지는데, 조용히 떨어지면 누락을 못 보므로 개발 모드
(주소에 `?i18n=debug`)에서는 표시를 감싸 눈에 띄게 한다.

용어는 업계 표준 영문을 쓴다. 위험가중자산 Risk-Weighted Assets (RWA),
보통주자본비율 CET1 ratio, 거액익스포저 Large Exposures, 적합성검증
independent validation, 소진율 utilisation, 잔여한도 headroom, 핵심예금
core deposits, 금리개정기일 repricing date, 수정듀레이션 modified duration.
"""

from __future__ import annotations

# 초기 언어. 사용자가 고르기 전 기본값이며, 선택은 localStorage 에 남는다.
DEFAULT_LANG = "en"

# localStorage 키. 화면 밝기(rynta-theme)와 같은 접두사를 쓴다.
STORAGE_KEY = "rynta-lang"

LANGS = ("en", "ko")

MESSAGES: dict[str, dict[str, str]] = {}


def _m(**kw: str) -> None:
    """`키='한국어||English'` 를 카탈로그에 넣는다.

    항목이 많아 `{"ko": ..., "en": ...}` 를 매번 적으면 카탈로그가 읽히지
    않는다. 구분자는 화면 문자열에 등장하지 않는 `||` 를 쓴다.
    """
    for key, val in kw.items():
        ko, sep, en = val.partition("||")
        if not sep or not en.strip():
            raise ValueError(f"i18n 항목 {key} 에 영문이 없다")
        if key in MESSAGES:
            raise ValueError(f"i18n 키 중복: {key}")
        MESSAGES[key] = {"ko": ko, "en": en}


def ko_to_en() -> dict[str, str]:
    """조회용 사전. 같은 한국어에 서로 다른 영문이 붙으면 실패한다.

    같은 문자열이 화면 두 곳에서 다른 뜻으로 쓰이면 한쪽이 틀린 영문으로
    나가는데, 그 사실이 화면에 남지 않는다. 빌드 시점에 막는다.
    """
    out: dict[str, str] = {}
    seen: dict[str, str] = {}
    for key, v in MESSAGES.items():
        ko, en = v["ko"], v["en"]
        if ko in out and out[ko] != en:
            raise ValueError(
                f"같은 한국어 '{ko}' 에 영문이 둘이다: "
                f"{seen[ko]}={out[ko]!r} / {key}={en!r}")
        out[ko] = en
        seen[ko] = key
    return out


def payload(debug: bool = False) -> dict:
    """화면에 인라인할 i18n 페이로드."""
    return {
        "default": DEFAULT_LANG,
        "langs": list(LANGS),
        "storage_key": STORAGE_KEY,
        "debug": bool(debug),
        "map": ko_to_en(),
    }


# ════════════════════════════════════════════════════════════════════════
# 1. 머리말·꼬리말·공통 조작 (헤더 칩, 비상정지, 언어·밝기 전환)
# ════════════════════════════════════════════════════════════════════════

_m(
    app_title='에이전틱 UI 스튜디오||Agentic UI Studio',
    hdr_asof='기준일||As-of date',
    hdr_digest='지문||Digest',
    hdr_seed='시드||Seed',
    hdr_tables='테이블||Tables',
    hdr_rows='행||rows',
    hdr_tables_n='{n}장||{n}',
    hdr_readonly='Read-only · PII Mask||Read-only · PII Mask',
    btn_theme='화면 밝기||Theme',
    btn_theme_to_light='밝은 화면으로||Switch to light',
    btn_theme_to_dark='어두운 화면으로||Switch to dark',
    btn_theme_title='밝은 화면과 어두운 화면을 전환한다||Toggle light and dark appearance',
    btn_theme_stored='선택한 화면 밝기||Theme you selected',
    btn_theme_system='시스템 설정을 따르는 중||Following the system setting',
    btn_theme_press='누르면 전환한다.||Click to switch.',
    btn_lang_to_ko='한국어||한국어',
    btn_lang_to_en='English||English',
    btn_lang_title='화면 언어를 전환한다. 원장에서 오는 값(차주명·등급·서식 항목명·컬럼명)은 원문 그대로 둔다.||Switch the interface language. Values that come from the ledgers (obligor names, grades, regulatory form line labels, column names) stay in the original Korean.',
    btn_kill='Kill Switch||Kill Switch',
    btn_kill_release='Kill Switch 해제||Release Kill Switch',
    kill_scope='범위||Scope',
    kill_reason='비상정지 사유 (필수)||Reason for emergency stop (required)',
    kill_reason_default='시장데이터 지연 확인 중 신규 재계산 보류||Holding new recalculations while a market data delay is investigated',
    kill_go='정지||Stop',
    kill_no='취소||Cancel',
    kill_note='중요 범위는 운영에서 독립된 2차 확인이 추가로 필요하다.||Critical scopes need a second confirmation from outside the operating line.',
    scope_all='전사||Enterprise-wide',
)

_m(
    foot_line1='엔진 산출은 결정론적이며, 에이전트는 제안만 하고 승인은 사람이 한다.||Engine output is deterministic. Agents only propose, people approve.',
    foot_line2='화면의 모든 값은 합성 포트폴리오에서||Every figure on screen comes from a synthetic portfolio produced by',
    foot_line3='로 산출한 것이며 실제 기관 수치가 아니다.||and is not an actual institution figure.',
    foot_line4='에이전트는 신용등급·여신승인, PD·LGD·EAD 등 핵심 위험파라미터, ECL·충당금, RWA·BIS 비율, 감독제출·공시, 경영조치를 자동확정하지 않는다.||Agents never finalise credit grades or loan approvals, key risk parameters (PD, LGD, EAD), ECL and loan loss allowance, RWA and BIS ratios, regulatory submissions and disclosures, or management actions.',
    foot_abbr='약어||Abbreviations',
    foot_abbr_body='RDM(리스크데이터관리) · RWA(위험가중자산) · ECL(기대신용손실) · ALM(자산부채관리) · IRRBB(은행계정 금리리스크) · LCR(유동성커버리지비율) · NSFR(순안정자금조달비율) · IPV(독립가격검증) · SICR(신용위험 유의적 증가) · DQ(데이터품질) · AST(구문트리) · PSMOR(운영리스크 건전관리 원칙).||RDM (risk data management) · RWA (risk-weighted assets) · ECL (expected credit loss) · ALM (asset and liability management) · IRRBB (interest rate risk in the banking book) · LCR (liquidity coverage ratio) · NSFR (net stable funding ratio) · IPV (independent price verification) · SICR (significant increase in credit risk) · DQ (data quality) · AST (abstract syntax tree) · PSMOR (Principles for the Sound Management of Operational Risk).',
    nav_aria='메뉴||Menu',
)

# ════════════════════════════════════════════════════════════════════════
# 2. 네비게이션 (그룹명·화면명). 최우선 번역 대상.
# ════════════════════════════════════════════════════════════════════════

_m(
    navg_report='보고서||Reports',
    navg_control='통제센터||Control centre',
    navg_query='조회·컴포저||Query and composer',
    navg_model='모형||Models',
    navg_model_inventory='모형 인벤토리||Model inventory',
    navg_credit_model='신용모형||Credit models',
    navg_irb_estimation='내부등급법 추정||IRB estimation',
    navg_behaviour='고객행동모형||Customer behavioural models',
    navg_riskdata='리스크데이터||Risk data',
    navg_rdm='RDM||RDM',
    navg_upstream='선행 원장||Upstream ledgers',
    navg_rwa='위험가중자산(RWA)||Risk-Weighted Assets (RWA)',
    navg_lex='거액익스포져||Large Exposures',
    navg_alm_stress='ALM·위기상황||ALM and stress testing',
    navg_alm='ALM||ALM',
    navg_stress='위기상황||Stress testing',
    navg_prudential='증권 건전성||Securities prudential',
    navg_reporting='보고||Regulatory reporting',
    navg_validation='검증·거버넌스||Validation and governance',
    navg_validation_sub='검증||Validation',
    navg_data_settings='데이터·설정||Data and settings',
    navg_settings='⚙ 설정||⚙ Settings',
    navg_reference='(참고)||(Reference)',
)

_m(
    nav_exec_report='종합보고서||Executive report',
    nav_cockpit='콕핏||Cockpit',
    nav_structured='정형 조회||Governed query',
    nav_adaptive='비정형 UI||Adaptive UI',
    nav_rdm='RDM||RDM',
    nav_credit='신용||Credit',
    nav_credit_rwa='신용 RWA||Credit RWA',
    nav_ecl='ECL||ECL',
    nav_market='시장||Market',
    nav_operational='운영||Operational',
    nav_alm='ALM||ALM',
    nav_stress='위기상황||Stress testing',
    nav_regulatory='감독보고||Regulatory reports',
    nav_validation='검증||Validation',
    nav_agents='에이전트||Agents',
    nav_changes='변경||Change factory',
    nav_datamodel='데이터모델||Data model',
    nav_req_trace='요건 추적||Requirement traceability',
    nav_settings='⚙ 설정||⚙ Settings',
    nav_source_contract='원천·계약||Source contracts',
    nav_dq='DQ·대사||DQ and reconciliation',
    nav_exception='예외·조치||Exceptions and actions',
    nav_collateral='담보·보증||Collateral and guarantees',
    nav_migration='등급 전이||Rating migration',
    nav_ews='조기경보||Early warning',
    nav_ipv='가격검증·IPV||Price verification (IPV)',
    nav_backtest='백테스팅||Backtesting',
    nav_var_es='VaR·ES||VaR and ES',
    nav_oploss='손실·회수||Losses and recoveries',
    nav_kri='KRI·통제||KRI and controls',
    nav_ncr='NCR·건전성||NCR and prudential',
    nav_market_rwa='시장 RWA||Market RWA',
    nav_op_rwa='운영 RWA||Operational RWA',
    nav_ciu='집합투자증권||Collective investment undertakings',
    nav_derivative='파생상품||Derivatives',
    nav_securitisation='유동화||Securitisation',
    nav_agg='집계 원장||Aggregation ledgers',
    nav_commercial='상업성||Commercial case',
    nav_simulation='시뮬레이션||Simulation',
    nav_limits='한도관리||Limit management',
    nav_overlay='오버레이||Overlays',
    nav_macro='거시지표 모니터링||Macro indicator monitoring',
    nav_reverse_stress='역스트레스||Reverse stress testing',
    nav_scenario='시나리오 설정||Scenario setup',
    nav_code_master='코드 마스터||Code master',
    nav_code_scope='코드 매핑||Code mapping',
    nav_model_inventory='모형 인벤토리||Model inventory',
    nav_model_schedule='검증 일정||Validation schedule',
    nav_model_risk='모형리스크||Model risk',
    nav_model_perf='변별력·안정성||Discrimination and stability',
    nav_model_calib='등급 보정||Grade calibration',
    nav_methodology='산출 방법론||Calculation methodology',
    nav_irrbb='금리리스크||IRRBB',
    nav_alm_cashflow='현금흐름 원장||Cash flow ledger',
    nav_ladder='유동성 사다리||Maturity ladder',
    nav_liquidity='유동성리스크||Liquidity risk',
    nav_survival='생존기간||Survival horizon',
    nav_alm_param='ALM 계수 원장||ALM factor ledger',
    nav_kr_irrbb='국내 금리리스크||Domestic IRRBB',
    nav_bhv_model='행동모형 추정||Behavioural model estimation',
    nav_nmd_core='비만기성예금 코어||NMD core deposits',
    nav_bhv_backtest='행동모형 백테스트||Behavioural model backtest',
    nav_pd='PD 추정||PD estimation',
    nav_lgd='LGD 추정||LGD estimation',
    nav_ccf='CCF 추정||CCF estimation',
    nav_defaulted_lgd='부도자산 LGD||Defaulted asset LGD',
    nav_irb_gov='모형 거버넌스||Model governance',
    nav_lgd_ead_bt='LGD·EAD 실측검증||LGD and EAD outcome validation',
    nav_lex_setting='거액 설정||Large exposure setup',
    nav_lex_analysis='거액 분석||Large exposure analysis',
)
