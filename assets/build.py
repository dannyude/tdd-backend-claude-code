#!/usr/bin/env python3
"""Builds the animated SVGs used by the README and the site.

    python3 assets/build.py

Needs fontTools + brotli (pip install fonttools brotli). The book's two faces (Caladea Bold for
display, DejaVu Sans Mono for everything technical) are subset to the glyphs each SVG uses and
embedded as WOFF2, so the graphics look like the book on any machine. Both fonts are freely
licensed (Apache 2.0 / Bitstream Vera).

Design rules come from the book-reel style guide: paper and terminal are the only two
surfaces; one accent (copper) for FAIL/RED and the final number; green only for PASS;
type arrives by mask (it rises into a clipped box), never by fade; no gradients, no window
chrome. Every string on screen is real output or a real path from this repository.
"""
from __future__ import annotations

import base64
import io
from html import escape
from pathlib import Path

from fontTools import subset
from fontTools.ttLib import TTFont

HERE = Path(__file__).resolve().parent
FONT_DIRS = [HERE / "fonts", Path("/usr/share/fonts/truetype/crosextra"),
             Path("/usr/share/fonts/truetype/dejavu")]

# ------------------------------------------------------------------ tokens (the book's own)
PAPER, INK, COPPER, SLATE = "#FBFAF8", "#1B365D", "#B5532C", "#5B6B82"
PASS = "#2E7D5B"
RULE = "#E4E0D9"
T_BG, T_FG, T_HEAD, T_DIM, T_PASS, T_ACC = (
    "#14181F", "#C9D1D9", "#FBFAF8", "#7D8A9C", "#3FB27F", "#D4703C")

MONO_STACK = "'BookMono', 'DejaVu Sans Mono', ui-monospace, Menlo, Consolas, monospace"
DISP_STACK = "'BookDisplay', Caladea, Cambria, Georgia, serif"


def find_font(name: str) -> Path:
    for d in FONT_DIRS:
        if (d / name).exists():
            return d / name
    raise SystemExit(f"font not found: {name}")


def font_face(family: str, file: str, text: str) -> str:
    opts = subset.Options()
    opts.flavor = "woff2"
    opts.layout_features = ["kern", "liga"]
    opts.name_IDs = []
    opts.hinting = False
    font = TTFont(find_font(file))
    sub = subset.Subsetter(opts)
    sub.populate(text=text + " ")
    sub.subset(font)
    buf = io.BytesIO()
    font.flavor = "woff2"
    font.save(buf)
    b64 = base64.b64encode(buf.getvalue()).decode()
    return (f"@font-face{{font-family:'{family}';"
            f"src:url(data:font/woff2;base64,{b64}) format('woff2');}}")


