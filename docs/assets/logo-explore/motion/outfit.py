#!/usr/bin/env python3
"""Outfit deep-dive: weights, geometric neighbours and Outfit-as-wordmark pairings, side by side.
Run: python3 outfit.py          (needs wordmarks.json + wordmarks-extra.json from wordmark.py)
Writes outfit.html next to itself."""
import json, os

HERE = os.path.dirname(os.path.abspath(__file__))
WM = json.load(open(os.path.join(HERE, "wordmarks.json")))
WX = json.load(open(os.path.join(HERE, "wordmarks-extra.json")))
ALL = {**WM, **WX}

ARCH = "M6.769 26.321V14.910a9.231 9.231 0 0 1 18.462 0V16.575"
DX, DY, DR = 25.231, 24.974, 3.526
GAP = 8.5

WEIGHTS = ["outfit500", "outfit", "outfit700", "outfit800"]
WEIGHT_NOTE = {
    "outfit500": "Medium. Lighter and more elegant; the arch mark may out-weigh the word.",
    "outfit":    "SemiBold. The current brand setting - balanced next to the 4.358 stroke.",
    "outfit700": "Bold. Stronger lockup, better at small sizes and on dark tiles.",
    "outfit800": "ExtraBold. Display territory; the letters start competing with the mark.",
}
NEIGH = ["outfit", "urbanist", "figtree", "jost", "onest", "hanken", "poppins"]
NEIGH_NOTE = {
    "outfit":   "Outfit - the anchor. Circular geometric, high x-height, open counters.",
    "urbanist": "Urbanist - slightly softer curves, a touch more humanist warmth.",
    "figtree":  "Figtree - friendlier terminals, the closest all-rounder to Outfit.",
    "jost":     "Jost - Futura lineage, narrower, more geometric severity.",
    "onest":   "Onest - Outfit-like geometry with more even texture.",
    "hanken":   "Hanken Grotesk - compact and grotesque rather than geometric.",
    "poppins":  "Poppins - the classic geometric comparison; wider and rounder.",
}
FAM = {"outfit": "Outfit", "instrument": "Instrument Sans", "inter": "Inter", "plexsans": "IBM Plex Sans",
       "publicsans": "Public Sans", "sora": "Sora", "plexmono": "IBM Plex Mono", "jetbrains": "JetBrains Mono",
       "spacemono": "Space Mono"}
GF = ("family=Outfit:wght@400;500;600;700;800&family=Instrument+Sans:wght@400;500;600&family=Inter:wght@400;500;600&"
      "family=IBM+Plex+Sans:wght@400;500;600&family=Public+Sans:wght@400;500;600&family=Sora:wght@400;500;600&"
      "family=IBM+Plex+Mono:wght@400;500&family=JetBrains+Mono:wght@400;500&family=Space+Mono:wght@400;700&display=swap")

# Outfit as the wordmark/heading face: (body, mono, tag, note)
PAIRS = [
    ("instrument", "plexmono", "Recommended",
     "Outfit stays the voice of the brand, Instrument Sans keeps the UI quiet, Plex Mono fits API docs."),
    ("inter", "jetbrains", "Dev-standard",
     "The familiar developer stack under an Outfit wordmark. Inter disappears, JetBrains feels like home."),
    ("plexsans", "plexmono", "Family cohesion",
     "One superfamily below the wordmark - even texture, zero clashing, slightly corporate."),
    ("publicsans", "spacemono", "Open-source stack",
     "Public Sans and Space Mono read civic and maker-ish; a fully open-source type stack."),
    ("sora", "plexmono", "Soft-futurist",
     "Sora body under Outfit headings - two geometrics, subtle contrast in the tails."),
]

def letters_svg(face, cls):
    return "".join(f'<path class="{cls}" d="{l["d"]}"/>' for l in ALL[face]["letters"] if l["d"])

def specimen_svg(face, cap_px=36):
    w = ALL[face]; sc = cap_px / w["cap"]
    bw, bh = w["maxx"] - w["minx"], w["maxy"] - w["miny"]
    return (f'<svg class="spec" width="{bw*sc:.1f}" height="{bh*sc:.1f}" viewBox="{w["minx"]:.2f} {w["miny"]:.2f} {bw:.2f} {bh:.2f}" '
            f'aria-label="OpenGateway in {w["label"]}">{letters_svg(face, "spec")}</svg>')

