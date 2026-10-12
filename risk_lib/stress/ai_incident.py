"""AI 사고 시나리오 스트레스테스트.

AI 사고 일곱 유형(요건 BR-049 사고분류 7종, 공급자 장애·공통모델 실패는 BR-055)을
기존 전 축 위기상황 엔진(`multi_axis.evaluate_point`)에 개별 사건 덧씌우기
(`StressOverlay`)로 얹어 CET1·RWA·ECL·LCR 경로로 옮긴다. 계산식은 새로 만들지 않고
엔진의 신용 RWA·ECL·운영 RWA(OPE25 ILM)·LCR·손익·세금·자본·산출하한을 그대로 쓴다.

설계 원칙

1. 세 심도는 모두 사고 발생을 전제로 한 조건부 크기다. 빈도 가중을 하지 않는다.
   기준은 통제가 작동한 경우, 악화는 공개 선례의 대표값, 심각은 관측 최악 선례나
   법정 상한이다. 재현기간은 서열 해석(기준 약 5년, 악화 약 20년, 심각 약 50년
   이상)이며 손실분포 적합이 아니다.
2. 크기는 기관 규모에 비례한다. REV(엔진 영업수익), BI(OPE25 영업지표), OPEX,
   FEE = REV x 0.20, NII = REV x 0.80, NP_EAD(자연인 IRB 익스포저)를 곱한다.
   원화 절대액 상수는 없다. 아홉 기관은 통화 환산이 없어 원화로 비교할 수 없다.
3. 채널 종류가 회계 처리를 정한다.
   - op: 세전 직접손실, 운영손실 자료에 들어가 10년 평균에 L/10 가산(ILM)
   - nonop: 세전 직접손실이지만 운영손실 자료 밖(일실수익·이용료·이전비)
   - fine: 세후 차감(손금불산입 과징금), 운영손실 자료에 들어간다
   - pd·lgd·fallback: 신용 경계사건. 운영손실 자료에 넣지 않는다
   - pd_capital: 자본 산출 전용 PD 배수(감독 보수성). RWA 에만 들어가고 ECL 에는
     넣지 않는다
   - runoff: LCR 전용. 자본으로 되먹임되지 않는다
   같은 사건을 기존 op_loss 축과 직접손실에 함께 넣지 않는다.
4. 일회성 손실과 흐름 손실은 사건 이후 누적해 넘긴다. 엔진은 분기마다 기준 대비
   연간 이익 변화로 자본을 다시 맞추므로, 분기 값만 넣으면 다음 분기에 사라진다.
5. 제재 시차는 날짜로 정한다. 사고일은 첫 투영 분기 시작일 + 14일, 탐지형 사고의
   탐지일은 사고일 + 4개월이다. 과징금은 그 날짜 + 4/7/11개월(SKT·쿠팡·롯데카드
   선례)이 속한 분기에 착지하고, 시계 밖이면 버리지 않고 시계 밖 금액으로 남긴다.
   운영·비운영 손실의 시계 밖 몫도 앞당기지 않고 같은 방식으로 남긴다.
6. 표준방법 회귀(모형 사용 정지)는 자본을 줄이는 쪽이면 받아들이지 않는다
   (무완화 규칙). 두 번 풀어 RWA 합계가 큰 쪽을 채택하고 포기한 완화액을 남긴다.
7. 요구치 판정은 엔진과 같이 CET1·Tier1·총자본 세 계층(완충 포함)의 구속 계층으로
   한다. CET1 계층만의 잉여·미달과 역스트레스 임계는 따로 남긴다(접미 _cet1).

운영손실 기준선. 이 모듈은 파이프라인 헤드라인 운영 RWA와 같은 10년 평균 손실
(운영 명목 x 기관 손실률)로 고친 장부를 받는다. 기존 위기상황 경로의 장부는 명목
x 0.001 을 쓰므로 국내 표본 외 기관에서 운영 RWA 기준점이 헤드라인과 다르다. 그
경로는 바꾸지 않았고, 차이는 자체검증 상세에 남는다.

크기 대부분은 재량·미규정 내부 관리값이며 공개 선례(검색 요약 확인, 원문 대조
미완)는 2차자료로 적는다. 기관 승인 시나리오로 교체가 전제다.
"""

from __future__ import annotations

import calendar
import math
from dataclasses import dataclass, field, replace
from datetime import date

import pandas as pd

from risk_lib.alm.params import EVIDENCE_STATUS
from risk_lib.datamodel.spec import ColumnSpec as C, ForeignKey as FK, TableSpec
from risk_lib.stress.multi_axis import (
    INTEREST_SHARE_OF_REVENUE, TAX_RATE, StressBooks, StressOverlay,
    evaluate_point,
)
from risk_lib.stress.path import DEFAULT_STRESS_PATHS

SEVERITIES = ("baseline", "adverse", "severely_adverse")
SEVERITY_KO = {"baseline": "기준", "adverse": "악화",
               "severely_adverse": "심각", "combined": "결합"}
SEVERITY_KEYS = SEVERITIES + ("combined",)
_IX = {s: i for i, s in enumerate(SEVERITIES)}

INCIDENT_CLASSES = ("권한/행동위반", "모형오류", "데이터유출", "공정성/소비자피해",
                    "가용성", "공급망", "증빙손상", "복합")
TIMING_TYPES = ("사고형", "탐지형", "결합")
CHANNEL_KINDS = ("driver", "op", "nonop", "fine", "pd", "pd_capital", "lgd", "runoff",
                 "fallback", "rule")

IRB3 = ("corporate", "residential_mortgage", "retail_other")
NATURAL_PERSON = ("residential_mortgage", "retail_other")
RETAIL_RUNOFF = ("retail_stable", "retail_less_stable")
FEE_SHARE = 1.0 - INTEREST_SHARE_OF_REVENUE

INCIDENT_DAY_OFFSET = 14            # 첫 투영 분기 시작일 + 14일
DETECTION_LAG_MONTHS = 4            # 탐지형 사고의 탐지 시점
SANCTION_LAG_MONTHS = (4, 7, 11)    # 기준·악화·심각
EU_AI_ACT_HIGH_RISK_DATE = date(2027, 12, 2)
PD_MULTIPLIER_CAP = 1.30            # retail_other 혹 모양 K 부호 가드
IMPACT_TOLERANCE_DAYS = 1           # 핵심업무서비스 '모바일 이체' 영향허용치
KR_CREDIT_INFO_HACKING_CAP = 5.0e9  # 신용정보법 해킹 유출 과징금 절대 상한 (KR 관할 가드)
PIPA_GENERAL_CAP = 0.03             # 개인정보보호법 제64조의2 일반 상한 (전체 매출액 대비)
PIPA_AGGRAVATED_CAP = 0.10          # 같은 조 가중 상한 (2026-09-11 시행, 고의·중과실 반복 등)
TIER_KO = {"cet1": "CET1", "tier1": "Tier1", "total": "총자본"}

_EV_SECONDARY = "2차자료"
_EV_DISCRETION = "재량·미규정"
_EV_CODE = "원문미확인·현행계승"


# --------------------------------------------------------------------------- 카탈로그
@dataclass(frozen=True)
class AIScenario:
    scenario_id: str
    name: str
    incident_class: str
    br055: bool
    basel_event_type: str | None
    timing_type: str
    narrative: str
    trigger: str
    kill_switch_scope: str
    recovery: str
    time_profile: str
    requirement_refs: str


@dataclass(frozen=True)
class AIParam:
    scenario_id: str
    channel: str
    kind: str
    unit: str
    values: tuple[float, float, float]
    scope: str
    timing: str
    citation: str
    evidence_status: str

    def at(self, severity: str) -> float:
        return float(self.values[_IX[severity]])


