# 미팅 부검: {계정명} ({미팅 일자})

> 저장 경로: `docs/sales/deals/{계정슬러그}/debrief-{YYYYMMDD}.md`
> 에이전트는 채점 초안과 판정 권고까지만 만든다. 진행/조건부/탈락의 최종 판정은 PO가 §6 판정란에 기록해야 유효하다 [G1][G8].

| 항목 | 내용 |
|---|---|
| 계정 / 미팅 | {계정명} / {일시, 참석자} |
| 작성 에이전트 | deal-strategist (PO 미팅 노트 기반 초안) |
| 검토 | outreach-qa (후속 메일 §5 팩트체크) {PASS/FAIL} |
| 승인 | **PO 최종 판정 (§6)** {기록 완료 / 판정 대기} |
| 기준일 | {YYYY-MM-DD} |

## 1. 요약

- 미팅 결과 한 줄: {…}
- **판정 권고 (에이전트): {진행 / 조건부 / 탈락}** / 근거: {…}
- **PO 최종 판정: §6 기록 전까지 이 기회는 "판정 대기"이며 다음 스테이지로 갈 수 없다 [G8].**
- 다음 단계: {확정 (일시/참석자/산출물) / 미확정 → 24시간 내 팔로업 메일에 구체 일시 2개 제안 (§5)}

## 2. SPICED 5필드 (고객 발언 인용 필수)

| 필드 | 기록 | 고객 발언 인용 (따옴표 원문) | 증거 강도 |
|---|---|---|---|
| Situation | {…} | "{…}" | {강/중/약/없음} |
| Pain | {…} | "{…}" | {…} |
| Impact (정량) | {…} | "{…}" | {…} |
| Critical Event | {…} | "{…}" | {…} |
| Decision (결정권자 실명) | {…} | "{…}" | {…} |

- 인용 없는 필드는 "증거 없음"으로 채점에서 깎는다. Pain과 Impact가 비면 기회로 승격하지 않는다 [G8].

## 3. 페인 3층 노트 (kb/sales/04 §3.5)

| 층 | 내용 | 상태 |
|---|---|---|
| 1층: 표면 페인 (업무 불편) | {…} | {확보/미확보} |
| 2층: 비즈니스 문제 (KPI) | {…} | {…} |
| 3층: 정량화 임팩트 (돈/시간/리스크) | {숫자} + 고객 동의 여부 {동의/미동의} | {…} |

- 1층에서 멈춘 노트는 자격검증 실패로 간주한다. 감정(담당자가 얼마나 아파하는가)도 기록: {…}

## 4. 자격검증 채점 초안과 판정 권고 (deal-strategist)

- SPICED 5필드 충족도: {n}/5 (고객 발언·문서 증거 있는 필드만 인정)
- (고ACV 시) MEDDPICC 16점 채점: {점수표 또는 해당 없음}
- 판정 권고: {진행 / 조건부 (확인 필요 항목: …) / 탈락 (사유: …)}
- 챔피언 후보: {이름, 코치/챔피언 판별 메모. **챔피언 판정 자체는 PO** [G1]}
- 기회 승격 요건 대조 [G8]: SPICED 5필드 기록 { }, 페인 정량화 값 { }, 결정권자 실명 { }

## 5. 포워더블 후속 메일 초안 (영문, 24시간 내 발송)

제목줄: {예시} `notes + next step`

{예시}
```
{FirstName}, thanks for the time today. Three things we agreed on:

1. Manual report review is adding roughly {X hours} per analyst
   each week.
2. At current headcount that's about {Y} a year, before the
   {regulatory deadline} pressure kicks in.
3. Next step: a 45-minute working session with {stakeholder} to
   scope a six-week paid pilot.

Would Tuesday 3pm or Thursday 10am work for that session? Happy to
move it if another slot suits {stakeholder} better.
```

- 긍정 반응 단계이므로 interest CTA가 아니라 **구체 시간 2개 제시**로 전환한다 (kb/sales/01 §4.2). 챔피언이 내부 전달에 그대로 쓸 수 있는 포워더블 형태로 쓴다.
- [ ] [G3] 수치·주장 outreach-qa 팩트체크 (KB08 [확인] 등급 대조): {PASS/FAIL}
- [ ] [G1] 발송은 PO가 한다 (승인 대기 항목으로 상신)

## 6. PO 최종 판정란 [G1][G8]

| 항목 | 기록 |
|---|---|
| 판정 | {진행 / 조건부 (조건: …) / 탈락 (사유: …)} |
| PO 서명 | {…} |
| 날짜 | {YYYY-MM-DD} |

- 조건부인 경우 확인 항목과 기한: {…}
- 판정 기록 없는 기회는 파이프라인에서 "판정 대기"로 표시되고 다음 스테이지로 이동할 수 없다 [G8].
