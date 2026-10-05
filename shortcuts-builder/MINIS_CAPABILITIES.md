# MINIS_CAPABILITIES

## Purpose

When building a shortcut, if the task involves iOS system capabilities, Minis's own tools, or needs Hybrid execution, this document provides a quick **scenario → Minis command** mapping.

Use it for:
- Scenario analysis: decide which Minis tools can cover the user's needs
- Hybrid route design: define the boundary between the shortcut entry point and Minis backend execution
- Command parameter lookup: check command usage quickly without re-running `--help` every time

## Quick Scenario Lookup Table

| User scenario keywords | Minis tool | Scenario tag |
|---|---|---|
| alarm, timer | `apple-alarm` | Time management |
| reminder, to-do, Reminders | `apple-reminders`, `apple-calendar remind` | Time management |
| calendar, schedule, meeting | `apple-calendar` | Time management |
| notification, push alert | `apple-notification` | System interaction |
| weather, temperature, rain | `apple-weather` | Information lookup |
| location, positioning, nearby, navigation | `apple-location`, `apple-maps` | Spatial awareness |
| map, route, commute | `apple-maps` | Spatial awareness |
| clipboard, copy/paste | `apple-clipboard` | Input/output |
| device info, battery, storage | `apple-device` | System monitoring |
| health, exercise, steps, heart rate, sleep | `apple-healthkit` | Health tracking |
| smart home, lights, AC, scenes | `apple-homekit` | Smart home |
| media, music, playback, volume | `apple-media` | Media control |
| player, video, audio playback | `apple-player` | Media control |
| read aloud, voice announcement, TTS | `apple-speak` | Voice interaction |
| speech recognition, speech-to-text, recording | `apple-speech` | Voice interaction |
| NFC, read card, write card, bank card | `apple-nfc` | Physical interaction |
| photos, albums, image management | `apple-photos` | Media management |
| vision, OCR, scan code, faces, image classification | `apple-vision` | AI perception |
| NLP, tokenization, sentiment, entity recognition, embeddings | `apple-nlp` | AI perception |
| Bluetooth, BLE devices | `apple-bluetooth` | Peripheral connectivity |
| browser, web screenshot, web scraping | `minis-browser-use` | Web interaction |
| Minis chats, search history, send message | `minis-sessions-cli` | Minis self-interaction |
| call AI model, generate image | `minis-model-use` | AI capability |
| app settings, config changes | `minis-config` | System configuration |
| open file, preview URL | `minis-open`, `apple-open` | General entry point |

---

## Tool Categories in Detail

### 1. Time Management

| Tool | Core commands | Typical scenarios | Hybrid suitable |
|---|---|---|---|
| `apple-alarm` | `set`, `timer`, `list`, `cancel` | Timed reminders, countdowns, alarm management | ✅ |
| `apple-calendar` | `list`, `create`, `update`, `delete`, `remind`, `freebusy`, `calendars` | Schedule queries, creating events, free time slots | ✅ |
| `apple-reminders` | `list`, `create`, `update`, `complete`, `delete` | To-do management, reminder creation | ✅ |
| `apple-notification` | `schedule`, `pending`, `cancel`, `settings` | Local push, scheduled notifications | ✅ |

**Scenario matching priority**:
- User says "remind me to do X" → first decide between a system reminder (`apple-reminders`), an alarm (`apple-alarm`), or a notification (`apple-notification`)
- User says "show today's schedule" → `apple-calendar list --today`
- User says "wake me at 2 pm" → `apple-alarm set --time 14:00`

### 2. Information Lookup

| Tool | Core commands | Typical scenarios | Hybrid suitable |
|---|---|---|---|
| `apple-weather` | `current`, `hourly`, `daily`, `alerts`, `report` | Weather briefings, travel advice, outfit suggestions | ✅ (query only) |
| `apple-location` | `current`, `geocode`, `forward` | Current location, address resolution, coordinate conversion | ✅ |
| `apple-maps` | `search`, `route`, `eta` | Nearby search, route planning, commute time | ✅ |