SCENARIOS: tuple[AIScenario, ...] = (
    AIScenario(
        "AI-01", "AI 에이전트 권한 초과 실행 (자금·주문 오실행)", "권한/행동위반", False,
        "execution_delivery", "사고형",
        "배포 변경 뒤 운영 AI 에이전트가 셸·쓰기 도구로 승인 범위 밖의 이체와 주문을 "
        "반복 실행하고, 차단이 늦어질수록 손실이 쌓인다. 손실은 일회성이지만 내부손실승수를 "
        "거쳐 운영리스크 자본에 시계 끝까지 남고, 감독 제재가 시차를 두고 뒤따른다.",
        "쓰기 권한이 없다고 등록된 에이전트가 셸·쓰기 도구로 자금·주문 API 를 호출하는 "
        "루프. 1차 감지는 거래량·금액 이상치 KRI 이며 손실 크기는 탐지부터 차단까지의 "
        "지연이 정한다.",
        "agent 에서 tool 로: 해당 에이전트 즉시 정지 후 셸·쓰기 도구를 도구 단위로 회수, "
        "심각은 workflow 단위로 확장 (BR-050)",
        "원인 분석과 재개승인(BR-052)까지 쓰기 도구 차단 유지. 상대방 취소·보험 회수는 "
        "0 으로 둔다.",
        "첫 분기 실행손실 전액 인식, 제재는 사고일 + 4/7/11개월이 속한 분기에 착지",
        "BR-049 · BR-050 · BR-052"),
    AIScenario(
        "AI-02", "AI·통계 신용평가모형 공통 실패 (분포이탈 PD·LGD 과소추정)", "모형오류",
        False, "execution_delivery", "탐지형",
        "세 신용평가모형이 공유하는 특성값 파이프라인의 결함으로 부도율과 부도시손실률이 "
        "같은 방향으로 과소추정되다가 분기 사후검증에서 드러난다. 은행은 재보정 배수로 "
        "신용 위험가중자산과 충당금을 다시 산출하며, 심각 단계의 기업 모형 사용 정지가 "
        "자본을 줄이는 결과는 받아들이지 않는다.",
        "첫 분기 사후검증에서 기업·주택담보·기타소매 모형의 실현 부도율이 추정을 일관되게 "
        "넘고 원인이 공통 파이프라인으로 확인된다. 내부 개발 모형이므로 공급자 장애(BR-055) "
        "가 아니며, 손실은 신용 채널에만 귀속한다.",
        "workflow: 신용심사 자동결정 워크플로 정지, 수기 심사 전환. 자본 산출 모형은 직전 "
        "승인 버전으로 동결하고 재보정 배수 결과만 쓴다.",
        "재보정 배수를 둘째 분기부터 시계 끝까지 유지. 기업 모형 사용 정지 판정은 넷 분기 "
        "뒤 해제.",
        "첫 분기 발견, 둘째 분기부터 PD 배수·LGD 가산 유지(저량), 심각의 표준방법 회귀 판정 "
        "넷 분기",
        "BR-049 · BR-021 · BR-023 · BR-024"),
    AIScenario(
        "AI-03", "생성형 AI 경유 개인신용정보 유출과 이중제재", "데이터유출", False,
        "external_fraud", "사고형",
        "외부 공격자의 프롬프트 주입으로 고객 상담 생성형 AI 의 검색 도구가 개인신용정보를 "
        "응답에 실어 밖으로 내보낸다. 개인정보보호위원회와 금융위원회 과징금이 시차를 두고 "
        "이중으로 부과되고, 고객 보상, 신규 영업 일부정지, 고객 이탈과 소매예금 유출이 "
        "뒤따른다.",
        "검색 범위 통제 실패나 간접 프롬프트 주입으로 차단 DLP 규칙을 우회하는 경로에서 "
        "신용정보 반출. 마스킹 적중 0건은 하네스가 언어모형을 호출하지 않아서이며 통제 "
        "효과의 증거가 아니다.",
        "tool 에서 tenant 로: 검색 도구와 고객정보 커넥터를 도구 단위로 차단, 심각은 생성형 "
        "AI 고객 채널 tenant 전면 중단 (BR-050)",
        "보상은 첫 두 분기 지급, 고객 이탈 이자이익 감소는 네 분기 지속, 예금 이탈 가산은 "
        "첫 두 분기, 영업정지는 금융위원회 의결 다음 분기부터.",
        "보상 첫 두 분기, 과징금 사고일 + 4/7/11개월, 영업정지 그 다음 분기, 이탈 둘째~다섯째 "
        "분기",
        "BR-049 · BR-013 · BR-015 · BR-020 · BR-040"),
    AIScenario(
        "AI-04", "AI 대출심사 차별·챗봇 오안내에 따른 소비자 피해 (고영향 AI)",
        "공정성/소비자피해", False, "clients_products", "탐지형",
        "자연인 대상 AI 대출심사가 특정 집단에 불리한 금리와 한도를 매기고, 상담 챗봇이 "
        "약관과 다르게 안내한 사실이 민원과 검사에서 확인된다. 은행은 자동심사와 챗봇 "
        "워크플로를 멈추고 이자 환급과 수수료 환불을 하며, 감독 제재가 탐지 후 시차를 두고 "
        "부과된다.",
        "자연인 세그먼트의 승인율·금리 집단 간 격차와 챗봇 오안내 민원이 누적되어 탐지된다. "
        "AI 기본법 고영향 AI(대출 심사)와 EU AI Act Annex III 신용평가 범위다. PD 오류가 "
        "아니므로 PD 배수를 쓰지 않는다.",
        "workflow: 자연인 자동심사·상담 응답 워크플로 정지, 사전 승인된 수기 경로로 전환 "
        "(BR-050)",
        "공정성 재검증·재개승인(BR-052) 후 재개. 보상·제재는 일회성 누적. AI 기본법 "
        "과태료는 절대액이 작아 0 으로 둔다.",
        "탐지 둘째 분기, 환급 셋째 분기, 제재 탐지일 + 4/7/11개월, 표준방법 회귀 판정 악화 "
        "두 분기·심각 네 분기",
        "BR-049 · BR-028 · BR-034"),
    AIScenario(
        "AI-05", "외부 AI 공급자·제3자 장애에 따른 핵심 채널 중단", "가용성", True,
        "business_disruption", "사고형",
        "외부 AI 공급자나 제3자 보안 소프트웨어의 결함 업데이트로 모바일뱅킹, AI 상담, "
        "이상거래탐지 스코어링이 함께 멈추고 부분 운영이 길게 이어진다. 은행은 중단 기간의 "
        "수수료수익을 잃고 복구·보상 비용과 감독 제재를 떠안으며, 자본보다 영향허용치와 "
        "유동성비율이 먼저 깨진다.",
        "공급자 측 결함 업데이트나 서비스 장애가 공통 의존 구성요소(언어모형 게이트웨이, "
        "보안 에이전트, 이상거래탐지 API)를 타고 핵심업무서비스로 번진다 (BR-055 공급자 "
        "장애, FSB 2024 제3자 집중).",
        "tenant 와 workflow: 공급자 tenant 연결 차단, AI 의존 워크플로를 규칙기반·인간 "
        "상담으로 전환, 재시도 폭주를 막기 위해 공급자 호출 도구 차단 (BR-050)",
        "완전중단 뒤 50% 부분운영을 거쳐 복구, 영구 수익 손실 없음. 보험 회수 0 "
        "(CrowdStrike 피해의 부보비중은 회수율이 아니다).",
        "첫 분기 수수료 일실·복구비·LCR 가산, 제재 사고일 + 4/7/11개월",
        "BR-049 · BR-055 · BR-073 · BR-074"),
    AIScenario(
        "AI-06", "외부 AI 공급망 공통모델 실패 (딥페이크 본인확인 우회·모델종료·가격·정책 변경)",
        "공급망", True, "external_fraud", "사고형",
        "여러 은행이 함께 쓰는 외부 본인확인·이상거래탐지 모형이 딥페이크와 음성 복제에 "
        "공통으로 뚫리고, 같은 시기 공급자가 모델 종료와 가격 인상, 이용정책 변경을 통보한다. "
        "대체 모형 승인까지 사기 손실이 이어지고 이전·재검증 비용과 늘어난 이용료가 쌓이며, "
        "무과실 배상 입법이 시행되면 반복 손실이 더해진다.",
        "외부 공급 본인확인·이상거래탐지 모형이 임원 사칭 화상회의와 음성 생체인증 우회에 "
        "공통 실패하고, 같은 분기 모델 버전 종료·단가 인상·이용정책 변경 통보 (BR-055 "
        "공통모델 실패·모델종료·가격·정책변경).",
        "tool 에서 workflow 로: 외부 모델 호출 차단, 비대면 고액이체·원격 본인확인에 대면 "
        "재확인과 추가 인증 강제 (BR-050)",
        "대체 모형 승인까지 사기 노출 지속, 사기 회수 0, 이용료 인상은 시계 끝까지, 무과실 "
        "배상은 넷째 분기부터 시계 끝까지 반복.",
        "사기 노출 첫 2/3/5 분기 균등, 이전비 둘째·셋째 분기, 이용료 둘째 분기부터, 무과실 "
        "배상 넷째 분기부터",
        "BR-049 · BR-053 · BR-054 · BR-055"),
    AIScenario(
        "AI-07", "AI 의사결정·모형 증빙 손상과 감독 보수성 가산", "증빙손상", False,
        "execution_delivery", "탐지형",
        "로그 파이프라인 변경이나 에이전트 쓰기 권한 오남용으로 AI 의사결정 기록과 모형 "
        "계보, 검증 기록의 해시 체인이 손상되어 대출 거절 사유와 자본 산출 근거를 재현하지 "
        "못한다. 은행은 소급 재수행을 하고 기록보존 위반으로 제재를 받으며, 감독당국은 증빙 "
        "재구축 때까지 PD 보수성 가산을 요구한다.",
        "추적 기록, 검증 산출물, 시드·기준일·지문 재현 정보의 덮어쓰기·손상이나 보존기간 전 "
        "삭제가 3선 재계산이나 감독 검사에서 재현 불가로 판정된다. 모형오류(AI-02)와 다른 "
        "사건이며 두 PD 배수를 겹치지 않는다.",
        "tool 에서 workflow·tenant 로: 증빙 저장소 쓰기 도구 차단, 증빙을 남기지 못하는 "
        "워크플로 중단, 손상 범위 tenant 쓰기 동결",
        "소급 재수행 두 분기, 증빙 재구축 네 분기 동안 보수성 가산과 표준방법 회귀 판정, "
        "그 뒤 해제. 복구비·제재금은 일회성 누적.",
        "탐지 둘째 분기, 재수행 둘째·셋째 분기, 제재 탐지일 + 4/7/11개월, 보수성 배수 셋째~"
        "여섯째 분기",
        "BR-049 · BR-061 · BR-024"),
    AIScenario(
        "AI-C1", "거시 심각 + 모형오류·정보유출 결합 (이사회 보고용)", "복합", False, None,
        "결합",
        "거시 심각 경로가 학습 분포 밖 환경을 만들어 신용평가모형 오류가 셋째 분기 "
        "사후검증에서 드러나고, 독립 사건인 정보유출이 둘째 분기에 일어나 과징금이 거시 "
        "저점 근처에 착지한다. 거시 꼬리와 AI 꼬리를 곱하지 않도록 AI 심도는 악화로 둔다.",
        "거시 severely_adverse 기존 경로 + AI-02 악화(PD 배수만, LGD 가산은 거시 축과 "
        "겹쳐 제외) + AI-03 악화(사고일을 탐지형 시점으로 이동)",
        "각 구성 시나리오의 차단 범위를 따른다",
        "각 구성 시나리오의 복구 가정을 따른다",
        "거시 경로 분기 심도 + AI 구성요소의 날짜 기반 시점",
        "BR-049 · SRP20"),
    AIScenario(
        "AI-C2", "거시 심각 + 정보유출 심각 (제재 착지 점검)", "복합", False, None, "결합",
        "거시 심각 경로 위에 정보유출 심각이 첫 분기에 일어나 개인정보보호위원회와 "
        "금융위원회 과징금이 사고일 + 11개월 뒤 거시 저점 분기에 세금차폐 없이 착지하는지 "
        "본다.",
        "거시 severely_adverse 기존 경로 + AI-03 심각",
        "AI-03 을 따른다", "AI-03 을 따른다",
        "거시 경로 분기 심도 + AI-03 심각 시점", "BR-049 · SRP20"),
)
SCENARIO_BY_ID = {s.scenario_id: s for s in SCENARIOS}
STANDALONE_IDS = tuple(s.scenario_id for s in SCENARIOS if s.timing_type != "결합")
COMBINED_IDS = tuple(s.scenario_id for s in SCENARIOS if s.timing_type == "결합")

_KNIGHT = ("Knight Capital 2012 알고리즘 오류: 장 개시 후 약 45분, 손실 USD 460m 초과 "
           "(SEC 2013-222 · 34-70694), Form 8-K 세전 약 USD 440m, 자기자본 약 30%, "
           "SEC 제재 USD 12m (검색 요약)")
_LAG = ("SKT 2025 사고~PIPC 약 4개월, 쿠팡 탐지~PIPC 약 7개월, 롯데카드 사고~PIPC 약 "
        "7개월·사고~금융위원회 약 11.5개월 (보도 검색 요약)")

