# Learnings

## [LRN-20260317-EUC] category

**Time Logged**: 2026-03-17T14:05:12Z
**Priority**: medium
**Status**: pending
**Domain**: docs

### Summary

The script lacks execute permission when initializing `self-improving-agent`

### Details

In Minis, this script should be called explicitly with `sh` to avoid a "Permission denied" error. Prefer `sh /var/minis/skills/self-improving-agent/scripts/minis_auto_log.sh init`.

### Recommended Actions

(To be added)

### Metadata

- Source: conversation
- Related files: (optional)
- Tags: (optional)

---

## [LRN-20260317-EXY] category

**Recorded Time**: 2026-03-17T14:16:26Z
**Priority**: medium
**Status**: pending
**Domain**: docs

### Summary

The default location for learning logs has been changed to `workspace/learnings`

### Details

The hidden directory `.learnings` has poor visibility in cross-project search and file selection scenarios. The default has been changed to `/var/minis/workspace/learnings`. At the same time, `--project` project-level isolation and `--base` custom paths are retained, creating a dual track of shared accumulated learnings and project isolation.

### Recommended Actions

(To be added)

### Metadata

- Source: conversation
- Scope: workspace
- Base path: /var/minis/workspace/learnings
- Related Files: (optional)
- Tags: (optional)

---

## [LRN-20260317-KNL] category

**Recorded Time**: 2026-03-17T14:26:04Z
**Priority**: medium
**Status**: pending
**Domain**: docs

### Summary

Duplicate issue for `demo-b`

### Details

Used for subsequent testing of promotion to the public area

### Recommended Action

(To be added)

### Metadata

- Source: conversation
- Scope: project
- Base path: /var/minis/workspace/demo-b/.learnings
- Project Path: /var/minis/workspace/demo-b
- Related Files: (optional)
- Tags: (optional)

---

## [LRN-20260317-JJ4] category

**Recorded Time**: 2026-03-17T15:10:28Z
**Priority**: medium
**Status**: pending
**Domain**: docs

### Summary

`promote` write-back test

### Details

Test whether `promoted` is automatically written back after promotion

### Recommended Action

(To be added)

### Metadata

- Source: conversation
- Scope: skill
- Base path: /var/minis/skills/self-improving-agent/data
- Related Files: (optional)
- Tags: (optional)

---

## [LRN-20260317-QQG] category

**Recorded Time**: 2026-03-17T15:12:21Z
**Priority**: medium
**Status**: pending
**Domain**: docs

### Summary

Second layout test for `promote`

### Details

Check whether the write-back position is before the separator line

### Recommended Action

(To be added)

### Metadata

- Source: conversation
- Scope: skill
- Base path: /var/minis/skills/self-improving-agent/data
- Related Files: (optional)
- Tags: (optional)

---

## [LRN-20260317-2LU] category

**Recorded Time**: 2026-03-17T15:16:42Z
**Priority**: medium
**Status**: pending
**Domain**: docs

### Summary

Repeated `promote` protection test

### Details

Test whether the second `promote` action is blocked

### Recommended Action

(To be added)

### Metadata

- Source: conversation
- Scope: skill
- Base path: /var/minis/skills/self-improving-agent/data
- Related Files: (optional)
- Tags: (optional)

---