**Combination patterns**:
- "Weather + commute time before leaving" → `weather current` + `maps eta`
- "What's nearby" → `location current` → `maps search --lat ... --lon ...`

### 3. AI Perception

| Tool | Core commands | Typical scenarios | Hybrid suitable |
|---|---|---|---|
| `apple-vision` | `ocr`, `barcode`, `classify`, `detect`, `faces`, `analyze`, `similarity`, `overlap` | Image text recognition, code scanning, image classification, face detection, image similarity, long-screenshot stitching | ✅ (strongly recommended) |
| `apple-nlp` | `language`, `tokenize`, `pos`, `ner`, `sentiment`, `embed`, `analyze` | Language detection, tokenization, part-of-speech tagging, entity recognition, sentiment analysis | ✅ |
| `apple-speech` | `transcribe`, `languages`, `status` | Speech-to-text, meeting notes | ✅ |
| `apple-speak` | `speak`, `voices`, `stop` | Text read-aloud, notification announcements | ✅ |

**Combination patterns**:
- "Take a photo, extract text, and read it aloud" → `vision ocr` → `speak`
- "Voice memo to text" → `speech transcribe --source file` → save the text
- "Analyze and describe a photo" → `vision analyze` → `speak`

### 4. Media Management

| Tool | Core commands | Typical scenarios | Hybrid suitable |
|---|---|---|---|
| `apple-photos` | `list`, `near`, `albums`, `album`, `stats`, `export`, `import`, `favorite`, `delete` | Photo search, album management, import/export | ✅ |
| `apple-media` | `now-playing`, `play`, `pause`, `toggle`, `next`, `prev`, `volume`, `search`, `play-search` | Music control, media library search | ✅ |
| `apple-player` | `play`, `pause`, `resume`, `seek`, `status`, `stop`, `list` | Audio/video playback control | ✅ |

**Combination patterns**:
- "Export recent photos to Minis" → `photos list --days 1` → `export --id ...`
- "Search for and play a song" → `media play-search --query ...`

### 5. Smart Home

| Tool | Core commands | Typical scenarios | Hybrid suitable |
|---|---|---|---|
| `apple-homekit` | `list`, `search`, `get`, `set`, `scenes`, `trigger` | Device control, scene execution | ✅ |
| `apple-bluetooth` | `status`, `scan`, `connect`, `read`, `write`, `notify` | BLE device interaction | ✅ |

**Scenario matching**:
- "Arrive-home mode" → `homekit trigger --name "Arrive Home"`
- "Dim the living room light" → `homekit set --name "Living Room Light" --characteristic brightness --value 30`
- "Scan for nearby Bluetooth devices" → `bluetooth scan --duration 10`

### 6. Health Tracking

| Tool | Core commands | Typical scenarios | Hybrid suitable |
|---|---|---|---|
| `apple-healthkit` | `steps`, `heart-rate`, `sleep`, `workouts`, `weight`, `summary`, `batch`, `types`, `log`, `delete` | Health data queries, workout summaries, data writing | ✅ |

**High-frequency scenarios**:
- "Today's steps" → `healthkit steps --today`
- "This week's workout summary" → `healthkit summary --days 7`
- "Sleep analysis" → `healthkit sleep --days 7`
- "Batch export health data" → `healthkit batch --types steps,heart-rate,sleep,active-energy --days 7`

### 7. System Interaction and Device

| Tool | Core commands | Typical scenarios | Hybrid suitable |
|---|---|---|---|
| `apple-clipboard` | `get`, `set`, `clear`, `status` | Clipboard read/write, text relay | ✅ |
| `apple-device` | `info`, `battery`, `storage` | Device monitoring, battery queries | ✅ |
| `apple-open` | `<url>`, `settings[://page]` | Open an app/URL/settings | ✅ |
| `minis-open` | `<url-or-path>` | Preview files/URLs inside Minis | — |
| `minis-config` | `get`, `set`, `list-topics`, `audit-list` | Change Minis settings | — (use with caution) |

