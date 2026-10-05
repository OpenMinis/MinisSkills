---
name: disk-scan
description: >
  Report what is actually taking up space in a directory tree — the biggest
  subdirectories and the biggest individual files, largest first. Use this skill
  whenever the user asks where their storage went or what is eating space: "why is my
  phone full", "what's using all my space", "find the big files", "what's in this
  folder taking up 8 GB", "which folder should I clean", "外接盘爆了", "手机满了",
  "哪个文件夹最大", "找大文件", "磁盘占用", "清理空间", 용량 확인, 가장 큰 파일,
  ストレージ不足, 大きいファイル. Also use it before any cleanup, archive or move, so
  the target is chosen from measurements rather than from a guess — and when a scan
  comes back empty or short, to confirm the directory really is empty instead of
  assuming the tool failed.
compatibility: >
  Python 3.8+ on PATH. Standard library only, no network. Read-only: it never
  creates, moves, renames or deletes anything, on any flag combination.
---

# Disk Scan

## Overview

`scripts/disk_scan.py` walks a directory tree once and reports it back in two ranked
lists: the largest subdirectories, and the largest files. Sizes are subtree totals,
so a directory figure is everything underneath it, not just the files sitting
directly inside.

Read-only by construction. There is no cleanup mode, no `--apply`, and no code path
that modifies the filesystem. Cleaning up is a decision that deserves its own explicit
confirmation; a measurement tool that can also delete is one flag away from a
disaster, so this one cannot.

## Why one pass matters

The obvious implementation sizes each directory separately, which re-walks every
subtree: the root's walk plus each child's walk plus each grandchild's, and so on.
That is quadratic in depth, and it is exactly the case that hurts — a media library,
a project with `node_modules`, a backup folder. The same tree that answers in three
seconds with one pass can take fifteen with the naive version, and the gap grows with
every level.

Nothing here is clever — it accumulates each file's size into its ancestors during the
one walk it already has to do. On a real tree of 3,483 directories and 19,354 files
that is 3.1 s against 14.9 s, and the difference widens with depth.

## Command

```bash
python3 scripts/disk_scan.py --dir /path/to/scan --top 15
```

| flag | meaning |
|---|---|
| `--dir PATH` | root to scan (default: current directory) |
| `--top N` | rows per section (default `15`) |
| `--min-mb M` | hide files smaller than M MB — use when a long tail buries the real hogs |
| `--exclude NAME[,NAME...]` | skip directories by name, e.g. `.git,node_modules` |
| `--json` | machine-readable output, including `total_bytes` and `file_count` |

Typical output:

```
root: /workspace/projects
total: 1.9 GB in 24,118 files
excluded: .git

largest directories (4):
    812.4 MB  media
    604.1 MB  archive
    233.7 MB  node_modules
     92.8 MB  docs

largest files (2):
     310.2 MB  archive/2025-06-backup.zip
     204.9 MB  media/raw/dsc_0421.mov

read-only scan; nothing was changed.
```

Exit codes: `0` scanned; `2` bad path or bad usage. An empty result is a successful
scan of an empty tree, not an error — say so rather than reporting a failure.

Run `python3 scripts/disk_scan.py --help` for the authoritative flag list.

## Which number answers the question

The two lists point at different actions, and conflating them sends the user to the
wrong place:

- **A large directory with no large files** is a breadth problem — many small files.
  Cleaning it means deleting *sets*, and the directory ranking is the useful one.
- **A large file inside a small directory** is a single-artifact problem, and the file
  ranking is the useful one. `--min-mb` makes these visible when a long tail of small
  files outranks them.
- **A directory showing as large but surfacing nothing large inside** usually means
  one nested directory holds everything; scan that path directly to descend.

Report the measurement and the shape, not a verdict. "media is 812 MB, mostly video"
is actionable; "your storage is a mess" is not.

## What this cannot do

| limitation | consequence |
|---|---|
| Reports logical size, not on-disk size | Block rounding, sparse files, compression and copy-on-write means the bytes a clean-up actually frees can be smaller — sometimes much smaller — than the figure here |
| Does not follow symlinks | A symlink to a huge tree contributes nothing; the same as never following symlinks to avoid loops. Follow the link yourself and scan the target |
| Counts hard links once per path | A file hard-linked in two places is counted twice, so totals can exceed the real usage |
| Skips what it cannot read | Permission errors are counted as `skipped_entries` in `--json`, never as zero. A sandbox root will skip a lot — report the skip count instead of presenting the total as complete |
| Reads metadata only | It does not open files, so it cannot detect duplicates. Two identical 300 MB files are 600 MB here, correctly |
| Single filesystem | Mount points appear as directories on the same filesystem; there is no per-device breakdown |
| Cannot clean anything | Deletion is out of scope by design. Never present this output as a cleanup |

When the user's real goal is reclaiming space, pair the measurement with an explicit
decision about what can go: name the candidates, state what freeing them would
actually recover in the user's terms, and get confirmation before anything is
removed.

## Examples

**"Why is my phone full?"** Find the reachable root first — on a sandboxed device the
answer is often that the big data is outside what the scanner can see, which is itself
the finding worth reporting. Scan, then compare against the device's reported free
space: if the scan totals far less than the storage that is missing, the remainder is
in app containers the sandbox cannot reach, and that is the honest answer.

**Descend into a hot directory.**

```bash
python3 scripts/disk_scan.py --dir /workspace/media --top 20
```

**Cut the noise in a code project.**

```bash
python3 scripts/disk_scan.py --dir . --top 10 --exclude .git,node_modules --min-mb 5
```

Excluding is for readability here, not for accuracy — if the question is "what could I
free", do not exclude: `node_modules` may well be the answer.

**Machine-readable, for a report.**

```bash
python3 scripts/disk_scan.py --dir /workspace --json > scan.json
```

`total_bytes`, `file_count`, `skipped_entries` and both ranked lists are all present,
so a downstream step can quantify rather than parse the human output.

## Working on Minis

- **Run it in the on-device shell.** `python3 scripts/disk_scan.py --dir <path>` needs
  no install — the sandbox already has the interpreter this needs.
- **Scan the workspace, not the whole device.** What is reachable depends on what the
  sandbox has been granted, and the app container is deliberately not open. Establish
  what the user means by "full" — the sandbox, the shared folders, or the device
  overall — before scanning, because a scan of the reachable tree will not add up to
  the device's storage and presenting it as if it did would be wrong.
- **Read `skipped_entries` before you report a total.** On a device it will rarely be
  zero, and a total that silently dropped unreadable directories reads as complete when
  it is not. If it is non-zero, one line stating what was skipped belongs in the answer.
- **Nothing here is destructive, so it is safe to run unprompted** when the user is
  only asking a question. The moment the conversation turns to deleting, stop and get
  an explicit decision per item; do not slide from measurement into cleanup.