class Svg:
    """Collects text per face so the embedded subset is exactly what is drawn."""

    def __init__(self, w: int, h: int, title: str):
        self.w, self.h, self.title = w, h, title
        self.body: list[str] = []
        self.css: list[str] = []
        self.defs: list[str] = []
        self.mono_text = ""
        self.disp_text = ""
        self.n = 0

    def uid(self, p: str = "c") -> str:
        self.n += 1
        return f"{p}{self.n}"

    def text(self, x, y, s, *, size, fill, face="mono", weight=400, cls="", anchor="start",
             spacing=None, raw=None):
        if face == "mono":
            self.mono_text += s
        else:
            self.disp_text += s
        fam = "m" if face == "mono" else "d"
        style = f' letter-spacing="{spacing}"' if spacing else ""
        c = f' class="{fam} {cls}"'.rstrip()
        content = raw if raw is not None else escape(s)
        return (f'<text x="{x}" y="{y}" font-size="{size}" fill="{fill}" font-weight="{weight}" '
                f'text-anchor="{anchor}"{style}{c}>{content}</text>')

    def tspan(self, s, fill, weight=400, face="mono"):
        if face == "mono":
            self.mono_text += s
        else:
            self.disp_text += s
        return f'<tspan fill="{fill}" font-weight="{weight}">{escape(s)}</tspan>'

    def rise(self, inner: str, x, y_top, w, h, anim: str) -> str:
        """Clip `inner` to a box and let it rise into it (the reel's mask reveal)."""
        cid = self.uid("clip")
        self.defs.append(f'<clipPath id="{cid}"><rect x="{x}" y="{y_top}" width="{w}" '
                         f'height="{h}"/></clipPath>')
        return f'<g clip-path="url(#{cid})"><g class="{anim}">{inner}</g></g>'

    def render(self, bg: str | None) -> str:
        faces = ""
        if self.mono_text:
            bold = font_face("BookMono", "DejaVuSansMono-Bold.ttf", self.mono_text)
            reg = font_face("BookMono", "DejaVuSansMono.ttf", self.mono_text)
            faces += reg + bold.replace("format('woff2');}", "format('woff2');font-weight:700;}")
        if self.disp_text:
            faces += font_face("BookDisplay", "Caladea-Bold.ttf", self.disp_text)
        base = (f"text{{white-space:pre}}.m{{font-family:{MONO_STACK}}}.d{{font-family:{DISP_STACK};font-weight:700}}"
                "@media (prefers-reduced-motion: reduce){*{animation:none!important}}")
        bgrect = f'<rect width="100%" height="100%" fill="{bg}" rx="12"/>' if bg else ""
        return (f'<svg xmlns="http://www.w3.org/2000/svg" width="{self.w}" height="{self.h}" '
                f'viewBox="0 0 {self.w} {self.h}" role="img" aria-label="{escape(self.title)}">'
                f"<title>{escape(self.title)}</title>"
                f"<style>{faces}{base}{''.join(self.css)}</style>"
                f"<defs>{''.join(self.defs)}</defs>{bgrect}{''.join(self.body)}</svg>")


def keyframes(name: str, T: float, on: float, off: float | None, frm: str, to: str,
              ease_s: float = 0.45) -> str:
    """A looping one-shot: `frm` until `on`, eases to `to`, holds, snaps back at `off`."""
    p = lambda t: f"{max(0.0, min(100.0, t / T * 100)):.3f}%"
    frames = [f"0%,{p(on)}{{{frm}}}", f"{p(on + ease_s)}{{{to}}}"]
    if off is not None:
        frames += [f"{p(off)}{{{to}}}", f"{p(off + 0.01)},100%{{{frm}}}"]
    else:
        frames += [f"100%{{{to}}}"]
    return f"@keyframes {name}{{{''.join(frames)}}}"


EASE = "cubic-bezier(.2,.8,.2,1)"


