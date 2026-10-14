import argparse

from PIL import Image, ImageDraw, ImageFont, features

parser = argparse.ArgumentParser()
parser.add_argument("--output", metavar="PNG", help="where to save the image")
args = parser.parse_args()

# Shaped text only: Raqm (HarfBuzz) applies the font's kerning; Pillow's basic
# layout would silently render without it.
if not features.check("raqm"):
    raise SystemExit("Pillow has no Raqm support (libraqm + fribidi); refusing to render unkerned text")

FONT_DIR = "fonts/iosevkacharon"
FONTS = {
    "regular": f"{FONT_DIR}/IosevkaCharon-Regular.ttf",
    "italic": f"{FONT_DIR}/IosevkaCharon-Italic.ttf",
    "bold": f"{FONT_DIR}/IosevkaCharon-Bold.ttf",
}

# Rendered at 2x so glyph positions and kerning land within half a pixel;
# GitHub scales the image down to the page width.
SCALE = 2


def px(value):
    return round(value * SCALE)


WIDTH, MARGIN = px(900), px(50)
TITLE_SIZE = px(32)
FONT_SIZE = px(32)
SMALL_SIZE = px(28)
LINE_HEIGHT = px(18)
WHITE = (255, 255, 255)
GRAY = (140, 140, 140)

RAQM = ImageFont.Layout.RAQM
regular = ImageFont.truetype(FONTS["regular"], FONT_SIZE, layout_engine=RAQM)
italic = ImageFont.truetype(FONTS["italic"], FONT_SIZE, layout_engine=RAQM)
bold = ImageFont.truetype(FONTS["bold"], FONT_SIZE, layout_engine=RAQM)
title = ImageFont.truetype(FONTS["regular"], TITLE_SIZE, layout_engine=RAQM)
small = ImageFont.truetype(FONTS["regular"], SMALL_SIZE, layout_engine=RAQM)


# Calculate height
def calc_height():
    y = MARGIN
    y += TITLE_SIZE + px(28)  # title line
    y += FONT_SIZE + LINE_HEIGHT  # line 1
    y += FONT_SIZE + LINE_HEIGHT  # line 2
    y += FONT_SIZE + LINE_HEIGHT  # line 3
    y += FONT_SIZE + LINE_HEIGHT  # line 4
    y += FONT_SIZE + LINE_HEIGHT  # line 5
    y += px(30) + px(25)  # gap + line + gap
    y += SMALL_SIZE + px(12)  # digits
    y += SMALL_SIZE + px(12)  # punctuation
    y += px(22) + px(25)  # gap + line + gap
    y += SMALL_SIZE + px(12)  # accents
    y += SMALL_SIZE + px(12)  # currency
    y += MARGIN
    return y


HEIGHT = calc_height()

img = Image.new("RGB", (WIDTH, HEIGHT), color=(0, 0, 0))
draw = ImageDraw.Draw(img)


def draw_line(y, segments):
    """Draw a line of runs, each advancing by its true (kerned) advance width.

    Punctuation belongs in the same run as the word before it, so the pair is kerned.
    """
    x = MARGIN
    for text, font in segments:
        draw.text((x, y), text, font=font, fill=WHITE)
        x += draw.textlength(text, font=font)
    return y + FONT_SIZE + LINE_HEIGHT


y = MARGIN

# Title line
draw.text((MARGIN, y), "Dream in type; move in pixels.", font=title, fill=WHITE)
y += TITLE_SIZE + px(40)

# Literary body text about a promised land
y = draw_line(y, [("Beyond the river lay a ", regular), ("promised land,", italic)])
y = draw_line(
    y,
    [("where ", regular), ("241 languages", bold), (" wove through the air", regular)],
)
y = draw_line(y, [("like threads of gold. Iosevka Charon carried", regular)])
y = draw_line(
    y, [("each word across the threshold; ", regular), ("every glyph", italic)]
)
y = draw_line(y, [("a vessel, every sentence a promise.", regular)])

y += px(30)
draw.line([(MARGIN, y), (WIDTH - MARGIN, y)], fill=GRAY, width=px(1))
y += px(25)

draw.text((MARGIN, y), "0123456789", font=small, fill=WHITE)
y += SMALL_SIZE + px(12)
draw.text(
    (MARGIN, y),
    "! ? . , ; : ' \" ( ) [ ] { } + - * / = @ # $ % ^ & _ ~",
    font=small,
    fill=WHITE,
)
y += SMALL_SIZE + px(12)

y += px(22)
draw.line([(MARGIN, y), (WIDTH - MARGIN, y)], fill=GRAY, width=px(1))
y += px(25)

draw.text(
    (MARGIN, y),
    "à á â ä æ ã å ā ç è é ê ë ü € £ ¥ ¢ § © ® ™ ° ¶ ↗ ↙",
    font=small,
    fill=WHITE,
)

img.save(args.output)
print("Pillow: Done - Iosevka Charon")
