from PIL import Image, ImageDraw

def create_checkbox_icon():
    size = (256, 256)
    # Background color (Dark gray for game UI feel)
    bg_color = (40, 40, 40)
    # Border color (White)
    border_color = (200, 200, 200)
    # Checkmark color (Green or bright white)
    check_color = (0, 255, 0) # Bright green for "Test Passed" feel

    image = Image.new('RGBA', size, (0, 0, 0, 0))
    draw = ImageDraw.Draw(image)

    # Draw rounded rectangle background
    margin = 20
    draw.rounded_rectangle(
        [(margin, margin), (size[0]-margin, size[1]-margin)],
        radius=40,
        fill=bg_color,
        outline=border_color,
        width=15
    )

    # Draw Checkmark
    # Points for a checkmark
    points = [
        (60, 130),
        (110, 180),
        (200, 80)
    ]
    draw.line(points, fill=check_color, width=25, joint='curve')

    # Save as PNG for internal use
    image.save('app_icon.png')
    
    # Save as ICO for Windows Executable
    image.save('app_icon.ico', format='ICO', sizes=[(256, 256), (128, 128), (64, 64), (48, 48), (32, 32), (16, 16)])

if __name__ == "__main__":
    create_checkbox_icon()
    print("Icons created: app_icon.png, app_icon.ico")
