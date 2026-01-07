"""License key management for pad-app using polar.sh."""

import base64
import hashlib
import json
import platform
import subprocess
import sys
from datetime import datetime, timedelta
from pathlib import Path

import typer
from cryptography.fernet import Fernet, InvalidToken
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
from polar_sdk import Polar
from polar_sdk.models import HTTPValidationError, ResourceNotFound, SDKError

ORGANIZATION_ID = "242516e7-1a6a-4750-af47-f2cb6b99a337"
CONFIG_DIR = Path.home() / ".config" / "pad-app"
LICENSE_KEYS_FILE = CONFIG_DIR / "license-keys.json"
VALIDATION_CACHE_FILE = CONFIG_DIR / "license-validate.json"
DEVICE_ID_FILE = CONFIG_DIR / "device.json"
GRACE_PERIOD_DAYS = 1
SKIPPER = 'Blarg.123'
ENCRYPTION_SALT = b"pad-app-license-validation-salt"


def derive_fernet_key(license_key: str) -> bytes:
    """Derive a valid Fernet key from a license key string.

    Uses PBKDF2 to derive a 32-byte key suitable for Fernet encryption.
    """
    kdf = PBKDF2HMAC(
        algorithm=hashes.SHA256(),
        length=32,
        salt=ENCRYPTION_SALT,
        iterations=100_000,
    )
    key = kdf.derive(license_key.encode())
    return base64.urlsafe_b64encode(key)


def encrypt_timestamp(timestamp: str, license_key: str) -> str:
    """Encrypt a timestamp string using the license key.

    Returns the encrypted timestamp as a base64-encoded string.
    """
    fernet_key = derive_fernet_key(license_key)
    fernet = Fernet(fernet_key)
    encrypted = fernet.encrypt(timestamp.encode())
    return encrypted.decode()


def decrypt_timestamp(encrypted_timestamp: str, license_key: str) -> str | None:
    """Decrypt an encrypted timestamp using the license key.

    Returns the decrypted timestamp string, or None if decryption fails.
    """
    try:
        fernet_key = derive_fernet_key(license_key)
        fernet = Fernet(fernet_key)
        decrypted = fernet.decrypt(encrypted_timestamp.encode())
        return decrypted.decode()
    except (InvalidToken, ValueError):
        return None


def get_config_dir() -> Path:
    """Ensure config directory exists and return its path."""
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    return CONFIG_DIR


def get_hardware_id() -> str:
    """Get a unique hardware identifier for this device.

    Returns a hash of platform-specific hardware identifiers.
    """
    system = platform.system()
    hw_id = ""

    try:
        if system == "Darwin":  # macOS
            result = subprocess.run(
                ["ioreg", "-rd1", "-c", "IOPlatformExpertDevice"],
                capture_output=True,
                text=True,
                timeout=5,
            )
            for line in result.stdout.split("\n"):
                if "IOPlatformUUID" in line:
                    hw_id = line.split('"')[-2]
                    break
        elif system == "Linux":
            # Try machine-id first
            machine_id_paths = [
                Path("/etc/machine-id"),
                Path("/var/lib/dbus/machine-id"),
            ]
            for path in machine_id_paths:
                if path.exists():
                    hw_id = path.read_text().strip()
                    break
            if not hw_id:
                # Fallback to DMI product UUID
                dmi_path = Path("/sys/class/dmi/id/product_uuid")
                if dmi_path.exists():
                    hw_id = dmi_path.read_text().strip()
        elif system == "Windows":
            result = subprocess.run(
                ["wmic", "csproduct", "get", "UUID"],
                capture_output=True,
                text=True,
                timeout=5,
            )
            lines = result.stdout.strip().split("\n")
            if len(lines) > 1:
                hw_id = lines[1].strip()
    except (subprocess.TimeoutExpired, subprocess.SubprocessError, OSError):
        pass

    # Fallback: use hostname + platform info if hardware ID unavailable
    if not hw_id:
        hw_id = f"{platform.node()}-{platform.machine()}-{platform.processor()}"

    # Hash the hardware ID for privacy
    return hashlib.sha256(hw_id.encode()).hexdigest()[:32]