PARAMS: tuple[AIParam, ...] = (
    # ---- AI-01
    AIParam("AI-01", "kill_latency_minutes", "driver", "분", (2, 10, 45),
            "탐지~차단 지연. 실행손실 산식에만 쓴다", "첫 분기",
            "심각: " + _KNIGHT + ". 기준·악화는 재량", _EV_DISCRETION),
    AIParam("AI-01", "execution_loss", "op", "BI 대비 비율 (= 0.002 x 차단지연 분)",
            (0.004, 0.02, 0.09), "전 기관, 오실행 거래·이체 손실", "첫 분기 전액",
            "분당 BI 0.2% 산식은 재량. Knight 2012 는 질적 앵커", _EV_DISCRETION),
    AIParam("AI-01", "regulatory_sanction", "fine", "execution_loss 대비 배수",
            (0.027, 0.027, 0.027), "전 기관, 감독 제재 (손금불산입)",
            "사고일 + 4/7/11개월", "Knight Capital SEC 제재 USD 12m / 손실 약 USD 440m",
            _EV_SECONDARY),
    AIParam("AI-01", "corporate_non_operational", "runoff", "이탈률 가산 (소수)",
            (0.0, 0.03, 0.10), "LCR 법인 비영업성 예금 (기본 40%)", "첫 분기",
            "재량: 거래상대방 신뢰 하락 가정", _EV_DISCRETION),
    # ---- AI-02
    AIParam("AI-02", "pd_multiplier", "pd", "PD 배수", (1.05, 1.15, 1.30),
            "IRB 모형산출 3개 자산군 공통 (corporate · residential_mortgage · retail_other)",
            "둘째 분기부터 시계 끝까지",
            "재량. 앵커: 엔진 거시 위성모형의 기업 PD 상승배수(악화 정점 약 1.26, 심각 정점 "
            "약 1.67)의 일부. 배수 상한 1.30 은 retail_other 혹 모양 K 부호 가드. SR 11-7 · "
            "PRA SS1/23 보수성 원칙", _EV_DISCRETION),
    AIParam("AI-02", "lgd_addon", "lgd", "LGD 가산 (소수)", (0.0, 0.01, 0.02),
            "IRB 장부 전체 = 모형산출 3개 자산군. 단독 실행에서만, 결합에서는 제외",
            "둘째 분기부터 시계 끝까지",
            "재량. CRE36.83 하강기 LGD 관리값은 거시 보정이라 크기 근거로 쓰지 않는다",
            _EV_DISCRETION),
    AIParam("AI-02", "sa_fallback_corporate", "fallback", "적용 플래그 (1 = 판정 수행)",
            (0, 0, 1), "기업 모형 사용 정지 판정, 무완화 규칙", "둘째~다섯째 분기",
            "재량 (감독 사용정지 가정)", _EV_DISCRETION),
    # ---- AI-03
    AIParam("AI-03", "pipc_fine", "fine", "REV 대비 비율", (0.001, 0.0106, 0.03),
            "전 기관, 개인정보보호법 과징금 (손금불산입)", "사고일 + 4/7/11개월",
            "악화: SKT 2025 PIPC 1,347.91억 = 별도매출 약 1.06% (쿠팡 2026 약 1.37%). 심각: "
            "개인정보보호법 제64조의2 일반 상한 전체 매출액의 3%. 가중요건(고의·중과실 반복, "
            "1천만 명 이상 피해, 시정명령 불이행 후 유출) 미충족 가정이며, 가중 상한 10% "
            "(2026-09-11 시행)는 역스트레스 F* 와 비교만 한다. 기준 0.1% 는 재량",
            _EV_SECONDARY),
    AIParam("AI-03", "fsc_fine", "fine", "pipc_fine 대비 배수", (0.52, 0.52, 0.52),
            "전 기관, 신용정보법 과징금 (PIPC 부과 시에만, KR 관할은 해킹 상한 가드)",
            "PIPC 와 같은 분기 (재량: 롯데카드 선례는 PIPC 의결 뒤 약 4.5개월)",
            "롯데카드: PIPC 96.2억, 금융위원회 50억(신용정보법 해킹 상한) 비율. 상한에 걸린 "
            "사례라 하한 성격", _EV_SECONDARY),
    AIParam("AI-03", "customer_redress", "op", "REV 대비 비율", (0.0005, 0.0159, 0.0393),
            "전 기관, 고객 보상·통지·포렌식", "첫 분기 50%, 둘째 분기 50%",
            "심각: SKT 2025 보상 약 5,000억 / 별도매출 약 12.7조 = 약 3.93%. 기준·악화는 재량",
            _EV_SECONDARY),
    AIParam("AI-03", "suspension_months", "driver", "개월", (0.0, 1.5, 4.5),
            "신규영업 일부정지 기간. 일실수익 산식에만 쓴다",
            "금융위원회 의결 다음 분기부터 (재량: 선례는 의결 다음 날 시작)",
            "롯데카드: 금융위원회 최종 1.5개월, 금융감독원 원안 4.5개월", _EV_SECONDARY),
    AIParam("AI-03", "suspension_revenue_share", "nonop",
            "정지 대상 신규취급의 연 REV 기여 비중", (0.10, 0.10, 0.10),
            "전 기관, 일실수익 = REV x 비중 x 정지개월/12", "정지 분기",
            "재량: 국내 은행 정지 대상 수익 비중 공개 근거 없음", _EV_DISCRETION),
    AIParam("AI-03", "attrition_nii", "nonop", "연 NII 대비 비율 (분기 1/4 누적)",
            (0.0, 0.01, 0.03), "전 기관, 고객 이탈 이자이익 감소", "둘째~다섯째 분기",
            "재량. SKT 영업이익 감소는 통신업 이탈이 섞여 크기 이전 불가", _EV_DISCRETION),
    AIParam("AI-03", "retail_stable", "runoff", "이탈률 가산 (소수)", (0.0, 0.02, 0.05),
            "LCR 안정 소매예금 (기본 5%)", "첫 두 분기",
            "재량 가설값. SVB 하루 24% 는 무보호 법인예금 사례이고 Fed Bowman(2026-09-18) "
            "위탁 검토가 SNS 촉발·가속을 부정", _EV_DISCRETION),
    AIParam("AI-03", "retail_less_stable", "runoff", "이탈률 가산 (소수)",
            (0.0, 0.05, 0.10), "LCR 불안정 소매예금 (기본 10%)", "첫 두 분기",
            "재량 가설값 (위와 같음)", _EV_DISCRETION),
    # ---- AI-04
    AIParam("AI-04", "interest_redress", "op", "NP_EAD 대비 비율",
            (0.002, 0.01, 0.03), "자연인 IRB 익스포저, 과다 가산금리 소급 환급",
            "탐지 다음 분기",
            "재량 (0.2%p x 1년 / 0.5%p x 2년 / 1.0%p x 3년). CFPB 2024 Apple/Goldman 약 "
            "USD 89m 은 분모가 없어 크기 비교 불가", _EV_DISCRETION),
    AIParam("AI-04", "chatbot_fee_refund", "op", "연 FEE 대비 비율", (0.002, 0.01, 0.03),
            "전 기관, 챗봇 오안내 수수료 환불", "탐지 다음 분기",
            "Air Canada 2024 Moffatt 판정은 책임 선례이며 크기 근거가 아니다. 크기는 재량",
            _EV_DISCRETION),
    AIParam("AI-04", "conduct_sanction", "fine", "환급 합계 대비 배수",
            (0.5, 0.75, 1.0), "전 기관, 금융소비자 보호 제재", "탐지일 + 4/7/11개월",
            "재량", _EV_DISCRETION),
    AIParam("AI-04", "origination_halt_months", "driver", "개월", (0.0, 1.5, 4.5),
            "자연인 자동심사 정지 기간. 일실수익 = REV x NP_SHARE x 개월/12 (nonop)",
            "탐지 분기부터",
            "롯데카드 영업 일부정지 1.5개월·원안 4.5개월을 자발적 정지에 전이한 재량",
            _EV_DISCRETION),
    AIParam("AI-04", "sa_fallback_natural_person", "fallback",
            "적용 플래그 (1 = 판정 수행)", (0, 1, 1),
            "주택담보·기타소매 고영향 AI 사용 제한, 무완화 규칙",
            "악화 두 분기, 심각 네 분기 (탐지 다음 분기부터)", "재량", _EV_DISCRETION),
    AIParam("AI-04", "eu_ai_act_floor", "rule", "REV 대비 비율", (0.0, 0.0, 0.03),
            "EU 기관만. 탐지일이 2027-12-02 이후일 때 제재 = max(행위 제재, 비율 x REV)",
            "활성 시 제재 분기",
            "EU AI Act Art. 99 고위험 의무 위반 EUR 15m 또는 3%, 신용평가 고위험 의무 "
            "2027-12-02 로 연기", _EV_SECONDARY),
    # ---- AI-05
    AIParam("AI-05", "full_outage_days", "driver", "일", (3, 5, 13),
            "핵심업무서비스 완전중단 일수", "첫 분기",
            "SGI서울보증 랜섬웨어 2025 약 3일, CrowdStrike 2024 Delta 5일, 국가정보자원관리원 "
            "화재 2025 13일 경과 시점 복구율 25.5%", _EV_SECONDARY),
    AIParam("AI-05", "partial_outage_days_at_50pct", "driver", "일", (2, 5, 45),
            "50% 부분운영 일수", "첫 분기",
            "재량. NIRS 2025 장기 꼬리는 질적 근거", _EV_DISCRETION),
    AIParam("AI-05", "fee_income_lost", "nonop",
            "연 FEE 대비 비율 = (완전중단일 + 0.5 x 부분운영일)/365", (0.0110, 0.0205, 0.0973),
            "전 기관, 장애 중 이자는 발생하므로 수수료만", "첫 분기",
            "산식 재량, 일수는 두 driver", _EV_DISCRETION),
    AIParam("AI-05", "remediation_and_compensation", "op", "BI 대비 비율",
            (0.002, 0.008, 0.02), "전 기관, 복구·실패거래 보상·FDS 중단 중 사기 누수",
            "첫 분기",
            "규모 앵커: CrowdStrike 2024 Fortune 500 직접손실 USD 5.4bn, 은행업 1.149bn, "
            "기업당 평균 44m (Parametrix 추정, 검색 요약). BI 비율은 재량", _EV_DISCRETION),
    AIParam("AI-05", "outage_sanction", "fine", "remediation_and_compensation 대비 배수",
            (0.0, 0.5, 1.49), "전 기관, 전자금융·운영복원력 제재", "사고일 + 4/7/11개월",
            "심각: TSB 2018 IT 이전 사고 제재 GBP 48.65m / 보상 32.7m = 1.49. 악화 0.5 재량",
            _EV_SECONDARY),
    AIParam("AI-05", "retail_stable", "runoff", "이탈률 가산 (소수)", (0.0, 0.01, 0.03),
            "LCR 안정 소매예금", "첫 분기", "재량 가설값", _EV_DISCRETION),
    AIParam("AI-05", "retail_less_stable", "runoff", "이탈률 가산 (소수)",
            (0.0, 0.03, 0.08), "LCR 불안정 소매예금", "첫 분기", "재량 가설값",
            _EV_DISCRETION),
    # ---- AI-06
    AIParam("AI-06", "exposure_quarters", "driver", "분기", (2, 3, 5),
            "대체 모형 승인까지 사기 노출 분기 수", "첫 분기부터", "재량", _EV_DISCRETION),
    AIParam("AI-06", "shared_model_fraud", "op", "REV 대비 비율", (0.002, 0.0115, 0.023),
            "전 기관, 자기자금 편취와 고객 배상 (노출기간 합계)", "노출기간 균등",
            "악화: Arup 2024 딥페이크 CFO 화상회의 HK$200m, 총비용 GBP 25.4m = 매출 약 "
            "1.15%. 기준·심각은 재량", _EV_SECONDARY),
    AIParam("AI-06", "no_fault_liability", "op", "REV 대비 연간 비율 (분기 1/4 누적)",
            (0.0, 0.005, 0.0128), "전 기관, 보이스피싱·딥페이크 무과실 배상 (입법 조건부)",
            "넷째 분기부터 시계 끝까지",
            "재량. 심각 = 0.005 x 2.56, 2.56 은 금융위원회 추정 업계부담 연 1,098억~2,811억 "
            "범위의 상하단 비", _EV_DISCRETION),
    AIParam("AI-06", "run_cost_uplift", "nonop", "연 OPEX 대비 비율 (분기 1/4 누적)",
            (0.005, 0.015, 0.03), "전 기관, 가격 인상·정책변경 대응 운영비",
            "둘째 분기부터 시계 끝까지", "재량. BR-055 가격 항목", _EV_DISCRETION),
    AIParam("AI-06", "migration_revalidation", "nonop", "BI 대비 비율",
            (0.001, 0.003, 0.008), "전 기관, 대체 모델 도입·재검증",
            "둘째 분기 50%, 셋째 분기 50%", "SR 11-7 · PRA SS1/23 재검증 요구는 질적 근거. "
            "크기는 재량", _EV_DISCRETION),
    # ---- AI-07
    AIParam("AI-07", "lookback_reperformance", "op", "REV 대비 비율",
            (0.001, 0.003, 0.005), "전 기관, 외부 전문가 소급 재수행·포렌식",
            "둘째 분기 50%, 셋째 분기 50%", "재량. BCBS d516 추적성·사고관리 원칙은 질적 근거",
            _EV_DISCRETION),
    AIParam("AI-07", "recordkeeping_sanction", "fine", "REV 대비 비율", (0.0, 0.002, 0.008),
            "전 기관, 기록보존·내부통제 위반 제재", "탐지일 + 4/7/11개월",
            "재량. 동양생명 금융감독원 원안 약 1,402억 대비 금융위원회 최종 70.23억(약 5%)은 "
            "제재 수준 불확실성의 참고", _EV_DISCRETION),
    AIParam("AI-07", "supervisory_moc", "pd_capital", "PD 배수", (1.0, 1.05, 1.10),
            "IRB 모형산출 3개 자산군 감독 보수성 배수. 자본 산출(RWA·산출하한 분모) 전용이며 "
            "IFRS 9 ECL 에는 넣지 않는다", "셋째~여섯째 분기",
            "재량. SR 11-7 · PRA SS1/23 보수성 원칙, CRE36 문서화 요건", _EV_DISCRETION),
    AIParam("AI-07", "sa_fallback_all", "fallback", "적용 플래그 (1 = 판정 수행)",
            (0, 0, 1), "3개 자산군 승인 효력 정지 판정, 무완화 규칙", "셋째~여섯째 분기",
            "재량", _EV_DISCRETION),
    # ---- 공통 규칙
    AIParam("AI-01", "sanction_lag_months", "rule", "개월", SANCTION_LAG_MONTHS,
            "전 시나리오 공통. 사고일(탐지형은 탐지일) 기준 제재 시차", "날짜가 속한 분기",
            _LAG, _EV_SECONDARY),
    AIParam("AI-01", "op_loss_10y_addon", "rule", "누적 운영손실 산입액 대비 배수",
            (0.1, 0.1, 0.1),
            "전 시나리오 공통. op 와 fine 누적의 1/10 을 10년 평균손실에 가산", "매 분기 누적",
            "OPE25 ILM: LC = 15 x 10년 평균손실 (risk_lib/capital/op_risk.py). 과징금의 "
            "손실자료 포함은 OPE25 원문 미확인", _EV_CODE),
)
_PARAM = {(p.scenario_id, p.channel): p for p in PARAMS}


