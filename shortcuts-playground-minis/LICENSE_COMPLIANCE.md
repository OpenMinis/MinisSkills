# License & Compliance Notes

## Conclusion

The current `shortcuts-playground-minis` may be localized, modified, used, and redistributed in compliance with the **MIT license**, but you must retain:

1. The upstream copyright notice
2. The MIT license text
3. Source attribution
4. A description of local modifications

As long as these are done, localization itself does not infringe the upstream repository's license rights.

## Upstream Source

- Upstream: `viticci/shortcuts-playground-plugin`
- URL: <https://github.com/viticci/shortcuts-playground-plugin>
- Author: Federico Viticci / MacStories
- License: MIT
- SPDX: `MIT`

## What the MIT License Means for Localization

MIT permits:

- Use
- Copying
- Modification
- Merging
- Distribution
- Sublicensing
- Commercial use

Provided that:

- **All copies or substantial portions retain the copyright notice and license text**

This means the local skill may:

- Copy upstream knowledge-base files
- Rewrite `SKILL.md`
- Add scripts and wrapper layers
- Change output directories, workflows, and local documentation
- Continue to evolve in the Minis context

But it may not:

- Remove the upstream copyright and MIT text and then republish
- Present substantial methods and materials inherited from upstream as "entirely original"
- Hide key sources when sharing, causing misleading attribution

## Compliance Files the Local Skill Should Retain

The following files are the minimum compliance set and should not be deleted:

- `LICENSE`
- `UPSTREAM_ATTRIBUTION.md`
- `LICENSE_COMPLIANCE.md` (this file)
- The explanation of upstream source and local-modification boundaries in `README.md`
- The note on methods borrowed from upstream in `SKILL.md`

## How to Express Local Modifications Compliantly

Recommended wording:

- "Localized adaptation based on `viticci/shortcuts-playground-plugin`"
- "Draws on the upstream knowledge base, methods, and validation flow, with the runtime environment adapted for Minis"
- "This directory is an adaptation and extension layer for Minis, not written entirely from scratch"

Not recommended:

- "This is my own original shortcut generation framework"
- "Unrelated to the upstream project; I only borrowed a few ideas"

## Minimum Requirements for Distribution and Sharing

If you later share this skill with others, migrate it to another device, or package it for other users, at least:

1. Keep `LICENSE`
2. Keep `UPSTREAM_ATTRIBUTION.md`
3. State the upstream repository URL explicitly in `README.md` or the documentation
4. State which parts are local modifications
5. Do not remove the original author's attribution
6. Do not present the local skill as the official upstream version, a version authorized by the original author, or a version endorsed by MacStories

## Parts That Are More Like "Upstream Inheritance"

The following clearly continue upstream methods or materials and should continue to be attributed:

- The main body of the Shortcuts reference knowledge base
- The Craig Loop validation approach
- The working mode of treating unsigned XML as the source of truth
- The delivery approach of separating draft / archive / signed artifact
- The overall knowledge system of action / parameter / golden example

## Parts That Are More Like "Local Additions"

The following are mainly local adaptations and extensions and may be stated explicitly as local contributions:

- Minis path structure and result-directory conventions
- The HubSign wrapper layer
- Local self-test
- General routing framework, mode framework, capability decision framework, environment profile framework
- Fixed clarification templates, recommended flows, copyable confirmation text
- Delivery and usage on iPhone / iPad

## Practical Recommendations

When continuing to improve the skill, do these first to stay compliant:

- Keep upstream-borrowing notes in all newly added framework files; not every file needs one, but the entry files and attribution files must state it explicitly
- If upstream files are later deleted or heavily rewritten, still retain `LICENSE` and `UPSTREAM_ATTRIBUTION.md`
- If a `NOTICE.md` is added, it can condense "upstream + local-addition boundaries" into a one-page summary for easy sharing
- If an independent public repository is formed later, the first screen of the README home page should state the "fork / adaptation / based on" relationship explicitly

## Current Assessment

The current localization direction **may continue in compliance**.

What needs further strengthening is not the license itself, but:

- Distinguishing more clearly between "upstream-inherited content" and "locally added content"
- Making README / SKILL / attribution files consistent with one another
- Avoiding accidentally removing source information in later optimizations
