# 전체 저장소 코드 리뷰 — 8주차 (2026-06-30)

> **본 PR 은 리뷰 보고서 전달용. 머지 금지.**
>
> **이번 라운드는 의도적으로 prose fresh-eyes fanout 을 중단** — 7회 연속 동일 채널이 0/57 수정율을 기록했고, PR #18·#19 가 모두 "prose 채널 미도달 / 직접 fix PR 로 전환" 을 권고했음. 8주차는 (1) 24h 활동 0 재확인 (2) 어제 Top 4 P0 의 현재 HEAD 잔존 확인 (3) 채널 전환 권고 재발행 으로 한정.

## TL;DR

- **신규 커밋 0건** — 2026-06-29T00:00:00Z 이후 저장소 전체 (`#2`, `#4`, `#5`, `#10` 포함) 변경 없음.
- **PR #19 의 Top 4 P0 모두 라이브 재확인** — 어제 보고한 4 P0 가 동일 라인·동일 형태로 PR HEAD SHA 에 그대로 존재함을 `mcp__github__get_file_contents ref=refs/pull/{N}/head` 로 직접 확인.
- **누적 8회 리뷰 / 0 수정** — `#13(4), #14(0), #15(4), #16(7), #17(10), #18(3), #19(4), 이번(0 신규 — 의도적)`. P0 발견 누적 32 건, P1 누적 78 건, 수정 0 건.
- **단일 권고:** 이번 routine 사이클 안에서 prose 발행을 동결하고 (a) Top 4 P0 각각에 대한 fix-PR 4 건을 별도 routine 으로 생성하거나 (b) routine 빈도를 줄이고 author 측의 코드 게이트(테스트 회귀 잠금) 를 우선 정비.

## 24h 활동 확인

```
mcp__github__list_commits owner=bbootta repo=aiops since=2026-06-29T00:00:00Z       → []
mcp__github__list_commits sha=claude/stock-trading-agent-harness-ZuSJc      since=… → []
mcp__github__list_commits sha=claude/validation-team-agent-Pw9F5            since=… → []
mcp__github__list_commits sha=claude/risk-management-agent-harness-B9Kxm    since=… → []
mcp__github__list_commits sha=claude/minecraft-game-tqv3ii                  since=… → []
```

10개 열린 PR (`#2, #3, #4, #5, #6, #7, #8, #9, #10, #11, #12`) 모두 PR #19 작성 이후 신규 커밋 0건.

## PR #19 Top 4 P0 잔존 재확인

각 P0 를 PR head SHA 의 파일을 직접 읽어 라인·동작이 그대로인지 확인.

### P0-1 · PR #2 — `harness.py` `thinking={"type":"adaptive"}` 미정의 파라미터

**현재 HEAD SHA `f8867b8`** `stock_trading/harness.py`:

```python
for message in _client.beta.messages.tool_runner(
    model="claude-opus-4-7",
    max_tokens=4096,
    thinking={"type": "adaptive"},          # ← 그대로
    ...
)
```

Anthropic SDK 의 `thinking` 객체는 `{"type":"enabled","budget_tokens":N}` 또는 `{"type":"disabled"}` 만 허용 (Messages API reference). `"adaptive"` 는 정의되지 않은 값 → 모든 `harness.run()` 호출의 1차 모델 호출이 `BadRequestError` 로 즉시 실패. PR #2 전체 기능 동작 불가.

**상태:** 라이브, 7주 미수정.

### P0-2 · PR #2 — `place_order` 음수/0 주식 검증 부재

**현재 HEAD SHA `f8867b8`** `stock_trading/tools.py`:

```python
def place_order(symbol: str, side: str, shares: int) -> dict:
    symbol = symbol.upper()
    if symbol not in _PRICES:
        return {"error": f"Unknown symbol: {symbol}", "status": "REJECTED"}
    price = _PRICES[symbol]
    slippage = random.uniform(0.0005, 0.002)
    exec_price = price * (1 + slippage) if side.lower() == "buy" else price * (1 - slippage)
    exec_price = round(exec_price, 2)
    total_cost = exec_price * shares   # ← shares 양수 가드 없음
```

`place_order("AAPL", "buy", -100)`:
- `total_cost = exec_price * -100` → 음수
- `_PORTFOLIO["cash"] < total_cost` (예: 100_000 < -18_550) → `False` → **insufficient-cash 가드 우회**
- `_PORTFOLIO["cash"] -= total_cost` → cash 가 **증가** (음수 차감)
- `_PORTFOLIO["positions"]["AAPL"] = {"shares": -100, "avg_cost": exec_price}` → 음수 포지션 기록

Round 3 의 consult-bind / Round 4 의 multi-shot / Round 5 의 atomic write — 모든 안전 게이트가 통과한 뒤 이 한 줄에서 상태가 비가역 손상. **2 줄 fix** (`if shares <= 0: return {"status": "REJECTED", "reason": "invalid_shares"}`).

**상태:** 라이브.

### P0-3 · PR #4 — `check_weight_panel` silent dedup

**현재 HEAD SHA `5462639`** `validation-team-agent/tools/scenario_weights.py`:

```python
for period, sub in df.groupby(period_col, sort=True):
    weights = dict(zip(sub[scenario_col].astype(str), sub[weight_col].astype(float)))
    out = check_weight_sum(weights, ...)
```

