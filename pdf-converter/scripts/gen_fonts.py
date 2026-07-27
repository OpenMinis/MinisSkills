#!/usr/bin/env python3
"""预生成常用中文+符号的字体子集（一次性，后续复用）

生成 GB2312 一级汉字（3755字）+ ASCII + 常用符号的子集字体。
后续转 PDF 时直接复用，不再每次做 fontTools subset（CJK subset 太慢）。
"""
import os, sys, time

REG_TTC = '/usr/share/fonts/noto/NotoSansCJK-Regular.ttc'
BLD_TTC = '/usr/share/fonts/noto/NotoSansCJK-Bold.ttc'
EMOJI_SRC = '/usr/share/fonts/twemoji/Twemoji.ttf'

OUT_DIR = '/var/minis/skills/pdf-converter/fonts'
REG_OUT = os.path.join(OUT_DIR, 'NotoSansSC-Regular-subset.ttf')
BLD_OUT = os.path.join(OUT_DIR, 'NotoSansSC-Bold-subset.ttf')
EMOJI_OUT = os.path.join(OUT_DIR, 'Twemoji-subset.ttf')


def gen_common_chars():
    """生成常用字符集：GB2312 一级汉字 + ASCII + 常用符号 + 常见 emoji"""
    chars = set()
    # ASCII
    for i in range(32, 127):
        chars.add(chr(i))
    # GB2312 一级汉字（常用 3755 字，U+4E00 区附近）
    # 通过 GB2312 编码范围生成
    for high in range(0xB0, 0xF8):       # 一级汉字区
        for low in range(0xA1, 0xFF):
            try:
                b = bytes([high, low])
                c = b.decode('gb2312')
                chars.add(c)
            except:
                pass
    # 全角标点
    for c in '、。，！？：；“”‘’（）【】《》—…·～　':
        chars.add(c)
    # 常用特殊符号
    for c in '¥℃°①②③④⑤⑥⑦⑧⑨⑩©®™•●○◎■□▲△▼▽◆◇★☆※→←↑↓↔⇒♪♫§¶†‡':
        chars.add(c)
    # 常见 emoji（文档中常用）
    emoji_str = (
        '✅✨❌❎✓✔✕✖➕➖➗≠≤≥∞≈±×÷'
        '😀😃😄😁😆😅🤣😂🙂🙃😉😊😇🥰😍🤩😘😗☺😚😙'
        '🥲😋😛😜🤪😝🤑🤗🤭🤫🤔🤐🤨😐😑😶😏😒🙄😬'
        '😌😔😪🤤😴😷🤒🤕🤢🤮🤧🥵🥶🥴😵🤯🤠🥳😎🤓🧐'
        '😕😟🙁☹😮😯😲😳🥺😦😧😨😰😥😢😭😱😖😣😞😓😩😫🥱'
        '😤😡😠🤬😈👿💀☠💩🤡👹👺👻👽👾🤖'
        '👏🙌👍👎👌✌🤞🤟🤘🤙👋🤚🖐✋🖖🙌🙏💪🦾🦿🦵🦶'
        '🔥✨⭐🌟💫💥💢💯💦💨🎈🎉🎊🎁🏆🥇🥈🥉🏅🎖🏵🎗🎫'
        '📍📌📎🔗🔍🔎💡🔔📣📢💬💭🗯♠♥♦♣🃏🎴🀄'
        '🕐🕑🕒🕓🕔🕕🕖🕗🕘🕙🕚🕛⏰⏳⌛⏱⌚'
        '🌱🌿☘🍀🎍🎋🍃🍂🍁🌾🌺🌸🌼🌻🌹🌷🥀💐'
        '☀🌤⛅🌥☁🌦🌧⛈🌩🌨❄☃⛄☄🌪🌈🌊💧🔥'
        '🍎🍊🍋🍌🍉🍇🍓🍈🍒🍑🥭🍍🥥🥝🍅🍆🥑🥦🥬🥒🌶🌽🥕🥔🍠🥐🥯🍞🥖🥨🧀🥚🍳🧈🥞🧇🥓🥩🍗🍖🦴🌭🍔🍟🍕🥪🥙🧆🌮🌯🥗🥘🥫🍝🍜🍲🍛🍣🍱🥟🦪🍤🍙🍚🍘🍥🥠🥮🍢🍡🍧🍨🍦🥧🧁🍰🎂🍮🍭🍬🍫🍿🍩🍪🌰🥜🍯🥛🍼☕🍵🧃🥤🍶🍺🍻🥂🍷🥃🍸🍹🧉🍾🧊🥄🍴🍽🥣🥡🥢🧂'
        '⚽🏀🏈⚾🥎🎾🏐🏉🥏🎱🪀🏓🏸🏒🏑🥍🏏🪃🥅⛳🪁🏹🎣🤿🥊🥋🎽🛹🛼🛷⛸🥌🎿⛷🏂🪂🏋🏌🤸🤼🤽🤾🧗🚵🚴🏇🏌️🏂🏄🚣🏊🤽⛹🏋🚴🚵🤸🤼'
        '🚗🚕🚙🚌🚎🏎🚓🚑🚒🚐🚚🚛🚜🦯🦽🦼🛴🚲🛵🏍🛺🚨🚔🚍🚘🚖🚡🚠🚟🚃🚋🚞🚝🚄🚅🚈🚂🚆🚇🚊🚉✈🛫🛬🛩💺🛰🚀🛸🚁🛶⛵🚤🛥🛳⛴🚢⚓🪝⛽🚧🚦🚥🚏🗺🗿🗽🗼🏰🏯🏟🎡🎢🎠⛲⛱🏖🏝🏜🌋⛰🏔🗻🏕⛺🛖🏠🏡🏘🏚🏗🏭🏢🏬🏣🏤🏥🏦🏨🏪🏫🏩💒🏛⛪🕌🕍🛕🕋⛩🛤🛣🗾🎑🏞🌅🌄🌠🎇🎆🌇🌆🏙🌃🌌🌉🌁⌛⏳⌚⏰⏱⏲🕰'
        '🌡☀️☁️⛅🌦🌧⛈🌩🌨❄️☃️⛄️🌬💨💧💦☔️☂️🌊🌫'
        '🎯🔮🎮🕹🎰🎲🧩🧨🧨🎆🎇✨🎈🎉🎊🎋🎍🎎🎏🎐🎑🧧🎀🎁🎗🎟🎫🎖🏆🏅🥇🥈🥉⚽🏀🏈⚾🥎🎾🏐🏉🥏🎱🪀🏓🏸🏒🏑🥍🏏🪃🥅⛳🪁🏹🎣🤿🥊🥋🎽🛹🛼🛷⛸🥌🎿⛷🏂🪂🏋🏌🤸🤼🤽🤾🧗🚵🚴🏇'
        '⚠️⚡🔒🔓🔑🛡🔧🔨🛠⚙🧰🧲🔬🔭📡💉💊🩹🩺🧬🧪🧫🧯🔥💧🌊🌋🏔⛰️🏕🗺🧭'
        '📋📁📂🗂📅📆🗒🗓📇📈📉📊📌📍📎🖇📏📐✂️🗃🗄🔒🔓🔏🔐🔑🗝🔨🛠🔧🔩⚙️🗜⚖️🧰🧲⚗️🧪🧫🧬🔬🔭📡💉💊🩹🩺🧯🚰🚿🛁🛀🧼🧽🧴🛎🔑🚪🛋🛏🛌🧸🖼🛍🛒🎁🎈🎏🎀🎊🎉🏮🎐🧧✉📩📨📧💌📥📤📦🏷📪📫📬📭📮📯📜📃📄📑📊📈📉🗒🗓📆📅📇🗃🗄📁📂🗂🗞📰📓📔📒📕📗📘📙📚📖🔖🔗📎🖇📐📏✏️✒️ ink🖋🖊🖌🖍📝💼🎓🎗🎙🎚🎛🧳'
    )
    for c in emoji_str:
        chars.add(c)
    return ''.join(sorted(c for c in chars if c not in '\n\r\t'))


