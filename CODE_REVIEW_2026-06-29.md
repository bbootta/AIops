# 전체 저장소 코드 리뷰 — 2026-06-29 (7주차 fresh-eyes)

## 1. 라운드 컨텍스트

- 직전 라운드(PR #18, 2026-06-28) 이후 **24시간**. 10개 PR 모두 신규 커밋 0건.
- 누적 6회 리뷰에서 P0/P1 수정 진척률 **0/44** (PR #18 시점).
- 이번 라운드는 이전 6회가 손대지 않은 영역에 집중:
  - PR #2 — `tools.py` 입력 검증 / `harness.run` SDK 파라미터 / VaR 수치
  - PR #4 — 정책-파일 외부화된 신규 도구 (`scenario_weights`, `classify_error`, `findings`)
  - PR #5 — `provisioning/macro`, `stress/reverse`, `validation/consistency`
  - PR #10 — save 데이터 무결성 / 모바일 입력 분기 / 보스 렌더링

## 2. 가장 시급한 단일 액션 — Top 4 P0

### 1. PR #2 — `place_order` 가 음수/0 주식 수량을 허용 (`stock_trading/tools.py:218`)

```python
def place_order(symbol, side, shares, ...):
    cost = shares * price
    if side == "buy":
        if cash < cost: return {"status": "REJECTED", "reason": "Insufficient cash"}
        ...
```

오케스트레이터/Trader 가 `shares=-100, side="buy"` 전달 시 `cost=-100*price` 음수 → `cash < cost` 항상 False → **cash 가 음수만큼 증가** + position `{shares: -100}` 기록. 모든 prior round 안전 게이트(consult bind, DRY_RUN, lock) 가 통과한 뒤 이 한 줄에서 상태가 비가역으로 손상. Fix: 함수 진입부에서 `if not isinstance(shares, int) or shares <= 0: return REJECTED`.

### 2. PR #2 — `harness.run` 의 `thinking={"type": "adaptive"}` 파라미터 미정의 (`stock_trading/harness.py:182`)

Anthropic API 의 `thinking` 객체는 `{"type": "enabled", "budget_tokens": N}` 또는 `{"type": "disabled"}` 두 값만 받음 (2026-06 기준). `"adaptive"` 는 정의되지 않음 → `BadRequestError` → 모든 `harness.run()` 호출이 1차 모델 호출 단계에서 실패. PR #2 전체 기능 동작 불가. 이전 6회 라운드가 `thinking` 객체 자체를 확인하지 않아 누락. Fix: `{"type": "enabled", "budget_tokens": 1024}` 또는 파라미터 제거.

### 3. PR #4 — `check_weight_panel` 가 중복 시나리오 행을 silent dedup (`validation-team-agent/tools/scenario_weights.py:84`)

```python
period_weights = dict(zip(sub[scenario_col], sub[weight_col]))
```

한 period 안에서 같은 시나리오 두 행 (예: `base=0.5, base=0.5`) 입력 시 `dict()` 가 마지막 값만 유지 → 실제 합이 1.5/2.0 이어도 0.5 로 보임 → "합계 ≠ 1" 검증이 silent pass. IFRS 9 시나리오 가중치 정합성이 이 검증의 유일한 게이트. Fix: `dict()` 전에 duplicate 검출 또는 `groupby([period, scenario]).agg("sum")` 후 합계 검증.

### 4. PR #4 — `record_feedback` 가 원문 텍스트를 git-tracked JSONL 에 영구 기록 (`validation-team-agent/tools/classify_error.py:202`)

```python
record = {"text": text, "predicted": predicted, "actual": actual, ...}
path.write_text(...)   # memory/classify_feedback.jsonl (git tracked)
```

`_scan_feedback_for_sensitive` 가 5개 regex 만 검사 → 한국어 변형 주민번호, 내부 계좌 ID, 자유 텍스트 코멘트는 그대로 통과 → 영구 plaintext 저장 + CI 의 git sync 로 원격에 푸시. Round 1 의 `data_safety_guard.scan_dataframe` 인덱스 노출보다 노출 표면이 큼. Fix: `text` 필드 자체를 제거하거나 `hashlib.sha256(text + salt).hexdigest()` 만 저장.

## 3. 결과 매트릭스

| PR | 변경(48h) | 이번 라운드 NEW | 권고 |
|---|---|---|---|
| **#2** | 없음 | **P0×2** (place_order 음수 / thinking adaptive) + P1×3 (VaR z-score / get_history 마지막봉 덮어쓰기 / last_text stale) + P2×2 | **block-merge** |
| **#4** | 없음 | **P0×2** (check_weight_panel dedup / classify_error 원문 영구 저장) + P1×6 (promote_if_passing 우회 / duplicate_keys PII / IFRS9 정렬 미보장 / pack_diff 심각도 / policy_lint 거짓양성 / findings.py 비원자) + P2×3 | **block-merge** |
| **#5** | 없음 | P1×2 (macro.py z_quarterly 분기-연 매핑 / consistency.py 단계 커버리지 거짓경보) + P2×3 (rating 경계 / CRM 미들 sovereign 등급 / 주석 stale) | changes requested |
| **#10** | 없음 | P1×2 (save NaN 통과 → 무적/통과 + 충돌 무력화) + P2×4 (crop tick 불일치 / 모바일 dialog 카메라 / 보스 HP 바 중복 / 보스 충돌 폭) | changes requested |
| #3/#6/#7/#8/#9/#11/#12 | 없음 | — | 이전 권고 유지 |

### 누적 7회 리뷰 결산

| | PR #13 | PR #14 | PR #15 | PR #16 | PR #17 | PR #18 | 이번 |
|---|---|---|---|---|---|---|---|
| 신규 P0 | 4 | 0 | 4 | 7 | 10 | 3 | **4** |
| 신규 P1 | 8 | 0 | 6 | 18 | 24 | 9 | **13** |
| 누적 수정 | — | 0/9 | 0/15 | 0/22 | 0/32 | 0/44 | **0/57** |

## 4. 작성자 워크플로 신호 (7주차)

- 직전 24h: 10개 PR 모두 신규 커밋 0건 (PR #18 의 PR #10 `cc7c5d2` 활동 후 정지).
- 누적 57개 P0/P1 결함 중 수정 0건. **prose 채널 미도달 7주 연속 확정.**
- PR #18 이 권고한 채널 전환(prose 중단 + 코드 측 강제: tests/test_basel_table_values.py · test_no_secret_in_findings.py · test_atomic_writes.py + CI block) 미실행. 동일 권고를 8주차에 또 발행해도 진척 기대 없음.

## 5. 다음 라운드 권고

**8주차는 prose 발행 중단 + 직접 fix PR 제출 모드로 전환:**

1. Top 4 P0 를 각각 별도 fix PR 로 작성 (`stock_trading-place-order-guard`, `stock_trading-thinking-param-fix`, `validation-team-agent-weight-panel-dedup`, `validation-team-agent-feedback-text-redact`).
2. 각 fix PR 은 회귀 테스트 동반 (`tests/test_place_order_validates_shares.py` 등).
3. CI gate 추가 (테스트 실패 시 머지 차단).
4. 본 routine 의 prose 리뷰는 8주차 단발 trial run 으로 fix PR merge 회수만 측정.

## 6. 리뷰 방식

- 4개 병렬 general-purpose 에이전트 (PR #2, #4, #5, #10) — 각 ~400 단어 cap.
- 데이터 소스: `mcp__github__get_file_contents` / `mcp__github__pull_request_read get_files` 로 head SHA 의 파일 직접 읽기.
- 6회 prior 결함 인벤토리를 input 으로 제공, NEW issues only 요청.
- 총 출력 토큰 ~405K (PR #18 대비 +25% — 미탐색 영역(SDK 파라미터·CSV 정렬·NaN 통과·feedback PII) 더 깊게 확인).
