# Choosing Objective-C or Swift

## Selection policy

1. Follow the user's requested language. Never silently replace Swift with Objective-C because a toolchain is missing.
2. For an existing project, preserve its language and build settings.
3. For new modern apps, prefer Swift when a compatible compiler/SDK is available. UIKit is callable from both languages; UIKit does not mean Objective-C.
4. Choose Objective-C/C for small UIKit demos, runtime APIs, existing C/Objective-C libraries, or when only clang and an older SDK are available.
5. If Swift prerequisites are missing, install/configure them or explain the blocker. Ask about changing language only when it changes the implementation.

| Project | Template | Compiler |
|---|---|---|
| Objective-C/C Hello | `assets/hello` | clang |
| Objective-C paging demo | `assets/swipe` | clang |
| Swift UIKit + WKWebView browser | `assets/browser` | swift-frontend, then clang + Mach-O linker |

Both language paths share provisioning, signing, packaging, installation and verification. Same-target cross-language calls via bridging headers/generated Swift headers are not configured; reject such projects clearly rather than claiming mixed-language interoperability.

## Reusable project configuration

```yaml
name: MyApp
bundle_id: com.example.myapp    # replace with the identifier authorized by your profile
language: swift               # auto (default), swift, or objc (allows C)
# sdk: /path/to/iPhoneOS.sdk   # optional; resolves from IOSDEV_SDK or installed SDKs
sources: [src/*.swift]
frameworks: [UIKit, Foundation, WebKit]
swift_version: "5"            # language mode, not compiler release
swift_optimize: true
sign:
  mode: adhoc                 # structural test only; configure your own p12/profile for device install
```

For Objective-C use `language: objc` and `sources: [src/*.m, src/*.c]`. In auto mode, the builder discovers `.m`, `.c` and `.swift` files. The build log reports the selected language; the IPA name and app identifier say nothing about source language.

Compiler selection: `SWIFT_FRONTEND` overrides discovery; otherwise search the executable PATH and the usual installed Swift toolchain. SDK selection: explicit `sdk` → `IOSDEV_SDK` → installed SDK discovery. No user account, device identifier or signing credential belongs in a template.

## SDK compatibility and caching

A compiler must be able to parse the SDK's Swift interfaces and import its Clang modules. Do not infer compatibility solely from the device OS or SDK filename. Check the installed compiler and SDK interfaces. Known compiler/SDK combinations are examples, not universal minimum versions. If module loading fails, inspect the first underlying diagnostic before treating the generic “SDK not supported” message as definitive.

The first Swift build can spend minutes generating SDK modules; later builds reuse the cache. Cache identity includes compiler and SDK paths, compiler version and build flags. Changing compiler, SDK, flags or source files must invalidate the object cache. Never copy another device's compiled module cache as a required setup step.

Use a separate Darwin resource directory containing only the compiler's Clang headers; do not accidentally import Linux Swift modules into an iOS build. Link against the SDK's Darwin Swift stubs, not Linux static libraries. Build all Swift sources as a single module; an `@main` entry uses `-parse-as-library`, while a top-level entry conventionally lives in `main.swift`.

## Verification

Report language-specific compilation separately. A successful IPA build is not proof of installation, and a running process is not proof of correct UI. Verify in order: build → correct development signature/profile → install → read back app metadata → launch → check process survival/logs → observe UI if available. Diagnose pairing using the configured record and current device; do not assume an old record is still trusted. Warn before overwriting an app with the same Bundle ID.
