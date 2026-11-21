#!/usr/bin/env python3
"""Genera el perfil completo: los SVG (dark y light) y el README.md, a partir de CONTENT.

Edita CONTENT y ejecuta:  python3 build.py

Las fuentes (Inter Tight, Inter, JetBrains Mono) se descargan de Google Fonts y se
incrustan en cada SVG recortadas a los caracteres que usa (≈3 KB por fuente), así el
perfil se ve igual en cualquier sistema y los anchos de texto se miden de verdad.
Las descargas se guardan en assets/src/ (ignorado por git).
"""
import base64
import datetime
import hashlib
import json
import os
import re
import struct
import urllib.parse
import urllib.request
from xml.sax.saxutils import escape

ROOT = os.path.dirname(os.path.abspath(__file__))
ASSETS = os.path.join(ROOT, "assets")
CACHE = os.path.join(ASSETS, "src")

# ------------------------------------------------------------------ contenido
CONTENT = {
    # La misma marca que el portafolio: «Diseñador UX de producto» y la tesis del criterio.
    "name": ["Jorge", "Ramos"],
    "overline": "KNOWLEDGE IS UNIVERSAL. JUDGMENT ISN'T.",
    "role_tag": "Hello, I'm",  # nombre del marco de Figma que rodea el nombre
    "role": ("Product UX designer", "with an engineer's mind."),  # solo para el texto alternativo del banner
    # chips del banner: todos en el celeste del perfil
    "chips": [("#38BDF8", "Product design"), ("#38BDF8", "Design Systems"), ("#38BDF8", "Design Ops"), ("#38BDF8", "AI + judgment")],
    "links": [  # (etiqueta, url, glifo, insignia opcional). El primero se dibuja como botón principal.
        ("LinkedIn", "https://www.linkedin.com/in/jorge-ramos-tellez", "linkedin"),
        # cuando el portafolio tenga dominio, cambia la url y quita «WIP»
        ("Portfolio", "https://github.com/JorgeRamos-UX/Portafolio-UX", "globe", "WIP"),
    ],
    # Dos párrafos cortos: quién eres y qué haces (con prueba). Se leen en 10 segundos.
    "intro": ("I'm a **Product UX designer with an engineer's mind**. I trained in Cybernetic Electronics Engineering, "
              "so I start with how the system works, and only then design the screen.\n\n"
              "I design products end to end, and the tools that help teams build them well: design systems, Design Ops "
              "and AI agents. At **[Hexalis](https://hexalis.org/en/)**, an open source nonprofit, I'm the product "
              "designer behind its Design System and Design Ops Toolkit."),
    "about": [  # (glifo, color, título, descripción, etiquetas)
        ("pen", "#F24E1E", "Product UX design",
         "From problem framing and user flows to polished, high-fidelity interfaces for web and mobile products.",
         ["Flows", "Interaction", "Hi-fi UI", "Prototyping"]),
        ("components", "#A259FF", "Design Systems & DesignOps",
         "Components, tokens and variables, plus the documentation and processes that help teams build consistently at scale.",
         ["Components", "Tokens", "Variables", "Docs"]),
        ("search", "#1ABCFE", "UX Research & IA",
         "Interviews, synthesis and information architecture that turn messy problems into clear structures.",
         ["Interviews", "Synthesis", "IA"]),
        ("sparkle", "#0ACF83", "AI with judgment",
         "AI brings the knowledge; my judgment decides what stays. Agentic design systems, design-to-code and automations.",
         ["Agents", "Design-to-code", "Automation"]),
    ],
    # «How I break down a problem»: las cinco etapas del portafolio, la vida de una pieza.
    # (ícono, etapa, pregunta que responde, una frase corta: dos líneas como máximo)
    "method": [
        ("chip", "Engineering", "How it works", "System first, then the screen."),
        ("nodes", "Systems", "How it connects", "Problems live between screens."),
        ("components", "Design", "How it's made", "I design how teams build it."),
        ("sparkle", "AI", "How it's built", "AI informs. Judgment decides."),
        ("person", "People", "Who it's for", "People trust what they understand."),
    ],
    # sección «AI with judgment»: el agente construye un componente y pregunta antes de decidir
    "agent": {"name": "Design system agent", "status": "online · reads tokens.json",
              "prompt": "Create a primary button for the onboarding screen",
              "found": "Found 3 tokens in the library: brand/primary, text/on-brand and radius/md.",
              "question": "Which size should it use?", "options": ["S · 32", "M · 44", "L · 56"], "pick": 1,
              "done": "Published Button / Primary to the library.", "cta": "Get started",
              "toast": "Jorge approved · published to library",
              # Las tres reglas con las que diseño la IA: vienen del caso ATLAS del portafolio (criterio.ts).
              "rules": [("sparkle", "It shows its sources", "Every field the AI fills is marked, with where it came from."),
                        ("question", "It says when it doesn't know", "“Not found” beats a confident guess."),
                        ("person", "A person decides", "Accept or discard in one click. The call stays human.")]},
    # Banner del portafolio (assets/portfolio-*.svg): una ventana al sitio que se está construyendo.
    # Cifras tal como están publicadas en milanko.hexalis.org, hexalis.org y el caso de ATLAS del portafolio.
    "portfolio": {"url": "https://github.com/JorgeRamos-UX/Portafolio-UX", "status": "PORTFOLIO · IN PROGRESS",
                  "title": ["Case studies,", "told by decisions."],
                  "lead": "The why behind every call in ATLAS, Milanko and the Hexalis libraries.",
                  "cta": "Follow the build ↗", "aside": "Built in public on GitHub",
                  "cases": [("#2DA44E", "ATLAS", "Syllabus prep: 8.77 h → 1.5 h"),
                            ("#FF8A4C", "Milanko", "NASA Space Apps 2026"),
                            ("#4C7DEB", "Hexalis libraries", "85 + 112 components, open source")],
                  "note": ('Meanwhile: <a href="https://milanko.hexalis.org/">Milanko</a> is live (made at Hexalis for the '
                           'NASA Space Apps Challenge 2026; not an official NASA app nor endorsed by NASA) and the '
                           '<a href="https://hexalis.org/en/#sistema">Hexalis libraries</a> are open source.')},
    "exploring": ["Product design strategy", "Human-Computer Interaction", "Agentic design systems",
                  "AI + Product Design", "Design-to-code"],
    "contact": {"question": "What decision is your team weighing right now?"},
    "quote": "Product design with an *engineer's mind*.",  # *…* = texto seleccionado
    "signature": "designed in figma · versioned with git",
    # Pantalla que se construye dentro del banner: de wireframe a alta fidelidad.
    # La IA sugiere el texto del botón y Jorge decide: la tesis del criterio en pequeño.
    "mock": {"screen": "New project", "title": "Ideas, shipped.", "subtitle": ["From first sketch", "to production-ready."],
             "tags": [("#F24E1E", "Research"), ("#A259FF", "Design"), ("#1ABCFE", "Code")],
             "cta_before": "Submit", "cta": "Get started", "component": "Button / Primary", "token": "brand/primary",
             "comment": ["Try “Get started” —", "“Submit” feels like a form."]},
}

# -------------------------------------------------------------------- tokens
THEMES = {
    "dark": dict(bg="#0D1117", surface="#161B22", raised="#1C2128", border="#30363D", fg="#E6EDF3",
                 muted="#8B949E", dot="#21262D", handle="#0D1117", shadow=".55"),
    "light": dict(bg="#FFFFFF", surface="#F6F8FA", raised="#FFFFFF", border="#D0D7DE", fg="#1F2328",
                  muted="#59636E", dot="#E4E8EC", handle="#FFFFFF", shadow=".12"),
}
# Paleta celeste: ACCENT dibuja líneas, brillos y números; BRAND rellena el botón principal.
# El azul claro no aguanta texto blanco (2.8:1 en sky-500), así que sobre BRAND va ON_BRAND (8.3:1).
ACCENT = "#38BDF8"     # celeste (sky-400)
BRAND = "#7DD3FC"      # celeste claro (sky-300)
BRAND_DEEP = "#0284C7" # fondo del degradado de la tarjeta del banner
ON_BRAND = "#082F49"   # texto e íconos sobre BRAND
CLAUDE = "#D97757"     # solo en el agente de la sección «AI with judgment»: es su marca, no la tuya
AI = "#068454"         # la IA genérica del banner: el verde de Figma oscurecido hasta AA con texto blanco
SELECT = "#0D99FF"     # selección de Figma
COMPONENT = "#9747FF"  # instancias de componente en Figma
REDLINE = "#F24822"    # medidas de Figma
RADIUS = {"sm": 7, "md": 12, "lg": 16, "xl": 20}  # etiquetas · botones · tarjetas · banner
W = 900   # ancho de escritorio (GitHub muestra el README a 846 px)
MW = 360  # ancho móvil (GitHub muestra el README a ~293 px en un teléfono)

FONTS = {  # clave: (familia en Google Fonts, peso, pila de respaldo, ancho opcional). Las mismas del portafolio.
    "display": ("Mona Sans", 800, "-apple-system, BlinkMacSystemFont, 'Segoe UI', Helvetica, Arial, sans-serif", 112.5),
    "regular": ("Mona Sans", 400, "-apple-system, BlinkMacSystemFont, 'Segoe UI', Helvetica, Arial, sans-serif"),
    "medium": ("Mona Sans", 500, "-apple-system, BlinkMacSystemFont, 'Segoe UI', Helvetica, Arial, sans-serif"),
    "semibold": ("Mona Sans", 600, "-apple-system, BlinkMacSystemFont, 'Segoe UI', Helvetica, Arial, sans-serif"),
    "bold": ("Mona Sans", 700, "-apple-system, BlinkMacSystemFont, 'Segoe UI', Helvetica, Arial, sans-serif"),
    "mono": ("Martian Mono", 500, "ui-monospace, SFMono-Regular, Menlo, Consolas, monospace"),
}

# ---------------------------------------------------------------------- red
def fetch(url, path=None):
    # UA neutro: Google Fonts responde TTF (no woff2), que es lo que sabemos medir
    req = urllib.request.Request(url, headers={"User-Agent": "curl/8 (profile-readme build)"})
    try:
        data = urllib.request.urlopen(req, timeout=30).read()  # descarga antes de abrir: sin archivos vacíos si falla
    except OSError as e:
        # «::error::» lo muestra GitHub Actions como anotación, visible sin iniciar sesión
        print(f"::error::No se pudo descargar {url} ({e})")
        raise SystemExit(1)
    if path:
        with open(path, "wb") as f:
            f.write(data)
    return data


def cached(name, url):
    os.makedirs(CACHE, exist_ok=True)
    path = os.path.join(CACHE, name)
    if not os.path.exists(path):
        fetch(url, path)
    with open(path, "rb") as f:
        return f.read()


def data_uri(svg_text):
    return "data:image/svg+xml;base64," + base64.b64encode(svg_text.encode()).decode()


# ------------------------------------------------------------------- fuentes
def font_file(key, text=None):
    """TTF completo (para medir) o recortado a `text` (para incrustar)."""
    family, weight, _, *width = FONTS[key]
    q = f"family={family.replace(' ', '+')}:" + (f"wdth,wght@{width[0]},{weight}" if width else f"wght@{weight}")
    tag = f"{family.replace(' ', '')}-{weight}" + (f"-w{width[0]}" if width else "")
    if text is not None:
        q += "&text=" + urllib.parse.quote(text)
        tag += "-" + hashlib.sha1(text.encode()).hexdigest()[:10]
    css = cached(f"{tag}.css", f"https://fonts.googleapis.com/css2?{q}").decode()
    return cached(f"{tag}.ttf", re.search(r"url\((\S+?)\)", css).group(1))


def ttf_metrics(b):
    """unitsPerEm y avance por carácter, leyendo head/hhea/hmtx/cmap (formato 4)."""
    n = struct.unpack(">H", b[4:6])[0]
    tables = {b[12 + 16 * i:16 + 16 * i].decode("latin-1"): struct.unpack(">I", b[20 + 16 * i:24 + 16 * i])[0]
              for i in range(n)}
    upm = struct.unpack(">H", b[tables["head"] + 18:tables["head"] + 20])[0]
    n_hm = struct.unpack(">H", b[tables["hhea"] + 34:tables["hhea"] + 36])[0]
    hmtx = tables["hmtx"]
    adv = [struct.unpack(">H", b[hmtx + 4 * i:hmtx + 4 * i + 2])[0] for i in range(n_hm)]
    o = tables["cmap"]
    sub = None
    for i in range(struct.unpack(">H", b[o + 2:o + 4])[0]):
        pid, eid, off = struct.unpack(">HHI", b[o + 4 + 8 * i:o + 12 + 8 * i])
        if (pid, eid) == (3, 1):
            sub = o + off
    segs = struct.unpack(">H", b[sub + 6:sub + 8])[0] // 2
    col = lambda off: struct.unpack(f">{segs}H", b[off:off + 2 * segs])
    ends, starts = col(sub + 14), col(sub + 16 + 2 * segs)
    deltas, ranges = col(sub + 16 + 4 * segs), col(sub + 16 + 6 * segs)
    ro = sub + 16 + 6 * segs  # inicio de idRangeOffset
    widths = {}
    for s in range(segs):
        for cp in range(starts[s], min(ends[s], 0xFFFE) + 1):
            if ranges[s] == 0:
                gid = (cp + deltas[s]) & 0xFFFF
            else:
                p = ro + 2 * s + ranges[s] + 2 * (cp - starts[s])
                gid = struct.unpack(">H", b[p:p + 2])[0]
                gid = (gid + deltas[s]) & 0xFFFF if gid else 0
            if gid:
                widths[chr(cp)] = adv[min(gid, n_hm - 1)]
    return upm, widths


METRICS = {}


def tw(text, size, font="regular", ls=0):
    """Ancho real del texto con la fuente incrustada (sin kerning)."""
    if font not in METRICS:
        METRICS[font] = ttf_metrics(font_file(font))
    upm, widths = METRICS[font]
    return sum(widths.get(ch, upm * .6) for ch in text) * size / upm + ls * max(len(text) - 1, 0)


