# Copilot Instructions — `gatt-link-ha`

- **Architecture:** Follow `ARCHITECTURE.md` as the source of truth. Implement one phase at a time.
- **Integration layout:** Keep Home Assistant integration code in `custom_components/gatt_link/`.
- **BLE boundary:** Use `gatt-link-ble` for BLE discovery, connections, GATT access, and payload parsing. Do not add `bleak` or raw BLE parsing to this repository.
- **Home Assistant:** Use supported Home Assistant APIs, config entries, Bluetooth discovery, coordinators, entity descriptions, and translations. Redact addresses and unique IDs from diagnostics.
- **Tooling:** Use `uv` for project commands. Do not use raw `pip`.
- **Code quality:** Use Python 3.12+ annotations, `mypy --strict`, Ruff formatting, and focused tests with `pytest-homeassistant-custom-component`.
- **Releases:** Use Conventional Commits and Python Semantic Release for GitHub tags/releases only. Never publish this integration to PyPI.
- **Verification:** Before finishing a code task, run `uv sync --dev && uv run ruff format --check . && uv run ruff check . && uv run mypy custom_components tests && uv run pytest`.
