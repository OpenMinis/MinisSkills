---
name: web-content-extractor
description: Clean and extract the main body content from a webpage URL. Use this skill whenever the user asks to extract, scrape, or read the main article, text, or content from a webpage, especially if they mention wanting clean Markdown or text without ads and navigation.
---

# Web Content Extractor

This skill helps you extract the clean main content (body text/Markdown) from a webpage URL by using Defuddle or Jina AI's reader API.

## How it works

To extract the content of a target URL, you will prepend a specific service URL to the target URL and fetch it. This converts the messy webpage into clean Markdown containing only the main content.

### Available Services

1. **Defuddle (Default)**
   - Format: `https://defuddle.md/<target-url>`
   - Example: `https://defuddle.md/https://example.com/article`
   - Use this as the primary method.

2. **Jina AI Reader (Fallback)**
   - Format: `https://r.jina.ai/<target-url>`
   - Example: `https://r.jina.ai/https://example.com/article`
   - Use this if Defuddle fails or returns an error.

## Execution Steps

1. **Identify the target URL**: Extract the full URL the user wants to read from their request. Ensure it includes the protocol (e.g., `https://`).
2. **Construct the fetch URL**: Prepend `https://defuddle.md/` to the target URL.
3. **Fetch the content**: Use the `shell_execute` tool with `curl -sL "FETCH_URL"` to download the content.
   - Example command: `curl -sL "https://defuddle.md/https://example.com/article"`
4. **Handle Fallbacks**: If the `curl` command fails, returns empty, or returns an error message indicating failure, try the Jina AI service instead: `curl -sL "https://r.jina.ai/https://example.com/article"`
5. **Process the output**: The output will be in Markdown format.
   - If the user asked you to read it to answer a question, use the content to answer.
   - If the user asked you to extract or save it, present the Markdown to them or save it to a file as requested.

## Notes

- Always enclose the URL in quotes in the `curl` command to prevent shell interpretation of special characters like `&` or `?`.
- If the target URL is missing `http://` or `https://`, prepend `https://` before appending it to the service URL.
