import argparse

from PIL import Image, ImageDraw, ImageFont

parser = argparse.ArgumentParser()
parser.add_argument("--output", metavar="PNG", help="where to save the image")
args = parser.parse_args()

FONT_DIR = "fonts/iosevkacharonmono"
FONTS = {
    "regular": f"{FONT_DIR}/IosevkaCharonMono-Regular.ttf",
    "bold": f"{FONT_DIR}/IosevkaCharonMono-Bold.ttf",
}

WIDTH, MARGIN = 900, 50
FONT_SIZE = 28
SMALL_SIZE = 24

# Brighter colors
BG = (23, 23, 23)  # #171717
WHITE = (255, 255, 255)
GRAY = (180, 180, 180)  # brighter gray
BLUE = (86, 156, 214)  # brighter blue
RED = (255, 100, 100)  # brighter red
ORANGE = (206, 145, 80)  # brighter orange
TEAL = (78, 201, 162)  # brighter teal

regular = ImageFont.truetype(FONTS["regular"], FONT_SIZE)
bold = ImageFont.truetype(FONTS["bold"], FONT_SIZE)
small = ImageFont.truetype(FONTS["regular"], SMALL_SIZE)


# Calculate height
def calc_height():
    y = MARGIN
    y += FONT_SIZE + 8  # def hello
    y += FONT_SIZE + 8  # msg = "...
    y += FONT_SIZE + 8  # continuation
    y += FONT_SIZE + 8  # print
    y += FONT_SIZE + 8  # blank
    y += FONT_SIZE + 8  # if
    y += FONT_SIZE + 8  # hello()
    y += 25 + 20  # gap + line + gap
    y += SMALL_SIZE + 6  # ABC
    y += SMALL_SIZE + 6  # abc
    y += SMALL_SIZE + 6  # disambiguation
    y += 20 + 20  # gap + line + gap
    y += SMALL_SIZE + 6  # operators
    y += SMALL_SIZE + 6  # box drawing
    y += MARGIN
    return y


HEIGHT = calc_height()

img = Image.new("RGB", (WIDTH, HEIGHT), color=BG)
draw = ImageDraw.Draw(img)


def draw_code_line(y, segments):
    x = MARGIN
    for text, color in segments:
        draw.text((x, y), text, font=regular, fill=color)
        bbox = draw.textbbox((x, y), text, font=regular)
        x = bbox[2]
    return y + FONT_SIZE + 8


def draw_code_bold(y, segments):
    x = MARGIN
    for text, color, is_bold in segments:
        font = bold if is_bold else regular
        draw.text((x, y), text, font=font, fill=color)
        bbox = draw.textbbox((x, y), text, font=font)
        x = bbox[2]
    return y + FONT_SIZE + 8


y = MARGIN

# def hello() -> None:
y = draw_code_bold(
    y,
    [
        ("def", BLUE, True),
        (" ", GRAY, False),
        ("hello", RED, False),
        ("()", GRAY, False),
        (" -> ", GRAY, False),
        ("None", BLUE, False),
        (":", GRAY, False),
    ],
)

# msg = "..."
y = draw_code_line(
    y,
    [
        ("    ", GRAY),
        ("msg", WHITE),
        (" = ", GRAY),
        ('"hello in iosevka charon mono;', TEAL),
    ],
)

y = draw_code_line(
    y,
    [
        ("        ", GRAY),
        ('quick grey fox, 0-9: 0123456789"', TEAL),
    ],
)

# print(msg)
y = draw_code_line(
    y,
    [
        ("    ", GRAY),
        ("print", ORANGE),
        ("(", GRAY),
        ("msg", WHITE),
        (")", GRAY),
    ],
)

y += FONT_SIZE + 8

draw.line([(MARGIN, y), (WIDTH - MARGIN, y)], fill=GRAY, width=1)
y += 20

draw.text((MARGIN, y), "ABCDEFGHIJKLMNOPQRSTUVWXYZ 0123456789", font=small, fill=WHITE)
y += SMALL_SIZE + 6
draw.text((MARGIN, y), "abcdefghijklmnopqrstuvwxyz !@#$%^&*()", font=small, fill=WHITE)
y += SMALL_SIZE + 6
draw.text((MARGIN, y), "iIlL1|  oO0  {}[]()<>  +-*/=  \"'`~_", font=small, fill=WHITE)
y += SMALL_SIZE + 6

y += 20
draw.line([(MARGIN, y), (WIDTH - MARGIN, y)], fill=GRAY, width=1)
y += 20

draw.text(
    (MARGIN, y), "->  =>  <=  >=  ==  !=  &&  ||  ::  ...", font=small, fill=WHITE
)
y += SMALL_SIZE + 6
draw.text((MARGIN, y), "┌──┬──┐ ╔══╦══╗ ░▒▓█ ◆◇●○ ▲▼◀▶", font=small, fill=WHITE)

img.save(args.output)
print("Pillow: Done - Iosevka Charon Mono")
