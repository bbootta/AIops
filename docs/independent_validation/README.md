# 상시 독립검증 교환 디렉터리

리스크관리 팀에이전트(2선)와 적합성검증 팀에이전트(3선)가 요청·응답을 주고받는
곳이다.

```
<run_id>.request.json    리스크관리 팀 → 적합성검증 팀 (매 작업 자동 생성)
<run_id>.dispatch.json   발신 기록: 대상 브랜치·경로·인계 명령 (`dispatch_request`)
outbox/<run_id>.request.json   3선이 집어 가는 사본 (발신 시 생성)
<run_id>.response.json   적합성검증 팀 → 리스크관리 팀 (독립 재계산 결과)
```

- 요청은 `risk_lib.validation.independent.build_request`가 만든다.
- 발신은 `dispatch_request` (또는 `python -m risk_lib.cli validation-request
  --dispatch`) 가 기록한다. 기록이 없으면 요청은 만들어졌을 뿐 넘어가지 않은
  것이다.
- 게이트는 `check_gate`가 판정하며 **fail-closed** — 응답 파일이 없으면
  `응답대기`이고 결재 상신이 막힌다.
- 응답의 `run_id`·`request_id`가 요청과 다르면 `부적합`으로 본다. 다른 실행의
  승인을 이 실행에 쓰면 게이트가 무의미해진다.

## 응답 형식

```json
{
  "request_id": "IVR-XXXXXXXXXXXX",
  "run_id": "RUN-20260630-42",
  "verdict": "적합",
  "validated_by": "적합성검증 팀에이전트",
  "validated_at": "2026-06-30T09:00:00+00:00",
  "recalc_matches": {"rwa_final_total": true, "cet1_ratio": true},
  "findings": [
    {"finding_id": "F-001", "severity": "경부적합",
     "target": "ecl_total", "detail": "할인율 가정 문서화 미흡",
     "recomputed": 94531443664.9, "reported": 94531443664.9}
  ]
}
```

`verdict`는 적합 · 경부적합 · 중부적합 중 하나다. 중부적합이 하나라도 있으면
`verdict`가 적합이어도 게이트는 부적합으로 판정한다.

`verdict`가 경부적합이고 중부적합 finding이 0건이면 게이트는 `조건부`다 — 통과도
부적합도 아니다. 결재 책임자가 잔여위험·후속조건·이행기한·배포 범위를 담은
`ConditionalApproval`을 기록해야만 `require()`가 통과한다. 기록이 없거나 항목이
비면 통과하지 않는다 (지적 F-207).
