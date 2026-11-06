# Floating Window Interaction & Human Takeover

## Visual States & Controls
- Video fills the rounded card edge-to-edge; the title pill and action buttons overlay the top of the video without adding extra bar height.
- An AGSL breathing-light border animates around the card edges:
  - **Fast multi-color (blue/purple/orange/pink)**: AI is actively operating
  - **Calm light blue**: AI standby
  - **Green**: Human takeover active
  - **Red/orange**: AI stopped by user
- Top-bar controls:
  - Left: **Task title pill** (shows current step, e.g. `Computing 37x42`; hidden during takeover so it does not overlap the resume pill)
  - Right:
    - While AI is operating: Red circular **Stop button** (white square icon)
    - Standby / Human operating: Gray circular **x Close button** (first tap arms confirmation and displays `Tap again to close`; second tap within 3 seconds shuts down the entire virtual display stack)
    - Takeover / Stopped state: Green **"Hand back to AI" pill**

## Gesture Rules
| Gesture | While AI Is Operating | Standby State | Human in Control |
|---|---|---|---|
| **Light tap** | Ignored (no takeover, not forwarded) | Ignored (no takeover, not forwarded; hold 1 s first) | Forwarded as tap to virtual display |
| **One-finger drag** | Moves floating window (snaps/docks at screen edges) | Moves floating window | Forwarded as swipe to virtual display |
| **Stationary 1 s long-press** | **Enters takeover** (green progress ring fills over 1 s) | **Enters takeover** | Forwarded as long-press to virtual display |
| **Two-finger pinch / spread** | **Proportional resize** (anchored at finger midpoint) | **Proportional resize** | **Proportional resize** |
| **Drag to left/right screen edge** | **Docks & collapses into arrow pull-tab** | **Docks & collapses** | **Docks & collapses** |

- **Docked / collapsed state**: The card slides off-screen and leaves a small rounded arrow pull-tab on the screen edge. The virtual display continues running in the background and the agent can still query `/ui`, take screenshots, and inject actions; tapping the pull-tab expands the card back onto the screen.
- **Size bounds & control scaling**: Window width is clamped between `120dp` and `85%` of the screen; top-bar controls and the center hint scale proportionally (`0.75x` to `1.15x`) so buttons never look oversized on a small card.

## Human Takeover & HTTP 423
- **Entering takeover**: Stationary long-pressing the card for 1 second (or tapping the top-right Stop button) enters takeover mode.
- **HTTP 423 interception**: Throughout takeover, every control request from the agent (`tap`, `swipe`, `key`, `text`, `start`) is rejected with **HTTP 423**:
  ```json
  {"ok": false, "error": "human has control", "humanActive": true}
  ```
  If the user tapped the top-right Stop button, the response is:
  ```json
  {"ok": false, "error": "stopped by user", "hint": "The user pressed Stop. Ask the user before continuing, or ask them to tap Hand back to AI."}
  ```
- **Agent handling rules**:
  1. Never retry in a tight loop when receiving HTTP 423.
  2. Pause immediately and inform the user in chat that manual takeover / stop was detected and they can tap **Hand back to AI** on the floating window when ready.
  3. Only pass `force=1` if the user explicitly instructs the agent in chat to continue despite takeover.
- **Read-only operations remain available**: Widget tree inspection (`ui`), screenshots (`shot`), status queries (`status`), and title updates (`title`) continue to work normally during takeover.
