---
name: shortcut-share-file
version: 2.1.0
description: Share iCloud Drive files using the iOS Shortcut "Instant Share." Trigger this skill when the user mentions file-sharing actions such as "share a file," "transfer a file," "send a file," "share with xxx," "share using a Shortcut," or "send a file from the backup." Supports passing any file path under the iCloud Drive backup directory to the Shortcut.
---

# Share Files, "Instant Share" Shortcut

Shortcut link: https://www.icloud.com/shortcuts/c0cd9fbdc42149c3b98e4f9fcb103011

## Core Principles

- **No processing and no checks**: Do not unzip, list contents, inspect file types, or confirm that the file exists. Go directly to the sharing workflow.
- **File path**: The source file is mapped in iCloud to `/var/minis/mounts/iCloud/Instant Share/`. Pass the parameter as `Instant Share/<filename>` (a relative path, not an absolute path).

## Workflow

### A. Speed Test (Use the cached memory first)

```
memory_get(keywords="iperf3 Speed Test: Upload Speed")
```

- If a record exists and is less than 24 hours old, use the `upload_MBs` value directly.
- If no record exists or the record has expired, run:

```
iperf3 -c ping.online.net -t 3 --json 2>/dev/null | python3 -c "import sys,json;d=json.load(sys.stdin);bps=d['end']['sum_sent']['bits_per_second'];print(f'{bps/8000000:.2f}')"
```

The output is in MB/s (megabytes per second). Write it to memory immediately:

```
memory_write(content="## Speed Cache\n- upload_MBs: <Value> (<Date>)\n- Valid for 24 hours")
```

### B. Copy the File (If Needed) and Calculate the Time

If the file is not under `/var/minis/mounts/iCloud/Instant Share/`:

```
cp <Source file path> /var/minis/mounts/iCloud/Instant Share/<filename>
```

Calculate the parameter suffix:

- **From another iCloud directory** → `--0Second`
- **From an external source such as attachments** → `--<ceil(file_size_MB / upload_MBs * 1.2)>Second` (add a 20% buffer to handle network fluctuations)

### C. Invoke the Shortcut

```
apple-open "shortcuts://run-shortcut?name=%E6%9E%81%E9%80%9F%E5%88%86%E4%BA%AB&input=text&text=%E6%9E%81%E9%80%9F%E5%88%86%E4%BA%AB/<filename>--<time>Second"
```

## User Feedback

"The Shortcut has started. When it finishes, the link will be copied to the clipboard automatically. You can paste and send it directly."

---

## Bundled Resources

- [Help Documentation](minis://skills/shortcut-share-file/references/Help%20Documentation.md) - Installation steps, feature overview, and usage guide. Provide this when the user has questions.
