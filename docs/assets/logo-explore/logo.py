#!/usr/bin/env python3
"""OpenGateway logo assets: the round-4 foot-plain mark, the Outfit SemiBold lockup,
and the README banner.
Run: python3 logo.py          (needs motion/wordmarks.json from wordmark.py)
Writes mark.{dark,light}.svg, logo.{dark,light}.svg and banner.svg next to itself.
Rasterise the banner (1792x592, no fonts - the wordmark is outlined paths):
    magick banner.svg ../banner.png
"""
import json, os

HERE = os.path.dirname(os.path.abspath(__file__))
WM = json.load(open(os.path.join(HERE, "motion", "wordmarks.json")))

# round-4 foot-plain mark (motion.py)
ARCH = "M6.769 26.321V14.910a9.231 9.231 0 0 1 18.462 0V16.575"
SW = 4.358
DX, DY, DR = 25.231, 24.974, 3.526
GAP = 8.5
FACE = "outfit"  # Outfit SemiBold - the current brand setting (outfit.py)

THEMES = {
    "dark":  {"c": "#EDEBE6", "o": "#FF5A1F", "bg": "#0B0B0C"},
    "light": {"c": "#151517", "o": "#CC3A06", "bg": "#F5F5F4"},
}

def mark_body(th):
    return (f'<path d="{ARCH}" fill="none" stroke="{th["c"]}" stroke-width="{SW}" '
            f'stroke-linecap="round" stroke-linejoin="round"/>'
            f'<circle cx="{DX}" cy="{DY}" r="{DR}" fill="{th["o"]}"/>')

def mark_svg(theme):
    th = THEMES[theme]
    return ('<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 32 32" width="256" height="256" '
            'role="img" aria-label="OpenGateway"><title>OpenGateway</title>'
            + mark_body(th) + '</svg>')

def lockup_geom():
    w = WM[FACE]
    tx = 27.41 + GAP - w["minx"]
    x0, x1 = 2.5, 27.41 + GAP + (w["maxx"] - w["minx"]) + 2.1
    y0, y1 = 1.4, max(w["maxy"], 28.5) + 2.1
    return w, tx, x0, y0, x1 - x0, y1 - y0

def logo_svg(theme):
    th = THEMES[theme]
    w, tx, x, y, vw, vh = lockup_geom()
    letters = "".join(f'<path d="{l["d"]}"/>' for l in w["letters"] if l["d"])
    h = 256
    return (f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="{x} {y} {vw:.3f} {vh:.3f}" '
            f'width="{vw / vh * h:.0f}" height="{h}" role="img" aria-label="OpenGateway">'
            f'<title>OpenGateway</title>'
            f'{mark_body(th)}'
            f'<g transform="translate({tx:.3f} 0)" fill="{th["c"]}">{letters}</g></svg>')

def banner_svg():
    th, BW, BH = THEMES["dark"], 1792, 592
    w, tx, x, y, vw, vh = lockup_geom()
    s = 6.32                      # lockup lands ~1350px wide, matching the old banner
    px, py = (BW - vw * s) / 2, (BH - vh * s) / 2
    letters = "".join(f'<path d="{l["d"]}"/>' for l in w["letters"] if l["d"])
    plus = ('<pattern id="grid" width="56" height="56" patternUnits="userSpaceOnUse">'
            '<path d="M28 22v12M22 28h12" stroke="#17171A" stroke-width="1.4" stroke-linecap="round"/></pattern>')
    return (f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {BW} {BH}" width="{BW}" height="{BH}" '
            f'role="img" aria-label="OpenGateway, the AI gateway that doesn\'t paywall the features">'
            f'<title>OpenGateway</title>'
            f'<defs>{plus}</defs>'
            f'<rect width="{BW}" height="{BH}" fill="{th["bg"]}"/>'
            f'<rect width="{BW}" height="{BH}" fill="url(#grid)"/>'
            f'<g transform="translate({px - x * s:.2f} {py - y * s:.2f}) scale({s})">'
            f'{mark_body(th)}'
            f'<g transform="translate({tx:.3f} 0)" fill="{th["c"]}">{letters}</g></g></svg>')

if __name__ == "__main__":
    for theme in THEMES:
        for name, svg in (("mark", mark_svg(theme)), ("logo", logo_svg(theme))):
            path = os.path.join(HERE, f"{name}.{theme}.svg")
            open(path, "w").write(svg)
            print("wrote", path)
    path = os.path.join(HERE, "banner.svg")
    open(path, "w").write(banner_svg())
    print("wrote", path)
    print('rasterise: magick banner.svg ../banner.png')
