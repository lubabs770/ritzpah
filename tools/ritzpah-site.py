#!/usr/bin/env python3
"""Build the Ritzpah roster site: a folder you can drag onto Netlify Drop.

Reads themes/<slug>/theme.json + colors.toml and writes a self-contained static
site. The page has no external requests -- no CDN, no webfont, no analytics --
so the whole thing is one HTML file plus images.

This is the one script in the repo that writes outside the repo, and only to the
output directory it is given.
"""

import html
import importlib.util
import json
import os
import shutil
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
_spec = importlib.util.spec_from_file_location("ritzpah_lib", os.path.join(HERE, "ritzpah-lib.py"))
lib = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(lib)

# Preview PNGs are 1-2.5 MB each straight out of the generators. The site does
# not need that: re-encode to WebP at display width. Falls back to a plain copy
# if ImageMagick is missing, because a heavier site beats no site.
PREVIEW_WIDTH = 1600
THUMB_WIDTH = 720
SHEET_WIDTH = 1200


def convert(src, dst, width, quality=82):
    # ImageMagick 7 is `magick`; the 6.x still shipped by Ubuntu (and therefore
    # by GitHub's runners) only has `convert`. Try both before giving up, so CI
    # produces the same small site a local build does.
    for binary in ("magick", "convert"):
        try:
            subprocess.run(
                [binary, src, "-resize", f"{width}>", "-quality", str(quality), dst],
                check=True, capture_output=True,
            )
            return os.path.basename(dst)
        except FileNotFoundError:
            continue
        except subprocess.CalledProcessError:
            break
    fallback = os.path.splitext(dst)[0] + os.path.splitext(src)[1]
    shutil.copy2(src, fallback)
    return os.path.basename(fallback)


def find_doc(repo, slug, suffix, generic):
    """docs/ naming is inconsistent -- the first theme shipped before the
    convention existed, so it owns the unprefixed names."""
    for name in (f"{slug}-{suffix}", generic):
        path = os.path.join(repo, "docs", name)
        if os.path.isfile(path):
            return path
    return None


def collect(repo, assets):
    themes = []
    for path in lib.theme_dirs(repo):
        info = lib.meta(path)
        slug = info["slug"]
        declared = info["declared"]

        try:
            report = lib.contrast_report(path)
        except Exception:
            report = {"background": "#000000", "slots": []}

        colours = lib.read_colors(path)
        assets_for_theme = {}

        preview = os.path.join(path, "preview.png")
        if os.path.isfile(preview):
            assets_for_theme["preview"] = convert(
                preview, os.path.join(assets, f"{slug}-preview.webp"), PREVIEW_WIDTH)
            assets_for_theme["thumb"] = convert(
                preview, os.path.join(assets, f"{slug}-thumb.webp"), THUMB_WIDTH, 78)

        sheet = find_doc(repo, slug, "wallpapers.jpg", "wallpapers.jpg")
        if sheet:
            assets_for_theme["sheet"] = convert(
                sheet, os.path.join(assets, f"{slug}-wallpapers.webp"), SHEET_WIDTH)

        themes.append({
            "slug": slug,
            "name": info["name"],
            "tagline": info["tagline"],
            "tags": info["tags"],
            "kind": info["kind"],
            "floor": info["floor"],
            "exempt": info["exempt"],
            "shader": info["shader"],
            "battery": declared.get("battery", ""),
            "notes": declared.get("notes", ""),
            "wallpapers": len(info["wallpapers"]),
            "sections": len(info["shell_sections"]),
            "background": report["background"],
            "slots": report["slots"],
            "colours": {k: v for k, v in colours.items()
                        if isinstance(v, str) and lib.HEX.match(v)},
            "assets": assets_for_theme,
        })
    return themes


AUDIT_PROMPT = """Audit this repo before I install it: https://github.com/lubabs770/ritzpah
Clone it somewhere temporary and actually read it. Tell me:
- what executes, and when - install time, every shell start, on a timer?
- does anything touch the network, and where does it connect?
- does it write anywhere outside ~/.config/omarchy/themes?
- does it read anything it has no business reading - keys, tokens, shell history?
- anything obfuscated: base64, eval, curl piped into a shell?
Quote the exact lines for anything you flag. If it's clean, say so plainly."""


