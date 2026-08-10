"""ALM 화면 여섯 장. 원장 결선·리터럴 금지·미확인 노출을 고정한다.

이 화면들이 지켜야 하는 것은 세 가지다.

  1) 화면이 부르는 원장 키가 실재한다. 오타 난 키는 `D.data[...]` 에서 조용히
     undefined 가 되고, 그 자리는 "해당 없음"으로 읽힌다.
  2) 화면 코드에 수치가 없다. 충격폭·계수·상한을 화면에 적어 두면 원장이
     바뀌어도 화면은 옛 값을 말한다. 실제로 직전 화면은 아웃라이어 기준 15%를
     코드에 박아 두고 있었고, 그 기준값은 원장 어디에도 없다.
  3) 미확인이 화면에 보인다. 금리충격폭은 원화 계정이 비어 있어 USD 계정을
     대용 중이다. 그 사실을 숨기면 감독당국이 화면만 보고 원화 계정 산출로
     읽는다. 이 화면이 낼 수 있는 최악의 결과다.

집계 원장이 잘려 실리는 것도 여기서 막는다. 사다리·워터폴·소진경로는 버킷과
일자 전체가 있어야 성립하고, 표본으로 그린 그림은 모집단으로 읽힌다.
"""

from __future__ import annotations

import os
import re
from pathlib import Path

import pytest

from risk_lib.datamodel import catalog as cat
from risk_lib.ui_studio import app as ui

_APP = Path(ui.__file__).read_text(encoding="utf-8")

# ALM 화면의 여섯 리프. 라벨은 NAVGROUPS·TABS·SUMMARIES 세 곳에서 같은
# 문자열이어야 하므로 여기 한 번만 적는다.
ALM_SCREENS = ("금리리스크", "현금흐름 원장", "유동성 사다리", "유동성리스크",
               "생존기간", "ALM 계수 원장")


def _region() -> str:
    """ALM 화면 구간. 소스에 박아 둔 경계 주석 사이다."""
    a = _APP.index("/* ══════════════ ALM 화면 (시작)")
    b = _APP.index("/* ══════════════ ALM 화면 (끝)")
    return _APP[a:b]


# ----- 원장 결선 --------------------------------------------------------------

# 아직 만들어지지 않은 원장. 화면이 자리를 잡아 두고 없다는 사실을 적는다.
# 목록은 tests/test_ui_screens.py 의 _PENDING_LEDGERS 와 같은 뜻이며, 원장이
# 생기면 두 곳에서 함께 빠진다.
_PENDING_LEDGERS = {"lim_breach_action"}


def test_every_ledger_key_on_screen_exists():
    """화면이 문자열로 부르는 원장 키가 전부 카탈로그에 있다."""
    names = {sp.name for sp in cat.ALL_TABLES}
    used = set(re.findall(r"D\.data\['([a-z0-9_]+)'\]", _APP))
    used |= set(re.findall(r"almF\('([a-z0-9_]+)'\)", _APP))
    assert used, "원장 키를 하나도 못 찾았다. 정규식이 소스와 어긋났다"
    missing = sorted(k for k in used
                     if k not in names and k not in _PENDING_LEDGERS)
    assert missing == [], f"실재하지 않는 원장 키: {missing}"


def test_alm_screens_are_registered_in_every_place():
    """리프 라벨은 화면 목록·메뉴 트리·요약 세 곳에서 같아야 한다."""
    reg = _region()
    for label in ALM_SCREENS:
        assert f"['{label}','E · " in _APP, f"{label}: DETAIL_SCREENS 누락"
        assert f"'{label}'" in _APP[_APP.index("const NAVGROUPS="):], \
            f"{label}: NAVGROUPS 누락"
        assert f"'{label}':" in reg, f"{label}: 요약(SUMMARIES) 누락"


