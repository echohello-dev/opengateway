#!/usr/bin/env python3
"""OpenGateway font-pairing exploration. Each pairing is a mini brand board shown side by side:
outlined wordmark + foot-plain lockup (from wordmarks.json) next to a live type stack -
heading in the wordmark face, body in the companion face, code in the mono face.
Same copy in every board, so only the type differs.
Run: python3 pairing.py          (needs wordmarks.json from wordmark.py)
Writes pairing.html next to itself."""
import json, os

HERE = os.path.dirname(os.path.abspath(__file__))
WM = json.load(open(os.path.join(HERE, "wordmarks.json")))

ARCH = "M6.769 26.321V14.910a9.231 9.231 0 0 1 18.462 0V16.575"
DX, DY, DR = 25.231, 24.974, 3.526
GAP = 8.5

FAM = {"instrument": "Instrument Sans", "inter": "Inter", "publicsans": "Public Sans", "outfit": "Outfit",
       "familjen": "Familjen Grotesk", "sora": "Sora", "space": "Space Grotesk", "syne": "Syne",
       "martian": "Martian Mono", "unbounded": "Unbounded", "parkinsans": "Parkinsans", "dela": "Dela Gothic One",
       "ibmplexmono": "IBM Plex Mono", "jetbrains": "JetBrains Mono", "spacemono": "Space Mono"}
GF = ("family=Space+Grotesk:wght@400;500;600;700&family=Instrument+Sans:wght@400;500;600&"
      "family=Inter:wght@400;500;600&family=IBM+Plex+Sans:wght@400;500;600&family=Public+Sans:wght@400;500;600&"
      "family=Outfit:wght@400;500;600&family=Familjen+Grotesk:wght@400;500;600;700&family=Sora:wght@400;500;600&"
      "family=Syne:wght@400;500;600;700&family=Martian+Mono:wght@400;500;600&family=Unbounded:wght@400;500;600&"
      "family=Parkinsans:wght@400;500;600&family=Dela+Gothic+One&family=IBM+Plex+Mono:wght@400;500&"
      "family=JetBrains+Mono:wght@400;500&family=Space+Mono:wght@400;700&display=swap")

# (wordmark, body, mono, tag, note) - same copy everywhere so the type is the only variable
PAIRS = [
    ("space", "instrument", "ibmplexmono", "Recommended",
     "The balanced system. Space Grotesk quirks carry the personality, Instrument Sans keeps the UI calm, Plex Mono fits API docs."),
    ("space", "inter", "jetbrains", "Dev-standard",
     "The same wordmark against the most familiar dev trio. Inter disappears in the UI, JetBrains Mono feels like the IDE."),
    ("syne", "familjen", "spacemono", "Expressive editorial",
     "Loudest voice on the page. Syne headlines, Familjen body copy, Space Mono as the maker-y accent. Artsy, opinionated."),
    ("martian", "outfit", "martian", "Terminal identity",
     "One voice from CLI to docs: mono everywhere it counts, Outfit softens the UI so it does not read as a terminal emulator."),
    ("unbounded", "sora", "ibmplexmono", "Geometric futurist",
     "Wide display wordmark with a cool, even body. Long lockup - give it room on the marketing site."),
    ("familjen", "publicsans", "ibmplexmono", "Compact industrious",
     "Tightest lockup of the set (93% width) with two workhorse grotesques. Quiet, dense, product-like."),
    ("sora", "instrument", "jetbrains", "Quiet tech",
     "Even-tempered everywhere. Nothing shouts - the mark does all the branding."),
    ("parkinsans", "outfit", "spacemono", "Friendly gateway",
     "Softest pairing. Rounded wordmark plus Outfit reads approachable, good for onboarding-heavy products."),
    ("dela", "outfit", "ibmplexmono", "Statement",
     "Max-volume wordmark against a quiet UI. The contrast is the idea - use the lockup sparingly, at size."),
]

def letters_svg(face, cls):
    return "".join(f'<path class="{cls}" d="{l["d"]}"/>' for l in WM[face]["letters"] if l["d"])

def lockup_svg(face, theme, h=52):
    w = WM[face]
    tx = 27.41 + GAP - w["minx"]
    x0, x1 = 2.5, 27.41 + GAP + (w["maxx"] - w["minx"]) + 2.1
    y0, y1 = 1.4, max(w["maxy"], 28.5) + 2.1
    body = (f'<path class="mk-arch" d="{ARCH}"/><circle class="mk-dot" cx="{DX}" cy="{DY}" r="{DR}"/>'
            f'<g transform="translate({tx:.2f} 0)">{letters_svg(face, "mk-l")}</g>')
    return (f'<svg class="lock" data-theme="{theme}" width="{(x1-x0)/(y1-y0)*h:.1f}" height="{h}" '
            f'viewBox="{x0:.2f} {y0:.2f} {x1-x0:.2f} {y1-y0:.2f}" aria-label="OpenGateway lockup">{body}</svg>')

