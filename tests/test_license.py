"""Tests for pad.license module."""

import json
from datetime import datetime, timedelta
from pathlib import Path
from unittest.mock import patch

import httpx
import pytest
import typer

from pad import license


class TestGetConfigDir:
    """Tests for get_config_dir function."""

    def test_creates_directory_if_not_exists(self, tmp_path: Path):
        """Should create config directory if it doesn't exist."""
        config_dir = tmp_path / ".config" / "pad-app"
        assert not config_dir.exists()

        with patch("pad.license.CONFIG_DIR", config_dir):
            result = license.get_config_dir()
            assert result == config_dir
            assert config_dir.exists()

    def test_returns_existing_directory(self, tmp_path: Path):
        """Should return existing directory without error."""
        config_dir = tmp_path / ".config" / "pad-app"
        config_dir.mkdir(parents=True)

        with patch("pad.license.CONFIG_DIR", config_dir):
            result = license.get_config_dir()
            assert result == config_dir


class TestLoadLicenseKeys:
    """Tests for load_license_keys function."""

    def test_returns_empty_list_when_file_not_exists(self, temp_config_dir: Path):
        """Should return empty list when license keys file doesn't exist."""
        result = license.load_license_keys()
        assert result == []

    def test_loads_keys_from_file(self, license_keys_file: Path):
        """Should load license keys from file."""
        keys = ["key1", "key2", "key3"]
        license_keys_file.write_text(json.dumps({"keys": keys}))

        result = license.load_license_keys()
        assert result == keys

    def test_returns_empty_list_on_invalid_json(self, license_keys_file: Path):
        """Should return empty list when file contains invalid JSON."""
        license_keys_file.write_text("not valid json")

        result = license.load_license_keys()
        assert result == []

    def test_returns_empty_list_on_missing_keys_field(self, license_keys_file: Path):
        """Should return empty list when 'keys' field is missing."""
        license_keys_file.write_text(json.dumps({"other": "data"}))

        result = license.load_license_keys()
        assert result == []


class TestSaveLicenseKey:
    """Tests for save_license_key function."""

    def test_saves_new_key_to_empty_file(self, temp_config_dir: Path, license_keys_file: Path):
        """Should save a new key when no keys exist."""
        license.save_license_key("new-key")

        data = json.loads(license_keys_file.read_text())
        assert data["keys"] == ["new-key"]

    def test_appends_key_to_existing_keys(self, license_keys_file: Path):
        """Should append new key to existing keys."""
        license_keys_file.write_text(json.dumps({"keys": ["existing-key"]}))

        license.save_license_key("new-key")

        data = json.loads(license_keys_file.read_text())
        assert data["keys"] == ["existing-key", "new-key"]

    def test_does_not_duplicate_existing_key(self, license_keys_file: Path):
        """Should not add duplicate keys."""
        license_keys_file.write_text(json.dumps({"keys": ["existing-key"]}))

        license.save_license_key("existing-key")

        data = json.loads(license_keys_file.read_text())
        assert data["keys"] == ["existing-key"]


class TestLoadValidationCache:
    """Tests for load_validation_cache function."""

    def test_returns_empty_dict_when_file_not_exists(self, temp_config_dir: Path):
        """Should return empty dict when cache file doesn't exist."""
        result = license.load_validation_cache()
        assert result == {}

    def test_loads_cache_from_file(self, validation_cache_file: Path):
        """Should load cache data from file."""
        cache_data = {
            "last_validated_at": "2024-01-15T10:00:00",
            "last_validated_key": "test-key",
            "valid": True,
        }
        validation_cache_file.write_text(json.dumps(cache_data))

        result = license.load_validation_cache()
        assert result == cache_data

    def test_returns_empty_dict_on_invalid_json(self, validation_cache_file: Path):
        """Should return empty dict when file contains invalid JSON."""
        validation_cache_file.write_text("not valid json")

        result = license.load_validation_cache()
        assert result == {}


class TestSaveValidationCache:
    """Tests for save_validation_cache function."""

    def test_saves_validation_result(self, temp_config_dir: Path, validation_cache_file: Path):
        """Should save validation result to cache file."""
        license.save_validation_cache("test-key", True)

        data = json.loads(validation_cache_file.read_text())
        assert data["last_validated_key"] == "test-key"
        assert data["valid"] is True
        assert "last_validated_at" in data

    def test_overwrites_existing_cache(self, validation_cache_file: Path):
        """Should overwrite existing cache data."""
        validation_cache_file.write_text(json.dumps({
            "last_validated_key": "old-key",
            "valid": False,
        }))

        license.save_validation_cache("new-key", True)

        data = json.loads(validation_cache_file.read_text())
        assert data["last_validated_key"] == "new-key"
        assert data["valid"] is True


