#!/usr/bin/env python3
"""OpenGateway typeface exploration page. Every face in wordmarks.json as a wordmark specimen
(matched cap height), a lockup with the round-4 foot-plain mark (dark and light), and a
small-size legibility strip in live Google Fonts text.
Run: python3 typeface.py          (needs wordmarks.json from wordmark.py)
Writes typeface.html next to itself."""
import json, os

HERE = os.path.dirname(os.path.abspath(__file__))
WM = json.load(open(os.path.join(HERE, "wordmarks.json")))

ARCH = "M6.769 26.321V14.910a9.231 9.231 0 0 1 18.462 0V16.575"   # round-4 foot-plain mark (motion.py)
SW = 4.358
DX, DY, DR = 25.231, 24.974, 3.526
GAP = 8.5
ORDER = ["instrument", "outfit", "space", "syne", "familjen", "unbounded", "sora", "parkinsans", "martian", "dela"]
NOTES = {
    "instrument": "Control. Neutral grotesque, the current Figma lockup face.",
    "outfit": "Control. Even geometric sans.",
    "space": "Proportional sibling of Space Mono. Flat-spur G, mechanical a and y. Unique but usable.",
    "syne": "Wide angular display. Distinctive a, G and w. The most expressive of the set.",
    "familjen": "Tight Scandinavian grotesque with quirky terminals. Shortest wordmark.",
    "unbounded": "Wide geometric display. Bold rounded presence, widest lockup.",
    "sora": "Futuristic tech geometric. Calm and even, cool tone.",
    "parkinsans": "Rounded and friendly. Distinctive a and G, softest voice.",
    "martian": "Monospace wildcard. Instantly reads as CLI and gateway tooling. wdth 75 keeps it compact.",
    "dela": "Ultra-black display statement. Heaviest and loudest, hard to pair quietly.",
}
FAMILY = {"instrument": "Instrument Sans", "outfit": "Outfit", "space": "Space Grotesk", "syne": "Syne",
          "familjen": "Familjen Grotesk", "unbounded": "Unbounded", "sora": "Sora",
          "parkinsans": "Parkinsans", "martian": "Martian Mono", "dela": "Dela Gothic One"}
GF = ("family=Instrument+Sans:wght@600&family=Outfit:wght@600&family=Space+Grotesk:wght@600&"
      "family=Syne:wght@600&family=Familjen+Grotesk:wght@600&family=Unbounded:wght@600&"
      "family=Sora:wght@600&family=Parkinsans:wght@600&family=Martian+Mono:wght@600&"
      "family=Dela+Gothic+One&display=swap")

def letters_svg(face, cls):
    return "".join(f'<path class="{cls}" d="{l["d"]}"/>' for l in WM[face]["letters"] if l["d"])

def specimen_svg(face, cap_px=40):
    w = WM[face]; sc = cap_px / w["cap"]
    bw, bh = w["maxx"] - w["minx"], w["maxy"] - w["miny"]
    return (f'<svg width="{bw*sc:.1f}" height="{bh*sc:.1f}" viewBox="{w["minx"]:.2f} {w["miny"]:.2f} {bw:.2f} {bh:.2f}" '
            f'aria-label="OpenGateway in {w["label"]}">{letters_svg(face, "spec")}</svg>')

def lockup_parts(face):
    w = WM[face]
    tx = 27.41 + GAP - w["minx"]
    x0, x1 = 2.5, 27.41 + GAP + (w["maxx"] - w["minx"]) + 2.1
    y0, y1 = 1.4, max(w["maxy"], 28.5) + 2.1
    body = (f'<path class="mk-arch" d="{ARCH}"/><circle class="mk-dot" cx="{DX}" cy="{DY}" r="{DR}"/>'
            f'<g transform="translate({tx:.2f} 0)">{letters_svg(face, "mk-l")}</g>')
    return body, (x0, y0, x1 - x0, y1 - y0)

def lockup_svg(face, theme, h=64):
    body, (x, y, w, hh) = lockup_parts(face)
    return (f'<svg class="lock" width="{w/hh*h:.1f}" height="{h}" viewBox="{x:.2f} {y:.2f} {w:.2f} {hh:.2f}" '
            f'data-theme="{theme}" aria-label="OpenGateway lockup in {WM[face]["label"]}">{body}</svg>')

def rows():
    base = WM["instrument"]["advance"]
    out = []
    for f in ORDER:
        w = WM[f]
        pct = round(w["advance"] / base * 100)
        out.append(f"""<div class="row">
  <div class="meta"><b>{w["label"]}</b><span class="chip">{pct}% width</span><p>{NOTES[f]}</p></div>
  <div class="specwrap">{specimen_svg(f)}</div>
</div>""")
    return "\n".join(out)

def lockups():
    out = []
    for f in ORDER:
        out.append(f"""<div class="card">
  <h2>{WM[f]["label"]}</h2>
  <div class="tiles">{lockup_svg(f, "dark")}{lockup_svg(f, "light")}</div>
</div>""")
    return "\n".join(out)

def sizes():
    out = []
    for f in ORDER:
        fam = FAMILY[f]
        txt = "".join(f'<span class="s{s}">OpenGateway</span>' for s in (20, 16, 13))
        out.append(f"""<div class="row"><div class="meta"><b>{WM[f]["label"]}</b></div>
  <div class="livewrap" style='font-family:"{fam}",sans-serif'>{txt}
  <span class="s13 dim">Routing, guardrails, audit logs. OpenAI-compatible.</span></div></div>""")
    return "\n".join(out)