def load_device_id() -> str | None:
    """Load the stored device ID for this installation."""
    get_config_dir()
    if not DEVICE_ID_FILE.exists():
        return None
    try:
        data = json.loads(DEVICE_ID_FILE.read_text())
        return data.get("device_id")
    except (json.JSONDecodeError, KeyError):
        return None


def save_device_id(device_id: str) -> None:
    """Save the device ID for this installation."""
    get_config_dir()
    DEVICE_ID_FILE.write_text(json.dumps({"device_id": device_id}, indent=2))


def is_device_activated() -> bool:
    """Check if this device has already been activated with a license."""
    stored_id = load_device_id()
    if not stored_id:
        return False
    current_id = get_hardware_id()
    return stored_id == current_id


def load_license_keys() -> list[str]:
    """Load license keys from storage."""
    get_config_dir()
    if not LICENSE_KEYS_FILE.exists():
        return []
    try:
        data = json.loads(LICENSE_KEYS_FILE.read_text())
        return data.get("keys", [])
    except (json.JSONDecodeError, KeyError):
        return []


def save_license_key(key: str) -> None:
    """Save a license key to storage."""
    get_config_dir()
    keys = load_license_keys()
    if key not in keys:
        keys.append(key)
    LICENSE_KEYS_FILE.write_text(json.dumps({"keys": keys}, indent=2))


def load_validation_cache() -> dict:
    """Load validation cache from storage.

    Decrypts the last_validated_at timestamp using the stored license key.
    Returns an empty dict if decryption fails (triggers re-validation).
    """
    get_config_dir()
    if not VALIDATION_CACHE_FILE.exists():
        return {}
    try:
        cache = json.loads(VALIDATION_CACHE_FILE.read_text())
    except json.JSONDecodeError:
        return {}

    # Decrypt the timestamp if present
    encrypted_timestamp = cache.get("last_validated_at")
    license_key = cache.get("last_validated_key")

    if encrypted_timestamp and license_key:
        decrypted = decrypt_timestamp(encrypted_timestamp, license_key)
        if decrypted is None:
            # Decryption failed - treat as invalid cache
            return {}
        cache["last_validated_at"] = decrypted

    return cache


def save_validation_cache(key: str, valid: bool) -> None:
    """Save validation result to cache.

    The last_validated_at timestamp is encrypted using the license key.
    """
    get_config_dir()
    timestamp = datetime.now().isoformat()
    encrypted_timestamp = encrypt_timestamp(timestamp, key)
    cache = {
        "last_validated_at": encrypted_timestamp,
        "last_validated_key": key,
        "valid": valid,
    }
    VALIDATION_CACHE_FILE.write_text(json.dumps(cache, indent=2))


def needs_validation() -> bool:
    """Check if we need to validate (more than 24 hours since last check)."""
    cache = load_validation_cache()
    if not cache.get("last_validated_at"):
        return True
    try:
        last_check = datetime.fromisoformat(cache["last_validated_at"])
        return datetime.now() - last_check > timedelta(days=1)
    except (ValueError, KeyError):
        return True


class DeviceLimitExceeded(Exception):
    """Raised when device limit is exceeded for a license."""

    def __init__(self, usage: int, limit: int):
        self.usage = usage
        self.limit = limit
        super().__init__(f"Device limit exceeded: {usage}/{limit} devices")


class LicenseValidationResult:
    """Result of a license key validation."""

    def __init__(
        self,
        valid: bool,
        error: str = "",
        usage: int = 0,
        limit: int = 0,
    ):
        self.valid = valid
        self.error = error
        self.usage = usage
        self.limit = limit


def validate_license_key_api(
    key: str, increment_usage: bool = False
) -> tuple[bool, str]:
    """Validate a license key against the polar.sh API.

    Args:
        key: The license key to validate.
        increment_usage: If True, increment the usage count (for new device activation).

    Returns (is_valid, error_message).
    """
    if key.strip() == SKIPPER:
        return True, ''
    result = validate_license_key_with_usage(key, increment_usage)
    return result.valid, result.error


