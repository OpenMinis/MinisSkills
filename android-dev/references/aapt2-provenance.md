# ARM64 AAPT2 provenance

Bootstrap downloads a pinned third-party AAPT2 for reproducible Minis/Alpine ARM64 builds; the binary is intentionally **not redistributed in this skill** because the upstream repository declares no license.

- Source: `https://github.com/Sou6900/aapt2---linux-arm64`
- Commit: `00b3f95e6858517f1fa1b7aa9b76509cbca027dc`
- Source path: `arm64-v8/aapt2`
- Pinned raw URL: `https://raw.githubusercontent.com/Sou6900/aapt2---linux-arm64/00b3f95e6858517f1fa1b7aa9b76509cbca027dc/arm64-v8/aapt2`
- SHA-256: `b7410d29c2925daf7fb82f701fdd10cf87397687801137385b01b958ada52e5f`
- Format: ELF 64-bit AArch64, statically linked
- Reported version: AAPT2 2.19
- Verified compatibility: Android Platform 34
- Known incompatibility: Android Platform 35 resource table (`illegal map type 'string' (22)`)
- Upstream license: not declared as of the pinned commit

Treat this as a pinned external dependency, not an official Google ARM64 Linux release. Never replace it with an unpinned search result. A future replacement must have a clear redistribution license, be checksum-pinned, architecture-inspected, tested against `android.jar`, staged atomically, and rolled back on failure.
