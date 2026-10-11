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
    "name": ["Jorge Alberto", "Ramos Tellez"],
    "overline": "PRODUCT DESIGNER · CYBERNETICS ENGINEER",
    "role_tag": "Design Engineer",
    "chips": [("#F24E1E", "UI/UX"), ("#A259FF", "Design Systems"), ("#1ABCFE", "Design Engineering"), ("#D97757", "AI-assisted")],
    "links": [  # (etiqueta, url, glifo, insignia opcional). El primero se dibuja como botón principal.
        ("LinkedIn", "https://www.linkedin.com/in/jorge-ramos-tellez", "linkedin"),
        # cuando el portafolio esté publicado: cambia la URL, quita "WIP" y súbelo al primer lugar
        ("Portfolio", "https://github.com/JorgeRamos-UX/Portafolio-UX", "globe", "WIP"),
    ],
    "intro": ("I'm a **Product Designer and Design Engineer** with a background in **Cybernetics Engineering**. "
              "I design digital products end to end — research, flows, interfaces and design systems — and use AI "
              "and code to take ideas from first sketch to something real."),
    "about": [  # (glifo, color, título, descripción, etiquetas)
        ("pen", "#F24E1E", "Product Design & UI/UX",
         "From problem framing and user flows to polished, high-fidelity interfaces for web and mobile products.",
         ["Flows", "Interaction", "Hi-fi UI", "Prototyping"]),
        ("components", "#A259FF", "Design Systems & DesignOps",
         "Components, tokens and variables, plus the documentation and processes that help teams build consistently at scale.",
         ["Components", "Tokens", "Variables", "Docs"]),
        ("search", "#1ABCFE", "UX Research & IA",
         "Interviews, synthesis and information architecture that turn messy problems into clear structures.",
         ["Interviews", "Synthesis", "IA"]),
        ("sparkle", "#D97757", "AI & Design Engineering",
         "AI-assisted workflows and design-to-code: HTML prototypes, agents and tooling that close the gap between design and build.",
         ["Agents", "Design-to-code", "Tooling"]),
    ],
    "workflow": [
        ("figma", "Figma", "Design systems, components, variables, prototyping"),
        ("claude", "Claude", "Research, UX writing, HTML prototypes, design-to-code"),
        ("git", "Git", "Versioning tokens, specs and prototypes"),
        ("github", "GitHub", "Handoff, docs and collaboration with devs"),
    ],
    # lo que viaja de un paso al siguiente en el workflow del celular
    "handoffs": ["frame", "code", "commit"],
    # en escritorio, un mismo entregable cambia de forma en cada herramienta: (ícono, texto)
    "artifacts": [("frame", "Onboarding.fig"), ("code", "<Onboarding />"),
                  ("commit", "a1f3c9e · feat: onboarding"), ("pr", "PR #12 · merged")],
    # sección «Agentic design system»: el agente construye un componente y pregunta antes de decidir
    "agent": {"name": "Design system agent", "status": "online · reads tokens.json",
              "prompt": "Create a primary button for the onboarding screen",
              "found": "Found 3 tokens in the library: brand/primary-ink, text/on-brand and radius/md.",
              "question": "Which size should it use?", "options": ["S · 32", "M · 44", "L · 56"], "pick": 1,
              "done": "Published Button / Primary to the library.", "cta": "Get started"},
    # Tarjetas de proyecto (assets/work-N-*.svg). Vacío = la sección no aparece en el README.
    # Formato: (ilustración: grid|phone|flow, color, etiqueta, título, resultado, url)
    # e.g. ("grid", "#A259FF", "Design system", "Project name", "Adopted by 4 product teams", "https://…")
    "work": [],  # en el README se acomodan 3 por fila en escritorio y 1 por fila en el celular
    "exploring": ["Product design strategy", "Human-Computer Interaction", "Agentic design systems",
                  "AI + Product Design", "Design-to-code"],
    "quote": "Designing digital products with a *systems mindset*.",  # *…* = texto seleccionado
    "signature": "designed in figma · built with claude · versioned with git",
    # Pantalla que se construye dentro del banner: de wireframe a alta fidelidad
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
ACCENT = "#D97757"     # Claude
SELECT = "#0D99FF"     # selección de Figma
COMPONENT = "#9747FF"  # instancias de componente en Figma
REDLINE = "#F24822"    # medidas de Figma
RADIUS = {"sm": 7, "md": 12, "lg": 16, "xl": 20}  # etiquetas · botones · tarjetas · banner
W = 900   # ancho de escritorio (GitHub muestra el README a 846 px)
MW = 360  # ancho móvil (GitHub muestra el README a ~293 px en un teléfono)

