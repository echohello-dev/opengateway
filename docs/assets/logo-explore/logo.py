#!/usr/bin/env python3
"""OpenGateway logo assets: the round-4 foot-plain mark, the Outfit SemiBold lockup,
and the slim README banner (static + animated).
Run: python3 logo.py          (needs motion/wordmarks.json from wordmark.py
                               and motion/svg/m-connect.dark.svg from motion.py)
Writes mark.{dark,light}.svg, logo.{dark,light}.svg, banner.svg and
banner.anim.svg next to itself.
    magick banner.svg ../banner.png          # slim static banner
The animated banner GIF is captured from banner.anim.svg in a browser
(CSS animations do not rasterise) and encoded with ffmpeg.
"""
import json, os, re

HERE = os.path.dirname(os.path.abspath(__file__))
WM = json.load(open(os.path.join(HERE, "motion", "wordmarks.json")))
CONNECT = open(os.path.join(HERE, "motion", "svg", "m-connect.dark.svg")).read()

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
BW, BH = 1792, 360        # slim banner, one logo, no vertical padding to burn

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

def _banner_frame():
    """Shared layout: dark grid, lockup centred on the slim canvas."""
    th = THEMES["dark"]
    w, tx, x, y, vw, vh = lockup_geom()
    s = min((BW - 260) / vw, (BH - 130) / vh)
    px, py = (BW - vw * s) / 2, (BH - vh * s) / 2
    letters = "".join(f'<path d="{l["d"]}"/>' for l in w["letters"] if l["d"])
    plus = ('<pattern id="grid" width="56" height="56" patternUnits="userSpaceOnUse">'
            '<path d="M28 22v12M22 28h12" stroke="#17171A" stroke-width="1.4" stroke-linecap="round"/></pattern>')
    wrap_open = (f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {BW} {BH}" width="{BW}" height="{BH}" '
                 f'role="img" aria-label="OpenGateway, the AI gateway that doesn\'t paywall the features">'
                 f'<title>OpenGateway</title>'
                 f'<defs>{plus}</defs>'
                 f'<rect width="{BW}" height="{BH}" fill="{th["bg"]}"/>'
                 f'<rect width="{BW}" height="{BH}" fill="url(#grid)"/>'
                 f'<g transform="translate({px - x * s:.2f} {py - y * s:.2f}) scale({s})">')
    wrap_close = '</g></svg>'
    tail = f'<g transform="translate({tx:.3f} 0)" fill="{th["c"]}">{letters}</g>'
    return wrap_open, tail, wrap_close

def banner_svg():
    """Static banner: the settled foot-plain lockup, presentation attributes only
    so any rasteriser (magick) renders it correctly."""
    wrap_open, tail, wrap_close = _banner_frame()
    return wrap_open + mark_body(THEMES["dark"]) + tail + wrap_close

def banner_anim_svg():
    """Animated banner: the Connect sequence plays on the mark (key clicks down/up,
    the ring unlocks into the gate, the leg latches closed). CSS lives inside the
    SVG, so it must be rasterised in a browser. The keyframes and mark markup are
    extracted from motion.py's own output to keep one animation source."""
    style = re.search(r'<style>(.*?)</style>', CONNECT, re.S).group(1)
    mark = re.search(r'<g class="m-connect-mark">.*</g></svg>', CONNECT, re.S).group(0)
    mark = mark[:-len('</svg>')]
    wrap_open, tail, wrap_close = _banner_frame()
    return wrap_open.replace('</defs>', f'<style>{style}</style></defs>') + mark + tail + wrap_close

if __name__ == "__main__":
    for theme in THEMES:
        for name, svg in (("mark", mark_svg(theme)), ("logo", logo_svg(theme))):
            path = os.path.join(HERE, f"{name}.{theme}.svg")
            open(path, "w").write(svg)
            print("wrote", path)
    for name, svg in (("banner", banner_svg()), ("banner.anim", banner_anim_svg())):
        path = os.path.join(HERE, f"{name}.svg")
        open(path, "w").write(svg)
        print("wrote", path)
    print('rasterise: magick banner.svg ../banner.png   (banner.anim.svg -> browser capture -> ../banner.gif)')