def param(scenario_id: str, channel: str, severity: str) -> float:
    return _PARAM[(scenario_id, channel)].at(severity)


# --------------------------------------------------------------------------- 시점
def _q_parse(label: str) -> tuple[int, int]:
    return int(label[:4]), int(label[-1])


def _q_start(label: str) -> date:
    y, q = _q_parse(label)
    return date(y, 3 * (q - 1) + 1, 1)


def _add_months(d: date, months: float) -> date:
    whole = int(math.floor(months))
    m0 = d.month - 1 + whole
    y, m = d.year + m0 // 12, m0 % 12 + 1
    day = min(d.day, calendar.monthrange(y, m)[1])
    out = date(y, m, day)
    frac = months - whole
    if frac:
        out = date.fromordinal(out.toordinal() + int(round(frac * 30)))
    return out


def _q_of(d: date, quarters: list[str]) -> int | None:
    """날짜가 속한 분기의 인덱스. 시계 앞이면 0, 시계 뒤면 None."""
    label = f"{d.year}Q{(d.month - 1) // 3 + 1}"
    if label in quarters:
        return quarters.index(label)
    if label < quarters[0]:
        return 0
    return None


@dataclass(frozen=True)
class Timeline:
    quarters: tuple[str, ...]
    incident_date: date
    detection_date: date

    @property
    def n(self) -> int:
        return len(self.quarters)

    def q(self, d: date) -> int | None:
        return _q_of(d, list(self.quarters))

    def sanction_q(self, severity: str, *, detected: bool = False,
                   start: date | None = None) -> int | None:
        base = start or (self.detection_date if detected else self.incident_date)
        return self.q(_add_months(base, SANCTION_LAG_MONTHS[_IX[severity]]))


def timeline(quarters: list[str]) -> Timeline:
    q0 = _q_start(quarters[0])
    inc = date.fromordinal(q0.toordinal() + INCIDENT_DAY_OFFSET)
    return Timeline(tuple(quarters), inc, _add_months(inc, DETECTION_LAG_MONTHS))


# --------------------------------------------------------------------------- 계획
@dataclass
class Plan:
    """한 (시나리오, 심도)의 성분. 금액은 원화, 가중치는 {분기: 비중}.

    가중치의 분기가 시계 밖(>= n)이어도 버리거나 앞당기지 않는다. 누적(_cum)이
    시계 안 분기만 더하므로 시계 밖 몫은 자본 경로에 들어가지 않고, 영향 요약의
    시계 밖 금액 열(_oob)로 남는다. 과징금은 add_fine 이 같은 규칙으로 따로 모은다.
    """
    op: list[tuple[float, dict[int, float]]] = field(default_factory=list)
    nonop: list[tuple[float, dict[int, float]]] = field(default_factory=list)
    fine: list[tuple[float, dict[int, float]]] = field(default_factory=list)
    fine_out_of_horizon: float = 0.0
    pd: list[tuple[str, float, int, int]] = field(default_factory=list)
    # 자본 산출 전용 PD 배수 (감독 보수성). ECL 에는 들어가지 않는다.
    pd_capital: list[tuple[str, float, int, int]] = field(default_factory=list)
    lgd: tuple[float, int, int] | None = None
    runoff: tuple[tuple[tuple[str, float], ...], int, int] | None = None
    fallback: tuple[tuple[str, ...], int, int] | None = None
    tolerance_breach_days: float | None = None
    revenue_lost: float = 0.0
    flags: list[str] = field(default_factory=list)

    def add_fine(self, amount: float, q: int | None) -> None:
        if amount <= 0:
            return
        if q is None:
            self.fine_out_of_horizon += amount
        else:
            self.fine.append((amount, {q: 1.0}))


@dataclass(frozen=True)
class Scale:
    REV: float
    BI: float
    OPEX: float
    FEE: float
    NII: float
    NP_EAD: float
    NP_SHARE: float

    @classmethod
    def of(cls, books: StressBooks) -> "Scale":
        irb = books.irb
        np_ead = float(irb.loc[irb["asset_class"].isin(NATURAL_PERSON), "ead"].sum())
        total = float(books.full["ead"].sum()) or 1.0
        rev = float(books.revenue)
        return cls(REV=rev, BI=float(books.bi.bi), OPEX=float(books.operating_cost),
                   FEE=rev * FEE_SHARE, NII=rev * INTEREST_SHARE_OF_REVENUE,
                   NP_EAD=np_ead, NP_SHARE=np_ead / total)


def _even(a: int, z: int) -> dict[int, float]:
    return {o: 1.0 / (z - a + 1) for o in range(a, z + 1)}


def _flow(a: int, n: int, annual: float) -> list[tuple[float, dict[int, float]]]:
    """연율 흐름을 분기 1/4 씩 a 분기부터 시계 끝까지."""
    return [(annual / 4.0, {o: 1.0}) for o in range(a, n)]


def _scaled_pd(m: float, k: float) -> float:
    return 1.0 + k * (m - 1.0)


def plan_ai01(s: Scale, sev: str, tl: Timeline, k: float = 1.0, **_) -> Plan:
    p = Plan()
    loss = k * 0.002 * param("AI-01", "kill_latency_minutes", sev) * s.BI
    p.op.append((loss, {0: 1.0}))
    p.add_fine(param("AI-01", "regulatory_sanction", sev) * loss, tl.sanction_q(sev))
    ro = k * param("AI-01", "corporate_non_operational", sev)
    if ro:
        p.runoff = ((("corporate_non_operational", ro),), 0, 0)
    return p


