---
name: self-improving-agent
description: "Self-improvement logging and closed-loop feedback: Trigger when a command or operation fails, the user corrects you, outdated knowledge is identified, an external API fails, or a better reusable solution is found. Review historical learnings before important tasks. Avoid triggering during ordinary chat, for temporary mistakes that do not need to be logged, or when the user has explicitly said not to log."
metadata:
  language: en-US
  scope: minis
---

# Self-Improvement Skill (Minis Edition)

This skill is used in the Minis environment to **record errors, corrections, and reusable best practices**, creating a traceable learning loop.

## Minis Directory Conventions

- **Working directory**: `/var/minis/workspace/`
- **Default learning log directory for this skill**: `/var/minis/skills/self-improving-agent/data/`
- **Public learning log directory within this skill (after promotion)**: `/var/minis/skills/self-improving-agent/data/public/`
- **Project-level learning log directory (optional)**: `<project>/.learnings/`
- **Learning log files**:
  - `LEARNINGS.md` (corrections, knowledge gaps, best practices)
  - `ERRORS.md` (command failures, exception output)
  - `FEATURE_REQUESTS.md` (new capabilities requested by users)

> By default, log entries go first to the skill's own `data` directory. When you explicitly specify a project, write to the project-level log. When an issue has been abstracted into a cross-project rule, promote it to the skill's public area or the Minis memory system.

## Current Final Rules

- **Default logging location**: `/var/minis/skills/self-improving-agent/data/`
- **Public area within the skill**: `/var/minis/skills/self-improving-agent/data/public/`
- **Project-level logging**: Use `<project>/.learnings/` only when `--project <path>` is passed explicitly
- **Recommended public parameter**: `--public`
- **Compatibility alias**: `--workspace` is still available, but only for compatibility and is no longer recommended
- **Promotion behavior**: `promote <entryID>` copies the entry to the public area within the skill, automatically marks the source entry as `promoted`, and writes back `**Promoted to**` and `### Resolution Record`
- **Duplicate protection**: If the entry already exists in the skill's public area, running `promote` again will not append a duplicate

## Quick Reference

| Scenario | Action |
|-----------|--------|
| Command or operation fails | Log to the skill directory by default: `data/ERRORS.md` |
| The user corrects you | Log to the skill directory by default: `data/LEARNINGS.md`, category `correction` |
| The user needs a missing capability | Log to the skill directory by default: `data/FEATURE_REQUESTS.md` |
| Project context is explicitly specified | Log to `<project>/.learnings/` |
| External API or tool fails | Log to `ERRORS.md` in the current scope, including integration details |
| Knowledge is outdated | Log to `LEARNINGS.md` in the current scope, category `knowledge_gap` |
| A better solution is found | First log it to the current scope, then promote it after confirming it is generally applicable |
| Similar issues recur across multiple projects | Promote to the public area within the skill: `data/public/` |
| Similar to an existing entry | Link with `**See Also**` and consider raising the priority |
| Widely applicable experience | Promote to the public area within the skill or to Minis memory. See "Promoting to Minis Memory" below |

## Trigger Logging Rules (Minis Runtime Conventions)

> Note: By default, this skill **does not automatically listen in the background**. When trigger conditions are met, the assistant (or you) should actively call `scripts/minis_auto_log.sh` to write the log to disk.

### Recommended Triggers That "Must Be Logged"

If any of the following conditions are met, the event should be logged unless you explicitly say "do not log it":

1. **A command or operation fails and the cause is not obvious**: For example, permissions, paths, dependencies, network issues, or third-party API exceptions that require investigation to diagnose.
2. **User correction**: You point out where my understanding is wrong, where my logic does not match the actual behavior of this software, or where paths or conventions are incorrect.
3. **Knowledge update or outdated assumption correction**: A previous assumption is found not to apply to Minis, or documentation or implementation needs correction.
4. **Reusable better solution**: A stable practice, convention, template, or workflow emerges that can significantly reduce rework.
5. **Recurring pattern**: Similar issues appear repeatedly within the same task, or across tasks or projects.

### Situations That Generally Should Not Be Logged

- Ordinary chat, one-off small changes, or minor details with no reuse value.
- You explicitly ask "do not log this."

### Recommended Logging Location

- **By default**, write to the skill area `data/` first.
- After confirming that the entry has reuse value across tasks, use `promote` to move it to the public area within the skill: `data/public/`.

## Difference from Minis Memory and Promotion Criteria

### Difference (Suggested Interpretation)

