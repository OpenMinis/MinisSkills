---
name: generative-ui-minis
description: In the current Minis environment, automatically convert text descriptions into a single-file HTML generator similar to Claude Artifact, with unified support for outputs such as cards, tables, records, timelines, code blocks, and charts. Use this skill first when users mention these components or visualization pages.
metadata:
  openclaw:
    emoji: "🧩"
    requires:
      bins: ["python3"]
---

# Generative UI Minis Skill

This is a **Claude Artifact-style generator skill** designed for the current Minis / iSH environment.

The goal is not to modify the chat host itself, but to:

1. Organize user instructions into a structured spec
2. Render them with Python into a single-file HTML artifact
3. Save it to `/var/minis/workspace/`
4. Let users preview, share, and continue iterating directly

## Automatic Trigger Scenarios

Use this skill first when users express any of the following intentions:

- "Create a Claude Artifact / Claude-style page"
- "Turn the answer into cards"
- "Generate a table / record sheet / checklist"
- "Organize the content into a timeline"
- "Generate a code block display page"
- "Create a chart / visualization page"
- "Render this content as an HTML prototype"
- "Create an interactive explanation page / artifact"

In particular, when the user also mentions:
**cards, tables, records, code blocks, timelines, charts, visualization pages, artifacts**
assume by default that this skill should be invoked to generate an additional page.

## Currently Supported Unified Components

- `cards`: information cards / KPI cards
- `table`: table
- `records`: record list
- `timeline`: timeline / step flow
- `code`: code block
- `chart`: built-in bar chart
- `details`: collapsible details

## Main Scripts

### 1) Complete Artifact Generator

```bash
python3 /var/minis/skills/generative-ui-minis/scripts/generative_ui_artifact.py \
  "Weekly Project Report" \
  --text "Need overview cards\nNeed risk table\nNeed timeline\nNeed code block\nNeed chart"
```

By default, this outputs to:

```bash
/var/minis/workspace/<title>_artifact.html
```

### 2) Render from a JSON spec

```bash
python3 /var/minis/skills/generative-ui-minis/scripts/generative_ui_artifact.py \
  "Demo" \
  --spec /path/to/spec.json \
  --out /var/minis/workspace/demo_artifact.html \
  --json-out /var/minis/workspace/demo_spec.json
```

## spec Format

```json
{
  "title": "Generative UI Example",
  "summary": "Unified output of multiple components.",
  "chips": ["Artifact", "Cards", "Table"],
  "blocks": [
    {
      "type": "cards",
      "title": "Overview Cards",
      "items": [
        {"title": "Status", "value": "In Progress", "desc": "In the current iteration"}
      ]
    },
    {
      "type": "table",
      "title": "Record Sheet",
      "columns": ["Date", "Item", "Status"],
      "rows": [["03-17", "Generator Development", "Done"]]
    },
    {
      "type": "timeline",
      "title": "Timeline",
      "items": [
        {"title": "Phase One", "desc": "Requirements Organization"},
        {"title": "Phase Two", "desc": "Page Rendering"}
      ]
    },
    {
      "type": "code",
      "title": "Sample Code",
      "language": "python",
      "content": "print('hello artifact')"
    },
    {
      "type": "chart",
      "title": "Progress Chart",
      "series": [
        {"label": "Design", "value": 70},
        {"label": "Development", "value": 85}
      ]
    }
  ]
}
```

## Recommended Workflow

1. Determine whether the user needs an artifact page
2. If the input is only a natural-language description, first use the script to automatically infer the basic blocks
3. If the content is complex, organize it into a JSON spec before rendering
4. After generating the HTML, send the workspace link directly to the user
5. Continue modifying the spec or template based on feedback

## Capability Boundaries

**Can do:**
- Generate a unified single-file artifact HTML
- Support cards, tables, records, timelines, code blocks, and charts
- Serve as a visual supplement to an answer

**Does not directly do yet:**
- Native message-level component injection into the chat host
- Complex frontend applications driven by real-time databases
- Long-running interactive server-side services

## Trigger Recommendations

If the user says:
- "Make me a card version"
- "Also generate a table/timeline/code block"
- "Organize it into an artifact page"

Do not respond with text only. Run this skill directly to generate an additional HTML artifact.
