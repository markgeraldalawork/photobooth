from PIL import Image

width, height = 1800, 1200
# Transparent overlay
img = Image.new("RGBA", (width, height), (0, 0, 0, 0))
img.save("layouts/4R/overlay.png")
print("✅ overlay.png created")