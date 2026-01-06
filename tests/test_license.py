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
        """Should load and decrypt cache data from file."""
        timestamp = "2024-01-15T10:00:00"
        license_key = "test-key"
        encrypted_timestamp = license.encrypt_timestamp(timestamp, license_key)
        cache_data = {
            "last_validated_at": encrypted_timestamp,
            "last_validated_key": license_key,
            "valid": True,
        }
        validation_cache_file.write_text(json.dumps(cache_data))

        result = license.load_validation_cache()
        assert result["last_validated_at"] == timestamp
        assert result["last_validated_key"] == license_key
        assert result["valid"] is True

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


class TestGetHardwareId:
    """Tests for get_hardware_id function."""

    def test_returns_string(self):
        """Should return a non-empty string."""
        result = license.get_hardware_id()
        assert isinstance(result, str)
        assert len(result) > 0

    def test_returns_consistent_value(self):
        """Should return the same value on multiple calls."""
        result1 = license.get_hardware_id()
        result2 = license.get_hardware_id()
        assert result1 == result2

    def test_returns_32_char_hash(self):
        """Should return a 32-character hash."""
        result = license.get_hardware_id()
        assert len(result) == 32

    def test_handles_subprocess_failure(self):
        """Should return fallback ID when subprocess fails."""
        with patch("subprocess.run", side_effect=OSError("Command not found")):
            result = license.get_hardware_id()
            assert isinstance(result, str)
            assert len(result) == 32


class TestLoadDeviceId:
    """Tests for load_device_id function."""

    def test_returns_none_when_file_not_exists(self, temp_config_dir: Path):
        """Should return None when device file doesn't exist."""
        result = license.load_device_id()
        assert result is None

    def test_loads_device_id_from_file(self, device_id_file: Path):
        """Should load device ID from file."""
        device_id_file.write_text(json.dumps({"device_id": "test-device-123"}))
        result = license.load_device_id()
        assert result == "test-device-123"

    def test_returns_none_on_invalid_json(self, device_id_file: Path):
        """Should return None when file contains invalid JSON."""
        device_id_file.write_text("not valid json")
        result = license.load_device_id()
        assert result is None

    def test_returns_none_on_missing_device_id_field(self, device_id_file: Path):
        """Should return None when 'device_id' field is missing."""
        device_id_file.write_text(json.dumps({"other": "data"}))
        result = license.load_device_id()
        assert result is None


class TestSaveDeviceId:
    """Tests for save_device_id function."""

    def test_saves_device_id(self, temp_config_dir: Path, device_id_file: Path):
        """Should save device ID to file."""
        license.save_device_id("my-device-id")
        data = json.loads(device_id_file.read_text())
        assert data["device_id"] == "my-device-id"

    def test_overwrites_existing_device_id(self, device_id_file: Path):
        """Should overwrite existing device ID."""
        device_id_file.write_text(json.dumps({"device_id": "old-device"}))
        license.save_device_id("new-device")
        data = json.loads(device_id_file.read_text())
        assert data["device_id"] == "new-device"


class TestIsDeviceActivated:
    """Tests for is_device_activated function."""

    def test_returns_false_when_no_device_file(self, temp_config_dir: Path):
        """Should return False when device file doesn't exist."""
        result = license.is_device_activated()
        assert result is False

    def test_returns_true_when_device_id_matches(self, temp_config_dir: Path, device_id_file: Path):
        """Should return True when stored device ID matches current hardware."""
        current_hw_id = license.get_hardware_id()
        device_id_file.write_text(json.dumps({"device_id": current_hw_id}))
        result = license.is_device_activated()
        assert result is True

    def test_returns_false_when_device_id_differs(self, device_id_file: Path):
        """Should return False when stored device ID doesn't match."""
        device_id_file.write_text(json.dumps({"device_id": "different-device-id"}))
        result = license.is_device_activated()
        assert result is False


