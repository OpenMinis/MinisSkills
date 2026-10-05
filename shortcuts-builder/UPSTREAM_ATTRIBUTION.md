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

## Scope Boundary

The bundled knowledge files may still mention general Shortcuts internals or upstream-compatible concepts when that information is part of the underlying method. However, the **authoritative workflow** for this skill is the Minis workflow described in `SKILL.md` and `README.md`.

## Credit Practice

When sharing, reusing, or continuing to evolve this skill, keep all three points explicit:

1. the method and core knowledge base are borrowed from the upstream repository;
2. this skill is a Minis-focused adaptation and packaging layer;
3. the adaptation should preserve attribution rather than present the work as wholly original.