# ======================================================================== banner
def banner(dark: bool) -> str:
    W, H = 1280, 460
    s = Svg(W, H, "Test-Driven Backend Development with Claude Code: from first test to CI/CD")
    bg = T_BG if dark else PAPER
    ink = T_HEAD if dark else INK
    dim = T_DIM if dark else SLATE
    red = T_ACC if dark else COPPER
    grn = T_PASS if dark else PASS
    T = 14.0  # loop length (terminal replays; the title stays)

    # ---- left: the title, risen in once
    x0 = 72
    s.css.append(f".up{{animation:up .9s {EASE} both}}"
                 "@keyframes up{from{transform:translateY(105%)}to{transform:none}}")
    kicker = s.text(x0, 96, "A BOOK + ITS COMPANION REPOSITORY", size=15, fill=dim,
                    weight=700, spacing="2.4")
    s.body.append(s.rise(kicker, x0, 78, 560, 26, "up"))
    for i, line in enumerate(["Test-Driven Backend", "Development with", "Claude Code"]):
        y = 178 + i * 70
        t = s.text(x0, y, line, size=64, fill=red if i == 2 else ink, face="disp",
                   spacing="-1.6")
        s.css.append(f".up{i}{{animation:up 1s {EASE} {0.15 + i * 0.12:.2f}s both}}")
        s.body.append(s.rise(t, x0 - 4, y - 62, 640, 80, f"up{i}"))
    # the book's section rule, wiping in
    s.css.append(f".wipe{{transform-origin:{x0}px 0;animation:wipe 1s {EASE} .6s both}}"
                 "@keyframes wipe{from{transform:scaleX(0)}to{transform:scaleX(1)}}")
    s.body.append(f'<rect class="wipe" x="{x0}" y="342" width="560" height="2" fill="{dim}"/>')
    sub = s.text(x0, 380, "", size=17, fill=dim, raw=(
        s.tspan("Spec → ", dim) + s.tspan("Red", red, 700) + s.tspan(" → ", dim)
        + s.tspan("Green", grn, 700) + s.tspan(" → Refactor → Verify → Review", dim)))
    s.css.append(f".up9{{animation:up .9s {EASE} .8s both}}")
    s.body.append(s.rise(sub, x0, 362, 600, 26, "up9"))
    by = s.text(x0, 414, "Python · FastAPI · SQLAlchemy · PostgreSQL · by Daniel Ude",
                size=15, fill=dim)
    s.css.append(f".up10{{animation:up .9s {EASE} .95s both}}")
    s.body.append(s.rise(by, x0, 398, 600, 24, "up10"))

    # ---- right: the single definition of "done", typed on a loop
    px, py, pw, ph = 720, 64, 488, 336
    panel = "#0D1015" if dark else T_BG
    s.body.append(f'<rect x="{px}" y="{py}" width="{pw}" height="{ph}" rx="10" fill="{panel}"'
                  + (f' stroke="#2A313C"' if dark else "") + "/>")
    lines = [
        (0.6, [("$ ", T_ACC, 400), ("bash scripts/check.sh", T_HEAD, 700)]),
        (1.6, [("==> ruff lint", T_DIM, 400)]),
        (2.1, [("All checks passed!", T_FG, 400)]),
        (2.6, [("==> ruff format", T_DIM, 400)]),
        (3.0, [("25 files already formatted", T_FG, 400)]),
        (3.5, [("==> mypy", T_DIM, 400)]),
        (4.2, [("Success: no issues found in 13 source files", T_FG, 400)]),
        (4.7, [("==> pytest", T_DIM, 400)]),
        (5.9, [("9 passed", T_PASS, 700), (" in 0.07s", T_DIM, 400)]),
        (6.6, [("All checks passed.", T_PASS, 700)]),
    ]
    lh = 27
    for i, (t, parts) in enumerate(lines):
        y = py + 46 + i * lh
        raw = "".join(s.tspan(txt, col, w) for txt, col, w in parts)
        txt = s.text(px + 28, y, "", size=16, fill=T_FG, raw=raw)
        name = f"tl{i}"
        s.css.append(keyframes(name, T, t, T - 0.6, "transform:translateY(110%)",
                               "transform:none", 0.3))
        s.css.append(f".{name}{{animation:{name} {T}s linear infinite}}")
        s.body.append(s.rise(txt, px + 20, y - 20, pw - 40, lh, name))
    # cursor that rides under the last typed line
    cur_y = [py + 46 + i * lh for i in range(len(lines))]
    kf = []
    for i, (t, _) in enumerate(lines):
        kf.append(f"{t / T * 100:.2f}%{{transform:translateY({cur_y[i] - cur_y[0] + lh}px)}}")
    s.css.append("@keyframes cur{0%{transform:translateY(0)}" + "".join(kf)
                                  + f"{(T - 0.59) / T * 100:.2f}%,100%{{transform:translateY(0)}}}}"
                 "@keyframes blink{50%{opacity:0}}"
                 f".cur{{animation:cur {T}s steps(1,end) infinite}}"
                 ".blink{animation:blink 1s steps(1,end) infinite}")
    s.body.append(f'<g class="cur"><rect class="blink" x="{px + 28}" y="{cur_y[0] - 15}" '
                  f'width="10" height="19" fill="{T_FG}"/></g>')
    # caption under the panel
    cap = s.text(px, py + ph + 30, "scripts/check.sh: the single definition of \"done\"",
                 size=14, fill=dim)
    s.body.append(cap)
    return s.render(bg)


