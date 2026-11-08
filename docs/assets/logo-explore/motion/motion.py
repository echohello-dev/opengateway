#!/usr/bin/env python3
"""OpenGateway logo motion. Generates standalone animated SVGs (dark and light, two wordmark faces) and a self-contained
preview page with synthesised sound (Web Audio, no audio files).

Mark geometry is the golden foot-plain mark (see ../gen.py round 4): stroke 4.358 on a 32 unit box, plain dot, no outline.
Run:  python3 motion.py          (needs wordmarks.json from wordmark.py)

Motion rules used (Emil Kowalski): ease-out for entering, ease-in-out for on-screen movement, linear for constant motion,
transform/opacity only (plus stroke-dashoffset for the draw-on), nothing scales from 0, reduced motion shows the static mark.
Exception: the drop in 'roll' uses ease-in for gravity because it is a physical event in a brand moment, not UI feedback.
"""
import json, os

HERE = os.path.dirname(os.path.abspath(__file__))
WM = json.load(open(os.path.join(HERE, "wordmarks.json")))

EO = "cubic-bezier(0.23,1,0.32,1)"        # strong ease-out
EIO = "cubic-bezier(0.77,0,0.175,1)"      # strong ease-in-out
EBACK = "cubic-bezier(0.34,1.56,0.64,1)"  # easeOutBack, for the dot pop only
EIQ = "cubic-bezier(0.55,0.085,0.68,0.53)"  # easeInQuad, gravity only

ARCH = "M6.769 26.321V14.910a9.231 9.231 0 0 1 18.462 0V16.575"
SW = 4.358
DX, DY, DR = 25.231, 24.974, 3.526
LEG = "M25.231 16.575V22.4"
# ring -> arch morph. Both paths share one command structure (M C A C) so the browser can interpolate them.
RING_D = "M16 24.141C10.902 24.141 6.769 20.008 6.769 14.91A9.231 9.231 0 0 1 25.231 14.91C25.231 20.008 21.098 24.141 16 24.141"
ARCH_M = "M6.769 26.321C6.769 22.5 6.769 18.7 6.769 14.91A9.231 9.231 0 0 1 25.231 14.91C25.231 15.5 25.231 16 25.231 16.575"
THEMES = {"dark": {"c": "#EDEBE6", "o": "#FF5A1F", "bg": "#0B0B0C"}, "light": {"c": "#151517", "o": "#CC3A06", "bg": "#F5F5F4"}}
E5, G5, A5, B5, D6, E6 = 659.25, 783.99, 880.0, 987.77, 1174.66, 1318.51
PENTA = [E5, G5, A5, B5, D6, E6, D6, B5, A5, G5, E5]

BASE = (".§-arch{fill:none;stroke:var(--c);stroke-width:%s;stroke-linecap:round;stroke-linejoin:round}"
        ".§-dot{fill:var(--o)}") % SW

# ---- mark animations: css, svg parts, cycle ms, loops, sound schedule --------------------------------------------
def sub(css):
    return css.replace("EIQ", EIQ).replace("EIO", EIO).replace("EBACK", EBACK).replace("EO", EO).replace("SWV", str(SW)).replace("RINGD", RING_D).replace("ARCHD", ARCH_M)

def mark_svg(pre="", mid=""):
    return (f'<g class="§-mark">{pre}<path class="§-arch" pathLength="1" d="{ARCH}"/>{mid}'
            f'<circle class="§-dot" cx="{DX}" cy="{DY}" r="{DR}"/></g>')

M = {}

M["morph"] = dict(
    css=sub(BASE + ".§-arch{stroke-dasharray:1 3;animation:§-ring 650ms EIO 150ms backwards,§-open 600ms EIO 900ms backwards}"
            ".§-dot{transform-box:fill-box;transform-origin:center;animation:§-pop 320ms EBACK backwards}"
            ".§-dotg{animation:§-go 1850ms linear backwards}"
            "@keyframes §-ring{from{stroke-dashoffset:1.06}to{stroke-dashoffset:0}}"
            '@keyframes §-open{from{d:path("RINGD")}to{d:path("ARCHD")}}'
            "@keyframes §-pop{from{opacity:0;transform:scale(.6)}to{opacity:1;transform:scale(1)}}"
            "@keyframes §-go{0%{transform:translate(-9.231px,-10.064px)}67.57%{transform:translate(-9.231px,-10.064px);animation-timing-function:EIO}"
            "83.78%{transform:translate(-9.231px,0);animation-timing-function:EO}100%{transform:translate(0,0)}}"),
    svg=(f'<g class="§-mark"><path class="§-arch" pathLength="1" d="{ARCH_M}"/>'
         f'<g class="§-dotg"><circle class="§-dot" cx="{DX}" cy="{DY}" r="{DR}"/></g></g>'),
    cycle=1900, loop=False,
    audio=[dict(t=0, c="pop", f=E5, g=.40), dict(t=150, c="sweep", d=650, f0=250, f1=900, g=.07),
           dict(t=900, c="sweep", d=600, f0=1400, f1=500, g=.06), dict(t=1550, c="tick", f=G5, g=.08),
           dict(t=1830, c="pop", f=B5, g=.32)])
