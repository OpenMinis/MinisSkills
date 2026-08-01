#!/usr/bin/env python3
"""
Nano Banana — Image Editing (image + prompt → image)
Usage:   python3 edit.py <input_image> "edit instruction" [output_path]
Example: python3 edit.py /var/minis/attachments/photo.jpg "add a wizard hat to the cat" /var/minis/attachments/edited.png
"""
import os, sys
from google import genai
from google.genai import types

client = genai.Client(api_key=os.environ["GEMINI_API_KEY"])

if len(sys.argv) < 3:
    print("Usage: edit.py <input_image> <prompt> [output_path]")
    sys.exit(1)

input_path  = sys.argv[1]
edit_prompt = sys.argv[2]
output_path = sys.argv[3] if len(sys.argv) > 3 else "/var/minis/attachments/edited.png"

ext = input_path.lower().rsplit(".", 1)[-1]
mime_map = {"jpg": "image/jpeg", "jpeg": "image/jpeg", "png": "image/png", "webp": "image/webp"}
mime_type = mime_map.get(ext, "image/jpeg")

with open(input_path, "rb") as f:
    image_bytes = f.read()

print(f"Editing: {input_path}")
print(f"Instruction: {edit_prompt[:60]}...")

response = client.models.generate_content(
    model="gemini-3.1-flash-image-preview",
    contents=[
        types.Part.from_bytes(data=image_bytes, mime_type=mime_type),
        edit_prompt,
    ],
    config=types.GenerateContentConfig(
        response_modalities=["IMAGE", "TEXT"],
    ),
)

saved = False
for part in response.candidates[0].content.parts:
    if part.inline_data is not None:
        part.as_image().save(output_path)
        print(f"✅ Saved: {output_path}")
        saved = True
    elif hasattr(part, "text") and part.text:
        print(f"ℹ️  Model: {part.text}")

if not saved:
    print("❌ No image returned.")
    sys.exit(1)