def plan_ai02(s: Scale, sev: str, tl: Timeline, k: float = 1.0, *, lgd: bool = True,
              start: int = 1, fallback: bool = True, **_) -> Plan:
    p = Plan()
    m = min(_scaled_pd(param("AI-02", "pd_multiplier", sev), k),
            1.0 + k * (PD_MULTIPLIER_CAP - 1.0))
    p.pd = [(cl, m, start, tl.n - 1) for cl in IRB3]
    add = k * param("AI-02", "lgd_addon", sev)
    if lgd and add:
        p.lgd = (add, start, tl.n - 1)
    if fallback and param("AI-02", "sa_fallback_corporate", sev):
        p.fallback = (("corporate",), start, min(start + 3, tl.n - 1))
    return p


def plan_ai03(s: Scale, sev: str, tl: Timeline, k: float = 1.0, *,
              incident: date | None = None, jurisdiction: str = "", **_) -> Plan:
    p = Plan()
    t0 = tl.q(incident or tl.incident_date) or 0
    fq = tl.sanction_q(sev, start=incident or tl.incident_date)
    pipc = k * param("AI-03", "pipc_fine", sev) * s.REV
    fsc = param("AI-03", "fsc_fine", sev) * pipc if pipc > 0 else 0.0
    if jurisdiction == "KR" and fsc > KR_CREDIT_INFO_HACKING_CAP:
        fsc = KR_CREDIT_INFO_HACKING_CAP
        p.flags.append("fsc_capped")
    p.add_fine(pipc, fq)
    p.add_fine(fsc, fq)
    redress = k * param("AI-03", "customer_redress", sev) * s.REV
    p.op.append((redress, {t0: 0.5, t0 + 1: 0.5}))
    months = param("AI-03", "suspension_months", sev)
    susp = k * s.REV * param("AI-03", "suspension_revenue_share", sev) * months / 12.0
    if susp > 0:
        # 의결이 시계 밖이면 정지도 시계 밖이다. 시계 끝 다음 분기로 두어 _oob 로 남긴다.
        first = (fq if fq is not None else tl.n) + 1
        w = ({first: 1.0} if months <= 3 else
             {first: 3.0 / months, first + 1: (months - 3.0) / months})
        p.nonop.append((susp, w))
        p.revenue_lost += susp
    att = k * param("AI-03", "attrition_nii", sev) * s.NII
    if att > 0:
        p.nonop.append((att, _even(t0 + 1, t0 + 4)))
        p.revenue_lost += att
    rs = tuple((c, k * param("AI-03", c, sev)) for c in RETAIL_RUNOFF
               if param("AI-03", c, sev))
    if rs:
        p.runoff = (rs, t0, min(t0 + 1, tl.n - 1))
    return p


def plan_ai04(s: Scale, sev: str, tl: Timeline, k: float = 1.0, *,
              jurisdiction: str = "", **_) -> Plan:
    p = Plan()
    det = tl.q(tl.detection_date) or 0
    redress = k * (param("AI-04", "interest_redress", sev) * s.NP_EAD
                   + param("AI-04", "chatbot_fee_refund", sev) * s.FEE)
    rq = det + 1
    p.op.append((redress, {rq: 1.0}))
    fine = param("AI-04", "conduct_sanction", sev) * redress
    if (jurisdiction == "EU" and tl.detection_date >= EU_AI_ACT_HIGH_RISK_DATE):
        fine = max(fine, k * param("AI-04", "eu_ai_act_floor", sev) * s.REV)
    p.add_fine(fine, tl.sanction_q(sev, detected=True))
    months = param("AI-04", "origination_halt_months", sev)
    halt = k * s.REV * s.NP_SHARE * months / 12.0
    if halt > 0:
        w = ({det: 1.0} if months <= 3 else
             {det: 3.0 / months, det + 1: (months - 3.0) / months})
        p.nonop.append((halt, w))
        p.revenue_lost += halt
    if param("AI-04", "sa_fallback_natural_person", sev):
        span = 1 if sev == "adverse" else 3
        p.fallback = (NATURAL_PERSON, rq, min(rq + span, tl.n - 1))
    return p


def plan_ai05(s: Scale, sev: str, tl: Timeline, k: float = 1.0, **_) -> Plan:
    p = Plan()
    full = param("AI-05", "full_outage_days", sev)
    part = param("AI-05", "partial_outage_days_at_50pct", sev)
    lost = k * s.FEE * (full + 0.5 * part) / 365.0
    rem = k * param("AI-05", "remediation_and_compensation", sev) * s.BI
    p.op.append((rem, {0: 1.0}))
    p.nonop.append((lost, {0: 1.0}))
    p.revenue_lost += lost
    p.add_fine(param("AI-05", "outage_sanction", sev) * rem, tl.sanction_q(sev))
    rs = tuple((c, k * param("AI-05", c, sev)) for c in RETAIL_RUNOFF
               if param("AI-05", c, sev))
    if rs:
        p.runoff = (rs, 0, 0)
    p.tolerance_breach_days = max(0.0, full + part - IMPACT_TOLERANCE_DAYS)
    return p


def plan_ai06(s: Scale, sev: str, tl: Timeline, k: float = 1.0, **_) -> Plan:
    p = Plan()
    fraud = k * param("AI-06", "shared_model_fraud", sev) * s.REV
    win = int(param("AI-06", "exposure_quarters", sev))
    p.op.append((fraud, _even(0, win - 1)))
    nf = k * param("AI-06", "no_fault_liability", sev) * s.REV
    if nf:
        p.op += _flow(3, tl.n, nf)
    p.nonop += _flow(1, tl.n, k * param("AI-06", "run_cost_uplift", sev) * s.OPEX)
    mig = k * param("AI-06", "migration_revalidation", sev) * s.BI
    p.nonop.append((mig, {1: 0.5, 2: 0.5}))
    return p


def plan_ai07(s: Scale, sev: str, tl: Timeline, k: float = 1.0, **_) -> Plan:
    p = Plan()
    det = tl.q(tl.detection_date) or 0
    rem = k * param("AI-07", "lookback_reperformance", sev) * s.REV
    p.op.append((rem, {det: 0.5, det + 1: 0.5}))
    p.add_fine(k * param("AI-07", "recordkeeping_sanction", sev) * s.REV,
               tl.sanction_q(sev, detected=True))
    m = _scaled_pd(param("AI-07", "supervisory_moc", sev), k)
    a, z = det + 1, min(det + 4, tl.n - 1)
    if m > 1.0:
        p.pd_capital = [(cl, m, a, z) for cl in IRB3]
    if param("AI-07", "sa_fallback_all", sev):
        p.fallback = (IRB3, a, z)
    return p


PLANS = {"AI-01": plan_ai01, "AI-02": plan_ai02, "AI-03": plan_ai03,
         "AI-04": plan_ai04, "AI-05": plan_ai05, "AI-06": plan_ai06,
         "AI-07": plan_ai07}


def merge(*plans: Plan) -> Plan:
    out = Plan()
    for p in plans:
        out.op += p.op
        out.nonop += p.nonop
        out.fine += p.fine
        out.fine_out_of_horizon += p.fine_out_of_horizon
        out.pd += p.pd
        out.pd_capital += p.pd_capital
        out.revenue_lost += p.revenue_lost
        out.flags += p.flags
        for attr in ("lgd", "runoff", "fallback"):
            if getattr(p, attr) is not None:
                if getattr(out, attr) is not None:
                    raise ValueError(f"결합 계획에서 {attr} 창이 겹친다")
                setattr(out, attr, getattr(p, attr))
    return out


def _cum(parts: list[tuple[float, dict[int, float]]], q: int) -> float:
    return sum(a * sum(w for o, w in ws.items() if o <= q) for a, ws in parts)


def _oob(parts: list[tuple[float, dict[int, float]]], n: int) -> float:
    """시계 밖(분기 >= n) 몫의 합."""
    return sum(a * sum(w for o, w in ws.items() if o >= n) for a, ws in parts)


def overlay_at(plan: Plan, q: int) -> tuple[StressOverlay, tuple[str, ...], dict]:
    op, nonop, fine = _cum(plan.op, q), _cum(plan.nonop, q), _cum(plan.fine, q)
    pdm: dict[str, float] = {}
    for cl, m, a, z in plan.pd:
        if a <= q <= z:
            pdm[cl] = pdm.get(cl, 1.0) * m
    pdc: dict[str, float] = {}
    for cl, m, a, z in plan.pd_capital:
        if a <= q <= z:
            pdc[cl] = pdc.get(cl, 1.0) * m
    ax = ()
    if plan.lgd and plan.lgd[1] <= q <= plan.lgd[2] and plan.lgd[0] > 0:
        ax = (("lgd_addon", float(plan.lgd[0])),)
    ro = ()
    if plan.runoff and plan.runoff[1] <= q <= plan.runoff[2]:
        ro = tuple((c, float(v)) for c, v in plan.runoff[0] if v > 0)
    fb = ()
    if plan.fallback and plan.fallback[1] <= q <= plan.fallback[2]:
        fb = tuple(plan.fallback[0])
    ov = StressOverlay(axis_addons=ax, direct_loss=op + nonop, post_tax_charge=fine,
                       op_loss_10y_addon=(op + fine) / 10.0,
                       pd_multiplier=tuple(sorted(pdm.items())),
                       pd_multiplier_capital=tuple(sorted(pdc.items())), runoff_addon=ro)
    both = {cl: pdm.get(cl, 1.0) * pdc.get(cl, 1.0) for cl in set(pdm) | set(pdc)}
    parts = {"op": op, "nonop": nonop, "fine": fine,
             "pd": max(both.values()) if both else 1.0,
             "lgd": ax[0][1] if ax else 0.0,
             "runoff": max((v for _, v in ro), default=0.0)}
    return ov, fb, parts


# --------------------------------------------------------------------------- 산출
@dataclass
class _Ctx:
    books: StressBooks
    buffers: dict | None
    base: dict
    macro: dict[str, list[float]]
    macro_vals: dict[tuple[str, int], dict]

    def macro_point(self, path: str | None, q: int) -> dict:
        if path is None:
            return self.base
        key = (path, q)
        if key not in self.macro_vals:
            self.macro_vals[key] = evaluate_point(
                self.books, self.macro[path][q], buffers=self.buffers,
                base=self.base).values
        return self.macro_vals[key]


