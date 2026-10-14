import argparse

from PIL import Image, ImageDraw, ImageFont, features

parser = argparse.ArgumentParser()
parser.add_argument("--output", metavar="PNG", help="where to save the image")
args = parser.parse_args()

# Shaped text only: Raqm (HarfBuzz) applies the fonts' kerning; Pillow's basic
# layout would silently render without it.
if not features.check("raqm"):
    raise SystemExit("Pillow has no Raqm support (libraqm + fribidi); refusing to render unkerned text")

FONT_DIR = "fonts/iosevkacaleuche"
WEIGHTS = ["Light", "Regular", "Medium", "SemiBold", "Bold"]

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


def face(style, size=FONT_SIZE):
    return ImageFont.truetype(f"{FONT_DIR}/IosevkaCaleuche-{style}.ttf", size, layout_engine=RAQM)


regular, italic, bold = face("Regular"), face("Italic"), face("Bold")
title, small = face("Regular", TITLE_SIZE), face("Regular", SMALL_SIZE)
upright_ladder = [face(w, SMALL_SIZE) for w in WEIGHTS]
italic_ladder = [face("Italic" if w == "Regular" else f"{w}Italic", SMALL_SIZE) for w in WEIGHTS]


# Calculate height
def calc_height():
    y = MARGIN
    y += TITLE_SIZE + px(40)  # title line
    y += (FONT_SIZE + LINE_HEIGHT) * 4  # prose
    y += px(30) + px(25)  # gap + line + gap
    y += (SMALL_SIZE + px(12)) * 2  # weights, upright and italic
    y += px(22) + px(25)  # gap + line + gap
    y += SMALL_SIZE + px(12)  # digits
    y += SMALL_SIZE + px(12)  # punctuation
    y += MARGIN
    return y


HEIGHT = calc_height()

img = Image.new("RGB", (WIDTH, HEIGHT), color=(0, 0, 0))
draw = ImageDraw.Draw(img)


def draw_line(y, segments, advance=FONT_SIZE + LINE_HEIGHT):
    """Draw a line of runs, each advancing by its true (kerned) advance width.

    Punctuation belongs in the same run as the word before it, so the pair is kerned.
    """
    x = MARGIN
    for text, font, *color in segments:
        draw.text((x, y), text, font=font, fill=color[0] if color else WHITE)
        x += draw.textlength(text, font=font)
    return y + advance


y = MARGIN

# Title line
draw.text((MARGIN, y), "A ship of lights on a quiet sea.", font=title, fill=WHITE)
y += TITLE_SIZE + px(40)

# The Caleuche of Chiloé, and the pairing with Kerberos
y = draw_line(y, [("Off Chiloé, on still nights, the ", regular), ("Caleuche", italic), (" sails out lit", regular)])
y = draw_line(y, [("like a festival, gathering those the sea has kept.", regular)])
y = draw_line(y, [("Iosevka Caleuche", bold), (" sails beside ", regular), ("Kerberos", italic), (" the same way,", regular)])
y = draw_line(y, [("with its x-height, its colour and its line.", regular)])

y += px(30)
draw.line([(MARGIN, y), (WIDTH - MARGIN, y)], fill=GRAY, width=px(1))
y += px(25)

# Every weight, upright and italic
ladder = SMALL_SIZE + px(12)
y = draw_line(y, [(f"{w}  ", f) for w, f in zip(WEIGHTS, upright_ladder)], ladder)
y = draw_line(y, [(f"{w}  ", f) for w, f in zip(WEIGHTS, italic_ladder)], ladder)

y += px(22)
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

img.save(args.output)
print("Pillow: Done - Iosevka Caleuche")