# ======================================================================== feature loop
PHASES = [
    ("0", "SPEC", INK, [("Agree the behaviour before any code: ", None),
                         ("who may cancel, which states, which errors.", None)]),
    ("1", "RED", COPPER, [("echo red > .tdd-phase", "code"), ("  ·  tests committed alone  ·  ", None),
                          ("7 failed, 1 passed", "red")]),
    ("2", "GREEN", PASS, [("echo green > .tdd-phase", "code"), ("  ·  tests locked  ·  ", None),
                          ("check.sh exits 0", "green")]),
    ("3", "REFACTOR", INK, [("Rules move to ", None), ("app/services/orders.py", "code"),
                            ("  ·  behaviour unchanged", None)]),
    ("4", "VERIFY", INK, [("migration round-trip · Schemathesis · smoke test · ", None),
                          ("24/24 mutants killed", "green")]),
    ("5", "REVIEW", INK, [("reviewer subagent reads ", None), ("git diff main...HEAD", "code"),
                          ("  ·  open the PR", None)]),
]


def feature_loop() -> str:
    W, H = 1280, 300
    s = Svg(W, H, "The feature loop: Spec, Red, Green, Refactor, Verify, Review")
    step = 2.6
    T = step * len(PHASES)
    x0, x1, ry = 110, 1170, 120
    gap = (x1 - x0) / (len(PHASES) - 1)

    head = s.text(64, 56, "THE FEATURE LOOP  ·  PART 5", size=14, fill=SLATE, weight=700,
                  spacing="2.2")
    s.body.append(head)
    s.body.append(f'<rect x="{x0}" y="{ry - 1}" width="{x1 - x0}" height="2" fill="{RULE}"/>')
    # progress rule that fills as the loop advances
    s.css.append(f"@keyframes prog{{0%{{transform:scaleX(0)}}"
                 f"{(T - step) / T * 100:.2f}%{{transform:scaleX(1)}}"
                 f"{(T - 0.05) / T * 100:.2f}%{{transform:scaleX(1)}}100%{{transform:scaleX(0)}}}}"
                 f".prog{{transform-origin:{x0}px 0;animation:prog {T}s linear infinite}}")
    s.body.append(f'<rect class="prog" x="{x0}" y="{ry - 1}" width="{x1 - x0}" height="2" fill="{SLATE}"/>')

    for i, (num, name, col, cap) in enumerate(PHASES):
        cx = x0 + i * gap
        on, off = i * step, (i + 1) * step
        a, b = on / T * 100, off / T * 100
        # node: hollow until its turn, filled while active, ink-dot after
        nm = f"n{i}"
        s.css.append(
            f"@keyframes {nm}{{0%,{max(a - .01, 0):.2f}%{{fill:{PAPER};stroke:{RULE}}}"
            f"{a:.2f}%,{b - .01:.2f}%{{fill:{col};stroke:{col}}}"
            f"{b:.2f}%,99.9%{{fill:{SLATE};stroke:{SLATE}}}100%{{fill:{PAPER};stroke:{RULE}}}}}"
            f".{nm}{{animation:{nm} {T}s steps(1,end) infinite}}")
        s.css.append(
            f"@keyframes r{nm}{{0%,{max(a - .01, 0):.2f}%{{transform:scale(0)}}"
            f"{a:.2f}%{{transform:scale(.6)}}{a + 3:.2f}%{{transform:scale(1)}}"
            f"{b - .01:.2f}%{{transform:scale(1)}}{b:.2f}%,100%{{transform:scale(0)}}}}"
            f".r{nm}{{transform-origin:{cx}px {ry}px;transform-box:view-box;"
            f"animation:r{nm} {T}s {EASE} infinite}}")
        s.body.append(f'<circle class="r{nm}" cx="{cx}" cy="{ry}" r="20" fill="none" '
                      f'stroke="{col}" stroke-width="1.5" opacity=".35"/>')
        s.body.append(f'<circle class="{nm}" cx="{cx}" cy="{ry}" r="9" stroke-width="2"/>')
        # label: number + name; the active one turns its colour
        s.css.append(
            f"@keyframes l{nm}{{0%,{max(a - .01, 0):.2f}%{{fill:{SLATE}}}"
            f"{a:.2f}%,{b - .01:.2f}%{{fill:{col}}}{b:.2f}%,100%{{fill:{SLATE}}}}}"
            f".l{nm}{{animation:l{nm} {T}s steps(1,end) infinite}}")
        s.body.append(s.text(cx, ry + 48, f"{num} · {name}", size=15, fill=SLATE, weight=700,
                             anchor="middle", cls=f"l{nm}", spacing="1.4"))
        # caption: rises in under the rule while active
        raw = ""
        for txt, kind in cap:
            if kind == "code":
                raw += s.tspan(txt, INK, 700)
            elif kind == "red":
                raw += s.tspan(txt, COPPER, 700)
            elif kind == "green":
                raw += s.tspan(txt, PASS, 700)
            else:
                raw += s.tspan(txt, SLATE)
        title = s.text(W / 2, 228, name.title() if name != "REVIEW" else "Review & ship",
                       size=30, fill=col if col != INK else INK, face="disp", anchor="middle")
        captxt = s.text(W / 2, 262, "", size=16, fill=SLATE, anchor="middle", raw=raw)
        cn = f"c{i}"
        s.css.append(
            f"@keyframes {cn}{{0%,{max(a - .01, 0):.2f}%{{transform:translateY(110%)}}"
            f"{a + 2.5:.2f}%{{transform:none}}{b - 1.2:.2f}%{{transform:none}}"
            f"{b - .2:.2f}%,100%{{transform:translateY(-110%)}}}}"
            f".{cn}{{animation:{cn} {T}s {EASE} infinite}}")
        s.body.append(s.rise(title + captxt, 40, 196, W - 80, 76, cn))
    return s.render(PAPER)