def test_alm_screens_read_the_new_cashflow_ledgers():
    """갭 근사 시절의 원장(alm_irrbb_shock)이 아니라 현금흐름 엔진 원장을 읽는다."""
    reg = _region()
    for name in ("alm_irrbb_result", "alm_irrbb_bucket_pv", "alm_nii_result",
                 "alm_cashflow_bucket", "alm_maturity_ladder",
                 "alm_survival_path", "alm_lcr_flow", "alm_lcr_factor",
                 "alm_nsfr_factor", "alm_rate_shock_param"):
        assert f"'{name}'" in reg, f"{name} 를 ALM 화면이 읽지 않는다"
    assert "alm_irrbb_shock" not in reg


# ----- 리터럴 금지 ------------------------------------------------------------

# 허용 숫자: 0·1·2·3 은 열 인덱스와 소수 자릿수, 10 은 일자 축 라벨 간격이다.
# 백분율 변환 `*100` 은 별도로 걷어낸다. 규제 수치는 어느 쪽에도 해당하지 않는다
# (아웃라이어 15%, 충격폭 200/300/150, 헤어컷 0.85/0.50, 상한 0.75 …).
_ALLOWED_NUMBERS = {"0", "1", "2", "3", "10"}


def test_alm_region_carries_no_hardcoded_numbers():
    reg = _region()
    body = re.sub(r"'(?:\\.|[^'\\])*'", "''", reg)      # 문장 안 숫자는 제외
    body = re.sub(r'"(?:\\.|[^"\\])*"', '""', body)
    body = body.replace("*100", "")                      # 비율 → % 변환
    found = sorted({n for n in re.findall(r"(?<![\w.])\d+(?:\.\d+)?", body)
                    if n not in _ALLOWED_NUMBERS})
    assert found == [], f"ALM 화면에 박힌 숫자: {found}"


def test_the_outlier_threshold_is_not_asserted_on_screen():
    """판정 기준값이 원장에 없으므로 화면도 판정선을 그리지 않는다."""
    reg = _region()
    assert "이상치 기준" not in reg
    assert "미판정" in reg          # outlier_test_pass 가 비면 그렇게 적는다


# ----- 페이로드: 집계 원장은 전량이 실린다 --------------------------------------

@pytest.fixture(scope="module")
def studio(result, portfolio):
    from risk_lib.ui_studio.studio import build_studio
    return build_studio(result, portfolio)


@pytest.fixture(scope="module")
def payload(studio):
    return ui._payload(studio)


def test_aggregated_alm_ledgers_are_embedded_in_full(payload):
    """화면이 집계해서 그리는 원장은 잘리면 안 된다."""
    data = payload["data"]
    for name in ui.ALM_FULL_TABLES:
        assert name in data, f"{name} 가 화면 데이터에 없다"
        f = data[name]
        assert f["shown"] == f["total"], (
            f"{name}: {f['shown']}/{f['total']}행만 실렸다. 집계가 모집단과 다르다")


def test_behaviour_contribution_is_the_ledger_sum_not_a_sample(payload, studio):
    """행동모형 기여도는 원장 전량 합계다. 화면 표본 집계가 아니다."""
    alm = payload["alm"]
    src = studio.tables["alm_cashflow_behavioural"]
    assert alm["behaviour_rows"] == len(src)
    f = alm["behaviour_contrib"]
    col = {c: k for k, c in enumerate(f["columns"])}
    got = {(r[col["scenario"]], r[col["behaviour_model"]]): r[col["adjustment_cf"]]
           for r in f["rows"]}
    want = src.groupby(["scenario", "behaviour_model"])["adjustment_cf"].sum()
    assert set(got) == set(want.index)
    for key, v in want.items():
        assert got[key] == pytest.approx(float(v), rel=1e-9, abs=1.0)


# ----- 브라우저: 미확인이 실제로 화면에 뜬다 ------------------------------------

_CHROME = Path(os.environ.get("PLAYWRIGHT_BROWSERS_PATH", "/opt/pw-browsers")) / "chromium"
_pw = pytest.importorskip("playwright.sync_api")
browser_only = pytest.mark.skipif(not _CHROME.exists(), reason="chromium 미설치")


