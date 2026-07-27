---
name: contact-vcard-extractor
description: Extract contact information from text, chat logs, web pages, screenshots, business card photos, and QR codes/OCR results; clean names, phone numbers, email addresses, companies, job titles, addresses, and websites; generate vCard/.vcf files; and guide users to import them into iOS Contacts or share them with others. Trigger words include: extract contacts, save to contacts, generate vCard/.vcf, business card recognition, add contacts from images/screenshots/text, share contacts, and export contacts.
---

# Contact vCard Extractor

## Objective
Convert contact information from user-provided text or images into previewable, importable, and shareable `.vcf` vCard files. Prioritize the real user experience: extract the data and have the user confirm it before generating the file. Mark any uncertain fields and do not silently fill in guesses.

## Typical Workflow
1. **Receive Input**
   - Text: Directly parse user messages, pasted text, or results extracted from web pages.
   - Images: Business card photos, screenshots, posters, or chat screenshots. First use `apple-vision ocr` to recognize text. If it appears to contain a QR code, use `apple-vision barcode`.
   - Files: First check `/var/minis/attachments/`, `/var/minis/workspace/`, and `/var/minis/mounts/`.
2. **Extract Fields**
   - Name `FN/N`
   - Phone `TEL`: Multiple numbers must be split into separate `TEL` entries. The number field should contain only the number itself. Do not append labels such as "front desk," "mobile," or "WeChat" to the number. Export all phone numbers uniformly as `TEL;TYPE=CELL`; users can change the type themselves if needed. Labels can be shown in the summary and, if necessary, placed in notes.
   - Email `EMAIL`
   - Company `ORG`
   - Job title `TITLE`
   - Address `ADR`
   - Website `URL`
   - Notes `NOTE`: Source, WeChat ID, uncategorized but long-term useful information, and uncertain recognition items. Do not include temporary to-dos, reminders, or next follow-up items.
3. **User Confirmation**
   - List the fields concisely and highlight content that may have been recognized incorrectly.
   - If the name or phone/email is missing, ask whether the user wants to add it. If the user is in a hurry, generate an "Unnamed Contact."
4. **Generate vCard**
   - Use the bundled script: `/var/minis/skills/contact-vcard-extractor/scripts/contact_to_vcard.py`
   - Output to `/var/minis/workspace/Contact Name.vcf`. Remove special characters from the file name. If necessary, use `contact.vcf`.
5. **Present and Import/Share**
   - Provide a Markdown file link: `[Import Contact](minis://workspace/xxx.vcf)`.
   - Use `minis-open /var/minis/workspace/xxx.vcf` to preview/share within the app.
   - If the user explicitly wants to open the import screen, run `apple-open /var/minis/workspace/xxx.vcf` or `minis-open`. Usually, prefer `minis-open` to stay in the chat.

## Image/OCR Command Pattern
```sh
apple-vision ocr /var/minis/attachments/card.jpg --lang zh-Hans,en --level accurate --compact
apple-vision barcode /var/minis/attachments/card.jpg --compact
```
After saving the OCR output as a text file, run the parsing script.

## Text-to-vCard Command
```sh
python3 /var/minis/skills/contact-vcard-extractor/scripts/contact_to_vcard.py \
  --text-file /var/minis/workspace/contact_ocr.txt \
  --out /var/minis/workspace/contact.vcf \
  --json
```
Text can also be passed via stdin. Do not inline very long text in shell commands; for long text, first use `file_write` to write it to a file.

## User Experience Details
- **Do not include temporary information in contact notes**: For example, to-dos such as "Send a quote next Tuesday," "Call back tomorrow," or "Follow up at the end of the month" should be removed from the vCard notes. In the reply, separately ask, "Would you like me to create a reminder or to-do item?" If the user explicitly agrees, use `apple-reminders create` to create the reminder.
- **Phone fields must be clean and consistently CELL**: `TEL` may contain only numbers, such as `010-66668888` or `13344445555`. For "010-66668888 (front desk), mobile 13344445555," split it into two phone entries. Use "front desk/mobile" only as display labels or notes, and do not append them to the number. When exporting, use `TEL;TYPE=CELL` for all phone numbers. Do not write types such as `VOICE/HOME/WORK` unless the user explicitly specifies them.
- **Do not import directly into Contacts** unless the user explicitly confirms. First generate the vcf and have the user open it to confirm.
- **Keep privacy prompts lightweight**: Contacts are personal information. Remind users to confirm authorization and content only when sharing or processing in batches.
- **Multiple contacts**: If the text or image clearly contains multiple people, generate separate `.vcf` files, or merge them into one `contacts.vcf` file containing multiple vCards. Finally, list each person in a table.
- **QR codes**: If the QR code content is `MECARD:`, `BEGIN:VCARD`, `tel:`, `mailto:`, WeChat, or a URL, parse it according to the content. Raw vCard content can be saved directly as `.vcf`; MECARD must be converted.
- **Chinese names**: The vCard `N` field can use the first character as the family name and the remaining characters as the given name. If uncertain, prioritize correct display in `FN`.
- **International numbers**: Preserve `+Country Code`, extensions, and spaces. Do not forcefully rewrite them.
- **File naming**: Prefer `Name.vcf`; if the name is empty, use `contact-YYYYMMDD-HHMM.vcf`.
- **Final reply format**:
  1. A one-sentence confirmation that it has been generated.
  2. A summary of the fields.
  3. A link to the file.
  4. "Tap it to add it to Contacts, or use the share button to send it to someone else."

## Sample Reply
I’ve organized this business card:

| Field | Content |
|---|---|
| Name | Zhang San |
| Phone | +86 138 0000 0000 |
| Email | zhangsan@example.com |
| Company | Example Tech |

[Import/Share Contact](minis://workspace/%E5%BC%A0%E4%B8%89.vcf)

After opening it, you can add it to Contacts or share it directly with someone else.

## Bundled Script Notes
`contact_to_vcard.py` performs basic rule-based extraction and vCard escaping. It is not the only method: for complex input, low-quality OCR, or messy layouts, use model judgment to manually correct the fields before generating the vCard.