- This skill's logs (`data/` and `data/public/`) are an **editable work review repository**: they record context, troubleshooting processes, and solution evolution, and they allow long text and details.
- Minis memory (`memory_write` writing to `/var/minis/memory/`) is for **cross-session long-term rules and preferences**: entries should be short, stable, and reusable. Poorly written entries can "pollute" future decisions for a long time.

### Where to Write (Log First, Then Refine into Memory)

- **Write to this skill's logs first**: When the content needs context, such as error output, troubleshooting paths, or solution comparisons; when it is not yet clear whether it is generally applicable; or when it is still being iterated on.
- **Then promote to memory**: When the conclusion is stable, applies across tasks or skills, and can be expressed in one sentence.

### When to Promote to Memory (Hard Criteria)

Consider `memory_write` only if at least one of the following is true:

1. It can be condensed into a rule of the form "**When X happens in the future, do Y**" and does not depend on specific project details.
2. It **recurs 3 or more times within 30 days**, or appears in at least **2 different tasks or domains**.
3. It clearly belongs to your long-term preferences or conventions, such as tool usage constraints, path conventions, or output format rules, and you explicitly say "remember this" or "do this from now on."

### Recommended Promotion Actions

- First use `promote` to promote the entry to the public area within the skill, `data/public/`, for higher visibility and easier review.
- Then distill 1 to 3 short rules from the public entry and write them to the day's memory with `memory_write`.

Usage examples:

```bash
# By default, write to the skill's own data directory
sh /var/minis/skills/self-improving-agent/scripts/minis_auto_log.sh init

# Log a skill-level learning
sh /var/minis/skills/self-improving-agent/scripts/minis_auto_log.sh learning "Fixed the download timeout" "Use chunking and retries"

# If you need to log explicitly at the project level, pass --project
sh /var/minis/skills/self-improving-agent/scripts/minis_auto_log.sh --project /var/minis/workspace/my-project error "curl request failed" "HTTP 429"

# If you need to write directly to the public area within the skill, pass --public explicitly
sh /var/minis/skills/self-improving-agent/scripts/minis_auto_log.sh --public feature "Support batch export" "Operations needs daily reports"

# Search the skill area + project area + public area within the skill
sh /var/minis/skills/self-improving-agent/scripts/minis_auto_log.sh search timeout

# Promote an entry to the public area within the skill
sh /var/minis/skills/self-improving-agent/scripts/minis_auto_log.sh promote LRN-20260317-ABC

# View the current scope
sh /var/minis/skills/self-improving-agent/scripts/minis_auto_log.sh status
```

## Logging Format

### Learning Record

Append to `.learnings/LEARNINGS.md`:

```markdown
## [LRN-YYYYMMDD-XXX] category

**Record time**: ISO-8601 timestamp
**Priority**: low | medium | high | critical
**Status**: pending
**Domain**: frontend | backend | infra | tests | docs | config

### Summary
One-line description of what was learned

### Details
Full context: what happened, what went wrong, and the correct approach

### Recommended Action
Specific actionable improvement or fix

### Metadata
- Source: conversation | error | user_feedback
- Related file: path/to/file.ext
- Tags: tag1, tag2
- Related entry: LRN-20250110-001 (if applicable)
- Pattern key: simplify.dead_code | harden.input_validation (optional, for recurring pattern tracking)
- Recurrence count: 1 (optional)
- First seen: 2025-01-15 (optional)
- Last seen: 2025-01-15 (optional)

---
```

### Error Record

Append to `.learnings/ERRORS.md`:

````markdown
## [ERR-YYYYMMDD-XXX] skill_or_command_name

**Record time**: ISO-8601 timestamp
**Priority**: high
**Status**: pending
**Domain**: frontend | backend | infra | tests | docs | config

### Summary
Brief description of the failure

### Error
```
Actual error message or output
```

### Context
- Command or operation attempted
- Input or parameters
- Environment details, if relevant

### Recommended Fix
If identifiable, provide possible solutions

### Metadata
- Reproducible: yes | no | unknown
- Related file: path/to/file.ext
- Related entry: ERR-20250110-001 (if recurring)

---
````

### Feature Request Record

Append to `.learnings/FEATURE_REQUESTS.md`:

