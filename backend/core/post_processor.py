"""Post-processor: applies black + isort formatting to generated source.

Both formatters are optional — if they're not installed the raw source is
returned along with a warning so the pipeline can still complete.
"""

from __future__ import annotations

import importlib
import logging

logger = logging.getLogger(__name__)


def post_process(source: str) -> tuple[str, list[str]]:
    """Apply black and isort to *source*.

    Returns:
        (formatted_source, warnings) where warnings is an empty list on
        success or contains one entry per formatter that could not run.
    """
    warnings: list[str] = []
    source = _apply_black(source, warnings)
    source = _apply_isort(source, warnings)
    return source, warnings


def _apply_black(source: str, warnings: list[str]) -> str:
    try:
        black = importlib.import_module("black")
    except ImportError:
        warnings.append("black is not installed; code will not be reformatted (pip install black)")
        return source

    mode = black.Mode(line_length=100, string_normalization=True, is_pyi=False)
    try:
        return black.format_str(source, mode=mode)
    except black.InvalidInput as exc:
        warnings.append(f"black could not format generated code: {exc}")
        return source
    except Exception as exc:
        warnings.append(f"black encountered an unexpected error: {exc}")
        return source


def _apply_isort(source: str, warnings: list[str]) -> str:
    try:
        isort = importlib.import_module("isort")
    except ImportError:
        warnings.append("isort is not installed; imports will not be sorted (pip install isort)")
        return source

    try:
        config = isort.Config(profile="black", line_length=100)
        return isort.code(source, config=config)
    except Exception as exc:
        warnings.append(f"isort could not sort imports: {exc}")
        return source
