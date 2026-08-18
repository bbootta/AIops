"""Auto-generated CLI reference / how-to.

Helps the ops team discover every entry point without reading the source.
The output is plain markdown, suitable for committing as a README or
appending to runbooks.
"""

from __future__ import annotations


def cli_reference() -> str:
    return """# risk_lib CLI reference

모든 명령은 `python -m risk_lib.cli <명령> ...` 형태로 실행합니다.

## 산출 명령
- `run`              : 파이프라인 실행, 마크다운 리포트 출력
- `report-set`       : 경영진+실무진 2단계 HTML 보고서 + manifest 생성
- `pdf`              : 경영진 1-pager PDF 생성 (한국어 인라인, 이메일 첨부용)
- `export-json`      : 11개 JSON 엔드포인트 디렉터리에 저장
- `notify`           : Slack/이메일/마크다운 알림 페이로드 생성

## 운영 명령
- `serve`            : stdlib HTTP API 서버 (12개 GET 엔드포인트)
- `compare`          : N개 manifest 비교 (history → CSV)
- `reproduce`        : manifest 재실행 → headline_digest 일치 검증

---

## 사용 예시

### 1. 정기(분기) 결재 워크플로우
```bash
# 1) 두 단계 보고서 생성 (CRO + 실무진 + manifest)
python -m risk_lib.cli report-set --out reports/2026Q3/

# 2) 경영진 PDF 출력 (이메일 결재 회람)
python -m risk_lib.cli pdf --out reports/2026Q3/exec.pdf

# 3) Slack 채널에 자동 알림
python -m risk_lib.cli notify --out reports/2026Q3/alerts/
# alert_slack.json 을 webhook URL에 POST
curl -X POST -H 'Content-type: application/json' \\
     --data @reports/2026Q3/alerts/alert_slack.json \\
     $SLACK_WEBHOOK_URL
```

### 2. 외부 시스템 연동 (BI / 데이터레이크)
```bash
# JSON 파일로 출력 (배치형)
python -m risk_lib.cli export-json --out exports/

# 실시간 API (서버형)
python -m risk_lib.cli serve --port 8765
# GET http://localhost:8765/headline
# GET http://localhost:8765/raf
# GET http://localhost:8765/alm/lcr
```

### 3. QoQ / YoY 비교
```bash
python -m risk_lib.cli compare \\
   --manifests reports/2026Q1/manifest.json \\
               reports/2026Q2/manifest.json \\
               reports/2026Q3/manifest.json \\
   --out history.csv
```

### 4. 감사 / 재현성 검증
```bash
# 누구나 manifest를 받아서 같은 결과를 재현
python -m risk_lib.cli reproduce --manifest reports/2026Q3/manifest.json
# → "재현 성공" (exit 0) | "재현 실패" + 변경 필드 출력 (exit 2)
```

---

## HTTP API 엔드포인트

| Path | 반환 |
|---|---|
| `GET /healthz` | `{"status":"ok"}` |
| `GET /` | 사용 가능한 엔드포인트 인덱스 |
| `GET /headline` | RWA/BIS/Leverage/ECL/LCR/NSFR/IRRBB/ICAAP 헤드라인 |
| `GET /raf` | RAF 12개 KRI 실측·한계·등급 |
| `GET /validation` | 자체검증 체크 리스트 |
| `GET /alm/lcr` | HQLA detail + outflow/inflow 분해 |
| `GET /alm/nsfr` | ASF/RSF detail |
| `GET /alm/irrbb` | 6대 시나리오 ΔEVE/ΔNII + 만기갭 |
| `GET /icaap` | 경제자본 위험유형별 + 통합 |
| `GET /sensitivity` | 1F + 2F 민감도 그리드 |
| `GET /climate` | 전환·물리 시나리오별 ECL uplift |
| `GET /alerts` | 알림 번들 (Slack JSON 변환 전 raw) |
| `GET /manifest` | manifest 정보 |

---

## 5종 산출물 산출 명세

| 산출물 | 명령 | 용도 |
|---|---|---|
| **HTML 보고서 세트** | `report-set` | 경영진 1-pager + 실무진 31 페이지 deep-dive |
| **경영진 PDF** | `pdf` | 이메일 첨부 결재 회람용 1-pager |
| **JSON 엔드포인트** | `export-json` / `serve` | BI/datalake/외부 시스템 연동 |
| **알림 페이로드** | `notify` | Slack 웹훅 + 이메일 발송 |
| **manifest** | (모든 명령 자동) | 비트 단위 재현 + 감사 추적 |

모든 산출물은 **같은 시드에서 동일하게 재현되며**, 수치 일치는 manifest의
`headline_digest`로 SHA-256 검증됩니다.
"""


def write_cli_docs(out_path) -> str:
    from pathlib import Path
    p = Path(out_path); p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(cli_reference(), encoding="utf-8")
    return str(p.resolve())
