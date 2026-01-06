# Specification: Encrupt last validated at

When we save last_validated_at in the license.py module, we want to encrypt it so users dont just modify the value themselves.

- When `last_validated_at` is saved in `license_validate.json`, it needs to be encrypted
- When `last_validated_at` is read from `license_validate.json`, it needs to be decryped so it can be used
- The encryption algorythm should be fernet.
- If the decryption failes, treat it like the user needs to supply the license key again
- The encryption key will be the license key 