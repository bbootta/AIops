"""Our World in Data 의 CO2·에너지 자료(CC-BY 4.0)에서 국가별 최신 연도 값을 뽑아
risk_lib/data/climate_country.json 을 만든다. 전환위험 축의 실측 지표다.

  co2_per_capita  1인당 CO2 배출 (tCO2/인)        owid-co2-data.csv
  co2             CO2 배출 총량 (MtCO2)             owid-co2-data.csv
  total_ghg       온실가스 총량 (MtCO2e)           owid-co2-data.csv
  fossil_share    1차 에너지 중 화석연료 비중 (%)   owid-energy-data.csv

원본: https://github.com/owid/co2-data (Global Carbon Budget 등),
      https://github.com/owid/energy-data (Energy Institute Statistical Review 등)
사용: python3 tools/gen_climate_country.py <owid-co2-data.csv> <owid-energy-data.csv>
"""
from __future__ import annotations

import csv
import hashlib
import json
import sys
from pathlib import Path

OUT = Path(__file__).resolve().parent.parent / "risk_lib/data/climate_country.json"
FIELDS = {
    "owid-co2-data.csv": {"co2_per_capita": "co2_per_capita", "co2": "co2", "total_ghg": "total_ghg"},
    "owid-energy-data.csv": {"fossil_share": "fossil_share_energy"},
}


def main(co2_path: str, energy_path: str) -> None:
    values: dict[str, dict[str, list]] = {}
    sources = []
    for path, spec in ((co2_path, FIELDS["owid-co2-data.csv"]), (energy_path, FIELDS["owid-energy-data.csv"])):
        raw = Path(path).read_bytes()
        sources.append({"file": Path(path).name, "sha256": hashlib.sha256(raw).hexdigest(),
                        "licence": "CC-BY 4.0 (Our World in Data)"})
        for r in csv.DictReader(raw.decode("utf-8").splitlines()):
            iso = r.get("iso_code") or ""
            if len(iso) != 3 or not iso.isalpha():
                continue                                  # 지역·집계 행(OWID_*)은 뺀다
            year = int(r["year"])
            for key, col in spec.items():
                v = r.get(col)
                if v in (None, ""):
                    continue
                cur = values.setdefault(iso, {}).get(key)
                if cur is None or year > cur[1]:
                    values[iso][key] = [round(float(v), 3), year]
    doc = {"sources": sources, "generator": "tools/gen_climate_country.py",
           "fields": {"co2_per_capita": "1인당 CO2 배출 (tCO2/인)", "co2": "CO2 배출 총량 (MtCO2)",
                      "total_ghg": "온실가스 배출 총량 (MtCO2e)", "fossil_share": "1차 에너지 중 화석연료 비중 (%)"},
           "values": dict(sorted(values.items()))}
    OUT.write_text(json.dumps(doc, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    print(f"{OUT}: 국가 {len(values)}개 · {OUT.stat().st_size:,} bytes")


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2])