def wrap(s, width, font="regular", size=14, ls=0):
    """Parte un texto en líneas que caben en `width`, midiendo con la fuente real."""
    lines, cur = [], ""
    for word in s.split():
        cand = f"{cur} {word}".strip()
        if cur and tw(cand, size, font, ls) > width:
            lines.append(cur)
            cur = word
        else:
            cur = cand
    return lines + [cur] if cur else lines


def wrap_even(s, width, font="regular", size=14):
    """Como wrap, pero si salen dos líneas las deja parejas: nada de una palabra sola abajo."""
    lines = wrap(s, width, font, size)
    if len(lines) != 2:
        return lines
    words = s.split()
    cuts = [(" ".join(words[:k]), " ".join(words[k:])) for k in range(1, len(words))]
    cuts = [c for c in cuts if max(tw(x, size, font) for x in c) <= width]
    return list(min(cuts, key=lambda c: max(tw(x, size, font) for x in c)))


def _rgb(h):
    return [int(h[i:i + 2], 16) for i in (1, 3, 5)]


def mix(a, b, k):
    """a mezclado con b; k = proporción de a."""
    return "#" + "".join(f"{round(x * k + y * (1 - k)):02X}" for x, y in zip(_rgb(a), _rgb(b)))


def contrast(a, b):
    def lum(h):
        c = [x / 255 for x in _rgb(h)]
        c = [x / 12.92 if x <= .03928 else ((x + .055) / 1.055) ** 2.4 for x in c]
        return .2126 * c[0] + .7152 * c[1] + .0722 * c[2]
    hi, lo = sorted((lum(a), lum(b)), reverse=True)
    return (hi + .05) / (lo + .05)


def ink(color, bg, target=4.5):
    """El mismo tono, oscurecido o aclarado lo justo para que como texto pase WCAG AA sobre `bg`."""
    toward = "#000000" if contrast(bg, "#000000") > contrast(bg, "#FFFFFF") else "#FFFFFF"
    for k in range(0, 101, 2):
        c = mix(toward, color, k / 100)
        if contrast(c, bg) >= target:
            return c
    return toward


USED = {}  # caracteres por fuente del SVG que se está armando


def use(font, chars):
    USED.setdefault(font, set()).update(chars)


def text(x, y, s, font="regular", size=14, fill="currentColor", anchor=None, ls=0, attrs="", tail=""):
    use(font, s)
    a = f' text-anchor="{anchor}"' if anchor else ""
    l = f' letter-spacing="{ls}"' if ls else ""
    return (f'<text x="{x:.1f}" y="{y:.1f}" class="f-{font}" font-size="{size}" fill="{fill}"{a}{l}{attrs}>'
            f'{escape(s)}{tail}</text>')


def font_css():
    out = []
    for key in sorted(USED):
        family, weight, fallback, *_ = FONTS[key]
        chars = "".join(sorted(USED[key] | {" "}))
        b64 = base64.b64encode(font_file(key, chars)).decode()
        out.append(f"@font-face{{font-family:'p-{key}';font-weight:{weight};"
                   f"src:url(data:font/ttf;base64,{b64}) format('truetype')}}"
                   f".f-{key}{{font-family:'p-{key}','{family}',{fallback};font-weight:{weight}}}")
    USED.clear()
    return "".join(out)


def svg(w, h, body, css="", title=""):
    return (f'<svg xmlns="http://www.w3.org/2000/svg" width="{w}" height="{h}" viewBox="0 0 {w} {h}" '
            f'fill="none" role="img"><title>{escape(title)}</title>'
            f'<style>{font_css()}{css}@media (prefers-reduced-motion: reduce){{*{{animation:none!important}}}}</style>'
            f'{body}</svg>')


def dual(piece, *args):
    """SVG móvil con los dos temas dentro; elige con prefers-color-scheme.

    GitHub reescribe cualquier <source> que mencione el tema cuando el usuario fija uno,
    así que no se puede combinar «ancho + tema» en el <picture>: el móvil va en un solo archivo.
    """
    parts = []
    for name, t in THEMES.items():
        w, h, body, css, title = piece(dict(t, name=name), *args)
        if name == "dark":  # ids únicos para que los dos temas no se pisen
            body = re.sub(r'id="([^"]+)"', r'id="d-\1"', body)
            body = re.sub(r"url\(#([^)]+)\)", r"url(#d-\1)", body)
        parts.append(f'<g class="th-{name}">{body}</g>')
    css += ".th-dark{display:none}@media (prefers-color-scheme: dark){.th-light{display:none}.th-dark{display:inline}}"
    return svg(w, h, "".join(parts), css, title)


# --------------------------------------------------------------------- iconos
def claude_path():
    src = cached("claude.svg", "https://cdn.simpleicons.org/claude").decode()
    return src.split(' d="', 1)[1].split('"', 1)[0]


def claude_mark(cx, cy, size, fill="#fff"):
    """Logo de Claude centrado en (cx, cy); el path original mide 24×24."""
    k = size / 24
    return f'<path transform="translate({cx - size / 2:.1f} {cy - size / 2:.1f}) scale({k:.4f})" fill="{fill}" d="{claude_path()}"/>'


GLYPHS = {
    "pen": '<path d="M12 28l2.5-7 10-10 4.5 4.5-10 10z M22 13.5l4.5 4.5" stroke="{c}" stroke-width="2" stroke-linejoin="round"/>',
    "components": ('<g fill="{c}"><path class="cmp" d="M20 9l4 4-4 4-4-4z"/>'
                   '<path class="cmp" style="animation-delay:.3s" d="M27 16l4 4-4 4-4-4z"/>'
                   '<path class="cmp" style="animation-delay:.6s" d="M20 23l4 4-4 4-4-4z"/>'
                   '<path class="cmp" style="animation-delay:.9s" d="M13 16l4 4-4 4-4-4z"/></g>'),
    "search": '<circle cx="18" cy="18" r="6.5" stroke="{c}" stroke-width="2.2"/><path d="M23 23l6 6" stroke="{c}" stroke-width="2.2" stroke-linecap="round"/>',
    "sparkle": '<path d="M20 9l2.6 8.4L31 20l-8.4 2.6L20 31l-2.6-8.4L9 20l8.4-2.6z" fill="{c}"/>',
    # glifos de 20×20 para los botones de contacto
    "mail": '<rect x="2" y="4" width="16" height="12" rx="3" stroke="{c}" stroke-width="1.8"/><path d="M3 6l7 5 7-5" stroke="{c}" stroke-width="1.8" stroke-linejoin="round"/>',
    "linkedin": ('<rect x="2" y="2" width="16" height="16" rx="4" fill="{c}"/>'
                 '<path d="M6.5 8.5v5.5M6.5 6v.01M9.5 14V8.5M9.5 11c0-1.6 1-2.6 2.3-2.6s2.2.9 2.2 2.6V14" stroke="{bg}" stroke-width="1.7" stroke-linecap="round"/>'),
    "arrow": '<path d="M4 10h12M11 5l5 5-5 5" stroke="{c}" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/>',
    "globe": ('<circle cx="10" cy="10" r="7.5" stroke="{c}" stroke-width="1.8"/>'
              '<path d="M2.5 10h15M10 2.5c2.2 2.1 3.2 4.6 3.2 7.5s-1 5.4-3.2 7.5c-2.2-2.1-3.2-4.6-3.2-7.5s1-5.4 3.2-7.5z" stroke="{c}" stroke-width="1.6" stroke-linejoin="round"/>'),
}

CURSOR = "M0 0L0 17L4.6 12.8L7.6 19.6L10.4 18.4L7.4 11.6L13.6 11.4Z"


def cursor(color, label, t):
    lw = tw(label, 12, "semibold") + 16
    return (f'<path d="{CURSOR}" fill="{color}" stroke="{t["handle"]}" stroke-width="1.2" stroke-linejoin="round"/>'
            f'<rect x="12" y="18" width="{lw:.0f}" height="22" rx="6" fill="{color}"/>'
            + text(20, 33, label, "semibold", 12, "#fff"))


def ai_mark(cx, cy, size, fill="#fff"):
    """Destello de la IA centrado en (cx, cy); el glifo mide 22 px dentro de su caja de 40."""
    k = size / 22
    return f'<g transform="translate({cx - 20 * k:.1f} {cy - 20 * k:.1f}) scale({k:.4f})">{GLYPHS["sparkle"].format(c=fill)}</g>'


def diamond(x, y, s, color):
    """Ícono de componente de Figma (cuatro rombos) de lado s con esquina superior izquierda en (x, y)."""
    h = s / 4
    pts = [(x + s / 2, y + h), (x + h, y + s / 2), (x + s - h, y + s / 2), (x + s / 2, y + s - h)]
    return "".join(f'<path d="M{px:.1f} {py - h:.1f}l{h:.1f} {h:.1f}-{h:.1f} {h:.1f}-{h:.1f}-{h:.1f}z" fill="{color}"/>'
                   for px, py in pts)


# -------------------------------------------------------------------- banner
def rulers(t, h, sel_x, sel_y):
    """Reglas de Figma en los bordes del lienzo, con el rango de la selección resaltado."""
    r = 22
    out = [f'<rect width="{W}" height="{r}" fill="{t["surface"]}"/><rect width="{r}" height="{h}" fill="{t["surface"]}"/>',
           f'<rect x="{sel_x[0]}" width="{sel_x[1] - sel_x[0]:.0f}" height="{r}" fill="{SELECT}" fill-opacity=".14"/>',
           f'<rect y="{sel_y[0]}" width="{r}" height="{sel_y[1] - sel_y[0]:.0f}" fill="{SELECT}" fill-opacity=".14"/>']
    ticks = []
    for x in range(r + 8, W, 10):
        ticks.append(f"M{x} {r}v{-7 if x % 50 == 0 else -4}")
        if x % 100 == 0:
            out.append(text(x + 3, 11, str(x), "mono", 8, t["muted"]))
    for y in range(r + 8, h, 10):
        ticks.append(f"M{r} {y}h{-7 if y % 50 == 0 else -4}")
    out.append(f'<path d="{"".join(ticks)}" stroke="{t["border"]}"/>')
    out.append(f'<path d="M0 {r - .5}H{W}M{r - .5} 0V{h}" stroke="{t["border"]}"/>')
    out.append(f'<rect width="{r}" height="{r}" fill="{t["surface"]}"/>')
    return "".join(out)


def phone(t, px, py):
    """Pantalla que se construye en vivo: wireframe punteado → el cursor dibuja el hero → texto,
    etiquetas y botón en alta fidelidad. Todas las piezas viven en coordenadas del teléfono."""
    m = CONTENT["mock"]
    pw, ph = 176, 296
    dash = f'stroke="{t["muted"]}" stroke-opacity=".75" stroke-dasharray="3 3"'
    # etiquetas pequeñas bajo el subtítulo
    tags, x = [], 16
    for color, label in m["tags"]:
        tgw = tw(label, 8.5, "medium") + 20
        tags.append((x, tgw, color, label))
        x += tgw + 4
    wire = "".join(f'<rect x="{x + .5:.1f}" y="203.5" width="{tgw - 1:.1f}" height="15" rx="7.5" {dash}/>' for x, tgw, _, _ in tags)
    tag_svg = "".join(
        f'<rect x="{x + .5:.1f}" y="203.5" width="{tgw - 1:.1f}" height="15" rx="7.5" fill="{t["surface"]}" stroke="{t["border"]}"/>'
        f'<circle cx="{x + 8:.1f}" cy="211" r="2.5" fill="{color}"/>' + text(x + 13, 214, label, "medium", 8.5, t["fg"])
        for x, tgw, color, label in tags)
    dims = "152 × 86"
    dmw = tw(dims, 9, "semibold") + 10
    comp_w = tw(m["component"], 10, "semibold") + 18
    return f"""
    <g transform="translate({px} {py})">
      <rect x=".5" y=".5" width="{pw - 1}" height="{ph - 1}" rx="28" fill="{t["raised"]}" stroke="{t["border"]}" filter="url(#lift)"/>
      <rect x="68" y="10" width="40" height="11" rx="5.5" fill="{t["border"]}"/>
      {text(16, 48, m["screen"], "bold", 14, t["fg"])}
      <circle cx="156" cy="43" r="9" fill="{ACCENT}" fill-opacity=".22"/>
      <g class="wire">
        <rect x="12.5" y="60.5" width="151" height="85" rx="14" {dash}/>
        <path d="M18 66L158 140M158 66L18 140" {dash} stroke-width=".8"/>
        <rect x="16" y="157" width="104" height="13" rx="4" fill="{t["border"]}"/>
        <rect x="16" y="177" width="80" height="6" rx="3" fill="{t["border"]}"/>
        <rect x="16" y="189" width="104" height="6" rx="3" fill="{t["border"]}"/>
        {wire}
        <rect x="12.5" y="242.5" width="151" height="37" rx="12" {dash}/>
      </g>
      <g class="s-hero">
        <clipPath id="hero"><rect x="12" y="60" width="152" height="86" rx="14"/></clipPath>
        <g clip-path="url(#hero)">
          <rect x="12" y="60" width="152" height="86" fill="url(#brand)"/>
          <circle cx="56" cy="104" r="24" fill="#fff" fill-opacity=".92"/>
          <rect x="84" y="82" width="40" height="40" rx="10" fill="#1F2328" fill-opacity=".85" transform="rotate(12 104 102)"/>
          <path d="M126 136L148 96L170 136Z" fill="#fff" fill-opacity=".35"/>
          <circle cx="142" cy="76" r="5" fill="#fff" fill-opacity=".7"/>
        </g>
      </g>
      <g class="dim">
        <rect x="{88 - dmw / 2:.1f}" y="149" width="{dmw:.1f}" height="13" rx="3" fill="{SELECT}"/>
        {text(88, 158.5, dims, "semibold", 9, "#fff", "middle")}
      </g>
      <g class="s-text">
        {text(16, 170, m["title"], "display", 17, t["fg"], ls=-.3)}
        {"".join(text(16, 184 + i * 12, l, "regular", 9.5, t["muted"]) for i, l in enumerate(m["subtitle"]))}
      </g>
      <g class="red">
        <path d="M134 147v10M130 147h8M130 157h8" stroke="{REDLINE}" stroke-width="1.2"/>
        <rect x="141" y="146" width="18" height="12" rx="3" fill="{REDLINE}"/>
        {text(150, 155, "12", "bold", 8.5, "#fff", "middle")}
      </g>
      <g class="s-tags">{tag_svg}</g>
      <g class="s-cta">
        <rect x="12" y="242" width="152" height="38" rx="12" fill="{BRAND}"/>
        <g class="cta-old">{text(88, 265, m["cta_before"], "semibold", 12, ON_BRAND, "middle")}</g>
        <g class="cta-new">{text(88, 265, m["cta"], "semibold", 12, ON_BRAND, "middle")}</g>
      </g>
      <rect class="swap" x="10" y="240" width="156" height="42" rx="13" stroke="{ACCENT}" stroke-width="2"/>
      <circle class="tap" cx="100" cy="261" r="14" fill="{SELECT}" fill-opacity=".3"/>
      <rect x="64" y="286" width="48" height="4" rx="2" fill="{t["muted"]}" fill-opacity=".45"/>
      <g class="comp">
        <rect x="9.5" y="239.5" width="157" height="43" rx="13" stroke="{COMPONENT}" stroke-width="1.5"/>
        <rect x="10" y="224" width="{comp_w:.0f}" height="15" rx="4" fill="{COMPONENT}"/>
        {diamond(13, 226.5, 10, "#fff")}
        {text(26, 234.5, m["component"], "semibold", 10, "#fff")}
      </g>
    </g>"""