CSS = """
*,*::before,*::after{box-sizing:border-box}
:root{
  --bg:#0c0c10; --panel:#141419; --line:#26262f; --ink:#e8e8ef;
  --dim:#9a9aab; --accent:#8b7fff; --accent-ink:#0c0c10;
  --mono:ui-monospace,"JetBrainsMono Nerd Font","SFMono-Regular",Menlo,Consolas,monospace;
}
html{scroll-behavior:smooth}
body{margin:0;background:var(--bg);color:var(--ink);font:16px/1.65 var(--mono);
  transition:background .45s ease,color .45s ease}
.wrap{max-width:1120px;margin:0 auto;padding:0 20px}
a{color:var(--accent);text-underline-offset:3px}
h2{letter-spacing:-.02em}
.eyebrow{font-size:11.5px;letter-spacing:.16em;text-transform:uppercase;color:var(--dim);margin:0 0 10px}

/* ---------------------------------------------------------------- hero */
.hero{padding:86px 0 60px}
.hero h1{margin:0;font-size:clamp(46px,13vw,132px);letter-spacing:-.05em;line-height:.9}
.hero h1 .dot{color:var(--accent)}
.hero .lede{margin:20px 0 0;font-size:clamp(17px,2.6vw,23px);max-width:34ch;line-height:1.45}
.hero .lede em{font-style:normal;color:var(--accent)}
.stats{margin:34px 0 0;display:flex;flex-wrap:wrap;gap:34px}
.stats div{min-width:96px}
.stats dt{font-size:11.5px;letter-spacing:.1em;text-transform:uppercase;color:var(--dim)}
.stats dd{margin:4px 0 0;font-size:27px;letter-spacing:-.02em}
.cta{margin:34px 0 0;display:flex;gap:10px;flex-wrap:wrap}
.btn{display:inline-block;border:1px solid var(--line);border-radius:8px;padding:11px 18px;
  font-size:14px;text-decoration:none;color:var(--ink);transition:all .2s ease}
.btn:hover{border-color:var(--ink)}
.btn.primary{background:var(--accent);color:var(--accent-ink);border-color:var(--accent)}

/* ---------------------------------------------------------------- rail */
nav.rail{position:sticky;top:0;z-index:9;background:var(--bg);border-top:1px solid var(--line);
  border-bottom:1px solid var(--line);padding:11px 0;transition:background .45s ease}
.rail-inner{display:flex;gap:8px;overflow-x:auto;scrollbar-width:thin;align-items:center}
.chip{flex:0 0 auto;border:1px solid var(--line);background:transparent;color:var(--dim);
  font:13px/1 var(--mono);padding:9px 13px;border-radius:999px;cursor:pointer;
  white-space:nowrap;transition:all .2s ease;text-decoration:none}
.chip:hover{color:var(--ink);border-color:var(--ink)}
.chip[aria-pressed="true"],.chip.on{background:var(--accent);color:var(--accent-ink);border-color:var(--accent)}
.chip .sw{display:inline-block;width:8px;height:8px;border-radius:50%;margin-right:7px;vertical-align:1px}
.rail-sep{flex:0 0 auto;width:1px;height:22px;background:var(--line);margin:0 4px}

/* ------------------------------------------------------------- catalog */
section{border-bottom:1px solid var(--line)}
.catalog{padding:56px 0}
.catalog h2{margin:0;font-size:clamp(24px,4.6vw,40px)}
.catalog .note{margin:8px 0 0;color:var(--dim);max-width:64ch}
.filters{margin:26px 0 22px;display:flex;flex-wrap:wrap;gap:7px;align-items:center}
.filters .lbl{font-size:11.5px;letter-spacing:.1em;text-transform:uppercase;color:var(--dim);margin-right:4px}
.grid{display:grid;gap:16px;grid-template-columns:repeat(auto-fill,minmax(305px,1fr))}
.card{border:1px solid var(--line);border-radius:12px;overflow:hidden;background:var(--panel);
  text-decoration:none;color:inherit;display:flex;flex-direction:column;transition:transform .18s ease,border-color .18s ease}
.card:hover{transform:translateY(-3px);border-color:var(--accent)}
.card img{width:100%;aspect-ratio:16/9;object-fit:cover;display:block;border-bottom:1px solid var(--line)}
.card .body{padding:15px 16px 17px;flex:1;display:flex;flex-direction:column;gap:9px}
.card h3{margin:0;font-size:19px;letter-spacing:-.01em}
.card p{margin:0;font-size:13.5px;color:var(--dim);line-height:1.55;flex:1}
.card .strip{display:flex;height:9px;border-radius:3px;overflow:hidden}
.card .strip i{flex:1}
.card .meta{display:flex;gap:9px;flex-wrap:wrap;font-size:11.5px;color:var(--dim)}
.card .meta b{font-weight:400;color:var(--ink)}
.card[hidden]{display:none}

/* -------------------------------------------------------------- detail */
.theme{padding:56px 0}
.theme h2{margin:0;font-size:clamp(26px,5vw,44px)}
.theme .tag{margin:9px 0 0;color:var(--dim);max-width:64ch}
.tags{margin:14px 0 0;display:flex;flex-wrap:wrap;gap:6px}
.tags span{font-size:12px;color:var(--dim);border:1px solid var(--line);padding:3px 9px;border-radius:999px}
figure{margin:26px 0 0}
figure img{width:100%;height:auto;display:block;border:1px solid var(--line);border-radius:10px}
figcaption{margin-top:8px;font-size:12.5px;color:var(--dim)}
.facts{margin:26px 0 0;display:grid;gap:1px;background:var(--line);border:1px solid var(--line);
  border-radius:10px;overflow:hidden;grid-template-columns:repeat(auto-fit,minmax(150px,1fr))}
.facts div{background:var(--panel);padding:14px 16px}
.facts dt{font-size:11.5px;letter-spacing:.09em;text-transform:uppercase;color:var(--dim)}
.facts dd{margin:5px 0 0;font-size:19px}
.swatches{margin:26px 0 0;display:grid;gap:8px;grid-template-columns:repeat(auto-fill,minmax(132px,1fr))}
.sw-card{border:1px solid var(--line);border-radius:8px;overflow:hidden;background:var(--panel)}
.sw-chip{height:52px}
.sw-meta{padding:8px 10px;font-size:11.5px;line-height:1.45}
.sw-name{color:var(--ink);word-break:break-all}
.sw-num{color:var(--dim)}
.sw-num.under{color:#ff6b6b}
.sw-num.xmpt{color:#e8b04b}

.cmd{margin:26px 0 0;display:flex;gap:10px;align-items:stretch;flex-wrap:wrap}
.cmd code{flex:1 1 320px;background:var(--panel);border:1px solid var(--line);border-radius:8px;
  padding:13px 15px;font-size:13.5px;overflow-x:auto;white-space:pre}
.cmd button{border:1px solid var(--line);background:transparent;color:var(--dim);
  font:13px/1 var(--mono);padding:0 16px;border-radius:8px;cursor:pointer}
.cmd button:hover{color:var(--ink);border-color:var(--ink)}

/* --------------------------------------------------------- contributing */
.contrib{padding:56px 0}
.contrib h2{margin:0 0 10px;font-size:clamp(24px,4.6vw,40px)}
.contrib p{max-width:70ch;color:var(--dim)}
.contrib p strong{color:var(--ink);font-weight:400}
.steps{margin:30px 0 0;padding:0;list-style:none;counter-reset:step;
  display:grid;gap:14px;grid-template-columns:repeat(auto-fit,minmax(275px,1fr))}
.steps li{counter-increment:step;border:1px solid var(--line);border-radius:10px;
  background:var(--panel);padding:16px 17px}
.steps li::before{content:counter(step,decimal-leading-zero);display:block;
  font-size:11.5px;letter-spacing:.12em;color:var(--accent);margin-bottom:7px}
.steps h4{margin:0 0 6px;font-size:15px;font-weight:400;color:var(--ink)}
.steps p{margin:0;font-size:13.5px;color:var(--dim);line-height:1.55;max-width:none}
.steps code{font-size:12.5px;color:var(--ink)}
.rulebox{margin:30px 0 0;border-left:2px solid var(--accent);padding:2px 0 2px 17px}
.rulebox p{margin:0;color:var(--ink)}
.rulebox p + p{margin-top:10px;color:var(--dim)}

/* --------------------------------------------------------------- trust */
.trust{padding:56px 0}
.trust h2{margin:0 0 12px;font-size:clamp(22px,4vw,34px)}
.trust p{max-width:70ch;color:var(--dim)}
.trust pre{background:var(--panel);border:1px solid var(--line);border-radius:10px;
  padding:16px 18px;overflow-x:auto;font-size:13px;line-height:1.6;color:var(--ink)}
.claim{border-left:2px solid var(--accent);padding-left:17px;margin:22px 0;color:var(--ink)}

footer{border:0;padding:34px 0 64px;color:var(--dim);font-size:13.5px}
@media (prefers-reduced-motion:reduce){*{transition:none!important;scroll-behavior:auto}}
"""