class TestNeedsValidation:
    """Tests for needs_validation function."""

    def test_returns_true_when_no_cache(self, temp_config_dir: Path):
        """Should return True when no validation cache exists."""
        result = license.needs_validation()
        assert result is True

    def test_returns_true_when_no_timestamp(self, validation_cache_file: Path):
        """Should return True when cache has no timestamp."""
        validation_cache_file.write_text(json.dumps({"valid": True}))

        result = license.needs_validation()
        assert result is True

    def test_returns_false_when_recently_validated(self, validation_cache_file: Path):
        """Should return False when validated within last 24 hours."""
        recent_time = datetime.now() - timedelta(hours=12)
        validation_cache_file.write_text(json.dumps({
            "last_validated_at": recent_time.isoformat(),
            "valid": True,
        }))

        result = license.needs_validation()
        assert result is False

    def test_returns_true_when_validation_expired(self, validation_cache_file: Path):
        """Should return True when last validation was more than 24 hours ago."""
        old_time = datetime.now() - timedelta(days=2)
        validation_cache_file.write_text(json.dumps({
            "last_validated_at": old_time.isoformat(),
            "valid": True,
        }))

        result = license.needs_validation()
        assert result is True

    def test_returns_true_on_invalid_timestamp(self, validation_cache_file: Path):
        """Should return True when timestamp is invalid."""
        validation_cache_file.write_text(json.dumps({
            "last_validated_at": "not-a-valid-date",
            "valid": True,
        }))

        result = license.needs_validation()
        assert result is True


class TestValidateLicenseKeyApi:
    """Tests for validate_license_key_api function."""

    def test_returns_true_for_granted_status(self, httpx_mock):
        """Should return True when API returns 'granted' status."""
        httpx_mock.add_response(
            url=license.POLAR_VALIDATE_URL,
            json={"status": "granted"},
        )

        valid, error = license.validate_license_key_api("test-key")
        assert valid is True
        assert error == ""

    def test_returns_true_for_active_status(self, httpx_mock):
        """Should return True when API returns 'active' status."""
        httpx_mock.add_response(
            url=license.POLAR_VALIDATE_URL,
            json={"status": "active"},
        )

        valid, error = license.validate_license_key_api("test-key")
        assert valid is True
        assert error == ""

    def test_returns_false_for_revoked_status(self, httpx_mock):
        """Should return False when API returns 'revoked' status."""
        httpx_mock.add_response(
            url=license.POLAR_VALIDATE_URL,
            json={"status": "revoked"},
        )

        valid, error = license.validate_license_key_api("test-key")
        assert valid is False
        assert "revoked" in error.lower()

    def test_returns_false_for_404(self, httpx_mock):
        """Should return False when license key not found."""
        httpx_mock.add_response(
            url=license.POLAR_VALIDATE_URL,
            status_code=404,
        )

        valid, error = license.validate_license_key_api("test-key")
        assert valid is False
        assert "not found" in error.lower()

    def test_returns_false_for_422(self, httpx_mock):
        """Should return False for invalid license key format."""
        httpx_mock.add_response(
            url=license.POLAR_VALIDATE_URL,
            status_code=422,
        )

        valid, error = license.validate_license_key_api("bad-format")
        assert valid is False
        assert "invalid" in error.lower()

    def test_returns_false_for_other_http_errors(self, httpx_mock):
        """Should return False for other HTTP errors."""
        httpx_mock.add_response(
            url=license.POLAR_VALIDATE_URL,
            status_code=500,
        )

        valid, error = license.validate_license_key_api("test-key")
        assert valid is False
        assert "500" in error

    def test_handles_timeout(self, httpx_mock):
        """Should handle timeout exceptions."""
        httpx_mock.add_exception(httpx.TimeoutException("Connection timed out"))

        valid, error = license.validate_license_key_api("test-key")
        assert valid is False
        assert "timeout" in error.lower()

    def test_handles_network_error(self, httpx_mock):
        """Should handle network errors."""
        httpx_mock.add_exception(httpx.ConnectError("Connection refused"))

        valid, error = license.validate_license_key_api("test-key")
        assert valid is False
        assert "network error" in error.lower()

    def test_sends_correct_request_body(self, httpx_mock):
        """Should send correct organization_id and key in request."""
        httpx_mock.add_response(
            url=license.POLAR_VALIDATE_URL,
            json={"status": "granted"},
        )

        license.validate_license_key_api("my-test-key")

        request = httpx_mock.get_request()
        body = json.loads(request.content)
        assert body["key"] == "my-test-key"
        assert body["organization_id"] == license.ORGANIZATION_ID


class TestPromptForLicenseKey:
    """Tests for prompt_for_license_key function."""

    def test_returns_entered_key(self):
        """Should return the key entered by user."""
        with patch("builtins.input", return_value="user-entered-key"):
            result = license.prompt_for_license_key()
            assert result == "user-entered-key"

    def test_strips_whitespace(self):
        """Should strip whitespace from entered key."""
        with patch("builtins.input", return_value="  key-with-spaces  "):
            result = license.prompt_for_license_key()
            assert result == "key-with-spaces"

    def test_returns_none_for_empty_input(self):
        """Should return None for empty input."""
        with patch("builtins.input", return_value=""):
            result = license.prompt_for_license_key()
            assert result is None

    def test_returns_none_on_keyboard_interrupt(self):
        """Should return None when user presses Ctrl+C."""
        with patch("builtins.input", side_effect=KeyboardInterrupt):
            result = license.prompt_for_license_key()
            assert result is None

    def test_returns_none_on_eof(self):
        """Should return None on EOF."""
        with patch("builtins.input", side_effect=EOFError):
            result = license.prompt_for_license_key()
            assert result is None