def token_chip(t, x, y, target_x):
    """Chip de variable de Figma enlazado al color de la tarjeta."""
    label = CONTENT["mock"]["token"]
    w = tw(label, 10.5, "mono") + 34
    end = x + w if x < target_x else x
    return f"""
    <g class="tok">
      <path d="M{target_x} {y + 12}H{end:.1f}" stroke="{COMPONENT}" stroke-width="1.2" stroke-dasharray="2 3"/>
      <circle cx="{target_x}" cy="{y + 12}" r="3" fill="{COMPONENT}"/>
      <rect x="{x + .5}" y="{y + .5}" width="{w:.0f}" height="23" rx="7" fill="{t["raised"]}" stroke="{t["border"]}" filter="url(#lift)"/>
      <rect x="{x + 8}" y="{y + 6}" width="12" height="12" rx="3.5" fill="{BRAND}"/>
      {text(x + 26, y + 16, label, "mono", 10.5, t["fg"])}
    </g>"""


def comment(t, pin_x, pin_y, right):
    """Pin de comentario de Figma: la IA sugiere el texto del botón; Jorge decide."""
    lines = CONTENT["mock"]["comment"]
    bw = max(tw(l, 11, "regular") for l in lines) + 28
    bh = 68
    bx, by = right - bw, pin_y - bh - 8
    cover = bw - 20
    return f"""
    <g class="bubble">
      <rect x="{bx:.1f}" y="{by}" width="{bw:.1f}" height="{bh}" rx="12" fill="{t["raised"]}" stroke="{t["border"]}" filter="url(#lift)"/>
      <circle cx="{bx + 20:.1f}" cy="{by + 18}" r="8" fill="{AI}"/>
      {ai_mark(bx + 20, by + 18, 11)}
      {text(bx + 34, by + 22, "AI", "bold", 11, t["fg"])}
      {text(bx + 34 + tw("AI", 11, "bold") + 6, by + 22, "suggestion", "regular", 10, t["muted"])}
      <g clip-path="url(#typing)">
        {"".join(text(bx + 14, by + 42 + i * 16, l, "regular", 11, t["fg"]) for i, l in enumerate(lines))}
        <rect class="type" x="{bx + 10 + cover:.1f}" y="{by + 30}" width="{cover:.0f}" height="34" fill="{t["raised"]}"/>
      </g>
      <clipPath id="typing"><rect x="{bx + 10:.1f}" y="{by + 30}" width="{cover:.0f}" height="34"/></clipPath>
    </g>
    <g transform="translate({pin_x} {pin_y})">
      <path d="M0 28V14A14 14 0 1 1 14 28Z" fill="{t["raised"]}" stroke="{t["border"]}" filter="url(#lift)"/>
      <circle cx="14" cy="14" r="10" fill="{AI}"/>
      {ai_mark(14, 14, 13)}
    </g>"""


def banner(t):
    c = CONTENT
    h = 360
    # nombre dentro de un marco de selección de Figma, ajustado al ancho real del texto
    name_w = max(tw(l, 56, "display", -1.6) for l in c["name"])
    fx, fy, fw, fh = 52, 122, round(name_w + 24), 124
    handles = "".join(f'<rect x="{x - 4}" y="{y - 4}" width="8" height="8" fill="{t["handle"]}" stroke="{SELECT}" stroke-width="1.5"/>'
                      for x in (fx, fx + fw) for y in (fy, fy + fh))
    dims = f"{fw} × {fh}"
    dw = tw(dims, 11, "semibold") + 14
    # chips de especialidad
    chips, x = [], 64
    for color, label in c["chips"]:
        cw = tw(label, 12.5, "medium") + 34
        chips.append(f'<rect x="{x + .5:.1f}" y="292.5" width="{cw - 1:.1f}" height="31" rx="15.5" fill="{t["surface"]}" stroke="{t["border"]}"/>'
                     f'<circle cx="{x + 15:.1f}" cy="308" r="4" fill="{color}"/>' + text(x + 24, 312.5, label, "medium", 12.5, t["fg"]))
        x += cw + 8
    assert x < 580, "los chips del banner chocan con el teléfono: acorta las etiquetas"
    # Historia de 14 s: wireframe → Jorge dibuja el hero → aparecen texto, etiquetas y botón →
    # la IA sugiere «Get started» y Jorge cambia el botón. Sin animación (reduced motion) queda el final.
    px, py = 588, 44
    me0, ai0 = (fx + fw - 2, fy + fh - 2), (820, 168)
    rel = lambda x, y: f"translate({px + x - me0[0]:.0f}px,{py + y - me0[1]:.0f}px)"
    ai_pin = (792 - ai0[0], 304 - ai0[1])
    ease = "cubic-bezier(.45,0,.2,1)"
    css = f"""
    .caret{{animation:blink 1.1s steps(1) infinite}} @keyframes blink{{50%{{opacity:0}}}}
    .me{{animation:me 14s {ease} infinite}}
    @keyframes me{{0%,5%,92%,100%{{transform:translate(0,0)}} 12%,14%{{transform:{rel(12, 60)}}}
      26%,28%{{transform:{rel(164, 146)}}} 34%,40%{{transform:{rel(110, 176)}}} 48%,70%{{transform:{rel(112, 262)}}}}}
    .s-hero{{animation:hero 14s {ease} infinite;transform-box:fill-box;transform-origin:0 0}}
    @keyframes hero{{0%,13.9%{{opacity:0;transform:scale(.02)}} 14%{{opacity:1;transform:scale(.02)}}
      26%,97%{{opacity:1;transform:scale(1)}} 100%{{opacity:0;transform:scale(1)}}}}
    .wire,.dim,.red,.cta-old,.swap{{opacity:0}}
    .wire{{animation:wire 14s infinite}} @keyframes wire{{0%,44%{{opacity:1}}50%,97%{{opacity:0}}100%{{opacity:1}}}}
    .dim{{animation:dim 14s infinite}} @keyframes dim{{0%,15%{{opacity:0}}17%,30%{{opacity:1}}33%,100%{{opacity:0}}}}
    .s-text{{animation:stext 14s infinite}} @keyframes stext{{0%,30%{{opacity:0;transform:translateY(4px)}}34%,97%{{opacity:1;transform:none}}100%{{opacity:0}}}}
    .red{{animation:red 14s infinite}} @keyframes red{{0%,33%{{opacity:0}}35%,41%{{opacity:1}}43%,100%{{opacity:0}}}}
    .s-tags{{animation:stags 14s infinite}} @keyframes stags{{0%,38%{{opacity:0;transform:translateY(4px)}}42%,97%{{opacity:1;transform:none}}100%{{opacity:0}}}}
    .s-cta{{animation:scta 14s infinite}} @keyframes scta{{0%,44%{{opacity:0}}47%,97%{{opacity:1}}100%{{opacity:0}}}}
    .ai{{animation:ai 14s {ease} infinite}}
    @keyframes ai{{0%,100%{{transform:translate(0,0)}} 20%{{transform:translate(-8px,22px)}} 40%{{transform:translate(4px,-6px)}}
      56%,88%{{transform:translate({ai_pin[0]}px,{ai_pin[1]}px)}}}}
    .comp{{animation:comp 14s infinite}} @keyframes comp{{0%,51%,94%,100%{{opacity:0}}53%,92%{{opacity:1}}}}
    .tap{{opacity:0;animation:tap 14s infinite;transform-box:fill-box;transform-origin:center}}
    @keyframes tap{{0%,51%{{opacity:0;transform:scale(.4)}}52%{{opacity:1;transform:scale(.4)}}56%,100%{{opacity:0;transform:scale(1.6)}}}}
    .bubble{{animation:bubble 14s infinite}} @keyframes bubble{{0%,58%,96%,100%{{opacity:0}}60%,94%{{opacity:1}}}}
    .type{{animation:type 14s steps(26) infinite;transform-box:fill-box}}
    @keyframes type{{0%,60%{{transform:translateX(-100%)}}76%,100%{{transform:translateX(0)}}}}
    .tok{{animation:tok 14s infinite}} @keyframes tok{{0%,25%{{opacity:0}}29%,96%{{opacity:1}}100%{{opacity:0}}}}
    .cta-old{{animation:ctaold 14s infinite}} @keyframes ctaold{{0%,76%{{opacity:1}}78%,97%{{opacity:0}}99%,100%{{opacity:1}}}}
    .cta-new{{animation:ctanew 14s infinite}} @keyframes ctanew{{0%,77%{{opacity:0}}79%,96%{{opacity:1}}98%,100%{{opacity:0}}}}
    .swap{{animation:swap 14s infinite}} @keyframes swap{{0%,77%{{opacity:0}}79%{{opacity:1}}88%,100%{{opacity:0}}}}
    .me,.ai,.s-hero,.wire,.dim,.s-text,.red,.s-tags,.s-cta,.comp,.tap,.bubble,.type,.tok,.cta-old,.cta-new,.swap{{animation-delay:-11.5s}}
    """
    # El retraso negativo hace que el primer cuadro sea la pantalla ya terminada; luego se repite la historia.
    body = f"""
    <defs>
      <pattern id="dots" x="22" y="22" width="22" height="22" patternUnits="userSpaceOnUse"><circle cx="1.5" cy="1.5" r="1.2" fill="{t["dot"]}"/></pattern>
      <radialGradient id="glow" cx="78%" cy="18%" r="60%"><stop offset="0" stop-color="{ACCENT}" stop-opacity=".16"/><stop offset="1" stop-color="{ACCENT}" stop-opacity="0"/></radialGradient>
      <linearGradient id="brand" x1="0" y1="0" x2="1" y2="1"><stop offset="0" stop-color="{BRAND}"/><stop offset="1" stop-color="{BRAND_DEEP}"/></linearGradient>
      <filter id="lift" x="-100%" y="-100%" width="300%" height="300%"><feDropShadow dx="0" dy="6" stdDeviation="8" flood-color="#000" flood-opacity="{t["shadow"]}"/></filter>
      <clipPath id="card"><rect width="{W}" height="{h}" rx="20"/></clipPath>
    </defs>
    <g clip-path="url(#card)">
      <rect width="{W}" height="{h}" fill="{t["bg"]}"/>
      <rect width="{W}" height="{h}" fill="url(#dots)"/>
      <rect width="{W}" height="{h}" fill="url(#glow)"/>
      {rulers(t, h, (fx, fx + fw), (fy, fy + fh))}
      {text(64, 72, c["overline"], "mono", 12, t["muted"], ls=2, tail=f'<tspan class="caret" fill="{ACCENT}"> ▍</tspan>')}
      {text(fx, fy - 9, c["role_tag"], "semibold", 11, ink(SELECT, t["bg"]))}
      {"".join(text(64, fy + 50 + i * 60, l, "display", 56, t["fg"], ls=-1.6) for i, l in enumerate(c["name"]))}
      <rect x="{fx}" y="{fy}" width="{fw}" height="{fh}" stroke="{SELECT}" stroke-width="1.5"/>
      {handles}
      <rect x="{fx + fw / 2 - dw / 2:.1f}" y="{fy + fh + 9}" width="{dw:.1f}" height="19" rx="4" fill="{SELECT}"/>
      {text(fx + fw / 2, fy + fh + 22.5, dims, "semibold", 11, "#fff", "middle")}
      {"".join(chips)}
      {phone(t, px, py)}
      {token_chip(t, px - 8 - (tw(c["mock"]["token"], 10.5, "mono") + 34), py + 62, px + 12)}
      {comment(t, 772, 292, 888)}
      <g transform="translate({ai0[0]} {ai0[1]})"><g class="ai">{cursor(AI, "AI", t)}</g></g>
      <g transform="translate({me0[0]} {me0[1]})"><g class="me">{cursor(SELECT, "Jorge", t)}</g></g>
    </g>
    <rect x=".5" y=".5" width="{W - 1}" height="{h - 1}" rx="19.5" stroke="{t["border"]}"/>
    """
    return W, h, body, css, f'{" ".join(c["name"])} — {" ".join(c["role"])}'


def flow_chips(items, width, size, font="medium", gap=8, pad=36):
    """Reparte chips en filas que caben en `width`; devuelve [(x, ancho, item), ...] por fila."""
    rows, row, x = [], [], 0
    for item in items:
        cw = tw(item[1] if isinstance(item, tuple) else item, size, font) + pad
        if row and x + cw > width:
            rows.append(row)
            row, x = [], 0
        row.append((x, cw, item))
        x += cw + gap
    return rows + [row] if row else rows


