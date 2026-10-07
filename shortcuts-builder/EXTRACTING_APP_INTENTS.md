# Extracting Third-Party App Intents (maintainer guide)

How the catalog behind `THIRD_PARTY_INTENTS.md` was produced, and how to extend or refresh it. This is for **adding or updating apps**. Day-to-day shortcut building does not need it: use `scripts/appintent_catalog.py`.

## 1. What is being extracted, and why it works

Every iOS app that exposes App Intents ships a build-time metadata folder inside its package:

```text
Payload/<App>.app/Metadata.appintents/extract.actionsdata      <- the app itself
Payload/<App>.app/PlugIns/<X>.appex/Metadata.appintents/...    <- app extensions
Payload/<App>.app/Extensions/<X>.appex/Metadata.appintents/...
Payload/<App>.app/Frameworks/<X>.framework/Metadata.appintents/...
Payload/<App>.app/Watch/<W>.app/Metadata.appintents/...        <- Apple Watch companion
```

- `extract.actionsdata` is **plain JSON**. It is not encrypted, so no decryption of the app is needed.
- It lists the app's intents (`actions`), their parameters, enums (`enums`), entities (`entities`), queries and Siri phrases.
- An app can have several of these files (main app, each extension, each framework, the Watch app). Of the 894 harvested directories, the files came from: main app 183, `PlugIns` 164, `Extensions` 22, `Watch` 20, `Frameworks` 5.
- An app can have several of these files. **Collect all of them**; an intent can live in an extension, and the catalog records which component it came from (`c` field).
- The folder is generated at build time, so it matches the exact app version that was read. Re-read it after the app updates.

An app with no `Metadata.appintents` folder simply exposes no App Intents. That is a real result, not a failure (about 680 of 940 apps checked had none).

## 2. Ways to get the files

| Way | Cost | Needs | Use when |
|---|---|---|---|
| **Read only the needed ZIP entries over HTTP Range** | Small: a few hundred KB per app | A logged-in `ipatool` build with a `fetch-intents` command | Default, many apps |
| Download the whole IPA, then unzip the entries | Hundreds of MB per app | A logged-in `ipatool` | The range method fails for that app |
| Take the file from a `.ipa` or `.app` you already have | None | The package | A single app you already hold |
| Read from a Mac with the app installed | None | The Mac | The app is a macOS or Catalyst app |

An IPA is a ZIP file. Its central directory (the table of contents) sits at the end of the file. The range method fetches that directory, then fetches only the `Metadata.appintents/*` entries, and writes them **byte for byte**. Results were compared with extraction from a full download and were byte-identical. About 760 apps in the harvest were read this way; the earlier ~130 were extracted from full downloads (`method` is empty in their `info.json`).

### 2.1 Tooling that was used

- The official `ipatool` with the fix from upstream PR #609 (the authentication URL needs a trailing `/`; without it login fails with 301/404/204).
- A local build named `ipatool-fetch` adding a `fetch-intents` command:

```bash
ipatool-fetch fetch-intents -b <bundle id> -o <output dir> [--platform iphone|ipad|appletv|visionos]
# or by App Store id:  -i <track id>
```

- A small batch driver that, for each app: resolves the name to a bundle id and store id (search only), calls `fetch-intents`, records the result, and waits between apps.

Run these on a **Mac** that is logged in to `ipatool`. Do not try to sign in from iSH: Apple's login handshake gives wrong results under the CPU emulation used there.

## 3. Rules that must hold (safety and honesty)

1. **Credentials never pass through the agent.** The user signs in to `ipatool` themselves in their own terminal window. Never ask for, read, log or store an Apple ID password or a verification code. Log lines must be scrubbed of e-mail addresses.
2. **Never buy anything.** Do not pass `--purchase` unless the user explicitly agrees for that specific app. Apps the account does not own are listed and skipped (`need_purchase`), not acquired.
3. **Read only, keep originals.** Save the files unmodified and record a SHA-256 for each. Do all cleaning in a separate step, never in the raw copy.
4. **Do not keep IPAs.** If a full download was needed, delete the IPA right after extraction and check free disk space first.
5. **Throttle.** Wait several seconds between apps and stop on the first sign of rate limiting. Provide a stop switch (a `STOP` file the loop checks).
6. **Stage, then merge.** Write new data to a staging directory, validate it, and only then add it to the catalog.
7. **Only the account's own apps.** Metadata reflects what that account's storefront can see.

## 4. Procedure

1. **Decide the list.** Names or bundle ids. Prefer apps the user actually has.
2. **Resolve.** Turn each name into a bundle id and store id with a search, nothing downloaded. Apps not found in that storefront are recorded as unavailable.
3. **Check ownership.** Apps not owned are skipped and recorded (`need_license` / `need_purchase`).
4. **Fetch** with `fetch-intents` into `apps/<bundleID>__<name>/`.
5. **Verify**: for every saved file, recompute SHA-256 and compare with `info.json`; confirm `extract.actionsdata` parses as JSON.
6. **Index**: record per app `status` (`done`, `no_appintents`, `need_license`, `error`), the app version, the region, and the method used.
7. **Rebuild the catalog** (section 5) and run the regression tests.

Directory layout used:

```text
apps/<bundleID>__<name>/
  info.json                                  bundle id, version, region, method, per-file sha256
  main__extract.actionsdata                  the app itself
  PlugIns_<X>.appex__extract.actionsdata     one per extension
  Frameworks_<X>.framework__extract.actionsdata
  Watch_<W>.app__extract.actionsdata
INDEX.json   need_purchase.json   unavailable.json   README.md
```

