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
body{margin:0;background:var(--bg);color:var(--ink);
  font:16px/1.65 var(--mono);
  transition:background .45s ease,color .45s ease}
.wrap{max-width:1100px;margin:0 auto;padding:0 20px}
a{color:var(--accent)}

header.top{padding:56px 0 28px;border-bottom:1px solid var(--line)}
h1{margin:0;font-size:clamp(38px,9vw,84px);letter-spacing:-.04em;line-height:.95}
h1 .dot{color:var(--accent)}
.sub{margin:10px 0 0;color:var(--dim);font-size:clamp(15px,2.4vw,19px)}

nav.rail{position:sticky;top:0;z-index:5;background:var(--bg);
  border-bottom:1px solid var(--line);padding:12px 0;
  transition:background .45s ease}
.rail-inner{display:flex;gap:8px;overflow-x:auto;scrollbar-width:thin}
.chip{flex:0 0 auto;border:1px solid var(--line);background:transparent;color:var(--dim);
  font:13px/1 var(--mono);padding:9px 13px;border-radius:999px;cursor:pointer;
  white-space:nowrap;transition:all .2s ease}
.chip:hover{color:var(--ink);border-color:var(--ink)}
.chip[aria-pressed="true"]{background:var(--accent);color:var(--accent-ink);border-color:var(--accent)}
.chip .sw{display:inline-block;width:8px;height:8px;border-radius:50%;margin-right:7px;vertical-align:1px}

section.theme{padding:52px 0;border-bottom:1px solid var(--line)}
.theme h2{margin:0;font-size:clamp(26px,5vw,44px);letter-spacing:-.02em}
.theme .tag{margin:8px 0 0;color:var(--dim);max-width:62ch}
.tags{margin:14px 0 0;display:flex;flex-wrap:wrap;gap:6px}
.tags span{font-size:12px;color:var(--dim);border:1px solid var(--line);
  padding:3px 9px;border-radius:999px}

figure{margin:26px 0 0}
figure img{width:100%;height:auto;display:block;border:1px solid var(--line);border-radius:10px}
figcaption{margin-top:8px;font-size:12.5px;color:var(--dim)}

.facts{margin:26px 0 0;display:grid;gap:1px;background:var(--line);
  border:1px solid var(--line);border-radius:10px;overflow:hidden;
  grid-template-columns:repeat(auto-fit,minmax(150px,1fr))}
.facts div{background:var(--panel);padding:14px 16px}
.facts dt{font-size:11.5px;letter-spacing:.09em;text-transform:uppercase;color:var(--dim)}
.facts dd{margin:5px 0 0;font-size:19px}

.swatches{margin:26px 0 0;display:grid;gap:8px;
  grid-template-columns:repeat(auto-fill,minmax(132px,1fr))}