class TestValidateLicenseKeyWithUsage:
    """Tests for validate_license_key_with_usage function."""

    def test_returns_usage_info_on_success(self, httpx_mock):
        """Should return usage info when validation succeeds."""
        httpx_mock.add_response(
            url=license.POLAR_VALIDATE_URL,
            json={"status": "granted", "usage": 2, "limit_usage": 5},
        )
        result = license.validate_license_key_with_usage("test-key")
        assert result.valid is True
        assert result.usage == 2
        assert result.limit == 5
        assert result.error == ""

    def test_sends_increment_usage_when_requested(self, httpx_mock):
        """Should send increment_usage in request body when True."""
        httpx_mock.add_response(
            url=license.POLAR_VALIDATE_URL,
            json={"status": "granted", "usage": 1, "limit_usage": 5},
        )
        license.validate_license_key_with_usage("test-key", increment_usage=True)
        request = httpx_mock.get_request()
        body = json.loads(request.content)
        assert body["increment_usage"] == 1

    def test_does_not_send_increment_usage_when_false(self, httpx_mock):
        """Should not send increment_usage in request when False."""
        httpx_mock.add_response(
            url=license.POLAR_VALIDATE_URL,
            json={"status": "granted"},
        )
        license.validate_license_key_with_usage("test-key", increment_usage=False)
        request = httpx_mock.get_request()
        body = json.loads(request.content)
        assert "increment_usage" not in body

    def test_raises_device_limit_exceeded_when_at_limit(self, httpx_mock):
        """Should raise DeviceLimitExceeded when usage equals limit."""
        httpx_mock.add_response(
            url=license.POLAR_VALIDATE_URL,
            json={"status": "usage_exceeded", "usage": 5, "limit_usage": 5},
        )
        with pytest.raises(license.DeviceLimitExceeded) as exc_info:
            license.validate_license_key_with_usage("test-key")
        assert exc_info.value.usage == 5
        assert exc_info.value.limit == 5


class TestDeviceLimitExceeded:
    """Tests for DeviceLimitExceeded exception."""

    def test_stores_usage_and_limit(self):
        """Should store usage and limit values."""
        exc = license.DeviceLimitExceeded(3, 5)
        assert exc.usage == 3
        assert exc.limit == 5

    def test_message_contains_usage_info(self):
        """Should have descriptive message."""
        exc = license.DeviceLimitExceeded(3, 5)
        assert "3" in str(exc)
        assert "5" in str(exc)


class TestGetDeviceUsage:
    """Tests for get_device_usage function."""

    def test_returns_usage_tuple(self, httpx_mock):
        """Should return (usage, limit) tuple."""
        httpx_mock.add_response(
            url=license.POLAR_VALIDATE_URL,
            json={"status": "granted", "usage": 2, "limit_usage": 5},
        )
        result = license.get_device_usage("test-key")
        assert result == (2, 5)

    def test_returns_none_when_no_limit(self, httpx_mock):
        """Should return None when license has no limit."""
        httpx_mock.add_response(
            url=license.POLAR_VALIDATE_URL,
            json={"status": "granted", "usage": 0, "limit_usage": 0},
        )
        result = license.get_device_usage("test-key")
        assert result is None


class TestDisplayDeviceUsage:
    """Tests for display_device_usage function."""

    def test_displays_usage_info(self, capsys):
        """Should print usage information."""
        license.display_device_usage(2, 5)
        captured = capsys.readouterr()
        assert "2/5" in captured.out
        assert "3 more device(s)" in captured.out

    def test_displays_limit_reached(self, capsys):
        """Should indicate when limit is reached."""
        license.display_device_usage(5, 5)
        captured = capsys.readouterr()
        assert "5/5" in captured.out
        assert "reached your device limit" in captured.out


