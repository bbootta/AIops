# Risk Management Agent Harness (Basel III / FSS)

바젤 III 및 금감원 기준에 따른 은행 리스크관리팀 에이전트 하네스.
신용평가모형(PD/LGD), 위험가중자산(SA + IRB), BIS비율, 연체율·부도율·회수율
모니터링, 한도관리, RAPM(RAROC)을 모두 실제 동작 가능한 형태로 제공하며,
자체검증 에이전트가 모든 산출의 정합성을 점검한다.

## 구조

```
.claude/agents/                  # 10개 서브에이전트
  risk-orchestrator.md           ── 코디네이터 (작업 분해·위임·검증 강제)
  credit-rating-modeler.md       ── PD/LGD 모형 개발 및 등급화
  rwa-calculator.md              ── RWA 산출 (신용 SA+IRB, 시장, 운영, CRM/CCF, output floor)
  bis-ratio-analyst.md           ── CET1/Tier1/Total 비율 + 레버리지비율
  delinquency-pd-lgd-monitor.md  ── 연체·부도·회수
  limit-manager.md               ── 한도관리 (동일차주/섹터/국가) + 집중도(HHI)
  rapm-analyst.md                ── RAROC / 경제자본
  ifrs9-ecl-analyst.md           ── IFRS9 ECL 충당금 (3-stage)
  stress-test-engineer.md        ── 거시 스트레스테스트
  risk-validator.md              ── 자체검증 (필수 마지막 단계)

risk_lib/                        # Python 계산 라이브러리
  capital/
    rwa_sa.py                    ── Basel III CRE20 표준방법
    rwa_irb.py                   ── CRE31 IRB 위험가중함수
    bis.py                       ── 자본비율 + 최저/버퍼 점검
    crm.py                       ── CRM(담보 haircut, 보증) + CCF
    market_risk.py               ── MAR40 간편표준방법 시장리스크 RWA
    op_risk.py                   ── OPE25 표준방법 운영리스크 RWA (BIC×ILM)
    output_floor.py              ── 바젤 III 최종안 output floor (72.5%)
    leverage.py                  ── 레버리지비율 (Tier1/익스포저, ≥3%)
  models/
    pd_model.py                  ── 로지스틱 PD + Gini/KS/PSI
    lgd_model.py                 ── workout LGD + 회귀 모형
    rating.py                    ── 17등급 master scale
  provisioning/
    ecl.py                       ── IFRS9 ECL (3-stage, 12m/lifetime)
  monitoring/
    delinquency.py               ── DPD 버킷, 부도율, 전이행렬
    recovery.py                  ── 회수 곡선
  limits/
    limit_engine.py              ── 다차원 한도 엔진
    concentration.py             ── HHI 집중리스크
  performance/
    rapm.py                      ── RAROC, 경제자본
  stress/
    scenario.py                  ── 시나리오 PD/LGD 충격 → RWA/BIS/ECL
  validation/
    consistency.py               ── 정합성 자동 체크 (21종)
    backtest.py                  ── HL test, 등급별 binomial
  data_gen.py                    ── 합성 포트폴리오 생성
  pipeline.py                    ── end-to-end 오케스트레이션
  report.py                      ── markdown 결재 리포트 생성
  cli.py                         ── CLI 러너

examples/run_end_to_end.py       # 전체 흐름 데모
tests/                           # pytest (67건)
```

## 빠른 시작

```bash
pip install -e .

# 1) CLI 러너 — 전체 파이프라인 + 검증 + markdown 리포트
python -m risk_lib.cli run --report report.md          # 합성 데이터
python -m risk_lib.cli run --data book.csv --seed 7     # 실제 포트폴리오

# 2) 단계별 데모
python examples/run_end_to_end.py

# 3) 테스트
pytest -q
```

CLI는 검증에서 FAIL이 하나라도 있으면 종료코드 1을 반환한다(결재 불가 게이트).

## 에이전트 사용

Claude Code에서:

```
> 합성 포트폴리오로 전체 자본적정성을 평가하고 검증해줘
```

`risk-orchestrator`가 호출되어 다음을 순서대로 수행한다.

1. `credit-rating-modeler` — PD/LGD 학습 + 등급 매핑
2. `rwa-calculator` — SA(국가/은행) + IRB(기업/리테일/모기지) 산출
3. `bis-ratio-analyst` — 자본비율 계산
4. `delinquency-pd-lgd-monitor` + `limit-manager` (병렬)
5. `rapm-analyst` — RAROC
6. `risk-validator` — **필수**: 정합성 + PD 백테스트, FAIL 시 재작업 지시

## 검증(자체검증) 보장

모든 산출은 다음 자동 체크를 통과해야만 결재 가능:

- PD/LGD/EAD 범위 점검
- SA·IRB 중복 산출 방지
- RWA 합계와 BIS 입력 일치
- BIS 비율의 plausible 범위와 ordering(Total ≥ Tier1 ≥ CET1)
- CET1 최저 4.5% 위반 감지
- EL ≤ EAD
- 레버리지비율 ≥ 3% 점검
- output floor 적용 여부(binding 시 WARN)
- 시장·운영 RWA 음수 점검
- IFRS9 ECL 음수 및 Stage 커버리지 단조성(S1≤S2≤S3)
- 집중도 HHI 임계(0.18) 초과 경보
- 스트레스 단조성(스트레스 RWA ≥ 기준, CET1 비율 ≤ 기준)
- PD 모형 Hosmer-Lemeshow + 등급별 단측 binomial (Green/Yellow/Red)

`run_consistency_checks()`는 `ValidationReport`를 반환하며, `passes()`가
True인 경우에만 다음 단계로 진행한다.

## 준거 기준

- Basel III: CRE20 (SA), CRE31~CRE36 (IRB), CRE22 (CRM), RBC25 (자본),
  MAR40 (시장리스크 간편표준방법), OPE25 (운영리스크 SA), LEV (레버리지),
  output floor (바젤 III 최종안)
- IFRS 9 5.5 (기대신용손실)
- 금감원: 「은행업감독업무시행세칙」 자본적정성 / 자산건전성 편,
  「은행법」 §35 (신용공여 한도), 「대손충당금 적립기준」, 스트레스테스트 운영기준
- BCBS Working Paper 14 (모형 검증), BCBS 283 (대규모 익스포저)

## 주의 사항

- 시장리스크는 간편표준방법(SSA), 운영리스크는 표준방법(SA)으로 산출한다.
  완전 sensitivities-based(SBM) 시장리스크는 범위 외이며, 시장 포지션·BI는
  파이프라인에서 예시값으로 생성된다(실제 거래·재무 데이터로 대체 필요).
- 합성 데이터의 부도율·회수율 분포는 모형 학습 가능성 검증용이며 실제 분포와 다를 수 있다.
- 본 하네스는 의사결정 보조용이며, 결재용 보고서로 사용하려면 데이터 거버넌스
  (수집·정제·승인) 절차와 통합이 필요하다.
