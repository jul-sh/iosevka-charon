import argparse

from PIL import Image, ImageDraw, ImageFont

parser = argparse.ArgumentParser()
parser.add_argument("--output", metavar="PNG", help="where to save the image")
parser.add_argument("--font-dir", default="fonts/iosevkacharon", help="font directory to use")
args = parser.parse_args()

FONT_DIR = args.font_dir
FONTS = {
    "regular": f"{FONT_DIR}/IosevkaCharon-Regular.ttf",
    "italic": f"{FONT_DIR}/IosevkaCharon-Italic.ttf",
    "bold": f"{FONT_DIR}/IosevkaCharon-Bold.ttf",
}

WIDTH, MARGIN = 1200, 50
TITLE_SIZE = 36
FONT_SIZE = 28
LINE_HEIGHT = 12
WHITE = (255, 255, 255)
GRAY = (140, 140, 140)

regular = ImageFont.truetype(FONTS["regular"], FONT_SIZE)
bold = ImageFont.truetype(FONTS["bold"], FONT_SIZE)
title = ImageFont.truetype(FONTS["bold"], TITLE_SIZE)

# Multilingual test text
multilingual_text = [
    "WIRIOÙ СНЕЖНЯ Арганізацыі Абʼяднаных правоў «яе тэрыторый».",
    "ГЕНЕРАЛЬНАЯ үйелменінің құқықтарының лынбайтындығын Ұлттар Әр",
    "Құлдық Өзінің Ҳар kǎ bɔŋɔ̌ kǒ nüxü̃́ ӷавргуйныр̌кир̌ phẩm jǐ Nǔ Åtta",
    "өрэхтээһин éyaltai{ab Enyiń mpɔ̂ Það juisɨ̱kio malɇ Ṱhalutshezo",
]


# Calculate height
def calc_height():
    y = MARGIN
    y += TITLE_SIZE + 40  # title line + gap
    y += (FONT_SIZE + LINE_HEIGHT) * len(multilingual_text)  # text lines
    y += MARGIN
    return y


HEIGHT = calc_height()

img = Image.new("RGB", (WIDTH, HEIGHT), color=(0, 0, 0))
draw = ImageDraw.Draw(img)

y = MARGIN

# Title line
draw.text((MARGIN, y), "Multilingual Character Support Test", font=title, fill=WHITE)
y += TITLE_SIZE + 40

# Draw each line of multilingual text
for line in multilingual_text:
    draw.text((MARGIN, y), line, font=regular, fill=WHITE)
    y += FONT_SIZE + LINE_HEIGHT

img.save(args.output)
print(f"Multilingual test image saved to {args.output}")