def banner_mobile(t):
    """Versión de 360 px: el nombre seleccionado, las especialidades y los dos cursores."""
    c = CONTENT
    w = MW
    name_w = max(tw(l, 42, "display", -1.2) for l in c["name"])
    fx, fy, fw, fh = 16, 84, round(name_w + 20), 98
    rows = flow_chips(c["chips"], w - 40, 12.5, gap=8, pad=34)
    chips_y = fy + fh + 48
    h = round(chips_y + len(rows) * 38 + 18)
    handles = "".join(f'<rect x="{x - 3.5}" y="{y - 3.5}" width="7" height="7" fill="{t["handle"]}" stroke="{SELECT}" stroke-width="1.5"/>'
                      for x in (fx, fx + fw) for y in (fy, fy + fh))
    dims = f"{fw} × {fh}"
    dw = tw(dims, 10, "semibold") + 12
    chips = []
    for r, row in enumerate(rows):
        for x, cw, (color, label) in row:
            x += 20
            y = chips_y + r * 38
            chips.append(f'<rect x="{x + .5:.1f}" y="{y + .5}" width="{cw - 1:.1f}" height="29" rx="14.5" fill="{t["surface"]}" stroke="{t["border"]}"/>'
                         f'<circle cx="{x + 14:.1f}" cy="{y + 15}" r="3.5" fill="{color}"/>' + text(x + 23, y + 19.5, label, "medium", 12.5, t["fg"]))
    r = 18
    ticks = "".join(f"M{x} {r}v{-6 if x % 50 == 0 else -3}" for x in range(r + 2, w, 10))
    css = """
    .caret{animation:blink 1.1s steps(1) infinite} @keyframes blink{50%{opacity:0}}
    .me{animation:me 6s ease-in-out infinite} @keyframes me{0%,100%{transform:translate(0,0)}50%{transform:translate(6px,5px)}}
    .ai{animation:ai 9s ease-in-out infinite}
    @keyframes ai{0%,100%{transform:translate(0,0)}33%{transform:translate(-18px,-6px)}66%{transform:translate(-4px,6px)}}
    """
    body = f"""
    <defs>
      <pattern id="dots" x="18" y="18" width="20" height="20" patternUnits="userSpaceOnUse"><circle cx="1.2" cy="1.2" r="1.1" fill="{t["dot"]}"/></pattern>
      <radialGradient id="glow" cx="90%" cy="10%" r="70%"><stop offset="0" stop-color="{ACCENT}" stop-opacity=".18"/><stop offset="1" stop-color="{ACCENT}" stop-opacity="0"/></radialGradient>
      <clipPath id="card"><rect width="{w}" height="{h}" rx="18"/></clipPath>
    </defs>
    <g clip-path="url(#card)">
      <rect width="{w}" height="{h}" fill="{t["bg"]}"/>
      <rect width="{w}" height="{h}" fill="url(#dots)"/>
      <rect width="{w}" height="{h}" fill="url(#glow)"/>
      <rect width="{w}" height="{r}" fill="{t["surface"]}"/>
      <rect x="{fx}" width="{fw}" height="{r}" fill="{SELECT}" fill-opacity=".14"/>
      <path d="{ticks}" stroke="{t["border"]}"/><path d="M0 {r - .5}H{w}" stroke="{t["border"]}"/>
      {"".join(text(x + 3, 10, str(x), "mono", 7.5, t["muted"]) for x in (100, 200, 300))}
      {text(20, 52, c["overline"], "mono", 10, t["muted"], ls=1.2, tail=f'<tspan class="caret" fill="{ACCENT}"> ▍</tspan>')}
      {text(fx, fy - 8, c["role_tag"], "semibold", 10.5, ink(SELECT, t["bg"]))}
      {"".join(text(fx + 10, fy + 40 + i * 46, l, "display", 42, t["fg"], ls=-1.2) for i, l in enumerate(c["name"]))}
      <rect x="{fx}" y="{fy}" width="{fw}" height="{fh}" stroke="{SELECT}" stroke-width="1.5"/>
      {handles}
      <rect x="{fx + fw / 2 - dw / 2:.1f}" y="{fy + fh + 8}" width="{dw:.1f}" height="17" rx="4" fill="{SELECT}"/>
      {text(fx + fw / 2, fy + fh + 20, dims, "semibold", 10, "#fff", "middle")}
      {"".join(chips)}
      <g transform="translate({w - 96} {chips_y + (len(rows) - 1) * 38 + 8})"><g class="ai">{cursor(AI, "AI", t)}</g></g>
      <g transform="translate({fx + fw - 2} {fy + fh - 2})"><g class="me">{cursor(SELECT, "Jorge", t)}</g></g>
    </g>
    <rect x=".5" y=".5" width="{w - 1}" height="{h - 1}" rx="17.5" stroke="{t["border"]}"/>
    """
    return w, h, body, css, f'{" ".join(c["name"])} — {" ".join(c["role"])}'


# --------------------------------------------------------------------- piezas
# Cada pieza devuelve (ancho, alto, cuerpo, css, título); svg() o dual() la convierten en archivo.
def button(t, label, glyph, primary, badge=None):
    h = 44
    lw = tw(label, 14, "semibold")
    bw = tw(badge, 10, "mono", 1) + 14 if badge else 0
    w = round(lw + 64 + (bw + 8 if badge else 0))
    # celeste claro con tinta oscura: el blanco no pasa AA sobre un azul tan claro
    fill, fg = (BRAND, ON_BRAND) if primary else (t["surface"], t["fg"])
    stroke = f' stroke="{ACCENT}"' if primary else f' stroke="{t["border"]}"'
    pill = ""
    if badge:  # p. ej. «WIP»: algo que todavía se está construyendo
        tint = mix(ACCENT, fill, .16)
        pill = (f'<rect x="{46 + lw + 8:.1f}" y="12" width="{bw:.1f}" height="20" rx="6" fill="{tint}" stroke="{ACCENT}" stroke-opacity=".5" stroke-dasharray="3 2"/>'
                + text(46 + lw + 8 + bw / 2, 26, badge, "mono", 10, ink(ACCENT, tint), "middle", ls=1))
    body = f"""
    <rect x=".5" y=".5" width="{w - 1}" height="{h - 1}" rx="12" fill="{fill}"{stroke}/>
    <g transform="translate(18 12)">{GLYPHS[glyph].format(c=fg, bg=fill)}</g>
    {text(46, 27, label, "semibold", 14, fg)}
    {pill}
    """
    return w, h, body, "", f"{label} ({badge})" if badge else label


def header(t, num, title, slug, w=W):
    small = w < 500
    h, size = (52, 21) if small else (64, 24)
    cy = h / 2
    x_title = 46 if small else 52
    x_line0 = x_title + tw(title, size, "bold", -.4) + (14 if small else 20)
    x_line1 = w - tw(slug, 12 if small else 13, "mono") - (12 if small else 16)
    if x_line1 - x_line0 < 24:  # un título largo no deja sitio: se quedan el número y el título
        slug, x_line1 = "", x_line0
    body = f"""
    <rect x="0" y="{cy - 13}" width="{32 if small else 36}" height="26" rx="7" fill="{ACCENT}" fill-opacity=".14"/>
    {text(16 if small else 18, cy + 4.5, num, "mono", 13, ink(ACCENT, t["bg"]), "middle")}
    {text(x_title, cy + 8, title, "bold", size, t["fg"], ls=-.4)}
    <path d="M{x_line0:.0f} {cy}H{x_line1:.0f}" stroke="{t["border"]}" stroke-dasharray="2 5" stroke-linecap="round"/>
    {text(w, cy + 4.5, slug, "mono", 12 if small else 13, t["muted"], "end")}
    """
    return w, h, body, "", title


NAVY, NAVY_2, NAVY_INK = "#0B1430", "#14275C", "#A9B6D6"  # la noche del portafolio y su texto secundario


def portfolio(t, w=W):
    """Banner del portafolio: el texto invita a seguir la construcción y una ventana muestra el sitio
    armándose caso por caso. El fondo es la noche del portafolio en los dos temas. 10 s en bucle;
    el primer cuadro (y la versión sin animación) es la página ya armada."""
    p = CONTENT["portfolio"]
    small = w < 500
    pad = 20 if small else 44
    cycle, delay = 10, -5
    css = [f".pf{{animation-duration:{cycle}s;animation-iteration-count:infinite;animation-delay:{delay}s}}",
           ".pulse{animation:pulse 1.8s ease-out infinite;transform-box:fill-box;transform-origin:center}"
           "@keyframes pulse{0%{transform:scale(1);opacity:.7}100%{transform:scale(2.8);opacity:0}}"]
    # ------------------------------------------------------------- texto
    ts, tl = (27, 33) if small else (36, 44)
    text_w = w - 2 * pad if small else 420
    assert max(tw(l, ts, "display", -.8) for l in p["title"]) < text_w, "el título del portafolio no cabe"
    lead = wrap(p["lead"], text_w, "regular", 15.5)
    y = 30 if small else 46
    sw_ = tw(p["status"], 10.5, "mono", 1.4) + 38
    out = [f'<rect x="{pad}" y="{y}" width="{sw_:.0f}" height="26" rx="13" fill="#fff" fill-opacity=".06" stroke="#fff" stroke-opacity=".14"/>'
           f'<circle class="pulse" cx="{pad + 15}" cy="{y + 13}" r="4" fill="{ACCENT}"/>'
           f'<circle cx="{pad + 15}" cy="{y + 13}" r="4" fill="{ACCENT}"/>'
           + text(pad + 27, y + 17.5, p["status"], "mono", 10.5, "#BAE6FD", ls=1.4)]
    y += 26 + (46 if small else 58)
    out += [text(pad, y + i * tl, l, "display", ts, "#fff", ls=-.8) for i, l in enumerate(p["title"])]
    y += (len(p["title"]) - 1) * tl + 32
    out += [text(pad, y + j * 23, l, "regular", 15.5, NAVY_INK) for j, l in enumerate(lead)]
    y += (len(lead) - 1) * 23 + 26
    bw = tw(p["cta"], 14.5, "semibold") + 40
    out.append(f'<rect x="{pad}" y="{y}" width="{bw:.0f}" height="44" rx="12" fill="{BRAND}"/>'
               + text(pad + bw / 2, y + 27.5, p["cta"], "semibold", 14.5, ON_BRAND, "middle"))
    if not small:
        out.append(text(pad + bw + 16, y + 27, p["aside"], "regular", 13, NAVY_INK))
    # ------------------------------------------------------------ ventana
    if small:
        wx, wy, ww = pad, y + 44 + 32, w - pad + 24
        h = wy + 232
    else:
        wx, wy, ww = 500, 40, 372
        h = y + 44 + 40  # el mismo aire abajo que arriba
    win, rows_y = [], 128
    win.append(f'<rect x=".5" y=".5" width="{ww - 1}" height="330" rx="14" fill="#0F1C44" stroke="#fff" stroke-opacity=".16" filter="url(#pshadow)"/>'
               + "".join(f'<circle cx="{16 + k * 14}" cy="17" r="4.5" fill="{col}"/>' for k, col in enumerate(("#FF5F57", "#FEBC2E", "#28C840")))
               + f'<rect x="{ww / 2 - 78:.0f}" y="7" width="156" height="20" rx="10" fill="#fff" fill-opacity=".07"/>'
               + text(ww / 2, 21, "portfolio · in progress", "mono", 9.5, NAVY_INK, "middle")
               + f'<path d="M0 34.5H{ww}" stroke="#fff" stroke-opacity=".1"/>'
               + f'<rect class="pf load" x="0" y="33" width="{ww}" height="2" fill="{ACCENT}"/>')
    # encabezado de la página: esqueleto → texto
    win.append('<g class="pf hk">'
               f'<rect x="20" y="52" width="110" height="7" rx="3.5" fill="#fff" fill-opacity=".1"/>'
               f'<rect x="20" y="70" width="210" height="12" rx="6" fill="#fff" fill-opacity=".12"/>'
               f'<rect x="20" y="90" width="140" height="12" rx="6" fill="#fff" fill-opacity=".12"/></g>'
               '<g class="pf hd">' + text(20, 60, "PRODUCT UX DESIGNER", "mono", 9, NAVY_INK, ls=1.2)
               + text(20, 82, "Knowledge is universal.", "display", 15.5, "#fff", ls=-.3)
               + text(20, 102, "Judgment isn't.", "display", 15.5, ACCENT, ls=-.3) + "</g>")
    rw = ww - 40
    for i, (color, title, meta) in enumerate(p["cases"]):
        ry = rows_y + i * 50
        box = f'<rect x="20" y="{ry}" width="{rw}" height="42" rx="10" fill="#fff" fill-opacity=".05" stroke="#fff" stroke-opacity=".1"/>'
        win.append(f'<g class="pf k{i}">{box}<rect x="29" y="{ry + 9}" width="24" height="24" rx="7" fill="#fff" fill-opacity=".1"/>'
                   f'<rect x="63" y="{ry + 12}" width="90" height="7" rx="3.5" fill="#fff" fill-opacity=".14"/>'
                   f'<rect x="63" y="{ry + 25}" width="140" height="6" rx="3" fill="#fff" fill-opacity=".09"/></g>'
                   f'<g class="pf c{i}">{box}<rect x="29" y="{ry + 9}" width="24" height="24" rx="7" fill="{color}"/>'
                   f'<rect x="35" y="{ry + 15}" width="12" height="12" rx="3.5" fill="#fff" fill-opacity=".75"/>'
                   + text(63, ry + 19, title, "semibold", 12.5, "#fff")
                   + text(63, ry + 33, meta, "regular", 10.5, NAVY_INK)
                   + text(rw + 8, ry + 26, "→", "semibold", 13, NAVY_INK, "end") + "</g>")
    # el cursor de Jorge revisa cada caso mientras se arma
    rest = (ww - 96, 58)
    stops = [(rows_y + i * 50 + 26) for i in range(3)]
    cur = (f"0%,8%{{transform:translate(0,0)}}" + "".join(
        f"{16 + 14 * i}%,{22 + 14 * i}%{{transform:translate({-36 - 10 * i}px,{sy - rest[1]}px)}}" for i, sy in enumerate(stops))
           + "70%,100%{transform:translate(0,0)}")
    win.append(f'<g transform="translate({rest[0]} {rest[1]})"><g class="pf pcur">{cursor(SELECT, "Jorge", t)}</g></g>')
    css.append(f".pcur{{animation-name:pcur;animation-timing-function:cubic-bezier(.45,0,.2,1)}}@keyframes pcur{{{cur}}}"
               ".load{animation-name:load;transform-box:fill-box;transform-origin:0 0}"
               "@keyframes load{0%{transform:scaleX(0);opacity:1}55%,88%{transform:scaleX(1);opacity:1}93%,100%{transform:scaleX(1);opacity:0}}"
               ".hk,.k0,.k1,.k2{opacity:0}")
    for cls, at in (("hd", 8), ("c0", 20), ("c1", 34), ("c2", 48)):
        css.append(f".{cls}{{animation-name:{cls}}}@keyframes {cls}{{0%,{at - 2}%{{opacity:0;transform:translateY(4px)}}"
                   f"{at + 2}%,90%{{opacity:1;transform:none}}95%,100%{{opacity:0}}}}")
        sk = "hk" if cls == "hd" else "k" + cls[1]
        css.append(f".{sk}{{animation-name:{sk}}}@keyframes {sk}{{0%,{at - 2}%{{opacity:1}}{at + 1}%,93%{{opacity:0}}96%,100%{{opacity:1}}}}")
    body = f"""
    <defs>
      <linearGradient id="pbg" x1="0" y1="0" x2="1" y2="1"><stop offset="0" stop-color="{NAVY}"/><stop offset="1" stop-color="{NAVY_2}"/></linearGradient>
      <radialGradient id="pglow" cx="{.85 if not small else .9}" cy="{.05 if not small else .55}" r=".7"><stop offset="0" stop-color="{ACCENT}" stop-opacity=".32"/><stop offset="1" stop-color="{ACCENT}" stop-opacity="0"/></radialGradient>
      <pattern id="pdots" width="22" height="22" patternUnits="userSpaceOnUse"><circle cx="1.5" cy="1.5" r="1.1" fill="#fff" fill-opacity=".07"/></pattern>
      <filter id="pshadow" x="-30%" y="-30%" width="160%" height="160%"><feDropShadow dx="0" dy="14" stdDeviation="16" flood-color="#000" flood-opacity=".45"/></filter>
      <clipPath id="pcard"><rect width="{w}" height="{h}" rx="20"/></clipPath>
    </defs>
    <g clip-path="url(#pcard)">
      <rect width="{w}" height="{h}" fill="url(#pbg)"/>
      <rect width="{w}" height="{h}" fill="url(#pdots)"/>
      <rect width="{w}" height="{h}" fill="url(#pglow)"/>
      {"".join(out)}
      <g transform="translate({wx} {wy})">{"".join(win)}</g>
    </g>
    <rect x=".5" y=".5" width="{w - 1}" height="{h - 1}" rx="19.5" stroke="{t["border"]}"/>
    """
    return w, round(h), body, "".join(css), f'Portfolio, work in progress: {" ".join(p["title"])} {p["lead"]}'


