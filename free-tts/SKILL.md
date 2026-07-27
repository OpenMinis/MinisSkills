---
name: free-tts
version: 1.0.0
description: >
  Free text-to-speech (edge-tts), with no API key or registration required. Converts text to MP3 audio files.
  Trigger this skill when the user says "read aloud," "text-to-speech," "TTS," "generate audio," "read it,"
  "read it out loud," "say it," "play it," or in any scenario where text needs to be converted to speech for playback.
---

# Free TTS Skill

Use `edge-tts` (a Python library) to convert text to an MP3 audio file. It calls the Microsoft Edge browser's online TTS interface in the background. It is **completely free, requires no registration, needs no configuration, has unlimited usage, and connects directly from within China**.

## Environment Dependencies

```sh
pip install edge-tts
```

No API key, account, or token is required.

## Complete List of Chinese Voices

| # | Voice ID | Name | Gender | Language/Style |
|:-:|---------|------|:----:|-----------|
| 1 | `zh-CN-XiaoxiaoNeural` | Xiaoxiao ⭐ | Female | Mandarin, warm and natural |
| 2 | `zh-CN-XiaoyiNeural` | Xiaoyi | Female | Mandarin, lively and playful |
| 3 | `zh-CN-YunxiNeural` | Yunxi | Male | Mandarin, cheerful and energetic |
| 4 | `zh-CN-YunjianNeural` | Yunjian | Male | Mandarin, passionate and powerful |
| 5 | `zh-CN-YunyangNeural` | Yunyang | Male | Mandarin, professional and reliable |
| 6 | `zh-CN-YunxiaNeural` | Yunxia | Male | Mandarin, cute and charming |
| 7 | `zh-CN-liaoning-XiaobeiNeural` | Xiaobei | Female | Northeastern Chinese, humorous and friendly |
| 8 | `zh-CN-shaanxi-XiaoniNeural` | Xiaoni | Female | Shaanxi dialect, bright and cheerful |
| 9 | `zh-HK-HiuGaaiNeural` | HiuGaai | Female | Cantonese, friendly |
|10 | `zh-HK-HiuMaanNeural` | HiuMaan | Female | Cantonese, friendly |
|11 | `zh-HK-WanLungNeural` | WanLung | Male | Cantonese, friendly |
|12 | `zh-TW-HsiaoChenNeural` | HsiaoChen | Female | Taiwan Mandarin, friendly |
|13 | `zh-TW-HsiaoYuNeural` | HsiaoYu | Female | Taiwan Mandarin, friendly |
|14 | `zh-TW-YunJheNeural` | YunJhe | Male | Taiwan Mandarin, friendly |

To view the complete list of multilingual voices, run `edge-tts --list-voices`.

## Usage

```sh
# Default voice (Xiaoxiao)
edge-tts --text "Hello, and welcome to our free text-to-speech service." --write-media /var/minis/workspace/output.mp3

# Specify a voice
edge-tts --voice zh-CN-XiaoyiNeural --text "The weather is really nice today." --write-media /var/minis/workspace/output.mp3

# Adjust speech rate and volume (percentage, -50 ~ +100)
edge-tts --voice zh-CN-XiaoxiaoNeural --rate=+20% --volume=+50% \
  --text "Welcome to today's news." --write-media /var/minis/workspace/output.mp3
```

### Parameter Description

| Parameter | Description | Default Value |
|------|------|-------|
| `--text` | Text to synthesize (required) | N/A |
| `--write-media` | Output MP3 file path (required) | N/A |
| `--voice` | Voice ID | `zh-CN-XiaoxiaoNeural` |
| `--rate` | Speech rate adjustment percentage | `0%` |
| `--volume` | Volume adjustment percentage | `0%` |
| `--pitch` | Pitch adjustment | `0Hz` |

## Output Format

Return an MP3 file link that the user can click to play, in this format:

```
![Audio](minis://workspace/free_tts_<timestamp>.mp3)
```

## Shortcuts

| User Input | Action |
|----------|------|
| "Read it" / "Read aloud" | Synthesize and play using the default voice (Xiaoxiao) |
| "Use a male voice" | Switch to YunJhe (Taiwan Mandarin male voice) |
| "Change" | Cycle to the next voice in the list |
| "Switch to a dialect" | Switch to Xiaoni (Shaanxi dialect) |
| "Switch to Cantonese" / "Speak Cantonese" | Switch to WanLung (Cantonese) |
| "Restore default" | Return to Xiaoxiao |

## Complete Workflow

1. The user requests that text be read aloud or says "Read it"
2. Determine the target voice (specified by the user or the current default)
3. Call `edge-tts` to synthesize an MP3 at `/var/minis/workspace/free_tts_<timestamp>.mp3`
4. Return an audio link for the user to play

## Notes

- **Synthesis speed**: About 1 to 2 seconds per sentence
- **Internet connection required**: Cloud-based synthesis through the Microsoft Edge TTS online interface
- **Zero cost**: No account or payment required
- **Output format**: 24 kHz, 160 kbps MP3
- English and other non-Chinese voices can also speak Chinese, but their accents are not standard, so they are not recommended.
