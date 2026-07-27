---
name: asc-cli
description: Use the asc (App Store Connect CLI) to manage iOS/macOS apps — TestFlight builds, beta groups, distribution, App Store submissions, release, user reviews, analytics reports, crash logs, and more. Triggers when user mentions "asc", "TestFlight", "beta test", "app store review", "App Store Connect", "release v1.x", "public tester", "add build to test", "check crashes", "what's new", "store listing", "submit to app store review", "approve and release", or any App Store Connect operation.
---

# ASC CLI

Use `asc` to manage App Store Connect from the command line.

## Installation

iSH (Alpine Linux, aarch64) uses the prebuilt `linux_arm64` binary from GitHub Releases.

```bash
# 1. Check latest version at https://github.com/rorkai/App-Store-Connect-CLI/releases/latest
# 2. Download linux_arm64 binary
VERSION="1.2.6"  # or latest
curl -L -o /usr/local/bin/asc \
  "https://github.com/rorkai/App-Store-Connect-CLI/releases/download/${VERSION}/asc_${VERSION}_linux_arm64"
chmod +x /usr/local/bin/asc

# 3. Verify
asc version
```

**Updating**: Repeat the same `curl` + `chmod` with the new version.

**macOS (separate machine)**: Use `brew install asc` or the `macOS_arm64` binary.

## Auth Setup

### Getting an API Key (Step-by-Step Guide)

App Store Connect uses API keys for machine-to-machine access. The user needs an Apple Developer account with the appropriate role: Account Holder, Admin, or App Manager.

**Step 1 - Open the API Keys page:**

Tell the user to visit [App Store Connect -> Users and Access -> Integrations -> API Keys](https://appstoreconnect.apple.com/access/integrations/api). They must sign in with their Apple Developer account.

**Step 2 - Generate a private key:**

Click the "+" button, give the key a name (for example, "Minis CI"), and choose the access role:

- **App Manager**: Enough for TestFlight builds, App Store submissions, and reviews.
- **Admin**: Needed for user management, agreements, and finance reports.

After clicking "Generate", a `.p8` private key file downloads immediately. **Save it. Apple only shows the download link once.**

**Step 3 - Collect three pieces of information:**

The API Keys page shows a table. Find the newly created key row:

- **Key ID**: The 10-character string in the first column, for example, `ABC123XYZ9`.
- **Issuer ID**: Shown at the top of the page, a UUID like `aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee`.
- **Private key file**: The `.p8` file downloaded in Step 2.

**Step 4 - Get the `.p8` file into iSH:**

The user can share the `.p8` file to Minis as an attachment, or place it in a mounted folder under `/var/minis/mounts/`.

**Step 5 - Run auth login:**

iSH has no system keychain, so use `--bypass-keychain`:

```bash
# Copy the .p8 into /root/ (not /tmp/ - /tmp is wiped on restart)
cp /var/minis/attachments/AuthKey_XXXX.p8 /root/AuthKey_XXXX.p8
chmod 600 /root/AuthKey_XXXX.p8

asc auth login --bypass-keychain \
  --name "ProfileName" \
  --key-id "KEY_ID" \
  --issuer-id "ISSUER_ID" \
  --private-key /root/AuthKey_XXXX.p8
```

**Step 6 - Verify:**

```bash
asc auth status --validate
# Should show "validation: works"
asc apps list --output table
# Should list the user's apps
```

### Detecting and Handling Auth Problems

When a user asks to do something with `asc` but auth is not set up yet, **do not run the command blindly**. Instead:

1. Run `asc auth status --validate 2>&1` to check the current state.
2. If it returns an error or shows no credentials, tell the user:
   > "asc has not been configured for authentication yet. You need an App Store Connect API Key. Would you like me to walk you through generating one step by step?"
3. If the user agrees, walk them through Steps 1-6 above.
4. If the user already has a `.p8` file but has not configured auth, just do Steps 5-6.
5. If `asc` is not installed, see [Installation](#installation) first.

### Auth Files Location

- Config: `/root/.asc/config.json`
- Private Key: `/root/AuthKey_*.p8`

Both must be in `/root/` for persistence across iSH restarts. `/tmp/` is lost on reboot.

## Environment

- **Installed**: `/usr/local/bin/asc` (`linux_arm64` binary, iSH Alpine)
- **Auth**: `/root/.asc/config.json`, private key at `/root/AuthKey_*.p8`

## Core Workflows

### 1. List Apps

```bash
asc apps list --output table
```

Get `APP_ID` from the output. All subsequent commands need `--app APP_ID`.

### 2. TestFlight

**List builds:**

```bash
asc builds list --app APP_ID --output table
```

**List beta groups:**

```bash
asc testflight groups list --app APP_ID --output table
```

**Add build to public beta group + submit review:**

```bash
asc publish testflight \
  --app APP_ID \
  --build BUILD_ID \
  --group "GROUP_ID" \
  --test-notes "Notes" \
  --locale "en-US" \
  --submit --confirm
```

**View tester metrics:**

```bash
asc testflight metrics app-testers --app APP_ID --paginate --output json
```

**List crash submissions:**

```bash
asc testflight crashes list --app APP_ID --paginate --output json
```

**Get crash log:**

```bash
asc testflight crashes log --submission-id SUBMISSION_ID
```

### 3. App Store Release

**Stage version (create version + copy metadata + attach build):**

```bash
asc release stage \
  --app APP_ID \
  --version "1.X" \
  --build BUILD_ID \
  --copy-metadata-from "1.Y" \
  --exclude-fields "whatsNew" \
  --confirm
```

**Update what's new (en-US):**

```bash
asc localizations update \
  --version VERSION_ID \
  --locale "en-US" \
  --whats-new "Release notes text..."
```

**Create Chinese locale:**

```bash
asc localizations create --version VERSION_ID --locale "zh-Hans"
```

**Fill required fields for new locale:**

```bash
asc localizations update \
  --version VERSION_ID \
  --locale "zh-Hans" \
  --description "App description" \
  --keywords "keyword1,keyword2" \
  --support-url "https://..." \
  --whats-new "Release Notes"
```

**Validate readiness:**

```bash
asc validate --app APP_ID --version "1.X"
```

**Submit for review:**

```bash
asc review submit --app APP_ID --version "1.X" --build BUILD_ID --confirm
```

**Release after approval (manual release):**

```bash
asc versions release --version-id VERSION_ID --confirm
```

### 4. User Reviews

```bash
asc reviews list --app APP_ID --output table
```

### 5. Auth and General

```bash
asc auth status --validate    # Check auth health
asc version                   # Show version
asc <command> --help          # Built-in help is authoritative
```

## Idempotent Operations

- Adding a build to a group multiple times is safe. It returns "already has beta app review submission".
- `release stage` with `--confirm` is idempotent. It creates the version only if it does not already exist.
- `builds list` always shows the latest builds at the top; use `head -N` to limit the output.

## Notes

- No real-time download/install counts per build. The Apple API only returns cumulative tester-level metrics.
- The Crashes API does not expose the build number. Filter by upload timestamp instead.
- TestFlight builds are valid for 90 days from upload.
- Always use `--confirm` on destructive commands; try `--dry-run` first where available.
- Metrics return sessions/crashes per tester over 365 days by default.