def _eval(ctx: _Ctx, plan: Plan, q: int, path: str | None) -> tuple[dict, float | None, dict]:
    sev = 0.0 if path is None else ctx.macro[path][q]
    ov, fb, parts = overlay_at(plan, q)
    v = evaluate_point(ctx.books, sev, buffers=ctx.buffers, base=ctx.base,
                       overlay=ov).values
    relief = None
    if fb:
        v2 = evaluate_point(ctx.books, sev, buffers=ctx.buffers, base=ctx.base,
                            overlay=replace(ov, sa_fallback=fb)).values
        relief = v["rwa_total"] - v2["rwa_total"]
        parts["fallback_adopted"] = bool(v2["rwa_total"] > v["rwa_total"])
        if v2["rwa_total"] > v["rwa_total"]:
            v = v2
    return v, relief, parts


def _surplus(v: dict) -> float:
    """구속 계층 잉여 (원화). CET1·Tier1·총자본 요구치(완충 포함) 가운데 가장 빠듯한
    계층의 잉여다. 엔진 판정(passes)과 같은 기준이다."""
    return float(v["binding_surplus"] * v["rwa_total"])


def _cet1_surplus(v: dict) -> float:
    """CET1 계층만의 잉여 (원화)."""
    return float(v["cet1"] - v["cet1_required"] * v["rwa_total"])


def _binding_tier(v: dict) -> str:
    return ("cet1", "tier1", "total")[int(v["binding_index"])]


def _breached_tiers(v: dict) -> str:
    """요구치 미달 계층을 '계층 비율 < 요구' 로 적는다. 없으면 빈 문자열."""
    out = [f"{TIER_KO[k]} {v[f'{k}_ratio']:.2%} < {v[f'{k}_required']:.2%}"
           for k in ("cet1", "tier1", "total") if v[f"{k}_surplus"] < 0]
    return ", ".join(out)


def _path_rows(ctx: _Ctx, tl: Timeline, sid: str, sev_key: str, plan: Plan,
               path: str | None) -> list[dict]:
    rows = []
    for q in range(tl.n):
        vm = ctx.macro_point(path, q)
        v, relief, parts = _eval(ctx, plan, q, path)
        rows.append({
            "scenario_id": sid, "severity_key": sev_key, "quarter": tl.quarters[q],
            "q_index": q,
            "macro_severity": 0.0 if path is None else float(ctx.macro[path][q]),
            "loss_op_cum": parts["op"], "loss_nonop_cum": parts["nonop"],
            "fine_cum": parts["fine"],
            "op_loss_10y_addon": (parts["op"] + parts["fine"]) / 10.0,
            "pd_multiplier": parts["pd"], "lgd_addon": parts["lgd"],
            "runoff_addon_max": parts["runoff"],
            "sa_fallback_tested": relief is not None,
            "sa_fallback_adopted": bool(parts.get("fallback_adopted", False)),
            "relief_forgone": (float(relief) if relief is not None and relief > 0
                               else (0.0 if relief is not None else None)),
            "cet1": float(v["cet1"]), "cet1_ratio": float(v["cet1_ratio"]),
            "cet1_ratio_macro": float(vm["cet1_ratio"]),
            "delta_cet1_bp": float((v["cet1_ratio"] - vm["cet1_ratio"]) * 1e4),
            "delta_cet1": float(v["cet1"] - vm["cet1"]),
            "rwa_total": float(v["rwa_total"]), "rwa_op": float(v["rwa_op"]),
            "delta_rwa_op": float(v["rwa_op"] - vm["rwa_op"]),
            "delta_rwa_total": float(v["rwa_total"] - vm["rwa_total"]),
            "ecl": float(v["ecl"]), "delta_ecl": float(v["ecl"] - vm["ecl"]),
            "lcr": float(v["lcr"]), "lcr_macro": float(vm["lcr"]),
            "pre_tax_income": float(v["pre_tax_income"]),
            "cet1_surplus": _cet1_surplus(v),
            "capital_surplus": _surplus(v),
            "binding_tier": _binding_tier(v),
            "passes": bool(_surplus(v) >= 0.0),
            "interaction_bp": None,
        })
    return rows


@dataclass
class AIIncidentResult:
    scenario: pd.DataFrame
    param: pd.DataFrame
    path: pd.DataFrame
    impact: pd.DataFrame
    reverse: pd.DataFrame
    base: dict
    published: dict
    institution_code: str
    quarters: list[str]
    flags: dict[str, list[str]] = field(default_factory=dict)

    def tables(self) -> dict[str, pd.DataFrame]:
        return {"st_ai_scenario": self.scenario, "st_ai_param": self.param,
                "st_ai_path": self.path, "st_ai_impact": self.impact,
                "st_ai_reverse": self.reverse}

    def worst(self) -> pd.Series:
        sev = self.impact[(self.impact["severity_key"] == "severely_adverse")
                          & self.impact["scenario_id"].isin(STANDALONE_IDS)]
        return sev.loc[sev["delta_cet1_bp"].idxmin()]


def _impact_row(rows: list[dict], plan: Plan, scale: Scale) -> dict:
    df = pd.DataFrame(rows)
    i = int(df["cet1_ratio"].idxmin())
    j = int(df["lcr"].idxmin())
    t = df.loc[i]
    last = df.iloc[-1]
    return {
        "scenario_id": t["scenario_id"], "severity_key": t["severity_key"],
        "severity_label": SEVERITY_KO[t["severity_key"]],
        "trough_quarter": t["quarter"],
        "cet1_ratio_reference": float(t["cet1_ratio_macro"]),
        "cet1_ratio_trough": float(t["cet1_ratio"]),
        "delta_cet1_bp": float(df["delta_cet1_bp"].min()),
        "delta_cet1_bp_at_trough": float(t["delta_cet1_bp"]),
        "cet1_surplus_trough": float(df["cet1_surplus"].min()),
        "capital_surplus_trough": float(df["capital_surplus"].min()),
        "breach": bool((df["capital_surplus"] < 0).any()),
        "cet1_breach": bool((df["cet1_surplus"] < 0).any()),
        "cet1_ratio_end": float(last["cet1_ratio"]),
        "delta_cet1_bp_end": float(last["delta_cet1_bp"]),
        "lcr_min": float(df.loc[j, "lcr"]), "lcr_min_quarter": df.loc[j, "quarter"],
        "loss_op_total": float(last["loss_op_cum"]),
        "loss_nonop_total": float(last["loss_nonop_cum"]),
        "fine_total": float(last["fine_cum"]),
        "fine_out_of_horizon": float(plan.fine_out_of_horizon),
        "loss_op_out_of_horizon": float(_oob(plan.op, len(df))),
        "loss_nonop_out_of_horizon": float(_oob(plan.nonop, len(df))),
        "delta_rwa_op_max": float(df["delta_rwa_op"].max()),
        "delta_ecl_max": float(df["delta_ecl"].max()),
        "relief_forgone_max": (float(df["relief_forgone"].dropna().max())
                               if df["relief_forgone"].notna().any() else None),
        "cum_loss_to_bi": float((last["loss_op_cum"] + last["loss_nonop_cum"]
                                 + last["fine_cum"]) / scale.BI) if scale.BI else 0.0,
        "revenue_lost_to_rev": (float(plan.revenue_lost / scale.REV)
                                if scale.REV else 0.0),
        "impact_tolerance_breach_days": plan.tolerance_breach_days,
    }


def _bisect(f, lo: float, hi: float, n: int = 32) -> float:
    """f(lo) > 0 이고 f(hi) <= 0 인 구간에서 f = 0 근을 찾는다."""
    for _ in range(n):
        mid = 0.5 * (lo + hi)
        if f(mid) > 0:
            lo = mid
        else:
            hi = mid
    return hi


