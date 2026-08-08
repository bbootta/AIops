# 번역 에이전트팀 하네스 (Translation Agent Team Harness)

회사 문서를 한국어 ↔ 영어 ↔ 기타 언어로 자연스럽게 번역하는 Claude Code 멀티에이전트 파이프라인.

## 사용법

```
/translate <원문 파일> <도착어> [추가 지시]
```

예:

```
/translate docs/사업계획서.md en
/translate reports/q3-report.md ko 사내 공유용, 합쇼체
/translate notice.md ja 거래처 발송용 이메일
```

작업 산출물은 `translation/jobs/<날짜>-<문서명>/`에 생성되며, 최종 번역본과 인도 보고서(delivery-report.md)가 핵심 결과물이다.

용어집 반영:

```
/glossary-add                        # 최신 작업의 용어 후보 반영
/glossary-add 품의 = approval request  # 직접 추가
```

## 파이프라인

```
원문
 │
 ▼
① doc-analyst          문서 유형·독자·어체 판정 → 번역 브리프
 ▼
② terminology-curator  용어 추출 + 용어집 대조 → 확정 용어표
 ▼
③ translator           초안 작성 (긴 문서는 청크 병렬)
 ▼
④ accuracy-reviewer    원문 대조 — 오역·누락·숫자·용어 (정확성만)
 ▼
⑤ fluency-editor       원문 없이 통독 — 번역투 제거·윤문 (자연스러움만)
 ▼
⑥ translation-qa       형식·회귀 점검 + TN 수집 → 인도 보고서
 ▼
최종 번역본 + 사용자 확인 항목
```

설계 의도: **정확성 검수(④)와 윤문(⑤)을 분리**한 것이 핵심이다. 한 에이전트가 둘 다 하면 자연스럽게 고치다 의미를 훼손하거나, 원문에 끌려 번역투를 못 벗어난다. ⑤는 원문을 보지 않고 읽기 때문에 번역투를 독자의 눈으로 잡아내고, ⑥이 윤문으로 인한 의미 훼손을 회귀 점검한다.

## 지식베이스

| 파일 | 내용 |
|---|---|
| `knowledge/principles.md` | 전 에이전트 공통 최상위 원칙 (의미 등가, 충실성 3대 금지, 번역투 제거) |
| `knowledge/ko-to-en.md` | 한→영: 주어 복원, 명사화 해소, 완곡 표현 기능 번역, 헤징 조정 |
| `knowledge/en-to-ko.md` | 영→한: 번역투 패턴 표, 수동태 전환, 어체 결정, 외래어 표기 |
| `knowledge/other-languages.md` | 일본어·중국어·유럽 언어 + 신규 언어 체크리스트 |
| `knowledge/document-types.md` | 이메일·보고서·계약·마케팅·공문서 등 유형별 전략 |
| `knowledge/style-formatting.md` | 날짜·숫자·통화·만/억 환산·직급·문장부호 규칙 |
| `knowledge/qa-checklist.md` | 검수 체크리스트와 심각도 분류 (에이전트 역할별 분담) |
| `glossary/glossary.md` | **회사 용어집 — 최우선 적용.** 실제 용어로 채워야 함 |
| `glossary/do-not-translate.md` | 번역 금지 목록 (제품명·코드·약어 등) |

## 운영 팁

- **용어집을 채울수록 품질이 오른다.** 초기에는 예시만 있으므로, 첫 몇 번의 번역에서 `/glossary-add`로 회사 용어를 축적하는 것이 가장 효과적인 투자다.
- 문서 시리즈(월간 보고서 등)는 이전 작업 디렉터리를 추가 지시로 알려주면 용어·문체 일관성이 유지된다.
- 한국어 공문서를 **작성**해야 하는 번역(영→한 대관 문서)은 `korean-official-document` 스킬이 자동 연계된다 (`document-types.md` 참조).
- 계약서 등 법적 효력이 있는 문서의 번역본은 반드시 전문가 검토를 거칠 것 — 이 하네스는 초벌·실무용 품질을 목표로 한다.
