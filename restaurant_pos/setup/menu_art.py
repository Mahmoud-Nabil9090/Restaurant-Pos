"""رسومات SVG لأصناف المنيو والتصنيفات (من غير أي ملفات أو إنترنت).

render(item_name)       -> نص SVG للصنف
render_category(group)  -> نص SVG للتصنيف
slug(name)              -> اسم الملف
"""
import random
import re

# ---------------------------------------------------------------- helpers


def slug(name):
    return re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")


def shade(hexc, amt):
    h = hexc.lstrip("#")
    r, g, b = (int(h[i : i + 2], 16) for i in (0, 2, 4))
    if amt >= 0:
        r, g, b = (round(c + (255 - c) * amt) for c in (r, g, b))
    else:
        r, g, b = (round(c * (1 + amt)) for c in (r, g, b))
    return "#%02x%02x%02x" % (r, g, b)


def ell(cx, cy, rx, ry, fill, extra=""):
    return f'<ellipse cx="{cx}" cy="{cy}" rx="{rx}" ry="{ry}" fill="{fill}" {extra}/>'


def circ(cx, cy, r, fill, extra=""):
    return f'<circle cx="{cx}" cy="{cy}" r="{r}" fill="{fill}" {extra}/>'


def rect(x, y, w, h, fill, rx=0, extra=""):
    return f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="{rx}" fill="{fill}" {extra}/>'


def path(d, fill="none", extra=""):
    return f'<path d="{d}" fill="{fill}" {extra}/>'


def line(x1, y1, x2, y2, stroke, w=4, extra=""):
    return (
        f'<line x1="{x1}" y1="{y1}" x2="{x2}" y2="{y2}" stroke="{stroke}" '
        f'stroke-width="{w}" stroke-linecap="round" {extra}/>'
    )


def rot(content, deg, cx, cy):
    return f'<g transform="rotate({deg} {cx} {cy})">{content}</g>'


def shadow(cy=262, rx=120):
    return ell(200, cy, rx, 13, "#000", 'opacity=".13"')


def plate(cx=200, cy=196, rx=156, ry=64):
    return (
        shadow(cy + ry + 6, rx - 14)
        + ell(cx, cy, rx, ry, "#ffffff", 'stroke="#e5e7eb" stroke-width="3"')
        + ell(cx, cy + 2, rx - 30, ry - 22, "#f3f4f6")
    )


def lemon(x, y, r=17):
    s = circ(x, y, r, "#ffd84d") + circ(x, y, r - 4, "#fff0a0")
    for a in range(0, 180, 45):
        s += rot(line(x - r + 5, y, x + r - 5, y, "#ffd84d", 2), a, x, y)
    return s


def herb(rng, cx, cy, spread, n=10, col="#3f9b4a"):
    s = ""
    for _ in range(n):
        s += ell(
            cx + rng.uniform(-spread, spread),
            cy + rng.uniform(-spread * 0.4, spread * 0.4),
            5,
            2.6,
            col,
            f'transform="rotate({rng.randint(0, 170)} {cx} {cy})"',
        )
    return s


def tomato(x, y, r=11):
    return circ(x, y, r, "#e5483d") + ell(x - 3, y - 4, 3.5, 2, "#ff8f84", 'opacity=".7"')


def wrap_svg(body, c1, c2):
    return (
        '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 400 300" width="400" height="300">'
        '<defs><linearGradient id="bg" x1="0" y1="0" x2="1" y2="1">'
        f'<stop offset="0" stop-color="{c1}"/><stop offset="1" stop-color="{c2}"/>'
        "</linearGradient></defs>"
        '<rect width="400" height="300" fill="url(#bg)"/>'
        f"{body}</svg>"
    )


# ---------------------------------------------------------------- burgers

LAYER_H = {
    "lettuce": 12, "tomato": 10, "patty": 26, "onion": 8, "cheese": 8,
    "bacon": 9, "mushroom": 14, "jalapeno": 10, "pickle": 8,
}


def _layer(kind, y, bun, rng):
    name, _, variant = kind.partition(":")
    h = LAYER_H[name]
    if name == "patty":
        col = {"crispy": "#d9993a", "veg": "#7c6a3b", "grill": "#c98d57"}.get(variant, "#6a3a21")
        s = rect(100, y - h, 200, h, col, 13)
        for i in range(9):
            dx = 122 + i * 22
            if variant == "crispy":
                s += circ(dx, y - 13 + (i % 3) * 4 - 4, 3, "#f0c26c", 'opacity=".8"')
            elif variant == "veg":
                s += ell(dx, y - 13 + (i % 3) * 4 - 4, 5, 3, "#6fae4b", 'opacity=".85"')
            elif variant == "grill":
                s += line(dx, y - 20, dx + 8, y - 6, "#8a5a2c", 3, 'opacity=".6"')
            else:
                s += ell(dx, y - 13 + (i % 2) * 6 - 3, 4, 2.2, "#8a5636", 'opacity=".8"')
        return s, h
    if name == "cheese":
        col = {"swiss": "#fff0a6", "pepper": "#ffb347"}.get(variant, "#ffc83d")
        s = rect(104, y - 8, 192, 8, col, 3)
        s += path(f"M120,{y} l14,16 l14,-16 Z", col)
        s += path(f"M232,{y} l10,12 l10,-12 Z", col)
        return s, h
    if name == "lettuce":
        d = f"M98,{y} " + "q11,-20 22,0 " + "t22,0 " * 8 + f"L298,{y + 6} L98,{y + 6} Z"
        return path(d, "#5fbf55"), h
    if name == "tomato":
        return rect(108, y - 10, 184, 11, "#e5483d", 5) + "".join(
            ell(130 + i * 35, y - 7, 6, 2, "#ff9a90", 'opacity=".55"') for i in range(5)
        ), h
    if name == "onion":
        return rect(112, y - 8, 176, 8, "#e8d3f0", 4) + line(120, y - 4, 280, y - 4, "#c9a6dc", 2), h
    if name == "bacon":
        return rect(106, y - 9, 188, 9, "#b4453a", 4) + "".join(
            line(118 + i * 24, y - 7, 126 + i * 24, y - 2, "#e9a9a0", 3) for i in range(7)
        ), h
    if name == "mushroom":
        s = ""
        for i in range(4):
            cx = 128 + i * 48
            s += path(f"M{cx - 22},{y} C{cx - 22},{y - 22} {cx + 22},{y - 22} {cx + 22},{y} Z", "#b98b63")
            s += rect(cx - 6, y - 4, 12, 4, "#e6cfae")
        return s, h
    if name == "jalapeno":
        return "".join(
            circ(122 + i * 28, y - 5, 7, "#2f8f3f") + circ(122 + i * 28, y - 5, 3, "#9be08f") for i in range(7)
        ), h
    if name == "pickle":
        return "".join(ell(130 + i * 46, y - 4, 15, 4, "#6ea43a") for i in range(4)), h
    raise ValueError(kind)