HTML = f"""<!doctype html>
<html lang="en" data-theme="dark">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>OpenGateway - typeface exploration</title>
<link rel="stylesheet" href="https://fonts.googleapis.com/css2?{GF}">
<style>
:root{{--bg:#0B0B0C;--text:#EDEBE6;--text2:#A0A0A6;--text3:#6E6E76;--surface:#121214;--surface2:#17171A;--line:#232327;--o:#FF5A1F}}
[data-theme=light]{{--bg:#F5F5F4;--text:#151517;--text2:#55555C;--text3:#8A8A92;--surface:#FFFFFF;--surface2:#EDECEA;--line:#DCDBD8;--o:#CC3A06}}
*{{box-sizing:border-box}}
body{{margin:0;background:var(--bg);color:var(--text);font:14px/1.45 "Instrument Sans",system-ui,sans-serif;-webkit-font-smoothing:antialiased}}
header{{position:sticky;top:0;z-index:2;background:var(--bg);border-bottom:1px solid var(--line);padding:14px 24px;display:flex;align-items:baseline;gap:16px;flex-wrap:wrap}}
h1{{font-size:20px;font-weight:600;letter-spacing:-.01em;margin:0}}
.sub{{color:var(--text3);font-size:12px}}
.spacer{{flex:1}}
button{{font:inherit;font-weight:500;color:var(--text);background:var(--surface2);border:1px solid var(--line);border-radius:6px;padding:6px 12px;cursor:pointer}}
main{{padding:8px 24px 48px;max-width:1180px;margin:0 auto}}
h2.sec{{font-size:13px;font-weight:600;letter-spacing:.08em;text-transform:uppercase;color:var(--text2);margin:32px 0 4px}}
.secnote{{color:var(--text3);font-size:12px;margin:0 0 12px}}
.row{{display:flex;gap:24px;align-items:center;padding:14px 0;border-bottom:1px solid var(--line)}}
.meta{{width:250px;flex:none}}.meta b{{font-size:13px;display:block}}
.meta p{{margin:6px 0 0;color:var(--text2);font-size:12px;line-height:1.45}}
.chip{{display:inline-block;font-size:11px;font-weight:500;padding:1px 7px;border-radius:999px;background:var(--surface2);color:var(--text3);margin-top:4px}}
.specwrap{{flex:1;overflow-x:auto;padding:4px 0}}
.spec{{fill:var(--text)}}
.grid{{display:grid;grid-template-columns:repeat(auto-fill,minmax(360px,1fr));gap:14px;margin-top:12px}}
.card{{background:var(--surface);border:1px solid var(--line);border-radius:10px;padding:12px}}
.card h2{{font-size:13px;font-weight:600;margin:0 0 10px}}
.tiles{{display:flex;flex-direction:column;gap:8px}}
.lock[data-theme=dark]{{background:#0B0B0C;border-radius:8px;padding:10px 12px}}
.lock[data-theme=light]{{background:#F5F5F4;border-radius:8px;padding:10px 12px}}
.mk-arch{{fill:none;stroke-width:4.358;stroke-linecap:round;stroke-linejoin:round}}
.lock[data-theme=dark] .mk-arch{{stroke:#EDEBE6}}.lock[data-theme=dark] .mk-dot{{fill:#FF5A1F}}.lock[data-theme=dark] .mk-l{{fill:#EDEBE6}}
.lock[data-theme=light] .mk-arch{{stroke:#151517}}.lock[data-theme=light] .mk-dot{{fill:#CC3A06}}.lock[data-theme=light] .mk-l{{fill:#151517}}
.livewrap{{flex:1;display:flex;align-items:baseline;gap:22px;flex-wrap:wrap}}
.s20{{font-size:20px;font-weight:600}}.s16{{font-size:16px;font-weight:600}}.s13{{font-size:13px;font-weight:600}}
.dim{{color:var(--text2);font-weight:400}}
</style>
</head>
<body>
<header>
  <h1>OpenGateway - typeface exploration</h1>
  <span class="sub">10 faces, SemiBold 600 where variable. Wordmarks outlined at matched cap height (40px).</span>
  <span class="spacer"></span>
  <button onclick="let e=document.documentElement;e.dataset.theme=e.dataset.theme==='dark'?'light':'dark'">Toggle theme</button>
</header>
<main>
  <h2 class="sec">Wordmark specimens</h2>
  <p class="secnote">Same cap height, so width and letterform differences read directly. Percentage is wordmark width against the Instrument Sans control.</p>
{rows()}

  <h2 class="sec">Lockups with the mark</h2>
  <p class="secnote">Round-4 foot-plain arch, mark 1.15x the font size, 2% tracking. Dark and light tiles.</p>
  <div class="grid">
{lockups()}
  </div>

  <h2 class="sec">Small sizes</h2>
  <p class="secnote">Live text where the logo actually lives - nav, footer, body.</p>
{sizes()}
</main>
</body>
</html>
"""
open(os.path.join(HERE, "typeface.html"), "w").write(HTML)
print("wrote typeface.html", len(HTML), "bytes,", len(ORDER), "faces")