def subset_font_to_file(src, font_index, chars, out_path):
    """子集化字体到文件"""
    from fontTools.ttLib import TTFont
    from fontTools.subset import Subsetter, Options
    font = TTFont(src, fontNumber=font_index) if font_index >= 0 else TTFont(src)
    opts = Options()
    opts.drop_tables += ['DSIG']
    opts.name_IDs = ['*']
    opts.notdef_outline = True
    ss = Subsetter(options=opts)
    ss.populate(text=chars)
    ss.subset(font)
    font.save(out_path)
    font.close()
    return os.path.getsize(out_path)


def main():
    os.makedirs(OUT_DIR, exist_ok=True)
    chars = gen_common_chars()
    print(f"字符集: {len(chars)} 个字符")

    tasks = [
        (REG_TTC, 2, REG_OUT, 'SC Regular'),
        (BLD_TTC, 2, BLD_OUT, 'SC Bold'),
        (EMOJI_SRC, -1, EMOJI_OUT, 'Twemoji'),
    ]
    for src, idx, out, name in tasks:
        if os.path.exists(out):
            print(f"  ✅ {name}: 已存在 ({os.path.getsize(out)/1024:.0f}KB)，跳过")
            continue
        t0 = time.time()
        print(f"  生成 {name}...", flush=True)
        try:
            sz = subset_font_to_file(src, idx, chars, out)
            print(f"  ✅ {name}: {sz/1024:.0f}KB ({time.time()-t0:.0f}s)")
        except Exception as e:
            print(f"  ❌ {name} 失败: {e}")

    print(f"\n字体目录: {OUT_DIR}")
    for f in os.listdir(OUT_DIR):
        print(f"  {f}: {os.path.getsize(os.path.join(OUT_DIR, f))/1024:.0f}KB")


if __name__ == '__main__':
    main()
