"""Generate Inno Setup wizard images from logo.png."""
from pathlib import Path
from PIL import Image, ImageDraw

root = Path(__file__).resolve().parent.parent
src = root / "logo.png"
out = root / "scripts" / "assets"
out.mkdir(exist_ok=True)

logo = Image.open(src).convert("RGBA")

# --- Sidebar (163x314): dark background + centered logo ---
W, H = 163, 314
sidebar = Image.new("RGBA", (W, H), (18, 18, 28, 255))

logo_size = 90
logo_resized = logo.resize((logo_size, logo_size), Image.LANCZOS)
x = (W - logo_size) // 2
y = (H - logo_size) // 2 - 20
sidebar.paste(logo_resized, (x, y), logo_resized)

sidebar_rgb = Image.new("RGB", (W, H), (18, 18, 28))
sidebar_rgb.paste(sidebar, mask=sidebar.split()[3])
sidebar_rgb.save(out / "wizard_sidebar.bmp", format="BMP")
print(f"Saved wizard_sidebar.bmp ({W}x{H})")

# --- Small banner (55x55): logo on dark bg ---
S = 55
small = Image.new("RGBA", (S, S), (18, 18, 28, 255))
logo_s = logo.resize((42, 42), Image.LANCZOS)
xo = (S - 42) // 2
yo = (S - 42) // 2
small.paste(logo_s, (xo, yo), logo_s)

small_rgb = Image.new("RGB", (S, S), (18, 18, 28))
small_rgb.paste(small, mask=small.split()[3])
small_rgb.save(out / "wizard_small.bmp", format="BMP")
print(f"Saved wizard_small.bmp ({S}x{S})")
