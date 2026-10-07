#!/usr/bin/env python3
"""Index golden-shortcuts: extract action identifiers, patterns, and wiring highlights.

Usage:
  python3 scripts/index_golden.py [--update]

Without --update: prints enriched index to stdout as JSONL.
With --update: overwrites golden-shortcuts/index.jsonl in place.
"""

import json
import os
import plistlib
import re
import sys
from pathlib import Path

SKILL_ROOT = Path(__file__).resolve().parents[1]
INDEX_PATH = SKILL_ROOT / "golden-shortcuts" / "index.jsonl"
XML_DIR = SKILL_ROOT / "golden-shortcuts" / "xml"

# Pattern detection rules: action identifier sets → pattern name
PATTERN_RULES = [
    ({"is.workflow.actions.ask"}, "ask_text"),
    ({"is.workflow.actions.getclipboard"}, "clipboard_in"),
    ({"is.workflow.actions.choosefrommenu"}, "menu_select"),
    ({"is.workflow.actions.choosefromlist"}, "list_select"),
    ({"is.workflow.actions.conditional"}, "if_guard"),
    ({"is.workflow.actions.repeat.each"}, "repeat_each"),
    ({"is.workflow.actions.repeat.count"}, "repeat_count"),
    ({"is.workflow.actions.dictionary", "is.workflow.actions.getvalueforkey"}, "dictionary_flow"),
    ({"is.workflow.actions.gettext"}, "text_template"),
    ({"is.workflow.actions.text.replace"}, "text_replace"),
    ({"is.workflow.actions.text.match"}, "regex_extract"),
    ({"is.workflow.actions.downloadurl"}, "json_request"),
    ({"is.workflow.actions.detect.dictionary"}, "json_parse"),
    ({"is.workflow.actions.urlencode"}, "url_encode"),
    ({"is.workflow.actions.showresult"}, "show_result"),
    ({"is.workflow.actions.notification"}, "show_notification"),
    ({"is.workflow.actions.share"}, "share_output"),
    ({"is.workflow.actions.openurl"}, "open_target"),
    ({"is.workflow.actions.filter.notes"}, "write_system_note"),
    ({"is.workflow.actions.appendnote"}, "write_system_note"),
    ({"is.workflow.actions.addnewreminder"}, "write_reminder"),
    ({"is.workflow.actions.documentpicker.save"}, "write_file"),
    ({"is.workflow.actions.setclipboard"}, "clipboard_out"),
    ({"is.workflow.actions.savetocameraroll"}, "save_photo"),
    ({"is.workflow.actions.base64encode"}, "base64"),
    ({"is.workflow.actions.format.date"}, "format_date"),
    ({"is.workflow.actions.setvariable"}, "set_variable"),
    ({"is.workflow.actions.appendvariable"}, "append_variable"),
]


def extract_actions_from_plist(plist_data):
    """Extract unique action identifiers from parsed plist."""
    actions = plist_data.get("WFWorkflowActions", [])
    identifiers = set()
    for action in actions:
        ident = action.get("WFWorkflowActionIdentifier", "")
        if ident:
            identifiers.add(ident)
    return sorted(identifiers)


def detect_patterns(action_set):
    """Detect which common patterns are present based on action identifiers."""
    patterns = []
    for required_actions, pattern_name in PATTERN_RULES:
        if required_actions.issubset(action_set):
            if pattern_name not in patterns:
                patterns.append(pattern_name)
    return patterns


def extract_wiring_highlights(plist_data):
    """Extract key wiring observations from the shortcut."""
    highlights = []
    actions = plist_data.get("WFWorkflowActions", [])
    action_set = {a.get("WFWorkflowActionIdentifier", "") for a in actions}

    # Count control flow
    menu_count = sum(1 for a in actions
                     if a.get("WFWorkflowActionIdentifier") == "is.workflow.actions.choosefrommenu"
                     and a.get("WFWorkflowActionParameters", {}).get("WFControlFlowMode", 0) == 0)
    if_count = sum(1 for a in actions
                   if a.get("WFWorkflowActionIdentifier") == "is.workflow.actions.conditional"
                   and a.get("WFWorkflowActionParameters", {}).get("WFControlFlowMode", 0) == 0)
    repeat_each = sum(1 for a in actions
                      if a.get("WFWorkflowActionIdentifier") == "is.workflow.actions.repeat.each"
                      and a.get("WFWorkflowActionParameters", {}).get("WFControlFlowMode", 0) == 0)
    repeat_count = sum(1 for a in actions
                       if a.get("WFWorkflowActionIdentifier") == "is.workflow.actions.repeat.count"
                       and a.get("WFWorkflowActionParameters", {}).get("WFControlFlowMode", 0) == 0)

    if menu_count:
        highlights.append(f"Menu x{menu_count}")
    if if_count:
        highlights.append(f"If x{if_count}")
    if repeat_each:
        highlights.append(f"Repeat Each x{repeat_each}")
    if repeat_count:
        highlights.append(f"Repeat Count x{repeat_count}")

    # Count WFTextTokenString usage
    token_string_count = 0
    for a in actions:
        params = a.get("WFWorkflowActionParameters", {})
        for v in params.values():
            if isinstance(v, dict) and v.get("WFSerializationType") == "WFTextTokenString":
                token_string_count += 1
    if token_string_count:
        highlights.append(f"TokenString refs x{token_string_count}")

    # Named variables
    named_vars = set()
    for a in actions:
        if a.get("WFWorkflowActionIdentifier") == "is.workflow.actions.setvariable":
            name = a.get("WFWorkflowActionParameters", {}).get("WFVariableName", "")
            if name:
                named_vars.add(name)
    if named_vars:
        highlights.append(f"Named vars: {', '.join(sorted(named_vars))}")

    # Total action count
    highlights.append(f"Total actions: {len(actions)}")

    return highlights


def load_xml(xml_path):
    """Load and parse a plist XML file."""
    with open(xml_path, "rb") as f:
        return plistlib.load(f)


def enrich_entry(entry, xml_dir):
    """Add actions, patterns, wiring_highlights to an index entry."""
    xml_rel = entry.get("xml", "")
    xml_path = SKILL_ROOT / xml_rel
    if not xml_path.exists():
        return entry

    try:
        plist_data = load_xml(xml_path)
    except Exception as e:
        entry["_parse_error"] = str(e)
        return entry

    actions = extract_actions_from_plist(plist_data)
    action_set = set(actions)
    patterns = detect_patterns(action_set)
    wiring = extract_wiring_highlights(plist_data)

    entry["actions"] = actions
    entry["patterns"] = patterns
    entry["wiring_highlights"] = wiring
    return entry


def main():
    update_mode = "--update" in sys.argv

    # Load existing index
    entries = []
    if INDEX_PATH.exists():
        with open(INDEX_PATH, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line:
                    entries.append(json.loads(line))

    # Enrich each entry
    enriched = []
    for entry in entries:
        enriched.append(enrich_entry(entry, XML_DIR))

    # Output
    lines = [json.dumps(e, ensure_ascii=False) for e in enriched]
    output = "\n".join(lines) + "\n"

    if update_mode:
        with open(INDEX_PATH, "w", encoding="utf-8") as f:
            f.write(output)
        print(f"Updated {INDEX_PATH} with {len(enriched)} entries.")
    else:
        print(output, end="")


if __name__ == "__main__":
    main()