def rules(t, w=W):
    """Las tres reglas con las que diseño la IA (del caso ATLAS). Un anillo recorre las tarjetas."""
    items = CONTENT["agent"]["rules"]
    small = w < 500
    n, gap, pad = len(items), 12, 18
    c = ink(ACCENT, t["bg"])
    soft = mix(ACCENT, t["surface"], .22)
    tile_bg = mix(ACCENT, t["surface"], .1)
    cw = w if small else (w - gap * (n - 1)) / n
    tx = pad + 58 if small else pad
    descs = [wrap_even(d, cw - tx - pad, "regular", 13.5) for *_, d in items]
    beat = 2.4
    css = (f".rr{{opacity:0;animation:rr {n * beat}s ease-out infinite}}"
           f"@keyframes rr{{0%{{opacity:0}}6%{{opacity:1}}30%,100%{{opacity:0}}}}")
    oy = 26
    out = [text(0, 12, "THREE RULES I DESIGN AI BY · FROM ATLAS", "mono", 10.5, t["muted"], ls=1.4)]
    y = oy
    for i, ((kind, title, _), ds) in enumerate(zip(items, descs)):
        x = 0 if small else i * (cw + gap)
        if small:  # ícono a la izquierda, texto a la derecha
            ch = max(44 + 2 * pad, pad + 39 + 19 * (len(ds) - 1) + 6 + pad)
        else:  # todas del mismo alto
            ch = pad + 92 + 19 * (max(map(len, descs)) - 1) + 6 + pad
        title_y, desc_y = (pad + 17, pad + 39) if small else (pad + 68, pad + 92)
        out.append(f'<g transform="translate({x:.1f} {y})">'
                   f'<rect x=".5" y=".5" width="{cw - 1:.1f}" height="{ch - 1}" rx="14" fill="{t["surface"]}" stroke="{t["border"]}"/>'
                   f'<rect class="rr" style="animation-delay:{i * beat}s" x=".5" y=".5" width="{cw - 1:.1f}" height="{ch - 1}" rx="14" stroke="{ACCENT}" stroke-width="1.5"/>'
                   f'<rect x="{pad}" y="{pad}" width="44" height="44" rx="12" fill="{tile_bg}"/>'
                   f'<g transform="translate({pad + 2} {pad + 2}) scale(1)">{method_icon(kind, c, soft, t["surface"], 0)}</g>'
                   + text(tx, title_y, title, "bold", 15, t["fg"], ls=-.2)
                   + "".join(text(tx, desc_y + j * 19, l, "regular", 13.5, t["muted"]) for j, l in enumerate(ds))
                   + "</g>")
        y = y + ch + gap if small else y
        last_h = ch
    h = (y - gap) if small else oy + last_h
    title = "Three rules I design AI by: " + "; ".join(f"{a[1]} — {a[2]}" for a in items)
    return w, round(h), "".join(out), css, title


def redline_pill(cx, cy, s):
    pw = tw(s, 9.5, "bold") + 10
    return (f'<rect x="{cx - pw / 2:.1f}" y="{cy - 7}" width="{pw:.1f}" height="14" rx="3" fill="{REDLINE}"/>'
            + text(cx, cy + 3.5, s, "bold", 9.5, "#fff", "middle"))





# About: un panel de capas de Figma que sí se puede clicar. GitHub muestra los SVG como imágenes (sin clics
# por dentro), así que cada capa es un <details>: la fila es el <summary> y al abrirla aparece su inspector.
def layers_head(t, w=W):
    small = w < 500
    hint = "tap a layer to inspect it" if small else "click a layer to inspect it"
    c = ink(ACCENT, t["bg"])
    x = tw("LAYERS", 11, "mono", 1.5) + 16
    name = "" if small else (f'<path d="M{x + 1} 13h11M{x + 1} 19h11M{x + 4} 10v12M{x + 9} 10v12" stroke="{t["muted"]}" stroke-width="1.3"/>'
                             + text(x + 20, 20.5, " ".join(CONTENT["name"]), "semibold", 13, t["fg"]))
    hx = w - 14 - tw(hint, 11, "mono")
    body = (text(0, 20, "LAYERS", "mono", 11, t["muted"], ls=1.5) + name
            + text(hx - 6, 20, hint, "mono", 11, c)
            + f'<path d="M{w - 10} 11v9M{w - 14} 16.5l4 4 4-4" stroke="{c}" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round"/>')
    return w, 30, body, "", f"Layers — {' '.join(CONTENT['name'])}: {hint}"


def layer_row(t, i, w=W):
    """Fila de la capa i: ícono, nombre y, a la derecha, sus propiedades y «inspect»."""
    glyph, color, title, _, tags = CONTENT["about"][i]
    small = w < 500
    h = 52
    c = ink(ACCENT, t["surface"])
    tint = mix(color, t["surface"], .16)
    cue = "inspect"
    cx = w - 16
    out = [f'<rect x=".5" y=".5" width="{w - 1}" height="{h - 1}" rx="12" fill="{t["surface"]}" stroke="{t["border"]}"/>',
           f'<rect x="12" y="12" width="28" height="28" rx="8" fill="{tint}"/>',
           f'<g transform="translate(12 12) scale(.7)">{GLYPHS[glyph].format(c=color)}</g>',
           f'<path d="M{cx - 8} 23l4 4 4-4" stroke="{c}" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round"/>']
    if small:  # en el celular: ícono, nombre y la flecha
        out.append(text(52, 31.5, title, "semibold", 15, t["fg"]))
        assert 52 + tw(title, 15, "semibold") < cx - 20, f"{title} no cabe en la fila del celular"
    else:
        out += [text(52, 31, f"0{i + 1}", "mono", 11, t["muted"]), text(78, 31.5, title, "semibold", 15, t["fg"]),
                text(cx - 16, 30.5, cue, "mono", 11, c, "end")]
    if not small:
        props = " · ".join(tags)
        px = cx - 16 - tw(cue, 11, "mono") - 22
        assert px - tw(props, 11, "mono") > 78 + tw(title, 15, "semibold") + 24, f"las propiedades de {title} chocan con el nombre"
        out.append(text(px, 30.5, props, "mono", 11, t["muted"], "end"))
    return w, h, "".join(out), "", f"Layer 0{i + 1}: {title} — click to inspect"


def inspector(t, i, w=W):
    """Inspector de la capa i: lo que se ve al abrirla."""
    glyph, color, title, desc, tags = CONTENT["about"][i]
    pad = 20
    tint = mix(color, t["surface"], .12)
    lines = wrap(desc, w - 2 * pad, "regular", 15)
    rows = flow_chips(tags, w - 2 * pad, 11.5, "mono", 8, 20)
    size = 22 if pad + 60 + tw(title, 22, "bold", -.3) < w - pad else 18
    last = pad + 104 + 23 * (len(lines) - 1)
    chips = []
    for r, row in enumerate(rows):
        for x, cw, tag in row:
            y = last + 46 + r * 34
            chips.append(f'<rect x="{pad + x:.1f}" y="{y}" width="{cw:.1f}" height="26" rx="7" fill="{tint}"/>'
                         + text(pad + x + 10, y + 17, tag, "mono", 11.5, ink(color, tint)))
    h = last + 46 + len(rows) * 34 + pad - 8
    body = f"""
    <rect x=".5" y=".5" width="{w - 1}" height="{h - 1}" rx="14" fill="{t["surface"]}" stroke="{t["border"]}"/>
    <path d="M14 .5H{w - 14}" stroke="{color}" stroke-width="2" stroke-linecap="round"/>
    {text(pad, pad + 12, "INSPECT", "mono", 11, t["muted"], ls=1.5)}
    <g transform="translate({pad} {pad + 28})"><rect width="44" height="44" rx="12" fill="{color}" fill-opacity=".14"/>
      <g transform="translate(2 2)">{GLYPHS[glyph].format(c=color)}</g></g>
    {text(pad + 60, pad + 44, f"LAYER 0{i + 1}", "mono", 10.5, t["muted"], ls=1.2)}
    {text(pad + 60, pad + 66, title, "bold", size, t["fg"], ls=-.3)}
    {"".join(text(pad, pad + 104 + j * 23, l, "regular", 15, t["muted"]) for j, l in enumerate(lines))}
    {text(pad, last + 30, "PROPERTIES", "mono", 10.5, t["muted"], ls=1.2)}
    {"".join(chips)}
    """
    return w, round(h), body, "", f"{title}: {desc} Properties: {', '.join(tags)}."


def method_icon(kind, c, soft, on, d):
    """Íconos del método en una caja de 40: trazo de 2 px redondeado, relleno suave y un detalle sólido.
    `d` es el segundo en que la etapa se enciende; ahí corre su microanimación."""
    s = f'stroke="{c}" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"'
    thin = s.replace('width="2"', 'width="1.5"')
    dl = lambda k=0: f' style="animation-delay:{d + k:.2f}s"'
    if kind == "chip":  # ingeniería: el sistema por dentro
        pins = "".join(f"M{p} 6.5v3M{p} 30.5v3M6.5 {p}h3M30.5 {p}h3" for p in (15, 20, 25))
        return (f'<path class="mi-pin"{dl()} d="{pins}" {s}/>'
                f'<rect x="10.5" y="10.5" width="19" height="19" rx="4.5" fill="{soft}" {s}/>'
                f'<rect class="mi-die"{dl()} x="15.5" y="15.5" width="9" height="9" rx="2" fill="{c}"/>')
    if kind == "nodes":  # sistemas: el problema vive entre dos pantallas
        edges = "".join(f'<path class="mi-edge"{dl(k * .15)} pathLength="1" d="{p}" {s}/>'
                        for k, p in enumerate(("M15.5 11.5h9", "M12.6 15.6l5.2 9", "M27.4 15.6l-5.2 9")))
        return (edges + f'<circle cx="11" cy="11.5" r="4.5" fill="{soft}" {s}/><circle cx="29" cy="11.5" r="4.5" fill="{soft}" {s}/>'
                f'<circle class="mi-hub"{dl(.35)} cx="20" cy="29" r="5" fill="{c}"/>')
    if kind == "components":  # diseño: piezas que el equipo arma
        out = []
        for k, (x, y) in enumerate(((20, 12), (28, 20), (20, 28), (12, 20))):
            fill = f'fill="{c}"' if k == 0 else f'fill="{soft}" {s}'
            out.append(f'<path class="mi-d{k}"{dl()} d="M{x} {y - 5.5}l5.5 5.5-5.5 5.5-5.5-5.5z" {fill}/>')
        return "".join(out)
    if kind == "sparkle":  # IA: aporta; el criterio decide
        return (f'<path class="mi-star"{dl()} d="M18 10Q19.4 19.6 29 21Q19.4 22.4 18 32Q16.6 22.4 7 21Q16.6 19.6 18 10Z" fill="{c}"/>'
                f'<path class="mi-tw"{dl(.3)} d="M29.5 6.5Q30.1 10.4 34 11Q30.1 11.6 29.5 15.5Q28.9 11.6 25 11Q28.9 10.4 29.5 6.5Z" fill="{soft}" {thin}/>')
    if kind == "question":  # la IA dice cuando no sabe
        return (f'<circle cx="20" cy="20" r="12" fill="{soft}" {s}/>'
                f'<path d="M16.4 16.6a3.7 3.7 0 1 1 5.3 3.3c-1.1.6-1.7 1.4-1.7 2.6v.5" {s}/>'
                f'<circle cx="20" cy="27" r="1.5" fill="{c}"/>')
    if kind == "person":  # personas: confían en lo que entienden
        return (f'<circle cx="17" cy="13.5" r="5.5" fill="{soft}" {s}/>'
                f'<path d="M7 32c0-5.8 4.4-9.5 10-9.5 2.3 0 4.4.6 6 1.7" {s}/>'
                f'<g class="mi-ok"{dl(.2)}><circle cx="29.5" cy="28.5" r="6" fill="{c}"/>'
                f'<path d="M26.9 28.6l1.8 1.8 3.5-3.6" stroke="{on}" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"/></g>')
    raise KeyError(kind)


