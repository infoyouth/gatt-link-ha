"""Tests for the integration scaffold metadata."""

import json
import struct
import tomllib
from pathlib import Path

from custom_components.gatt_link.const import DOMAIN

PROJECT_ROOT = Path(__file__).parents[1]


def test_manifest_uses_project_domain_and_ble_pin() -> None:
    manifest = json.loads(
        (PROJECT_ROOT / "custom_components/gatt_link/manifest.json").read_text(
            encoding="utf-8"
        )
    )
    pyproject = tomllib.loads(
        (PROJECT_ROOT / "pyproject.toml").read_text(encoding="utf-8")
    )

    ble_requirement_prefix = "gatt-link-ble=="
    project_ble_requirements = [
        requirement
        for requirement in pyproject["project"]["dependencies"]
        if requirement.lower().startswith(ble_requirement_prefix)
    ]
    manifest_ble_requirements = [
        requirement
        for requirement in manifest["requirements"]
        if requirement.lower().startswith(ble_requirement_prefix)
    ]

    assert manifest["domain"] == DOMAIN
    assert len(project_ble_requirements) == 1
    assert len(manifest_ble_requirements) == 1
    assert project_ble_requirements == manifest_ble_requirements
    assert project_ble_requirements[0].removeprefix(ble_requirement_prefix)


def test_marketplace_metadata_and_brand_asset_sizes() -> None:
    """Marketplace metadata and required brand images are present."""
    hacs = json.loads((PROJECT_ROOT / "hacs.json").read_text(encoding="utf-8"))
    assert hacs["homeassistant"] == "2026.11.0"
    assert hacs["render_readme"] is True

    assets = {
        "custom_components/gatt_link/brand/icon.png": (256, 256),
        "custom_components/gatt_link/brand/icon@2x.png": (512, 512),
    }
    for asset_path, dimensions in assets.items():
        png = (PROJECT_ROOT / asset_path).read_bytes()
        assert png[:8] == b"\x89PNG\r\n\x1a\n"
        assert struct.unpack(">II", png[16:24]) == dimensions
