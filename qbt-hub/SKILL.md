---
name: qbt-hub
description: Manage qBittorrent downloads via WebUI API (v5.0+). Use this skill whenever the user asks to add a torrent or magnet link, check download progress, search/filter tasks, delete tasks, set speed limits, manage tags/categories, or do anything related to qBittorrent. Trigger keywords: "qBittorrent", "qbt", "torrent", "magnet", "download task", "seeding", "add torrent", "qbt-hub".
---

# qbt-hub

Manage qBittorrent (v5.0+) via its WebUI API using the bundled `scripts/qbt.py`.

## Authentication

Credentials are read from env vars (set once, reused forever):
- `QBT_HOST` — e.g. `http://qbt.example.com`
- `QBT_USER` — WebUI username
- `QBT_PASS` — WebUI password

Can also be overridden per-call: `--host / --user / --pass`

## Script Location

```
/var/minis/skills/qbt-hub/scripts/qbt.py
```

Alias for convenience:
```bash
alias qbt="python3 /var/minis/skills/qbt-hub/scripts/qbt.py"
```

## Commands

### Add a task

```bash
# magnet link
python3 qbt.py add "magnet:?xt=urn:btih:..."

# https .torrent URL
python3 qbt.py add "https://example.com/file.torrent"

# local .torrent file
python3 qbt.py add ~/Downloads/movie.torrent

# with options
python3 qbt.py add "magnet:..." --savepath /data/movies --category Movies --tags "4K,DV" --paused --sequential
```

### List / filter tasks

```bash
python3 qbt.py list                              # all tasks
python3 qbt.py list --filter downloading         # active downloads
python3 qbt.py list --filter completed
python3 qbt.py list --tag 4K --sort size         # filter by tag, sort by size
python3 qbt.py list --category Movies --asc
```

Filter choices: `all` `downloading` `seeding` `completed` `paused` `active` `inactive` `stalled` `errored`
Sort choices: `name` `size` `progress` `dlspeed` `upspeed` `ratio` `added_on`

### Search

```bash
python3 qbt.py search ubuntu          # fuzzy match on task name
```

### Global status

```bash
python3 qbt.py status                 # DL/UL speed, totals, limits, turtle mode
```

### Task details

```bash
python3 qbt.py info ubuntu            # progress, files, trackers, peers
```

### Pause / Resume / Recheck

```bash
python3 qbt.py pause ubuntu
python3 qbt.py resume all
python3 qbt.py recheck ubuntu
```

### Delete

```bash
python3 qbt.py delete ubuntu          # keep local files
python3 qbt.py delete ubuntu --files  # also delete local data
```

### Speed limits

```bash
# per-task
python3 qbt.py limit ubuntu --dl 500 --ul 100   # KB/s
python3 qbt.py limit ubuntu --dl 0              # remove limit

# global
python3 qbt.py speedlimit                        # show current
python3 qbt.py speedlimit --dl 2048 --ul 512
python3 qbt.py speedlimit --dl 0                 # unlimited
python3 qbt.py speedlimit --alt                  # toggle turtle mode
```

### Tags

```bash
python3 qbt.py tag ubuntu --tags "linux,iso"
python3 qbt.py untag ubuntu --tags "iso"
python3 qbt.py tags                              # list all tags with counts
```

### Categories

```bash
python3 qbt.py category ubuntu --cat Linux
python3 qbt.py categories                        # list all categories
```

### Rename / Move

```bash
python3 qbt.py rename ubuntu --name "Ubuntu 24.04 LTS"
python3 qbt.py move ubuntu --path /data/iso
```

### Top N

```bash
python3 qbt.py top --n 10 --sort size    # largest tasks
python3 qbt.py top --n 5 --sort dl       # fastest downloads
python3 qbt.py top --n 5 --sort ratio    # highest ratio seeders
```

Sort choices: `size` `dl` `ul` `ratio` `progress` `added`

### RSS

```bash
python3 qbt.py rss list
python3 qbt.py rss add --url "https://example.com/feed.rss"
python3 qbt.py rss remove --path "FeedName"
python3 qbt.py rss addrule --name "4K Shows" --pattern "2160p" --category TV
python3 qbt.py rss removerule --name "4K Shows"
```

## Workflow: Search the web and add a torrent

1. Search for the torrent on sites like `torrentkitty.net` or `thepiratebay.org` using `browser_use`
2. Extract the magnet link from the page
3. Run `python3 qbt.py add "<magnet>" --savepath /path --tags "tag1,tag2"`

## Common patterns

```bash
# Check what's currently downloading
python3 qbt.py list --filter downloading

# Find and delete a large task including its files
python3 qbt.py top --n 10 --sort size
python3 qbt.py delete "keyword" --files

# Tag all completed tasks
python3 qbt.py list --filter completed   # find keyword
python3 qbt.py tag "keyword" --tags "done"

# Slow down a task to save bandwidth
python3 qbt.py limit "keyword" --dl 200 --ul 50
```

## Notes

- `keyword` matching is case-insensitive fuzzy match on task name
- Use `all` as keyword to target every task (e.g. `resume all`, `pause all`)
- `delete` always prompts for confirmation before executing
- `rename` requires an exact single match; use a more specific keyword if multiple tasks match
- qBittorrent instance: `http://qbt.wsen.me` (internal network, v5.0.2)
