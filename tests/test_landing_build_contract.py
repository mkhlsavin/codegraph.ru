"""Contracts for the DRY landing route and content sources."""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Any

import pytest

LANDING_ROOT = Path(__file__).resolve().parents[1]
REPOSITORY_ROOT = LANDING_ROOT.parents[1]
ROOT_ROUTE_REGISTRY = REPOSITORY_ROOT / "scripts" / "landing_build_registry.py"
if ROOT_ROUTE_REGISTRY.is_file() and str(REPOSITORY_ROOT) not in sys.path:
    sys.path.insert(0, str(REPOSITORY_ROOT))

from scripts.landing_content import SITE_CONTENT  # noqa: E402


def _shared_routes(repository_root: Path, landing_root: Path) -> list[Any]:
    """Load canonical source routes or skip when validating a standalone projection."""

    registry = repository_root / "scripts" / "landing_build_registry.py"
    if not registry.is_file():
        pytest.skip(
            "canonical root route registry is unavailable in standalone projection"
        )
    if str(repository_root) not in sys.path:
        sys.path.insert(0, str(repository_root))
    from scripts.landing_build_registry import iter_shared_routes

    return list(iter_shared_routes(landing_root))


def test_shared_route_registry_is_unique_and_points_to_existing_pages() -> None:
    """Require every shared route to be unique and backed by a public page."""
    routes = _shared_routes(REPOSITORY_ROOT, LANDING_ROOT)
    paths = [route.path for route in routes]

    assert paths
    assert len(paths) == len(set(paths))
    assert all((LANDING_ROOT / path).is_file() for path in paths)
    assert "whitepaper.html" in paths
    assert any(path.startswith("compare/") for path in paths)
    assert any(path.startswith("research/") for path in paths)


def test_standalone_projection_skips_only_the_source_registry_assertion(
    tmp_path: Path,
) -> None:
    """A distribution checkout must collect the suite without the root source repository."""

    with pytest.raises(pytest.skip.Exception):
        _shared_routes(tmp_path / "source-absent", LANDING_ROOT)


def test_shared_positioning_contract_has_all_non_empty_values() -> None:
    """Require every canonical positioning field to have public content."""
    expected = {
        "canonical_category",
        "canonical_seo_title",
        "canonical_meta_description",
        "home_h1",
        "social_image_alt",
    }

    assert set(SITE_CONTENT) == expected
    assert all(value.strip() for value in SITE_CONTENT.values())