def burger(bun="#e9a23b", layers=("lettuce", "tomato", "patty"), scale=1.0, seeds=True):
    rng = random.Random("burger" + bun + "".join(layers))
    p = []
    y = 250
    p.append(rect(108, y - 26, 184, 26, shade(bun, -0.15), 13))
    y -= 26
    for kind in layers:
        s, h = _layer(kind, y, bun, rng)
        p.append(s)
        y -= h
    p.append(
        path(
            f"M98,{y} C98,{y - 96} 302,{y - 96} 302,{y} C302,{y + 10} 292,{y + 12} 280,{y + 12} "
            f"H120 C108,{y + 12} 98,{y + 10} 98,{y} Z",
            bun,
        )
    )
    p.append(
        path(
            f"M128,{y - 42} C150,{y - 68} 200,{y - 74} 244,{y - 62}",
            "none",
            'stroke="#fff" stroke-opacity=".38" stroke-width="9" stroke-linecap="round"',
        )
    )
    if seeds:
        for dx, dy, a in [(158, -58, 20), (200, -70, -10), (244, -56, 25), (178, -38, -30), (226, -40, 10), (140, -30, 35), (264, -30, -25)]:
            p.append(ell(dx, y + dy, 6, 3, "#fff3d6", f'transform="rotate({a} {dx} {y + dy})"'))
    body = shadow(262, 125) + "".join(p)
    if scale != 1.0:
        body = f'<g transform="translate(200 262) scale({scale}) translate(-200 -262)">{body}</g>'
    return body


# ---------------------------------------------------------------- mains


def _steak():
    s = plate()
    s += path("M118,200 C112,162 190,148 252,164 C298,176 296,218 250,232 C198,248 124,242 118,200 Z", "#7a3d20")
    s += path("M130,198 C128,172 190,160 246,174", "none", 'stroke="#a8603a" stroke-width="6" stroke-linecap="round" opacity=".7"')
    for i in range(4):
        s += line(150 + i * 30, 176 + i * 2, 166 + i * 30, 226 + i * 1, "#3d1d0d", 5, 'opacity=".7"')
    s += circ(300, 176, 14, "#e5483d") + circ(300, 176, 6, "#ff9a90")
    s += line(112, 224, 152, 238, "#3f9b4a", 4) + herb(random.Random(1), 130, 236, 14, 6)
    return s


def _grilled_chicken():
    s = plate()
    for dx, dy, a in [(-34, 6, -14), (40, 0, 10)]:
        leg = (
            path("M0,0 C-30,-20 -22,-60 10,-62 C46,-62 56,-22 28,6 Z", "#c97a2e")
            + path("M10,-58 C34,-56 44,-28 22,-6", "none", 'stroke="#e6a455" stroke-width="6" stroke-linecap="round" opacity=".7"')
            + rect(22, 0, 8, 26, "#f4ead9", 4)
            + circ(20, 28, 7, "#f4ead9") + circ(32, 28, 7, "#f4ead9")
        )
        s += f'<g transform="translate({200 + dx} {196 + dy}) rotate({a})">{leg}</g>'
    s += lemon(296, 214) + lemon(114, 218, 14)
    s += herb(random.Random(2), 200, 228, 60, 8)
    return s


def _mixed_grill():
    s = plate(rx=160)
    s += path("M110,196 C110,170 160,164 186,176 C206,190 190,218 150,222 C120,224 110,214 110,196 Z", "#a85a2e")
    s += "".join(line(124 + i * 18, 178, 134 + i * 18, 216, "#4a2412", 4, 'opacity=".6"') for i in range(4))
    for i in range(3):
        s += rot(rect(196, 168 + i * 18, 100, 14, "#9b4a28", 7) + line(204, 175 + i * 18, 290, 175 + i * 18, "#d78a52", 3, 'opacity=".6"'), -6, 246, 190)
    s += rot(rect(206, 150, 120, 5, "#cbd5e1", 2), -6, 246, 190)
    s += path("M262,226 C268,206 304,204 312,222 C318,240 276,248 262,226 Z", "#d99a3b")
    s += tomato(136, 236) + tomato(160, 242, 9) + lemon(300, 160, 12)
    return s


def _kofta():
    s = plate(rx=160)
    for i in range(3):
        y = 160 + i * 26
        s += rot(rect(104, y, 190, 20, "#8a4a26", 10) + "".join(line(124 + k * 26, y + 4, 132 + k * 26, y + 16, "#4a2412", 3, 'opacity=".55"') for k in range(6)), -4, 200, y + 10)
        s += rot(rect(92, y + 8, 216, 4, "#cbd5e1", 2), -4, 200, y + 10)
    s += tomato(122, 240) + tomato(150, 244, 9)
    s += circ(300, 232, 11, "none", 'stroke="#d8b4e8" stroke-width="5"') + circ(300, 232, 4, "none", 'stroke="#d8b4e8" stroke-width="3"')
    s += herb(random.Random(3), 230, 244, 40, 8)
    return s


