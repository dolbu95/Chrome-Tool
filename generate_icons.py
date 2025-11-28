from PIL import Image, ImageDraw, ImageFont, ImageFilter
import os

def create_rounded_rect(draw, xy, corner_radius, fill, outline=None, width=1):
    upper_left_point = xy[0]
    bottom_right_point = xy[1]
    draw.rounded_rectangle(
        [upper_left_point, bottom_right_point],
        radius=corner_radius,
        fill=fill,
        outline=outline,
        width=width
    )

def draw_checkmark(draw, bounds, color, width, style='smooth'):
    x, y, w, h = bounds
    if style == 'pixel':
        # Simple pixel checkmark
        points = [
            (x + 0.2*w, y + 0.5*h),
            (x + 0.4*w, y + 0.7*h),
            (x + 0.8*w, y + 0.3*h)
        ]
        draw.line(points, fill=color, width=width, joint='curve')
    else:
        points = [
            (x + 0.25*w, y + 0.55*h),
            (x + 0.45*w, y + 0.75*h),
            (x + 0.8*w, y + 0.3*h)
        ]
        draw.line(points, fill=color, width=width, joint='curve')

def generate_options():
    size = (256, 256)
    preview_size = (1024, 300)
    preview_bg = (240, 240, 240)
    
    options = []

    # Option 1: Cyberpunk Neon
    img1 = Image.new('RGBA', size, (0,0,0,0))
    d1 = ImageDraw.Draw(img1)
    create_rounded_rect(d1, [(10,10), (246,246)], 40, (30,30,35), (0,255,0), 5)
    draw_checkmark(d1, (10,10,246,246), (0,255,0), 25)
    # Add glow effect (simulated by drawing multiple transparent lines)
    options.append(("1. Neon Gamer", img1))
    img1.save("icon_opt_1.png")

    # Option 2: Minimalist Dark (White/Black)
    img2 = Image.new('RGBA', size, (0,0,0,0))
    d2 = ImageDraw.Draw(img2)
    create_rounded_rect(d2, [(10,10), (246,246)], 60, (0,0,0), (255,255,255), 0)
    draw_checkmark(d2, (10,10,246,246), (255,255,255), 30)
    options.append(("2. Minimal Dark", img2))
    img2.save("icon_opt_2.png")

    # Option 3: Retro Pixel
    img3 = Image.new('RGBA', size, (0,0,0,0))
    d3 = ImageDraw.Draw(img3)
    # Draw pixelated bg
    d3.rectangle([(20,20), (236,236)], fill=(50,50,150), outline=(0,0,0), width=5)
    # Draw pixel checkmark (manually)
    pixels = [
        (60, 130), (70, 130), (80, 130),
        (70, 140), (80, 140), (90, 140),
        (80, 150), (90, 150), (100, 150),
        (90, 160), (100, 160), (110, 160),
        (100, 170), (110, 170), (120, 170),
        (110, 160), (120, 160), (130, 160),
        (120, 150), (130, 150), (140, 150),
        (130, 140), (140, 140), (150, 140),
        (140, 130), (150, 130), (160, 130),
        (150, 120), (160, 120), (170, 120),
        (160, 110), (170, 110), (180, 110),
        (170, 100), (180, 100), (190, 100),
    ]
    # Scale up pixels
    scale = 1.2
    center_offset = 20
    for px in pixels:
        x, y = px
        x = int(x * scale) - 20
        y = int(y * scale) - 20
        d3.rectangle([x, y, x+10, y+10], fill=(255,200,0))
    options.append(("3. Retro Pixel", img3))
    img3.save("icon_opt_3.png")

    # Option 4: Modern Flat (White Box)
    img4 = Image.new('RGBA', size, (0,0,0,0))
    d4 = ImageDraw.Draw(img4)
    create_rounded_rect(d4, [(10,10), (246,246)], 50, (255,255,255), (0,0,0), 10)
    draw_checkmark(d4, (10,10,246,246), (0,0,0), 25)
    options.append(("4. Modern Light", img4))
    img4.save("icon_opt_4.png")

    # Create Preview Sheet
    preview = Image.new('RGB', preview_size, preview_bg)
    p_draw = ImageDraw.Draw(preview)
    
    try:
        font = ImageFont.truetype("arial.ttf", 20)
    except:
        font = None

    for i, (label, img) in enumerate(options):
        # Resize for preview
        thumb = img.resize((150, 150))
        x = 50 + i * 240
        y = 50
        preview.paste(thumb, (x, y), thumb)
        
        # Draw Label
        if font:
            p_draw.text((x + 20, y + 160), label, fill=(0,0,0), font=font)
        else:
            p_draw.text((x + 20, y + 160), label, fill=(0,0,0))

    preview.save("icon_preview.png")
    print("Generated icon_preview.png")

if __name__ == "__main__":
    generate_options()