def _reverse_capital(ctx: _Ctx, tl: Timeline, scale: Scale, impact: pd.DataFrame,
                     jurisdiction: str, surplus_fn, suffix: str,
                     tier_ko: str) -> list[dict]:
    """자본 임계 지표. surplus_fn 이 판정 계층을 정한다 (구속 3계층 또는 CET1)."""
    rows = []
    base = ctx.base
    surplus0 = surplus_fn(base)
    breached = surplus0 < 0
    # 미달 계층의 비율은 보고서·2선 상세에 적는다. 비고는 고정 문구로 두어 영문 빌드가 옮긴다.
    why = f"기준점이 이미 {tier_ko} 요구치 미달"

    def surplus_of(ov: StressOverlay) -> float:
        return surplus_fn(evaluate_point(ctx.books, 0.0, buffers=ctx.buffers,
                                         base=base, overlay=ov).values)

    def row(mid, ko, value, unit, note, *, resilient=False):
        rows.append({"metric_id": mid + suffix, "metric": f"{ko} [{tier_ko}]",
                     "value": value, "unit": unit, "already_breached": bool(breached),
                     "resilient": bool(resilient), "note": note})

    # 1. ILM 산입 세전손실 L*
    ko = "임계 세전 운영손실 / BI (ILM 경로 포함)"
    if breached:
        row("loss_star_bi", ko, 0.0, "ratio", why)
    else:
        hi = 10.0 * scale.BI
        f = lambda L: surplus_of(StressOverlay(direct_loss=L, op_loss_10y_addon=L / 10))
        if f(hi) > 0:
            row("loss_star_bi", ko, None, "ratio",
                "BI 10배 손실로도 요구치를 침범하지 않음", resilient=True)
        else:
            L = _bisect(f, 0.0, hi)
            row("loss_star_bi", ko, L / scale.BI, "ratio",
                f"세전 {L:,.0f} KRW. 세금차폐는 연간 세전이익 한도")
    # 1b. ILM 경로 없는 손익만 (닫힌꼴)
    P = max(float(base["pre_tax_income"]), 0.0)
    if breached:
        lstar0 = 0.0
    else:
        lstar0 = (surplus0 / (1 - TAX_RATE) if surplus0 <= (1 - TAX_RATE) * P
                  else surplus0 + TAX_RATE * P)
    row("loss_star_bi_no_ilm", "임계 세전손실 / BI (ILM 경로 제외, 닫힌꼴)",
        lstar0 / scale.BI if scale.BI else None, "ratio",
        why if breached else
        "운영 RWA 가 손실에 반응하지 않는 경우(ILM = 1 재량)의 손익 경로만")
    # 2. 세후 과징금 F*
    ko = "임계 세후 과징금 / REV"
    if breached:
        row("fine_star_rev", ko, 0.0, "ratio", why)
    else:
        hi = 10.0 * scale.REV
        f = lambda F: surplus_of(StressOverlay(post_tax_charge=F,
                                               op_loss_10y_addon=F / 10))
        if f(hi) > 0:
            row("fine_star_rev", ko, None, "ratio", "REV 10배로도 미침범", resilient=True)
        else:
            F = _bisect(f, 0.0, hi)
            x = F / scale.REV
            if x <= PIPA_GENERAL_CAP:
                cmp = "개인정보위 과징금 일반 상한 안에서 침범 가능"
            elif x <= PIPA_AGGRAVATED_CAP:
                cmp = ("일반 상한 초과, 가중 상한 이내: 가중요건 충족 시 개인정보위 "
                       "과징금 단독으로 침범 가능")
            else:
                cmp = "가중 상한 초과: 개인정보위 과징금 단독으로는 침범하지 않음"
            row("fine_star_rev", ko, x, "ratio",
                f"세후 {F:,.0f} KRW (BI 대비 {F / scale.BI:.4f}). 개인정보보호법 "
                f"제64조의2 일반 상한 {PIPA_GENERAL_CAP:.2f}, 가중 상한 "
                f"{PIPA_AGGRAVATED_CAP:.2f} (전체 매출액 대비). {cmp}")
    # 3. 공통 PD 임계배수 m*
    ko = "모형오류 공통 PD 임계배수"
    if breached:
        row("pd_multiplier_star", ko, 1.0, "multiple", why)
    else:
        f = lambda m: surplus_of(StressOverlay(
            pd_multiplier=tuple((c, m) for c in IRB3)))
        if f(20.0) > 0:
            row("pd_multiplier_star", ko, None, "multiple", "PD 20배로도 미침범",
                resilient=True)
        else:
            row("pd_multiplier_star", ko, _bisect(f, 1.0, 20.0), "multiple",
                "IRB 3개 자산군 공통. retail_other 는 PD 상향이 RWA 를 낮출 수 있다")
    # 4. 시나리오 배율 k* (CET1 저점 분기 기준)
    for sid in STANDALONE_IDS:
        imp = impact[(impact["scenario_id"] == sid)
                     & (impact["severity_key"] == "severely_adverse")]
        q = tl.quarters.index(imp["trough_quarter"].iloc[0])

        def sur_k(kk, sid=sid, q=q):
            pl = PLANS[sid](scale, "severely_adverse", tl, kk, jurisdiction=jurisdiction)
            v, _, _ = _eval(ctx, pl, q, None)
            return surplus_fn(v)
        mid = f"scenario_k:{sid}"
        ko = f"{sid} 심각 벡터 임계 배율 (CET1 저점 분기 기준)"
        if breached:
            row(mid, ko, 0.0, "multiple", why)
        elif sur_k(1.0) <= 0:
            row(mid, ko, _bisect(sur_k, 0.0, 1.0, 20), "multiple",
                f"저점 {tl.quarters[q]}. 금액 x k, PD 배수 1 + k(m - 1)")
        elif sur_k(8.0) > 0:
            row(mid, ko, None, "multiple", "8배로도 미침범", resilient=True)
        else:
            row(mid, ko, _bisect(sur_k, 1.0, 8.0, 22), "multiple",
                f"저점 {tl.quarters[q]}. 금액 x k, PD 배수 1 + k(m - 1)")
    return rows


def _reverse_rows(ctx: _Ctx, tl: Timeline, scale: Scale, impact: pd.DataFrame,
                  jurisdiction: str) -> list[dict]:
    """역스트레스. 자본 지표는 구속 3계층(주 지표)과 CET1 계층(접미 _cet1) 두 벌,
    LCR 지표는 자체 기준(LCR 100%)으로 미달을 판정한다."""
    rows = _reverse_capital(ctx, tl, scale, impact, jurisdiction, _surplus, "",
                            "3계층")
    rows += _reverse_capital(ctx, tl, scale, impact, jurisdiction, _cet1_surplus,
                             "_cet1", "CET1")
    base = ctx.base
    lcr0 = float(base["lcr"])
    ko = "LCR 100% 를 만드는 소매예금 이탈률 가산"

    def row(value, note, *, resilient=False):
        rows.append({"metric_id": "lcr_retail_runoff_star", "metric": ko,
                     "value": value, "unit": "ratio",
                     "already_breached": bool(lcr0 < 1.0),
                     "resilient": bool(resilient), "note": note})
    if lcr0 < 1.0:
        row(0.0, "기준 LCR 이 이미 100% 미달")
    else:
        g = lambda x: evaluate_point(
            ctx.books, 0.0, buffers=ctx.buffers, base=base,
            overlay=StressOverlay(runoff_addon=tuple((c, x) for c in RETAIL_RUNOFF))
        ).values["lcr"] - 1.0
        if g(1.0) > 0:
            row(None, "전액 이탈로도 100% 유지", resilient=True)
        else:
            row(_bisect(g, 0.0, 1.0),
                "안정·불안정 소매예금에 같은 가산. 가설 AI 증폭 예금이탈은 이 임계와 "
                "비교만 한다")
    return rows


def run_ai_incident_stress(books: StressBooks, *, quarters: list[str],
                           buffers: dict | None = None,
                           institution_code: str = "",
                           published: dict | None = None) -> AIIncidentResult:
    """AI 사고 7종 x 심도 3 단독 경로, 결합 2종, 역스트레스를 산출한다.

    `books` 는 운영손실 10년 평균을 헤드라인과 같은 값으로 맞춘 장부여야 한다.
    `published` 는 대사용 헤드라인 값(cet1_ratio, rwa_total, rwa_op)이다.
    """
    tl = timeline(list(quarters))
    scale = Scale.of(books)
    jurisdiction = (institution_code or "KR")[:2].upper()
    base = evaluate_point(books, 0.0, buffers=buffers).values
    macro = {p.name: p.severities(tl.n) for p in DEFAULT_STRESS_PATHS}
    ctx = _Ctx(books, buffers, base, macro, {})

    path_rows: list[dict] = []
    impact_rows: list[dict] = []
    flags: dict[str, list[str]] = {}
    for sid in STANDALONE_IDS:
        for sev in SEVERITIES:
            plan = PLANS[sid](scale, sev, tl, jurisdiction=jurisdiction)
            rows = _path_rows(ctx, tl, sid, sev, plan, None)
            path_rows += rows
            impact_rows.append(_impact_row(rows, plan, scale))
            if plan.flags:
                flags[f"{sid}:{sev}"] = list(plan.flags)

    # 결합 AI-C1: 거시 심각 + AI-02 악화(PD 만, 셋째 분기부터) + AI-03 악화(탐지 시점 사고)
    c1_a2 = plan_ai02(scale, "adverse", tl, lgd=False, start=2, fallback=False)
    c1_a3 = plan_ai03(scale, "adverse", tl, incident=tl.detection_date,
                      jurisdiction=jurisdiction)
    c1 = merge(c1_a2, c1_a3)
    rows = _path_rows(ctx, tl, "AI-C1", "combined", c1, "severely_adverse")
    r2 = _path_rows(ctx, tl, "AI-C1", "combined", c1_a2, "severely_adverse")
    r3 = _path_rows(ctx, tl, "AI-C1", "combined", c1_a3, "severely_adverse")
    for r, a, b in zip(rows, r2, r3):
        r["interaction_bp"] = r["delta_cet1_bp"] - a["delta_cet1_bp"] - b["delta_cet1_bp"]
    path_rows += rows
    impact_rows.append(_impact_row(rows, c1, scale))
    # 결합 AI-C2: 거시 심각 + AI-03 심각
    c2 = plan_ai03(scale, "severely_adverse", tl, jurisdiction=jurisdiction)
    rows = _path_rows(ctx, tl, "AI-C2", "combined", c2, "severely_adverse")
    path_rows += rows
    impact_rows.append(_impact_row(rows, c2, scale))

    path = pd.DataFrame(path_rows)
    impact = pd.DataFrame(impact_rows)
    reverse = pd.DataFrame(_reverse_rows(ctx, tl, scale, impact, jurisdiction))
    return AIIncidentResult(
        scenario=scenario_frame(), param=param_frame(), path=path, impact=impact,
        reverse=reverse, base=dict(base), published=dict(published or {}),
        institution_code=institution_code, quarters=list(quarters), flags=flags)


def scenario_frame() -> pd.DataFrame:
    return pd.DataFrame([{
        "scenario_id": s.scenario_id, "scenario_name": s.name,
        "incident_class": s.incident_class, "br055": s.br055,
        "basel_event_type": s.basel_event_type, "timing_type": s.timing_type,
        "narrative": s.narrative, "trigger": s.trigger,
        "kill_switch_scope": s.kill_switch_scope, "recovery": s.recovery,
        "time_profile": s.time_profile, "requirement_refs": s.requirement_refs,
    } for s in SCENARIOS])


def param_frame() -> pd.DataFrame:
    rows = []
    for p in PARAMS:
        for sev in SEVERITIES:
            rows.append({"scenario_id": p.scenario_id, "channel": p.channel,
                         "channel_kind": p.kind, "severity_key": sev,
                         "value": p.at(sev), "unit": p.unit, "scope": p.scope,
                         "timing": p.timing, "citation": p.citation,
                         "evidence_status": p.evidence_status})
    return pd.DataFrame(rows)


# --------------------------------------------------------------------------- 원장 스펙
AI_SCENARIO = TableSpec(
    name="st_ai_scenario", korean="AI 사고 시나리오", product="PRD-ST",
    grain="AI 사고 시나리오 1건당 1행 (결합 포함)",
    columns=(
        C("scenario_id", "string", "시나리오 식별자", nullable=False),
        C("scenario_name", "text", "시나리오명", nullable=False),
        C("incident_class", "string", "사고분류 (BR-049)", nullable=False,
          allowed=INCIDENT_CLASSES),
        C("br055", "bool", "공급자 장애·공통모델 실패 (BR-055)", nullable=False),
        C("basel_event_type", "string", "바젤 운영손실 사건유형", nullable=True,
          note="catalog.OP_EVENT_TYPES 코드. 결합 시나리오는 NULL"),
        C("timing_type", "string", "시점 유형", nullable=False, allowed=TIMING_TYPES),
        C("narrative", "text", "서사", nullable=False),
        C("trigger", "text", "발생 조건", nullable=False),
        C("kill_switch_scope", "text", "차단 범위 (BR-050)", nullable=False),
        C("recovery", "text", "복구 가정 (BR-052)", nullable=False),
        C("time_profile", "text", "시점 구성", nullable=False),
        C("requirement_refs", "text", "관련 요건", nullable=False),
    ),
    primary_key=("scenario_id",),
)

