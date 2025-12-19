import argparse
import numpy as np
from PIL import Image, ImageDraw, ImageFont

parser = argparse.ArgumentParser()
parser.add_argument("--output", metavar="PNG", help="where to save the image")
args = parser.parse_args()

FONT_DIR_1 = "fonts/iosevkacharon"  # Google Fonts version
FONT_DIR_2 = "unprocessed_fonts/IosevkaCharon/ttf"  # Unprocessed version

WIDTH, MARGIN = 1600, 50
TITLE_SIZE = 36
SUBTITLE_SIZE = 22
FONT_SIZE = 48
LINE_HEIGHT = 20
BG_COLOR = (15, 15, 20)
WHITE = (255, 255, 255)
GRAY = (140, 140, 140)
RED = (255, 80, 80)    # Pixels only in GF version
GREEN = (80, 255, 120)  # Pixels only in Unprocessed version
YELLOW = (255, 255, 100)  # Differences

test_samples = [
    ("English Text Sample", 48),
    ("ü̃́ü̃́ü̃́ü̃́ü̃́ü̃́ X̲X̲X̲X̲X̲ Арганізацыі Абʼяднаных правоў «яе тэрыторый».", 42),
    ("N̰N̰N̰N̰N̰ үйелменінің құқықтарының лынбайтындығын Ұлттар Әр Құлдық", 42),
    ("Өзінің a̱a̱a̱a̱a̱ bɔŋɔ̌ kǒ nüxü̃́ ӷавргуйныр̌кир̌ phẩm jǐ Nǔ Åtta", 42),
    ("p̱p̱p̱p̱p̱p̱ éyaltai{ab Enyiń mpɔ̂ Það juisɨ̱kio malɇ Ṱhalutshezo", 42),
    ("0123456789 !@#$%", 44),
    ("à á â ä æ ã å ā ç è é ê ë", 40),
]


def render_text_to_array(text, font_path, size):
    """Render text to a numpy array for pixel-level comparison"""
    font = ImageFont.truetype(font_path, size)

    # Create temporary image to measure text
    temp_img = Image.new("L", (1, 1))
    temp_draw = ImageDraw.Draw(temp_img)
    bbox = temp_draw.textbbox((0, 0), text, font=font)
    text_width = bbox[2] - bbox[0] + 20
    text_height = bbox[3] - bbox[1] + 20

    # Render text
    img = Image.new("L", (text_width, text_height), color=0)
    draw = ImageDraw.Draw(img)
    draw.text((10, 10), text, font=font, fill=255)

    return np.array(img), text_width, text_height


def create_diff_image(arr1, arr2):
    """Create a color-coded difference image from two grayscale arrays"""
    # Normalize arrays to binary (threshold at 128)
    binary1 = (arr1 > 128).astype(np.uint8)
    binary2 = (arr2 > 128).astype(np.uint8)

    # Create RGB output
    h, w = binary1.shape
    diff_img = np.zeros((h, w, 3), dtype=np.uint8)

    # White where both have pixels (identical)
    both = binary1 & binary2
    diff_img[both == 1] = WHITE

    # Red where only GF version has pixels
    only_gf = binary1 & ~binary2
    diff_img[only_gf == 1] = RED

    # Green where only Unprocessed version has pixels
    only_gu = ~binary1 & binary2
    diff_img[only_gu == 1] = GREEN

    return diff_img


# Calculate total height needed
def calc_height():
    y = MARGIN
    y += TITLE_SIZE + 20  # main title
    y += SUBTITLE_SIZE + 30  # subtitle + gap

    for _, size in test_samples:
        y += size + 30  # text + gap between samples

    y += 40  # legend
    y += MARGIN
    return y


HEIGHT = calc_height()

# Create main image
main_img = Image.new("RGB", (WIDTH, HEIGHT), color=BG_COLOR)
main_draw = ImageDraw.Draw(main_img)

y = MARGIN

# Title
try:
    title_font = ImageFont.truetype(f"{FONT_DIR_1}/IosevkaCharon-Bold.ttf", TITLE_SIZE)
    subtitle_font = ImageFont.truetype(f"{FONT_DIR_1}/IosevkaCharon-Regular.ttf", SUBTITLE_SIZE)
    legend_font = ImageFont.truetype(f"{FONT_DIR_1}/IosevkaCharon-Regular.ttf", 18)
except:
    print("Warning: Could not load title fonts, using default")
    title_font = ImageFont.load_default()
    subtitle_font = ImageFont.load_default()
    legend_font = ImageFont.load_default()

main_draw.text((MARGIN, y), "Font Overlay Comparison", font=title_font, fill=WHITE)
y += TITLE_SIZE + 10

main_draw.text((MARGIN, y), "Post-processed for Google Fonts (red) vs Base Font (green) — White = identical", font=subtitle_font, fill=GRAY)
y += SUBTITLE_SIZE + 30

# Draw separator line
main_draw.line([(MARGIN, y), (WIDTH - MARGIN, y)], fill=GRAY, width=1)
y += 20

# Process each sample
differences_found = []
for text, size in test_samples:
    try:
        # Render both versions
        font1_path = f"{FONT_DIR_1}/IosevkaCharon-Regular.ttf"
        font2_path = f"{FONT_DIR_2}/IosevkaCharon-Regular.ttf"

        arr1, w1, h1 = render_text_to_array(text, font1_path, size)
        arr2, w2, h2 = render_text_to_array(text, font2_path, size)

        # Pad arrays to same size
        max_w = max(w1, w2)
        max_h = max(h1, h2)

        padded1 = np.zeros((max_h, max_w), dtype=np.uint8)
        padded2 = np.zeros((max_h, max_w), dtype=np.uint8)

        padded1[:h1, :w1] = arr1
        padded2[:h2, :w2] = arr2

        # Create diff image
        diff_array = create_diff_image(padded1, padded2)
        diff_pil = Image.fromarray(diff_array, mode='RGB')

        # Check if there are differences
        has_diff = np.any((padded1 > 128) != (padded2 > 128))
        if has_diff:
            differences_found.append(text)

        # Paste onto main image
        main_img.paste(diff_pil, (MARGIN, y))

        y += size + 30

    except Exception as e:
        main_draw.text((MARGIN, y), f"Error rendering '{text}': {str(e)}", font=legend_font, fill=RED)
        y += 30

# Add legend at bottom
y += 10
main_draw.line([(MARGIN, y), (WIDTH - MARGIN, y)], fill=GRAY, width=1)
y += 15

legend_x = MARGIN
main_draw.rectangle([legend_x, y, legend_x + 20, y + 15], fill=WHITE)
main_draw.text((legend_x + 30, y), "Identical glyphs", font=legend_font, fill=WHITE)

legend_x += 250
main_draw.rectangle([legend_x, y, legend_x + 20, y + 15], fill=RED)
main_draw.text((legend_x + 30, y), "Only in post-processed", font=legend_font, fill=RED)

legend_x += 300
main_draw.rectangle([legend_x, y, legend_x + 20, y + 15], fill=GREEN)
main_draw.text((legend_x + 30, y), "Only in base font", font=legend_font, fill=GREEN)

# Save
main_img.save(args.output)

if differences_found:
    print(f"⚠ Differences found in: {', '.join(differences_found)}")
else:
    print("✓ No visual differences detected between the two font versions")

print(f"Font comparison overlay saved to {args.output}")
