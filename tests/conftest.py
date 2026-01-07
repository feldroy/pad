"""Pytest configuration and fixtures for pad-app tests."""

import json
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest


@pytest.fixture
def polar_mock():
    """Create a mock for the Polar SDK client."""
    with patch("pad.license.Polar") as mock_polar_class:
        mock_polar = MagicMock()
        mock_polar_class.return_value.__enter__ = MagicMock(return_value=mock_polar)
        mock_polar_class.return_value.__exit__ = MagicMock(return_value=False)

        # Store references for easy access in tests
        mock_polar_class.mock_instance = mock_polar
        mock_polar_class.validate = mock_polar.customer_portal.license_keys.validate

        yield mock_polar_class


@pytest.fixture
def temp_config_dir(tmp_path: Path):
    """Create a temporary config directory and patch license module to use it."""
    config_dir = tmp_path / ".config" / "pad-app"
    config_dir.mkdir(parents=True, exist_ok=True)

    with patch("pad.license.CONFIG_DIR", config_dir), \
         patch("pad.license.LICENSE_KEYS_FILE", config_dir / "license-keys.json"), \
         patch("pad.license.VALIDATION_CACHE_FILE", config_dir / "license-validate.json"), \
         patch("pad.license.DEVICE_ID_FILE", config_dir / "device.json"):
        yield config_dir


@pytest.fixture
def license_keys_file(temp_config_dir: Path) -> Path:
    """Return path to the license keys file in temp config dir."""
    return temp_config_dir / "license-keys.json"


@pytest.fixture
def validation_cache_file(temp_config_dir: Path) -> Path:
    """Return path to the validation cache file in temp config dir."""
    return temp_config_dir / "license-validate.json"


@pytest.fixture
def sample_license_key() -> str:
    """Return a sample license key for testing."""
    return "TEST-LICENSE-KEY-12345"


@pytest.fixture
def stored_license_keys(license_keys_file: Path, sample_license_key: str) -> list[str]:
    """Create stored license keys and return them."""
    keys = [sample_license_key, "ANOTHER-KEY-67890"]
    license_keys_file.write_text(json.dumps({"keys": keys}, indent=2))
    return keys


@pytest.fixture
def device_id_file(temp_config_dir: Path) -> Path:
    """Return path to the device ID file in temp config dir."""
    return temp_config_dir / "device.json"