def _fish():
    s = plate()
    s += path("M104,206 C120,164 220,150 292,184 C250,226 160,244 104,206 Z", "#e0a23f")
    s += path("M124,198 C160,176 230,170 276,186", "none", 'stroke="#f5cf86" stroke-width="7" stroke-linecap="round" opacity=".8"')
    s += "".join(circ(150 + i * 26, 200 + (i % 2) * 8, 3, "#c4801f", 'opacity=".7"') for i in range(6))
    s += lemon(300, 224, 18) + herb(random.Random(4), 140, 236, 30, 8)
    return s


def _pasta():
    s = plate()
    s += ell(200, 196, 92, 38, "#f6e7b8")
    for r in (78, 62, 46, 30, 14):
        s += ell(200, 190, r, r * 0.4, "none", 'stroke="#e9cf86" stroke-width="5"')
    s += ell(200, 172, 40, 14, "#fff6d6")
    s += herb(random.Random(5), 200, 172, 40, 14)
    s += "".join(circ(130 + i * 36, 224 + (i % 2) * 4, 5, "#f4ead9") for i in range(5))
    return s


def _shawarma():
    s = plate(rx=160)
    for i in range(6):
        s += rot(rect(112, 168 + i * 11, 130, 12, "#b8742f", 6) + line(122, 174 + i * 11, 230, 174 + i * 11, "#e2a865", 3, 'opacity=".6"'), -3, 176, 200)
    s += ell(286, 188, 24, 18, "#fffaf0") + ell(286, 184, 14, 7, "#ffffff", 'opacity=".9"')
    s += "".join(rot(rect(262 + i * 14, 214, 8, 26, "#f1c34f", 3), 14, 280, 226) for i in range(4))
    s += "".join(ell(130 + i * 30, 240, 12, 4, "#6ea43a") for i in range(3))
    return s


def _fajita():
    s = shadow(262, 130)
    s += ell(200, 205, 150, 56, "#2b2f36") + ell(200, 200, 132, 44, "#3a3f48")
    s += rect(318, 196, 70, 12, "#2b2f36", 6)
    cols = ["#e5483d", "#f2b705", "#4caf50"]
    rng = random.Random("fajita")
    for i in range(14):
        c = cols[i % 3]
        x, y = 130 + rng.uniform(0, 140), 180 + rng.uniform(0, 32)
        s += rot(rect(x, y, 34, 8, c, 4), rng.randint(-40, 40), x, y)
    for i in range(6):
        x, y = 140 + rng.uniform(0, 120), 188 + rng.uniform(0, 24)
        s += rot(rect(x, y, 30, 12, "#c47a35", 6), rng.randint(-30, 30), x, y)
    return s + lemon(120, 226, 12)