FONTS = {  # clave: (familia en Google Fonts, peso, pila de respaldo)
    "display": ("Inter Tight", 800, "-apple-system, BlinkMacSystemFont, 'Segoe UI', Helvetica, Arial, sans-serif"),
    "regular": ("Inter", 400, "-apple-system, BlinkMacSystemFont, 'Segoe UI', Helvetica, Arial, sans-serif"),
    "medium": ("Inter", 500, "-apple-system, BlinkMacSystemFont, 'Segoe UI', Helvetica, Arial, sans-serif"),
    "semibold": ("Inter", 600, "-apple-system, BlinkMacSystemFont, 'Segoe UI', Helvetica, Arial, sans-serif"),
    "bold": ("Inter", 700, "-apple-system, BlinkMacSystemFont, 'Segoe UI', Helvetica, Arial, sans-serif"),
    "mono": ("JetBrains Mono", 500, "ui-monospace, SFMono-Regular, Menlo, Consolas, monospace"),
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
    family, weight, _ = FONTS[key]
    q = f"family={family.replace(' ', '+')}:wght@{weight}"
    tag = f"{family.replace(' ', '')}-{weight}"
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
        family, weight, fallback = FONTS[key]
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
def icon(name, theme):
    """SVG de 256×256 con el estilo de Skill Icons."""
    if name == "claude":
        tile = "#242938" if theme == "dark" else "#F4F2ED"
        return (f'<svg xmlns="http://www.w3.org/2000/svg" width="256" height="256" viewBox="0 0 256 256">'
                f'<rect width="256" height="256" rx="60" fill="{tile}"/>'
                f'<g transform="translate(48 48) scale(6.6667)"><path fill="{ACCENT}" d="{claude_path()}"/></g></svg>')
    return cached(f"{name}-{theme}.svg", f"https://skillicons.dev/icons?i={name}&theme={theme}").decode()


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
        <rect x="12" y="242" width="152" height="38" rx="12" fill="{t["fg"]}"/>
        <g class="cta-old">{text(88, 265, m["cta_before"], "semibold", 12, t["bg"], "middle")}</g>
        <g class="cta-new">{text(88, 265, m["cta"], "semibold", 12, t["bg"], "middle")}</g>
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
    return f"""
    <g class="tok">
      <path d="M{target_x} {y + 12}H{x}" stroke="{COMPONENT}" stroke-width="1.2" stroke-dasharray="2 3"/>
      <circle cx="{target_x}" cy="{y + 12}" r="3" fill="{COMPONENT}"/>
      <rect x="{x + .5}" y="{y + .5}" width="{w:.0f}" height="23" rx="7" fill="{t["raised"]}" stroke="{t["border"]}" filter="url(#lift)"/>
      <rect x="{x + 8}" y="{y + 6}" width="12" height="12" rx="3.5" fill="{ACCENT}"/>
      {text(x + 26, y + 16, label, "mono", 10.5, t["fg"])}
    </g>"""


def comment(t, pin_x, pin_y, right):
    """Pin de comentario de Figma con la sugerencia de UX writing de Claude."""
    lines = CONTENT["mock"]["comment"]
    bw = max(tw(l, 11, "regular") for l in lines) + 28
    bh = 68
    bx, by = right - bw, pin_y - bh - 8
    cover = bw - 20
    return f"""
    <g class="bubble">
      <rect x="{bx:.1f}" y="{by}" width="{bw:.1f}" height="{bh}" rx="12" fill="{t["raised"]}" stroke="{t["border"]}" filter="url(#lift)"/>
      <circle cx="{bx + 20:.1f}" cy="{by + 18}" r="8" fill="{ACCENT}"/>
      {claude_mark(bx + 20, by + 18, 10)}
      {text(bx + 34, by + 22, "Claude", "bold", 11, t["fg"])}
      {text(bx + 34 + tw("Claude", 11, "bold") + 6, by + 22, "just now", "regular", 10, t["muted"])}
      <g clip-path="url(#typing)">
        {"".join(text(bx + 14, by + 42 + i * 16, l, "regular", 11, t["fg"]) for i, l in enumerate(lines))}
        <rect class="type" x="{bx + 10 + cover:.1f}" y="{by + 30}" width="{cover:.0f}" height="34" fill="{t["raised"]}"/>
      </g>
      <clipPath id="typing"><rect x="{bx + 10:.1f}" y="{by + 30}" width="{cover:.0f}" height="34"/></clipPath>
    </g>
    <g transform="translate({pin_x} {pin_y})">
      <path d="M0 28V14A14 14 0 1 1 14 28Z" fill="{t["raised"]}" stroke="{t["border"]}" filter="url(#lift)"/>
      <circle cx="14" cy="14" r="10" fill="{ACCENT}"/>
      {claude_mark(14, 14, 12)}
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
    # Claude sugiere «Get started» y el botón cambia. Sin animación (reduced motion) queda el final.
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
      <linearGradient id="brand" x1="0" y1="0" x2="1" y2="1"><stop offset="0" stop-color="{ACCENT}"/><stop offset="1" stop-color="#B4532F"/></linearGradient>
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
      {token_chip(t, px + 186, py + 74, px + 164)}
      {comment(t, 772, 292, 888)}
      <g transform="translate({ai0[0]} {ai0[1]})"><g class="ai">{cursor(ACCENT, "Claude", t)}</g></g>
      <g transform="translate({me0[0]} {me0[1]})"><g class="me">{cursor(SELECT, "Jorge", t)}</g></g>
    </g>
    <rect x=".5" y=".5" width="{W - 1}" height="{h - 1}" rx="19.5" stroke="{t["border"]}"/>
    """
    return W, h, body, css, f'{" ".join(c["name"])} — {c["role_tag"]}'


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
      <g transform="translate({w - 96} {chips_y + (len(rows) - 1) * 38 + 8})"><g class="ai">{cursor(ACCENT, "Claude", t)}</g></g>
      <g transform="translate({fx + fw - 2} {fy + fh - 2})"><g class="me">{cursor(SELECT, "Jorge", t)}</g></g>
    </g>
    <rect x=".5" y=".5" width="{w - 1}" height="{h - 1}" rx="17.5" stroke="{t["border"]}"/>
    """
    return w, h, body, css, f'{" ".join(c["name"])} — {c["role_tag"]}'


# --------------------------------------------------------------------- piezas
# Cada pieza devuelve (ancho, alto, cuerpo, css, título); svg() o dual() la convierten en archivo.
def button(t, label, glyph, primary, badge=None):
    h = 44
    lw = tw(label, 14, "semibold")
    bw = tw(badge, 10, "mono", 1) + 14 if badge else 0
    w = round(lw + 64 + (bw + 8 if badge else 0))
    # el naranja de marca no llega a AA con texto blanco: se usa su versión más oscura
    fill, fg = (ink(ACCENT, "#FFFFFF"), "#FFFFFF") if primary else (t["surface"], t["fg"])
    stroke = "" if primary else f' stroke="{t["border"]}"'
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
    body = f"""
    <rect x="0" y="{cy - 13}" width="{32 if small else 36}" height="26" rx="7" fill="{ACCENT}" fill-opacity=".14"/>
    {text(16 if small else 18, cy + 4.5, num, "mono", 13, ink(ACCENT, t["bg"]), "middle")}
    {text(x_title, cy + 8, title, "bold", size, t["fg"], ls=-.4)}
    <path d="M{x_line0:.0f} {cy}H{x_line1:.0f}" stroke="{t["border"]}" stroke-dasharray="2 5" stroke-linecap="round"/>
    {text(w, cy + 4.5, slug, "mono", 12 if small else 13, t["muted"], "end")}
    """
    return w, h, body, "", title


def thumb(kind, color, w, h):
    """Mini ilustración abstracta para la tarjeta de proyecto."""
    s = 'fill="#fff"'
    if kind == "grid":
        return "".join(f'<rect x="{w / 2 - 75 + c * 40}" y="{h / 2 - 34 + r * 40}" width="30" height="30" rx="8" {s} '
                       f'fill-opacity="{.95 if (c + r) % 3 == 0 else .4}"/>' for r in range(2) for c in range(4))
    if kind == "phone":
        x, y = w / 2 - 34, 16
        return (f'<rect x="{x}" y="{y}" width="68" height="{h}" rx="12" {s} fill-opacity=".95"/>'
                f'<rect x="{x + 10}" y="{y + 16}" width="30" height="6" rx="3" fill="{color}"/>'
                f'<rect x="{x + 10}" y="{y + 30}" width="48" height="22" rx="5" fill="{color}" fill-opacity=".25"/>'
                f'<rect x="{x + 10}" y="{y + 58}" width="48" height="6" rx="3" fill="{color}" fill-opacity=".35"/>'
                f'<rect x="{x + 10}" y="{y + 70}" width="36" height="6" rx="3" fill="{color}" fill-opacity=".35"/>')
    pts = [(w / 2 - 80, h / 2 - 10), (w / 2 - 10, h / 2 - 28), (w / 2 + 60, h / 2 - 10), (w / 2 - 10, h / 2 + 22)]
    lines = "".join(f'<path d="M{a[0] + 30} {a[1] + 12}L{b[0]} {b[1] + 12}" stroke="#fff" stroke-width="2" stroke-opacity=".7"/>'
                    for a, b in zip(pts, pts[1:3]))
    lines += f'<path d="M{pts[1][0] + 15} {pts[1][1] + 24}V{pts[3][1]}" stroke="#fff" stroke-width="2" stroke-opacity=".7"/>'
    return lines + "".join(f'<rect x="{x}" y="{y}" width="30" height="24" rx="6" {s}/>' for x, y in pts)


def work_card(t, i):
    # 276 px de ancho natural: 3 caben en los 846 px del README y en el celular van de a una sin achicarse
    kind, color, tag, title, outcome, _url = CONTENT["work"][i]
    w, h, th, m = 276, 248, 112, 4  # m: margen transparente que hace de separación entre tarjetas
    cw = w - 2 * m
    tint = mix(color, t["surface"], .15)
    tagw = tw(tag, 11, "mono") + 18
    lines = wrap(outcome, cw - 36, "regular", 13)[:2]
    body = f"""
    <defs><clipPath id="c"><rect x="{m}" y="{m}" width="{cw}" height="{h - 2 * m}" rx="16"/></clipPath>
      <linearGradient id="g" x1="0" y1="0" x2="1" y2="1"><stop offset="0" stop-color="{color}"/><stop offset="1" stop-color="{color}" stop-opacity=".55"/></linearGradient></defs>
    <g clip-path="url(#c)">
      <rect x="{m}" y="{m}" width="{cw}" height="{h}" fill="{t["surface"]}"/>
      <g transform="translate({m} {m})"><rect width="{cw}" height="{th}" fill="url(#g)"/>{thumb(kind, color, cw, th)}</g>
    </g>
    <rect x="{m + .5}" y="{m + .5}" width="{cw - 1}" height="{h - 2 * m - 1}" rx="15.5" stroke="{t["border"]}"/>
    <g transform="translate({m} {m})">
      <rect x="18" y="128" width="{tagw:.0f}" height="20" rx="10" fill="{tint}"/>
      {text(27, 142, tag, "mono", 11, ink(color, tint))}
      {text(18, 176, title, "bold", 17, t["fg"])}
      {"".join(text(18, 197 + j * 17, l, "regular", 13, t["muted"]) for j, l in enumerate(lines))}
      {text(cw - 18, 226, "View case →", "semibold", 13, ink(ACCENT, t["surface"]), "end")}
    </g>
    """
    return w, h, body, "", f"{title} — {tag}: {outcome}"


def redline_pill(cx, cy, s):
    pw = tw(s, 9.5, "bold") + 10
    return (f'<rect x="{cx - pw / 2:.1f}" y="{cy - 7}" width="{pw:.1f}" height="14" rx="3" fill="{REDLINE}"/>'
            + text(cx, cy + 3.5, s, "bold", 9.5, "#fff", "middle"))





def about(t, w=W):
    """Panel de Figma: a la izquierda las capas (una por especialidad) y a la derecha el inspector de la
    capa seleccionada. La selección avanza sola cada 4 s; sin animación queda la primera."""
    items = CONTENT["about"]
    n, beat = len(items), 4
    cycle, p = n * beat, 100 / n
    small = w < 500
    pad, row_h = 20, 44
    lw = w if small else 296
    iw = w if small else w - lw - 16
    css = (f".it,.hl{{opacity:0;animation:it {cycle}s infinite}}"
           f"@keyframes it{{0%{{opacity:0}}1.5%,{p - 1.5:.1f}%{{opacity:1}}{p:.1f}%,100%{{opacity:0}}}}"
           f".sg{{transform:scaleX(0);transform-box:fill-box;transform-origin:0 50%;animation:sg {cycle}s linear infinite}}"
           f"@keyframes sg{{0%{{transform:scaleX(0)}}{p:.1f}%{{transform:scaleX(1)}}{p + .01:.2f}%,100%{{transform:scaleX(0)}}}}"
           "@media (prefers-reduced-motion: reduce){.it0,.hl0{opacity:1}}")
    delay = lambda i: f"animation-delay:{i * beat - cycle}s"  # negativo: el ciclo ya está en marcha al cargar
    desc_w = iw - 2 * pad
    wrapped = [wrap(a[3], desc_w, "regular", 15) for a in items]
    tag_rows = [flow_chips(a[4], desc_w, 11.5, "mono", 8, 20) for a in items]
    ih = max(pad + 104 + 23 * (len(l) - 1) + 46 + len(r) * 34 + pad - 8 for l, r in zip(wrapped, tag_rows))
    lh = pad + 54 + n * row_h + 6
    if not small:
        ih = lh = max(ih, lh)
    # capas
    lp = [f'<rect x=".5" y=".5" width="{lw - 1}" height="{lh - 1}" rx="16" fill="{t["surface"]}" stroke="{t["border"]}"/>',
          text(pad, pad + 12, "LAYERS", "mono", 11, t["muted"], ls=1.5),
          f'<path d="M{pad + 1} {pad + 31}h11M{pad + 1} {pad + 37}h11M{pad + 4} {pad + 28}v12M{pad + 9} {pad + 28}v12" '
          f'stroke="{t["muted"]}" stroke-width="1.3"/>',
          text(pad + 22, pad + 39, " ".join(CONTENT["name"]), "semibold", 13, t["fg"]),
          f'<path d="M{pad + 6} {pad + 48}V{pad + 54 + (n - 1) * row_h + 19}" stroke="{t["border"]}"/>']
    for i, (glyph, color, title, _, _) in enumerate(items):
        y = pad + 54 + i * row_h
        lp.append(f'<rect class="hl hl{i}" style="{delay(i)}" x="8" y="{y}" width="{lw - 16}" height="{row_h - 6}" rx="8" '
                  f'fill="{SELECT}" fill-opacity=".16"/>'
                  f'<path d="M{pad + 6} {y + 19}h8" stroke="{t["border"]}"/>'
                  f'<g transform="translate({pad + 16} {y + 8})"><rect width="22" height="22" rx="6" fill="{color}" fill-opacity=".16"/>'
                  f'<g transform="scale(.55)">{GLYPHS[glyph].format(c=color)}</g></g>'
                  + text(pad + 48, y + 24, title, "medium", 13.5, t["fg"]))
    # inspector
    ix, iy = (0, lh + 12) if small else (lw + 16, 0)
    seg = 28
    ip = [f'<rect x=".5" y=".5" width="{iw - 1}" height="{ih - 1}" rx="16" fill="{t["surface"]}" stroke="{t["border"]}"/>',
          text(pad, pad + 12, "INSPECT", "mono", 11, t["muted"], ls=1.5)]
    for i in range(n):
        sx = iw - pad - n * seg - (n - 1) * 4 + i * (seg + 4)
        ip.append(f'<rect x="{sx}" y="{pad + 5}" width="{seg}" height="4" rx="2" fill="{t["border"]}"/>'
                  f'<rect class="sg" style="{delay(i)}" x="{sx}" y="{pad + 5}" width="{seg}" height="4" rx="2" fill="{ACCENT}"/>')
    for i, ((glyph, color, title, _, tags), lines, rows) in enumerate(zip(items, wrapped, tag_rows)):
        tint = mix(color, t["surface"], .12)
        size = 22 if pad + 60 + tw(title, 22, "bold", -.3) < iw - pad else 18
        last = pad + 104 + 23 * (len(lines) - 1)
        chips = []
        for r, row in enumerate(rows):
            for x, cw, tag in row:
                y = last + 46 + r * 34
                chips.append(f'<rect x="{pad + x:.1f}" y="{y}" width="{cw:.1f}" height="26" rx="7" fill="{tint}"/>'
                             + text(pad + x + 10, y + 17, tag, "mono", 11.5, ink(color, tint)))
        ip.append(f"""
        <g class="it it{i}" style="{delay(i)}">
          <g transform="translate({pad} {pad + 28})"><rect width="44" height="44" rx="12" fill="{color}" fill-opacity=".14"/>
            <g transform="translate(2 2)">{GLYPHS[glyph].format(c=color)}</g></g>
          {text(pad + 60, pad + 44, f"LAYER 0{i + 1}", "mono", 10.5, t["muted"], ls=1.2)}
          {text(pad + 60, pad + 66, title, "bold", size, t["fg"], ls=-.3)}
          {"".join(text(pad, pad + 104 + j * 23, l, "regular", 15, t["muted"]) for j, l in enumerate(lines))}
          {text(pad, last + 30, "PROPERTIES", "mono", 10.5, t["muted"], ls=1.2)}
          {"".join(chips)}
        </g>""")
    body = f'<g>{"".join(lp)}</g><g transform="translate({ix} {iy})">{"".join(ip)}</g>'
    h = lh + 12 + ih if small else lh
    return w, h, body, css, "About me: " + "; ".join(f"{a[2]} — {a[3]}" for a in items)


def workflow(t, w=W):
    """Un mismo entregable recorre las cuatro herramientas y cambia de forma en cada una:
    frame → código → commit → PR. En el celular se usa la versión vertical."""
    if w <= 500:
        return workflow_vertical(t, w)
    steps, n = CONTENT["workflow"], len(CONTENT["workflow"])
    cycle, beat = 8, 2
    step = w / n
    cxs = [step * i + step / 2 for i in range(n)]
    ty, tile = 20, 92
    cy = ty + tile / 2
    L = cxs[-1] - cxs[0]
    ease = "cubic-bezier(.6,0,.2,1)"
    stops = lambda f: (f"0%,17.5%{{{f(0)}}}25%,42.5%{{{f(1)}}}50%,67.5%{{{f(2)}}}75%,92%{{{f(3)};opacity:1}}"
                       f"96%{{{f(3)};opacity:0}}98%{{{f(0)};opacity:0}}100%{{{f(0)};opacity:1}}")
    arts = CONTENT["artifacts"]
    cw = max(tw(s, 10.5, "mono") for _, s in arts) + 46
    css = [f"""
    .ring{{opacity:0;animation:ring {cycle}s ease-out infinite;transform-box:fill-box;transform-origin:center}}
    @keyframes ring{{0%{{opacity:0;transform:scale(.92)}}5%{{opacity:1;transform:scale(1)}}18%,100%{{opacity:0;transform:scale(1.05)}}}}
    .rail{{stroke-dasharray:{L:.0f} {L:.0f};animation:rail {cycle}s {ease} infinite}}
    @keyframes rail{{{stops(lambda i: f"stroke-dashoffset:{L - i * step:.0f}")}}}
    .art{{transform:translateX({3 * step:.0f}px);animation:art {cycle}s {ease} infinite}}
    @keyframes art{{{stops(lambda i: f"transform:translateX({i * step:.0f}px)")}}}
    .av0,.av1,.av2{{opacity:0}}
    .av0{{animation:av0 {cycle}s infinite}}@keyframes av0{{0%,19%{{opacity:1}}23%,96%{{opacity:0}}97%,100%{{opacity:1}}}}
    .av1{{animation:av1 {cycle}s infinite}}@keyframes av1{{0%,19%{{opacity:0}}23%,44%{{opacity:1}}48%,100%{{opacity:0}}}}
    .av2{{animation:av2 {cycle}s infinite}}@keyframes av2{{0%,44%{{opacity:0}}48%,69%{{opacity:1}}73%,100%{{opacity:0}}}}
    .av3{{animation:av3 {cycle}s infinite}}@keyframes av3{{0%,69%{{opacity:0}}73%,96%{{opacity:1}}97%,100%{{opacity:0}}}}
    """]
    green = ink("#1F883D", t["raised"], 3)
    icons = {
        "frame": f'<path d="M-5-2h10M-5 2h10M-2-5v10M2-5v10" stroke="{SELECT}" stroke-width="1.4"/>',
        "code": text(0, 3.5, "</>", "mono", 10, ink(ACCENT, t["raised"]), "middle"),
        "commit": f'<path d="M-9 0h5M4 0h5" stroke="{t["muted"]}" stroke-width="1.4"/><circle r="3.5" fill="{t["raised"]}" stroke="{t["fg"]}" stroke-width="1.5"/>',
        "pr": f'<circle r="7" fill="{green}"/><path d="M-3 0l2 2 4-4" stroke="#fff" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round"/>',
    }
    variants = "".join(f'<g class="av{i}"><g transform="translate(16 18)">{icons[kind]}</g>'
                       + text(32, 22, label, "mono", 10.5, t["fg"]) + "</g>" for i, (kind, label) in enumerate(arts))
    out = [f'<path d="M{cxs[0]:.0f} {cy}H{cxs[-1]:.0f}" stroke="{t["border"]}" stroke-width="2" stroke-dasharray="2 6" stroke-linecap="round"/>',
           f'<path class="rail" d="M{cxs[0]:.0f} {cy}H{cxs[-1]:.0f}" stroke="{ACCENT}" stroke-width="2" stroke-linecap="round"/>']
    for i, (key, name, desc) in enumerate(steps):
        cx = cxs[i]
        out.append(f'<rect class="ring" style="animation-delay:{i * beat}s" x="{cx - 52:.0f}" y="{ty - 6}" width="104" height="104" rx="28" stroke="{ACCENT}" stroke-width="2"/>'
                   f'<rect x="{cx - 46:.0f}" y="{ty}" width="92" height="92" rx="24" fill="{t["surface"]}" stroke="{t["border"]}"/>'
                   f'<image href="{data_uri(icon(key, t["name"]))}" x="{cx - 30:.0f}" y="{ty + 16}" width="60" height="60"/>')
    ay = ty + tile + 18
    out.append(f"""
    <g transform="translate({cxs[0] - cw / 2:.1f} {ay})"><g class="art">
      <path d="M{cw / 2 - 6:.1f} .5l6-6 6 6" fill="{t["raised"]}" stroke="{ACCENT}"/>
      <rect x=".5" y=".5" width="{cw - 1:.1f}" height="35" rx="10" fill="{t["raised"]}" stroke="{ACCENT}"/>
      <path d="M{cw / 2 - 5:.1f} 1.5h10" stroke="{t["raised"]}" stroke-width="2"/>
      {variants}
    </g></g>""")
    lines = [wrap(desc, step - 20, "regular", 14) for _, _, desc in steps]
    ly = ay + 36 + 34
    for i, ((key, name, desc), ls) in enumerate(zip(steps, lines)):
        cx = cxs[i]
        out.append(text(cx, ly, f"STEP 0{i + 1}", "mono", 11, ink(ACCENT, t["bg"]), "middle", ls=1.5)
                   + text(cx, ly + 27, name, "bold", 19, t["fg"], "middle", ls=-.2)
                   + "".join(text(cx, ly + 52 + j * 21, l, "regular", 14, t["muted"], "middle") for j, l in enumerate(ls)))
    h = ly + 52 + 21 * (max(map(len, lines)) - 1) + 10
    return w, round(h), "".join(out), "".join(css), "Workflow: " + " → ".join(f"{s[1]} ({s[2]})" for s in steps)


def workflow_vertical(t, w):
    """Versión del celular: los pasos en columna y un punto que baja de una herramienta a la siguiente."""
    steps, n = CONTENT["workflow"], len(CONTENT["workflow"])
    cycle, beat = 6, 1.5
    step_ink, pk_ink = ink(ACCENT, t["bg"]), ink(ACCENT, t["surface"])
    css = [f"""
    .ring{{opacity:0;animation:ring {cycle}s ease-out infinite;transform-box:fill-box;transform-origin:center}}
    @keyframes ring{{0%{{opacity:0;transform:scale(.92)}}5%{{opacity:1;transform:scale(1)}}18%,100%{{opacity:0;transform:scale(1.05)}}}}
    """]
    out = []
    pitch, cx, tx = 124, 38, 92
    h = pitch * (n - 1) + 100
    for i in range(n - 1):
        y0, y1 = i * pitch + 76, (i + 1) * pitch + 2
        label = CONTENT["handoffs"][i]
        pw = tw(label, 10.5, "mono") + 18
        out.append(f'<path d="M{cx} {y0}V{y1 - 4}" stroke="{t["border"]}" stroke-width="2" stroke-dasharray="2 6" stroke-linecap="round"/>'
                   f'<path d="M{cx - 6} {y1 - 10}l6 6 6-6" stroke="{ACCENT}" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/>'
                   f'<rect x="{cx + 14}" y="{(y0 + y1) / 2 - 10:.1f}" width="{pw:.1f}" height="20" rx="7" fill="{t["surface"]}" stroke="{ACCENT}"/>'
                   + text(cx + 14 + pw / 2, (y0 + y1) / 2 + 4, label, "mono", 10.5, pk_ink, "middle"))
        # punto que baja de una herramienta a la siguiente (sale y entra por detrás de los íconos)
        css.append(f".pk{i}{{animation:pkv {cycle}s cubic-bezier(.5,0,.3,1) {i * beat}s infinite}}")
        out.append(f'<circle class="pk{i}" cx="{cx}" cy="{(y0 + y1) / 2:.1f}" r="4.5" fill="{ACCENT}"/>')
    span = (pitch - 76 + 2 + 20) / 2
    css.append(f"@keyframes pkv{{0%{{transform:translateY({-span:.0f}px)}}{beat / cycle * 100:.0f}%,100%{{transform:translateY({span:.0f}px)}}}}")
    for i, (key, name, desc) in enumerate(steps):
        y0 = i * pitch
        lines = wrap(desc, w - tx - 4, "regular", 14)
        out.append(f"""
        <rect class="ring" style="animation-delay:{i * beat}s" x="{cx - 38}" y="{y0}" width="76" height="76" rx="22" stroke="{ACCENT}" stroke-width="2"/>
        <rect x="{cx - 33}" y="{y0 + 5}" width="66" height="66" rx="18" fill="{t["surface"]}" stroke="{t["border"]}"/>
        <image href="{data_uri(icon(key, t["name"]))}" x="{cx - 21}" y="{y0 + 17}" width="42" height="42"/>
        {text(tx, y0 + 16, f"STEP 0{i + 1}", "mono", 10.5, step_ink, ls=1.5)}
        {text(tx, y0 + 40, name, "bold", 18, t["fg"], ls=-.2)}
        {"".join(text(tx, y0 + 62 + j * 20, l, "regular", 14, t["muted"]) for j, l in enumerate(lines))}""")
    return w, h, "".join(out), "".join(css), "Workflow: " + " → ".join(f"{s[1]} ({s[2]})" for s in steps)


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
            svg_ += f'<circle cx="{pad + 11}" cy="{y + 15}" r="11" fill="{ACCENT}"/>' + claude_mark(pad + 11, y + 15, 13)
        return svg_, bh, bx

    chat = [f'<circle cx="{pad + 14}" cy="{pad + 14}" r="14" fill="{ACCENT}"/>', claude_mark(pad + 14, pad + 14, 17),
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
                f'<circle cx="{pad + 11}" cy="{y + 15}" r="11" fill="{ACCENT}"/>{claude_mark(pad + 11, y + 15, 13)}{dots}</g>')
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
    fill = ink(ACCENT, "#FFFFFF")
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
      <g class="blabel">{text(18, 27.5, label, "semibold", 14, "#fff")}
        <g transform="translate({18 + lw + 8:.1f} 12)">{GLYPHS["arrow"].format(c="#fff")}</g></g>
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
    legend = [(fill, "fill", "brand/primary-ink"), ("#FFFFFF", "label", "text/on-brand"), (None, "radius", f"radius/md · {RADIUS['md']}")]
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
              + text(pad + 32, toast_y + 20.5, "Published to library", "semibold", 12, t["fg"])
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
            "brand": {"primary": col(ACCENT), "primary-ink": col(ink(ACCENT, "#FFFFFF"))},
            "figma": {"select": col(SELECT), "component": col(COMPONENT), "redline": col(REDLINE)},
            **{name: {k: col(v) for k, v in t.items() if v.startswith("#")} for name, t in THEMES.items()},
        },
        "font": {k: {"$type": "typography", "$value": {"fontFamily": f, "fontWeight": wgt}}
                 for k, (f, wgt, _) in FONTS.items()},
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
    out = ["<!--\n  Archivo generado por build.py: no lo edites a mano.\n"
           "  Para cambiar textos o enlaces, edita CONTENT en build.py: GitHub Actions lo regenera solo\n"
           "  (o ejecútalo tú con  python3 build.py)\n-->\n",
           block(picture("banner", f'{" ".join(c["name"])} — {c["overline"].title()} · '
                         + " · ".join(l for _, l in c["chips"]))),
           block(links), "<br>\n"]
    for key, num, title, _ in sections:
        out.append(block(picture(key, f"{num} · {title}")))
        if key == "h-about":
            out += [c["intro"] + "\n", block(picture("about", " · ".join(a[2] for a in c["about"])))]
        elif key == "h-work":
            # sin espacios entre tarjetas: el margen va dentro del SVG y así se acomodan solas en filas
            cards = "".join(f'<a href="{w[5]}">{picture(f"work-{i + 1}", f"{w[3]} — {w[4]}", None, False)}</a>'
                            for i, w in enumerate(c["work"]))
            out.append(block(cards))
        elif key == "h-workflow":
            out.append(block(picture("workflow", "My workflow: " + " → ".join(f"{w[1]} ({w[2]})" for w in c["workflow"]))))
        elif key == "h-system":
            a = c["agent"]
            out.append(block(picture("system", f'Agentic design system: "{a["prompt"]}" — the agent finds the tokens, '
                                               f'asks "{a["question"]}", builds the component and publishes it')))
            out.append('<p align="center"><sub>A concept I\'m exploring: an agent that builds with the design system '
                       'and asks before it decides. The tokens it uses are real — the same ones that draw this page, '
                       'exported to <a href="./tokens.json"><code>tokens.json</code></a>.</sub></p>\n')
        elif key == "h-exploring":
            out.append(block(picture("exploring", "Currently exploring: " + ", ".join(c["exploring"]))))
        out.append("<br>\n")
    out.append(block(picture("footer", plain(c["quote"]))))
    return "\n".join(out)


# ----------------------------------------------------------------------- main
def main():
    os.makedirs(ASSETS, exist_ok=True)
    # secciones numeradas en orden; "Selected work" solo aparece si hay proyectos
    sections = [("h-about", "About me", "/about")]
    if CONTENT["work"]:
        sections.append(("h-work", "Selected work", "/work"))
    sections += [("h-workflow", "My design workflow", "/stack"), ("h-system", "Agentic design system", "/system"),
                 ("h-exploring", "Currently exploring", "/now")]
    sections = [(key, f"{i + 1:02d}", title, slug) for i, (key, title, slug) in enumerate(sections)]

    pieces = {
        "banner": (banner,),
        "about": (about,),
        "workflow": (workflow,),
        "exploring": (exploring,),
        "system": (agentic,),
        "footer": (footer,),
        **{key: (header, num, title, slug) for key, num, title, slug in sections},
        **{f"work-{i + 1}": (work_card, i) for i in range(len(CONTENT["work"]))},
        **{f"link-{i + 1}": (button, label, glyph, i == 0, *badge)
           for i, (label, _, glyph, *badge) in enumerate(CONTENT["links"])},
    }
    mobile = {"banner": (banner_mobile,), "about": (about, MW), "workflow": (workflow, MW),
              "exploring": (exploring, MW), "system": (agentic, MW), "footer": (footer, MW),
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
