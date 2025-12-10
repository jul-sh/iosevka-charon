import argparse

from PIL import Image, ImageDraw, ImageFont

parser = argparse.ArgumentParser()
parser.add_argument("--output", metavar="PNG", help="where to save the image")
args = parser.parse_args()

FONT_DIR_1 = "fonts/iosevkacharon"
FONT_DIR_2 = "general_use_fonts/iosevkacharon/ttf"

WIDTH, MARGIN = 1400, 50
PANEL_WIDTH = (WIDTH - MARGIN * 3) // 2
TITLE_SIZE = 32
LABEL_SIZE = 24
FONT_SIZE = 28
LINE_HEIGHT = 12
WHITE = (255, 255, 255)
GRAY = (140, 140, 140)
ACCENT = (100, 149, 237)  # Cornflower blue

# Test text samples
test_samples = [
    ("英文 English", 28),
    ("WIRIOÙ СНЕЖНЯ Арганізацыі", 24),
    ("kǎ bɔŋɔ̌ kǒ nüxü̃́ phẩm", 24),
    ("0123456789", 28),
    ("!@#$%^&*()[]{}", 28),
    ("à á â ä æ ã å ā ç è é", 24),
]


# Calculate height
def calc_height():
    y = MARGIN
    y += TITLE_SIZE + 30  # title
    y += LABEL_SIZE + 20  # column headers
    y += 5  # separator line
    
    for _, _ in test_samples:
        y += FONT_SIZE + LINE_HEIGHT + 10
    
    y += MARGIN
    return y


HEIGHT = calc_height()

img = Image.new("RGB", (WIDTH, HEIGHT), color=(15, 15, 20))
draw = ImageDraw.Draw(img)

y = MARGIN

# Main title
title_font = ImageFont.truetype(f"{FONT_DIR_1}/IosevkaCharon-Bold.ttf", TITLE_SIZE)
draw.text((MARGIN, y), "Font Comparison: Google Fonts vs. General Use", font=title_font, fill=WHITE)
y += TITLE_SIZE + 30

# Column headers
label_font = ImageFont.truetype(f"{FONT_DIR_1}/IosevkaCharon-Bold.ttf", LABEL_SIZE)
left_x = MARGIN
right_x = MARGIN + PANEL_WIDTH + MARGIN

draw.text((left_x, y), "Google Fonts Version", font=label_font, fill=ACCENT)
draw.text((right_x, y), "General Use Version", font=label_font, fill=ACCENT)
y += LABEL_SIZE + 20

# Separator line
draw.line([(MARGIN, y), (WIDTH - MARGIN, y)], fill=GRAY, width=1)
y += 10

# Draw comparison samples
for text, size in test_samples:
    try:
        font1 = ImageFont.truetype(f"{FONT_DIR_1}/IosevkaCharon-Regular.ttf", size)
        font2 = ImageFont.truetype(f"{FONT_DIR_2}/IosevkaCharon-Regular.ttf", size)
        
        # Left panel (Google Fonts version)
        draw.text((left_x, y), text, font=font1, fill=WHITE)
        
        # Right panel (General Use version)
        draw.text((right_x, y), text, font=font2, fill=WHITE)
        
    except Exception as e:
        # If font loading fails, show error message
        error_font = ImageFont.truetype(f"{FONT_DIR_1}/IosevkaCharon-Italic.ttf", 18)
        draw.text((left_x, y), f"Error: {str(e)[:30]}...", font=error_font, fill=(255, 100, 100))
    
    y += FONT_SIZE + LINE_HEIGHT + 10

# Vertical separator between panels
separator_x = MARGIN + PANEL_WIDTH + MARGIN // 2
draw.line([(separator_x, MARGIN + TITLE_SIZE + 30), (separator_x, HEIGHT - MARGIN)], fill=GRAY, width=1)

img.save(args.output)
print(f"Font comparison image saved to {args.output}")
