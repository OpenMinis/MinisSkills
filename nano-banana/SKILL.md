---
name: nano-banana
description: Generate or edit images using Google Nano Banana (Gemini image generation API). Trigger this skill whenever the user asks to generate an image, draw something, create artwork, edit a photo, or mentions "nano banana", "nanobanana", or any AI image generation/editing need — even if they don't explicitly mention Nano Banana. Proactively use this skill for any image creation or transformation request.
---

# Nano Banana — Image Generation Skill

Generate or edit images locally using the Google Gemini image generation API (a.k.a. Nano Banana).

## Quick Workflow

1. Check environment (API key + dependencies)
2. Identify the mode: text-to-image / image editing / batch generation
3. Choose the right model
4. **Use the bundled scripts directly** — no need to rewrite them
5. Run the script and save output to `/var/minis/attachments/`
6. Display the result inline in the conversation

---

## Environment Setup

### Check API Key
```bash
source /etc/profile && echo $GEMINI_API_KEY | head -c 10
```

> ⚠️ Always run `source /etc/profile` first — environment variables are stored there and won't be available otherwise.

If not set, direct the user to [Google AI Studio](https://aistudio.google.com/apikey) to obtain a key, then:
```bash
echo 'export GEMINI_API_KEY="your_key_here"' >> /etc/profile
```

### Check Dependencies
```bash
pip show google-genai pillow 2>&1 | grep -E "^Name|not found"
```

If missing:
```bash
pip install google-genai pillow
```

---

## Model Selection

| Model | Model ID | Best For |
|-------|----------|----------|
| **Nano Banana 2** (recommended) | `gemini-3.1-flash-image-preview` | Fast, high quality, 2K support — default choice |
| **Nano Banana Pro** | `gemini-3-pro-image-preview` | Complex prompts, professional assets, precise text rendering |
| **Nano Banana (original)** | `gemini-2.5-flash-image` | Ultra-low latency, simple tasks |

**Default to `gemini-3.1-flash-image-preview`** unless the user explicitly requests another version.

---

## ⚠️ Known API Pitfalls

### 1. Aspect ratio / resolution config

❌ **Wrong** (old API, throws `AttributeError`):
```python
# types.ImageGenerationConfig does not exist!
image_generation_config=types.ImageGenerationConfig(aspect_ratio="16:9")
```

✅ **Correct**:
```python
config=types.GenerateContentConfig(
    response_modalities=["IMAGE"],
    image_config=types.ImageConfig(
        aspect_ratio="16:9",  # options: 1:1, 4:3, 3:4, 16:9, 9:16
        image_size="2K",      # options: 1K, 2K (default: 1K)
    ),
)
```

### 2. Environment variable loading

❌ Running `python3 script.py` directly may not have the API key  
✅ Always prefix with `source /etc/profile && python3 script.py`

### 3. Saving images

`part.as_image()` returns a PIL Image object — call `.save(path)` directly. No need to handle base64 manually.

---

## Bundled Scripts

Run any script with:
```bash
source /etc/profile && python3 <skill-path>/nano-banana/scripts/<script>.py [args]
```

---

### 📄 `gen.py` — Text to Image

```
Usage:  gen.py "prompt" [output_path] [aspect_ratio] [resolution]
Example: gen.py "a panda drinking tea in a bamboo forest" /var/minis/attachments/out.png 1:1 2K
```

---

### 📄 `edit.py` — Image Editing (image + prompt → image)

```
Usage:   edit.py <input_image> "edit instruction" [output_path]
Example: edit.py /var/minis/attachments/photo.jpg "add a wizard hat to the cat" /var/minis/attachments/edited.png
```

---

### 📄 `batch.py` — Batch Generation (multiple prompts → multiple images)

Edit the `TASKS` list at the top of the script, then run it.

---

## Step-by-Step

When the user makes an image generation request:

1. **Understand the request** — text-to-image, image editing, or batch?
2. **Check API key** — `source /etc/profile && echo $GEMINI_API_KEY | head -c 10`
3. **Verify scripts exist** — `ls <skill-path>/nano-banana/scripts/`
4. **If scripts are missing**, use `file_write` to recreate them from the source in this skill
5. **Run the appropriate script**:
   - Text-to-image: `source /etc/profile && python3 <skill-path>/nano-banana/scripts/gen.py "prompt" /var/minis/attachments/out.png 16:9 2K`
   - Image editing: `source /etc/profile && python3 <skill-path>/nano-banana/scripts/edit.py <image_path> "instruction" /var/minis/attachments/out.png`
   - Batch: edit `TASKS` in `scripts/batch.py`, then run it
6. **Display the result** — `![description](minis://attachments/out.png)`

---

## Prompt Tips

- **Describe a scene, don't just stack keywords** — "An elderly Japanese potter focused at the wheel, soft afternoon light through a studio window, photorealistic" beats "Japan pottery old man realistic"
- **Specify style explicitly** — for photography add camera details ("50mm lens, shallow depth of field"); for illustration name the style ("Ghibli-style watercolor")
- **Text in images** — spell out exactly what text should appear; the model renders it more accurately when it's explicit
- **Iterate with edit.py** — make small adjustments on an existing image rather than regenerating from scratch
- **Aspect ratio guide** — `16:9` for banners/social media, `1:1` for avatars/covers, `9:16` for phone wallpapers, `3:4` for portrait cards

---

## Troubleshooting

| Issue | Cause & Fix |
|-------|-------------|
| `AttributeError: ImageGenerationConfig` | Deprecated API — use `image_config=types.ImageConfig(...)` instead |
| `KeyError: GEMINI_API_KEY` | Run `source /etc/profile` before executing the script |
| Only text returned, no image | Ensure `response_modalities` includes `"IMAGE"` |
| Poor image quality | Switch to `gemini-3-pro-image-preview` or refine the prompt |
| Rate limit error | Free tier has limits — wait a moment and retry |
| Save fails | Confirm `/var/minis/attachments/` directory exists |

---

## References

- Official docs: https://ai.google.dev/gemini-api/docs/image-generation
- Get an API key: https://aistudio.google.com/apikey
