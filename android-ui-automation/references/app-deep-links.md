# Android App Deep Link Reference

Deep links let us jump straight into a target app's view without an API.
Scheme handling differs per app; test each once before relying on it.

## Spotify (`com.spotify.music`)
Directly supports search via `spotify://search/<query>`:

```
spotify://search/circles%20post%20malone
spotify://search/<percent-encoded-query>
```

- Opens Spotify and pre-fills the search — no OAuth, no API key. Works on Free accounts.
- **Known limitation (verified 2026-08-11):** the deep link lands on the
  *suggestion* page, NOT finished results. To reach results: tap a suggestion
  row such as `添加建议"<query>"` (find_node query: the suggestion text), then
  tap the result row. Tapping a suggestion may start playback from the queue
  immediately — verify with the `暂停` (pause) marker on the bottom bar.
- Foreground package to expect: `com.spotify.music`.
- After opening, the first result row usually matches; tap and verify a pause
  button appears to confirm playback.

## WeChat / Weixin (`com.tencent.mm`)
```
weixin://               → opens the app (often the chat list)
weixin://dl/moments     → Moments (朋友圈) foreground directly on some builds
```

- **Known limitation:** Moments shields its inner view tree from the
  Accessibility Service — `ui dump` may return no `com.tencent.mm` nodes. Do
  NOT blindly tap guessed coordinates; prefer `gesture swipe` for scroll-only
  automation, and ask the user to tap anything that needs exact positioning.

## YouTube (`com.google.android.youtube`)
```
https://www.youtube.com/results?search_query=<encoded>   → search results
vnd.youtube:<videoId>                                    → play a video
```

## Bilibili (`tv.danmaku.bili`)
```
bilibili://search/?keyword=<encoded>
https://www.bilibili.com/video/BV1... → web link, usually opens the app
```

Not all schemes are registered on every build. If `ui info` shows the expected
package did not reach the foreground, the scheme may be unhandled — fall back to
coordinating with the user or find another entry point.

## Guidance
- **Always verify foreground** after opening (see `open_deep_link.py`).
- **Percent-encode** query values; CJK and `&`/`?` break otherwise.
- When a scheme is unreliable, ask the user for an alternative entry point
  (home screen tap, etc.) rather than guessing.
