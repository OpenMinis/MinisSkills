---
name: ytmusic-hub
description: Read and write YouTube Music data using Python + ytmusicapi, authenticated via browser cookies obtained automatically with browser_use get_cookies — no manual copying required. Supports fetching playlists, liked songs, playlist details, creating/editing/deleting playlists, searching and adding songs, recommendations, charts, and lyrics. Trigger this skill whenever the user mentions "YouTube Music", "YT Music", "ytmusic", "ytmusic-hub", "get YouTube playlists", "create YouTube Music playlist", "my liked songs", "YTM playlist", or any scenario requiring programmatic read/write access to YouTube Music data.
---

# ytmusic-hub

Interact with YouTube Music using the `ytmusicapi` library, authenticated via browser cookies. Supports full playlist management, search, liked songs, and more.

---

## Setup

### Install dependency
```bash
pip install ytmusicapi
```

### Auth file path
```
/var/minis/workspace/ytmusic_headers.json
```

---

## Authentication (run before first use or when cookies expire)

Two steps: **get cookies** → **generate auth file**.

### Step 1: Get cookies

Navigate to YouTube Music and get cookies via `browser_use`:

```
browser_use navigate: https://music.youtube.com
browser_use get_cookies -> save env file path
```

Confirm the page is logged in (avatar visible in top-right), then call `get_cookies` and note the env file path.

### Step 2: Generate auth file

Load the env file and run the auth setup script:

```bash
. /var/minis/offloads/env_cookies_youtube_com_xxx.sh
python3 /var/minis/skills/ytmusic-hub/scripts/setup_auth.py
```

The script reads all Cookie env vars and writes a browser-auth file with SAPISIDHASH to `/var/minis/workspace/ytmusic_headers.json`.

### Step 3: Initialize YTMusic client

Use the unified client module — it automatically handles DNS pollution and SSL issues:

```python
import sys
sys.path.insert(0, "/var/minis/skills/ytmusic-hub/scripts")
from ytmusic_client import get_client

yt = get_client()
```

`get_client()` will automatically:
1. Patch urllib3 to disable SSL certificate verification (required in iSH)
2. Detect if local DNS is polluted
3. If polluted, resolve the real IP via Google DoH and patch `socket.getaddrinfo`
4. Return a ready-to-use YTMusic instance, or raise `RuntimeError` with a clear message

---

## API Reference

### 📋 Playlist Management

```python
# Get all my playlists
playlists = yt.get_library_playlists(limit=25)
# Returns: [{playlistId, title, count, ...}, ...]

# Get playlist contents (all tracks)
playlist = yt.get_playlist(playlistId, limit=100)
# Returns: {title, description, trackCount, tracks: [{videoId, title, artists, ...}]}

# Create a new playlist
playlistId = yt.create_playlist(
    title="Playlist name",
    description="Description",
    privacy_status="PRIVATE"  # PUBLIC / PRIVATE / UNLISTED
)

# Edit playlist metadata
yt.edit_playlist(playlistId, title="New name", description="New description")

# Delete a playlist
yt.delete_playlist(playlistId)

# Add songs to a playlist
yt.add_playlist_items(playlistId, videoIds=["videoId1", "videoId2"])

# Remove songs from a playlist
# setVideoId is the track's unique ID within the playlist (different from videoId)
tracks = yt.get_playlist(playlistId)["tracks"]
yt.remove_playlist_items(playlistId, tracks=[
    {"videoId": t["videoId"], "setVideoId": t["setVideoId"]}
    for t in tracks if t["title"] == "Target song"
])
```

### ❤️ Liked Songs & Library

```python
# Get liked songs
liked = yt.get_liked_songs(limit=100)
tracks = liked["tracks"]  # [{videoId, title, artists, album, ...}]

# Get library songs / albums / artists
songs   = yt.get_library_songs(limit=25)
albums  = yt.get_library_albums(limit=25)
artists = yt.get_library_artists(limit=25)

# Like / unlike a song
yt.rate_song(videoId, "LIKE")   # LIKE / DISLIKE / INDIFFERENT
```

### 🔍 Search

```python
# General search (mixed results)
results = yt.search("Jay Chou")

# Filter by type
songs   = yt.search("Jay Chou", filter="songs")
videos  = yt.search("Jay Chou", filter="videos")
albums  = yt.search("Jay Chou", filter="albums")
artists = yt.search("Jay Chou", filter="artists")

# Get videoId for adding to playlist
videoId = songs[0]["videoId"]
```

### 🎵 Browse & Recommendations

```python
# Home feed
home = yt.get_home()

# Charts (global or by country)
charts = yt.get_charts(country="US")  # TW / HK / CN / JP / KR etc.

# Mood playlists
moods = yt.get_mood_categories()
mood_playlists = yt.get_mood_playlists(params=moods["Moods & moments"][0]["params"])

# Lyrics
watch = yt.get_watch_playlist(videoId="videoId")
lyrics_id = watch.get("lyrics")
if lyrics_id:
    lyrics = yt.get_lyrics(lyrics_id)
    print(lyrics["lyrics"])
```

### 🎤 Artists & Albums

```python
artist = yt.get_artist(channelId)
album  = yt.get_album(browseId)
user   = yt.get_user(channelId)
user_playlists = yt.get_user_playlists(channelId, params)
```

---

## Common Workflows

### Workflow A: Search and add a song to a playlist

```python
results = yt.search("Gao Wu Ren - Love Missed", filter="songs")
videoId = results[0]["videoId"]

playlists = yt.get_library_playlists()
for i, pl in enumerate(playlists):
    print(f"{i+1}. {pl['title']} [{pl['playlistId']}]")

yt.add_playlist_items(playlistId, videoIds=[videoId])
print("✅ Added to playlist")
```

### Workflow B: Create a playlist from liked songs

```python
new_id = yt.create_playlist("My Favorites", "Picked from liked songs", "PRIVATE")
liked  = yt.get_liked_songs(limit=50)
ids    = [t["videoId"] for t in liked["tracks"][:20]]
yt.add_playlist_items(new_id, videoIds=ids)
print(f"✅ Created playlist with {len(ids)} songs")
```

### Workflow C: Export a playlist as Markdown

```python
playlist = yt.get_playlist(playlistId, limit=200)
lines = [f"# {playlist['title']}", f"> {playlist.get('description', '')}", ""]
for i, t in enumerate(playlist["tracks"], 1):
    artists = ", ".join(a["name"] for a in t.get("artists", []))
    lines.append(f"{i}. **{t['title']}** — {artists}")
print("\n".join(lines))
```

---

## Notes

- **Cookie expiry**: Cookies typically last days to weeks. Re-run the auth flow when they expire.
- **Auth file security**: `ytmusic_headers.json` contains login credentials — do not share it.
- **Rate limits**: ytmusicapi is unofficial. Avoid bulk operations that may trigger Google's rate limiting.
- **Network**: Requires access to `music.youtube.com`. The client module handles DNS pollution and SSL issues automatically.
- **videoId vs setVideoId**: When removing tracks from a playlist, you must use `setVideoId` (the track's position-specific ID), not `videoId`.
