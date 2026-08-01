# Instant Share — iOS Shortcuts Help

> Share an iCloud Drive URL with one tap using Minis

---

## 📲 Install the Shortcut

🔗 **[Click here to install Instant Share](https://www.icloud.com/shortcuts/c0cd9fbdc42149c3b98e4f9fcb103011)**

Installation steps:

1. Open the link above in Safari
2. Tap "Get Shortcut"
3. Scroll to the bottom and tap "Add Shortcut"
4. Confirm that it appears in the "Shortcuts" app
5. The Instant Share skill depends on the shortcut
6. On first use, tap "Allow" for all permission prompts

> If you see a "Cannot Open" message, first go to `Settings → Shortcuts → Allow Untrusted Shortcuts` and turn it on.

---

## How It Works

```
User says "Share file"
       ↓
Minis speed test (checks the memory cache or runs an actual iperf3 test)
       ↓
Copy the file to the iCloud/Instant Share/ directory
       ↓
Calculate the estimated upload time → append the parameter --<time>Second
       ↓
Call the shortcuts:// URL scheme
       ↓
The shortcut automatically copies the share link to the clipboard
```

## Parameter Suffix Rules

| Source | Suffix | Example |
|------|------|------|
| Existing file in iCloud | `--0Second` | `Instant Share/Report.pdf--0Second` |
| attachments and other external sources | `--<seconds>Second` | `Instant Share/Photo.jpg--25Second` |

- Keep the original filename; pass Chinese characters directly
- `Second` represents the number of seconds, calculated as file size divided by measured upload speed

---

## ❓ Frequently Asked Questions

**Q: Getting the message "iCloud directory does not exist"?**

A: First, mount iCloud as external storage in Minis and rename the folder to "iCloud." The shortcut will automatically create the `Instant Share` folder the first time it runs.

**Q: Will files remain in iCloud Drive after sharing?**

A: Yes. Files remain under `iCloud Drive/Instant Share/`. You can delete them manually if you need to clean them up.

---

*Last updated: May 2, 2026*