def _wings():
    s = plate()
    rng = random.Random("wings")
    for i in range(6):
        x, y = 130 + (i % 3) * 66, 170 + (i // 3) * 42
        wing = (
            path("M0,0 C-26,-6 -30,-34 -4,-40 C24,-46 44,-24 30,-4 C22,8 10,6 0,0 Z", "#c8501e")
            + path("M-8,-30 C6,-36 24,-28 24,-14", "none", 'stroke="#f08a4b" stroke-width="5" stroke-linecap="round" opacity=".7"')
            + rect(24, -10, 24, 8, "#f4ead9", 4)
        )
        s += f'<g transform="translate({x} {y + 22}) rotate({rng.randint(-25, 25)})">{wing}</g>'
    s += lemon(318, 226, 12) + herb(rng, 200, 240, 60, 8)
    return s


def _strips():
    s = plate()
    rng = random.Random("strips")
    for i in range(5):
        x, y = 118 + i * 26, 168 + (i % 2) * 14
        s += rot(
            rect(x, y, 90, 24, "#d99a3b", 12)
            + "".join(circ(x + 14 + k * 14, y + 8 + (k % 2) * 8, 2.5, "#f2c46d") for k in range(5)),
            rng.randint(-14, 14), x + 45, y + 12,
        )
    s += ell(310, 220, 32, 16, "#fff") + ell(310, 218, 24, 10, "#e5483d")
    return s


# ---------------------------------------------------------------- sides


def _fries(col="#f6c23e", cheese=False, bacon=False):
    s = shadow(264, 100)
    rng = random.Random("fries" + col)
    for i in range(15):
        x = 138 + i * 8
        top = 88 + rng.randint(0, 34)
        s += rot(rect(x, top, 11, 130, col, 3, f'stroke="{shade(col, -0.12)}" stroke-width="1"'), rng.randint(-16, 16), x, 190)
    s += path("M128,150 L272,150 L256,258 L144,258 Z", "#e63946")
    s += path("M138,198 L262,198 L258,228 L142,228 Z", "#ffffff", 'opacity=".92"')
    s += path("M128,150 L272,150 L268,166 L132,166 Z", "#c92c39")
    if cheese:
        s += path("M138,140 C160,170 180,138 200,172 C220,138 240,170 262,140 L262,152 L138,152 Z", "#ffb52e")
        s += "".join(circ(152 + i * 32, 130 + (i % 2) * 8, 4, "#d94b3a") for i in range(4)) if bacon else ""
    return s


def _wedges():
    rng = random.Random("wedges")
    out = plate()
    for i in range(8):
        x, y = 122 + (i % 4) * 44, 164 + (i // 4) * 34
        out += (
            f'<g transform="translate({x} {y}) rotate({rng.randint(-20, 20)} 26 0)">'
            + path("M0,0 C14,-14 38,-14 52,0 C42,14 10,14 0,0 Z", "#e5ad47", 'stroke="#b87a22" stroke-width="2"')
            + "</g>"
        )
    out += ell(318, 222, 26, 14, "#fff") + ell(318, 220, 18, 8, "#e5483d")
    return out


def _onion_rings():
    s = plate()
    for i, (x, y) in enumerate([(160, 190), (214, 178), (262, 200), (190, 218), (240, 224)]):
        s += circ(x, y, 24, "none", 'stroke="#d9962f" stroke-width="14"') + circ(x, y, 24, "none", 'stroke="#f2c46d" stroke-width="5" opacity=".7"')
    s += ell(318, 230, 22, 12, "#fff") + ell(318, 228, 15, 7, "#f08a4b")
    return s


def _coleslaw():
    s = shadow(262, 90)
    s += path("M128,150 L272,150 L252,258 L148,258 Z", "#ffffff", 'stroke="#d1d5db" stroke-width="3"')
    s += rect(150, 192, 100, 22, "#4ca7d8", 4, 'opacity=".25"')
    rng = random.Random("slaw")
    s += path("M116,152 C120,90 280,90 284,152 Z", "#f6f0d8")
    for i in range(26):
        x, y = 130 + rng.uniform(0, 140), 112 + rng.uniform(0, 36)
        c = rng.choice(["#8fcf6a", "#f2a65a", "#fffaf0", "#d8e8a0"])
        s += rot(rect(x, y, 22, 5, c, 2), rng.randint(-60, 60), x, y)
    return s


def _mozzarella():
    s = plate()
    rng = random.Random("moz")
    for i in range(4):
        x, y = 130 + i * 34, 160 + (i % 2) * 18
        s += rot(rect(x, y, 80, 22, "#d99a3b", 11) + "".join(circ(x + 12 + k * 14, y + 8 + (k % 2) * 6, 2.4, "#f2c46d") for k in range(5)), rng.randint(-10, 10), x + 40, y + 11)
    s += rot(rect(120, 214, 80, 22, "#d99a3b", 11), 8, 160, 225)
    s += path("M196,222 C216,236 232,206 252,224", "none", 'stroke="#ffe08a" stroke-width="6" stroke-linecap="round"')
    s += ell(316, 218, 28, 15, "#fff") + ell(316, 216, 20, 9, "#d6362f")
    return s


def _corn():
    s = shadow(262, 90)
    s += path("M132,140 L268,140 L250,258 L150,258 Z", "#ffffff", 'stroke="#d1d5db" stroke-width="3"')
    s += rect(146, 196, 108, 24, "#f2b705", 4, 'opacity=".35"')
    rng = random.Random("corn")
    s += path("M126,142 C128,100 272,100 274,142 Z", "#f6c23e")
    for i in range(70):
        x, y = 134 + rng.uniform(0, 132), 108 + rng.uniform(0, 34)
        s += circ(x, y, 5.5, rng.choice(["#ffd84d", "#f2b705", "#ffe58f"]))
    s += rect(190, 108, 22, 12, "#fff4c2", 4)
    return s


def _garlic_bread():
    s = plate()
    for i in range(3):
        x, y = 130 + i * 50, 170 + (i % 2) * 18
        s += ell(x + 24, y + 22, 44, 24, "#c98a3e") + ell(x + 24, y + 20, 38, 19, "#f0c177")
        s += herb(random.Random(i), x + 24, y + 20, 22, 7, "#2f8f3f")
    return s


def _nachos():
    s = shadow(264, 130)
    s += path("M96,170 C100,252 300,252 304,170 Z", "#d6694a") + ell(200, 170, 108, 22, "#e8825f")
    rng = random.Random("nachos")
    for i in range(14):
        x, y = 120 + rng.uniform(0, 150), 118 + rng.uniform(0, 50)
        s += (
            f'<g transform="translate({x:.0f} {y:.0f}) rotate({rng.randint(0, 340)} 18 14)">'
            + path("M0,0 L36,0 L18,32 Z", rng.choice(["#f0c15a", "#e5ac3a"]), 'stroke="#c28522" stroke-width="2"')
            + "</g>"
        )
    s += path("M140,150 C170,176 200,140 232,172 C250,150 262,160 270,150 L270,164 L140,164 Z", "#ffb52e")
    s += circ(190, 140, 6, "#e5483d") + circ(224, 150, 5, "#e5483d") + circ(166, 150, 5, "#4caf50")
    return s


# ---------------------------------------------------------------- salads


def _salad(extras, greens=("#5fbf55", "#7bd06b", "#46a24a"), bowl="#ffffff", seed="salad"):
    rng = random.Random(seed)
    s = shadow(264, 125)
    s += path("M78,148 Q200,176 322,148 Q312,246 200,254 Q88,246 78,148 Z", bowl, 'stroke="#e5e7eb" stroke-width="3"')
    s += ell(200, 148, 122, 26, shade(bowl, -0.04), 'stroke="#e5e7eb" stroke-width="2"')
    for i in range(22):
        a = rng.uniform(0, 6.28)
        x, y = 200 + 92 * rng.uniform(0, 1) * rng.choice([-1, 1]) * abs(rng.random()), 138 + rng.uniform(-30, 12)
        s += rot(ell(x, y, 26, 12, rng.choice(greens)), rng.randint(0, 170), x, y)
    for kind, col, n in extras:
        for _ in range(n):
            x, y = 200 + rng.uniform(-84, 84), 128 + rng.uniform(-26, 14)
            if kind == "tomato":
                s += tomato(x, y, 9)
            elif kind == "cucumber":
                s += circ(x, y, 9, "#b7e08a", 'stroke="#4f9a3a" stroke-width="3"')
            elif kind == "olive":
                s += ell(x, y, 6, 5, col) + circ(x, y, 2, "#fff", 'opacity=".5"')
            elif kind == "feta":
                s += rot(rect(x, y, 16, 14, "#fffdf5", 3, 'stroke="#e5e0cc"'), rng.randint(0, 80), x, y)
            elif kind == "chunk":
                s += rot(rect(x, y, 18, 12, col, 5), rng.randint(0, 80), x, y)
            elif kind == "crouton":
                s += rot(rect(x, y, 13, 13, "#e5ad47", 3), rng.randint(0, 80), x, y)
            elif kind == "avocado":
                s += (
                    f'<g transform="translate({x:.0f} {y:.0f}) rotate({rng.randint(0, 340)})">'
                    + path("M0,0 C-6,-14 14,-18 20,-4 C16,10 4,12 0,0 Z", "#9bcf53", 'stroke="#5c8f2a" stroke-width="2"')
                    + "</g>"
                )
            elif kind == "dot":
                s += circ(x, y, 3.2, col)
            elif kind == "leaf":
                s += rot(ell(x, y, 8, 3.4, col), rng.randint(0, 170), x, y)
            elif kind == "pita":
                s += f'<g transform="translate({x:.0f} {y:.0f}) rotate({rng.randint(0, 340)})">' + path("M0,0 L18,0 L9,16 Z", "#e9b867", 'stroke="#c28522" stroke-width="1.5"') + "</g>"
            elif kind == "egg":
                s += ell(x, y, 9, 7, "#fffaf0", 'stroke="#e8e0c8"') + circ(x, y, 3.5, "#ffc83d")
    return s


# ---------------------------------------------------------------- drinks


def _glass(liquid, top=84, ice=True, straw="#ef4444", extras="", foam=None, bubbles=False):
    s = shadow(264, 82)
    s += rot(rect(206, 30, 10, 190, straw, 4), 10, 211, 125) if straw else ""
    s += path(f"M146,{top} L254,{top} L240,252 L160,252 Z", liquid)
    if foam:
        s += path(f"M146,{top} L254,{top} L252,{top + 22} L148,{top + 22} Z", foam)
    if ice:
        for x, y, a in [(172, 120, 12), (204, 150, 28), (180, 186, -14), (218, 206, 8), (196, 112, -10)]:
            s += rot(rect(x, y, 30, 30, "#ffffff", 7, 'opacity=".5" stroke="#ffffff" stroke-opacity=".7"'), a, x + 15, y + 15)
    if bubbles:
        rng = random.Random("bub")
        for _ in range(16):
            s += circ(160 + rng.uniform(0, 80), 100 + rng.uniform(0, 140), rng.uniform(1.5, 3.2), "#ffffff", 'opacity=".55"')
    s += path(f"M146,{top} L254,{top} L240,252 L160,252 Z", "none", 'stroke="#ffffff" stroke-width="5" opacity=".7"')
    s += path(f"M158,{top + 12} L166,{top + 150}", "none", 'stroke="#ffffff" stroke-width="6" stroke-linecap="round" opacity=".5"')
    s += extras
    return s


def _water():
    s = shadow(264, 70)
    s += rect(176, 30, 48, 26, "#2a7de1", 6)
    s += path("M180,56 L220,56 L222,84 C250,100 252,126 252,150 L252,246 C252,256 246,260 236,260 L164,260 C154,260 148,256 148,246 L148,150 C148,126 150,100 178,84 Z", "#d9efff", 'stroke="#ffffff" stroke-width="4" opacity=".95"')
    s += path("M150,180 C180,164 220,196 250,180 L250,226 C220,242 180,210 150,226 Z", "#2a7de1", 'opacity=".9"')
    s += path("M150,196 C180,180 220,212 250,196", "none", 'stroke="#ffffff" stroke-width="3" opacity=".7"')
    s += path("M164,104 L162,170", "none", 'stroke="#ffffff" stroke-width="6" stroke-linecap="round" opacity=".7"')
    return s


def _cup_turkish():
    s = shadow(262, 120)
    s += ell(200, 232, 112, 26, "#ffffff", 'stroke="#e5e7eb" stroke-width="3"') + ell(200, 232, 82, 16, "#f3f4f6")
    s += path("M138,170 C138,230 170,246 200,246 C230,246 262,230 262,170 Z", "#ffffff", 'stroke="#e5e7eb" stroke-width="3"')
    s += path("M138,170 C138,176 138,176 140,182 L260,182 C262,176 262,176 262,170 Z", "#c9a24a", 'opacity=".8"')
    s += ell(200, 170, 62, 15, "#c9a24a") + ell(200, 170, 56, 12, "#3a2216") + ell(200, 168, 40, 7, "#8a5a36", 'opacity=".85"')
    s += path("M262,184 C296,184 296,226 258,224", "none", 'stroke="#ffffff" stroke-width="10" stroke-linecap="round"')
    s += path("M262,184 C296,184 296,226 258,224", "none", 'stroke="#e5e7eb" stroke-width="2"')
    for x in (176, 200, 224):
        s += path(f"M{x},140 C{x - 12},120 {x + 12},108 {x},86", "none", 'stroke="#ffffff" stroke-width="6" stroke-linecap="round" opacity=".8"')
    return s


def _milkshake(base="#fff1c9", cream="#ffffff", sauce=None, cherry=True):
    s = shadow(264, 80)
    s += rot(rect(214, 24, 10, 150, "#ef4444", 4), 14, 219, 100)
    s += path("M142,96 L258,96 L242,252 L158,252 Z", base)
    s += path("M142,96 L258,96 L256,112 L144,112 Z", shade(base, -0.08), 'opacity=".5"')
    if sauce:
        s += path("M146,100 C150,150 160,120 168,160 C176,130 186,150 196,116 C206,150 220,126 232,164 C240,130 248,142 254,100 Z", sauce, 'opacity=".9"')
    s += path("M142,96 L258,96 L242,252 L158,252 Z", "none", 'stroke="#fff" stroke-width="5" opacity=".7"')
    s += path("M156,110 L164,224", "none", 'stroke="#fff" stroke-width="6" stroke-linecap="round" opacity=".5"')
    s += ell(200, 94, 62, 14, cream)
    s += path("M152,92 C152,60 248,60 248,92 Z", cream) + path("M168,66 C170,38 232,38 232,66 Z", cream)
    s += path("M164,76 C190,84 214,70 238,82", "none", f'stroke="{shade(cream, -0.1)}" stroke-width="3" opacity=".6"')
    if cherry:
        s += circ(200, 36, 12, "#d6182f") + ell(196, 32, 4, 3, "#ff8f9b", 'opacity=".8"') + path("M200,26 C206,10 214,8 222,6", "none", 'stroke="#3f7d3a" stroke-width="3" stroke-linecap="round"')
    return s


def _mango():
    s = _glass("#ffb62e", top=96, extras="", straw="#14b8a6")
    s += path("M286,200 C262,168 316,150 336,184 C352,216 306,236 286,200 Z", "#f6a21e")
    s += path("M300,172 C312,166 330,176 332,190", "none", 'stroke="#ff6b3a" stroke-width="7" stroke-linecap="round" opacity=".7"')
    s += path("M312,166 C320,148 338,148 346,152 C340,164 328,170 312,166 Z", "#3f9b4a")
    return s


def _orange_juice():
    s = _glass("#ff9a1f", top=96, straw="#ef4444")
    s += circ(262, 98, 24, "#ff8a00") + circ(262, 98, 19, "#ffd27a")
    for a in range(0, 180, 40):
        s += rot(line(262 - 18, 98, 262 + 18, 98, "#ff8a00", 2), a, 262, 98)
    return s


def _lemon_mint():
    s = _glass("#d7f0b4", top=90, straw="#16a34a")
    for x, y in [(186, 130), (216, 176)]:
        s += lemon(x, y, 20)
    rng = random.Random("mint")
    for i in range(7):
        x, y = 160 + rng.uniform(0, 70), 70 + rng.uniform(0, 30)
        s += rot(ell(x, y, 17, 8, "#2f9e4f"), rng.randint(0, 170), x, y)
    return s


def _iced_coffee():
    s = _glass("#6b3f22", top=92, straw="#111827", foam="#f6e7cf")
    s += path("M147,114 C170,150 190,128 204,176 C216,140 230,160 244,114 Z", "#f6e7cf", 'opacity=".9"')
    return s


# ---------------------------------------------------------------- desserts


def _cheesecake():
    s = plate(rx=150, ry=58)
    s += path("M116,214 L286,214 L252,150 Z", "#fff0c4", 'stroke="#f0dca0" stroke-width="2"')
    s += path("M116,214 L286,214 L282,230 L120,230 Z", "#9b6a3c")
    s += path("M252,150 L270,174 L246,166 Z", "#fff0c4")
    s += path("M178,176 C196,164 232,164 258,172 L286,214 L116,214 Z", "#e03a52", 'opacity=".92"')
    for x, y in [(206, 182), (236, 190)]:
        s += path(f"M{x},{y} C{x - 12},{y - 6} {x - 12},{y + 14} {x},{y + 18} C{x + 12},{y + 14} {x + 12},{y - 6} {x},{y} Z", "#c61f3a")
    s += circ(300, 224, 9, "#c61f3a") + path("M300,216 L304,208", "none", 'stroke="#3f9b4a" stroke-width="3"')
    return s


def _om_ali():
    s = shadow(264, 130)
    s += path("M86,176 C90,252 310,252 314,176 Z", "#ffffff", 'stroke="#e5e7eb" stroke-width="3"') + ell(200, 176, 114, 26, "#f3f4f6")
    s += ell(200, 176, 100, 20, "#e9b765")
    rng = random.Random("omali")
    for i in range(30):
        s += circ(120 + rng.uniform(0, 160), 168 + rng.uniform(0, 16), rng.uniform(4, 9), rng.choice(["#b8742f", "#d99a3b", "#f2c46d"]))
    for i in range(10):
        x, y = 130 + rng.uniform(0, 140), 166 + rng.uniform(0, 14)
        s += rot(ell(x, y, 6, 3, "#fffaf0"), rng.randint(0, 170), x, y)
    for x in (170, 200, 230):
        s += path(f"M{x},140 C{x - 10},122 {x + 10},108 {x},90", "none", 'stroke="#ffffff" stroke-width="6" stroke-linecap="round" opacity=".8"')
    return s


def _brownie():
    s = plate()
    s += rot(rect(130, 170, 90, 52, "#4a2412", 8), -4, 175, 196) + rect(136, 176, 78, 10, "#6b3a1e", 5)
    s += rot(rect(190, 150, 90, 52, "#5a2d16", 8), 6, 235, 176) + rect(196, 156, 78, 10, "#7a4526", 5)
    s += circ(236, 134, 30, "#fff4dc") + ell(228, 124, 10, 6, "#ffffff", 'opacity=".6"')
    s += path("M196,140 C210,170 226,150 240,186 C252,156 266,176 276,150", "none", 'stroke="#3a1c0d" stroke-width="6" stroke-linecap="round"')
    return s


def _ice_cream():
    s = shadow(264, 90)
    s += path("M138,170 L262,170 L240,248 C238,256 162,256 160,248 Z", "#ffffff", 'stroke="#e5e7eb" stroke-width="3"')
    s += rect(130, 164, 140, 12, "#ffffff", 6, 'stroke="#e5e7eb" stroke-width="3"')
    s += circ(166, 146, 32, "#f4a3c0") + circ(234, 146, 32, "#8a5a36") + circ(200, 114, 34, "#fff4cf")
    s += ell(190, 104, 10, 6, "#ffffff", 'opacity=".6"') + ell(156, 136, 8, 5, "#ffffff", 'opacity=".45"')
    s += circ(200, 76, 11, "#d6182f") + path("M200,66 C204,52 212,48 220,48", "none", 'stroke="#3f7d3a" stroke-width="3" stroke-linecap="round"')
    s += rot(rect(238, 70, 16, 80, "#e9c88a", 3, 'stroke="#c9a15a" stroke-width="2"'), 18, 246, 110)
    return s


def _lava():
    s = plate()
    s += path("M124,214 C120,150 280,150 276,214 Z", "#5a2d16")
    s += path("M150,170 C176,150 224,150 250,170", "none", 'stroke="#8a5026" stroke-width="7" stroke-linecap="round" opacity=".6"')
    s += path("M186,166 L214,166 C220,196 234,214 252,226 C220,240 170,240 148,226 C168,214 182,196 186,166 Z", "#2a120a")
    s += ell(200, 232, 54, 9, "#2a120a")
    s += ell(200, 148, 14, 6, "#ffffff", 'opacity=".55"')
    s += "".join(circ(120 + i * 40, 142 + (i % 2) * 10, 2.4, "#ffffff", 'opacity=".8"') for i in range(8))
    s += circ(280, 220, 10, "#c61f3a") + circ(298, 226, 8, "#7a2a8f")
    return s


def _tiramisu():
    s = plate()
    s += path("M118,206 L270,206 L292,176 L140,176 Z", "#3a2216")
    s += rect(118, 206, 152, 18, "#fff1cf") + rect(118, 224, 152, 14, "#8a5a36") + rect(118, 238, 152, 8, "#fff1cf", 3)
    s += path("M118,206 L270,206 L270,246 L118,246 Z", "none", 'stroke="#e5d6b0" stroke-width="2"')
    s += path("M140,176 L292,176 L270,206 L118,206 Z", "#4a2c1a")
    for i in range(18):
        s += circ(140 + i * 8, 190 + (i % 3) * 5, 2, "#6b4429", 'opacity=".9"')
    s += path("M270,206 L292,176 L292,214 L270,246 Z", "#fff1cf", 'stroke="#e5d6b0" stroke-width="2"')
    s += ell(310, 214, 14, 8, "#3a2216")
    return s


def _waffle():
    s = plate()
    s += rot(rect(132, 142, 136, 116, "#e0a548", 14), -4, 200, 200)
    g = ""
    for i in range(4):
        g += line(150 + i * 32, 150, 150 + i * 32, 250, "#b87a22", 5, 'opacity=".8"')
        g += line(140, 164 + i * 28, 260, 164 + i * 28, "#b87a22", 5, 'opacity=".8"')
    s += rot(g, -4, 200, 200)
    s += path("M150,170 C170,200 200,160 220,214 C236,180 250,200 262,170 L262,184 L150,184 Z", "#a04a14", 'opacity=".85"')
    s += rect(176, 166, 36, 22, "#ffe58f", 5)
    s += circ(246, 168, 13, "#e03a52") + path("M246,156 L250,148", "none", 'stroke="#3f9b4a" stroke-width="3"')
    s += circ(160, 156, 8, "#7a2a8f")
    return s


def _pancakes():
    s = plate(rx=150)
    for i in range(4):
        y = 214 - i * 20
        s += ell(200, y + 10, 94, 18, "#c98a3e") + rect(106, y - 8, 188, 18, "#e0a548") + ell(200, y - 8, 94, 18, "#efc176")
    s += rect(178, 134, 44, 14, "#ffe58f", 4)
    s += path("M120,150 C130,190 150,160 160,200 C172,168 186,190 200,150 C214,186 230,162 244,198 C252,170 264,186 280,150 L280,160 L120,160 Z", "#a04a14", 'opacity=".9"')
    s += circ(300, 220, 9, "#e03a52") + circ(318, 226, 8, "#7a2a8f")
    return s


def _basbousa():
    s = plate()
    s += rot(rect(126, 150, 148, 100, "#e9b24a", 12), -3, 200, 200)
    for i in range(3):
        for j in range(2):
            x, y = 160 + i * 40, 178 + j * 44
            s += rot(path(f"M{x},{y - 18} L{x + 22},{y} L{x},{y + 18} L{x - 22},{y} Z", "#f2c870", 'stroke="#c28522" stroke-width="2"') + ell(x, y, 7, 4, "#fffaf0") + ell(x, y, 5, 2.6, "#e9d3a0"), -3, 200, 200)
    s += ell(150, 160, 14, 6, "#ffffff", 'opacity=".4"')
    return s


def _apple_pie():
    s = plate()
    s += path("M114,214 L286,214 L250,146 Z", "#f6d38a", 'stroke="#c28522" stroke-width="2"')
    s += path("M114,214 L286,214 L282,232 L118,232 Z", "#c98a3e")
    for i in range(5):
        s += line(142 + i * 26, 212, 212 + i * 4, 168, "#c98a3e", 6, 'opacity=".85"')
    for i in range(4):
        s += line(130 + i * 34, 178, 258 - i * 10, 206, "#c98a3e", 6, 'opacity=".5"')
    s += path("M250,146 L286,214 L272,214 Z", "#e0a548")
    for x, y in [(272, 204), (262, 188)]:
        s += circ(x, y, 6, "#b8531f")
    s += circ(300, 226, 24, "#fff4dc") + ell(294, 218, 8, 5, "#ffffff", 'opacity=".6"')
    return s


# ---------------------------------------------------------------- registry

BG = {
    "Burgers": ("#fff4e5", "#ffd9a8"),
    "Main Dishes": ("#fdeeee", "#f7c9c0"),
    "Sides": ("#fffadf", "#ffe58f"),
    "Salads": ("#edf8e9", "#c3e8b8"),
    "Drinks": ("#eaf4fd", "#b9dcf7"),
    "Desserts": ("#fdecf3", "#f6c4da"),
}

BREAD = "#e9a23b"

ART = {
    # Burgers
    "Beef Burger": ("Burgers", lambda: burger(BREAD, ("lettuce", "tomato", "patty", "onion"))),
    "Chicken Burger": ("Burgers", lambda: burger("#eab05a", ("lettuce", "tomato", "patty:grill"))),
    "Cheese Burger": ("Burgers", lambda: burger(BREAD, ("lettuce", "patty", "cheese", "pickle"))),
    "Double Smash": ("Burgers", lambda: burger("#e39a2f", ("patty", "cheese", "patty", "cheese"))),
    "BBQ Bacon Burger": ("Burgers", lambda: burger("#d98a2b", ("patty", "cheese", "bacon", "onion"))),
    "Mushroom Swiss Burger": ("Burgers", lambda: burger("#e9a23b", ("patty", "cheese:swiss", "mushroom"))),
    "Spicy Jalapeno Burger": ("Burgers", lambda: burger("#e0922c", ("lettuce", "patty", "cheese:pepper", "jalapeno"))),
    "Crispy Chicken Burger": ("Burgers", lambda: burger("#f0b566", ("lettuce", "tomato", "patty:crispy"))),
    "Veggie Burger": ("Burgers", lambda: burger("#d9a85a", ("lettuce", "tomato", "patty:veg", "onion"))),
    "Kids Mini Burger": ("Burgers", lambda: burger(BREAD, ("patty", "cheese"), scale=0.78)),
    # Main dishes
    "Grilled Chicken": ("Main Dishes", _grilled_chicken),
    "Mixed Grill": ("Main Dishes", _mixed_grill),
    "Chicken Wings": ("Main Dishes", _wings),
    "Chicken Strips": ("Main Dishes", _strips),
    "Beef Steak": ("Main Dishes", _steak),
    "Chicken Shawarma Plate": ("Main Dishes", _shawarma),
    "Grilled Kofta": ("Main Dishes", _kofta),
    "Fish Fillet": ("Main Dishes", _fish),
    "Pasta Alfredo": ("Main Dishes", _pasta),
    "Chicken Fajita": ("Main Dishes", _fajita),
    # Sides
    "French Fries": ("Sides", lambda: _fries()),
    "Onion Rings": ("Sides", _onion_rings),
    "Cheese Fries": ("Sides", lambda: _fries(cheese=True, bacon=True)),
    "Sweet Potato Fries": ("Sides", lambda: _fries("#f29a3a")),
    "Coleslaw": ("Sides", _coleslaw),
    "Mozzarella Sticks": ("Sides", _mozzarella),
    "Potato Wedges": ("Sides", _wedges),
    "Corn Cup": ("Sides", _corn),
    "Garlic Bread": ("Sides", _garlic_bread),
    "Nachos": ("Sides", _nachos),
    # Salads
    "Caesar Salad": ("Salads", lambda: _salad([("crouton", "", 7), ("feta", "", 4), ("chunk", "#d9b98a", 4)], ("#8fd17a", "#6cbf5c", "#a8dd8a"), seed="caesar")),
    "Greek Salad": ("Salads", lambda: _salad([("tomato", "", 5), ("cucumber", "", 6), ("olive", "#3a2a3f", 6), ("feta", "", 5)], seed="greek")),
    "Tuna Salad": ("Salads", lambda: _salad([("chunk", "#b9bfc9", 8), ("tomato", "", 4), ("olive", "#2f2a35", 4), ("egg", "", 3)], seed="tuna")),
    "Chicken Salad": ("Salads", lambda: _salad([("chunk", "#e2c28f", 8), ("tomato", "", 4), ("cucumber", "", 4), ("crouton", "", 4)], seed="chsalad")),
    "Fattoush": ("Salads", lambda: _salad([("pita", "", 8), ("tomato", "", 5), ("cucumber", "", 4), ("leaf", "#d6362f", 5)], seed="fattoush")),
    "Tabbouleh": ("Salads", lambda: _salad([("leaf", "#2f7d3a", 26), ("tomato", "", 4), ("dot", "#f2e7b8", 14)], ("#3f9b4a", "#2f8a3e", "#5cb35a"), seed="tabbouleh")),
    "Rocca Salad": ("Salads", lambda: _salad([("tomato", "", 4), ("feta", "", 4), ("dot", "#7a2a8f", 5)], ("#2f8a3e", "#4caf50", "#6cbf5c"), seed="rocca")),
    "Garden Salad": ("Salads", lambda: _salad([("tomato", "", 5), ("cucumber", "", 5), ("leaf", "#f08a2b", 5), ("olive", "#2f2a35", 3)], seed="garden")),
    "Quinoa Salad": ("Salads", lambda: _salad([("dot", "#e9d3a0", 36), ("tomato", "", 4), ("avocado", "", 3), ("dot", "#7a4a2a", 8)], seed="quinoa")),
    "Avocado Salad": ("Salads", lambda: _salad([("avocado", "", 7), ("tomato", "", 4), ("egg", "", 3), ("dot", "#f2f2f2", 8)], seed="avocado")),
    # Drinks
    "Pepsi": ("Drinks", lambda: _glass("#3a1f12", top=84, straw="#ef4444", bubbles=True)),
    "7Up": ("Drinks", lambda: _glass("#e6f7c8", top=84, straw="#16a34a", bubbles=True, extras=lemon(262, 96, 17))),
    "Mineral Water": ("Drinks", _water),
    "Fresh Orange Juice": ("Drinks", _orange_juice),
    "Mango Juice": ("Drinks", _mango),
    "Lemon Mint": ("Drinks", _lemon_mint),
    "Iced Coffee": ("Drinks", _iced_coffee),
    "Turkish Coffee": ("Drinks", _cup_turkish),
    "Vanilla Milkshake": ("Drinks", lambda: _milkshake("#fff1c9", "#ffffff", None)),
    "Chocolate Milkshake": ("Drinks", lambda: _milkshake("#8a5230", "#f6e7d4", "#3a1c0d")),
    # Desserts
    "Cheesecake": ("Desserts", _cheesecake),
    "Om Ali": ("Desserts", _om_ali),
    "Chocolate Brownie": ("Desserts", _brownie),
    "Ice Cream Cup": ("Desserts", _ice_cream),
    "Molten Lava Cake": ("Desserts", _lava),
    "Tiramisu": ("Desserts", _tiramisu),
    "Waffle": ("Desserts", _waffle),
    "Pancakes": ("Desserts", _pancakes),
    "Basbousa": ("Desserts", _basbousa),
    "Apple Pie": ("Desserts", _apple_pie),
}

# صورة التصنيف = رسمة صنف مميّز منه
CATEGORY_ART = {
    "Burgers": "Double Smash",
    "Main Dishes": "Mixed Grill",
    "Sides": "Cheese Fries",
    "Salads": "Greek Salad",
    "Drinks": "Chocolate Milkshake",
    "Desserts": "Ice Cream Cup",
}


SCALE = {"Burgers": 1.28, "Main Dishes": 1.1, "Sides": 1.08, "Salads": 1.14, "Drinks": 1.0, "Desserts": 1.1}


def _scaled(body, group):
    k = SCALE.get(group, 1.0)
    return f'<g transform="translate(200 262) scale({k}) translate(-200 -262)">{body}</g>'


def render(item_name):
    group, fn = ART[item_name]
    c1, c2 = BG[group]
    return wrap_svg(_scaled(fn(), group), c1, c2)


def render_category(group):
    _, fn = ART[CATEGORY_ART[group]]
    c1, c2 = BG[group]
    c1, c2 = shade(c1, -0.04), shade(c2, -0.08)
    return wrap_svg(_scaled(fn(), group), c1, c2)