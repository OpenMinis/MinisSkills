# Shortcuts Builder

An Apple Shortcuts generator skill for Minis. It turns natural-language automation requests into deliverable shortcut artifacts: a route decision, an action-chain plan, an unsigned XML draft, locally validated XML, and, on demand, a signed `.shortcut` file.

This is an adaptation of the upstream [`viticci/shortcuts-playground-plugin`](https://github.com/viticci/shortcuts-playground-plugin) by Federico Viticci / MacStories (MIT) for Minis on iPhone/iPad. It is not an unrelated original project and is not an official upstream release. See [UPSTREAM_ATTRIBUTION.md](UPSTREAM_ATTRIBUTION.md) for the source, license, and what was changed, and [LICENSE_COMPLIANCE.md](LICENSE_COMPLIANCE.md) for redistribution requirements. Currently synced with upstream 1.2.1 (2026-06-15); see [CHANGELOG.md](CHANGELOG.md).

## Read Before Use

iOS does not accept unsigned shortcuts, so they must be signed before delivery. **On first use you must choose a signing method**:

| Method | Privacy | Notes |
|---|---|---|
| **Your own Mac (recommended)** | Drafts are sent only to your own Mac | Requires a Mac running macOS 12+ with SSH access; uses Apple's official `shortcuts sign` |
| **HubSign (third-party, free)** | ⚠️ Drafts are uploaded to a third-party service and their content is visible to the service operator | Zero configuration; the service is maintained by an individual and availability is not guaranteed |

**The first import requires a one-time manual authorization**: the signing certificate is issued by Apple for each signature and is not tied to your own Apple ID or developer account, so on import iOS shows an "untrusted shortcut" style system prompt, and you must tap "Allow" / "Import Anyway" once. This is a normal step and does not mean the file is broken.

## Scope

This skill handles three kinds of tasks:

- **shortcut-native**: can be done mainly with native system actions
- **shortcut-hybrid**: the shortcut handles the entry point, and the complex parts are delegated to URIs, third-party actions, Minis, or external services
- **not-shortcut-first**: not suited to being built as a shortcut first; go through direct Minis execution or another implementation path instead

The goal of this skill is not to pile up examples around single cases, but to provide a reusable build framework.

## Document Reading Order

1. [SKILL.md](SKILL.md) — authoritative workflow and execution rules
2. [BUILD_CHECKLIST.md](BUILD_CHECKLIST.md) — pre-build checks
3. [CAPABILITY_DECISION.md](CAPABILITY_DECISION.md) — route decision
4. [ROUTING_FRAMEWORK.md](ROUTING_FRAMEWORK.md) — task spec and routing rules
5. [CLARIFICATION_TEMPLATES.md](CLARIFICATION_TEMPLATES.md) — fixed question templates for unclear requests
6. [ENV_PROFILE.md](ENV_PROFILE.md) — environment profile field notes
7. [TASK_FAMILY_INDEX.md](TASK_FAMILY_INDEX.md) — high-level task family index
8. [COMMON_PATTERNS.md](COMMON_PATTERNS.md) — common pattern taxonomy
9. [ACTION_RECIPES.md](ACTION_RECIPES.md) — skeletons of frequent action chains
10. [TEMPLATE_MAPPING.md](TEMPLATE_MAPPING.md) — rules mapping requests to templates
11. [XML_SNIPPET_PATTERNS.md](XML_SNIPPET_PATTERNS.md) — index of minimal XML snippets for frequent actions
12. [STABILITY_NOTES.md](STABILITY_NOTES.md) — stability and reproducibility notes
13. [BEST_PRACTICES.md](BEST_PRACTICES.md) and the technical reference docs — details on actions, parameters, variables, filters, and formats

## Core Commands

```bash
/var/minis/skills/shortcuts-builder/scripts/check-local-assets
/var/minis/skills/shortcuts-builder/scripts/profile-summary
/var/minis/skills/shortcuts-builder/scripts/load-env-profile
/var/minis/skills/shortcuts-builder/scripts/preflight-request 'I want to build a shortcut'
/var/minis/skills/shortcuts-builder/scripts/render-clarification 'I want to build a shortcut'
/var/minis/skills/shortcuts-builder/scripts/resolve-icon --prompt "Build a weather shortcut"
/var/minis/skills/shortcuts-builder/scripts/placeholder-range 'text with ￼ placeholder'
/var/minis/skills/shortcuts-builder/scripts/validate-shortcut /path/to/Shortcut.xml
/var/minis/skills/shortcuts-builder/scripts/sign-shortcut /path/to/Shortcut.xml --name "Shortcut Name"
python3 /var/minis/skills/shortcuts-builder/scripts/selftest_minis.py
```

## Signing

iOS does not accept unsigned `.shortcut` files: importing via the share sheet prompts "signing required", and `shortcuts://import-workflow` does not accept local `http://` or `file://` addresses. The signing certificate for shortcuts is issued by Apple on the spot, a new short-lived certificate each time; **it is not a developer certificate, and you cannot sign yourself in iSH with a p12**.

```bash
# Show the current backend
scripts/sign-shortcut --show-config

# Option 1: your own Mac (the password is passed only as an env var name; the value is never written to the config file)
scripts/sign-shortcut --setup-mac user@host --password-env MAC_SSH_PASSWORD
scripts/sign-shortcut --setup-mac user@host --key ~/.ssh/id_ed25519

# Option 2: HubSign (you must explicitly confirm that drafts will be uploaded)
scripts/sign-shortcut --setup-hubsign --i-understand-upload

# Sign (--mode only applies to the Mac backend; --backend switches temporarily)
scripts/sign-shortcut /path/to/Shortcut.xml --name "Shortcut Name" [--mode anyone|people-who-know-me]
```

- The Mac backend uses a temporary directory on the remote side and deletes it after signing; the config is saved at `~/.config/shortcuts-playground/sign.json` (permissions 600, no password).
- `anyone`: anyone can import. `people-who-know-me`: requires the Mac to be signed in to an Apple ID, and the recipient must be in the contacts.
- If no backend is configured, signing fails with exit code 10; it never silently picks HubSign.
- Manual signing (without the script): `cp x.xml x.shortcut && shortcuts sign -m anyone -i x.shortcut -o x-signed.shortcut`, the suffix must be `.shortcut`.

## Output Directories

- Final products: `/var/minis/attachments/shortcut/`
- Drafts: `/var/minis/attachments/shortcut/drafts/`
- Archive: `/var/minis/attachments/shortcut/archive/YYYY-MM-DD/`



## File Groups

### Framework Layer

- `SKILL.md`
- `BUILD_CHECKLIST.md`
- `CAPABILITY_DECISION.md`
- `ROUTING_FRAMEWORK.md`
- `CLARIFICATION_TEMPLATES.md`
- `COMMON_PATTERNS.md`
- `ACTION_RECIPES.md`
- `TEMPLATE_MAPPING.md`
- `TASK_FAMILY_INDEX.md`
- `XML_SNIPPET_PATTERNS.md`
- `ENV_PROFILE.md`
- `STABILITY_NOTES.md`
- `METHODOLOGY.md`
- `MINIS_CAPABILITIES.md`
- `KNOWN_PITFALLS.md`
- `ACTION_PARAM_INDEX.md`

### Technical Reference Layer

- `BEST_PRACTICES.md`
- `ACTIONS.md`
- `APPINTENTS.md`
- `PARAMETER_TYPES.md`
- `PLIST_FORMAT.md`
- `VARIABLES.md`
- `CONTROL_FLOW.md`
- `FILTERS.md`
- `EXAMPLES.md`
- `URL_SCHEMES.md`
- `ICONS_AND_COLORS.md`
- `HEALTHKIT.md`
- `THIRD_PARTY_ACTIONS.md`
- `TOOLKIT_SNAPSHOT.md`
- `AUTOMATION_TRIGGERS.md`
- `DATE_TIME.md`
- `JAVASCRIPT_WEBPAGE.md`
- `golden-shortcuts/index.jsonl`

### Script Layer

- `scripts/select_shortcut_icon_color.py`
- `scripts/validate_shortcut.py`
- `scripts/sign_shortcut.py` (signing entry point; choose one of two backends)
- `scripts/sign_shortcut_via_hubsign.py` (HubSign channel)
- `scripts/placeholder_range.py`
- `scripts/load_env_profile.py`
- `scripts/check_local_assets.py`
- `scripts/selftest_minis.py`
- `scripts/lookup_action_grounding.py`
- `scripts/fix_placeholder_positions.py`
- `scripts/preflight_request.py`
- `scripts/render_clarification.py`
- `scripts/match_golden.py`
- `scripts/index_golden.py`
- `scripts/profile_summary.py`
- `scripts/test_wiring_regressions.py`
- `scripts/test_random_mixed_shortcuts.py`
- `scripts/generate_healthkit_reference.py`

### Compliance Layer

- `LICENSE`
- `UPSTREAM_ATTRIBUTION.md`
- `LICENSE_COMPLIANCE.md`
- `NOTICE`
- `REDISTRIBUTION_CHECKLIST.md`

## Requirements

- Python 3.10+
- Minis runtime environment
- If signing: the chosen backend must be available (the Mac backend needs SSH access and the `shortcuts` command installed; HubSign needs network access)

## Compliance Requirements

MIT allows local use, modification, migration, and redistribution, but you must retain:

- The upstream copyright notice
- The MIT license text
- Source attribution
- A statement of the local-modification boundaries

Do not present this directory as the official upstream version, and do not imply that the original author or MacStories endorses the local version.
