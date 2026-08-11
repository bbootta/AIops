# AIops — 팀 에이전트 하네스 모음

Claude Code 기반 팀 에이전트 하네스 모노레포.

| 팀 | 위치 | 설명 |
|---|---|---|
| 법무팀 | `.claude/agents/legal-*`, `harness/legal/`, `kb/legal/`, `templates/legal/` | 아래 [법무 에이전트팀 하네스](#법무-에이전트팀-하네스-legal-agent-team-harness) |
| 데이터 엔지니어링팀 | `.claude/agents/`, `harness/`, `templates/`, `deliverables/` | 아래 [Data Engineering Team Agent Harness](#data-engineering-team-agent-harness) |
| 디자인팀 | `design-team/` | `design-team/README.md` |
| 번역팀 | `translation/` | `translation/README.md` |
| 적합성검증팀 연동 | `validation-team-agent/` | `validation-team-agent/README-INTEGRATION.md` |

---

# 법무 에이전트팀 하네스 (Legal Agent Team Harness)

회사 법무팀 · 변호인 · 법무컨설팅 업무를 지원하는 Claude Code 기반 법무
에이전트팀. 대한민국 법률을 기본 준거로 하고, 외국적 요소가 있는 사안에서
미국·EU·아시아 법제와 국제규범을 병행 검토한다.

> ⚠️ 본 하네스의 산출물은 내부 참고자료이며 변호사의 법률자문을 대체하지
> 않는다. 대외적 법률 판단과 소송 수행은 변호사 검토를 거친다.

## 구성

```
.claude/
  agents/legal-*.md          에이전트 12종 (팀장, 리서처 2, 영역 전문가 6, 작성자, 반대검증관)
  workflows/*.js             재사용 워크플로 5종 (자문/계약/분쟁/컴플라이언스/KB갱신)
  skills/legal-team/         하네스 진입점 스킬 (요청 라우팅 규칙)
harness/legal/
  team.yaml                  팀 정의, 인용 정책, 품질 게이트
  runbook.md                 시나리오별 운영 절차 (A 자문 / B 계약 / C 분쟁 / D 컴플라이언스 / E 국제)
kb/legal/
  00-index.md                KB 인덱스와 사용 규칙
  kr/01~10-*.md              국내법 10개 분야 (법체계/민사/회사/형사/노동/공정거래/개인정보·AI/금융/IP/조세·행정)
  global/11~13-*.md          글로벌 3개 분야 (미국/EU·아시아/국제거래·중재)
templates/legal/             산출물 템플릿 6종 (의견서/계약검토/전략메모/점검표/규제브리핑/내용증명)
reports/legal/               최종 산출물 저장 위치
```

## 에이전트팀

| 에이전트 | 역할 |
|---|---|
| `legal-lead` | 법무팀장 — 쟁점 정리, 작업계획, 종합 |
| `legal-statute-researcher` | 법령 리서처 — 조문·개정이력·시행일 |
| `legal-case-researcher` | 판례 리서처 — 국내외 판례, 인용 검증 |
| `legal-contract-reviewer` | 계약 검토 — 독소조항, 수정안, 협상 |
| `legal-corporate-advisor` | 회사법·지배구조·M&A |
| `legal-compliance-officer` | 공정거래·개인정보·금융·부패방지 |
| `legal-labor-advisor` | 인사노무·중대재해 |
| `legal-ip-tech-advisor` | 지재권·오픈소스·AI·데이터 |
| `legal-litigation-strategist` | 송무·수사 대응·분쟁 전략 |
| `legal-international-counsel` | 국제계약·역외규제·중재 |
| `legal-writer` | 법률문서 작성 (`reports/legal/`) |
| `legal-red-team` | 반대검증 — 품질 게이트 (PASS/FAIL) |

## 사용법

법무 요청을 그냥 말하면 `legal-team` 스킬이 라우팅한다. 직접 실행하려면:

```
# 법률자문 (쟁점 분해 → 병렬 조사 → 반대검증 → 의견서)
Workflow legal-consult      args: { "question": "...", "context": "..." }

# 계약 검토 (조항 분석 → 전문 심화 → 반대검증 → 보고서)
Workflow contract-review    args: { "contract_path": "...", "party": "을/수급인/..." }

# 분쟁 대응 (전략 → 판례조사 → 상대방 시뮬레이션 → 전략메모)
Workflow litigation-prep    args: { "case_summary": "...", "our_role": "피고" }

# 컴플라이언스 점검 (영역별 병렬 점검 → 통합 보고서)
Workflow compliance-audit   args: { "domains": ["privacy","labor"], "scope": "..." }

# KB 갱신 (분기 1회 권장)
Workflow legal-kb-update    args: { "date": "YYYY-MM-DD", "topics": ["kr-corporate"] }
```

가벼운 단일 질문은 워크플로 없이 해당 전문가 에이전트 하나만 투입한다.

## 품질 원칙

1. **국내법 우선** — 한국법 기준 검토 후 외국적 요소가 있을 때만 외국법 병행
2. **인용 무결성** — 사건번호·조문은 웹 검증된 것만 기재, 미확인은 `[사건번호 미확인]` 표기
3. **반대검증 게이트** — 의견서·전략메모·대외문서는 `legal-red-team` PASS 후 전달
4. **KB 우선, 웹 보강** — `kb/legal/`을 먼저 읽고 기준일 이후 변경만 웹 확인
5. **고지** — 모든 산출물에 검토 기준일과 "변호사 자문 대체 아님" 명시

## KB 유지보수

KB 기준일은 `kb/legal/00-index.md` 참조. 분기 1회 또는 큰 입법·판례
이벤트(정기국회, 대형 전원합의체 판결) 후 `legal-kb-update` 워크플로로
갱신한다. KB 구축·검증 이력은 각 문서 헤더의 갱신일로 추적한다.

---

# Data Engineering Team Agent Harness

A Claude Code multi-agent harness that acts as a data engineering team. The
team's methodology is inherited from
[DataExpert-io/data-engineer-handbook](https://github.com/DataExpert-io/data-engineer-handbook)
— each specialist agent encodes one module of the handbook's curriculum
(see [`harness/handbook-map.md`](harness/handbook-map.md)).

## Team

| Agent | Role |
|---|---|
| `data-engineering-lead` | Orchestrator: intake, routing, review gates, final assembly |
| `dimensional-data-modeler` | Dimensions, SCDs, cumulative tables, graph models |
| `fact-data-modeler` | Event/fact grain, dedup, datelist ints, array metrics |
| `spark-engineer` | Batch compute: PySpark + Iceberg jobs, joins, tests |
| `streaming-engineer` | Flink/Kafka real-time pipelines, watermarks, windows |
| `analytics-engineer` | Analytical patterns, growth accounting, KPIs, experiments |
| `data-quality-engineer` | Mandatory QA gate: contracts, checks, write-audit-publish |
| `pipeline-ops-engineer` | Runbooks, ownership, SLAs, on-call, tech debt |

## Usage

Open this repo in Claude Code — agents in `.claude/agents/` load automatically.

- Full-team task: "As the data-engineering-lead, design a daily user activity
  pipeline from our event stream."
- Narrow task: "Use the fact-data-modeler subagent to design a datelist-int
  activity table."

Workflow, gates, and invocation details: [`harness/de-team-runbook.md`](harness/de-team-runbook.md).
Roster and routing rules: [`harness/team.yaml`](harness/team.yaml).
Deliverable templates: [`templates/`](templates/).

## Layout

```
.claude/agents/   # agent definitions (auto-loaded by Claude Code)
harness/          # team roster, operating runbook, handbook inheritance map
templates/        # data-model spec, pipeline runbook, quality checklist
deliverables/     # team outputs (models/, pipelines/, runbooks/, analyses/)
```
