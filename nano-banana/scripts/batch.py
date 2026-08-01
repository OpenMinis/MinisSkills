#!/usr/bin/env python3
"""
Nano Banana — Batch Image Generation (multiple prompts → multiple images)
Usage: Edit the TASKS list below, then run:
       python3 batch.py
"""
import os
from google import genai
from google.genai import types

client = genai.Client(api_key=os.environ["GEMINI_API_KEY"])

# ✏️ Edit this list to define your batch tasks
TASKS = [
    {
        "prompt": "a futuristic city skyline at night, neon reflections on wet streets, cinematic",
        "file": "/var/minis/attachments/batch_1.png",
        "aspect": "16:9",
        "size": "1K",
    },
    {
        "prompt": "a cozy coffee shop interior, warm lighting, wooden furniture, rainy window",
        "file": "/var/minis/attachments/batch_2.png",
        "aspect": "1:1",
        "size": "1K",
    },
]

for i, task in enumerate(TASKS):
    print(f"[{i+1}/{len(TASKS)}] Generating: {task['file']}")
    try:
        response = client.models.generate_content(
            model="gemini-3.1-flash-image-preview",
            contents=[task["prompt"]],
            config=types.GenerateContentConfig(
                response_modalities=["IMAGE"],
                image_config=types.ImageConfig(
                    aspect_ratio=task.get("aspect", "1:1"),
                    image_size=task.get("size", "1K"),
                ),
            ),
        )
        saved = False
        for part in response.candidates[0].content.parts:
            if part.inline_data is not None:
                part.as_image().save(task["file"])
                print(f"  ✅ Saved: {task['file']}")
                saved = True
            elif hasattr(part, "text") and part.text:
                print(f"  ℹ️  {part.text}")
        if not saved:
            print(f"  ❌ No image returned for task {i+1}")
    except Exception as e:
        print(f"  ❌ Error: {e}")

print("\nAll done!")
