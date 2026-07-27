#!/usr/bin/env python3
"""子集化 Twemoji 字体（保留常用 emoji + ASCII），一次性操作"""
import os, time
from fontTools.ttLib import TTFont
from fontTools.subset import Subsetter, Options

SRC = '/usr/share/fonts/twemoji/Twemoji.ttf'
OUT = '/var/minis/skills/pdf-converter/Twemoji-subset.ttf'

# 常用 emoji 集合
EMOJIS = '''✅✨❌❎✓✔✕✖➕➖➗≠≤≥∞≈±×÷⚠️⚡
😀😃😄😁😆😅🤣😂🙂🙃😉😊😇🥰😍🤩😘😗☺😚😙🥲😋😛😜🤪😝🤑🤗🤭🤫🤔🤐🤨😐😑😶😏😒🙄😬😌😔😪🤤😴😷🤒🤕🤢🤮🤧🥵🥶🥴😵🤯🤠🥳😎🤓🧐😕😟🙁☹😮😯😲😳🥺😦😧😨😰😥😢😭😱😖😣😞😓😩😫🥱😤😡😠🤬😈👿💀☠💩🤡👹👺👻👽👾🤖
👏🙌👍👎👌✌🤞🤟🤘🤙👋🤚🖐✋🖖🙌🙏💪🦾🦿🦵🦶
🔥✨⭐🌟💫💥💢💯💦💨🎈🎉🎊🎁🏆🥇🥈🥉🏅🎖🏵🎗🎫
📍📌📎🔗🔍🔎💡🔔📣📢💬💭🗯♠♥♦♣🃏🎴🀄
🕐🕑🕒🕓🕔🕕🕖🕗🕘🕙🕚🕛⏰⏳⌛⏱⌚
🌱🌿☘🍀🎍🎋🍃🍂🍁🌾🌺🌸🌼🌻🌹🌷🥀💐
☀🌤⛅🌥☁🌦🌧⛈🌩🌨❄☃⛄☄🌪🌈🌊💧🔥
🍎🍊🍋🍌🍉🍇🍓🍈🍒🍑🥭🍍🥥🥝🍅🍆🥑🥦🥬🥒🌶🌽🥕🥔🍠🥐🥯🍞🥖🥨🧀🥚🍳🧈🥞🧇🥓🥩🍗🍖🦴🌭🍔🍟🍕🥪🥙🧆🌮🌯🥗🥘🥫🍝🍜🍲🍛🍣🍱🥟🦪🍤🍙🍚🍘🍥🥠🥮🍢🍡🍧🍨🍦🥧🧁🍰🎂🍮🍭🍬🍫🍿🍩🍪🌰🥜🍯🥛🍼☕🍵🧃🥤🍶🍺🍻🥂🍷🥃🍸🍹🧉🍾🧊🥄🍴🍽🥣🥡🥢🧂
⚽🏀🏈⚾🥎🎾🏐🏉🥏🎱🪀🏓🏸🏒🏑🥍🏏🪃🥅⛳🪁🏹🎣🤿🥊🥋🎽🛹🛼🛷⛸🥌🎿⛷🏂🪂🏋🏌🤸🤼🤽🤾🧗🚵🚴🏇
🚗🚕🚙🚌🚎🏎🚓🚑🚒🚐🚚🚛🚜🦯🦽🦼🛴🚲🛵🏍🛺🚨🚔🚍🚘🚖🚡🚠🚟🚃🚋🚞🚝🚄🚅🚈🚂🚆🚇🚊🚉✈🛫🛬🛩💺🛰🚀🛸🚁🛶⛵🚤🛥🛳⛴🚢⚓🪝⛽🚧🚦🚥🚏🗺🗿🗽🗼🏰🏯🏟🎡🎢🎠⛲⛱🏖🏝🏜🌋⛰🏔🗻🏕⛺🛖🏠🏡🏘🏚🏗🏭🏢🏬🏣🏤🏥🏦🏨🏪🏫🏩💒🏛⛪🕌🕍🛕🕋⛩🛤🛣🗾🎑🏞🌅🌄🌠🎇🎆🌇🌆🏙🌃🌌🌉🌁
🎯🔮🎮🕹🎰🎲🧩🧨🎆🎇✨🎈🎉🎊🎋🎍🎎🎏🎐🎑🧧🎀🎁🎗🎟🎫🎖🏆🏅🥇🥈🥉
⚠️⚡🔒🔓🔑🛡🔧🔨🛠⚙🧰🧲🔬🔭📡💉💊🩹🩺🧬🧪🧫🧯🔥💧🌊🌋🏔⛰🏕🗺🧭
📋📁📂🗂📅📆🗒🗓📇📈📉📊📌📍📎🖇📏📐✂️🗃🗄🔒🔓🔏🔐🔑🗝🔨🛠🔧🔩⚙️🗜⚖️🧰🧲⚗️🧪🧫🧬🔬🔭📡💉💊🩹🩺🧯🚰🚿🛁🛀🧼🧽🧴🛎🔑🚪🛋🛏🛌🧸🖼🛍🛒🎁🎈🎏🎀🎊🎉🏮🎐🧧✉📩📨📧💌📥📤📦🏷📪📫📬📭📮📯📜📃📄📑📊📈📉🗒🗓📆📅📇🗃🗄📁📂🗂🗞📰📓📔📒📕📗📘📙📚📖🔖🔗📎🖇📐📏✏️✒️🖋🖊🖌🖍📝💼🎓🎗🎙🎚🎛🧳
🌍🌎🌏🌐🗺🧭
'''.replace('\n', '')

chars = set(EMOJIS)
for i in range(32, 127):
    chars.add(chr(i))
chars_str = ''.join(sorted(c for c in chars if c not in '\n\r\t'))

print(f"Subset chars: {len(chars_str)}")
t0 = time.time()
font = TTFont(SRC)
opts = Options()
opts.drop_tables += ['DSIG']
ss = Subsetter(options=opts)
ss.populate(text=chars_str)
ss.subset(font)
os.makedirs(os.path.dirname(OUT), exist_ok=True)
font.save(OUT)
font.close()
print(f"Done: {time.time()-t0:.1f}s, {os.path.getsize(OUT)//1024}KB")
print(f"Output: {OUT}")
