"""Data Mart 적재와 보존·폐기 수명주기 (PLT-002 · DAT-008).

이 저장소는 원장을 만들지만 **적재 이력과 폐기 판정**을 남기지 않았다. 어떤
실행이 어느 원장을 몇 행 실었는지 기록이 없으면 판 사이 증감을 설명할 수
없고, 보존기간 정책이 없으면 산출물이 무한히 쌓인다.

원장 세 장이다.

  dat_retention_policy  자료 구분별 보존기간과 그 근거
  dat_mart_load         실행 x 원장별 적재 이력(행수·컬럼수·지문)
  dat_retention_action  판별 폐기 판정 결과

**폐기 판정은 fail-closed다.** 법정 최소 보존기간을 원문으로 확인하지 못한
자료 구분은 세대수 정책을 넘겨도 '폐기대상'으로 판정하지 않고 '판정불가'로
남긴다. 폐기는 되돌릴 수 없으므로 근거를 확인하기 전에는 판정하지 않는다.

현재 이 원장의 법정 보존기간 칸은 전건 NULL이다. 신용정보법·상법·전자금융
거래법의 해당 조문을 원문으로 열람하지 못했다. 값을 채우려면 조문을 확보해
`docs/primary_sources/`에 발췌를 남기고 이 빌더의 표를 고쳐야 한다.

다만 규정상 최소 관측기간은 원문으로 확인했다. [별표 3] 166·167은 보존 대상을
정하면서 기간을 정하지 않지만, 182.라·183.나·186.가·187.가·195.가·196.이
추정에 쓸 관측기간을 5년 또는 7년으로 요구한다. 그 기간의 데이터를 채우지
못하면 추정 자체가 요건을 벗어나므로 폐기의 추가 하한으로 쓴다.

이 모듈의 TableSpec은 아직 datamodel.catalog에 등재하지 않았다. 등재는 실체화
검증과 문서 수치 일치를 함께 만족해야 하므로 배선 단계에서 `SPECS`를 넘긴다.
스펙 품질 기준(입도·기본키·float 단위·FK 대상 존재)은 지금부터 지킨다.

참조: RYNTA BRD PLT-002(Risk Data Mart) · DAT-008(보존·폐기·비식별).
"""

from __future__ import annotations

import hashlib
from datetime import date

import pandas as pd

from risk_lib.alm.params import EVIDENCE_STATUS
from risk_lib.datamodel.spec import ColumnSpec as C, ForeignKey as FK, TableSpec

DATA_CLASSES = ("산출물 판", "정규 원장", "감사기록", "원천 스냅샷",
                "모형 문서", "개인신용정보")
DISPOSAL_DECISIONS = ("보관", "폐기대상", "판정불가")
LOAD_MODES = ("전체적재", "증분적재")
LOAD_STATUSES = ("성공", "행수0", "미적재")


RETENTION_POLICY = TableSpec(
    name="dat_retention_policy", korean="보존·폐기 정책", product="PRD-RDM",
    grain="자료 구분 1개당 1행",
    columns=(
        C("data_class", "string", "자료 구분", nullable=False,
          allowed=DATA_CLASSES),
        C("min_retention_years", "float", "법정 최소 보존기간", nullable=True,
          unit="years", min_value=0.0,
          note="원문 미열람 구간은 NULL이다. 엔진은 NULL을 만나면 폐기 판정을 하지 않는다"),
        C("min_observation_years", "float", "규정상 최소 관측기간", nullable=True,
          unit="years", min_value=0.0,
          note="모형 추정에 요구되는 관측기간. 그 기간의 데이터를 못 채우면 "
               "추정 자체가 규정 위반이므로 폐기의 추가 하한이 된다"),
        C("observation_basis", "text", "관측기간 근거", nullable=False),
        C("keep_generations", "int", "보관 세대수", nullable=True, unit="count",
          min_value=1, note="규정이 정하지 않는 내부 운영값"),
        C("anonymise_after_years", "float", "비식별 전환 시점", nullable=True,
          unit="years", min_value=0.0),
        C("legal_basis", "text", "법적 근거", nullable=False),
        C("evidence_status", "string", "근거 상태", nullable=False,
          allowed=EVIDENCE_STATUS,
          note="min_retention_years에 대한 근거 상태다. 관측기간의 근거는 "
               "observation_basis에 따로 적는다"),
        C("owner_role", "text", "정책 소유 역할", nullable=False),
    ),
    primary_key=("data_class",),
    note="값이 비어 있음을 원장에 드러낸다. 비어 있는 칸을 채워 넣으면 그 순간 근거가 사라진다.",
)