M["draw"] = dict(
    css=sub(BASE + ".§-arch{stroke-dasharray:1 3;animation:§-draw 900ms EIO 100ms backwards}"
            ".§-dot{transform-box:fill-box;transform-origin:center;animation:§-pop 420ms EBACK 860ms backwards}"
            "@keyframes §-draw{from{stroke-dashoffset:1.06}to{stroke-dashoffset:0}}"
            "@keyframes §-pop{from{opacity:0;transform:scale(.6)}to{opacity:1;transform:scale(1)}}"),
    svg=mark_svg(), cycle=1300, loop=False,
    audio=[dict(t=100, c="sweep", d=900, f0=300, f1=1400, g=.10), dict(t=900, c="pop", f=E5, g=.55)])
M["roll"] = dict(
    css=sub(BASE + ".§-dot{animation:§-fade 140ms EO 100ms backwards,§-roll 1500ms linear 100ms backwards}"
            "@keyframes §-fade{from{opacity:0}to{opacity:1}}"
            "@keyframes §-roll{0%{transform:translate(-9.231px,-12.974px);animation-timing-function:EIQ}"
            "30%{transform:translate(-9.231px,0);animation-timing-function:EO}"
            "42%{transform:translate(-9.231px,-3.2px);animation-timing-function:EIQ}"
            "52%{transform:translate(-9.231px,0);animation-timing-function:EO}"
            "100%{transform:translate(0,0)}}"),
    svg=mark_svg(), cycle=1600, loop=False,
    audio=[dict(t=550, c="thump", g=.5), dict(t=880, c="thump", g=.28, f=170), dict(t=900, c="rumble", d=650, g=.10), dict(t=1560, c="pop", f=E5, g=.32)])
M["pulse"] = dict(
    css=sub(BASE + ".§-halo{fill:var(--o);opacity:0;transform-box:fill-box;transform-origin:center;animation:§-halo 2400ms EO infinite}"
            "@keyframes §-halo{0%{opacity:.4;transform:scale(1)}70%{opacity:0;transform:scale(1.85)}100%{opacity:0;transform:scale(1.85)}}"),
    svg=mark_svg(pre=f'<circle class="§-halo" cx="{DX}" cy="{DY}" r="{DR}"/>'), cycle=2400, loop=True,
    audio=[dict(t=0, c="ping", f=B5, g=.20)])
M["trace"] = dict(
    css=sub(BASE + ".§-trace{fill:none;stroke:var(--o);stroke-width:SWV;stroke-linecap:round;stroke-linejoin:round;stroke-dasharray:.22 3;opacity:0;animation:§-trace 1600ms linear infinite}"
            ".§-dot{transform-box:fill-box;transform-origin:center;animation:§-beat 1600ms EO infinite}"
            "@keyframes §-trace{0%{opacity:1;stroke-dashoffset:.28}75%{opacity:1;stroke-dashoffset:-1.06}75.1%,100%{opacity:0;stroke-dashoffset:-1.06}}"
            "@keyframes §-beat{0%,72%{transform:scale(1)}80%{transform:scale(1.16)}100%{transform:scale(1)}}"),
    svg=mark_svg(mid=f'<path class="§-trace" pathLength="1" d="{ARCH}"/>'), cycle=1600, loop=True,
    audio=[dict(t=0, c="sweep", d=1200, f0=500, f1=2200, g=.06), dict(t=1200, c="ping", f=E6, g=.10)])
