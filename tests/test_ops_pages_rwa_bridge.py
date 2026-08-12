"""ops 페이지가 RWA 브리지를 먹이는 방식과 그 캡션을 고정한다.

두 가지를 잡는다.

1. **예시 스냅샷(shim)이 항등식의 모든 항을 넘긴다.** 페이지 23·26 은 현재
   산출을 복제해 SA·IRB 에 충격을 준 가상 스냅샷과 비교한다. 예전에는 그
   복제본의 `final_total` 을 SA·IRB·시장·운영 네 항만 더해 다시 만들었다.
   거래상대방신용·구조화·산출하한 가산이 통째로 사라져 브리지가 그 몫을
   "미배분 -4.15조" 로 드러냈다. 브리지가 옳고 shim 이 틀렸다.
2. **캡션이 분해가 낸 항과 어긋나지 않는다.** 페이지 26-3 캡션은 오래도록
   "4부문(SA / IRB / 시장 / 운영) + Output floor 가산" 이라고 적었지만
   분해는 일곱 항을 냈다. 캡션 문자열을 여기 박아두면 항이 늘 때 이 시험도
   같이 고쳐야 하므로, **분해가 내는 항 이름 집합과 캡션이 열거한 항 집합을
   맞댄다.** 항이 늘어도 시험은 그대로 잡는다.

"미배분" 행 자체는 없애지 않는다. 어긋나면 드러나야 한다.
"""

from __future__ import annotations

import re
import warnings

import pytest

from risk_lib.attribution import AttributionWarning, decompose_rwa
from risk_lib.ops_pages import governance, performance


_CAPTION_TERMS = re.compile(r'<span class="bridge-terms">(.*?)</span>', re.S)


def _caption_terms(html: str) -> set[str]:
    m = _CAPTION_TERMS.search(html)
    assert m is not None, "26-3 캡션에 항 목록(span.bridge-terms)이 없다"
    return {t.strip() for t in m.group(1).split("/") if t.strip()}


@pytest.fixture(scope="module")
def comparison_html(result) -> str:
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        return governance.page_comparison(result)


def test_comparison_caption_lists_exactly_the_decomposition_terms(
        result, comparison_html):
    """캡션이 열거한 항 집합 == 분해가 낸 항 집합."""
    with warnings.catch_warnings():
        warnings.simplefilter("error", AttributionWarning)
        expected = set(decompose_rwa(result)["component"])
    assert _caption_terms(comparison_html) == expected


def test_comparison_caption_is_not_the_old_four_way_wording(comparison_html):
    """네 항 + 하한이라고 적던 옛 캡션이 되살아나면 실패한다."""
    assert "4부문(SA / IRB / 시장 / 운영)" not in comparison_html


@pytest.mark.parametrize("page", ["23_attribution", "26_comparison"])
def test_example_snapshot_keeps_the_identity_closed(result, page):
    """shim 이 항을 버리면 AttributionWarning 이 뜬다. 미배분은 0 이어야 한다."""
    fn = (performance.page_attribution if page == "23_attribution"
          else governance.page_comparison)
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        fn(result)
    offending = [str(w.message) for w in caught
                 if issubclass(w.category, AttributionWarning)]
    assert offending == [], f"{page}: {offending}"


def test_comparison_caption_has_no_unallocated_term(comparison_html):
    """항등식이 닫혀 있으면 '미배분'은 항 목록에 나오지 않는다.

    이 시험은 '미배분' 행을 없애라는 뜻이 아니다. 캡션은 분해 결과를 그대로
    읽으므로, 여기 '미배분'이 보이면 shim 이 다시 항을 버린 것이다.
    """
    assert "미배분" not in _caption_terms(comparison_html)