# ======================================================================== guardrails
def guardrails() -> str:
    W, H = 1280, 470
    s = Svg(W, H, "The two guardrail hooks: tests are locked in Green, and Claude can't stop "
                  "while checks fail")
    T = 16.0
    cols = [
        ("PreToolUse  ·  .claude/hooks/lock_tests.py", [
            (0.4, [("$ cat .tdd-phase", T_DIM, 400)]),
            (0.9, [("green", T_HEAD, 700)]),
            (2.0, [("● ", T_ACC, 400), ("Claude: ", T_DIM, 400), ("Edit(", T_FG, 400),
                   ("tests/api/test_order_cancel.py", T_HEAD, 700), (")", T_FG, 400)]),
            (3.4, [("✗ blocked  ", T_ACC, 700), ("exit 2", T_DIM, 400)]),
            (3.9, [("  Green phase: tests are locked.", T_FG, 400)]),
            (4.3, [("  Fix the implementation.", T_FG, 400)]),
            (5.6, [("● ", T_PASS, 400), ("Claude: ", T_DIM, 400), ("Edit(", T_FG, 400),
                   ("app/services/orders.py", T_HEAD, 700), (")", T_FG, 400)]),
            (6.8, [("✓ allowed  ", T_PASS, 700), ("exit 0", T_DIM, 400)]),
        ]),
        ("Stop  ·  .claude/hooks/verify_on_stop.py", [
            (7.6, [("● ", T_ACC, 400), ("Claude: ", T_DIM, 400), ("\"Done.\"", T_HEAD, 700)]),
            (8.4, [("$ bash scripts/check.sh", T_DIM, 400)]),
            (9.3, [("FAILED ", T_ACC, 700),
                   ("…::test_owner_cancels_pending_order", T_FG, 400)]),
            (9.7, [("1 failed", T_ACC, 700), (" in 0.06s", T_DIM, 400)]),
            (10.4, [("✗ Not done — checks failing ", T_ACC, 700), ("exit 2", T_DIM, 400)]),
            (10.8, [("  (attempt 1 of 5)", T_FG, 400)]),
            (11.8, [("● ", T_PASS, 400), ("Claude: ", T_DIM, 400), ("Edit(", T_FG, 400), ("app/services/orders.py", T_HEAD, 700), (")", T_FG, 400)]),
            (12.8, [("All checks passed.", T_PASS, 700)]),
            (13.4, [("✓ stop allowed  ", T_PASS, 700), ("exit 0", T_DIM, 400)]),
        ]),
    ]
    pw, ph, py, gap = 568, 350, 76, 32
    head = s.text(64, 44, "PART 4  ·  GUARDRAILS, NOT JAILS", size=14, fill=SLATE, weight=700,
                  spacing="2.2")
    s.body.append(head)
    for ci, (title, lines) in enumerate(cols):
        px = 56 + ci * (pw + gap)
        s.body.append(f'<rect x="{px}" y="{py}" width="{pw}" height="{ph}" rx="10" fill="{T_BG}"/>')
        s.body.append(s.text(px + 24, py + 34, title, size=13, fill=T_DIM, weight=700,
                             spacing="0.6"))
        s.body.append(f'<rect x="{px + 24}" y="{py + 48}" width="{pw - 48}" height="1" fill="#2A313C"/>')
        lh = 29
        for li, (t, parts) in enumerate(lines):
            y = py + 84 + li * lh
            raw = "".join(s.tspan(txt, c, w) for txt, c, w in parts)
            txt = s.text(px + 24, y, "", size=15, fill=T_FG, raw=raw)
            name = f"g{ci}{li}"
            s.css.append(keyframes(name, T, t, T - 0.7, "transform:translateY(110%)",
                                   "transform:none", 0.35))
            s.css.append(f".{name}{{animation:{name} {T}s linear infinite}}")
            s.body.append(s.rise(txt, px + 16, y - 20, pw - 32, lh, name))
    cap = s.text(W / 2, H - 14, "", size=14, fill=SLATE, anchor="middle", raw=(
        s.tspan("Real messages from the hooks in ", SLATE)
        + s.tspan("shop-api/.claude/hooks/", INK, 700)
        + s.tspan("  ·  validate.sh checks both: exit codes 2 2 2 2 2 1", SLATE)))
    s.body.append(cap)
    return s.render(PAPER)


