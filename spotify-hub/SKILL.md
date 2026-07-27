---
name: spotify-hub
version: 1.0.0
description: A skill that uses Python and spotipy to control Spotify playback. It supports play/pause, skipping tracks, volume, shuffle, searching for and playing songs, generating mixed playlists from keywords (for example, TikTok hits, a specific genre, or a specific artist), and viewing the current playback status and device list. This skill must be triggered whenever the user mentions "Spotify," "play music," "skip a track," "pause," "search for a song," "switch playlists," "spotify-hub," or any scenario that requires controlling Spotify playback.
---

# Spotify Hub

Use the spotipy library to call the Spotify Web API, control playback, and search for music.

## Dependencies

Both scripts declare dependencies (`spotipy>=2.26.0`) using **uv inline script**. When executed with `uv run`, they are installed automatically, so no manual `pip install` is required.

## Environment Requirements

The following environment variables must be set. If they are not set, guide the user to create them:
- `SPOTIPY_CLIENT_ID` — [Settings](minis://settings/environments?create_key=SPOTIPY_CLIENT_ID&create_value=)
- `SPOTIPY_CLIENT_SECRET` — [Settings](minis://settings/environments?create_key=SPOTIPY_CLIENT_SECRET&create_value=)
- `SPOTIPY_REDIRECT_URI` — [Settings](minis://settings/environments?create_key=SPOTIPY_REDIRECT_URI&create_value=http://127.0.0.1:8888/callback)

Apply for credentials at https://developer.spotify.com/dashboard → Create App → set Redirect URI to `http://127.0.0.1:8888/callback`

## Authorization Flow (First Time or When the Token Expires)

The token is stored in `~/.config/spotify/cache` and includes a refresh_token. Under normal circumstances, it remains valid indefinitely and does not require repeated authorization.

**When authorization is required**, start the authorization server in the background, get the URL, and give it directly to the user to click:

```python
# Start the authorization server in the background
import subprocess, time
subprocess.Popen(["uv", "run", "--script", "--cache-dir", "/root/.cache/uv",
                              "/var/minis/skills/spotify-hub/scripts/spotify_auth.py"],
                 stdout=open("/tmp/spotify_auth.log", "w"), stderr=subprocess.STDOUT)
time.sleep(2)
url = open("/tmp/spotify_auth_url.txt").read().strip()
print(url)
```

Then provide the user with a clickable authorization link in the reply:
`[👉 Click to authorize Spotify](<url>)`

After authorization is complete, the browser displays "✅ Spotify authorization successful!". Once the user informs you, you can continue.

## Core Script

All operations are executed through `/var/minis/skills/spotify-hub/scripts/spotify.py`:

```bash
uv run --script --cache-dir /root/.cache/uv /var/minis/skills/spotify-hub/scripts/spotify.py <cmd> [args]
```

| Command | Description |
|------|------|
| `status` | Current playback status + device list |
| `play` / `pause` | Play / pause |
| `next` / `prev` | Next track / previous track |
| `volume <0-100>` | Set volume |
| `shuffle on/off` | Toggle shuffle |
| `repeat off/track/context` | Repeat mode |
| `seek <seconds or mm:ss>` | Seek playback position |
| `search <keyword>` | Search and play |
| `play-track <id/uri>` | Play a specified track |
| `play-playlist <id/uri>` | Play a specified playlist |
| `save` / `unsave` | Save / unsave the current track |
| `liked [count]` | View saved tracks |
| `recent [count]` | Recently played history |
| `top [tracks/artists] [count]` | Most-listened tracks / artists |
| `playlists` | View my playlist list |
| `create-playlist <name>` | Create a playlist |
| `add-to-playlist <id>` | Add the current track to a playlist |
| `follow <artist name>` | Follow an artist |
| `following` | View followed artists |

## Popular Playlist Scenarios (for example, "TikTok Hits" or "a Specific Genre")

Third-party public playlists will return 403. **Do not attempt to read playlists**. Instead, use multi-keyword search to mix and play tracks:

```python
from scripts.spotify import get_sp, search_multi_and_play

sp = get_sp()
keywords = ["TikTok trending", "douyin trending", "tiktok viral 2024", "TikTok hit songs"]
search_multi_and_play(sp, keywords, count_each=10, market="HK")
```

Or call `spotify.py search` directly with `shell_execute`:
```bash
uv run --script --cache-dir /root/.cache/uv /var/minis/skills/spotify-hub/scripts/spotify.py search "TikTok trending"
```

## Notes

- Playback control requires an active device (Spotify is open on a phone or computer and has played before)
- `market="HK"` can find more Chinese songs
- spotipy is preinstalled (`pip show spotipy` can verify this)
- In Development Mode, 403 for third-party public playlists is a normal restriction. Use search instead.
