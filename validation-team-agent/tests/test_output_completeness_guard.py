from middleware import output_completeness_guard as g


_FULL_REPORT = """# Demo

## 1. 요약
요약 본문.

## 2. 검증 목적
정기 검증.

## 3. 입력 데이터 및 전제
입력 행 수: 1000.

## 4. 검증 방법
변별력 / 안정성 / 캘리브레이션.

## 5. 주요 결과
- 변별력 (출처: `tools/metric_ks_auc.calculate_ks`): KS = 0.4123, n = 1000
- 안정성 (출처: `tools/metric_psi.calculate_psi`): PSI = 0.0820

## 6. 이상 징후 및 원인 후보
- 등급 5의 단조성 위반 1건 (출처: `tools/data_profile.profile_dataframe`).

## 7. 한계와 리스크
표본 부족 가능.

## 8. 검증 의견 초안
의견 초안 본문.

## 9. 추가 확인 사항
- 추가 확인 필요.

## 10. 감사추적 및 변경 이력
`harness/change_manifest.json`.
"""

_MISSING_REPORT = """# Demo

## 1. 요약
요약.

## 2. 검증 목적
정기 검증.
"""

_NO_CITATION_REPORT = """# Demo

## 5. 주요 결과
KS는 0.41이고 AUROC는 0.78이다. n = 1000.

## 6. 이상 징후 및 원인 후보
등급 5의 부도율 0.05%p 역전 1회.
"""


def test_check_report_passes_full():
    out = g.check_report(_FULL_REPORT)
    assert out["passed"] is True
    assert out["missing_sections"] == []
    assert out["empty_critical"] == []


def test_check_report_detects_missing():
    out = g.check_report(_MISSING_REPORT)
    assert out["passed"] is False
    assert "한계와 리스크" in out["missing_sections"]
    assert "추가 확인 사항" in out["empty_critical"]


def test_citations_pass_when_each_numeric_line_cites_source():
    out = g.check_numeric_citations(_FULL_REPORT)
    assert out["passed"] is True
    assert out["violations"] == []


def test_citations_fail_when_no_source_cited():
    out = g.check_numeric_citations(_NO_CITATION_REPORT)
    assert out["passed"] is False
    assert any(v["section"] == "주요 결과" for v in out["violations"])
    assert any(v["section"] == "이상 징후 및 원인 후보" for v in out["violations"])


_UNIT_LINE_REPORT = """# Demo

## 5. 주요 결과
- 변별력 (출처: `tools/metric_ks_auc.calculate_ks`): KS = 0.41
- (단위: %)
- (0~1)
- (p < 0.05)

## 6. 이상 징후 및 원인 후보
- 등급 5의 단조성 위반 1건 (출처: `tools/data_profile.profile_dataframe`).
"""


def test_unit_only_lines_are_whitelisted():
    out = g.check_numeric_citations(_UNIT_LINE_REPORT)
    assert out["passed"] is True


_TABLE_PROSE_CITED = """# Demo

## 5. 주요 결과
표 형식의 결과 (출처: `tools/metric_ks_auc.calculate_auc_gini`):

| 항목 | 값 |
|---|---|
| AUC | 0.78 |
| Gini | 0.56 |

## 6. 이상 징후 및 원인 후보
- 이상 없음 (출처: `tools/data_profile`).
"""


def test_table_inherits_citation_from_preceding_prose():
    out = g.check_numeric_citations(_TABLE_PROSE_CITED)
    assert out["passed"] is True
