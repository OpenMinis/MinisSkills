# MinisSkills

A community collection of skills for [Minis](https://github.com/OpenMinis) — reusable instruction sets that extend Claude's capabilities with specialized workflows, domain knowledge, and bundled resources.

---

## What is a Skill?

A skill is a directory containing a `SKILL.md` file (plus optional bundled resources) that Claude loads when it detects a relevant user request. Skills use a three-level loading system:

1. **Metadata** (`name` + `description` in frontmatter) — always in context, used for triggering (~100 words)
2. **SKILL.md body** — loaded into context whenever the skill triggers (keep under 500 lines)
3. **Bundled resources** — scripts, references, and assets loaded only as needed (unlimited size)

---

## Directory Structure

### Repository Layout

```
MinisSkills/
├── README.md
└── <skill-name>/           # One directory per skill (see naming rules below)
    ├── SKILL.md            # Required
    ├── evals/              # Optional: test cases
    │   └── evals.json
    ├── scripts/            # Optional: executable helper scripts
    ├── references/         # Optional: reference docs loaded into context as needed
    └── assets/             # Optional: templates, icons, fonts used in output
```

### Skill Directory Naming

- Use **lowercase kebab-case**: `my-skill-name`
- Be descriptive but concise (2–4 words is ideal)
- Use the domain or action as a prefix when it helps group related skills
- ✅ Good: `health-sleep-analysis`, `nano-banana`, `remote-dev-minis-app`
- ❌ Avoid: `MySkill`, `skill_for_doing_things`, `s1`

---

## SKILL.md Format

Every skill **must** have a `SKILL.md` with a YAML frontmatter block followed by Markdown instructions.

### Frontmatter (Required)

```yaml
---
name: skill-name
description: >
  One or two sentences describing what the skill does and — crucially — when
  Claude should trigger it. Include specific user phrases, contexts, and
  keywords that signal this skill is needed. Be slightly "pushy": list
  edge cases and near-miss scenarios where this skill should still win.
---
```

> **Why the description matters:** The `description` field is the primary trigger mechanism. Claude reads the skill name + description to decide whether to load the skill. A vague description leads to undertriggering. A good description covers both *what the skill does* and *when to use it*, with concrete phrases a real user might say.

### Optional Frontmatter Fields

```yaml
---
name: skill-name
description: ...
compatibility: Python 3.10+, requires ffmpeg  # tools/deps needed, if any
---
```

### Full Anatomy

```
skill-name/
├── SKILL.md
│   ├── YAML frontmatter    ← name, description (required); compatibility (optional)
│   └── Markdown body       ← instructions, examples, output formats, workflows
└── Bundled Resources (optional)
    ├── scripts/            ← deterministic/repetitive tasks; Claude runs without loading
    ├── references/         ← docs loaded into context on demand; include a TOC if >300 lines
    └── assets/             ← output templates, icons, fonts
```

---

## Writing a Good Skill

### Instructions Style

- Write in the **imperative form**: "Fetch the file", "Parse the JSON", "Return a table"
- **Explain the *why*** behind requirements — don't just say `MUST do X`, explain why X matters. Claude understands reasoning and applies it more flexibly than rigid rules
- Use `ALWAYS` / `NEVER` sparingly; prefer reasoning over mandates
- Aim for **under 500 lines** in SKILL.md; if longer, split content into `references/` files with clear pointers

### Defining Output Formats

Use an explicit template block when the output structure is fixed:

```markdown
## Output format
Always use this exact structure:

# [Title]
## Summary
## Steps
## Result
```

### Including Examples

```markdown
## Examples

**Example 1**
Input: "convert sales_q4.csv to a bar chart by region"
Output: a PNG file saved to the workspace, axes labeled, legend included
```

### Multi-Domain Skills

When a skill covers multiple frameworks or platforms, keep `SKILL.md` lean and delegate to reference files:

```
cloud-deploy/
├── SKILL.md          ← workflow overview + "read the relevant reference file"
└── references/
    ├── aws.md
    ├── gcp.md
    └── azure.md
```

### Progressive Disclosure Pattern

For large skills, add a hierarchy:

1. `SKILL.md` — overview, decision logic, pointers to sub-references
2. `references/<topic>.md` — deep detail, loaded only when relevant
3. `scripts/<task>.py` — executed directly without loading into context

---

## Evals (Optional but Recommended)

Skills with objectively verifiable outputs benefit from test cases saved in `evals/evals.json`:

```json
{
  "skill_name": "my-skill",
  "evals": [
    {
      "id": 1,
      "prompt": "A realistic user prompt — include context, file names, casual phrasing",
      "expected_output": "Description of what a correct result looks like",
      "files": [],
      "assertions": [
        {
          "text": "Output contains a valid JSON object with keys 'name' and 'score'",
          "type": "contains"
        }
      ]
    }
  ]
}
```

**Tips for good eval prompts:**
- Write them the way a real user would — casual, with typos, abbreviations, specific file names
- Cover edge cases, not just the happy path
- 2–5 prompts per skill is a good starting point

---

## Submission Checklist

Before opening a pull request, verify:

- [ ] Directory name is **lowercase kebab-case**
- [ ] `SKILL.md` exists with valid YAML frontmatter (`name` + `description`)
- [ ] `description` clearly states **what** the skill does and **when** to trigger it
- [ ] SKILL.md body is **under 500 lines** (or uses `references/` for overflow)
- [ ] Instructions use **imperative form** and explain the *why* behind key steps
- [ ] No hardcoded secrets, API keys, or credentials anywhere in the skill
- [ ] Bundled scripts are in `scripts/`, reference docs in `references/`, static assets in `assets/`
- [ ] If evals exist, `evals/evals.json` follows the schema above

---

## Example Skill

```
health-sleep-analysis/
├── SKILL.md
├── evals/
│   └── evals.json
└── references/
    └── healthkit-types.md
```

**`health-sleep-analysis/SKILL.md`:**

```markdown
---
name: health-sleep-analysis
description: >
  Analyze sleep health data from Apple HealthKit, including sleep stages
  (Deep/REM/Core/Awake), blood oxygen (SpO2), sleep duration trends, and
  bedtime patterns. Use this skill whenever the user asks about sleep quality,
  sleep analysis, sleep stages, blood oxygen during sleep, or any Apple Watch
  sleep data — even if they don't use the word "analysis".
---

# Sleep Health Analysis

Fetch sleep and SpO2 data from HealthKit, then produce a structured report
covering...
```

---

## License

[Apache License 2.0](LICENSE)