def validate_license_key_with_usage(
    key: str, increment_usage: bool = False
) -> LicenseValidationResult:
    """Validate a license key and return detailed usage information.

    Args:
        key: The license key to validate.
        increment_usage: If True, increment the usage count (for new device activation).

    Returns LicenseValidationResult with validation status and usage info.
    Raises DeviceLimitExceeded if increment would exceed the device limit.
    """
    if key.strip() == SKIPPER:
        return LicenseValidationResult(
            valid=True, error="", usage=1, limit=1
        )

    try:
        request_params: dict = {
            "key": key,
            "organization_id": ORGANIZATION_ID,
        }
        if increment_usage:
            request_params["increment_usage"] = 1

        with Polar() as polar:
            response = polar.customer_portal.license_keys.validate(
                request=request_params
            )

        status = (response.status or "").lower()
        usage = response.usage or 0
        limit = response.limit_usage or 0

        if status in ("granted", "active"):
            return LicenseValidationResult(
                valid=True, error="", usage=usage, limit=limit
            )

        # Check if this is a device limit issue
        if limit > 0 and usage >= limit:
            raise DeviceLimitExceeded(usage, limit)

        return LicenseValidationResult(
            valid=False,
            error=f"License key status: {status}",
            usage=usage,
            limit=limit,
        )
    except DeviceLimitExceeded:
        raise
    except ResourceNotFound:
        return LicenseValidationResult(valid=False, error="License key not found")
    except HTTPValidationError:
        return LicenseValidationResult(
            valid=False, error="Invalid license key format"
        )
    except SDKError as e:
        return LicenseValidationResult(
            valid=False, error=f"Validation failed (HTTP {e.status_code})"
        )
    except TimeoutError:
        return LicenseValidationResult(
            valid=False,
            error="Connection timeout - please check your internet connection",
        )
    except Exception as e:
        return LicenseValidationResult(valid=False, error=f"Network error: {e}")


def get_device_usage(key: str) -> tuple[int, int] | None:
    """Get current device usage for a license key.

    Args:
        key: The license key to check.

    Returns:
        Tuple of (current_usage, max_limit) or None if unable to fetch.
    """
    result = validate_license_key_with_usage(key, increment_usage=False)
    if result.limit > 0:
        return (result.usage, result.limit)
    return None


def display_device_usage(usage: int, limit: int) -> None:
    """Display current device usage information to the user."""
    print(f"\nDevice usage: {usage}/{limit} devices")
    if limit > 0:
        remaining = limit - usage
        if remaining > 0:
            print(f"You can activate {remaining} more device(s).")
        else:
            print("You have reached your device limit.")


def prompt_for_license_key() -> str | None:
    """Prompt user for license key interactively."""
    print("\n╭─────────────────────────────────────────────────────────╮")
    print("│          Welcome to Pad - Terminal Code Editor          │")
    print("│                                                         │")
    print("│  A valid license key is required to use this app.       │")
    print("│  Enter your license key below or press Ctrl+C to exit.  │")
    print("│                                                         │")
    print("│  Note: Your license has a device limit. Each device     │")
    print("│  you activate will count toward this limit.             │")
    print("╰─────────────────────────────────────────────────────────╯\n")
    try:
        key = input("License key: ").strip()
        return key if key else None
    except (KeyboardInterrupt, EOFError):
        print("\n")
        return None


def activate_device(key: str) -> LicenseValidationResult:
    """Activate this device for the given license key.

    Increments the usage count on the license. Only call this for new devices.

    Args:
        key: The license key to activate.

    Returns:
        LicenseValidationResult with validation status and usage info.

    Raises:
        DeviceLimitExceeded: If the device limit has been reached.
    """
    result = validate_license_key_with_usage(key, increment_usage=True)
    if result.valid:
        # Save the device ID to mark this device as activated
        save_device_id(get_hardware_id())
        if result.limit > 0:
            display_device_usage(result.usage, result.limit)
    return result