# ======================================================================== 54 / 54
def proof() -> str:
    W, H = 1280, 300
    s = Svg(W, H, "54 of 54 acceptance checks passed on Python 3.12 and 3.14")
    T = 10.0
    s.body.append(s.text(72, 84, "ALL CHECKS PASSED", size=15, fill=PASS, weight=700,
                         spacing="2.4"))
    raw = (s.tspan("54", INK, 700, "disp") + s.tspan(" / ", SLATE, 700, "disp")
           + s.tspan("54", COPPER, 700, "disp"))
    s.body.append(s.text(64, 196, "", size=120, fill=INK, face="disp", raw=raw, spacing="-3"))
    s.body.append(s.text(72, 246, "bash validate.sh --full  ·  Python 3.12 and 3.14", size=15,
                         fill=SLATE))
    # the wall of green: 54 cells, one per `rec` call in validate.sh
    cols, rows, cell, g = 9, 6, 30, 8
    gx, gy = 1208 - cols * (cell + g) + g, 40
    fill_end = 4.2
    for k in range(54):
        r, c = divmod(k, cols)
        x, y = gx + c * (cell + g), gy + r * (cell + g)
        t = 0.3 + k * (fill_end / 54)
        name = f"q{k}"
        s.css.append(keyframes(name, T, t, T - 0.4, f"fill:{RULE}", f"fill:{PASS}", 0.15))
        s.css.append(f".{name}{{animation:{name} {T}s linear infinite}}")
        s.body.append(f'<rect class="{name}" x="{x}" y="{y}" width="{cell}" height="{cell}" '
                      f'rx="4" fill="{RULE}"/>')
    return s.render(PAPER)


def main() -> None:
    out = {
        "banner-light.svg": banner(dark=False),
        "banner-dark.svg": banner(dark=True),
        "feature-loop.svg": feature_loop(),
        "guardrails.svg": guardrails(),
        "proof-54.svg": proof(),
    }
    for name, svg in out.items():
        (HERE / name).write_text(svg, encoding="utf-8")
        print(f"{name:20s} {len(svg) / 1024:6.1f} KB")


if __name__ == "__main__":
    main()
