# Feature Requests
# Feature Requests
## [FEAT-20260317-BQ5] capability

**Recorded on**: 2026-03-17T14:08:09Z
**Priority**: medium
**Status**: pending
**Scope**: docs

### Required Capability
The cross-project initialization semantics of `self-improving-agent` are unclear.

### User Context
The current script writes logs to a fixed location, `/var/minis/workspace/.learnings`. In practice, this is shared across the entire workspace, so initialization does not need to be repeated for each project. This could be improved by supporting `--base <path>` for multi-project isolation, or by adding a `status/doctor` command to explicitly indicate the current scope and whether it has been initialized.

### Complexity Assessment
medium

### Recommended Implementation
(To be added)

### Metadata
- Frequency: first_time
- Related Features: (optional)

---