def lockup_svg(face, theme, h=52):
    w = ALL[face]
    tx = 27.41 + GAP - w["minx"]
    x0, x1 = 2.5, 27.41 + GAP + (w["maxx"] - w["minx"]) + 2.1
    y0, y1 = 1.4, max(w["maxy"], 28.5) + 2.1
    body = (f'<path class="mk-arch" d="{ARCH}"/><circle class="mk-dot" cx="{DX}" cy="{DY}" r="{DR}"/>'
            f'<g transform="translate({tx:.2f} 0)">{letters_svg(face, "mk-l")}</g>')
    return (f'<svg class="lock" data-theme="{theme}" width="{(x1-x0)/(y1-y0)*h:.1f}" height="{h}" '
            f'viewBox="{x0:.2f} {y0:.2f} {x1-x0:.2f} {y1-y0:.2f}">{body}</svg>')

base = ALL["outfit"]["advance"]
weights = "\n".join(f"""<div class="row">
  <div class="meta"><b>{ALL[f]["label"]}</b><span class="chip">{round(ALL[f]["advance"]/base*100)}% width</span><p>{WEIGHT_NOTE[f]}</p></div>
  <div class="specwrap">{specimen_svg(f)}</div>
  <div class="tiles">{lockup_svg(f, "dark")}{lockup_svg(f, "light")}</div>
</div>""" for f in WEIGHTS)

neigh = "\n".join(f"""<div class="row">
  <div class="meta"><b>{ALL[f]["label"]}</b><span class="chip">{round(ALL[f]["advance"]/base*100)}% width</span><p>{NEIGH_NOTE[f]}</p></div>
  <div class="specwrap">{specimen_svg(f)}</div>
</div>""" for f in NEIGH)

def pair_card(i, body, mono, tag, note):
    hb, mb = FAM[body], FAM[mono]
    return f"""<article class="pair">
  <header><b>#{i}</b> <span class="wmname">Outfit</span> <span class="plus">+</span> <span class="bdname">{hb}</span> <span class="plus">+</span> <span class="mnname">{mb}</span><span class="chip">{tag}</span></header>
  <div class="cols">
    <div class="left">{lockup_svg("outfit", "dark")}{lockup_svg("outfit", "light")}</div>
    <div class="right">
      <h3 style='font-family:"Outfit"'>Ship the gateway.</h3>
      <p style='font-family:"{hb}"'>OpenGateway adds SSO, audit logs, guardrails and routing to any AI app. OpenAI-compatible, every feature free, MIT forever.</p>
      <pre style='font-family:"{mb}"'>$ pip install opengateway &amp;&amp; og serve --port 8080</pre>
      <button style='font-family:"{hb}"'>Quick Start</button>
    </div>
  </div>
  <p class="note">{note}</p>
</article>"""

pairs = "\n".join(pair_card(i + 1, *p) for i, p in enumerate(PAIRS))

small = "\n".join(f"""<div class="row"><div class="meta"><b>{ALL[f]["label"]}</b></div>
  <div class="livewrap" style='font-family:"Outfit";font-variation-settings:"wght" {"500" if f=="outfit500" else "600" if f=="outfit" else "700" if f=="outfit700" else "800"}'>
  <span class="s20">OpenGateway</span><span class="s16">OpenGateway</span><span class="s13">OpenGateway</span>
  <span class="s13 dim">Routing, guardrails, audit logs. OpenAI-compatible.</span></div></div>""" for f in WEIGHTS)