**Typical uses**:
- After a shortcut processes text, copy it to the clipboard → `clipboard set --text "..."`
- Open an app after a shortcut finishes → `apple-open "app-scheme://"`

### 8. NFC and Physical Interaction

| Tool | Core commands | Typical scenarios | Hybrid suitable |
|---|---|---|---|
| `apple-nfc` | `scan`, `write`, `tag-info`, `read-emv`, `apdu`, `felica`, `search` | NFC tag read/write, bank card reading, transit card queries | ✅ |

**Typical uses**:
- "Scan an NFC tag to get its content" → `nfc scan`
- "Read a transit card balance" → `nfc felica` or `nfc apdu`

### 9. Web Interaction (Minis-specific)

| Tool | Core commands | Typical scenarios | Hybrid suitable |
|---|---|---|---|
| `minis-browser-use` | `navigate`, `screenshot`, `click`, `type`, `get_text`, `get_readable`, `fetch`, `scroll_and_collect`, `execute_js` | Web screenshots, content extraction, form filling, file downloads | ✅ (core) |

**Typical uses**:
- "Screenshot this web page" → `browser-use navigate` → `screenshot --full-page`
- "Extract the article body" → `browser-use navigate` → `get_readable`
- "Download a file from a web page" → `browser-use navigate` → `fetch --url ...`

### 10. Minis Self-Interaction

| Tool | Core commands | Typical scenarios | Hybrid suitable |
|---|---|---|---|
| `minis-sessions-cli` | `list`, `search`, `messages`, `send`, `retry`, `status`, `open` | Chat history search, automated conversations, cross-session queries | ✅ |
| `minis-model-use` | `list`, `search`, `run` | Call AI models, generate images, text/audio/video generation | ✅ |

**Typical uses**:
- "Search earlier conversations" → `sessions-cli search --keywords "..."`
- "Have AI generate an image" → `model-use run --model ... --prompt "..."`

---

## Using Minis Commands in Hybrid Routes

### Pattern A: Shortcut as entry point + Minis as backend

```
Shortcut: Ask for Input → URL (minis-sessions-cli send) → Open URL
Minis:    receive input → run command chain → return result
```

**Suitable scenarios**:
- Capabilities that shortcuts do not support natively (NFC read/write, Bluetooth interaction, HealthKit queries, etc.)
- Complex tasks that need AI processing

### Pattern B: Shortcut collects + Minis processes + writes back to the system

```
Shortcut: Share Sheet → Get File → Save File (to /var/minis/)
Minis:    watch file → process (OCR/analysis/conversion) → write back via apple- commands
```

### Pattern C: Minis commands embedded directly in a shortcut

Implemented through `apple-open` with a URL Scheme or `shortcuts://run-shortcut`:
- Inside a shortcut, call `apple-open "shortcuts://run-shortcut?name=..."` to chain-trigger

---

## Usage Rules

1. **Scenario analysis**: check the "Quick Scenario Lookup Table" first to locate the relevant tools
2. **Route decision**: if the task's core capability lives in a Minis tool rather than a native Shortcuts action → mark it as `shortcut-hybrid`
3. **Command confirmation**: once the tool is chosen, consult the category details in this document to confirm parameters
4. **When parameters are uncertain**: run `<tool> --help` in the shell for the latest help
5. **Commands not in this document**: run `ls /usr/local/bin/apple-* /usr/local/bin/minis-*` to see the full list

## Maintenance Principles

- Update this document whenever a new Minis command is added
- Scenario keywords may be extended as needed, but keep each keyword mapped to one clear tool
- Do not duplicate all the details of `--help`; keep only the parameter combinations most commonly used when building shortcuts
