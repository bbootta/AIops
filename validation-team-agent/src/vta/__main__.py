"""`python -m vta` 진입점 — `vta.cli.__main__.main` 에 위임."""

from __future__ import annotations

from vta.cli.__main__ import main

if __name__ == "__main__":
    raise SystemExit(main())
