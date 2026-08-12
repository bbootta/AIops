"""Basel III / FSS risk management harness.

Curated entry points re-exported from submodules so callers can write::

    from risk_lib import run_pipeline, render_markdown, generate_portfolio

Direct submodule imports (``from risk_lib.capital.rwa_irb import ...``)
remain the supported way to reach lower-level functions and constants.
"""

__version__ = "0.4.0"

from risk_lib.data_gen import generate_portfolio
from risk_lib.pipeline import run_pipeline, PipelineResult
from risk_lib.report import render_markdown

__all__ = [
    "__version__",
    "generate_portfolio",
    "run_pipeline",
    "PipelineResult",
    "render_markdown",
]
