# permission_policy.md

본 문서는 quant-validation-agent가 수행 가능한 작업과 금지된 작업을 정의한다.

`middleware/permission_guard.py`가 본 정책의 핵심 키워드를 검사한다.

---

## 1. 허용 작업

- 로컬 CSV/Parquet 파일 읽기 (검증용 추출, 익명/샘플 데이터)
- `tools/` 함수 호출
- pytest 실행
- `reports/`, `logs/`에 산출물 저장
- `harness/change_manifest.json` 갱신
- `examples/` 샘플 데이터 사용

---

## 2. 금지 작업 (자동 실행 절대 금지)

| 카테고리 | 예시 키워드 / 명령 |
|---|---|
| 운영계 변경 | `DROP`, `DELETE`, `TRUNCATE`, `ALTER`, `UPDATE`, `INSERT INTO 운영`, `UPDATE 운영`, `prod`, `production`, `운영계` |
| 파일 파괴 | `rm -rf`, `del /s`, `format` |
| 배포 | `deploy`, `git push`, `docker push`, `kubectl apply`, `terraform apply` |
| 외부 전송 | 외부 API 호출, 메일 전송, Slack 게시 (검증 결과 자동 전송 금지) |
| 개인정보 저장 | 주민/계좌/카드/전화/이메일 원본 저장 |
| 임계값 임의 변경 | `threshold_policy.md`에 정의된 기준의 임의 완화 |

위 키워드가 입력 또는 생성되는 명령어/코드에 포함되면 즉시 중단하고 인간 검증자에게 보고한다.

---

## 3. 인간 승인 필요 작업

- 모형 적합/부적합 **확정** 의견
- 감독기관 제출 문안
- 정책 임계값(threshold) 변경
- 운영 반영 또는 모형 교체
- `change_manifest.json` 항목의 `status` → `validated` 또는 `applied` 전환

---

## 4. 위반 시 행동

1. 즉시 작업 중단
2. 위반 항목과 입력/명령을 로그에 기록
3. `change_manifest.json`에 `human_approval_required: true` 항목으로 기록
4. 인간 검증자에게 보고
