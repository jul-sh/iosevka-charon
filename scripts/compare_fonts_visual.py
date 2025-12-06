#!/usr/bin/env python3
"""
Quick visual comparison of before/after fonts for LLM analysis.
Generates a simple text-based comparison showing metrics and rendering differences.
"""

import sys
from pathlib import Path
from fontTools.ttLib import TTFont
from PIL import Image, ImageDraw, ImageFont

def get_metrics(font_path):
    """Extract key metrics from a font."""
    font = TTFont(font_path)
    return {
        'ascender': font['hhea'].ascender,
        'descender': font['hhea'].descender,
        'lineGap': font['hhea'].lineGap,
        'winAscent': font['OS/2'].usWinAscent,
        'winDescent': font['OS/2'].usWinDescent,
        'total_height': font['hhea'].ascender - font['hhea'].descender + font['hhea'].lineGap,
        'upm': font['head'].unitsPerEm
    }

def render_sample(font_path, text, size=48):
    """Render text sample using PIL."""
    try:
        font = ImageFont.truetype(str(font_path), size)

        # Calculate image size
        bbox = font.getbbox(text)
        width = bbox[2] - bbox[0] + 40
        height = bbox[3] - bbox[1] + 40

        # Create image
        img = Image.new('RGB', (width, height), 'white')
        draw = ImageDraw.Draw(img)

        # Draw text
        draw.text((20, 20), text, font=font, fill='black')

        return img
    except Exception as e:
        print(f"Error rendering: {e}")
        return None

def render_multiline_sample(font_path, lines, size=32):
    """Render multiple lines to show line spacing."""
    try:
        font = ImageFont.truetype(str(font_path), size)

        # Calculate dimensions
        max_width = 0
        total_height = 0
        line_heights = []

        for line in lines:
            bbox = font.getbbox(line)
            max_width = max(max_width, bbox[2] - bbox[0])
            line_height = bbox[3] - bbox[1]
            line_heights.append(line_height)
            total_height += line_height

        # Add spacing between lines (this is where we'll see the issue)
        line_spacing = int(size * 1.2)  # Normal line spacing
        total_height = line_spacing * len(lines) + 40

        # Create image
        img = Image.new('RGB', (max_width + 40, total_height), 'white')
        draw = ImageDraw.Draw(img)

        # Draw lines
        y = 20
        for line in lines:
            draw.text((20, y), line, font=font, fill='black')
            y += line_spacing

        return img
    except Exception as e:
        print(f"Error rendering multiline: {e}")
        return None

