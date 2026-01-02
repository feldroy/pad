# Requirement: License Key for pad-app users

All users of the app must provide a valid license key to access its features. The license key ensures that only authorized users can utilize the application.

## Specification

- Users must enter the license key upon first launch of the application
- The license manager will be polar.sh per these instructions: https://polar.sh/docs/features/benefits/license-keys
- The license key will be checked daily to ensure continued access via the "Validate License Keys" feature in the docs above
- The test license key is `FOUNDATION--77034B4F-8640-4839-8AE3-2E5FD2035607`, this is for development and testing purposes, but is not to be included in the app itself
- Our organization ID is `242516e7-1a6a-4750-af47-f2cb6b99a337`
- The license key is stored in a standard location for license keys on the user's system. As defined in ~/.config/pad-app/license-keys.json. The user can have multiple license keys and each will be checked in order
- If the license key is invalid or missing, the user will be given a 1 day grace period to enter a valid license key to continue using the application. If the grace period is over, the user the application will exit and a message is printed in the shell explaining the user needs to contact the server
- The license key is entered either via an interactive prompt on first launch or by passing the argument `--license-key YOUR_LICENSE_KEY` when launching the application
- There is just one tier for the license key, which unlocks all features of the application
- Cache the last successful license key validation timestamp in a file at ~/.config/pad-app/license-validate.json to avoid unnecessary checks
- The license key does not need to be obfuscated or encrypted in storage
- The user must be online in order to validate the license key