JS = """
const THEMES = __DATA__;
const byId = Object.fromEntries(THEMES.map(t => [t.slug, t]));

function apply(slug){
  const t = byId[slug];
  if(!t) return;
  const c = t.colours, r = document.documentElement.style;
  r.setProperty('--bg', t.background);
  r.setProperty('--panel', c.lighter_background || c.dark_background || t.background);
  r.setProperty('--line', c.selection || c.muted || '#333');
  r.setProperty('--ink', c.foreground || '#eee');
  r.setProperty('--dim', c.dark_foreground || c.muted || '#999');
  r.setProperty('--accent', c.accent || c.cyan || '#8b7fff');
  r.setProperty('--accent-ink', t.background);
  document.querySelectorAll('.chip[data-slug]').forEach(b =>
    b.setAttribute('aria-pressed', String(b.dataset.slug === slug)));
}

document.querySelectorAll('.chip[data-slug]').forEach(b => {
  b.addEventListener('click', () => {
    apply(b.dataset.slug);
    document.getElementById(b.dataset.slug).scrollIntoView({block:'start'});
  });
});

// Reading about a theme paints the page in it. It is the only honest way to
// show a palette on a web page, and it is cheaper than six screenshots.
const seen = new IntersectionObserver(entries => {
  const top = entries.filter(e => e.isIntersecting)
                     .sort((a,b) => a.boundingClientRect.top - b.boundingClientRect.top)[0];
  if(top) apply(top.target.id);
}, {rootMargin:'-45% 0px -45% 0px'});
document.querySelectorAll('section.theme').forEach(s => seen.observe(s));

// Catalog filter. Nothing is removed from the DOM, so a filtered-out card is
// still findable by the browser's own search.
const cards = [...document.querySelectorAll('.card')];
document.querySelectorAll('[data-filter]').forEach(btn => {
  btn.addEventListener('click', () => {
    const tag = btn.dataset.filter;
    document.querySelectorAll('[data-filter]').forEach(b => b.classList.toggle('on', b === btn));
    cards.forEach(c => {
      c.hidden = tag !== '*' && !c.dataset.tags.split(' ').includes(tag);
    });
  });
});

document.querySelectorAll('[data-copy]').forEach(b => {
  b.addEventListener('click', async () => {
    const text = document.getElementById(b.dataset.copy).textContent;
    try { await navigator.clipboard.writeText(text); } catch(e){ return; }
    const was = b.textContent; b.textContent = 'copied';
    setTimeout(() => { b.textContent = was; }, 1400);
  });
});

if(THEMES.length) apply(THEMES[0].slug);
"""