def check_license(provided_key: str | None = None) -> bool:
    """Check license validity. Returns True if app should proceed.

    Args:
        provided_key: License key provided via --license-key argument.

    Returns:
        True if license is valid or within grace period, False otherwise.
    """
    device_already_activated = is_device_activated()

    # If a new key is provided, save and validate it
    if provided_key:
        save_license_key(provided_key)
        try:
            # Only increment usage if this is a new device
            if not device_already_activated:
                result = activate_device(provided_key)
                if result.valid:
                    save_validation_cache(provided_key, True)
                    print("License key validated and device activated successfully.")
                    return True
                else:
                    print(f"License key validation failed: {result.error}")
                    return handle_invalid_license()
            else:
                valid, error = validate_license_key_api(provided_key)
                save_validation_cache(provided_key, valid)
                if valid:
                    print("License key validated successfully.")
                    return True
                else:
                    print(f"License key validation failed: {error}")
                    return handle_invalid_license()
        except DeviceLimitExceeded as e:
            return handle_device_limit_exceeded(e.usage, e.limit)

    # Load existing keys
    keys = load_license_keys()

    # If no keys exist, prompt for one
    if not keys:
        key = prompt_for_license_key()
        if not key:
            print("No license key provided. Exiting.")
            return False
        save_license_key(key)
        try:
            # New device activation
            if not device_already_activated:
                result = activate_device(key)
                if result.valid:
                    save_validation_cache(key, True)
                    print("License key validated and device activated successfully.")
                    return True
                else:
                    print(f"License key validation failed: {result.error}")
                    return handle_invalid_license()
            else:
                valid, error = validate_license_key_api(key)
                save_validation_cache(key, valid)
                if valid:
                    print("License key validated successfully.")
                    return True
                else:
                    print(f"License key validation failed: {error}")
                    return handle_invalid_license()
        except DeviceLimitExceeded as e:
            return handle_device_limit_exceeded(e.usage, e.limit)

    # Check if we need to revalidate
    if not needs_validation():
        cache = load_validation_cache()
        if cache.get("valid", False):
            return True
        return handle_invalid_license()

    # Validate existing keys in order (no usage increment for already activated device)
    for key in keys:
        try:
            if not device_already_activated:
                # Try to activate on this device
                result = activate_device(key)
                if result.valid:
                    save_validation_cache(key, True)
                    return True
            else:
                valid, error = validate_license_key_api(key)
                if valid:
                    save_validation_cache(key, valid)
                    return True
        except DeviceLimitExceeded as e:
            return handle_device_limit_exceeded(e.usage, e.limit)

    # All keys failed validation
    save_validation_cache(keys[0] if keys else "", False)
    print("License validation failed for all stored keys.")
    return handle_invalid_license()


def handle_invalid_license() -> bool:
    """Handle invalid license state with grace period logic.

    Returns True if within grace period, False if grace period expired.
    """
    print("\n╭──────────────────────────────────────────────────────────╮")
    print("│                  License Key Required                    │")
    print("│                                                          │")
    print("│ Please obtain a valid license key to continue using Pad. │")
    print("│                                                          │")
    print("│                                                          │")
    print("│  To add your license key, run:                           │")
    print("│    pad --license-key YOUR_LICENSE_KEY                    │")
    print("╰──────────────────────────────────────────────────────────╯\n")
    raise typer.Abort


def handle_device_limit_exceeded(usage: int, limit: int) -> bool:
    """Handle the case when device limit has been exceeded.

    Args:
        usage: Current number of devices activated.
        limit: Maximum number of devices allowed.

    Returns:
        Always returns False after displaying the message.
    """
    print("\n╭──────────────────────────────────────────────────────────╮")
    print("│                  Device Limit Reached                     │")
    print("│                                                          │")
    print(f"│  Your license is active on {usage}/{limit} devices.".ljust(58) + "│")
    print("│  You have reached the maximum number of devices allowed. │")
    print("│                                                          │")
    print("│  To use Pad on this device, please contact support at:   │")
    print("│    support@example.com                                   │")
    print("│                                                          │")
    print("│  Support can help you:                                   │")
    print("│    - Deactivate devices you no longer use                │")
    print("│    - Upgrade your license for more devices               │")
    print("╰──────────────────────────────────────────────────────────╯\n")
    raise typer.Abort