M["knock"] = dict(
    css=sub(BASE + ".§-dot{animation:§-knock 3200ms linear infinite}.§-arch{animation:§-thud 3200ms linear infinite}"
            "@keyframes §-knock{0%{transform:translateY(0);animation-timing-function:EIQ}"
            "5%{transform:translateY(-2.5px);animation-timing-function:EO}"
            "10.3%{transform:translateY(0);animation-timing-function:EIQ}"
            "16.25%{transform:translateY(-2.5px);animation-timing-function:EO}"
            "21.25%{transform:translateY(0);animation-timing-function:EIQ}"
            "25.6%{transform:translateY(-1.2px);animation-timing-function:EO}"
            "28.75%,100%{transform:translateY(0)}}"
            "@keyframes §-thud{0%{transform:translateY(0)}5%{transform:translateY(.45px)}8%{transform:translateY(0)}"
            "16.25%{transform:translateY(.45px)}19%{transform:translateY(0)}25.6%{transform:translateY(.25px)}27.5%,100%{transform:translateY(0)}}"),
    svg=mark_svg(), cycle=3200, loop=True,
    audio=[dict(t=160, c="knock", g=.5), dict(t=520, c="knock", g=.42), dict(t=820, c="knock", g=.25)])
M["latch"] = dict(
    css=sub(BASE + ".§-leg{fill:none;stroke:var(--c);stroke-width:SWV;stroke-linecap:round;stroke-dasharray:1 3;stroke-dashoffset:1.06;animation:§-leg 3600ms linear infinite}"
            "@keyframes §-leg{0%{stroke-dashoffset:1.06;animation-timing-function:EO}12%{stroke-dashoffset:0}"
            "62%{stroke-dashoffset:0;animation-timing-function:EIO}76%,100%{stroke-dashoffset:1.06}}"),
    svg=mark_svg(mid=f'<path class="§-leg" pathLength="1" d="{LEG}"/>'), cycle=3600, loop=True,
    audio=[dict(t=430, c="click", g=.35), dict(t=430, c="thump", g=.22, f=120), dict(t=2230, c="click", g=.18), dict(t=2740, c="tick", f=B5, g=.07)])
# the leg is drawn before the dot, so move the dot after it: mark_svg already orders arch, mid, dot
M["connect"] = dict(
    css=sub(BASE + ".§-arch{stroke-dasharray:1 3;animation:§-draw 500ms EIO backwards,§-open 600ms EIO 1200ms backwards,§-thud 2300ms linear backwards}"
            ".§-mark{animation:§-thud2 3300ms linear backwards}"
            ".§-leg{fill:none;stroke:var(--c);stroke-width:SWV;stroke-linecap:round;stroke-dasharray:1 3;stroke-dashoffset:1.06;animation:§-latch 450ms EO 2350ms both}"
            ".§-dot{transform-box:fill-box;transform-origin:center;animation:§-pop 220ms EBACK 400ms backwards,§-press 2300ms linear backwards}"
            ".§-dotg{animation:§-go 2300ms linear backwards}"
            "@keyframes §-draw{from{stroke-dashoffset:1.06}to{stroke-dashoffset:0}}"
            '@keyframes §-open{from{d:path("RINGD")}to{d:path("ARCHD")}}'
            "@keyframes §-pop{from{opacity:0;transform:scale(.6)}to{opacity:1;transform:scale(1)}}"
            "@keyframes §-thud{0%,36.7%{transform:translateY(0)}37.4%{transform:translateY(.5px)}38.5%,100%{transform:translateY(0)}}"
            "@keyframes §-thud2{0%,84.3%{transform:translateY(0)}84.8%{transform:translateY(.6px)}85.6%,100%{transform:translateY(0)}}"
            "@keyframes §-press{0%,30.4%{transform:scale(1)}37.4%{transform:scale(1.12,.78);animation-timing-function:EBACK}47.8%{transform:scale(1)}100%{transform:scale(1)}}"
            "@keyframes §-go{0%,30.4%{transform:translate(-9.231px,-10.064px)}37.4%{transform:translate(-9.231px,-6.4px);animation-timing-function:EBACK}47.8%{transform:translate(-9.231px,-10.064px)}"
            "63%{transform:translate(-9.231px,-10.064px);animation-timing-function:EIO}89.1%{transform:translate(-9.231px,0);animation-timing-function:EO}100%{transform:translate(0,0)}}"
            "@keyframes §-latch{from{stroke-dashoffset:1.06}to{stroke-dashoffset:0}}"),
    svg=(f'<g class="§-mark"><path class="§-arch" pathLength="1" d="{ARCH_M}"/><path class="§-leg" pathLength="1" d="{LEG}"/>'
         f'<g class="§-dotg"><circle class="§-dot" cx="{DX}" cy="{DY}" r="{DR}"/></g></g>'),
    cycle=3300, loop=False,
    audio=[dict(t=430, c="pop", f=E5, g=.30),
           dict(t=860, c="knock", g=.55), dict(t=860, c="click", g=.35), dict(t=860, c="thump", g=.25, f=140),
           dict(t=1060, c="click", g=.28), dict(t=1080, c="tick", f=G5, g=.08),
           dict(t=1200, c="sweep", d=600, f0=1400, f1=500, g=.07),
           dict(t=1780, c="tick", f=B5, g=.08),
           dict(t=2100, c="pop", f=E5, g=.38),
           dict(t=2800, c="click", g=.40), dict(t=2800, c="thump", g=.30, f=120),
           dict(t=2980, c="pluck", f=B5, g=.22), dict(t=3080, c="pluck", f=E5, g=.18)])