def card(i, wm, body, mono, tag, note):
    hb, mb, wb = FAM[body], FAM[mono], FAM[wm]
    return f"""<article class="pair">
  <header><b>#{i}</b> <span class="wmname">{wb}</span> <span class="plus">+</span> <span class="bdname">{hb}</span> <span class="plus">+</span> <span class="mnname">{mb}</span>
  <span class="chip">{tag}</span></header>
  <div class="cols">
    <div class="left">{lockup_svg(wm, "dark")}{lockup_svg(wm, "light")}</div>
    <div class="right">
      <h3 style='font-family:"{wb}"'>Ship the gateway.</h3>
      <p style='font-family:"{hb}"'>OpenGateway adds SSO, audit logs, guardrails and routing to any AI app. OpenAI-compatible, every feature free, MIT forever.</p>
      <pre style='font-family:"{mb}"'>$ pip install opengateway &amp;&amp; og serve --port 8080</pre>
      <button style='font-family:"{hb}"'>Quick Start</button>
    </div>
  </div>
  <p class="note">{note}</p>
</article>"""

cards = "\n".join(card(i + 1, *p) for i, p in enumerate(PAIRS))

HTML = f"""<!doctype html>
<html lang="en" data-theme="dark">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>OpenGateway - font pairings</title>
<link rel="stylesheet" href="https://fonts.googleapis.com/css2?{GF}">
<style>
:root{{--bg:#0B0B0C;--text:#EDEBE6;--text2:#A0A0A6;--text3:#6E6E76;--surface:#121214;--surface2:#17171A;--line:#232327;--o:#FF5A1F}}
[data-theme=light]{{--bg:#F5F5F4;--text:#151517;--text2:#55555C;--text3:#8A8A92;--surface:#FFFFFF;--surface2:#EDECEA;--line:#DCDBD8;--o:#CC3A06}}
*{{box-sizing:border-box}}
body{{margin:0;background:var(--bg);color:var(--text);font:14px/1.45 "Instrument Sans",system-ui,sans-serif;-webkit-font-smoothing:antialiased}}
header.top{{position:sticky;top:0;z-index:2;background:var(--bg);border-bottom:1px solid var(--line);padding:14px 24px;display:flex;align-items:baseline;gap:16px;flex-wrap:wrap}}
h1{{font-size:20px;font-weight:600;letter-spacing:-.01em;margin:0}}
.sub{{color:var(--text3);font-size:12px}}
.spacer{{flex:1}}
button.tgl{{font:inherit;font-weight:500;color:var(--text);background:var(--surface2);border:1px solid var(--line);border-radius:6px;padding:6px 12px;cursor:pointer}}
main{{padding:16px 24px 48px;max-width:1240px;margin:0 auto}}
.grid{{display:grid;grid-template-columns:repeat(auto-fill,minmax(540px,1fr));gap:16px}}
.pair{{background:var(--surface);border:1px solid var(--line);border-radius:10px;padding:14px}}
.pair>header{{font-size:12px;color:var(--text3);margin-bottom:10px;display:flex;align-items:baseline;gap:6px;flex-wrap:wrap}}
.pair>header b{{color:var(--text2)}}
.wmname{{color:var(--text);font-weight:600}}.bdname,.mnname{{color:var(--text2);font-weight:500}}
.plus{{color:var(--text3)}}
.chip{{font-size:11px;font-weight:500;padding:1px 8px;border-radius:999px;background:var(--surface2);color:var(--text3);margin-left:auto}}
.cols{{display:flex;gap:14px;align-items:stretch}}
.left{{flex:none;display:flex;flex-direction:column;gap:8px}}
.lock[data-theme=dark]{{background:#0B0B0C;border-radius:8px;padding:8px 10px}}
.lock[data-theme=light]{{background:#F5F5F4;border-radius:8px;padding:8px 10px}}
.mk-arch{{fill:none;stroke-width:4.358;stroke-linecap:round;stroke-linejoin:round}}
.lock[data-theme=dark] .mk-arch{{stroke:#EDEBE6}}.lock[data-theme=dark] .mk-dot{{fill:#FF5A1F}}.lock[data-theme=dark] .mk-l{{fill:#EDEBE6}}
.lock[data-theme=light] .mk-arch{{stroke:#151517}}.lock[data-theme=light] .mk-dot{{fill:#CC3A06}}.lock[data-theme=light] .mk-l{{fill:#151517}}
.right{{flex:1;min-width:0;display:flex;flex-direction:column;gap:8px;justify-content:center}}
.right h3{{font-size:23px;font-weight:600;letter-spacing:-.01em;margin:0;line-height:1.15}}
.right p{{font-size:13px;line-height:1.5;margin:0;color:var(--text2)}}
.right pre{{font-size:11.5px;line-height:1.5;margin:0;padding:8px 10px;border:1px solid var(--line);border-radius:6px;background:var(--surface2);color:var(--text2);overflow-x:auto;white-space:pre}}
.right button{{font-size:13px;font-weight:500;color:var(--text);background:var(--surface2);border:1px solid var(--line);border-radius:6px;padding:7px 14px;cursor:pointer;align-self:flex-start}}
.note{{margin:10px 0 0;color:var(--text3);font-size:12px;line-height:1.5}}
</style>
</head>
<body>
<header class="top">
  <h1>OpenGateway - font pairings</h1>
  <span class="sub">Wordmark face + body face + mono face. Same copy in every board. 9 pairings, side by side.</span>
  <span class="spacer"></span>
  <button class="tgl" onclick="let e=document.documentElement;e.dataset.theme=e.dataset.theme==='dark'?'light':'dark'">Toggle theme</button>
</header>
<main>
  <div class="grid">
{cards}
  </div>
</main>
</body>
</html>
"""
open(os.path.join(HERE, "pairing.html"), "w").write(HTML)
print("wrote pairing.html", len(HTML), "bytes,", len(PAIRS), "pairings")
