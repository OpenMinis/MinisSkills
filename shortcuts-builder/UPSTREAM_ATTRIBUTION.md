# Upstream Attribution and Adaptation Notes

## Upstream Source

This skill (`shortcuts-builder`) is derived from:

- Repository: `viticci/shortcuts-playground-plugin`
- URL: <https://github.com/viticci/shortcuts-playground-plugin>
- Original author: Federico Viticci / MacStories
- Upstream license: MIT
- Synced with upstream release: 1.2.1 (2026-06-15)

This skill is an **adaptation for Minis on iPhone/iPad**, not an original from-scratch invention. Its name is intentionally different from the upstream project; that does not change its origin.

## License Obligation Summary

MIT allows local use, copying, modification, redistribution, and commercial use, provided that:

- the upstream copyright notice is preserved;
- the MIT license text is preserved;
- substantial copied/adapted portions continue to carry attribution.

For this skill, the practical minimum is to keep:

- `LICENSE`
- `UPSTREAM_ATTRIBUTION.md`
- `LICENSE_COMPLIANCE.md`
- source attribution in `README.md` / `SKILL.md`

## What Was Preserved

This skill intentionally preserves the upstream project's core method and design ideas:

- natural-language-to-Shortcut workflow
- unsigned Shortcuts XML / plist as the editable source of truth
- reference-driven generation using bundled action and parameter docs
- Craig Loop style validation / repair before signing
- separation of draft, archive, and final signed artifact
- preference for surgical remixing instead of destructive rewriting

These ideas come from the upstream project and should continue to be credited that way.

## Why It Was Adapted

The upstream repository targets Claude Code / Codex plugin environments and assumes macOS for the native `shortcuts` signing step.

This local version exists to make the workflow usable inside Minis on iPhone/iPad, where those assumptions do not hold.

## Adaptation Changes

The main adaptation work in this skill is:

- removed Claude Code / Codex plugin packaging assumptions
- removed slash-command / hook / marketplace based usage instructions
- changed result directories to `/var/minis/attachments/shortcut/`
- kept draft XML, archive XML, and final `.shortcut` outputs as separate deliverables
- replaced the macOS-only `shortcuts sign` step with `scripts/sign-shortcut`, which lets the user choose between signing on their own Mac over SSH (Apple's `shortcuts sign`) or the third-party HubSign service
- added Minis-oriented self-test and file path conventions
- added routing / capability / common-pattern framework documents for broader natural-language use
- rewrote the main entry documentation so Minis users can use the skill directly

### Changes to upstream files (2026-10-07: iOS default)

These files came from upstream and were **modified here**. They no longer match the upstream copies; the upstream repository has the originals.

- `scripts/validate_shortcut.py`, `scripts/lookup_action_grounding.py`: the default target is now iOS/iPadOS and OS 27 (upstream defaults to macOS); added `--target-os` as an alias of `--target-macos`; added the `IOS_UNCONFIRMED_ACTIONS` and `MACOS_ONLY_ACTIONS` lists; clearer macOS-only error text.
- `data/toolkit-v78-first-party-parameter-keys.json`, `data/toolkit-v78-first-party-enum-cases.json`: trimmed to the entries that exist on the iOS 27 Simulator. The macOS-only entries were removed.
- `data/toolkit-v63-tool-ids.json`, `data/toolkit-v78-tool-ids.json`: removed (macOS identifier lists).
- `APPINTENTS.md`: removed the macOS System Settings entries (`com.apple.systempreferences.*`, `com.apple.Desktop-Settings.*`), corrected counts and the invocation example.
- `ACTIONS.md`, `AUTOMATION_TRIGGERS.md`, `BEST_PRACTICES.md`, `CONTROL_FLOW.md`, `TOOLKIT_SNAPSHOT.md`, `VARIABLES.md`: wording changed from "macOS 27" to "OS 27" where the behaviour applies to both, and the default-platform text updated. `VARIABLES.md` also gained a table of output names observed in the bundled golden samples.
- `scripts/test_wiring_regressions.py`: added third-party intent cases.

### Added here (not from upstream)

- `data/thirdparty-appintents.json.gz`, `scripts/appintent_catalog.py`, `THIRD_PARTY_INTENTS.md`: a catalog of third-party App Intents and the rules for using it. The catalog was extracted by the maintainers of this skill from each app's own `Metadata.appintents/extract.actionsdata`, not taken from upstream.
- `EXTRACTING_APP_INTENTS.md`: how that catalog is produced.
- `scripts/test_clarification_user_ask.py` and the `--json` mode of `scripts/render_clarification.py`: clarification through the `user_ask` tool.
- The third-party App Intent checks in the validator.
- `SKILL.md`, `CHANGELOG.md`, `CLARIFICATION_TEMPLATES.md`, `THIRD_PARTY_ACTIONS.md`, `scripts/render_clarification.py`: these were already rewritten for Minis in the first version of this skill (see the adaptation list above) and were extended again in this update (Quick Path, the iOS default, third-party rules, `user_ask`).

### Provenance of the data files

The ToolKit and automation-trigger data under `data/` (`toolkit-v78-*`, `macos27-*`) was exported by the upstream maintainer from a local macOS 27 and an iOS 27 Simulator Shortcuts ToolKit database (a June 2026 snapshot of a preview build). It was not produced by the maintainers of this skill and has not been refreshed since. `healthkit-ios26.2-reference.json` is generated from Xcode SDK headers by `scripts/generate_healthkit_reference.py`.

## Scope Boundary

The bundled knowledge files may still mention general Shortcuts internals or upstream-compatible concepts when that information is part of the underlying method. However, the **authoritative workflow** for this skill is the Minis workflow described in `SKILL.md` and `README.md`.

## Credit Practice

When sharing, reusing, or continuing to evolve this skill, keep all three points explicit:

1. the method and core knowledge base are borrowed from the upstream repository;
2. this skill is a Minis-focused adaptation and packaging layer;
3. the adaptation should preserve attribution rather than present the work as wholly original.