class TestHandleInvalidLicense:
    """Tests for handle_invalid_license function."""

    def test_raises_typer_abort(self, temp_config_dir: Path):
        """Should raise typer.Abort."""
        with pytest.raises(typer.Abort):
            license.handle_invalid_license()


class TestCheckLicense:
    """Tests for check_license function."""

    def test_validates_and_saves_provided_key(self, temp_config_dir: Path, license_keys_file: Path, httpx_mock):
        """Should validate and save a provided key."""
        httpx_mock.add_response(
            url=license.POLAR_VALIDATE_URL,
            json={"status": "granted"},
        )

        result = license.check_license(provided_key="new-key")

        assert result is True
        data = json.loads(license_keys_file.read_text())
        assert "new-key" in data["keys"]

    def test_returns_false_for_invalid_provided_key(self, temp_config_dir: Path, httpx_mock):
        """Should return False for invalid provided key."""
        httpx_mock.add_response(
            url=license.POLAR_VALIDATE_URL,
            status_code=404,
        )

        with pytest.raises(typer.Abort):
            license.check_license(provided_key="invalid-key")

    def test_prompts_when_no_keys_exist(self, temp_config_dir: Path, httpx_mock):
        """Should prompt for key when no keys exist."""
        httpx_mock.add_response(
            url=license.POLAR_VALIDATE_URL,
            json={"status": "granted"},
        )

        with patch.object(license, "prompt_for_license_key", return_value="prompted-key"):
            result = license.check_license()
            assert result is True

    def test_returns_false_when_prompt_cancelled(self, temp_config_dir: Path):
        """Should return False when user cancels prompt."""
        with patch.object(license, "prompt_for_license_key", return_value=None):
            result = license.check_license()
            assert result is False

    def test_uses_cache_when_recently_validated(
        self, temp_config_dir: Path, license_keys_file: Path, validation_cache_file: Path
    ):
        """Should use cached result when recently validated."""
        license_keys_file.write_text(json.dumps({"keys": ["cached-key"]}))
        recent_time = datetime.now() - timedelta(hours=12)
        validation_cache_file.write_text(json.dumps({
            "last_validated_at": recent_time.isoformat(),
            "last_validated_key": "cached-key",
            "valid": True,
        }))

        result = license.check_license()
        assert result is True

    def test_revalidates_when_cache_expired(
        self, temp_config_dir: Path, license_keys_file: Path, validation_cache_file: Path, httpx_mock
    ):
        """Should revalidate when cache is expired."""
        license_keys_file.write_text(json.dumps({"keys": ["stored-key"]}))
        old_time = datetime.now() - timedelta(days=2)
        validation_cache_file.write_text(json.dumps({
            "last_validated_at": old_time.isoformat(),
            "last_validated_key": "stored-key",
            "valid": True,
        }))

        httpx_mock.add_response(
            url=license.POLAR_VALIDATE_URL,
            json={"status": "granted"},
        )

        result = license.check_license()
        assert result is True

    def test_tries_all_stored_keys(
        self, temp_config_dir: Path, license_keys_file: Path, validation_cache_file: Path, httpx_mock
    ):
        """Should try all stored keys until one validates."""
        license_keys_file.write_text(json.dumps({"keys": ["bad-key", "good-key"]}))
        old_time = datetime.now() - timedelta(days=2)
        validation_cache_file.write_text(json.dumps({
            "last_validated_at": old_time.isoformat(),
        }))

        httpx_mock.add_response(
            url=license.POLAR_VALIDATE_URL,
            json={"status": "revoked"},
        )
        httpx_mock.add_response(
            url=license.POLAR_VALIDATE_URL,
            json={"status": "granted"},
        )

        result = license.check_license()
        assert result is True

    def test_handles_all_keys_invalid(
        self, temp_config_dir: Path, license_keys_file: Path, validation_cache_file: Path, httpx_mock
    ):
        """Should handle case when all stored keys are invalid."""
        license_keys_file.write_text(json.dumps({"keys": ["bad-key-1", "bad-key-2"]}))
        old_time = datetime.now() - timedelta(days=2)
        validation_cache_file.write_text(json.dumps({
            "last_validated_at": old_time.isoformat(),
        }))

        httpx_mock.add_response(
            url=license.POLAR_VALIDATE_URL,
            json={"status": "revoked"},
        )
        httpx_mock.add_response(
            url=license.POLAR_VALIDATE_URL,
            json={"status": "revoked"},
        )

        with pytest.raises(typer.Abort):
            license.check_license()
