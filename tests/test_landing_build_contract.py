"""Contracts for the DRY landing route and content sources."""

from __future__ import annotations

import sys
from pathlib import Path

LANDING_ROOT = Path(__file__).resolve().parents[1]
REPOSITORY_ROOT = LANDING_ROOT.parents[1]
if str(REPOSITORY_ROOT) not in sys.path:
    sys.path.insert(0, str(REPOSITORY_ROOT))

from scripts.landing_build_registry import iter_shared_routes  # noqa: E402
from scripts.landing_content import SITE_CONTENT  # noqa: E402


def test_shared_route_registry_is_unique_and_points_to_existing_pages() -> None:
    """Require every shared route to be unique and backed by a public page."""
    routes = list(iter_shared_routes(LANDING_ROOT))
    paths = [route.path for route in routes]

    assert paths
    assert len(paths) == len(set(paths))
    assert all((LANDING_ROOT / path).is_file() for path in paths)
    assert "whitepaper.html" in paths
    assert any(path.startswith("compare/") for path in paths)
    assert any(path.startswith("research/") for path in paths)


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