MART_LOAD = TableSpec(
    name="dat_mart_load", korean="Data Mart 적재 이력", product="PRD-RDM",
    grain="실행(run_id) x 원장 1건당 1행",
    columns=(
        C("run_id", "string", "실행 식별자", nullable=False),
        C("table_name", "string", "원장명", nullable=False),
        C("load_asof", "date", "적재 기준일", nullable=False),
        C("load_mode", "string", "적재 방식", nullable=False, allowed=LOAD_MODES),
        C("n_rows", "int", "행수", nullable=False, unit="count", min_value=0),
        C("n_columns", "int", "컬럼수", nullable=False, unit="count", min_value=0),
        C("fingerprint", "text", "적재분 지문(SHA-256 앞 16자)", nullable=False),
        C("status", "string", "적재 상태", nullable=False, allowed=LOAD_STATUSES),
        C("data_class", "string", "자료 구분", nullable=False,
          allowed=DATA_CLASSES),
    ),
    primary_key=("run_id", "table_name"),
    foreign_keys=(FK(("data_class",), "dat_retention_policy", ("data_class",)),),
    note="행수 0도 적재 사실이다. 기록하지 않으면 '만들지 않았다'와 '만들었는데 비었다'가 같아진다.",
)

RETENTION_ACTION = TableSpec(
    name="dat_retention_action", korean="보존·폐기 판정", product="PRD-RDM",
    grain="보관 대상 자산(판) 1건당 1행",
    columns=(
        C("artifact_id", "text", "자산 식별자", nullable=False),
        C("data_class", "string", "자료 구분", nullable=False,
          allowed=DATA_CLASSES),
        C("created_on", "date", "생성일", nullable=False),
        C("age_years", "float", "경과 연수", nullable=False, unit="years",
          min_value=0.0),
        C("generation_rank", "int", "최신 기준 세대 순위", nullable=False,
          unit="count", min_value=1),
        C("decision", "string", "판정", nullable=False,
          allowed=DISPOSAL_DECISIONS),
        C("reason", "text", "판정 사유", nullable=False),
    ),
    primary_key=("artifact_id",),
    foreign_keys=(FK(("data_class",), "dat_retention_policy", ("data_class",)),),
)

SPECS: tuple[TableSpec, ...] = (RETENTION_POLICY, MART_LOAD, RETENTION_ACTION)


# ---------------------------------------------------------------- 정책 적재
#
# 이 표가 이 모듈의 유일한 데이터 적재 지점이다. 판정 함수는 이 표를 참조하지
# 않고 인자로 받은 정책 DataFrame만 본다.
#
# 관측기간 근거. 원문을 열람하고 옮겼다.
_OBS_7Y = ("[별표 3] 186.가·195.가 고급내부등급법 기업 등 익스포져 LGD·EAD "
           "추정 최소 관측기간 7년")
_OBS_5Y = ("[별표 3] 182.라·183.나·187.가·196. PD 및 소매 LGD·EAD 추정 "
           "최소 관측기간 5년")
_NO_OBS = "해당 없음"

# (자료구분, 법정최소보존기간, 관측기간, 관측근거, 보관세대수, 비식별전환,
#  법적근거, 근거상태, 소유역할)
_POLICIES = (
    ("산출물 판", None, None, _NO_OBS, 8, None,
     "법정 보존기간 조문 미열람. 세대수는 내부 운영값",
     "미확인", "리스크데이터관리자"),
    ("정규 원장", None, 7.0, _OBS_7Y, 4, None,
     "[별표 3] 166·167은 보존 대상을 정하나 보존기간을 정하지 않는다. "
     "법정 보존기간 조문은 미열람",
     "미확인", "리스크데이터관리자"),
    ("감사기록", None, None, _NO_OBS, None, None,
     "전자금융감독규정의 전산기록 보존 조문 미열람",
     "미확인", "내부감사"),
    ("원천 스냅샷", None, 5.0, _OBS_5Y, 4, None,
     "[별표 3] 166·167은 보존 대상을 정하나 보존기간을 정하지 않는다. "
     "법정 보존기간 조문은 미열람",
     "미확인", "리스크데이터관리자"),
    ("모형 문서", None, None, _NO_OBS, None, None,
     "모형 문서 보존기간을 정한 조문 미열람",
     "미확인", "적합성검증담당"),
    ("개인신용정보", None, None, _NO_OBS, None, None,
     "신용정보법의 보유기간·파기 조문 미열람. 값을 채우기 전 폐기 판정 금지",
     "미확인", "리스크데이터관리자"),
)