@pytest.fixture(scope="module")
def page_path(studio, tmp_path_factory):
    from risk_lib.ui_studio.app import write_app
    return write_app(studio, tmp_path_factory.mktemp("ui_alm") / "studio.html")


@pytest.fixture(scope="module")
def alm_text(page_path):
    """여섯 화면을 실제로 눌러 본문 텍스트와 스크립트 오류를 걷어 온다."""
    from playwright.sync_api import sync_playwright
    out, errors = {}, []
    with sync_playwright() as pw:
        b = pw.chromium.launch(executable_path=str(_CHROME))
        pg = b.new_page(viewport={"width": 1400, "height": 1000})
        pg.on("pageerror", lambda e: errors.append(str(e)))
        # 화면 기본 언어는 영어다. 이 검사들은 한국어 화면 어휘로 단언하므로
        # 저장된 선택을 한국어로 두고 연다.
        pg.add_init_script("localStorage.setItem('rynta-lang','ko')")
        pg.goto(f"file://{page_path}")
        pg.wait_for_timeout(600)
        for label in ALM_SCREENS:
            pg.eval_on_selector_all(
                "nav button",
                "(els, t) => (els.find(e => e.textContent === t) ||"
                " els.find(e => e.textContent.includes(t))).click()", label)
            pg.wait_for_timeout(400)
            out[label] = pg.inner_text("section.on")
        b.close()
    out["__errors__"] = errors
    return out


@browser_only
def test_every_alm_screen_renders_from_a_named_ledger(alm_text):
    assert alm_text["__errors__"] == []
    for label in ALM_SCREENS:
        txt = alm_text[label]
        assert "연결 원장" in txt, f"{label}: 연결 원장 표기 없음"
        assert "alm_" in txt, f"{label}: 원장명이 화면에 없다"


@browser_only
def test_irrbb_screen_discloses_the_shock_source(alm_text):
    """충격폭이 어느 계정에서 왔는지가 화면에 있다.

    직전에는 "KRW 행이 비어 USD 계정을 프록시로 빌린다"가 화면에 실려야 했다.
    현행 원문([별표 9-1] 개정 2026.1.29)을 확보해 KRW 225/350/225가 적재되면서
    출처가 '직접'이 됐다. 프록시가 되돌아오면(원장 KRW 행이 다시 비면) 화면이
    그 사실을 말해야 하므로 출처 표기 자체를 요구한다.
    """
    txt = alm_text["금리리스크"]
    assert "충격 출처" in txt
    assert "직접" in txt
    # 두 산출기준이 나란히 있다. 감독당국이 비교하는 것이 이 차이다
    assert "계약기준 대 행동조정" in txt


@browser_only
def test_liquidity_screen_shows_factor_source_and_unused_items(alm_text):
    txt = alm_text["유동성리스크"]
    assert "잔액 × 계수 = 가중액" in txt
    assert "계수 출처" in txt and "근거 판정" in txt
    assert "국내 근거" in txt
    assert "상한 (어느 상한이 물었는가)" in txt
    assert "산출에 들어가지 않은 항목" in txt


@browser_only
def test_unverified_evidence_reaches_the_screen(alm_text):
    """미확인이 화면에 그대로 뜬다. 숨기면 확정값으로 읽힌다."""
    for label in ("금리리스크", "유동성리스크", "생존기간", "ALM 계수 원장"):
        assert "미확인" in alm_text[label], f"{label}: 미확인 표기 없음"
    blanks = alm_text["ALM 계수 원장"]
    assert "빈칸" in blanks and "승인일" in blanks


@browser_only
def test_survival_screen_names_the_scenario_it_could_not_compute(alm_text):
    """유출률이 비어 산출하지 못한 스트레스를 0으로 채우지 않는다."""
    txt = alm_text["생존기간"]
    assert "경로가 없는 스트레스" in txt
    assert "0으로 채우지 않는다" in txt
