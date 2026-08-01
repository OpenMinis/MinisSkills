---
name: quark-hub
version: 1.4.0
description: Quark Cloud Drive file management tool. Supports login, directory listing, saving shared links to your drive, downloading files, and creating directories. Login now uses minis-browser-use instead of the original project's Playwright. Trigger this skill when the user mentions "Quark Cloud Drive", "Quark download", "Quark save", "quark", or "pan.quark.cn".
---

# quark-hub

A Minis version of the Quark Cloud Drive tool, adapted from [ihmily/QuarkPanTool](https://github.com/ihmily/QuarkPanTool) (Apache-2.0).

## File Paths

| File | Path | Description |
|------|------|------|
| Main script | `/var/minis/skills/quark-hub/quark_hub.py` | Entry point for all commands |
| Share listing script | `/var/minis/skills/quark-hub/scripts/quark_share_ls.py` | Standalone script; no login required |
| **Cookie refresh script** | **`/var/minis/skills/quark-hub/scripts/refresh_cookie.sh`** | **Refresh the Cookie with one command** |
| **Cookie cache** | **`~/.quark_hub_cookie`** | Persists login state for reuse across sessions; permissions 600 |

## Dependencies

**No pip installation required**. Only native Alpine packages are needed (preinstalled on iSH):

| Package | Source | Purpose |
|---|---|---|
| `aiohttp` | Native Alpine (`py3-aiohttp`) | All async HTTP requests |
| Standard library | Built into Python | asyncio / json / re / urllib / threading, etc. |

If `aiohttp` is unavailable:

```bash
apk add py3-aiohttp
```

## Command Quick Reference

| Command | Login | Description |
|------|------|------|
| `ls-share <url>` | 🔓 Not required | List files in the root directory of a shared link |
| `tree-share <url>` | 🔓 Not required | Recursively expand the complete file tree of a shared link |
| `info` | 🔒 Required | View account information and storage capacity |
| `ls [fid]` | 🔒 Required | List your own cloud drive directory, including fid values |
| `save <url> [fid]` | 🔒 Required | Save shared files to your cloud drive, automatically checking whether they already exist |
| `dl <url> [dir]` | 🔒 Required | Download files from your own cloud drive to local storage, with a background thread and progress |
| `mkdir <name> [fid]` | 🔒 Required | Create a cloud drive directory |

## ⚡ Best Workflow for Saving and Downloading (Agents Must Read)

**When downloading files shared by others, follow this order to avoid duplicate saves:**

```
1. tree-share <url>           # See exactly what is in the share
2. ls [to_fid]                # Check whether the target cloud drive directory already has content with the same name
3a. Exists → download by fid directly    # Skip saving; use the existing fid to call api_get_download_urls
3b. Does not exist → save <url>          # Save to your drive (also checks internally and skips if it already exists)
4. ls [to_fid]                # Get the fid of the file after it has been saved
5. dl (pass extra_fids)       # Download in a background thread; automatically prints progress and 1-minute average speed
```

**Key: the `save` command now automatically checks whether a file with the same name already exists in the target directory and skips saving if it does.**
However, the agent should still run `ls` before calling `save` to confirm and avoid unnecessary network requests.

## Download Notes

- `dl` / `download_files_bg` can download only files in **your own cloud drive** due to Quark API restrictions.
- Files shared by others → first `save` to your drive → then `ls` to get the fid → then `dl`.
- Downloads run in a **background thread** and print progress every 10 seconds (downloaded / total size / percentage / 1-minute average speed).
- Download URLs point to Alibaba Cloud OSS, and headers must not include `Content-Type` (handled in the code).
- Files such as subtitles can be renamed during download with the `rename_map` parameter, for example to match the video filename.

## Code-Level API (for importing in scripts)

```python
from quark_hub import (
    ensure_cookie,           # Get/validate the Cookie; sys.exit(10) if invalid
    api_get_download_urls,   # Pass a fid list → return a list of dicts containing download_url
    download_files_bg,       # Download in a background thread; pass items=[{file_name, download_url, save_name?}]
    api_list_all,            # List a cloud drive directory
)
```

## Login Flow (performed by the agent)

**The script itself does not drive the browser.** When the script exits with **exit code 10**, login is required.
The agent completes login as follows:

### Step 1: Give the user a clickable login link

```markdown
Please log in to Quark Cloud Drive first: [Click to log in to Quark Cloud Drive](https://pan.quark.cn)
Let me know once you have finished logging in.
```

### Step 2: After the user confirms login, extract and save the Cookie

```bash
sh /var/minis/skills/quark-hub/scripts/refresh_cookie.sh
```

### Step 3: Verify that login succeeded

```bash
python3 /var/minis/skills/quark-hub/quark_hub.py info
```

## Usage Examples

```bash
S=/var/minis/skills/quark-hub/quark_hub.py

# 🔓 No login required
python3 $S ls-share   "https://pan.quark.cn/s/xxxxxxxx"
python3 $S tree-share "https://pan.quark.cn/s/xxxxxxxx"

# 🔒 Login required
python3 $S info
python3 $S ls
python3 $S ls <fid>
python3 $S save "https://pan.quark.cn/s/xxxxxxxx"         # Automatically checks existing content → skip or save
python3 $S save "https://pan.quark.cn/s/xxxxxxxx?pwd=1234" <target_fid>
python3 $S dl   "https://pan.quark.cn/s/xxxxxxxx" /var/minis/workspace/
python3 $S mkdir My Movies
```

## Notes

- Cookies are valid for about 7-30 days. Log in again after they expire.
- Use for illegal purposes is strictly prohibited. This tool only calls the official Quark API.
