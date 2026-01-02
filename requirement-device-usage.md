# Requirement: License Key Usage to limit number of devices

- Licenses will only accept so many devices, tracked in the usage field here: https://polar.sh/docs/features/benefits/license-keys#param-increment-usage. 
- When a license is activated on a new device, the usage count is incremented.
- If the usage count exceeds the allowed number of devices for that license, the license validation will fail.
- The application must handle license validation failures due to exceeding device limits by notifying the user and providing instructions on how to manage their devices or upgrade their license.
- Users should be informed about the device limit when they enter their license key for the first time.
- The application should provide a way for users to view their current device usage and the maximum allowed devices for their license.
- If a user attempts to activate a license on a new device that would exceed the device limit, they need to be told to contact support for assistance.
- The application must ensure that device usage is accurately tracked and updated each time a license is activated on a device.
- Licenses can't be deactivated from within the application; users must contact support
- A device is uniquely identified by its hardware id
- This needs to build off the code already in @src/pad/license.py.
- Tests that already exist for @src/pad/license.py must continue to pass