# 원장 접두어에서 자료 구분을 가른다. 접두어가 없으면 '정규 원장'으로 둔다.
_PREFIX_CLASS = (
    ("gov_audit_chain", "감사기록"),
    ("val_audit", "감사기록"),
    ("rdm_snapshot", "원천 스냅샷"),
    ("crm_model", "모형 문서"),
)


def build_retention_policy() -> pd.DataFrame:
    return pd.DataFrame([{
        "data_class": p[0], "min_retention_years": p[1],
        "min_observation_years": p[2], "observation_basis": p[3],
        "keep_generations": p[4], "anonymise_after_years": p[5],
        "legal_basis": p[6], "evidence_status": p[7], "owner_role": p[8],
    } for p in _POLICIES], columns=[c.name for c in RETENTION_POLICY.columns]
    ).astype({"keep_generations": "Int64", "min_retention_years": "float64",
              "min_observation_years": "float64",
              "anonymise_after_years": "float64"})


def classify_table(table_name: str) -> str:
    for prefix, cls in _PREFIX_CLASS:
        if table_name.startswith(prefix):
            return cls
    return "정규 원장"


def _fingerprint(df: pd.DataFrame) -> str:
    """적재분 지문. 컬럼 순서를 정렬해 순서 차이로 지문이 흔들리지 않게 한다."""
    h = hashlib.sha256()
    h.update(str(sorted(df.columns)).encode("utf-8"))
    h.update(str(df.shape).encode("utf-8"))
    if len(df):
        ordered = df[sorted(df.columns)]
        h.update(ordered.to_csv(index=False).encode("utf-8"))
    return h.hexdigest()[:16]


def build_mart_load(tables: dict[str, pd.DataFrame], *, run_id: str,
                    asof: str, load_mode: str = "전체적재") -> pd.DataFrame:
    """실행이 실은 원장을 전부 적재 이력으로 남긴다."""
    if load_mode not in LOAD_MODES:
        raise ValueError(f"알 수 없는 적재 방식: {load_mode!r}")
    rows = []
    for name in sorted(tables):
        df = tables[name]
        if not isinstance(df, pd.DataFrame):
            continue
        rows.append({
            "run_id": run_id, "table_name": name, "load_asof": asof,
            "load_mode": load_mode, "n_rows": int(len(df)),
            "n_columns": int(df.shape[1]), "fingerprint": _fingerprint(df),
            "status": "성공" if len(df) else "행수0",
            "data_class": classify_table(name),
        })
    return pd.DataFrame(rows, columns=[c.name for c in MART_LOAD.columns])


def _age_years(created: str, asof: str) -> float:
    a, c = date.fromisoformat(asof), date.fromisoformat(created)
    return round((a - c).days / 365.25, 4)