# ---- lockups -----------------------------------------------------------------------------------------------------
GAP = 8.5
LETTER_IN = ".§-l{fill:var(--c);animation:§-in 420ms EO calc(980ms + var(--i)*45ms) backwards}@keyframes §-in{from{opacity:0;transform:translateY(4px)}to{opacity:1;transform:translateY(0)}}"
L = {}

L["open"] = dict(base="morph", wrap=True, cycle=2600, loop=False,
                 extra=".§-all{animation:§-slide 800ms EIO 1500ms backwards}"
                       "@keyframes §-slide{from{transform:translateX(SLIDEXpx)}to{transform:translateX(0)}}"
                       ".§-l{fill:var(--c);animation:§-out 420ms EO calc(1750ms + var(--i)*35ms) backwards}"
                       "@keyframes §-out{from{opacity:0;transform:translateX(-12px)}to{opacity:1;transform:translateX(0)}}",
                 audio=M["morph"]["audio"] + [dict(t=1500, c="air", d=800, g=.04)]
                       + [dict(t=1750 + i * 35 + 120, c="tick", f=PENTA[i], g=.05) for i in range(11)]
                       + [dict(t=2350, c="pluck", f=E5, g=.20), dict(t=2500, c="pluck", f=B5, g=.20)])
L["reveal"] = dict(base="draw", extra=LETTER_IN, cycle=1900, loop=False,
                   audio=M["draw"]["audio"] + [dict(t=1000, c="air", d=700, g=.04), dict(t=1250, c="pluck", f=B5, g=.26)])
L["wave"] = dict(base=None, mark="pulse2",
                 extra=".§-l{fill:var(--c);animation:§-wave 3600ms ease-in-out infinite;animation-delay:calc(var(--i)*70ms)}"
                       "@keyframes §-wave{0%{fill:var(--c)}7%{fill:var(--o)}20%,100%{fill:var(--c)}}"
                       ".§-halo{fill:var(--o);opacity:0;transform-box:fill-box;transform-origin:center;animation:§-halo 3600ms EO infinite}"
                       "@keyframes §-halo{0%,28%{opacity:0;transform:scale(1)}30%{opacity:.4;transform:scale(1)}56%{opacity:0;transform:scale(1.85)}100%{opacity:0;transform:scale(1.85)}}",
                 cycle=3600, loop=True,
                 audio=[dict(t=i * 70 + 252, c="tick", f=PENTA[i], g=.10) for i in range(11)] + [dict(t=1100, c="ping", f=B5, g=.14)])
L["emerge"] = dict(base="roll", extra=".§-l{fill:var(--c);animation:§-out 420ms EO calc(1300ms + var(--i)*40ms) backwards}@keyframes §-out{from{opacity:0;transform:translateX(-10px)}to{opacity:1;transform:translateX(0)}}",
                   cycle=2200, loop=False,
                   audio=M["roll"]["audio"] + [dict(t=1300, c="air", d=600, g=.04), dict(t=1850, c="pluck", f=B5, g=.2)])
L["trace"] = dict(base="trace", extra=".§-l{fill:var(--c)}", cycle=1600, loop=True, audio=M["trace"]["audio"])