```markdown
## [FEAT-YYYYMMDD-XXX] capability_name

**Record time**: ISO-8601 timestamp
**Priority**: medium
**Status**: pending
**Domain**: frontend | backend | infra | tests | docs | config

### Requested Capability
The capability the user wants to implement

### User Context
Why it is needed and what problem it solves

### Complexity Assessment
simple | medium | complex

### Recommended Implementation
Possible implementation approaches and extension points

### Metadata
- Frequency: first_time | recurring
- Related feature: existing_feature_name

---
```

## ID Generation Rules

Format: `TYPE-YYYYMMDD-XXX`

- TYPE: `LRN` (learning), `ERR` (error), `FEAT` (feature)
- YYYYMMDD: current date
- XXX: sequential number or random 3-character value, such as `001` or `A7B`

Examples: `LRN-20250115-001`, `ERR-20250115-A3F`, `FEAT-20250115-002`

## Resolving Entries

After an issue is fixed, update the entry:

1. Change `**Status**: pending` to `**Status**: resolved`
2. Add a resolution block after the metadata:

```markdown
### Resolution Record
- **Resolution time**: 2025-01-16T09:00:00Z
- **Commit/PR**: abc123 or #42
- **Notes**: Brief description of what was done
```

Other statuses:

- `in_progress` - Being worked on
- `wont_fix` - Decided not to fix. Write the reason in the resolution record
- `promoted` - Promoted to Minis memory

## Promoting to Minis Memory

When a learning item is broadly applicable rather than a one-time fix, it should be promoted to the Minis memory system.

### When to Promote

- The learning applies across multiple files or features
- Any contributor, human or AI, should know it
- It prevents repeated mistakes
- It records project conventions

### Promotion Targets (Minis)

- **Daily memory**: `/var/minis/memory/YYYY-MM-DD.md` (written through `memory_write`)
- **Global memory**: `/var/minis/memory/GLOBAL.md` (read-only; the user must maintain it in settings)
- **Project notes**: Recommended target: `/var/minis/workspace/PROJECT_NOTES.md`

### How to Promote

1. **Distill**: Condense the learning into concise rules or facts
2. **Write**: Use `memory_write` to write to daily memory, and sync to project notes if needed
3. **Write back**: Update the original entry:
   - `**Status**: pending` to `**Status**: promoted`
   - Add `**Promoted**: YYYY-MM-DD.md` or `PROJECT_NOTES.md`

## Recurring Pattern Detection

If the content being logged is similar to an existing entry:

1. **Search first**: `grep -r "keyword" /var/minis/workspace/.learnings/`
2. **Create an association**: Add `**See Also**: ERR-20250110-001` to the metadata
3. **Raise the priority**: If the issue recurs
4. **Consider a systematic fix**: Recurring issues usually indicate:
   - Missing documentation (write to `PROJECT_NOTES.md` or daily memory)
   - Missing automation (add scripts or toolchain support)
   - Architectural issues (create a technical debt task)

## Simplify & Harden Feed

Used to ingest recurring patterns from the `simplify-and-harden` skill and convert them into persistent prompt rules.

### Ingestion Workflow

1. Read `simplify_and_harden.learning_loop.candidates` from the task summary.
2. For each candidate, use `pattern_key` as the stable deduplication key.
3. Search `.learnings/LEARNINGS.md` to see whether it already exists:
   - `grep -n "Pattern-Key: <pattern_key>" /var/minis/workspace/.learnings/LEARNINGS.md`
4. If it already exists:
   - Increment `Recurrence-Count`
   - Update `Last-Seen`
   - Add a `See Also` association
5. If it does not exist:
   - Create a new `LRN-...` entry
   - Set `Source: simplify-and-harden`
   - Set `Pattern-Key`, `Recurrence-Count: 1`, and `First-Seen`/`Last-Seen`

### Promotion Rules (System Prompt Feedback)

When the following conditions are met, promote the recurring pattern to Minis memory:

- `Recurrence-Count >= 3`
- Appears in at least 2 different tasks
- Occurs within 30 days

The promoted rule should be a **short and clear preventive rule** that describes what to do before or during work, not a lengthy incident review.

## Periodic Review

Review `.learnings/` at natural milestones:

### When to Review

- Before starting a new important task
- After completing a feature
- When entering a domain that has previous learnings
- Once a week during active development

### Quick Status Check

```bash
# Count pending items
grep -h "Status\*\*: pending" /var/minis/workspace/.learnings/*.md | wc -l

# List pending high-priority items
grep -B5 "Priority\*\*: high" /var/minis/workspace/.learnings/*.md | grep "^## \["

# Find learnings for a specific area
grep -l "Domain\*\*: backend" /var/minis/workspace/.learnings/*.md
```