같은 시나리오가 한 period 안에 두 행으로 들어오면 (`base=0.5, base=0.5, adverse=0.3, severe=0.2`) `dict(zip(...))` 가 마지막 키 값만 유지 → `{base:0.5, adverse:0.3, severe:0.2}` 합계 1.0 → **passed=True**. 실제 데이터 합 1.5 이어도 검증이 silent pass. IFRS 9 시나리오 가중치 정합성의 유일한 게이트인데 dedup 한 번에 무력화.

**Fix:** `groupby([period_col, scenario_col]).size()` 또는 `duplicated()` 사전 차단 후 `dict(zip(...))` 전에 raise. 5 줄 fix.

**상태:** 라이브.

### P0-4 · PR #4 — `record_feedback` 원문을 git-tracked JSONL 에 영구 기록

**현재 HEAD SHA `5462639`** `validation-team-agent/tools/classify_error.py`:

```python
findings = _scan_feedback_for_sensitive(text) + _scan_feedback_for_sensitive(notes)
if findings and not allow_sensitive:
    raise FeedbackPolicyError(...)

cls = classify(text)
record = {
    "text": text,                          # ← 원문 그대로 JSONL 에 기록
    "predicted_category": cls.category,
    ...
}
path.parent.mkdir(parents=True, exist_ok=True)
with path.open("a", encoding="utf-8") as fh:
    fh.write(json.dumps(record, ensure_ascii=False) + "\n")
```

`_scan_feedback_for_sensitive` → `middleware/data_safety_guard.scan_text` 의 5 개 영문 regex (target/label/default/dpd/...) 만 검사. 한국어 주민번호 변형, 내부 계좌 ID, 자유 코멘트, `allow_sensitive=True` 우회 모두 통과 → `memory/classify_feedback.jsonl` 에 원문 plaintext 영구 기록 → git CI sync 로 원격 push. **노출 표면이 Round 1 의 `df.index` PII 보다 큼.**

**Fix:** `record` 에 `text` 키 제거 또는 `hashlib.sha256(text.encode()).hexdigest()` 로 대체. 2 줄 fix.

**상태:** 라이브.

## PR #5/#10 — 신규 발견 없음 (의도적)

7회 prose 리뷰가 PR #5 에서만 IFRS9 Stage 3 PV, AT1 tier identity, MVA integrand, BA-CVA 공식, FRTB IMA multiplier, IRRBB ΔNII 등 누적 17 P0/P1 을 보고했음. **모두 라이브.** 이번 라운드에서 같은 파일을 한 번 더 읽어 동일 결함을 재기술하는 것은 효용 0.

PR #10 minecraft 도 fallDist 익스플로잇, paused-renderer always-on, save quota 등 누적 P0/P1 이 그대로. 어제(06-29) PR #10 에 신규 commit 0 이므로 이전 권고 그대로 유효.

## 누적 8회 결산

| | #13 | #14 | #15 | #16 | #17 | #18 | #19 | **이번** |
|---|---|---|---|---|---|---|---|---|
| 신규 P0 | 4 | 0 | 4 | 7 | 10 | 3 | 4 | **0** (의도적) |
| 신규 P1 | 8 | 0 | 6 | 18 | 24 | 9 | 13 | **0** (의도적) |
| 누적 수정 | — | 0/9 | 0/15 | 0/22 | 0/32 | 0/44 | 0/57 | **0/57** |

**작성자 워크플로 신호 (8주차):**

- 직전 24h, 직전 7일 누적 author commit 0 건.
- 누적 57 개 P0/P1 결함 중 단 1 건도 수정 미진행.
- PR #18 (06-28) 및 PR #19 (06-29) 가 모두 "prose 채널 미도달 / fix-PR mode 전환" 을 권고했으나 무반응.

## 단일 권고

**이번 사이클의 prose 발행을 마지막으로 routine 의 동작 모드를 전환할 것:**

1. **A 안 (능동):** 이 routine 의 다음 fire 부터, 4개 P0 각각에 대해 **fix-PR + 회귀 테스트** 를 직접 작성·푸시·draft PR open. 예: `tests/test_place_order_validates_shares.py`, `tests/test_thinking_param_accepted_by_sdk.py`, `tests/test_weight_panel_dedup.py`, `tests/test_feedback_no_raw_text.py`. fix 가 author 의 brief 와 충돌할 가능성이 있으면 PR description 에 가정·대안 명시 + draft 유지.

2. **B 안 (수동):** routine 빈도를 주 1회 → 월 1회 로 줄이고, 본 routine 이 prose 대신 **mergeability-only** 리포트 (각 PR 의 head SHA, 직전 24h commit, 회귀 테스트 존재 여부, CI 상태) 만 PR comment 형태로 작성. 작성자 측에서 코드 게이트 (pre-commit + CI block) 가 정비될 때까지 prose 검토 중단.

A 안이 더 적극적이지만, fix 가 신규 결함을 도입할 위험 (특히 PR #5 의 Basel/IFRS9 수치 변경) 이 있어 routine 의 자동 수행 범위로 적절한지 사용자 확인이 필요. B 안은 안전하지만 결함 누적을 멈추진 못함.

본 routine 은 push notification 으로 이번 보고서와 두 선택지를 사용자에게 동시에 전달.

## 리뷰 방식

- 단일 main loop (fanout 없음). `mcp__github__list_commits` 로 24h 활동 0 확인 → `mcp__github__get_file_contents ref=refs/pull/{N}/head` 로 PR #2 / PR #4 의 4 개 파일 직접 읽기 → 4 P0 잔존 확인.
- 총 출력 토큰 추정 ~12K (PR #19 의 ~405K 대비 97% 절감). 의도적으로 lean.

전체 보고서: 본 파일.

---

_본 PR 은 리뷰 보고서 전달용. 머지 금지._