def plan_disposal(policy: pd.DataFrame, artifacts, *, ref_date: str
                  ) -> tuple[pd.DataFrame, list[str]]:
    """보관 자산의 폐기 여부를 판정한다. (판정 원장, 건너뛴 사유)를 돌려준다.

    artifacts는 (artifact_id, data_class, created_on) 튜플의 열거이며 생성일
    내림차순으로 세대 순위를 매긴다. ref_date는 경과 연수를 세는 기준일이다.
    산출 기준일자(asof)와 다를 수 있다. 판은 기준일자 이후에 만들어지기 때문이다.

    판정 규칙은 둘을 모두 만족해야 '폐기대상'이다.
      1. 세대 순위가 보관 세대수를 넘는다
      2. 경과 연수가 법정 최소 보존기간을 넘는다
    둘 중 하나라도 정책값이 NULL이면 판정하지 않고 '판정불가'로 남긴다.
    """
    pol = policy.set_index("data_class")
    skipped: list[str] = []
    items = sorted(artifacts, key=lambda x: (x[1], x[2]), reverse=True)
    rank: dict[str, int] = {}
    rows = []
    for artifact_id, data_class, created_on in items:
        rank[data_class] = rank.get(data_class, 0) + 1
        gen = rank[data_class]
        age = _age_years(created_on, ref_date)
        if age < 0:
            # 기준일 이후에 만들어진 자산은 경과 연수를 셀 수 없다.
            rows.append((artifact_id, data_class, created_on, 0.0, gen,
                         "판정불가", f"생성일 {created_on}이 판정 기준일 {ref_date} 이후다"))
            skipped.append(f"{artifact_id}: 생성일이 기준일 이후")
            continue
        if data_class not in pol.index:
            rows.append((artifact_id, data_class, created_on, age, gen,
                         "판정불가", f"정책 원장에 자료 구분 {data_class}가 없다"))
            skipped.append(f"{artifact_id}: 정책 행 없음 ({data_class})")
            continue
        p = pol.loc[data_class]
        keep = p["keep_generations"]
        min_years = p["min_retention_years"]
        if pd.isna(min_years):
            reason = (f"법정 최소 보존기간 미확인 ({p['legal_basis']}). "
                      f"폐기 판정을 하지 않는다")
            rows.append((artifact_id, data_class, created_on, age, gen,
                         "판정불가", reason))
            skipped.append(f"{artifact_id}: 보존기간 NULL ({data_class})")
            continue
        if pd.isna(keep):
            rows.append((artifact_id, data_class, created_on, age, gen,
                         "판정불가", "보관 세대수 미정"))
            skipped.append(f"{artifact_id}: 세대수 NULL ({data_class})")
            continue
        # 관측기간은 폐기의 추가 하한이다. 법정 보존기간이 더 짧아도 관측기간을
        # 채우지 못하면 모형 추정 자체가 규정을 만족하지 못한다.
        obs = p["min_observation_years"]
        floor = float(min_years) if pd.isna(obs) else max(float(min_years), float(obs))
        over_gen = gen > int(keep)
        over_age = age > floor
        detail = f"세대 {gen}/{int(keep)}, 경과 {age}년, 하한 {floor}년"
        if not pd.isna(obs):
            detail += f" (법정 {min_years}년 · 관측 {obs}년 중 큰 값)"
        rows.append((artifact_id, data_class, created_on, age, gen,
                     "폐기대상" if (over_gen and over_age) else "보관", detail))
    # 빈 결과에서도 컬럼 타입을 스펙과 맞춘다. object로 남으면 판정 원장이
    # 비었을 때만 스펙 검증이 실패한다.
    frame = pd.DataFrame(rows, columns=[c.name for c in RETENTION_ACTION.columns]
                         ).astype({"age_years": "float64",
                                   "generation_rank": "int64"})
    return frame, skipped


def artifacts_from_archive(versions) -> list[tuple[str, str, str]]:
    """보관된 판 목록을 판정 입력으로 바꾼다.

    versions는 risk_lib.archive.scan()의 반환값이다. 판 목록을 손으로 적지
    않고 실제 보관 디렉터리에서 읽는다.
    """
    return [(f"{v.asof}/{v.label}", "산출물 판", v.run_date) for v in versions]


def build_retention(tables: dict[str, pd.DataFrame], *, run_id: str, asof: str,
                    versions=None, ref_date: str | None = None
                    ) -> tuple[dict[str, pd.DataFrame], list[str]]:
    """수명주기 원장 3장을 만든다. (원장, 폐기 판정을 건너뛴 사유)를 돌려준다.

    ref_date를 주지 않으면 보관된 판 중 가장 늦은 수행일자를 쓴다. 벽시계
    시각을 읽지 않기 위함이며, 보관분이 없으면 asof를 쓴다.
    """
    policy = build_retention_policy()
    loads = build_mart_load(tables, run_id=run_id, asof=asof)
    if versions is None:
        from risk_lib import archive
        versions = archive.scan()
    artifacts = artifacts_from_archive(versions)
    if ref_date is None:
        ref_date = max([a[2] for a in artifacts], default=asof)
    actions, skipped = plan_disposal(policy, artifacts, ref_date=ref_date)
    return ({"dat_retention_policy": policy,
             "dat_mart_load": loads,
             "dat_retention_action": actions}, skipped)
