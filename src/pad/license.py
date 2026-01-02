"""License key management for pad-app using polar.sh."""

import json
import sys
from datetime import datetime, timedelta
from pathlib import Path
import typer

import httpx

ORGANIZATION_ID = "242516e7-1a6a-4750-af47-f2cb6b99a337"
POLAR_VALIDATE_URL = "https://api.polar.sh/v1/customer-portal/license-keys/validate"
CONFIG_DIR = Path.home() / ".config" / "pad-app"
LICENSE_KEYS_FILE = CONFIG_DIR / "license-keys.json"
VALIDATION_CACHE_FILE = CONFIG_DIR / "license-validate.json"
GRACE_PERIOD_DAYS = 1


def get_config_dir() -> Path:
    """Ensure config directory exists and return its path."""
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    return CONFIG_DIR


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
    """Load validation cache from storage."""
    get_config_dir()
    if not VALIDATION_CACHE_FILE.exists():
        return {}
    try:
        return json.loads(VALIDATION_CACHE_FILE.read_text())
    except json.JSONDecodeError:
        return {}


def save_validation_cache(key: str, valid: bool) -> None:
    """Save validation result to cache."""
    get_config_dir()
    cache = load_validation_cache()
    cache["last_validated_at"] = datetime.now().isoformat()
    cache["last_validated_key"] = key
    cache["valid"] = valid
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


def validate_license_key_api(key: str) -> tuple[bool, str]:
    """Validate a license key against the polar.sh API.

    Returns (is_valid, error_message).
    """
    try:
        response = httpx.post(
            POLAR_VALIDATE_URL,
            json={"key": key, "organization_id": ORGANIZATION_ID},
            timeout=10.0,
        )
        if response.status_code == 200:
            data = response.json()
            # print(data)
            status = data.get("status", "").lower()
            if status in ("granted", "active"):
                return True, ""
            return False, f"License key status: {status}"
        elif response.status_code == 404:
            return False, "License key not found"
        elif response.status_code == 422:
            return False, "Invalid license key format"
        else:
            return False, f"Validation failed (HTTP {response.status_code})"
    except httpx.TimeoutException:
        return False, "Connection timeout - please check your internet connection"
    except httpx.RequestError as e:
        return False, f"Network error: {e}"


def prompt_for_license_key() -> str | None:
    """Prompt user for license key interactively."""
    print("\n╭─────────────────────────────────────────────────────────╮")
    print("│          Welcome to Pad - Terminal Code Editor          │")
    print("│                                                         │")
    print("│  A valid license key is required to use this app.       │")
    print("│  Enter your license key below or press Ctrl+C to exit.  │")
    print("╰─────────────────────────────────────────────────────────╯\n")
    try:
        key = input("License key: ").strip()
        return key if key else None
    except (KeyboardInterrupt, EOFError):
        print("\n")
        return None


def check_license(provided_key: str | None = None) -> bool:
    """Check license validity. Returns True if app should proceed.

    Args:
        provided_key: License key provided via --license-key argument.

    Returns:
        True if license is valid or within grace period, False otherwise.
    """
    # If a new key is provided, save and validate it
    if provided_key:
        save_license_key(provided_key)
        valid, error = validate_license_key_api(provided_key)
        save_validation_cache(provided_key, valid)
        if valid:
            print("License key validated successfully.")
            return True
        else:
            print(f"License key validation failed: {error}")
            return handle_invalid_license()

    # Load existing keys
    keys = load_license_keys()

    # If no keys exist, prompt for one
    if not keys:
        key = prompt_for_license_key()
        if not key:
            print("No license key provided. Exiting.")
            return False
        save_license_key(key)
        valid, error = validate_license_key_api(key)
        save_validation_cache(key, valid)
        if valid:
            print("License key validated successfully.")
            return True
        else:
            print(f"License key validation failed: {error}")
            return handle_invalid_license()

    # Check if we need to revalidate
    if not needs_validation():
        cache = load_validation_cache()
        if cache.get("valid", False):
            return True
        return handle_invalid_license()

    # Validate existing keys in order
    for key in keys:
        valid, error = validate_license_key_api(key)
        if valid:
            save_validation_cache(key, valid)
            return True

    # All keys failed validation
    save_validation_cache(keys[0] if keys else "", False)
    print("License validation failed for all stored keys.")
    return handle_invalid_license()


def handle_invalid_license() -> bool:
    """Handle invalid license state with grace period logic.

    Returns True if within grace period, False if grace period expired.
    """
    cache = load_validation_cache()
    last_validated = cache.get("last_validated_at")

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

    # if not last_validated:
    #     # First failure - start grace period
    #     save_validation_cache("", False)
    #     print(f"You have {GRACE_PERIOD_DAYS} day(s) to enter a valid license key.")
    #     return True

    # try:
    #     last_check = datetime.fromisoformat(last_validated)
    #     grace_end = last_check + timedelta(days=GRACE_PERIOD_DAYS)

    #     if datetime.now() < grace_end:
    #         remaining = grace_end - datetime.now()
    #         hours = int(remaining.total_seconds() / 3600)
    #         print(f"Grace period active. {hours} hour(s) remaining to enter a valid license key.")
    #         print("Use: pad --license-key YOUR_KEY")
    #         return True
    #     else:
    #         print("\n╭─────────────────────────────────────────────────────────╮")
    #         print("│                  License Key Required                    │")
    #         print("│                                                          │")
    #         print("│  Your grace period has expired. Please obtain a valid    │")
    #         print("│  license key to continue using Pad.                      │")
    #         print("│                                                          │")
    #         print("│  To add your license key, run:                           │")
    #         print("│    pad --license-key YOUR_LICENSE_KEY                    │")
    #         print("╰─────────────────────────────────────────────────────────╯\n")
    #         raise typer.Abort
        
    # except ValueError:
    #     # Invalid date in cache - reset and allow grace period
    #     save_validation_cache("", False)
    #     print(f"You have {GRACE_PERIOD_DAYS} day(s) to enter a valid license key.")
    #     return True
