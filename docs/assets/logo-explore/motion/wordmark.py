"""Shape 'OpenGateway' with real kerning and write per-letter SVG paths (32-unit mark scale) to wordmarks.json.
Run: uv run --with fonttools --with uharfbuzz python wordmark.py
Fonts are SIL OFL, fetched from github.com/google/fonts."""
import subprocess, json, io
import uharfbuzz as hb
from fontTools.ttLib import TTFont
from fontTools.varLib import instancer
from fontTools.pens.svgPathPen import SVGPathPen
from fontTools.pens.transformPen import TransformPen
from fontTools.pens.boundsPen import BoundsPen

TEXT = "OpenGateway"
FACES = {
    "instrument": ("Instrument Sans SemiBold", "InstrumentSans[wdth,wght].ttf", "instrumentsans", {"wght": 600, "wdth": 100}),
    "outfit":     ("Outfit SemiBold",          "Outfit[wght].ttf",              "outfit",          {"wght": 600}),
    "space":      ("Space Grotesk SemiBold",   "SpaceGrotesk[wght].ttf",        "spacegrotesk",    {"wght": 600}),
    "syne":       ("Syne SemiBold",            "Syne[wght].ttf",                "syne",            {"wght": 600}),
    "familjen":   ("Familjen Grotesk SemiBold", "FamiljenGrotesk[wght].ttf",    "familjengrotesk", {"wght": 600}),
    "unbounded":  ("Unbounded SemiBold",       "Unbounded[wght].ttf",           "unbounded",       {"wght": 600}),
    "sora":       ("Sora SemiBold",            "Sora[wght].ttf",                "sora",            {"wght": 600}),
    "parkinsans": ("Parkinsans SemiBold",      "Parkinsans[wght].ttf",          "parkinsans",      {"wght": 600}),
    "martian":    ("Martian Mono SemiBold",    "MartianMono[wdth,wght].ttf",    "martianmono",     {"wght": 600, "wdth": 75}),
    "dela":       ("Dela Gothic One",          "DelaGothicOne-Regular.ttf",     "delagothicone",   {}),
}
EXTRA = {  # exploration faces (Outfit deep-dive), written to wordmarks-extra.json
    "outfit500": ("Outfit Medium",             "Outfit[wght].ttf",              "outfit",          {"wght": 500}),
    "outfit700": ("Outfit Bold",               "Outfit[wght].ttf",              "outfit",          {"wght": 700}),
    "outfit800": ("Outfit ExtraBold",          "Outfit[wght].ttf",              "outfit",          {"wght": 800}),
    "urbanist":  ("Urbanist SemiBold",         "Urbanist[wght].ttf",            "urbanist",        {"wght": 600}),
    "figtree":   ("Figtree SemiBold",          "Figtree[wght].ttf",             "figtree",         {"wght": 600}),
    "jost":      ("Jost SemiBold",             "Jost[wght].ttf",                "jost",            {"wght": 600}),
    "onest":     ("Onest SemiBold",            "Onest[wght].ttf",               "onest",           {"wght": 600}),
    "hanken":    ("Hanken Grotesk SemiBold",   "HankenGrotesk[wght].ttf",       "hankengrotesk",   {"wght": 600}),
    "poppins":   ("Poppins SemiBold",          "Poppins-SemiBold.ttf",          "poppins",         {}),
}
FS = 32 / 1.15            # font size in mark units, so the mark is 1.15x the font size (as in the Figma lockups)
TRACK = -0.02             # -2% letter spacing
out = {}
for key, (label, fname, folder, axes) in {**FACES, **EXTRA}.items():
    raw = subprocess.run(["gh", "api", f"repos/google/fonts/contents/ofl/{folder}/{fname}", "-H", "Accept: application/vnd.github.raw"], capture_output=True).stdout
    font = TTFont(io.BytesIO(raw))
    if axes and "fvar" in font:
        font = instancer.instantiateVariableFont(font, axes)
    buf = io.BytesIO(); font.save(buf); data = buf.getvalue()
    upem = font["head"].unitsPerEm; s = FS / upem
    face = hb.Face(data); hbfont = hb.Font(face)
    b = hb.Buffer(); b.add_str(TEXT); b.guess_segment_properties(); hb.shape(hbfont, b, {"kern": True, "liga": False})
    gs = font.getGlyphSet(); order = font.getGlyphOrder()
    cap = getattr(font["OS/2"], "sCapHeight", 0.7 * upem) * s
    baseline = 16 + cap / 2                       # centre the cap height on the mark centre line
    x = 0.0; letters = []
    for i, (info, pos) in enumerate(zip(b.glyph_infos, b.glyph_positions)):
        name = order[info.codepoint]
        pen = SVGPathPen(gs, ntos=lambda v: f"{v:.2f}".rstrip("0").rstrip("."))
        gx = x + pos.x_offset * s
        gs[name].draw(TransformPen(pen, (s, 0, 0, -s, gx, baseline)))
        bp = BoundsPen(gs); gs[name].draw(TransformPen(bp, (s, 0, 0, -s, gx, baseline)))
        letters.append({"ch": TEXT[i], "d": pen.getCommands(), "x": round(gx, 2), "bounds": [round(v, 2) for v in bp.bounds] if bp.bounds else None})
        x += pos.x_advance * s + TRACK * FS
    x -= TRACK * FS
    bs = [l["bounds"] for l in letters if l["bounds"]]
    out[key] = {"label": label, "fs": round(FS, 2), "baseline": round(baseline, 2), "advance": round(x, 2), "cap": round(cap, 2),
                "minx": min(v[0] for v in bs), "maxx": max(v[2] for v in bs), "miny": min(v[1] for v in bs), "maxy": max(v[3] for v in bs), "letters": letters}
    print(key, label, "width", round(x, 1), "y range", round(out[key]["miny"], 1), round(out[key]["maxy"], 1), "baseline", round(baseline, 1))
json.dump({k: out[k] for k in FACES}, open("wordmarks.json", "w"))
json.dump({k: out[k] for k in EXTRA}, open("wordmarks-extra.json", "w"))
