"""Regenerate every icon in static/ from one set of vector geometry.

    pip install pillow
    python tools/make_icons.py

16/24px use a bolder variant (BOLD) so the glyph stays legible; larger sizes use REGULAR.
"""
from PIL import Image, ImageDraw

BRAND = (0x4F, 0x46, 0xE5)
WHITE = (255, 255, 255)
# geometry in a 100-unit square, measured from the AI-generated source
REGULAR = dict(big=(50, 33.5, 16.7), smalls=[(22.1, 74.5), (50, 74.5), (77.9, 74.5)], r=8.7, stroke=5.5)
# bolder variant so the glyph survives 16-24px
BOLD = dict(big=(50, 31.3, 18.75), smalls=[(18.75, 75), (50, 75), (81.25, 75)], r=9.4, stroke=7.5)
RADIUS = 19.1


def glyph(draw, s, g, scale=1.0, offset=(0, 0)):
    k = s / 100.0
    def P(x, y):
        return ((50 + (x - 50) * scale) * k + offset[0], (50 + (y - 50) * scale) * k + offset[1])
    bx, by, br = g["big"]
    for sx, sy in g["smalls"]:
        draw.line([P(bx, by), P(sx, sy)], fill=WHITE, width=round(g["stroke"] * scale * k))
    cx, cy = P(bx, by); r = br * scale * k
    draw.ellipse([cx - r, cy - r, cx + r, cy + r], fill=WHITE)
    for sx, sy in g["smalls"]:
        cx, cy = P(sx, sy); r = g["r"] * scale * k
        draw.ellipse([cx - r, cy - r, cx + r, cy + r], fill=WHITE)


def render(size, g, rounded=True, glyph_scale=1.0, ss=8):
    s = size * ss
    im = Image.new("RGBA", (s, s), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    if rounded:
        d.rounded_rectangle([0, 0, s - 1, s - 1], radius=RADIUS / 100 * s, fill=BRAND)
    else:
        d.rectangle([0, 0, s, s], fill=BRAND)
    glyph(d, s, g, glyph_scale)
    return im.resize((size, size), Image.LANCZOS)


def svg(g, rounded=True):
    bx, by, br = g["big"]
    lines = "".join(f'<path d="M{bx} {by}L{sx} {sy}"/>' for sx, sy in g["smalls"])
    circles = f'<circle cx="{bx}" cy="{by}" r="{br}"/>' + "".join(f'<circle cx="{sx}" cy="{sy}" r="{g["r"]}"/>' for sx, sy in g["smalls"])
    bg = f'<rect width="100" height="100" rx="{RADIUS}" fill="#4f46e5"/>' if rounded else '<rect width="100" height="100" fill="#4f46e5"/>'
    return (f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 100 100">{bg}'
            f'<g stroke="#fff" stroke-width="{g["stroke"]}">{lines}</g><g fill="#fff">{circles}</g></svg>\n')


if __name__ == "__main__":
    import os

    out = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "static")
    frames = [render(16, BOLD), render(24, BOLD), render(32, REGULAR), render(48, REGULAR)]
    frames[-1].save(f"{out}/favicon.ico", sizes=[(16, 16), (24, 24), (32, 32), (48, 48)], append_images=frames[:-1])
    render(180, REGULAR, rounded=False).convert("RGB").save(f"{out}/apple-touch-icon.png", optimize=True)
    render(192, REGULAR).save(f"{out}/icon-192.png", optimize=True)
    render(512, REGULAR).save(f"{out}/icon-512.png", optimize=True)
    render(512, REGULAR, rounded=False, glyph_scale=0.82).save(f"{out}/icon-maskable-512.png", optimize=True)
    with open(f"{out}/favicon.svg", "w") as fh:
        fh.write(svg(REGULAR))
    print("icons written to", os.path.normpath(out))
