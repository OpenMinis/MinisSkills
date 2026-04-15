---
name: contact-vcard-extractor
description: 从文本、聊天记录、网页、截图、名片照片、二维码/OCR结果中提取联系人信息，清洗姓名/电话/邮箱/公司/职位/地址/网站，生成 vCard/.vcf 文件，并引导用户导入 iOS 通讯录或分享给别人。触发词包括：提取联系人、保存到通讯录、生成 vCard/vcf、名片识别、从图片/截图/文本里加联系人、分享联系人、导出联系人。
---

# Contact vCard Extractor

## 目标
把用户提供的文本或图像里的联系人信息变成可预览、可导入、可分享的 `.vcf` vCard 文件。优先保证真实使用体验：先提取并让用户确认，再生成文件；不确定字段要标注，不要静默乱填。

## 典型流程
1. **接收输入**
   - 文本：直接解析用户消息、粘贴文本、网页提取结果。
   - 图像：名片照、截图、海报、聊天截图。先用 `apple-vision ocr` 识别文字；若疑似二维码，再用 `apple-vision barcode`。
   - 文件：优先检查 `/var/minis/attachments/`、`/var/minis/workspace/`、`/var/minis/mounts/`。
2. **提取字段**
   - 姓名 `FN/N`
   - 电话 `TEL`，多号码必须分成多条 `TEL`；号码字段只放号码本身，不要把“前台/手机/微信”等标签拼进号码。所有电话统一导出为 `TEL;TYPE=CELL`，用户需要时再自行改类型。标签可在摘要中显示，必要时放备注
   - 邮箱 `EMAIL`
   - 公司 `ORG`
   - 职位 `TITLE`
   - 地址 `ADR`
   - 网站 `URL`
   - 备注 `NOTE`：来源、微信号、未归类但长期有用的信息、识别不确定项。不要放临时待办/提醒/下次跟进事项
3. **用户确认**
   - 简洁列出字段，突出“可能识别错”的内容。
   - 如果姓名或电话/邮箱缺失，询问是否补充；若用户急着要，可生成“未命名联系人”。
4. **生成 vCard**
   - 使用 bundled script：`/var/minis/skills/contact-vcard-extractor/scripts/contact_to_vcard.py`
   - 输出到 `/var/minis/workspace/联系人名.vcf`，文件名需去除特殊字符；必要时用 `contact.vcf`。
5. **呈现与导入/分享**
   - 给出 Markdown 文件链接：`[导入联系人](minis://workspace/xxx.vcf)`。
   - 可用 `minis-open /var/minis/workspace/xxx.vcf` 在 App 内预览/分享。
   - 若用户明确要打开导入界面，可运行 `apple-open /var/minis/workspace/xxx.vcf` 或 `minis-open`；通常优先 `minis-open` 不离开聊天。

## 图像/OCR命令模式
```sh
apple-vision ocr /var/minis/attachments/card.jpg --lang zh-Hans,en --level accurate --compact
apple-vision barcode /var/minis/attachments/card.jpg --compact
```
将 OCR 输出保存为文本文件后调用解析脚本。

## 文本到 vCard 命令
```sh
python3 /var/minis/skills/contact-vcard-extractor/scripts/contact_to_vcard.py \
  --text-file /var/minis/workspace/contact_ocr.txt \
  --out /var/minis/workspace/contact.vcf \
  --json
```
也可通过 stdin 传入文本。不要在 shell 命令中内联很长文本；长文本先用 `file_write` 写入文件。

## 体验细节
- **临时性信息不要进联系人备注**：例如“下周二发报价单”“明天回电话”“月底跟进”等待办，应从 vCard 备注中剔除，并在回复里单独提示“是否需要我创建提醒/待办”。若用户明确同意，再用 `apple-reminders create` 创建提醒。
- **电话字段必须干净且统一 CELL**：`TEL` 只能写号码，如 `010-66668888`、`13344445555`。遇到“010-66668888（前台），手机 13344445555”要拆成两条电话；“前台/手机”只作为展示标签或备注，不附加到号码后面。导出时所有电话都用 `TEL;TYPE=CELL`，不要写 `VOICE/HOME/WORK` 等类型，除非用户明确指定。
- **不要直接导入通讯录**，除非用户明确确认；先生成 vcf 并让用户点开确认。
- **隐私提醒要轻量**：联系人属于个人信息；只在分享/批量处理时提醒用户确认授权与内容。
- **多联系人**：如果文本/图片明显包含多人，分别生成多个 `.vcf`，或合并成一个包含多张 vCard 的 `contacts.vcf`。最终用表格列出每个人。
- **二维码**：若二维码内容是 `MECARD:`、`BEGIN:VCARD`、`tel:`、`mailto:`、微信/网址，按内容解析；vCard 原文可直接保存为 `.vcf`，MECARD 需转换。
- **中文姓名**：vCard `N` 字段可按首字为姓、余下为名；不确定时 `FN` 优先保证显示正确。
- **国际号码**：保留 `+国家码`、分机、空格，不要强行改写。
- **文件命名**：优先 `姓名.vcf`；姓名为空用 `contact-YYYYMMDD-HHMM.vcf`。
- **最终回复格式**：
  1. 一句话说明已生成。
  2. 字段摘要。
  3. 文件链接。
  4. “点开后可添加到通讯录，也可以用分享按钮发给别人。”

## 示例回复
已整理好这张名片啦：

| 字段 | 内容 |
|---|---|
| 姓名 | 张三 |
| 电话 | +86 138 0000 0000 |
| 邮箱 | zhangsan@example.com |
| 公司 | 示例科技 |

[导入/分享联系人](minis://workspace/%E5%BC%A0%E4%B8%89.vcf)

点开后可以添加到通讯录，也能直接分享给别人。

## bundled script 说明
`contact_to_vcard.py` 会做基础规则抽取与 vCard 转义。它不是唯一方式：复杂、低质量 OCR 或排版混乱时，应结合模型判断手动修正字段，再生成 vCard。