def method_motion(pos, axis, beat, lift):
    """Un punto recorre la línea y enciende cada etapa al llegar; las que ya pasó quedan marcadas.
    Todo comparte un mismo ciclo. Sin animación (o con «reducir movimiento») queda el estado neutro."""
    n = len(pos)
    hold = beat + .6
    cycle = (n - 1) * beat + hold + .8
    p = lambda t: f"{max(0, min(t, cycle)) / cycle * 100:.2f}%"
    span = pos[-1] - pos[0]
    tr = "translateX" if axis == "x" else "translateY"
    sc = "scaleX" if axis == "x" else "scaleY"

    def track(fn):
        keys = [(0, 0, 0), (.25, 0, 1)]
        for i in range(n - 1):
            keys += [(i * beat + .45 * beat, i, 1), ((i + 1) * beat, i + 1, 1)]
        keys += [(cycle - .8, n - 1, 1), (cycle - .1, n - 1, 0), (cycle, n - 1, 0)]
        return "".join(f"{p(t)}{{transform:{fn(i)};opacity:{o}}}" for t, i, o in keys)

    css = [f"@keyframes m-dot{{{track(lambda i: f'{tr}({pos[i] - pos[0]:.1f}px)')}}}",
           f"@keyframes m-fill{{{track(lambda i: f'{sc}({(pos[i] - pos[0]) / span:.4f})')}}}",
           f".m-dot{{animation:m-dot {cycle:.2f}s ease-in-out infinite;opacity:0}}",
           f".m-fill{{animation:m-fill {cycle:.2f}s ease-in-out infinite;transform-box:fill-box;transform-origin:0 0;opacity:0}}"]
    up = "translateY(-4px)" if lift else "scale(1.04)"
    for i in range(n):
        a = i * beat
        keys = [(0, 0, "none")] if i == 0 else [(0, 0, "none"), (a - .25, 0, "none")]
        keys.append((a + .05 if i else .3, 1, up))
        if i < n - 1:
            keys += [(a + .8 * beat, 1, up), (a + .8 * beat + .35, .5, "none")]
        keys += [(cycle - .8, .5 if i < n - 1 else 1, "none" if i < n - 1 else up), (cycle - .1, 0, "none"), (cycle, 0, "none")]
        css.append(f"@keyframes m-on{i}{{" + "".join(f"{p(t)}{{opacity:{o}}}" for t, o, _ in keys) + "}"
                   f"@keyframes m-up{i}{{" + "".join(f"{p(t)}{{transform:{u}}}" for t, _, u in keys) + "}"
                   f"@keyframes m-nb{i}{{" + "".join(f"{p(t)}{{opacity:{1 if o else 0}}}" for t, o, _ in keys) + "}"
                   f".m-on{i}{{opacity:0;animation:m-on{i} {cycle:.2f}s ease-out infinite}}"
                   f".m-nb{i}{{opacity:0;animation:m-nb{i} {cycle:.2f}s ease-out infinite}}"
                   f".m-up{i}{{animation:m-up{i} {cycle:.2f}s ease-out infinite;transform-box:fill-box;transform-origin:center}}")
    # microanimaciones de los íconos: corren en el segundo que su etapa se enciende
    k = lambda t: f"{t / cycle * 100:.2f}%"
    loop = lambda name, extra="": (f".mi-{name}{{animation:mi-{name} {cycle:.2f}s ease-out infinite;"
                                   f"transform-box:fill-box;transform-origin:center{extra}}}")
    css += [f"@keyframes mi-pin{{0%{{opacity:.3}}{k(.6)},100%{{opacity:1}}}}", loop("pin"),
            f"@keyframes mi-die{{0%{{transform:scale(1)}}{k(.3)}{{transform:scale(1.3)}}{k(.75)},100%{{transform:scale(1)}}}}", loop("die"),
            f"@keyframes mi-edge{{0%{{stroke-dashoffset:1}}{k(.7)},100%{{stroke-dashoffset:0}}}}", loop("edge", ";stroke-dasharray:1"),
            f"@keyframes mi-hub{{0%{{transform:scale(1)}}{k(.25)}{{transform:scale(1.35)}}{k(.7)},100%{{transform:scale(1)}}}}", loop("hub"),
            f"@keyframes mi-star{{0%{{transform:rotate(0) scale(1)}}{k(.45)}{{transform:rotate(45deg) scale(1.15)}}{k(1)},100%{{transform:rotate(90deg) scale(1)}}}}", loop("star"),
            f"@keyframes mi-tw{{0%{{opacity:1;transform:scale(1)}}{k(.3)}{{opacity:.15;transform:scale(.4)}}{k(.8)},100%{{opacity:1;transform:scale(1)}}}}", loop("tw"),
            f"@keyframes mi-ok{{0%{{transform:scale(0)}}{k(.35)}{{transform:scale(1.2)}}{k(.6)},100%{{transform:scale(1)}}}}", loop("ok")]
    for j, (dx, dy) in enumerate(((0, -4), (4, 0), (0, 4), (-4, 0))):
        css += [f"@keyframes mi-d{j}{{0%{{transform:translate({dx}px,{dy}px);opacity:.2}}{k(.55)},100%{{transform:translate(0,0);opacity:1}}}}",
                loop(f"d{j}")]
    return "".join(css), cycle


def method_step(t, i, glyph, x, y, tile, scale, beat):
    """Mosaico de una etapa: fondo, capa encendida, ícono y número; (x, y) es su esquina superior izquierda."""
    c = ink(ACCENT, t["bg"])
    soft = mix(ACCENT, t["surface"], .22)
    lit = mix(ACCENT, t["surface"], .14)
    r = tile * .28
    bx, by, br = x + tile - 6, y + 6, 11 if tile > 70 else 10
    num = f"0{i + 1}"
    use("mono", num)
    badge = lambda fill, stroke, fg: (f'<circle cx="{bx:.1f}" cy="{by:.1f}" r="{br}" fill="{fill}" stroke="{stroke}" stroke-width="1.5"/>'
                                      + text(bx, by + 3.4, num, "mono", 9.5 if br > 10 else 9, fg, "middle"))
    icon = tile / 40 * .65 * scale  # la caja de 40 a ~2/3 del mosaico: el dibujo ocupa ~45 %
    return (f'<g class="m-up{i}">'
            f'<rect x="{x}" y="{y}" width="{tile}" height="{tile}" rx="{r:.0f}" fill="{t["surface"]}" stroke="{t["border"]}"/>'
            f'<rect class="m-on{i}" x="{x}" y="{y}" width="{tile}" height="{tile}" rx="{r:.0f}" fill="{lit}" stroke="{ACCENT}" stroke-width="2"/>'
            f'<g transform="translate({x + tile / 2 - 20 * icon:.1f} {y + tile / 2 - 20 * icon:.1f}) scale({icon:.3f})">'
            f'{method_icon(glyph, c, soft, t["surface"], i * beat)}</g>'
            + badge(t["bg"], c, c)
            + f'<g class="m-nb{i}">{badge(ACCENT, ACCENT, ON_BRAND)}</g></g>')  # el número queda sólido al pasar


def method(t, w=W):
    """«How I break down a problem»: las cinco etapas del portafolio. Se lee entera sin animación;
    con ella, un punto recorre la línea y enciende cada etapa. En el celular se usa la versión vertical."""
    if w <= 500:
        return method_vertical(t, w)
    steps, n = CONTENT["method"], len(CONTENT["method"])
    beat = 2.2
    step = w / n
    cxs = [step * i + step / 2 for i in range(n)]
    ty, tile = 16, 80
    cy = ty + tile / 2
    css, _ = method_motion(cxs, "x", beat, lift=True)
    c = ink(ACCENT, t["bg"])
    out = [f'<path d="M{cxs[0]:.0f} {cy}H{cxs[-1]:.0f}" stroke="{mix(ACCENT, t["bg"], .55)}" stroke-width="2" stroke-dasharray="2 6" stroke-linecap="round"/>'
           f'<rect class="m-fill" x="{cxs[0]:.0f}" y="{cy - 1}" width="{cxs[-1] - cxs[0]:.0f}" height="2" rx="1" fill="{ACCENT}"/>'
           f'<g class="m-dot"><circle cx="{cxs[0]:.0f}" cy="{cy}" r="9" fill="{ACCENT}" opacity=".25"/>'
           f'<circle cx="{cxs[0]:.0f}" cy="{cy}" r="4.5" fill="{ACCENT}"/></g>']
    descs = [wrap_even(desc, step - 20, "regular", 14) for *_, desc in steps]
    assert max(map(len, descs)) <= 2, "una frase del método pasa de dos líneas"
    ly = ty + tile + 34
    for i, ((glyph, name, head, _), ds) in enumerate(zip(steps, descs)):
        cx = cxs[i]
        out.append(method_step(t, i, glyph, cx - tile / 2, ty, tile, 1, beat)
                   + text(cx, ly, name, "bold", 18, t["fg"], "middle", ls=-.2)
                   + text(cx, ly + 23, head, "semibold", 14, c, "middle")
                   + "".join(text(cx, ly + 47 + j * 20, l, "regular", 14, t["muted"], "middle") for j, l in enumerate(ds)))
    h = ly + 47 + 20 * (max(map(len, descs)) - 1) + 10
    return w, round(h), "".join(out), css, method_title()


def method_title():
    return "How I break down a problem: " + " → ".join(f"{s[1]} ({s[2].lower()}): {s[3]}" for s in CONTENT["method"])


def method_vertical(t, w):
    """Versión del celular: las etapas en columna; el punto baja por la línea."""
    steps = CONTENT["method"]
    beat = 1.8
    c = ink(ACCENT, t["bg"])
    cx, tx, tile = 32, 80, 60
    rows, y0, centers = [], 8, []
    for i, (glyph, name, head, desc) in enumerate(steps):
        ds = wrap(desc, w - tx - 4, "regular", 14)
        centers.append(y0 + tile / 2)
        rows.append((i, glyph, name, head, ds, y0))
        y0 += max(tile, 62 + (len(ds) - 1) * 20) + 28
    css, _ = method_motion(centers, "y", beat, lift=False)
    out = [f'<path d="M{cx} {centers[0]}V{centers[-1]}" stroke="{mix(ACCENT, t["bg"], .55)}" stroke-width="2" stroke-dasharray="2 6" stroke-linecap="round"/>'
           f'<rect class="m-fill" x="{cx - 1}" y="{centers[0]}" width="2" height="{centers[-1] - centers[0]:.0f}" rx="1" fill="{ACCENT}"/>'
           f'<g class="m-dot"><circle cx="{cx}" cy="{centers[0]}" r="8" fill="{ACCENT}" opacity=".25"/>'
           f'<circle cx="{cx}" cy="{centers[0]}" r="4" fill="{ACCENT}"/></g>']
    for i, glyph, name, head, ds, y in rows:
        out.append(method_step(t, i, glyph, cx - tile / 2, y, tile, 1, beat)
                   + text(tx, y + 17, name, "bold", 17, t["fg"], ls=-.2)
                   + text(tx, y + 38, head, "semibold", 14, c)
                   + "".join(text(tx, y + 60 + j * 20, l, "regular", 14, t["muted"]) for j, l in enumerate(ds)))
    return w, round(y0 - 20), "".join(out), css, method_title()


