#!/usr/bin/env python3
"""
Nano Banana — Text to Image
Usage:   python3 gen.py "prompt" [output_path] [aspect_ratio] [resolution]
Example: python3 gen.py "a panda drinking tea in a bamboo forest" /var/minis/attachments/out.png 1:1 2K

Aspect ratios: 1:1, 4:3, 3:4, 16:9, 9:16
Resolutions:   1K, 2K
"""
import os, sys
from google import genai
from google.genai import types

client = genai.Client(api_key=os.environ["GEMINI_API_KEY"])

prompt      = sys.argv[1] if len(sys.argv) > 1 else "a beautiful landscape"
output_path = sys.argv[2] if len(sys.argv) > 2 else "/var/minis/attachments/output.png"
aspect      = sys.argv[3] if len(sys.argv) > 3 else "1:1"
size        = sys.argv[4] if len(sys.argv) > 4 else "1K"

print(f"Generating: {prompt[:60]}...")
print(f"Output: {output_path} | {aspect} | {size}")

response = client.models.generate_content(
    model="gemini-3.1-flash-image-preview",
    contents=[prompt],
    config=types.GenerateContentConfig(
        response_modalities=["IMAGE"],
        image_config=types.ImageConfig(
            aspect_ratio=aspect,
            image_size=size,
        ),
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
    print("❌ No image returned. Try rephrasing the prompt.")
    sys.exit(1)
