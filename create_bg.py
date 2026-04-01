from PIL import Image

width, height = 1800, 1200
img = Image.new("RGB", (width, height), "white")
img.save("layouts/4R/bg.png")
print("✅ bg.png created!")