AI_PARAM = TableSpec(
    name="st_ai_param", korean="AI 사고 시나리오 모수", product="PRD-ST",
    grain="시나리오 x 채널 x 심도 1건당 1행",
    columns=(
        C("scenario_id", "string", "시나리오 식별자", nullable=False),
        C("channel", "string", "채널", nullable=False),
        C("channel_kind", "string", "채널 종류", nullable=False, allowed=CHANNEL_KINDS),
        C("severity_key", "string", "심도", nullable=False, allowed=SEVERITIES),
        C("value", "float", "값", nullable=False, unit="param",
          note="단위는 unit 칸을 따른다"),
        C("unit", "text", "단위", nullable=False),
        C("scope", "text", "적용 범위", nullable=False),
        C("timing", "text", "시점", nullable=False),
        C("citation", "text", "근거", nullable=False),
        C("evidence_status", "string", "근거 상태", nullable=False,
          allowed=EVIDENCE_STATUS),
    ),
    primary_key=("scenario_id", "channel", "severity_key"),
    foreign_keys=(FK(("scenario_id",), "st_ai_scenario", ("scenario_id",)),),
)

AI_PATH = TableSpec(
    name="st_ai_path", korean="AI 사고 자본·유동성 경로", product="PRD-ST",
    grain="시나리오 x 심도 x 분기 1건당 1행",
    columns=(
        C("scenario_id", "string", "시나리오 식별자", nullable=False),
        C("severity_key", "string", "심도", nullable=False, allowed=SEVERITY_KEYS),
        C("quarter", "string", "분기", nullable=False),
        C("q_index", "int", "분기 순번", nullable=False, min_value=0),
        C("macro_severity", "float", "거시 심도", nullable=False, unit="severity",
          min_value=0.0),
        C("loss_op_cum", "float", "누적 운영손실 (세전, ILM 산입)", nullable=False,
          unit="KRW", min_value=0.0),
        C("loss_nonop_cum", "float", "누적 비운영 손실 (세전, ILM 제외)",
          nullable=False, unit="KRW", min_value=0.0),
        C("fine_cum", "float", "누적 과징금 (세후)", nullable=False, unit="KRW",
          min_value=0.0),
        C("op_loss_10y_addon", "float", "10년 평균손실 가산", nullable=False,
          unit="KRW", min_value=0.0),
        C("pd_multiplier", "float", "적용 PD 배수", nullable=False, unit="multiple",
          min_value=1.0, note="자본 전용 배수(감독 보수성) 포함. 자산군 가운데 최대"),
        C("lgd_addon", "float", "적용 LGD 가산", nullable=False, unit="ratio",
          min_value=0.0, max_value=1.0),
        C("runoff_addon_max", "float", "LCR 이탈률 가산 최대", nullable=False,
          unit="ratio", min_value=0.0, max_value=1.0),
        C("sa_fallback_tested", "bool", "표준방법 회귀 판정 수행", nullable=False),
        C("sa_fallback_adopted", "bool", "표준방법 회귀 채택", nullable=False),
        C("relief_forgone", "float", "무완화 규칙으로 포기한 RWA 감소", nullable=True,
          unit="KRW", min_value=0.0),
        C("cet1", "float", "보통주자본", nullable=False, unit="KRW"),
        C("cet1_ratio", "float", "보통주자본비율", nullable=False, unit="ratio"),
        C("cet1_ratio_macro", "float", "거시 단독 보통주자본비율", nullable=False,
          unit="ratio"),
        C("delta_cet1_bp", "float", "AI 사고 CET1비율 변화", nullable=False, unit="bp"),
        C("delta_cet1", "float", "AI 사고 CET1 변화", nullable=False, unit="KRW"),
        C("rwa_total", "float", "위험가중자산 합계", nullable=False, unit="KRW",
          min_value=0.0),
        C("rwa_op", "float", "운영 RWA", nullable=False, unit="KRW", min_value=0.0),
        C("delta_rwa_op", "float", "운영 RWA 증분", nullable=False, unit="KRW"),
        C("delta_rwa_total", "float", "RWA 합계 증분", nullable=False, unit="KRW"),
        C("ecl", "float", "기대신용손실", nullable=False, unit="KRW", min_value=0.0),
        C("delta_ecl", "float", "ECL 증분", nullable=False, unit="KRW"),
        C("lcr", "float", "LCR", nullable=False, unit="ratio", min_value=0.0),
        C("lcr_macro", "float", "거시 단독 LCR", nullable=False, unit="ratio",
          min_value=0.0),
        C("pre_tax_income", "float", "세전이익 (연환산)", nullable=False, unit="KRW"),
        C("cet1_surplus", "float", "CET1 요구치 대비 잉여", nullable=False, unit="KRW",
          note="CET1 계층만. 음수면 CET1 요구치(완충 포함) 미달"),
        C("capital_surplus", "float", "구속 계층 요구치 대비 잉여", nullable=False,
          unit="KRW", note="CET1·Tier1·총자본 요구치(완충 포함) 가운데 가장 빠듯한 계층"),
        C("binding_tier", "string", "구속 계층", nullable=False,
          allowed=("cet1", "tier1", "total")),
        C("passes", "bool", "자본 3계층 요구치 충족", nullable=False,
          note="capital_surplus >= 0. 엔진 판정(passes)과 같은 기준"),
        C("interaction_bp", "float", "결합 상호작용 잔차", nullable=True, unit="bp",
          note="AI-C1 만. 결합 증분 - 구성요소 증분의 합"),
    ),
    primary_key=("scenario_id", "severity_key", "quarter"),
    foreign_keys=(FK(("scenario_id",), "st_ai_scenario", ("scenario_id",)),),
)

AI_IMPACT = TableSpec(
    name="st_ai_impact", korean="AI 사고 영향 요약", product="PRD-ST",
    grain="시나리오 x 심도 1건당 1행",
    columns=(
        C("scenario_id", "string", "시나리오 식별자", nullable=False),
        C("severity_key", "string", "심도", nullable=False, allowed=SEVERITY_KEYS),
        C("severity_label", "string", "심도 표기", nullable=False,
          allowed=tuple(SEVERITY_KO.values())),
        C("trough_quarter", "string", "저점 분기", nullable=False),
        C("cet1_ratio_reference", "float", "저점 분기 비교 기준 CET1비율",
          nullable=False, unit="ratio"),
        C("cet1_ratio_trough", "float", "CET1비율 저점", nullable=False, unit="ratio"),
        C("delta_cet1_bp", "float", "최저 CET1비율 변화", nullable=False, unit="bp",
          note="분기 가운데 가장 작은 값. 하락은 음수"),
        C("delta_cet1_bp_at_trough", "float", "저점 분기 CET1비율 변화",
          nullable=False, unit="bp"),
        C("cet1_surplus_trough", "float", "CET1 요구치 대비 최소 잉여", nullable=False,
          unit="KRW"),
        C("capital_surplus_trough", "float", "구속 계층 요구치 대비 최소 잉여",
          nullable=False, unit="KRW"),
        C("breach", "bool", "자본 3계층 요구치 미달 발생", nullable=False,
          note="CET1·Tier1·총자본 가운데 하나라도 미달인 분기가 있음"),
        C("cet1_breach", "bool", "CET1 요구치 미달 발생", nullable=False),
        C("cet1_ratio_end", "float", "시계 끝 CET1비율", nullable=False, unit="ratio"),
        C("delta_cet1_bp_end", "float", "시계 끝 CET1비율 변화", nullable=False,
          unit="bp"),
        C("lcr_min", "float", "LCR 최저", nullable=False, unit="ratio", min_value=0.0),
        C("lcr_min_quarter", "string", "LCR 최저 분기", nullable=False),
        C("loss_op_total", "float", "운영손실 합계 (세전)", nullable=False, unit="KRW",
          min_value=0.0),
        C("loss_nonop_total", "float", "비운영 손실 합계 (세전)", nullable=False,
          unit="KRW", min_value=0.0),
        C("fine_total", "float", "과징금 합계 (세후, 시계 안)", nullable=False,
          unit="KRW", min_value=0.0),
        C("fine_out_of_horizon", "float", "시계 밖 과징금", nullable=False, unit="KRW",
          min_value=0.0),
        C("loss_op_out_of_horizon", "float", "시계 밖 운영손실", nullable=False,
          unit="KRW", min_value=0.0),
        C("loss_nonop_out_of_horizon", "float", "시계 밖 비운영 손실", nullable=False,
          unit="KRW", min_value=0.0, note="시계 밖 영업정지 일실수익·고객 이탈 몫"),
        C("delta_rwa_op_max", "float", "운영 RWA 최대 증분", nullable=False, unit="KRW"),
        C("delta_ecl_max", "float", "ECL 최대 증분", nullable=False, unit="KRW"),
        C("relief_forgone_max", "float", "포기한 RWA 감소 최대", nullable=True,
          unit="KRW", min_value=0.0),
        C("cum_loss_to_bi", "float", "누적 손실·과징금 / BI", nullable=False,
          unit="ratio", min_value=0.0),
        C("revenue_lost_to_rev", "float", "일실수익 / REV", nullable=False,
          unit="ratio", min_value=0.0, note="시계 밖 몫 포함"),
        C("impact_tolerance_breach_days", "float", "영향허용치 초과일수", nullable=True,
          unit="days", min_value=0.0, note="가용성 사고(AI-05)만"),
    ),
    primary_key=("scenario_id", "severity_key"),
    foreign_keys=(FK(("scenario_id",), "st_ai_scenario", ("scenario_id",)),),
)

AI_REVERSE = TableSpec(
    name="st_ai_reverse", korean="AI 사고 역스트레스", product="PRD-ST",
    grain="역스트레스 지표 1건당 1행",
    columns=(
        C("metric_id", "string", "지표 식별자", nullable=False),
        C("metric", "text", "지표", nullable=False),
        C("value", "float", "임계값", nullable=True, unit="param",
          note="단위는 unit 칸. 미침범이면 NULL"),
        C("unit", "string", "단위", nullable=False),
        C("already_breached", "bool", "기준점 이미 미달", nullable=False,
          note="자본 지표는 metric 끝의 [계층] 기준, LCR 지표는 LCR 100% 기준"),
        C("resilient", "bool", "탐색 범위 안 미침범", nullable=False),
        C("note", "text", "해석", nullable=False),
    ),
    primary_key=("metric_id",),
)

SPECS: tuple[TableSpec, ...] = (AI_SCENARIO, AI_PARAM, AI_PATH, AI_IMPACT, AI_REVERSE)