HTML = f"""<!doctype html>
<html lang="en" data-theme="dark">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>OpenGateway - Outfit deep dive</title>
<link rel="stylesheet" href="https://fonts.googleapis.com/css2?{GF}">
<style>
:root{{--bg:#0B0B0C;--text:#EDEBE6;--text2:#A0A0A6;--text3:#6E6E76;--surface:#121214;--surface2:#17171A;--line:#232327}}
[data-theme=light]{{--bg:#F5F5F4;--text:#151517;--text2:#55555C;--text3:#8A8A92;--surface:#FFFFFF;--surface2:#EDECEA;--line:#DCDBD8}}
*{{box-sizing:border-box}}
body{{margin:0;background:var(--bg);color:var(--text);font:14px/1.45 "Outfit",system-ui,sans-serif;-webkit-font-smoothing:antialiased}}
header.top{{position:sticky;top:0;z-index:2;background:var(--bg);border-bottom:1px solid var(--line);padding:14px 24px;display:flex;align-items:baseline;gap:16px;flex-wrap:wrap}}
h1{{font-size:20px;font-weight:600;letter-spacing:-.01em;margin:0}}
.sub{{color:var(--text3);font-size:12px}}
.spacer{{flex:1}}
button.tgl{{font:inherit;font-weight:500;color:var(--text);background:var(--surface2);border:1px solid var(--line);border-radius:6px;padding:6px 12px;cursor:pointer}}
main{{padding:8px 24px 48px;max-width:1180px;margin:0 auto}}
h2.sec{{font-size:13px;font-weight:600;letter-spacing:.08em;text-transform:uppercase;color:var(--text2);margin:32px 0 4px}}
.secnote{{color:var(--text3);font-size:12px;margin:0 0 12px}}
.row{{display:flex;gap:20px;align-items:center;padding:14px 0;border-bottom:1px solid var(--line)}}
.meta{{width:230px;flex:none}}.meta b{{font-size:13px;display:block}}
.meta p{{margin:6px 0 0;color:var(--text2);font-size:12px;line-height:1.45}}
.chip{{display:inline-block;font-size:11px;font-weight:500;padding:1px 7px;border-radius:999px;background:var(--surface2);color:var(--text3);margin-top:4px}}
.pair>header .chip{{margin:0 0 0 auto}}
.specwrap{{flex:1;overflow-x:auto;padding:4px 0}}
.spec{{fill:var(--text)}}
.tiles{{flex:none;display:flex;flex-direction:column;gap:6px}}
.lock[data-theme=dark]{{background:#0B0B0C;border-radius:8px;padding:8px 10px}}
.lock[data-theme=light]{{background:#F5F5F4;border-radius:8px;padding:8px 10px}}
.mk-arch{{fill:none;stroke-width:4.358;stroke-linecap:round;stroke-linejoin:round}}
.lock[data-theme=dark] .mk-arch{{stroke:#EDEBE6}}.lock[data-theme=dark] .mk-dot{{fill:#FF5A1F}}.lock[data-theme=dark] .mk-l{{fill:#EDEBE6}}
.lock[data-theme=light] .mk-arch{{stroke:#151517}}.lock[data-theme=light] .mk-dot{{fill:#CC3A06}}.lock[data-theme=light] .mk-l{{fill:#151517}}
.grid{{display:grid;grid-template-columns:repeat(auto-fill,minmax(540px,1fr));gap:16px}}
.pair{{background:var(--surface);border:1px solid var(--line);border-radius:10px;padding:14px}}
.pair>header{{font-size:12px;color:var(--text3);margin-bottom:10px;display:flex;align-items:baseline;gap:6px;flex-wrap:wrap}}
.pair>header b{{color:var(--text2)}}
.wmname{{color:var(--text);font-weight:600}}.bdname,.mnname{{color:var(--text2);font-weight:500}}
.plus{{color:var(--text3)}}
.cols{{display:flex;gap:14px;align-items:stretch}}
.left{{flex:none;display:flex;flex-direction:column;gap:8px}}
.right{{flex:1;min-width:0;display:flex;flex-direction:column;gap:8px;justify-content:center}}
.right h3{{font-family:"Outfit";font-size:23px;font-weight:600;letter-spacing:-.01em;margin:0;line-height:1.15}}
.right p{{font-size:13px;line-height:1.5;margin:0;color:var(--text2)}}
.right pre{{font-size:11.5px;line-height:1.5;margin:0;padding:8px 10px;border:1px solid var(--line);border-radius:6px;background:var(--surface2);color:var(--text2);overflow-x:auto;white-space:pre}}
.right button{{font-size:13px;font-weight:500;color:var(--text);background:var(--surface2);border:1px solid var(--line);border-radius:6px;padding:7px 14px;cursor:pointer;align-self:flex-start}}
.note{{margin:10px 0 0;color:var(--text3);font-size:12px;line-height:1.5}}
.livewrap{{flex:1;display:flex;align-items:baseline;gap:22px;flex-wrap:wrap}}
.s20{{font-size:20px;font-weight:600}}.s16{{font-size:16px;font-weight:600}}.s13{{font-size:13px;font-weight:600}}
.dim{{color:var(--text2);font-weight:400}}
</style>
</head>
<body>
<header class="top">
  <h1>Outfit deep dive</h1>
  <span class="sub">Weights, geometric neighbours and Outfit-as-wordmark pairings. Same copy everywhere.</span>
  <span class="spacer"></span>
  <button class="tgl" onclick="let e=document.documentElement;e.dataset.theme=e.dataset.theme==='dark'?'light':'dark'">Toggle theme</button>
</header>
<main>
  <h2 class="sec">Outfit weights</h2>
  <p class="secnote">Wordmark outlined at matched cap height, lockup with the foot-plain mark beside it.</p>
{weights}

  <h2 class="sec">Outfit neighbourhood</h2>
  <p class="secnote">Geometric sans relatives at SemiBold, so Outfit's own quirks are easy to spot. Widths are against Outfit SemiBold.</p>
{neigh}

  <h2 class="sec">Outfit as the wordmark</h2>
  <p class="secnote">Five systems under the same Outfit heading - side by side, identical copy.</p>
  <div class="grid">
{pairs}
  </div>

  <h2 class="sec">Small sizes</h2>
  <p class="secnote">Where the logo actually lives - nav, footer, body.</p>
{small}
</main>
</body>
</html>
"""
open(os.path.join(HERE, "outfit.html"), "w").write(HTML)
print("wrote outfit.html", len(HTML), "bytes")
