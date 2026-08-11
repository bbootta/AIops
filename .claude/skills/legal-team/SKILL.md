---
name: legal-team
description: 법무 에이전트팀 하네스 진입점. 법률자문, 계약검토, 소송·분쟁 대응, 컴플라이언스 점검, 국제거래 등 법무 요청이 들어오면 사용. 국내법 우선, 판례 인용 검증, 반대검증 게이트를 적용해 법무팀 수준의 산출물을 만든다.
---

# 법무 에이전트팀 (Legal Agent Team)

법무 요청을 받으면 이 하네스로 처리한다. 회사 법무팀, 변호인, 법무컨설팅
업무를 지원하는 에이전트팀이며, 운영 절차는 `harness/legal/runbook.md`,
팀 구성은 `harness/legal/team.yaml`에 정의되어 있다.

## 처리 절차

1. **인테이크**: 의뢰인 지위(갑/을, 원고/피고), 목적, 시한, 관할·준거법을
   확정한다. 불명확하면 착수 전에 사용자에게 묻는다(AskUserQuestion).
   시효·불변기간이 걸린 사안은 기간 확인이 최우선이다.
2. **KB 우선 참조**: `kb/legal/00-index.md`에서 관련 문서를 찾아 읽는다.
   KB 기준일 이후 변경 가능성이 있는 쟁점만 웹 조사로 보강한다.
3. **요청 유형별 라우팅**:

   | 요청 유형 | 처리 방법 |
   |---|---|
   | 법률자문·질의 | Workflow `legal-consult` — args: `{question, context}` |
   | 계약서·약관 검토 | Workflow `contract-review` — args: `{contract_path, party, background}` |
   | 소송·분쟁·수사 대응 | Workflow `litigation-prep` — args: `{case_summary, our_role, goal}` |
   | 컴플라이언스 점검 | Workflow `compliance-audit` — args: `{domains, scope}` |
   | KB 갱신 | Workflow `legal-kb-update` — args: `{date, topics}` |
   | 간단한 단일 질문 | Agent 도구로 해당 전문가 1명만 투입 (아래 표) |

   가벼운 질문에 워크플로 전체를 돌리지 않는다. 전문가 1~2명으로 답이
   되면 그렇게 한다. 단, Workflow 도구는 사용자가 멀티에이전트 실행에
   동의한 경우에만 사용한다.

4. **단일 전문가 매핑**:

   | 주제 | 에이전트 |
   |---|---|
   | 쟁점 정리·종합 | `legal-lead` |
   | 법령·조문 확인 | `legal-statute-researcher` |
   | 판례 조사 | `legal-case-researcher` |
   | 계약 조항 | `legal-contract-reviewer` |
   | 회사법·지배구조·M&A | `legal-corporate-advisor` |
   | 규제·컴플라이언스 | `legal-compliance-officer` |
   | 인사노무·중대재해 | `legal-labor-advisor` |
   | 지재권·AI·데이터 | `legal-ip-tech-advisor` |
   | 소송·수사 전략 | `legal-litigation-strategist` |
   | 국제계약·해외규제 | `legal-international-counsel` |
   | 문서 작성 | `legal-writer` |
   | 반대검증 | `legal-red-team` |

## 품질 규칙 (모든 산출물에 적용)

- **인용 무결성**: 사건번호·조문은 검증된 것만. 미확인 인용은
  `[사건번호 미확인]` 표기. 인용을 장식으로 만들어내지 않는다.
- **반대검증 게이트**: 의견서·전략메모·대외문서·치명 등급 계약검토는
  `legal-red-team` PASS 후 전달한다.
- **국내법 우선**: 한국법 기준으로 먼저 검토하고, 외국적 요소가 있을 때만
  외국법을 병행한다.
- **고지 의무**: 모든 산출물에 검토 기준일과 "내부 참고자료, 변호사 자문
  대체 아님" 고지를 넣는다. 최종 산출물은 `reports/legal/`에 저장한다.
- **에스컬레이션**: 변호사 선임이 즉시 필요한 국면(구속 위험, 임박한
  불변기간, 대규모 소송), 이해충돌 사안은 결론 대신 그 사실을 보고한다.
