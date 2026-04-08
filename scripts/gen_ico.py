"""Generate logo.ico from logo.png."""
from pathlib import Path
from PIL import Image

root = Path(__file__).resolve().parent.parent
src = root / "logo.png"
dst = root / "logo.ico"

img = Image.open(src).convert("RGBA")
img.save(dst, format="ICO", sizes=[(16, 16), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)])
print(f"Saved {dst}")