def lockup_geometry(face):
    w = WM[face]
    tx = 27.41 + GAP - w["minx"]
    x0, x1 = 2.5, 27.41 + GAP + (w["maxx"] - w["minx"]) + 2.1
    y0, y1 = 1.4, max(w["maxy"], 28.5) + 2.1
    return tx, (x0, y0, x1 - x0, y1 - y0)

def letters_svg(face):
    return "".join(f'<path class="§-l" style="--i:{i}" d="{l["d"]}"/>' for i, l in enumerate(WM[face]["letters"]) if l["d"])

def variant(kind, name, face="instrument"):
    """returns (css, body_svg, viewBox) for a variant with class prefix already substituted"""
    p = ("m" if kind == "mark" else "l") + "-" + name
    if kind == "mark":
        d = M[name]; css, body, vb = d["css"], d["svg"], "0 0 32 32"
    else:
        d = L[name]
        mk = M[d["base"]] if d["base"] else dict(css=M["pulse"]["css"].split(".§-halo")[0], svg=M["pulse"]["svg"])
        css = mk["css"] + sub(d["extra"])
        body_mark = mk["svg"]
        tx, vbx = lockup_geometry(face)
        body = body_mark + f'<g transform="translate({tx:.2f} 0)">{letters_svg(face)}</g>'
        if d.get("wrap"):
            body = f'<g class="§-all">{body}</g>'
            css = css.replace("SLIDEX", f"{vbx[0] + vbx[2] / 2 - 16:.2f}")
        vb = " ".join(f"{v:.2f}" for v in vbx)
    return css.replace("§", p), body.replace("§", p), vb

META = {
 ("mark", "morph"):   dict(title="Morph", purpose="Delight", tier="Rare", use="Splash and docs hero. A dot, a ring drawn around it, the ring opens into the arch, and the dot passes through the opening. Plays once.", sound="Pop, a rising draw, a falling unfold, a tick at the turn and a landing note."),
 ("lockup", "open"): dict(title="Morph and open", purpose="Delight", tier="Rare", use="The lead concept. The mark morphs, then the lockup slides to centre as the name unfurls from the gate. Plays once.", sound="The morph sounds, an air swell as it slides, a soft arpeggio across the letters and a closing open fifth."),
 ("mark", "draw"):    dict(title="Draw", purpose="Delight", tier="Rare", use="Splash, onboarding, docs hero. Plays once.", sound="Sweep while the arch draws, pluck when the dot lands."),
 ("mark", "roll"):    dict(title="Drop and roll", purpose="Explanation", tier="Rare", use="Docs hero, empty states. The request enters the gate and settles at its exit. Plays once.", sound="Two thumps, a short roll, a soft settle."),
 ("mark", "pulse"):   dict(title="Pulse", purpose="State: live", tier="Ambient", use="Next to a live request tail or a connected badge only. Static everywhere else.", sound="One ping on first play. Do not loop sound."),
 ("mark", "trace"):   dict(title="Trace", purpose="State: loading", tier="Ambient", use="Loading screen or long startup. Replace with the static mark when done.", sound="Soft sweep and a ping on first play. Do not loop sound."),
 ("mark", "knock"):   dict(title="Knock", purpose="State: retry", tier="Event", use="When a request retries or falls back. Plays once per event.", sound="Three knocks. Keep off by default, it signals a failure."),
 ("mark", "latch"): dict(title="Latch", purpose="State: connected", tier="Event", use="Connection status. The leg latches the gap closed when linked and opens on disconnect.", sound="Latch click on link, lighter release on disconnect."),
 ("mark", "connect"): dict(title="Connect", purpose="Event", tier="Event", use="When a key or provider connects. The dot is the key: it clicks down and up in the lock, the ring opens into the gate, the key exits, and the leg latches closed. Plays once.", sound="A pop as the key appears, a knock and click as it presses down, a lighter click on release, a falling sweep as the gate opens, a landing note, then a latch click and thump as the leg closes home, and a closing fifth."),
 ("lockup", "reveal"):dict(title="Reveal", purpose="Delight", tier="Rare", use="Splash, release video, README banner. Plays once.", sound="Sweep, pop, a soft air swell and an open fifth."),
 ("lockup", "wave"):  dict(title="Wave", purpose="Delight", tier="Ambient", use="Marketing hero on hover. A colour wave runs across the letters, then the dot ripples.", sound="Pentatonic blip per letter, then a ping. Hover only."),
 ("lockup", "emerge"):dict(title="Emerge", purpose="Explanation", tier="Rare", use="Splash. The dot rolls out and the name slides out of the gate behind it. Plays once.", sound="The roll sounds, then an air swell and a closing fifth."),
 ("lockup", "trace"): dict(title="Trace lockup", purpose="State: loading", tier="Ambient", use="Full-screen loading with the name visible.", sound="As the mark trace. First play only."),
}