def main():
    # Find fonts to compare
    before_regular = Path("sources/output/IosevkaCharonMono/ttf/IosevkaCharonMono-Regular.ttf")
    after_regular = Path("fonts/iosevkacharonmono/IosevkaCharonMono-Regular.ttf")

    if not before_regular.exists() or not after_regular.exists():
        print("ERROR: Font files not found")
        print(f"  Before: {before_regular} (exists: {before_regular.exists()})")
        print(f"  After: {after_regular} (exists: {after_regular.exists()})")
        sys.exit(1)

    print("=" * 80)
    print("FONT METRICS COMPARISON (Regular weight)")
    print("=" * 80)

    before_metrics = get_metrics(before_regular)
    after_metrics = get_metrics(after_regular)

    print("\nBEFORE (Raw Iosevka):")
    print(f"  Ascender:    {before_metrics['ascender']:>5}")
    print(f"  Descender:   {before_metrics['descender']:>5}")
    print(f"  LineGap:     {before_metrics['lineGap']:>5}")
    print(f"  WinAscent:   {before_metrics['winAscent']:>5}")
    print(f"  WinDescent:  {before_metrics['winDescent']:>5}")
    print(f"  Total:       {before_metrics['total_height']:>5}")
    print(f"  UPM:         {before_metrics['upm']:>5}")

    print("\nAFTER (Post-processed):")
    print(f"  Ascender:    {after_metrics['ascender']:>5} ({after_metrics['ascender'] - before_metrics['ascender']:+d})")
    print(f"  Descender:   {after_metrics['descender']:>5} ({after_metrics['descender'] - before_metrics['descender']:+d})")
    print(f"  LineGap:     {after_metrics['lineGap']:>5} ({after_metrics['lineGap'] - before_metrics['lineGap']:+d})")
    print(f"  WinAscent:   {after_metrics['winAscent']:>5} ({after_metrics['winAscent'] - before_metrics['winAscent']:+d})")
    print(f"  WinDescent:  {after_metrics['winDescent']:>5} ({after_metrics['winDescent'] - before_metrics['winDescent']:+d})")
    print(f"  Total:       {after_metrics['total_height']:>5} ({after_metrics['total_height'] - before_metrics['total_height']:+d}, {((after_metrics['total_height'] - before_metrics['total_height']) / before_metrics['total_height'] * 100):.1f}%)")

    print("\n" + "=" * 80)
    print("VISUAL IMPACT ANALYSIS")
    print("=" * 80)

    height_increase_pct = ((after_metrics['total_height'] - before_metrics['total_height']) / before_metrics['total_height'] * 100)

    if height_increase_pct > 20:
        print(f"\n⚠️  CRITICAL: Line height increased by {height_increase_pct:.1f}%")
        print("   This will make text appear significantly more spaced out")
        print("   and characters will look smaller in comparison.")
    elif height_increase_pct > 10:
        print(f"\n⚠️  WARNING: Line height increased by {height_increase_pct:.1f}%")
        print("   Noticeable increase in line spacing.")
    elif height_increase_pct > 5:
        print(f"\nℹ️  Line height increased by {height_increase_pct:.1f}%")
        print("   Minor increase in line spacing.")
    else:
        print(f"\n✓ Line height change: {height_increase_pct:.1f}% (acceptable)")

    # Generate visual samples
    print("\n" + "=" * 80)
    print("GENERATING VISUAL SAMPLES")
    print("=" * 80)

    output_dir = Path("out/visual-comparison")
    output_dir.mkdir(parents=True, exist_ok=True)

    # Sample texts
    alphabet_upper = "ABCDEFGHIJKLMNOPQRSTUVWXYZ"
    alphabet_lower = "abcdefghijklmnopqrstuvwxyz"
    digits = "0123456789"
    sample_text = "The quick brown fox jumps over the lazy dog"
    complex_block = """s-ôtes vre̊ymint 
ecretario.general@interlingua.com Көдэҥ параԝааньэрэҥ Йаԝнай GWIRIOÙ СНЕЖНЯ Арганізацыі Абʼяднаных правоў 
яе тэрыторый». ГЕНЕРАЛЬНАЯ үйелменінің құқықтарының алынбайтындығын Ұлттар Әр Құлдық Өзінің Ҳар kǎ 
ɔŋɔ̌ kǒ nüxü̃́ ĨXẼ qaỹaỹateeta nai>>ctaxa ƏBİLOV ləyoğətə Çəvon po'ñoc̈h Ḽifhasi Ḽoṱhe Nyanḓadzamafhungo ḽa ṅwaha 
ewa DPI/876/Rev3-07–07-30950-Shundunthule-2007.40M кӱнинде тӧзӧгӧзи Ӱредӱлик учурлу.Ӧскӧ manuśenqe famělia 
spirŕcia akalaɵar trąden rňdel teritorűqesqiri, maźutipen naśărdől Âaj procedůra. d´fhiacha Южно-Сахалинск Ниғвӊ 
уфтоӿ салӻанӿунвд ӷавргуйныр̌кир̌ Ыткғун Ӿаӊы Генеральнай айӈаниду į žmonių giminės sąžinę, Įgyvendindamas 
рођеног Òmma Фэдэр neɗɗo ɓesngu moƴƴam, kelliƭuya Ɗii Ês Ĝenerala ĉiuj efektiviĝo kontraŭ Ĉarto Ŝtatoj-Membroj paŝoj 
osedaĵoj, tjuta! Ó KU`OTENESE nɑn ʒem Được đồng phẩm jǐ Nǔ Åtta Үөрэхтээһин éyaltai{ab Enyiń mpɔ̂ Það þetta 
éttlætis lýst, ΔΕΚΕΜΒΡΙΟΥ Ἐπειδὴ ἡ ἀναγνώριση τῆς ἀξιοπρέπειας, ποὺ εἶναι σύμφυτη"""
    multiline_sample = [
        "The quick brown fox",
        "jumps over the lazy dog.",
        "Pack my box with five",
        "dozen liquor jugs."
    ]

    # Render single line samples
    for name, text in [
        ("alphabet-upper", alphabet_upper),
        ("alphabet-lower", alphabet_lower),
        ("digits", digits),
        ("sample", sample_text)
    ]:
        before_img = render_sample(before_regular, text, 48)
        after_img = render_sample(after_regular, text, 48)

        if before_img and after_img:
            # Combine side by side
            combined = Image.new('RGB', (before_img.width + after_img.width, max(before_img.height, after_img.height)), 'white')
            combined.paste(before_img, (0, 0))
            combined.paste(after_img, (before_img.width, 0))
            combined.save(output_dir / f"{name}-comparison.png")
            print(f"  ✓ Generated {name}-comparison.png")

    # Render complex multilingual sample to catch edge shaping/marks
    complex_lines = complex_block.splitlines()
    before_complex = render_multiline_sample(before_regular, complex_lines, 26)
    after_complex = render_multiline_sample(after_regular, complex_lines, 26)

    if before_complex and after_complex:
        max_width = max(before_complex.width, after_complex.width)
        combined = Image.new('RGB', (max_width, before_complex.height + after_complex.height + 20), 'white')
        combined.paste(before_complex, (0, 0))
        combined.paste(after_complex, (0, before_complex.height + 20))
        combined.save(output_dir / "complex-multilingual-comparison.png")
        print(f"  ✓ Generated complex-multilingual-comparison.png")

    # Render multiline sample to show line spacing issue
    before_multi = render_multiline_sample(before_regular, multiline_sample, 32)
    after_multi = render_multiline_sample(after_regular, multiline_sample, 32)

    if before_multi and after_multi:
        # Stack vertically for easy comparison
        max_width = max(before_multi.width, after_multi.width)
        combined = Image.new('RGB', (max_width, before_multi.height + after_multi.height + 20), 'white')
        combined.paste(before_multi, (0, 0))
        combined.paste(after_multi, (0, before_multi.height + 20))
        combined.save(output_dir / "multiline-comparison.png")
        print(f"  ✓ Generated multiline-comparison.png")

    print(f"\n✓ Visual samples saved to: {output_dir}/")
    print("\nTo view:")
    print(f"  open {output_dir}/")

if __name__ == "__main__":
    main()
