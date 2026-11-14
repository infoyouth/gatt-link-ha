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

    ble_requirement = "gatt-link-ble==0.3.1"
    assert manifest["domain"] == DOMAIN
    assert manifest["requirements"] == [ble_requirement]
    assert ble_requirement in pyproject["project"]["dependencies"]


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