def agentic(t, w=W):
    """Un agente del design system construye un componente con tokens reales y pregunta antes de decidir.
    16 s en bucle; el primer cuadro (y la versión sin animación) es el componente ya publicado."""
    a = CONTENT["agent"]
    small = w < 500
    cycle, delay, pad = 16, -13.4, 18
    cpw = w if small else 356
    cvw = w if small else w - cpw - 16
    css = []

    def anim(cls, frames, timing="ease-out"):
        css.append(f".{cls}{{animation:{cls} {cycle}s {timing} {delay}s infinite}}@keyframes {cls}{{{frames}}}")

    def appear(cls, at, end=94):
        anim(cls, f"0%,{at - 2}%{{opacity:0;transform:translateY(6px)}}{at}%,{end}%{{opacity:1;transform:none}}"
                  f"{end + 3}%,100%{{opacity:0;transform:none}}")

    # ------------------------------------------------------------- chat
    size, lh = 12.5, 18
    bmax = cpw - 2 * pad - 52

    def bubble(y, lines, right=False, lead=0):
        bw = max(tw(l, size, "regular") for l in lines) + 24 + lead
        bh = lh * len(lines) + 16
        bx = cpw - pad - bw if right else pad + 30
        fill = mix(SELECT, t["surface"], .18) if right else t["raised"]
        svg_ = (f'<rect x="{bx:.1f}" y="{y}" width="{bw:.1f}" height="{bh}" rx="12" fill="{fill}" stroke="{t["border"]}"/>'
                + "".join(text(bx + 12 + lead, y + 21 + j * lh, l, "regular", size, t["fg"]) for j, l in enumerate(lines)))
        if not right:  # avatar del agente
            svg_ += f'<circle cx="{pad + 11}" cy="{y + 15}" r="11" fill="{CLAUDE}"/>' + claude_mark(pad + 11, y + 15, 13)
        return svg_, bh, bx

    chat = [f'<circle cx="{pad + 14}" cy="{pad + 14}" r="14" fill="{CLAUDE}"/>', claude_mark(pad + 14, pad + 14, 17),
            text(pad + 36, pad + 11, a["name"], "semibold", 13.5, t["fg"]),
            f'<circle cx="{pad + 40}" cy="{pad + 24}" r="3" fill="{ink("#1F883D", t["surface"], 3)}"/>',
            text(pad + 48, pad + 27.5, a["status"], "mono", 10, t["muted"]),
            f'<path d="M{pad} {pad + 44.5}H{cpw - pad}" stroke="{t["border"]}"/>']
    y = pad + 60
    m1, h1, _ = bubble(y, wrap(a["prompt"], bmax, "regular", size), right=True)
    chat.append(f'<g class="m1">{m1}</g>')
    y += h1 + 12
    dots = "".join(f'<circle class="dt" style="animation-delay:{k * .15:.2f}s" cx="{pad + 44 + k * 9}" cy="{y + 15}" r="2.5" fill="{t["muted"]}"/>'
                   for k in range(3))
    chat.append(f'<g class="dots"><rect x="{pad + 30}" y="{y}" width="46" height="30" rx="12" fill="{t["raised"]}" stroke="{t["border"]}"/>'
                f'<circle cx="{pad + 11}" cy="{y + 15}" r="11" fill="{CLAUDE}"/>{claude_mark(pad + 11, y + 15, 13)}{dots}</g>')
    m2, h2, _ = bubble(y, wrap(a["found"], bmax, "regular", size))
    chat.append(f'<g class="m2">{m2}</g>')
    y += h2 + 12
    m3, h3, bx3 = bubble(y, wrap(a["question"], bmax, "regular", size))
    oy = y + h3 + 8
    opts, ox = [], bx3
    for i, o in enumerate(a["options"]):
        ow = tw(o, 11, "mono") + 22
        opts.append((ox, ow, o))
        ox += ow + 6
    chips = "".join(f'<rect x="{x + .5:.1f}" y="{oy + .5}" width="{ow - 1:.1f}" height="25" rx="12.5" fill="{t["surface"]}" stroke="{t["border"]}"/>'
                    + text(x + ow / 2, oy + 17, o, "mono", 11, t["fg"], "middle") for x, ow, o in opts)
    chat.append(f'<g class="m3">{m3}{chips}</g>')
    px_, pw_, po = opts[a["pick"]]
    tint = mix(ACCENT, t["surface"], .16)
    chat.append(f'<g class="pick"><rect x="{px_ + .5:.1f}" y="{oy + .5}" width="{pw_ - 1:.1f}" height="25" rx="12.5" fill="{tint}" stroke="{ACCENT}"/>'
                + text(px_ + pw_ / 2, oy + 17, po, "mono", 11, ink(ACCENT, tint), "middle") + "</g>")
    tap = (px_ + pw_ / 2, oy + 13)
    chat.append(f'<circle class="ctap" cx="{tap[0]:.1f}" cy="{tap[1]}" r="14" fill="{SELECT}" fill-opacity=".3"/>')
    y = oy + 25 + 12
    green = ink("#1F883D", t["raised"], 3)
    m4, h4, bx4 = bubble(y, wrap(a["done"], bmax - 20, "regular", size), lead=20)
    m4 += (f'<circle cx="{bx4 + 19:.1f}" cy="{y + 16}" r="7" fill="{green}"/>'
           f'<path d="M{bx4 + 16:.1f} {y + 16}l2 2 4-4" stroke="#fff" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round"/>')
    chat.append(f'<g class="m4">{m4}</g>')
    chat_h = y + h4 + pad

    # ----------------------------------------------------------- lienzo
    label = a["cta"]
    lw = tw(label, 14, "semibold")
    bw, bh = round(18 + lw + 8 + 20 + 18), 44
    k = 1.25 if small else 1.6
    sw, sh = bw * k, bh * k
    bx = (cvw - sw) / 2 if small else pad + 36
    by = 104
    list_x = pad if small else bx + sw + 40
    list_w = cvw - pad - list_x
    rows_y = by + sh + 66 if small else by + 4
    canvas_h = max(rows_y + 3 * 32 + 12 + 32 + pad if small else 0, by + sh + 120)
    if not small:
        chat_h = canvas_h = max(chat_h, canvas_h)
        # centra el bloque (etiqueta del componente → medidas de abajo) entre el título y el aviso
        dy = round((pad + 24 + canvas_h - pad - 32) / 2 - (by - 42 + by + sh + 40) / 2)
        by += dy
        rows_y += dy
    ox_, oy_ = (0, chat_h + 12) if small else (cpw + 16, 0)
    fill = BRAND
    cv = [f'<rect x=".5" y=".5" width="{cvw - 1:.1f}" height="{canvas_h - 1}" rx="16" fill="{t["surface"]}" stroke="{t["border"]}"/>',
          f'<rect x="1" y="1" width="{cvw - 2:.1f}" height="{canvas_h - 2}" rx="15.5" fill="url(#cdots)"/>',
          text(pad, pad + 12, "CANVAS", "mono", 11, t["muted"], ls=1.5),
          text(cvw - pad, pad + 12, "Onboarding", "mono", 11, t["muted"], "end")]
    cv.append(f'<g class="idle">{text(cvw / 2, canvas_h / 2, "waiting for the agent…", "mono", 11, t["muted"], "middle")}</g>')
    comp = "Button / Primary"
    cw_ = tw(comp, 10, "semibold") + 18
    cv.append(f'<g class="bcomp"><rect x="{bx - 4:.1f}" y="{by - 4}" width="{sw + 8:.1f}" height="{sh + 8:.1f}" rx="{12 * k + 4:.1f}" stroke="{COMPONENT}" stroke-width="1.5"/>'
              f'<rect x="{bx - 4:.1f}" y="{by - 42}" width="{cw_:.0f}" height="15" rx="4" fill="{COMPONENT}"/>'
              + diamond(bx - 1, by - 39.5, 10, "#fff") + text(bx + 12, by - 31.5, comp, "semibold", 10, "#fff") + "</g>")
    cv.append(f"""<g transform="translate({bx:.1f} {by}) scale({k})">
      <g class="bframe"><rect x=".5" y=".5" width="{bw - 1}" height="{bh - 1}" rx="12" stroke="{SELECT}" stroke-dasharray="4 3"/></g>
      <g class="bfill"><rect width="{bw}" height="{bh}" rx="12" fill="{fill}"/></g>
      <g class="blabel">{text(18, 27.5, label, "semibold", 14, ON_BRAND)}
        <g transform="translate({18 + lw + 8:.1f} 12)">{GLYPHS["arrow"].format(c=ON_BRAND)}</g></g>
    </g>""")
    # medidas
    rl = [f'<path d="M{bx:.1f} {by - 14}H{bx + sw:.1f}M{bx:.1f} {by - 18}v8M{bx + sw:.1f} {by - 18}v8'
          f'M{bx - 14:.1f} {by}V{by + sh:.1f}M{bx - 18:.1f} {by}h8M{bx - 18:.1f} {by + sh:.1f}h8" stroke="{REDLINE}"/>',
          redline_pill(bx + sw / 2, by - 14, str(bw)), redline_pill(bx - 14, by + sh / 2, str(bh))]
    yb = by + sh + 14
    segs = [(0, 18, "18"), (18, 18 + lw, f"{lw:.0f}"), (18 + lw, 26 + lw, "8"), (26 + lw, 46 + lw, "20"), (46 + lw, bw, "18")]
    for i, (s0, s1, s) in enumerate(segs):
        x0, x1 = bx + s0 * k, bx + s1 * k
        rl.append(f'<path d="M{x0 + 1:.1f} {yb}H{x1 - 1:.1f}M{x0 + 1:.1f} {yb - 4}v8M{x1 - 1:.1f} {yb - 4}v8" stroke="{REDLINE}"/>'
                  + redline_pill((x0 + x1) / 2, yb + 15 + (i % 2) * 17, s))  # alternadas para que no se pisen
    cv.append(f'<g class="bred">{"".join(rl)}</g>')
    # tokens que el agente enlaza
    legend = [(fill, "fill", "brand/primary"), (ON_BRAND, "label", "text/on-brand"), (None, "radius", f"radius/md · {RADIUS['md']}")]
    for i, (c, name, token) in enumerate(legend):
        ry = rows_y + i * 32
        row = (f'<rect x="{list_x:.1f}" y="{ry}" width="{list_w:.1f}" height="26" rx="8" fill="{t["raised"]}" stroke="{t["border"]}"/>'
               + (f'<rect x="{list_x + 8:.1f}" y="{ry + 7}" width="12" height="12" rx="3" fill="{c}" stroke="{t["border"]}"/>' if c else
                  f'<path d="M{list_x + 9:.1f} {ry + 19}v-5a5 5 0 0 1 5-5h5" stroke="{t["muted"]}" stroke-width="1.5"/>')
               + text(list_x + 28, ry + 17, name, "mono", 10.5, t["muted"])
               + text(list_x + list_w - 10, ry + 17, token, "mono", 10.5, t["fg"], "end"))
        if not small:
            row += (f'<path d="M{bx + sw + 6:.1f} {by + sh * (.25 + .25 * i):.1f}L{list_x - 4:.1f} {ry + 13}" '
                    f'stroke="{COMPONENT}" stroke-dasharray="2 3"/><circle cx="{bx + sw + 6:.1f}" cy="{by + sh * (.25 + .25 * i):.1f}" r="2.5" fill="{COMPONENT}"/>')
        cv.append(f'<g class="tk{i}">{row}</g>')
    toast_y = canvas_h - pad - 32
    cv.append(f'<g class="toast"><rect x="{pad}" y="{toast_y}" width="{cvw - 2 * pad:.1f}" height="32" rx="10" fill="{t["raised"]}" stroke="{t["border"]}"/>'
              f'<circle cx="{pad + 18}" cy="{toast_y + 16}" r="7" fill="{green}"/>'
              f'<path d="M{pad + 15} {toast_y + 16}l2 2 4-4" stroke="#fff" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round"/>'
              + text(pad + 32, toast_y + 20.5, a["toast"], "semibold", 12, t["fg"])
              + text(cvw - pad - 12, toast_y + 20.5, "v1.0", "mono", 10.5, t["muted"], "end") + "</g>")

    # cursor de Jorge: descansa arriba a la derecha del chat y baja a elegir la opción
    rest = (cpw - 84, pad)
    for cls, at in [("m1", 3), ("m2", 15), ("m3", 24), ("pick", 37), ("bfill", 46), ("blabel", 50), ("bred", 55),
                    ("tk0", 58), ("tk1", 61), ("tk2", 64), ("bcomp", 69), ("m4", 70), ("toast", 72)]:
        appear(cls, at)
    anim("dots", "0%,6%{opacity:0}8%,14%{opacity:1}15.5%,100%{opacity:0}")
    anim("idle", "0%,36%{opacity:1}39%,97%{opacity:0}100%{opacity:1}")
    anim("bframe", "0%,39%{opacity:0;transform:scaleX(0)}40%{opacity:1;transform:scaleX(0)}45%,94%{opacity:1;transform:scaleX(1)}"
                   "97%,100%{opacity:0;transform:scaleX(1)}", "cubic-bezier(.45,0,.2,1)")
    anim("cur", f"0%,28%{{transform:translate(0,0)}}34%,46%{{transform:translate({tap[0] - rest[0]:.0f}px,{tap[1] - rest[1]:.0f}px)}}"
                f"54%,100%{{transform:translate(0,0)}}", "cubic-bezier(.45,0,.2,1)")
    anim("ctap", "0%,35%{opacity:0;transform:scale(.4)}36%{opacity:1;transform:scale(.4)}40%,100%{opacity:0;transform:scale(1.6)}")
    css.append(".dots,.ctap,.idle{opacity:0}.bframe{transform-box:fill-box;transform-origin:0 0}"
               ".ctap{transform-box:fill-box;transform-origin:center}"
               ".dt{animation:dt 1s ease-in-out infinite}@keyframes dt{0%,60%,100%{transform:none}30%{transform:translateY(-3px)}}")
    body = f"""
    <defs><pattern id="cdots" x="0" y="0" width="16" height="16" patternUnits="userSpaceOnUse"><circle cx="1" cy="1" r=".9" fill="{t["dot"]}"/></pattern></defs>
    <rect x=".5" y=".5" width="{cpw - 1}" height="{chat_h - 1}" rx="16" fill="{t["surface"]}" stroke="{t["border"]}"/>
    {"".join(chat)}
    <g transform="translate({ox_} {oy_})">{"".join(cv)}</g>
    <g transform="translate({rest[0]} {rest[1]})"><g class="cur">{cursor(SELECT, "Jorge", t)}</g></g>
    """
    h = chat_h + 12 + canvas_h if small else canvas_h
    title = f'Agentic design system: "{a["prompt"]}" → the agent asks "{a["question"]}" → {a["done"]}'
    return w, round(h), body, "".join(css), title