## 5. Turning raw files into the catalog

Keep the raw files out of the skill (they were about 15 MB for 213 apps). Ship only a slim extract:

- Keep only **discoverable** actions (`isDiscoverable` is not false).
- Per action: summary text, description, output type, whether it opens the app, the component it came from.
- Per parameter: `name` (the key used in the shortcut), title, kind, optional flag, input flag.
- Per enum: its cases (`id` and display title).
- Compress to `data/thirdparty-appintents.json.gz` (about 106 KB for about 1,700 actions).

Parameter `kind` is derived from `valueType`. The primitive numbers below were read from the parameter titles that use them; treat the mapping as observed, not as an Apple contract:

| `primitive` typeIdentifier | Kind in the catalog | Seen on parameters like |
|---|---|---|
| 0 | `text` | Title, Text, keyword |
| 1 | `bool` | value, toggle flags |
| 2 | `int` | Count, Frequency, Spacing |
| 7 | `number` | Timeout (seconds), Amount, Opacity |
| 8, 9 | `date` | Date, startDate, dueDate |
| 10 | `location` | Location |
| 11 | `url` | URL, deeplink |
| 12 | `richtext` | note, content, body |

Other `valueType` shapes: `linkEnumeration` -> `enum:<Name>`, `entity` -> `entity:<Type>`, `array` -> `array<...>`, plus `file`, `intents`, `measurement`, `searchCriteria`. Anything unrecognised keeps its key name and is treated as **not authorable**.

## 6. Pitfalls and limits

- **iPad builds often have no metadata** even when the iPhone build does. This was cross-checked and is real. Request `--platform iphone` for phone shortcuts.
- **An app can have no `Metadata.appintents` and still be automatable.** Scriptable (`dk.simonbs.Scriptable`) ships old-style SiriKit intents instead: `Base.lproj/Intents.intentdefinition` (an XML property list) plus an `.appex` with `IntentsSupported`. A full download confirmed there is no `Metadata.appintents` in the package. Its definition lists 7 intents (`RunScript`, `RunScriptWithArguments`, `ParameterizedRunScript`, `RunScriptInline`, `CreateFileBookmark`, `RunScriptWidgetConfiguration`, `RefreshAllWidgets`). How such intents are written as a shortcut step (identifier and `AppIntentDescriptor`) is **not verified**: no golden sample has a third-party step without an `AppIntentDescriptor`. The catalog therefore does not include them. Do not invent a step for these; export one from a real shortcut first.
- **Several bundle ids per app** (iPhone, iPad, lite). Names in the catalog can repeat; always use the exact bundle id.
- **`extract.actionsdata` can have empty or missing titles.** Fall back to the parameter name, as the catalog does.
- **Localised keys.** Some apps use string keys such as `app_intents.xxx.title` instead of readable text. They are real values, not errors. Search by bundle id, intent id or parameter name when titles are opaque.
- **The default value of a text parameter can carry required rules.** Scripting's `RunTypescriptIntent` takes code as text, and the code must `import { Script, Intent } from "scripting"`; without it the run fails with `ReferenceError: Can't find variable: Intent`. That rule is only in the parameter's `LNValueTypeSpecificMetadataKeyDefaultValue` and its description, not in the catalog. When a text parameter holds code or a template, read its default value in the raw file before writing it.
- **Metadata is a declaration, not a guarantee.** An intent listed here may need a sign-in, a purchase, a feature flag or an app setting at run time. Unlisted behaviour (what it actually returns) is only known from the declared `outputType`.
- **Version drift.** A newer app version can add, rename or remove intents. Record the version and refresh when a shortcut stops working after an app update.
- **Coverage is only what was harvested.** The catalog is not "all apps". An app missing from it may well have intents. Say "not in the catalog", never "has no intents".
- **Not every app can be read.** In the harvest, 46 of about 940 apps ended in `error`:
  - 37: the range read failed. The tool only logged "fast fetch failed" with no cause, so the reason is unknown. Add logging before relying on a retry.
  - 7: `failed to validate package platform` on a package that is not a valid ZIP (these were macOS builds such as `...mac` bundle ids). They are not iPhone apps; skip them.
  - 2: no downloadable iOS version could be resolved for the app.
  Failures are recorded and were not retried. If an app matters, retry it with the whole-IPA method.
- **Do not paste a Team ID guess.** Shortcuts accepts `TeamIdentifier` `0000000000` (verified on a device), so the real Team ID is not needed and is not read from the app signature.
- **macOS keychain.** On the Mac that holds the `ipatool` session, a newly built binary prompts for keychain access the first time. Approve it **on that Mac's screen**; it cannot be answered over SSH. Run commands from a session that can read the keychain.

## 7. What extraction does not give you

Extraction tells you **what an app declares**. It does **not** tell you how Shortcuts stores each parameter kind in a saved file. That has to be checked on a device, one kind at a time, and is tracked in `THIRD_PARTY_INTENTS.md` section 3 and section 8. Never extend `appintent_catalog.py step` to a new parameter kind on the strength of the metadata alone.

To verify a new kind:

1. Build a minimal shortcut with one step using that kind, generated from the metadata.
2. Sign it and let the user import and run it on a phone.
3. Judge by an observable effect (the target app's state, or a Minis session containing the passed value), not by "it imported".
4. Only then allow the kind in `appintent_catalog.py` and `validate_shortcut.py`, and record the date in `THIRD_PARTY_INTENTS.md`.
