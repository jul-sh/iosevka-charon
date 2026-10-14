import argparse

from PIL import Image, ImageDraw, ImageFont

parser = argparse.ArgumentParser()
parser.add_argument("--output", metavar="PNG", help="where to save the image")
args = parser.parse_args()

FONTS = {
    "regular": "fonts/iosevkacaleuche/IosevkaCaleuche-Regular.ttf",
    "italic": "fonts/iosevkacaleuche/IosevkaCaleuche-Italic.ttf",
    "bold": "fonts/iosevkacaleuche/IosevkaCaleuche-Bold.ttf",
    "mono": "fonts/iosevkacaleuchemono/IosevkaCaleucheMono-Regular.ttf",
}

WIDTH, MARGIN = 900, 50
TITLE_SIZE = 32
FONT_SIZE = 32
SMALL_SIZE = 28
LINE_HEIGHT = 18
WHITE = (255, 255, 255)
GRAY = (140, 140, 140)
TEAL = (78, 201, 162)

RAQM = ImageFont.Layout.RAQM
regular = ImageFont.truetype(FONTS["regular"], FONT_SIZE, layout_engine=RAQM)
italic = ImageFont.truetype(FONTS["italic"], FONT_SIZE, layout_engine=RAQM)
bold = ImageFont.truetype(FONTS["bold"], FONT_SIZE, layout_engine=RAQM)
title = ImageFont.truetype(FONTS["regular"], TITLE_SIZE, layout_engine=RAQM)
mono = ImageFont.truetype(FONTS["mono"], SMALL_SIZE, layout_engine=RAQM)
small = ImageFont.truetype(FONTS["regular"], SMALL_SIZE, layout_engine=RAQM)


# Calculate height
def calc_height():
    y = MARGIN
    y += TITLE_SIZE + 40  # title line
    y += (FONT_SIZE + LINE_HEIGHT) * 4  # prose
    y += 30 + 25  # gap + line + gap
    y += (SMALL_SIZE + 12) * 3  # code, in Iosevka Caleuche Mono
    y += 22 + 25  # gap + line + gap
    y += SMALL_SIZE + 12  # digits
    y += SMALL_SIZE + 12  # punctuation
    y += MARGIN
    return y


HEIGHT = calc_height()

img = Image.new("RGB", (WIDTH, HEIGHT), color=(0, 0, 0))
draw = ImageDraw.Draw(img)


def draw_line(y, segments, advance=FONT_SIZE + LINE_HEIGHT):
    x = MARGIN
    for text, font, *color in segments:
        draw.text((x, y), text, font=font, fill=color[0] if color else WHITE)
        bbox = draw.textbbox((x, y), text, font=font)
        x = bbox[2]
    return y + advance


y = MARGIN

# Title line
draw.text((MARGIN, y), "A ship of lights on a quiet sea.", font=title, fill=WHITE)
y += TITLE_SIZE + 40

# The Caleuche of Chiloé, and the pairing with Kerberos
y = draw_line(y, [("Off Chiloé, on still nights, the ", regular), ("Caleuche", italic), (" sails out lit", regular)])
y = draw_line(y, [("like a festival, gathering those the sea has kept.", regular)])
y = draw_line(y, [("Iosevka Caleuche", bold), (" sails beside ", regular), ("Kerberos", italic), (" the same way,", regular)])
y = draw_line(y, [("with its x-height, its colour and its line.", regular)])

y += 30
draw.line([(MARGIN, y), (WIDTH - MARGIN, y)], fill=GRAY, width=1)
y += 25

code = SMALL_SIZE + 12
y = draw_line(y, [("buf = hb.Buffer()", mono)], code)
y = draw_line(y, [("buf.add_str(", mono), ('"Kerberos 1879"', mono, TEAL), (")", mono)], code)
y = draw_line(y, [("hb.shape(font, buf, {", mono), ('"onum"', mono, TEAL), (": True})", mono)], code)

y += 22
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

img.save(args.output)
print("Pillow: Done - Iosevka Caleuche")
