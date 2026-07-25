"""금융감독원 배포 기준 업무보고서 — 서식 정의·값 채움·엑셀 산출.

`build_forms(result, portfolio, tables)`가 서식별 라인을 산출값에서 채우고,
`write_workbook(...)`이 시트 하나에 서식 하나씩 담은 .xlsx를 만든다.
"""
from risk_lib.regulatory.forms import (
    FormSpec, FormLine, FormCheck, FORMS, build_forms, form_frames,
)
from risk_lib.regulatory.excel import write_workbook

__all__ = ["FormSpec", "FormLine", "FormCheck", "FORMS", "build_forms",
           "form_frames", "write_workbook"]