STANDALONE_RM = "@media (prefers-reduced-motion:reduce){*{animation:none!important}}"
def standalone(kind, name, theme, face):
    css, body, vb = variant(kind, name, face)
    t = THEMES[theme]; w, h = [float(v) for v in vb.split()[2:]]
    scale = 8 if kind == "mark" else 4
    return (f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="{vb}" width="{w*scale:.0f}" height="{h*scale:.0f}" role="img" aria-label="OpenGateway">'
            f'<style>svg{{--c:{t["c"]};--o:{t["o"]}}}{css}{STANDALONE_RM}</style>{body}</svg>\n')

def main():
    os.makedirs(os.path.join(HERE, "svg"), exist_ok=True)
    n = 0
    for (kind, name) in META:
        faces = list(WM) if kind == "lockup" else ["instrument"]
        for face in faces:
            for theme in ("dark", "light"):
                fn = f"{kind[0]}-{name}" + (f".{face}" if kind == "lockup" else "") + f".{theme}.svg"
                open(os.path.join(HERE, "svg", fn), "w").write(standalone(kind, name, theme, face)); n += 1
    # preview page
    css_all, cards, sched, cycle, loops = [], [], {}, {}, {}
    for (kind, name), m in META.items():
        vid = f"{kind[0]}-{name}"
        d = M[name] if kind == "mark" else L[name]
        css, _, _ = variant(kind, name)
        css_all.append(css)
        sched[vid] = d["audio"]; cycle[vid] = d["cycle"]; loops[vid] = d["loop"]
        def tile(theme):
            if kind == "mark":
                _, body, vb = variant(kind, name)
                return f'<div class="tile {theme}"><svg viewBox="{vb}" class="svgm" aria-hidden="true">{body}</svg></div>'
            inner = ""
            for face in WM:
                _, body, vb = variant(kind, name, face)
                inner += f'<svg viewBox="{vb}" class="svgl f-{face}" aria-hidden="true">{body}</svg>'
            return f'<div class="tile {theme}">{inner}</div>'
        cards.append(
            f'<article class="card" data-id="{vid}"><header><h2>{m["title"]}</h2><span class="chip">{m["purpose"]}</span><span class="chip t-{m["tier"].lower()}">{m["tier"]}</span></header>'
            f'<div class="tiles">{tile("dark")}{tile("light")}</div>'
            f'<p class="use">{m["use"]}</p><p class="snd"><b>Sound.</b> {m["sound"]}</p>'
            f'<footer><button class="btn replay" type="button">Replay</button><span class="meta">{"Loops every %.1f s" % (d["cycle"]/1000) if d["loop"] else "Plays once, %.1f s" % (d["cycle"]/1000)}</span></footer></article>')
    tpl = open(os.path.join(HERE, "preview.template.html")).read()
    face_css = "".join(f'body[data-face={f}]:not(.stage) .svgl:not(.f-{f}){{display:none}}' for f in WM)
    face_btns = "".join(f'<button type="button" data-face="{f}" aria-pressed="{"true" if f == "instrument" else "false"}">{WM[f]["label"].replace(" SemiBold", "")}</button>' for f in WM)
    html = (tpl.replace("/*@CSS@*/", face_css + "".join(css_all)).replace("<!--@FACES@-->", face_btns)
               .replace("<!--@MARKS@-->", "".join(c for c in cards if 'data-id="m-' in c))
               .replace("<!--@LOCKUPS@-->", "".join(c for c in cards if 'data-id="l-' in c))
               .replace("/*@SCHED@*/{}", json.dumps(sched)).replace("/*@CYCLE@*/{}", json.dumps(cycle)).replace("/*@LOOPS@*/{}", json.dumps(loops)))
    open(os.path.join(HERE, "index.html"), "w").write(html)
    print("wrote", n, "svgs and index.html")

if __name__ == "__main__":
    main()