def esc(value):
    return html.escape(str(value), quote=True)


REPO = "https://github.com/lubabs770/ritzpah"


def render_hero(themes):
    walls = sum(t["wallpapers"] for t in themes)
    slots = themes[0]["slots"] and len(themes[0]["slots"]) or 0
    shaders = sum(1 for t in themes if t["shader"])
    stats = [
        ("themes", len(themes)),
        ("wallpapers", walls),
        ("downloaded", 0),
        ("ink slots each", slots),
        ("shader themes", shaders),
    ]
    cells = "".join(f"<div><dt>{esc(k)}</dt><dd>{esc(v)}</dd></div>" for k, v in stats)
    return f"""<section class="hero"><div class="wrap">
<h1>RITZPAH<span class="dot">.</span></h1>
<p class="lede">Omarchy themes. <em>Loud ones.</em> Every wallpaper generated
from a script, never downloaded &mdash; and this page is wearing whichever
theme you are reading about.</p>
<dl class="stats">{cells}</dl>
<div class="cta">
<a class="btn primary" href="#catalog">Browse the catalog</a>
<a class="btn" href="#contributing">Add a theme</a>
<a class="btn" href="{REPO}">Source</a>
</div>
</div></section>"""


def render_rail(themes):
    chips = "".join(
        f'<button class="chip" data-slug="{esc(t["slug"])}" aria-pressed="false">'
        f'<span class="sw" style="background:{esc(t["colours"].get("accent", "#888"))}"></span>'
        f'{esc(t["name"])}</button>'
        for t in themes
    )
    return f"""<nav class="rail"><div class="wrap"><div class="rail-inner">
<a class="chip" href="#catalog">Catalog</a>
<a class="chip" href="#contributing">Contribute</a>
<span class="rail-sep"></span>{chips}
</div></div></nav>"""