def exploring(t, w=W):
    """Cada tema se «dibuja» como un rectángulo en Figma: el cursor arrastra el contorno y luego aparece el texto.
    12 s en bucle; el primer cuadro ya muestra todos los temas."""
    size = 14 if w > 500 else 13
    rows = flow_chips(CONTENT["exploring"], w - 8, size, gap=10, pad=46)
    chips = []
    for r, row in enumerate(rows):
        x0 = (w - (row[-1][0] + row[-1][1])) / 2  # cada fila centrada
        for x, cw, label in row:
            chips.append((x + x0, 10 + r * 46, cw, label))
    cycle, delay = 12, -6.6
    starts = [4 + i * 9 for i in range(len(chips))]
    ease = "cubic-bezier(.45,0,.2,1)"
    rx_, ry_ = chips[-1][0] + chips[-1][2], chips[-1][1] + 35  # el cursor descansa al final del último
    rel = lambda x, y: f"transform:translate({x - rx_:.0f}px,{y - ry_:.0f}px)"
    path = [f"0%,{starts[0]}%{{{rel(chips[0][0], chips[0][1])}}}"]
    css, out = [], []
    for i, ((x, y, cw, label), s) in enumerate(zip(chips, starts)):
        if i:
            path.append(f"{s}%{{{rel(x, y)}}}")
        path.append(f"{s + 5}%{{{rel(x + cw, y + 35)}}}")
        css.append(f".ex{i}{{animation:ex{i} {cycle}s {ease} {delay}s infinite;transform-box:fill-box;transform-origin:0 0}}"
                   f"@keyframes ex{i}{{0%,{s - .1:.1f}%{{opacity:0;transform:scale(.02)}}{s}%{{opacity:1;transform:scale(.02)}}"
                   f"{s + 5}%,92%{{opacity:1;transform:scale(1)}}96%,100%{{opacity:0;transform:scale(1)}}}}"
                   f".xs{i}{{opacity:0;animation:xs{i} {cycle}s {delay}s infinite}}"
                   f"@keyframes xs{i}{{0%,{s - .1:.1f}%{{opacity:0}}{s}%,{s + 6}%{{opacity:1}}{s + 8}%,100%{{opacity:0}}}}"
                   f".et{i}{{animation:et{i} {cycle}s {delay}s infinite}}"
                   f"@keyframes et{i}{{0%,{s + 5}%{{opacity:0}}{s + 7}%,92%{{opacity:1}}96%,100%{{opacity:0}}}}")
        out.append(f"""
        <g class="ex{i}">
          <rect x="{x + .5:.1f}" y="{y + .5}" width="{cw - 1:.1f}" height="35" rx="17.5" fill="{t["surface"]}" stroke="{t["border"]}"/>
          <rect class="xs{i}" x="{x + .5:.1f}" y="{y + .5}" width="{cw - 1:.1f}" height="35" rx="17.5" stroke="{SELECT}" stroke-width="1.5"/>
        </g>
        <g class="et{i}">
          <circle cx="{x + 20:.1f}" cy="{y + 18}" r="4" fill="{ACCENT}"/>
          {text(x + 32, y + 23, label, "medium", size, t["fg"])}
        </g>""")
    path.append(f"92%{{transform:translate(0,0)}}100%{{{rel(chips[0][0], chips[0][1])}}}")
    css.append(f".cur{{animation:cur {cycle}s {ease} {delay}s infinite}}@keyframes cur{{{''.join(path)}}}")
    out.append(f'<g transform="translate({rx_:.1f} {ry_})"><g class="cur">{cursor(SELECT, "Jorge", t)}</g></g>')
    h = ry_ + 44
    return w, round(h), "".join(out), "".join(css), "Currently exploring: " + ", ".join(CONTENT["exploring"])



def export_tokens():
    """tokens.json en formato W3C Design Tokens, con los mismos valores que dibujan el perfil."""
    col = lambda v: {"$type": "color", "$value": v}
    data = {
        "color": {
            "brand": {"primary": col(BRAND), "accent": col(ACCENT), "on-brand": col(ON_BRAND), "deep": col(BRAND_DEEP)},
            "claude": col(CLAUDE), "ai": col(AI),
            "figma": {"select": col(SELECT), "component": col(COMPONENT), "redline": col(REDLINE)},
            **{name: {k: col(v) for k, v in t.items() if v.startswith("#")} for name, t in THEMES.items()},
        },
        "font": {k: {"$type": "typography", "$value": {"fontFamily": f, "fontWeight": wgt}}
                 for k, (f, wgt, *_) in FONTS.items()},
        "radius": {k: {"$type": "dimension", "$value": f"{v}px"} for k, v in RADIUS.items()},
    }
    with open(os.path.join(ROOT, "tokens.json"), "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)
        f.write("\n")


def plain(s):
    return s.replace("*", "")


def footer(t, w=W):
    """Cita con la parte entre *…* seleccionada como texto en Figma; se parte en líneas si no cabe."""
    small = w < 500
    size, lh = (23, 32) if small else (26, 36)
    # palabras marcadas como seleccionadas o no
    words, prev = [], " "
    for k, part in enumerate(re.split(r"\*(.+?)\*", CONTENT["quote"])):
        for m in re.finditer(r"(\s*)(\S+)", part):
            glued = not m.group(1) and not (m.start() == 0 and prev[-1:].isspace())
            words.append((m.group(2), k % 2 == 1, glued and bool(words)))
        prev = part or prev
    def join(ws):
        return "".join(("" if g or i == 0 else " ") + x for i, (x, _, g) in enumerate(ws))
    lines, cur = [], []
    for wd in words:
        cand = join(cur + [wd])
        if cur and not wd[2] and tw(cand, size, "display", -.5) > w - 32:
            lines.append(cur)
            cur = []
        cur.append(wd)
    lines.append(cur)
    y0 = 78
    out = []
    caret = None
    for li, line in enumerate(lines):
        y = y0 + li * lh
        x0 = w / 2 - tw(join(line), size, "display", -.5) / 2
        # tramos consecutivos con el mismo estado, dibujados por separado para que la selección no se corra
        runs = []
        for wd in line:
            if runs and runs[-1][0][-1][1] == wd[1]:
                runs[-1][0].append(wd)
            else:
                runs.append(([wd], wd[2]))
        x = x0
        for ws, glued in runs:
            if x > x0 and not glued:
                x += tw(" ", size, "display", -.5) + .5
            seg = join([(a, b, False if i == 0 else g) for i, (a, b, g) in enumerate(ws)])
            sw = tw(seg, size, "display", -.5)
            if ws[0][1]:
                out.append(f'<rect x="{x - 2:.1f}" y="{y - size + 1}" width="{sw + 4:.1f}" height="{size + 8}" fill="{SELECT}" fill-opacity=".28"/>')
                caret = (x + sw + 1, y - size - 1)
            out.append(text(x, y, seg, "display", size, t["fg"], ls=-.5))
            x += sw
    if caret:
        out.append(f'<rect class="caret" x="{caret[0]:.1f}" y="{caret[1]}" width="2" height="{size + 12}" fill="{SELECT}"/>')
    y = y0 + (len(lines) - 1) * lh + 34
    sig = [CONTENT["signature"]]
    if small:
        sig = [""]
        for seg in CONTENT["signature"].split(" · "):
            cand = f"{sig[-1]} · {seg}" if sig[-1] else seg
            if sig[-1] and tw(cand, 11.5, "mono", 1) > w - 32:
                sig.append(seg)
            else:
                sig[-1] = cand
    for k, l in enumerate(sig):
        out.append(text(w / 2, y + k * 20, l, "mono", 11.5 if small else 12, t["muted"], "middle", ls=1))
    y += len(sig) * 20 + 4
    out.append(text(w / 2, y, datetime.date.today().strftime("updated %b %Y").lower(), "mono", 11, t["muted"], "middle", ls=1))
    css = ".caret{animation:blink 1.1s steps(1) infinite} @keyframes blink{50%{opacity:0}}"
    body = f"""
    <defs><linearGradient id="l" x1="0" x2="1"><stop offset="0" stop-color="{t["border"]}" stop-opacity="0"/>
      <stop offset=".5" stop-color="{ACCENT}"/><stop offset="1" stop-color="{t["border"]}" stop-opacity="0"/></linearGradient></defs>
    <path d="M{w / 6:.0f} 20H{w * 5 / 6:.0f}" stroke="url(#l)" stroke-width="1.5"/>
    <path d="M{w / 2} 14l6 6-6 6-6-6z" fill="{ACCENT}"/>
    {"".join(out)}
    """
    return w, round(y + 22), body, css, plain(CONTENT["quote"])


# -------------------------------------------------------------------- README
def picture(key, alt, width="100%", mobile=True):
    """<picture> sin espacios internos. Orden: móvil (solo por ancho) → oscuro → claro."""
    w = f' width="{width}"' if width else ""
    m = f'<source media="(max-width: 600px)" srcset="./assets/{key}-mobile.svg">' if mobile else ""
    return (f'<picture>{m}<source media="(prefers-color-scheme: dark)" srcset="./assets/{key}-dark.svg">'
            f'<img alt="{escape(alt, {chr(34): "&quot;"})}" src="./assets/{key}-light.svg"{w}></picture>')


def block(inner):
    return f'<p align="center">\n  {inner}\n</p>\n'


def readme(sections):
    c = CONTENT
    links = "\n  ".join(f'<a href="{url}">{picture(f"link-{i + 1}", label + (" (work in progress)" if rest[1:] else ""), None, False)}</a>'
                        for i, (label, url, *rest) in enumerate(c["links"]))
    picture_link = lambda url, inner: f'<a href="{url}">{inner}</a>' if url else inner
    out = ["<!--\n  Archivo generado por build.py: no lo edites a mano.\n"
           "  Para cambiar textos o enlaces, edita CONTENT en build.py: GitHub Actions lo regenera solo\n"
           "  (o ejecútalo tú con  python3 build.py)\n-->\n",
           block(picture("banner", f'{" ".join(c["name"])} — {" ".join(c["role"])} Knowledge is universal; judgment isn\'t. '
                         + " · ".join(l for _, l in c["chips"]))),
           block(links), "<br>\n"]
    for key, num, title, _ in sections:
        out.append(block(picture(key, f"{num} · {title}")))
        if key == "h-about":
            out += [c["intro"] + "\n", block(picture("layers-head", "Layers: click a layer to inspect it"))]
            # cada capa se abre con un clic; la primera viene abierta. 93 %: deja sitio al triángulo del <summary>
            for i, a in enumerate(c["about"]):
                out.append(f'<details{" open" if i == 0 else ""}>\n'
                           f'<summary>{picture(f"layer-{i + 1}", f"Layer 0{i + 1}: {a[2]} (click to inspect)", "93%")}</summary>\n\n'
                           + block(picture(f"inspect-{i + 1}", f"{a[2]}: {a[3]} Properties: {', '.join(a[4])}."))
                           + "</details>\n")
        elif key == "h-portfolio":
            p = c["portfolio"]
            alt = f'Portfolio, work in progress: {" ".join(p["title"])} {p["lead"]}'
            out.append(block(f'<a href="{p["url"]}">{picture("portfolio", alt)}</a>'))
            out.append(f'<p align="center"><sub>{p["note"]}</sub></p>\n')
        elif key == "h-method":
            out.append(block(picture("method", method_title())))
        elif key == "h-system":
            a = c["agent"]
            out.append(block(picture("system", f'Agentic design system: "{a["prompt"]}" — the agent finds the tokens, '
                                               f'asks "{a["question"]}", builds the component and publishes it')))
            out.append(block(picture("rules", "Three rules I design AI by: " + "; ".join(f"{r[1]} — {r[2]}" for r in a["rules"]))))
            out.append('<p align="center"><sub>AI brings the knowledge; my judgment decides what stays. The agent is a concept '
                       'I\'m exploring; the three rules come from ATLAS, my thesis product. The tokens it uses are real — the '
                       'same ones that draw this page, exported to <a href="./tokens.json"><code>tokens.json</code></a>.</sub></p>\n')
        elif key == "h-exploring":
            out.append(block(picture("exploring", "Currently exploring: " + ", ".join(c["exploring"]))))
        out.append("<br>\n")
    k = c["contact"]
    li = next(url for label, url, *_ in c["links"] if label == "LinkedIn")
    pf = c["portfolio"]["url"]
    out.append(f'<p align="center"><b>{k["question"]}</b><br>\n'
               f'<a href="{li}">Message me on LinkedIn</a> · <a href="{pf}">Follow the portfolio build</a></p>\n')
    out.append("<br>\n")
    out.append(block(picture("footer", plain(c["quote"]))))
    return "\n".join(out)


# ----------------------------------------------------------------------- main
def main():
    os.makedirs(ASSETS, exist_ok=True)
    # secciones numeradas en orden
    sections = [("h-about", "About me", "/about"), ("h-portfolio", "Portfolio", "/wip"),
                 ("h-method", "How I break down a problem", "/method"), ("h-system", "AI with judgment", "/agents"),
                 ("h-exploring", "Currently exploring", "/now")]
    sections = [(key, f"{i + 1:02d}", title, slug) for i, (key, title, slug) in enumerate(sections)]

    pieces = {
        "banner": (banner,),
        "layers-head": (layers_head,),
        **{f"layer-{i + 1}": (layer_row, i) for i in range(len(CONTENT["about"]))},
        **{f"inspect-{i + 1}": (inspector, i) for i in range(len(CONTENT["about"]))},
        "method": (method,),
        "exploring": (exploring,),
        "system": (agentic,),
        "rules": (rules,),
        "portfolio": (portfolio,),
        "footer": (footer,),
        **{key: (header, num, title, slug) for key, num, title, slug in sections},
        **{f"link-{i + 1}": (button, label, glyph, i == 0, *badge)
           for i, (label, _, glyph, *badge) in enumerate(CONTENT["links"])},
    }
    mobile = {"banner": (banner_mobile,), "layers-head": (layers_head, MW),
              **{f"layer-{i + 1}": (layer_row, i, MW) for i in range(len(CONTENT["about"]))},
              **{f"inspect-{i + 1}": (inspector, i, MW) for i in range(len(CONTENT["about"]))},
              "method": (method, MW),
              "exploring": (exploring, MW), "system": (agentic, MW), "rules": (rules, MW),
              "portfolio": (portfolio, MW), "footer": (footer, MW),
              **{key: (header, num, title, slug, MW) for key, num, title, slug in sections}}
    written = set()
    for key, (piece, *args) in pieces.items():
        for name, t in THEMES.items():
            written.add(f"{key}-{name}.svg")
            with open(os.path.join(ASSETS, f"{key}-{name}.svg"), "w", encoding="utf-8") as f:
                f.write(svg(*piece(dict(t, name=name), *args)))
    for key, (piece, *args) in mobile.items():
        written.add(f"{key}-mobile.svg")
        with open(os.path.join(ASSETS, f"{key}-mobile.svg"), "w", encoding="utf-8") as f:
            f.write(dual(piece, *args))
    # borra SVG generados que ya no corresponden (p. ej. una sección que se quitó)
    for old in os.listdir(ASSETS):
        if old.endswith(".svg") and old not in written:
            os.remove(os.path.join(ASSETS, old))

    with open(os.path.join(ROOT, "README.md"), "w", encoding="utf-8") as f:
        f.write(readme(sections))
    export_tokens()
    print("SVGs generados en", ASSETS, "y README.md actualizado")


if __name__ == "__main__":
    main()
