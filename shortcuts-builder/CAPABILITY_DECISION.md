# CAPABILITY_DECISION.md

## Core Question

Not every natural-language automation request is suited to becoming an Apple Shortcut.

Before generating, answer:

1. **Is Shortcuts suitable as the primary carrier?**
2. **Pure Shortcuts, or Hybrid?**
3. **Is it worth generating a finished product, rather than just giving an execution plan?**

## Decision Tree

### A. Prefer pure Shortcuts

The more of these that hold, the better the fit:

- Simple input: text, URL, date, location, share input
- Simple output: display, notification, Reminders, Notes, file, share, open URL
- Short flow
- Relies mainly on native system actions
- Does not depend heavily on web login state, cookies, or complex DOM
- Low retry cost on failure

### B. Prefer Hybrid

If any of these holds, seriously consider it:

- Needs Minis or an external script to handle complex logic
- Needs a downloader, transcoder, browser automation, or signer
- Needs to call third-party services
- Shortcuts should only handle the entry point, parameter collection, and result display

### C. Not recommended as a Shortcut

The more of these that hold, the worse the fit:

- Depends heavily on long-running background execution
- Depends heavily on complex web scraping, login state, or cookies
- Needs heavy file processing or has a high retry-on-failure rate
- The real value lies in shell / Python / browser automation, not Shortcuts interaction

## Typical Judgments

- Check weather: pure Shortcuts preferred
- Set an alarm: pure Shortcuts preferred
- Screenshot then share: pure Shortcuts preferred
- Quickly log text into a system app: pure Shortcuts preferred
- Write to a third-party notes app: depending on URI, plugin, or action support, may be pure Shortcuts or Hybrid
- Download web resources: depends; may be Hybrid
- Download videos from short-video platforms: usually judge as Hybrid or not suitable for pure Shortcuts

## Output Requirements

During internal planning, you must tag the task with one label:

- `shortcut-native`
- `shortcut-hybrid`
- `not-shortcut-first`

This label determines the subsequent workflow; do not change the route halfway through.