class TestActivateDevice:
    """Tests for activate_device function."""

    def test_saves_device_id_on_success(self, temp_config_dir: Path, device_id_file: Path, httpx_mock):
        """Should save device ID when activation succeeds."""
        httpx_mock.add_response(
            url=license.POLAR_VALIDATE_URL,
            json={"status": "granted", "usage": 1, "limit_usage": 5},
        )
        result = license.activate_device("test-key")
        assert result.valid is True
        assert device_id_file.exists()
        data = json.loads(device_id_file.read_text())
        assert data["device_id"] == license.get_hardware_id()

    def test_returns_invalid_result_on_invalid_key(self, temp_config_dir: Path, httpx_mock):
        """Should return invalid result when key is invalid."""
        httpx_mock.add_response(
            url=license.POLAR_VALIDATE_URL,
            status_code=404,
        )
        result = license.activate_device("invalid-key")
        assert result.valid is False
        assert "not found" in result.error.lower()

    def test_raises_device_limit_exceeded(self, temp_config_dir: Path, httpx_mock):
        """Should raise DeviceLimitExceeded when limit reached."""
        httpx_mock.add_response(
            url=license.POLAR_VALIDATE_URL,
            json={"status": "usage_exceeded", "usage": 5, "limit_usage": 5},
        )
        with pytest.raises(license.DeviceLimitExceeded):
            license.activate_device("test-key")


class TestHandleDeviceLimitExceeded:
    """Tests for handle_device_limit_exceeded function."""

    def test_raises_typer_abort(self):
        """Should raise typer.Abort."""
        with pytest.raises(typer.Abort):
            license.handle_device_limit_exceeded(5, 5)

    def test_displays_usage_info(self, capsys):
        """Should display usage information before aborting."""
        try:
            license.handle_device_limit_exceeded(3, 5)
        except typer.Abort:
            pass
        captured = capsys.readouterr()
        assert "3/5" in captured.out
        assert "contact support" in captured.out.lower()


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
        license_key = "cached-key"
        license_keys_file.write_text(json.dumps({"keys": [license_key]}))
        recent_time = datetime.now() - timedelta(hours=12)
        encrypted_timestamp = license.encrypt_timestamp(recent_time.isoformat(), license_key)
        validation_cache_file.write_text(json.dumps({
            "last_validated_at": encrypted_timestamp,
            "last_validated_key": license_key,
            "valid": True,
        }))

        result = license.check_license()
        assert result is True

    def test_revalidates_when_cache_expired(
        self, temp_config_dir: Path, license_keys_file: Path, validation_cache_file: Path, httpx_mock
    ):
        """Should revalidate when cache is expired."""
        license_key = "stored-key"
        license_keys_file.write_text(json.dumps({"keys": [license_key]}))
        old_time = datetime.now() - timedelta(days=2)
        encrypted_timestamp = license.encrypt_timestamp(old_time.isoformat(), license_key)
        validation_cache_file.write_text(json.dumps({
            "last_validated_at": encrypted_timestamp,
            "last_validated_key": license_key,
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

    def test_activates_new_device(
        self, temp_config_dir: Path, license_keys_file: Path, device_id_file: Path, httpx_mock
    ):
        """Should activate new device and save device ID."""
        httpx_mock.add_response(
            url=license.POLAR_VALIDATE_URL,
            json={"status": "granted", "usage": 1, "limit_usage": 5},
        )

        result = license.check_license(provided_key="new-key")

        assert result is True
        assert device_id_file.exists()
        data = json.loads(device_id_file.read_text())
        assert data["device_id"] == license.get_hardware_id()

    def test_does_not_increment_usage_for_activated_device(
        self, temp_config_dir: Path, license_keys_file: Path, device_id_file: Path, httpx_mock
    ):
        """Should not increment usage when device is already activated."""
        # Mark device as already activated
        device_id_file.write_text(json.dumps({"device_id": license.get_hardware_id()}))

        httpx_mock.add_response(
            url=license.POLAR_VALIDATE_URL,
            json={"status": "granted"},
        )

        result = license.check_license(provided_key="existing-key")

        assert result is True
        # Check that increment_usage was not sent
        request = httpx_mock.get_request()
        body = json.loads(request.content)
        assert "increment_usage" not in body

    def test_handles_device_limit_exceeded(
        self, temp_config_dir: Path, httpx_mock
    ):
        """Should handle device limit exceeded gracefully."""
        httpx_mock.add_response(
            url=license.POLAR_VALIDATE_URL,
            json={"status": "usage_exceeded", "usage": 5, "limit_usage": 5},
        )

        with pytest.raises(typer.Abort):
            license.check_license(provided_key="new-key")