def render_catalog(themes):
    tags = sorted({tag for t in themes for tag in t["tags"]})
    filters = '<span class="lbl">filter</span>' + \
        '<button class="chip on" data-filter="*">all</button>' + \
        "".join(f'<button class="chip" data-filter="{esc(tag)}">{esc(tag)}</button>' for tag in tags)

    cards = []
    for t in themes:
        strip = "".join(
            f'<i style="background:{esc(c)}"></i>'
            for c in [t["colours"].get(k) for k in
                      ("red", "orange", "yellow", "green", "cyan", "blue", "magenta", "accent")]
            if c
        )
        thumb = t["assets"].get("thumb") or t["assets"].get("preview")
        img = (f'<img loading="lazy" src="assets/{esc(thumb)}" alt="{esc(t["name"])}">'
               if thumb else "")
        worst = t["slots"][0]["ratio"] if t["slots"] else "-"
        meta = (f'<span>floor <b>{esc(t["floor"])}:1</b></span>'
                f'<span>worst <b>{esc(worst)}:1</b></span>'
                f'<span>walls <b>{esc(t["wallpapers"])}</b></span>'
                + ("<span><b>shader</b></span>" if t["shader"] else ""))
        cards.append(
            f'<a class="card" href="#{esc(t["slug"])}" data-tags="{esc(" ".join(t["tags"]))}">'
            f'{img}<div class="body"><h3>{esc(t["name"])}</h3>'
            f'<div class="strip">{strip}</div>'
            f'<p>{esc(t["tagline"])}</p>'
            f'<div class="meta">{meta}</div></div></a>')

    return f"""<section class="catalog" id="catalog"><div class="wrap">
<p class="eyebrow">The roster</p>
<h2>{len(themes)} themes, none of them subtle</h2>
<p class="note">Every number below was measured from that theme's
<code>colors.toml</code> when this page was built, not typed by hand. Pick one
to see its full palette, its wallpapers, and what it costs you.</p>
<div class="filters">{filters}</div>
<div class="grid">{"".join(cards)}</div>
</div></section>"""


