"""Regression contract for cross-platform Tailwind projection normalization."""

from __future__ import annotations

import subprocess
from pathlib import Path


def _normalize(script: Path, source: Path) -> str:
    completed = subprocess.run(
        ["node", str(script), str(source)],
        check=True,
        capture_output=True,
        text=True,
    )
    assert completed.stdout == ""
    return source.read_text(encoding="utf-8")


def test_tailwind_projection_normalizer_collapses_native_oklab_rounding_drift(
    tmp_path: Path,
) -> None:
    """Windows and Linux Lightning CSS variants must become byte-identical."""

    script = Path(__file__).parents[1] / "scripts" / "normalize_tailwind_projection.mjs"
    windows_projection = tmp_path / "windows.css"
    linux_projection = tmp_path / "linux.css"
    windows_projection.write_text(
        ".a{color:oklab(76.8591% .0560997 .154808/.4)}"
        ".b{color:oklab(28.2256% -.00315073 -.0873928/.3)}\n",
        encoding="utf-8",
        newline="\n",
    )
    linux_projection.write_text(
        ".a{color:oklab(76.8591% .0560995 .154808/.4)}"
        ".b{color:oklab(28.2256% -.00315079 -.0873928/.3)}\n",
        encoding="utf-8",
        newline="\n",
    )

    assert _normalize(script, windows_projection) == _normalize(
        script, linux_projection
    )
