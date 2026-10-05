# ENV_PROFILE

## Purpose

Records default environment information that significantly affects the shortcut generation route. Read these defaults first when generating; ask minimal clarification only when a value is missing and would change the route.

## Design Principles

- Keep only abstract fields reusable across tasks
- Do not write any single app, single note title, or single file name as a universal default structure
- The sample config shows only field types and hierarchy, not concrete business instances
- Fill in app-specific parameters only when a task hits that app

## Suggested Structure

```json
{
  "system_targets": {
    "default_note_folder": "",
    "default_note_identifier": "",
    "default_reminder_list": ""
  },
  "external_targets": {
    "default_app": "",
    "default_target_identifier": "",
    "supports_uri_write": false,
    "supports_action_extension": false
  },
  "minis_integration": {
    "prefer_hybrid_when_available": true,
    "default_minis_output_mode": "clipboard",
    "allow_minis_browser": true,
    "allow_minis_model_calls": true
  },
  "permissions": {
    "allow_third_party_signing": true,
    "allow_network_requests": true,
    "allow_open_url_schemes": true
  },
  "delivery_mode": "full-delivery"
}
```

## Field Notes

- `system_targets.default_note_folder`: default system Notes folder
- `system_targets.default_note_identifier`: default system note identifier, e.g. a fixed title or other stable identifying value
- `system_targets.default_reminder_list`: default Reminders list name
- `external_targets.default_app`: default third-party target app identifier
- `external_targets.default_target_identifier`: third-party target object identifier, e.g. target page, object ID, file path, or other locatable value
- `external_targets.supports_uri_write`: whether writing via URI/URL scheme is supported
- `external_targets.supports_action_extension`: whether writing via a Shortcuts action or plugin is supported
- `minis_integration.prefer_hybrid_when_available`: whether to prefer the Hybrid route when Minis commands can cover the need
- `minis_integration.default_minis_output_mode`: default way Minis returns results: `clipboard` (write to clipboard), `file` (write to file), `notification` (send notification)
- `minis_integration.allow_minis_browser`: whether shortcuts may trigger Minis browser operations
- `minis_integration.allow_minis_model_calls`: whether shortcuts may trigger Minis AI model calls
- `permissions.allow_third_party_signing`: whether HubSign is acceptable
- `permissions.allow_network_requests`: whether shortcuts that make network requests are allowed
- `permissions.allow_open_url_schemes`: whether launching third-party apps via URL scheme is allowed
- `delivery_mode`: whether to generate a draft, a validated version, or a finished product by default

## Usage Rules

- If a default exists, use it directly
- If missing but the route is unaffected, state a default assumption and continue
- If missing and the route would change, enter clarification
- Map abstract fields to an app's required parameters only when a task hits that specific app

