import argparse

from PIL import Image, ImageDraw, ImageFont

parser = argparse.ArgumentParser()
parser.add_argument("--output", metavar="PNG", help="where to save the image")
args = parser.parse_args()

FONT_DIR = "fonts/iosevkacharon"
FONTS = {
    "regular": f"{FONT_DIR}/IosevkaCharon-Regular.ttf",
    "italic": f"{FONT_DIR}/IosevkaCharon-Italic.ttf",
    "bold": f"{FONT_DIR}/IosevkaCharon-Bold.ttf",
}

WIDTH, MARGIN = 900, 50
TITLE_SIZE = 32
FONT_SIZE = 32
SMALL_SIZE = 28
LINE_HEIGHT = 18
WHITE = (255, 255, 255)
GRAY = (140, 140, 140)

regular = ImageFont.truetype(FONTS["regular"], FONT_SIZE)
italic = ImageFont.truetype(FONTS["italic"], FONT_SIZE)
bold = ImageFont.truetype(FONTS["bold"], FONT_SIZE)
title = ImageFont.truetype(FONTS["regular"], TITLE_SIZE)
small = ImageFont.truetype(FONTS["regular"], SMALL_SIZE)


# Calculate height
def calc_height():
    y = MARGIN
    y += TITLE_SIZE + 28  # title line
    y += FONT_SIZE + LINE_HEIGHT  # line 1
    y += FONT_SIZE + LINE_HEIGHT  # line 2
    y += FONT_SIZE + LINE_HEIGHT  # line 3
    y += FONT_SIZE + LINE_HEIGHT  # line 4
    y += FONT_SIZE + LINE_HEIGHT  # line 5
    y += 30 + 25  # gap + line + gap
    y += SMALL_SIZE + 12  # digits
    y += SMALL_SIZE + 12  # punctuation
    y += 22 + 25  # gap + line + gap
    y += SMALL_SIZE + 12  # accents
    y += SMALL_SIZE + 12  # currency
    y += MARGIN
    return y


HEIGHT = calc_height()

img = Image.new("RGB", (WIDTH, HEIGHT), color=(0, 0, 0))
draw = ImageDraw.Draw(img)


def draw_line(y, segments):
    x = MARGIN
    for text, font in segments:
        draw.text((x, y), text, font=font, fill=WHITE)
        bbox = draw.textbbox((x, y), text, font=font)
        x = bbox[2]
    return y + FONT_SIZE + LINE_HEIGHT


y = MARGIN

# Title line
draw.text((MARGIN, y), "Dream in type; move in pixels.", font=title, fill=WHITE)
y += TITLE_SIZE + 40

# Literary body text about a promised land
y = draw_line(
    y, [("Beyond the river lay a ", regular), ("promised land", italic), (",", regular)]
)
y = draw_line(
    y,
    [("where ", regular), ("241 languages", bold), (" wove through the air", regular)],
)
y = draw_line(y, [("like threads of gold. Iosevka Charon carried", regular)])
y = draw_line(
    y, [("each word across the threshold; ", regular), ("every glyph", italic)]
)
y = draw_line(y, [("a vessel, every sentence a promise.", regular)])

y += 30
draw.line([(MARGIN, y), (WIDTH - MARGIN, y)], fill=GRAY, width=1)
y += 25

draw.text((MARGIN, y), "0123456789", font=small, fill=WHITE)
y += SMALL_SIZE + 12
draw.text(
    (MARGIN, y),
    "! ? . , ; : ' \" ( ) [ ] { } + - * / = @ # $ % ^ & _ ~",
    font=small,
    fill=WHITE,
)
y += SMALL_SIZE + 12

y += 22
draw.line([(MARGIN, y), (WIDTH - MARGIN, y)], fill=GRAY, width=1)
y += 25

draw.text(
    (MARGIN, y),
    "à á â ä æ ã å ā ç è é ê ë ü € £ ¥ ¢ § © ® ™ ° ¶ ↗ ↙",
    font=small,
    fill=WHITE,
)

img.save(args.output)
print("Pillow: Done - Iosevka Charon")
