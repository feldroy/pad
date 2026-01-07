# Requirement: HTTPX to Polar SDK

The current implementation of @tests/pad/license.py uses httpx. We want to switch all uses of httpx to use Polar's official SDK. 

Reference: https://pypi.org/project/polar-sdk/

Requirements:

- Convert use of httpx to polar-sdk
- Tests need to still pass
- Map httpx errors to the most obvious polar-sdk errors
- Implement a mocking strategy to replace pytest-httpx
- If we are no longer using httpx, remove it from our dependency list
- Keep the SKIPPER bypass with the hardcoded key for now
