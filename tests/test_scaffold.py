"""Tests for the integration scaffold metadata."""

import json
import tomllib
from pathlib import Path

from gatt_link.const import DOMAIN

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