.sw-card{border:1px solid var(--line);border-radius:8px;overflow:hidden;background:var(--panel)}
.sw-chip{height:52px}
.sw-meta{padding:8px 10px;font-size:11.5px;line-height:1.45}
.sw-name{color:var(--ink);word-break:break-all}
.sw-num{color:var(--dim)}
.sw-num.under{color:#ff6b6b}
.sw-num.xmpt{color:#e8b04b}

.cmd{margin:26px 0 0;display:flex;gap:10px;align-items:stretch;flex-wrap:wrap}
.cmd code{flex:1 1 320px;background:var(--panel);border:1px solid var(--line);
  border-radius:8px;padding:13px 15px;font-size:13.5px;overflow-x:auto;white-space:pre}
.cmd button{border:1px solid var(--line);background:transparent;color:var(--dim);
  font:13px/1 var(--mono);padding:0 16px;border-radius:8px;cursor:pointer}
.cmd button:hover{color:var(--ink);border-color:var(--ink)}

.trust{padding:52px 0}
.trust h2{margin:0 0 12px;font-size:clamp(22px,4vw,34px)}
.trust p{max-width:70ch;color:var(--dim)}
.trust pre{background:var(--panel);border:1px solid var(--line);border-radius:10px;
  padding:16px 18px;overflow-x:auto;font-size:13px;line-height:1.6;color:var(--ink)}
.claim{border-left:2px solid var(--accent);padding-left:16px;margin:22px 0;color:var(--ink)}

footer{padding:34px 0 60px;color:var(--dim);font-size:13.5px;border-top:1px solid var(--line)}
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
  document.querySelectorAll('.chip').forEach(b =>
    b.setAttribute('aria-pressed', String(b.dataset.slug === slug)));
}

document.querySelectorAll('.chip').forEach(b => {
  b.addEventListener('click', () => {
    apply(b.dataset.slug);
    document.getElementById(b.dataset.slug).scrollIntoView({block:'start'});
  });
});

// Scrolling through the page repaints it in whichever theme you are reading
// about, which is the only honest way to show a palette on a web page.
const seen = new IntersectionObserver(entries => {
  const top = entries.filter(e => e.isIntersecting)
                     .sort((a,b) => a.boundingClientRect.top - b.boundingClientRect.top)[0];
  if(top) apply(top.target.id);
}, {rootMargin:'-45% 0px -45% 0px'});
document.querySelectorAll('section.theme').forEach(s => seen.observe(s));

document.querySelectorAll('[data-copy]').forEach(b => {
  b.addEventListener('click', async () => {
    const text = document.getElementById(b.dataset.copy).textContent;
    try { await navigator.clipboard.writeText(text); }
    catch(e){ return; }
    const was = b.textContent; b.textContent = 'copied';
    setTimeout(() => { b.textContent = was; }, 1400);
  });
});

if(THEMES.length) apply(THEMES[0].slug);
"""


def esc(value):
    return html.escape(str(value), quote=True)


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


def render(themes):
    chips = "".join(
        f'<button class="chip" data-slug="{esc(t["slug"])}" aria-pressed="false">'
        f'<span class="sw" style="background:{esc(t["colours"].get("accent", "#888"))}"></span>'
        f'{esc(t["name"])}</button>'
        for t in themes
    )
    data = json.dumps(themes, separators=(",", ":"))
    return f"""<!doctype html>
<html lang="en"><head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Ritzpah — Omarchy themes. Loud ones.</title>
<meta name="description" content="A collection of {len(themes)} Omarchy themes engineered to be seen from orbit. Every wallpaper generated, never downloaded.">
<style>{CSS}</style>
</head><body>

<header class="top"><div class="wrap">
<h1>RITZPAH<span class="dot">.</span></h1>
<p class="sub">Omarchy themes. Loud ones. {len(themes)} of them, and this page
is wearing whichever one you are reading about.</p>
</div></header>

<nav class="rail"><div class="wrap"><div class="rail-inner">{chips}</div></div></nav>

{"".join(render_theme(t) for t in themes)}

<section class="trust"><div class="wrap">
<h2>Don't trust me</h2>
<p>This repo ships shell scripts that run on your machine and write into
<code>~/.config/omarchy/</code>. You have no reason to trust a stranger's theme
repo. So don't &mdash; ask your own agent, before you install anything:</p>
<pre id="audit">{esc(AUDIT_PROMPT)}</pre>
<div class="cmd"><button data-copy="audit">copy the audit prompt</button></div>
<p class="claim">To make that cheap: the only things that execute are
<code>ritzpah</code>, <code>install</code>, <code>tools/ritzpah-lib.py</code>,
<code>tools/ritzpah-site.py</code> and <code>tools/make-backgrounds-*</code>.
Everything else is TOML, Lua and images. Nothing in the repo makes a network
request, runs on a schedule, or runs at shell startup.</p>
<p>An audit covers the commit you audited. Run it again after a <code>git
pull</code>.</p>
</div></section>

<footer><div class="wrap">
<a href="https://github.com/lubabs770/ritzpah">github.com/lubabs770/ritzpah</a>
&nbsp;&middot;&nbsp; MIT &nbsp;&middot;&nbsp; every contrast number on this page
was measured from <code>colors.toml</code>, not typed by hand
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