def render_theme(theme):
    parts = [f'<section class="theme" id="{esc(theme["slug"])}"><div class="wrap">']
    parts.append(f'<h2>{esc(theme["name"])}</h2>')
    if theme["tagline"]:
        parts.append(f'<p class="tag">{esc(theme["tagline"])}</p>')
    if theme["tags"]:
        chips = "".join(f"<span>{esc(tag)}</span>" for tag in theme["tags"])
        parts.append(f'<p class="tags">{chips}</p>')

    if theme["assets"].get("preview"):
        parts.append(
            f'<figure><img loading="lazy" src="assets/{esc(theme["assets"]["preview"])}" '
            f'alt="{esc(theme["name"])} desktop preview">'
            f'<figcaption>Rendered, not screenshotted.</figcaption></figure>')

    worst = theme["slots"][0]["ratio"] if theme["slots"] else "-"
    facts = [
        ("contrast floor", f'{theme["floor"]}:1'),
        ("worst slot", f'{worst}:1'),
        ("ink slots", len(theme["slots"])),
        ("wallpapers", theme["wallpapers"]),
        ("shader", "yes" if theme["shader"] else "no"),
        ("battery", theme["battery"] or "normal"),
    ]
    parts.append('<dl class="facts">')
    for label, value in facts:
        parts.append(f"<div><dt>{esc(label)}</dt><dd>{esc(value)}</dd></div>")
    parts.append("</dl>")

    parts.append('<div class="swatches">')
    for entry in theme["slots"]:
        ratio, slot = entry["ratio"], entry["slot"]
        if slot in theme["exempt"]:
            css_class, note = "xmpt", "exempt"
        elif ratio < theme["floor"]:
            css_class, note = "under", "under floor"
        else:
            css_class, note = "", "ok"
        title = theme["exempt"].get(slot) or ""
        parts.append(
            f'<div class="sw-card"{f" title={json.dumps(title)}" if title else ""}>'
            f'<div class="sw-chip" style="background:{esc(entry["colour"])}"></div>'
            f'<div class="sw-meta"><div class="sw-name">{esc(slot)}</div>'
            f'<div class="sw-num {css_class}">{ratio}:1 &middot; {note}</div>'
            f'</div></div>')
    parts.append("</div>")

    if theme["notes"]:
        parts.append(f'<p class="tag" style="margin-top:22px">{esc(theme["notes"])}</p>')

    cmd_id = f'cmd-{esc(theme["slug"])}'
    command = (f'./ritzpah install {theme["slug"]}\n'
               f'omarchy theme set {theme["slug"]}')
    parts.append(
        f'<div class="cmd"><code id="{cmd_id}">{esc(command)}</code>'
        f'<button data-copy="{cmd_id}">copy</button></div>')

    if theme["assets"].get("sheet"):
        parts.append(
            f'<figure><img loading="lazy" src="assets/{esc(theme["assets"]["sheet"])}" '
            f'alt="{esc(theme["name"])} wallpapers">'
            f'<figcaption>All {theme["wallpapers"]} wallpapers. Generated, never downloaded.'
            f'</figcaption></figure>')

    parts.append("</div></section>")
    return "\n".join(parts)


STEPS = [
    ("Start with the palette",
     "<code>themes/&lt;lowercase-hyphen-name&gt;/colors.toml</code>. That one file is a "
     "complete working theme &mdash; Omarchy generates the terminal, btop, neovim, "
     "Chromium and shell configs from it. Look at it before you reach for anything else."),
    ("Declare what it is",
     "<code>theme.json</code>: name, tagline, tags, and the contrast floor you hold "
     "yourself to. Every field is optional and unknown keys are kept, not rejected &mdash; "
     "a schema that refuses weird is a schema that stops you building the good one."),
    ("Earn the floor",
     "<code>./ritzpah contrast &lt;name&gt;</code> measures every ink slot against the "
     "background. Fix the palette, or exempt the slot <em>with a reason</em>. Do not "
     "lower the floor to make the error go away."),
    ("Generate the wallpapers",
     "A <code>tools/make-backgrounds-&lt;name&gt;</code> script that builds its images "
     "from primitives, and <code>chmod +x</code> in the same commit. The recipe is the "
     "deliverable; the exact image never was. Then open them and actually look."),
    ("Record the prompt",
     "<code>PROMPT.md</code>, verbatim, typos and all, with the date. No cleaning it up "
     "afterwards to sound smarter than you were. A theme without its prompt is an orphan."),
    ("Pass the gate",
     "<code>./ritzpah validate &lt;name&gt;</code> until it is <code>[ok]</code>, or every "
     "warning left is one you can defend out loud. CI runs the same command on your pull "
     "request, and a theme that fails it never reaches this page."),
]


def render_contributing():
    steps = "".join(
        f"<li><h4>{title}</h4><p>{body}</p></li>" for title, body in STEPS)
    return f"""<section class="contrib" id="contributing"><div class="wrap">
<p class="eyebrow">Contributing</p>
<h2>Add a theme</h2>
<p>Nothing here is ever updated after it is merged. This is a roster of
one-shots, which makes the merge the only moment a theme can be made right
&mdash; so <strong>perfect it before you contribute it</strong>, and expect the
gate to be the strict part of an otherwise permissive repo.</p>
<ol class="steps">{steps}</ol>
<div class="rulebox">
<p>House rule: <strong>Ritzpah is allowed to be too much.</strong> If a theme is
tasteful, restrained, or honestly pretty usable for daily driving, it is in the
wrong repo. Turn something up.</p>
<p>Blueprint is the exception that proves it, and it is not a loophole. It holds
AAA where the rest of the repo sits on AA &mdash; but the excess did not go
missing, it went into the rigour instead of the look. If you are going to be
restrained here, be insufferable about it.</p>
</div>
<div class="cta">
<a class="btn primary" href="{REPO}/blob/main/THEME_JSON.md">The theme.json schema</a>
<a class="btn" href="{REPO}/blob/main/RITZPAH_SKILL.md">The full build guide</a>
<a class="btn" href="{REPO}/issues/new">Open an issue</a>
</div>
</div></section>"""


def render_trust():
    return f"""<section class="trust" id="trust"><div class="wrap">
<p class="eyebrow">Before you install anything</p>
<h2>Don't trust me</h2>
<p>This repo ships shell scripts that run on your machine and write into
<code>~/.config/omarchy/</code>. You have no reason to trust a stranger's theme
repo. So don't &mdash; ask your own agent:</p>
<pre id="audit">{esc(AUDIT_PROMPT)}</pre>
<div class="cmd"><button data-copy="audit">copy the audit prompt</button></div>
<p class="claim">To make that cheap: the only things that execute are
<code>ritzpah</code>, <code>install</code>, <code>tools/ritzpah-lib.py</code>,
<code>tools/ritzpah-site.py</code> and <code>tools/make-backgrounds-*</code>.
Everything else is TOML, Lua and images. Nothing in the repo makes a network
request, runs on a schedule, or runs at shell startup.</p>
<p>An audit covers the commit you audited. Run it again after a
<code>git pull</code>.</p>
</div></section>"""


def render(themes):
    data = json.dumps(themes, separators=(",", ":"))
    quickstart = ("git clone " + REPO + ".git\n"
                  "cd ritzpah && ./ritzpah list")
    return f"""<!doctype html>
<html lang="en"><head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Ritzpah &mdash; Omarchy themes. Loud ones.</title>
<meta name="description" content="A catalog of {len(themes)} Omarchy themes engineered to be seen from orbit. Every wallpaper generated from a script, never downloaded.">
<meta property="og:title" content="Ritzpah - Omarchy themes. Loud ones.">
<meta property="og:description" content="{len(themes)} Omarchy themes. Every wallpaper generated, never downloaded.">
<meta name="color-scheme" content="dark">
<style>{CSS}</style>
</head><body>

{render_hero(themes)}
{render_rail(themes)}
{render_catalog(themes)}
{"".join(render_theme(t) for t in themes)}
{render_contributing()}
{render_trust()}

<footer><div class="wrap">
<div class="cmd"><code id="quickstart">{esc(quickstart)}</code>
<button data-copy="quickstart">copy</button></div>
<p><a href="{REPO}">github.com/lubabs770/ritzpah</a>
&nbsp;&middot;&nbsp; MIT &nbsp;&middot;&nbsp; every contrast number on this page
was measured from <code>colors.toml</code> at build time, not typed by hand.</p>
</div></footer>

<script>{JS.replace("__DATA__", data)}</script>
</body></html>
"""


def build(repo, out):
    assets = os.path.join(out, "assets")
    if os.path.isdir(out):
        shutil.rmtree(out)
    os.makedirs(assets)

    themes = collect(repo, assets)
    with open(os.path.join(out, "index.html"), "w", encoding="utf-8") as handle:
        handle.write(render(themes))

    # Netlify serves this for unknown paths; without it a typo'd URL 404s ugly.
    shutil.copy2(os.path.join(out, "index.html"), os.path.join(out, "404.html"))

    total = sum(
        os.path.getsize(os.path.join(root, name))
        for root, _, names in os.walk(out) for name in names
    )
    print(f"built {out} - {len(themes)} themes, {total / 1024 / 1024:.1f} MB")
    print("CI publishes this to Pages on every push to main;")
    print("open it locally with: xdg-open " + os.path.join(out, "index.html"))
    return 0


if __name__ == "__main__":
    if len(sys.argv) < 3:
        print("usage: ritzpah-site.py <repo> <out-dir>", file=sys.stderr)
        raise SystemExit(2)
    raise SystemExit(build(sys.argv[1], sys.argv[2]))
