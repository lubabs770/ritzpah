#!/usr/bin/env python3
"""Build the Ritzpah roster site: a folder you can drag onto Netlify Drop.

Reads themes/<slug>/theme.json + colors.toml and writes a self-contained static
site. The page has no external requests -- no CDN, no webfont, no analytics --
so the whole thing is one HTML file plus images.

This is the one script in the repo that writes outside the repo, and only to the
output directory it is given.
"""

import html
import re
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
            "generator": declared.get("generator", ""),
            "wallpapers": len(info["wallpapers"]),
            "sections": len(info["shell_sections"]),
            "background": report["background"],
            "slots": report["slots"],
            "colours": {k: v for k, v in colours.items()
                        if isinstance(v, str) and lib.HEX.match(v)},
            "assets": assets_for_theme,
        })
    return themes



REPO = "https://github.com/lubabs770/ritzpah"

# GitHub's own mark, inlined. An <img> would be a request to a third-party host,
# and this site does not make any.
GITHUB_MARK = (
    '<svg viewBox="0 0 16 16" aria-hidden="true" focusable="false"><path d="M8 0C3.58 0'
    ' 0 3.58 0 8c0 3.54 2.29 6.53 5.47 7.59.4.07.55-.17.55-.38 0-.19-.01-.82-.01-1.49-2.01'
    '.37-2.53-.49-2.69-.94-.09-.23-.48-.94-.82-1.13-.28-.15-.68-.52-.01-.53.63-.01 1.08.58'
    ' 1.23.82.72 1.21 1.87.87 2.33.66.07-.52.28-.87.51-1.07-1.78-.2-3.64-.89-3.64-3.95 0-.87'
    '.31-1.59.82-2.15-.08-.2-.36-1.02.08-2.12 0 0 .67-.21 2.2.82.64-.18 1.32-.27 2-.27.68 0'
    ' 1.36.09 2 .27 1.53-1.04 2.2-.82 2.2-.82.44 1.1.16 1.92.08 2.12.51.56.82 1.27.82 2.15 0'
    ' 3.07-1.87 3.75-3.65 3.95.29.25.54.73.54 1.48 0 1.07-.01 1.93-.01 2.2 0 .21.15.46.55.38A8.012'
    ' 8.012 0 0 0 16 8c0-4.42-3.58-8-8-8z"/></svg>')

# Disclosed on the page itself, so a reader can judge the scan rather than trust
# it. Deliberately broad: it over-matches (a URL in a comment counts) rather than
# risking a miss, and every hit is shown with its line.
NETWORK_PATTERN = re.compile(
    r"\b(curl|wget|nc|ssh|scp|rsync|ftp|urllib|requests\.|http\.client|socket\.|"
    r"fetch\(|XMLHttpRequest|https?://)", re.I)

SKIP_DIRS = {".git", "site", "node_modules", "__pycache__"}
DATA_SUFFIXES = {".toml", ".lua", ".json", ".md", ".png", ".jpg", ".jpeg", ".webp",
                 ".theme", ".conf", ".frag", ".txt", ".yml", ".yaml", ""}


def repo_commit(repo):
    try:
        out = subprocess.run(["git", "-C", repo, "rev-parse", "--short", "HEAD"],
                             capture_output=True, text=True, check=True)
        return out.stdout.strip()
    except (FileNotFoundError, subprocess.CalledProcessError):
        return ""


def audit_surface(repo):
    """Everything in the repo that can execute, found rather than remembered.

    A file counts as executable if the filesystem says so or it opens with a
    shebang. Each one is then scanned for anything that looks like it reaches
    the network, and the hits are reported verbatim -- including the false
    positives, because hiding them would defeat the point.
    """
    executables = []
    for root, dirs, names in os.walk(repo):
        dirs[:] = [d for d in dirs if d not in SKIP_DIRS]
        for name in sorted(names):
            path = os.path.join(root, name)
            rel = os.path.relpath(path, repo)
            executable = os.access(path, os.X_OK) and os.path.isfile(path)
            shebang = False
            text = ""
            try:
                with open(path, "r", encoding="utf-8") as handle:
                    text = handle.read()
                shebang = text.startswith("#!")
            except (OSError, UnicodeDecodeError):
                text = ""
            if not (executable or shebang):
                continue
            if os.path.splitext(name)[1] in {".png", ".jpg", ".jpeg", ".webp"}:
                continue
            hits = []
            for number, line in enumerate(text.splitlines(), 1):
                if NETWORK_PATTERN.search(line):
                    stripped = line.strip()
                    hits.append((number, stripped[:150]))
            executables.append({"path": rel, "exec_bit": executable,
                                "shebang": shebang, "hits": hits})
    executables.sort(key=lambda e: e["path"])
    return executables


AUDIT_PROMPT = """Audit this repo before I install it: https://github.com/lubabs770/ritzpah
Clone it somewhere temporary and actually read it. Tell me:
- what executes, and when - install time, every shell start, on a timer?
- does anything touch the network, and where does it connect?
- does it write anywhere outside ~/.config/omarchy/themes?
- does it read anything it has no business reading - keys, tokens, shell history?
- anything obfuscated: base64, eval, curl piped into a shell?
Quote the exact lines for anything you flag. If it's clean, say so plainly."""


def esc(value):
    return html.escape(str(value), quote=True)


# --------------------------------------------------------------- stylesheet

CSS = """
/* Neutral shell. Theme pages override these six tokens inline, so the page a
   theme lives on is drawn in that theme and nothing else has to change. */
:root{
  --bg:#0b0b0f; --panel:#131318; --line:#242430; --ink:#eaeaf2;
  --dim:#9494a6; --accent:#7c6cff; --accent-ink:#0b0b0f;
  --sans:system-ui,-apple-system,"Segoe UI",Roboto,Helvetica,Arial,sans-serif;
  --mono:ui-monospace,"JetBrainsMono Nerd Font",SFMono-Regular,Menlo,Consolas,monospace;
  --rad:12px; --pad:clamp(20px,5vw,32px);
}
*,*::before,*::after{box-sizing:border-box}
html{scroll-behavior:smooth}
body{margin:0;background:var(--bg);color:var(--ink);font:16px/1.65 var(--sans);
  -webkit-font-smoothing:antialiased}
img{max-width:100%;height:auto;display:block}
a{color:inherit}
h1,h2,h3{letter-spacing:-.025em;line-height:1.1;margin:0}
.wrap{width:100%;max-width:1160px;margin:0 auto;padding:0 var(--pad)}
.eyebrow{font:500 12px/1 var(--mono);letter-spacing:.14em;text-transform:uppercase;
  color:var(--accent);margin:0 0 14px}
.lede{color:var(--dim);font-size:clamp(16px,2vw,19px);max-width:60ch}

/* ------------------------------------------------------------------- nav */
.nav{position:sticky;top:0;z-index:20;background:color-mix(in srgb,var(--bg) 88%,transparent);
  backdrop-filter:blur(12px);border-bottom:1px solid var(--line)}
.nav-in{display:flex;align-items:center;gap:26px;height:62px}
.brand{font:600 18px/1 var(--mono);letter-spacing:-.02em;text-decoration:none;
  display:flex;align-items:center;gap:2px}
.brand i{color:var(--accent);font-style:normal}
.nav-links{display:flex;gap:22px;margin-left:auto;align-items:center}
.nav-links a{font-size:14.5px;color:var(--dim);text-decoration:none;transition:color .15s;
  display:inline-flex;align-items:center}
.nav-links a:hover,.nav-links a[aria-current]{color:var(--ink)}
.nav-links a svg{width:20px;height:20px;fill:currentColor;display:block}
@media(max-width:640px){.nav-links a.hide-sm{display:none}}

/* ----------------------------------------------------------------- button */
.btn{display:inline-flex;align-items:center;gap:8px;border:1px solid var(--line);
  border-radius:9px;padding:11px 18px;font-size:14.5px;font-weight:500;
  text-decoration:none;color:var(--ink);background:transparent;cursor:pointer;
  font-family:inherit;transition:border-color .16s,background .16s,transform .16s}
.btn:hover{border-color:var(--ink);transform:translateY(-1px)}
.btn.primary{background:var(--accent);border-color:var(--accent);color:var(--accent-ink)}
.btn.primary:hover{filter:brightness(1.1)}
.btn.sm{padding:8px 14px;font-size:13.5px}

/* ------------------------------------------------------------------ hero */
.hero{padding:clamp(64px,11vw,116px) 0 clamp(48px,7vw,76px)}
.hero-grid{max-width:none}
.hero h1{font-size:clamp(42px,7vw,78px);max-width:15ch}
.hero h1 i{color:var(--accent);font-style:normal}
.hero .lede{margin:22px 0 0;max-width:58ch}
.hero .actions{margin:30px 0 0;display:flex;gap:11px;flex-wrap:wrap}
/* ------------------------------------------------------------------ band */
.band{border-top:1px solid var(--line);border-bottom:1px solid var(--line);
  background:var(--panel)}
.band-in{display:grid;grid-template-columns:repeat(auto-fit,minmax(150px,1fr))}
.band-in div{padding:24px var(--pad);border-right:1px solid var(--line)}
.band-in div:last-child{border-right:0}
.band dt{font:500 11.5px/1 var(--mono);letter-spacing:.11em;text-transform:uppercase;color:var(--dim)}
.band dd{margin:8px 0 0;font-size:clamp(24px,3.4vw,32px);letter-spacing:-.03em}

/* --------------------------------------------------------------- sections */
.sec{padding:clamp(56px,8vw,92px) 0}
.sec + .sec{border-top:1px solid var(--line)}
.sec-head{max-width:64ch;margin:0 0 clamp(30px,4vw,44px)}
.sec-head h2{font-size:clamp(27px,4vw,40px)}
.sec-head p{margin:14px 0 0;color:var(--dim)}
.sec-head.row{max-width:none;display:flex;align-items:flex-end;justify-content:space-between;gap:20px;flex-wrap:wrap}

/* --------------------------------------------------------------- features */
.feats{display:grid;gap:18px;grid-template-columns:repeat(auto-fit,minmax(260px,1fr))}
.feat{border:1px solid var(--line);border-radius:var(--rad);padding:24px;background:var(--panel)}
.feat h3{font-size:17.5px;margin:0 0 9px}
.feat p{margin:0;color:var(--dim);font-size:14.5px;line-height:1.6}
.feat .ico{font:600 13px/1 var(--mono);color:var(--accent);margin-bottom:15px;display:block}

/* ----------------------------------------------------------------- cards */
.cards{list-style:none;margin:0;padding:0;display:grid;gap:18px;
  grid-template-columns:repeat(auto-fill,minmax(310px,1fr))}
.card{border:1px solid var(--line);border-radius:var(--rad);overflow:hidden;
  background:var(--panel);transition:border-color .16s,transform .16s}
.card:hover{border-color:var(--accent);transform:translateY(-3px)}
.card a{text-decoration:none;display:flex;flex-direction:column;height:100%}
.card .shot{aspect-ratio:16/9;object-fit:cover;object-position:top left;width:100%;border-bottom:1px solid var(--line)}
.card .body{padding:17px 18px 19px;display:flex;flex-direction:column;gap:11px;flex:1}
.card h3{font-size:18.5px}
.card .desc{margin:0;color:var(--dim);font-size:14px;line-height:1.55;flex:1}
.strip{display:flex;height:8px;border-radius:99px;overflow:hidden}
.strip i{flex:1}
.card .meta{display:flex;gap:14px;flex-wrap:wrap;font:12.5px/1 var(--mono);color:var(--dim)}
.card .meta b{font-weight:400;color:var(--ink)}
.card[hidden]{display:none}

/* --------------------------------------------------------------- filters */
.filters{display:flex;flex-wrap:wrap;gap:8px;margin:0 0 26px;align-items:center}
.filters .lbl{font:500 11.5px/1 var(--mono);letter-spacing:.11em;text-transform:uppercase;
  color:var(--dim);margin-right:5px}
.pill{border:1px solid var(--line);background:transparent;color:var(--dim);
  font:13.5px/1 var(--sans);padding:8px 14px;border-radius:99px;cursor:pointer;
  transition:all .16s}
.pill:hover{color:var(--ink);border-color:var(--ink)}
.pill.on{background:var(--accent);border-color:var(--accent);color:var(--accent-ink)}

/* ------------------------------------------------------------ theme page */
.t-hero{padding:clamp(40px,6vw,64px) 0 0}
.crumb{font:13.5px/1 var(--mono);color:var(--dim);text-decoration:none;
  display:inline-flex;gap:7px;margin-bottom:24px}
.crumb:hover{color:var(--ink)}
.t-hero h1{font-size:clamp(36px,6vw,58px)}
.t-hero .lede{margin:16px 0 0}
.tags{display:flex;flex-wrap:wrap;gap:7px;margin:20px 0 0}
.tags span{font:12.5px/1 var(--mono);color:var(--dim);border:1px solid var(--line);
  padding:6px 11px;border-radius:99px}
.t-shot{margin:clamp(30px,4vw,44px) 0 0;border:1px solid var(--line);
  border-radius:var(--rad);overflow:hidden}
.t-shot img{width:100%}
.t-shot figcaption{border-top:1px solid var(--line);background:var(--panel);
  padding:12px 16px;font:13px/1.4 var(--mono);color:var(--dim)}
.facts{margin:0;display:grid;gap:1px;background:var(--line);border:1px solid var(--line);
  border-radius:var(--rad);overflow:hidden;grid-template-columns:repeat(auto-fit,minmax(148px,1fr))}
.facts div{background:var(--panel);padding:17px 18px}
.facts dt{font:500 11.5px/1 var(--mono);letter-spacing:.1em;text-transform:uppercase;color:var(--dim)}
.facts dd{margin:7px 0 0;font-size:21px;letter-spacing:-.02em}
.swatches{display:grid;gap:9px;grid-template-columns:repeat(auto-fill,minmax(136px,1fr))}
.sw{border:1px solid var(--line);border-radius:9px;overflow:hidden;background:var(--panel)}
.sw .chip{height:56px}
.sw .m{padding:9px 11px;font:11.5px/1.5 var(--mono)}
.sw .n{color:var(--ink);word-break:break-all}
.sw .r{color:var(--dim)}
.sw .r.under{color:#ff6b6b}
.sw .r.xmpt{color:#e8b04b}
.pager{display:flex;justify-content:space-between;gap:14px;flex-wrap:wrap;
  border-top:1px solid var(--line);padding:28px 0 0;margin-top:8px}
.pager a{font:14px/1.4 var(--mono);color:var(--dim);text-decoration:none;max-width:46%}
.pager a:hover{color:var(--ink)}
.pager a b{display:block;color:var(--ink);font-weight:500;margin-top:5px;font-size:16px}

/* ------------------------------------------------------------------ code */
.cmd{display:flex;gap:10px;align-items:stretch;flex-wrap:wrap}
.cmd pre{flex:1 1 300px;margin:0;background:var(--panel);border:1px solid var(--line);
  border-radius:9px;padding:15px 17px;font:13.5px/1.7 var(--mono);overflow-x:auto}
.cmd .btn{flex:0 0 auto}
code{font-family:var(--mono);font-size:.93em}
.steps{list-style:none;counter-reset:s;margin:0;padding:0;display:grid;gap:16px;
  grid-template-columns:repeat(auto-fit,minmax(270px,1fr))}
.steps li{counter-increment:s;border:1px solid var(--line);border-radius:var(--rad);
  padding:22px;background:var(--panel)}
.steps li::before{content:counter(s,decimal-leading-zero);display:block;
  font:600 12px/1 var(--mono);color:var(--accent);margin-bottom:12px;letter-spacing:.1em}
.steps h3{font-size:16.5px;margin:0 0 8px}
.steps p{margin:0;color:var(--dim);font-size:14px;line-height:1.6}
.note-box{border-left:2px solid var(--accent);padding:4px 0 4px 18px;margin:0}
.note-box p{margin:0;max-width:68ch}
.note-box p + p{margin-top:11px;color:var(--dim)}

/* --------------------------------------------------------------- surface */
.tablewrap{overflow-x:auto;border:1px solid var(--line);border-radius:var(--rad);
  margin-top:22px;background:var(--panel)}
table.surface{border-collapse:collapse;width:100%;min-width:560px;font-size:14px}
table.surface th{text-align:left;font:500 11.5px/1 var(--mono);letter-spacing:.1em;
  text-transform:uppercase;color:var(--dim);padding:14px 16px;
  border-bottom:1px solid var(--line);white-space:nowrap}
table.surface td{padding:13px 16px;border-bottom:1px solid var(--line);vertical-align:top}
table.surface tr:last-child td{border-bottom:0}
table.surface .dimcell{color:var(--dim);white-space:nowrap}
table.surface .ok{color:var(--dim)}
table.surface details summary{cursor:pointer;color:var(--accent)}
table.surface details ul{margin:10px 0 0;padding-left:18px;display:grid;gap:7px}
table.surface details li{font:12.5px/1.5 var(--mono);color:var(--dim);word-break:break-word}
.scanline{margin:14px 0 0;font-size:13px;color:var(--dim);word-break:break-all}

/* ---------------------------------------------------------------- footer */
footer{border-top:1px solid var(--line);padding:52px 0 64px;background:var(--panel)}
.f-grid{display:grid;gap:32px;grid-template-columns:repeat(auto-fit,minmax(170px,1fr))}
.f-grid h4{margin:0 0 13px;font:500 11.5px/1 var(--mono);letter-spacing:.11em;
  text-transform:uppercase;color:var(--dim)}
.f-grid ul{list-style:none;margin:0;padding:0;display:grid;gap:9px}
.f-grid a{font-size:14.5px;color:var(--dim);text-decoration:none}
.f-grid a:hover{color:var(--ink)}
.f-base{margin-top:44px;padding-top:24px;border-top:1px solid var(--line);
  display:flex;justify-content:space-between;gap:16px;flex-wrap:wrap;
  font-size:13.5px;color:var(--dim)}
@media(prefers-reduced-motion:reduce){*{transition:none!important;scroll-behavior:auto}}
"""

JS = """
// Catalog filter. Cards are hidden, never removed, so find-in-page still works.
const cards = [...document.querySelectorAll('.card')];
document.querySelectorAll('[data-filter]').forEach(btn => {
  btn.addEventListener('click', () => {
    const tag = btn.dataset.filter;
    document.querySelectorAll('[data-filter]').forEach(b => b.classList.toggle('on', b === btn));
    cards.forEach(c => { c.hidden = tag !== '*' && !c.dataset.tags.split(' ').includes(tag); });
  });
});

document.querySelectorAll('[data-copy]').forEach(b => {
  b.addEventListener('click', async () => {
    const text = document.getElementById(b.dataset.copy).textContent;
    try { await navigator.clipboard.writeText(text); } catch (e) { return; }
    const was = b.textContent; b.textContent = 'Copied';
    setTimeout(() => { b.textContent = was; }, 1400);
  });
});
"""


# ------------------------------------------------------------------ chrome

def palette_vars(theme):
    """The six tokens that make a page wear a theme."""
    c = theme["colours"]
    return ";".join([
        f'--bg:{theme["background"]}',
        f'--panel:{c.get("lighter_background") or c.get("dark_background") or theme["background"]}',
        f'--line:{c.get("selection") or c.get("muted") or "#333"}',
        f'--ink:{c.get("foreground") or "#eee"}',
        f'--dim:{c.get("dark_foreground") or c.get("muted") or "#999"}',
        f'--accent:{c.get("accent") or c.get("cyan") or "#7c6cff"}',
        f'--accent-ink:{theme["background"]}',
    ])


def nav(active, depth=0):
    up = "../" * depth
    def link(href, label, key, small=False):
        cur = ' aria-current="page"' if key == active else ""
        cls = ' class="hide-sm"' if small else ""
        return f'<a href="{up}{href}"{cur}{cls}>{label}</a>'
    return f"""<nav class="nav"><div class="wrap nav-in">
<a class="brand" href="{up}index.html">ritzpah<i>.</i></a>
<div class="nav-links">
{link("catalog.html", "Themes", "catalog")}
{link("contributing.html", "Contribute", "contributing")}
{link("contributing.html#trust", "Security", "trust", True)}
<a href="{REPO}" aria-label="Ritzpah on GitHub" title="Source on GitHub">{GITHUB_MARK}</a>
<a class="btn primary sm" href="{up}catalog.html">Browse</a>
</div></div></nav>"""


def footer(themes, depth=0):
    up = "../" * depth
    theme_links = "".join(
        f'<li><a href="{up}themes/{t["slug"]}.html">{esc(t["name"])}</a></li>' for t in themes)
    return f"""<footer><div class="wrap">
<div class="f-grid">
<div><h4>Ritzpah</h4><ul>
<li><a href="{up}index.html">Home</a></li>
<li><a href="{up}catalog.html">All themes</a></li>
<li><a href="{up}contributing.html">Contribute</a></li>
<li><a href="{up}contributing.html#trust">Security</a></li>
</ul></div>
<div><h4>Themes</h4><ul>{theme_links}</ul></div>
<div><h4>Source</h4><ul>
<li><a href="{REPO}">Repository</a></li>
<li><a href="{REPO}/blob/main/THEME_JSON.md">theme.json schema</a></li>
<li><a href="{REPO}/blob/main/RITZPAH_SKILL.md">Build guide</a></li>
<li><a href="{REPO}/issues/new">Open an issue</a></li>
</ul></div>
</div>
<div class="f-base"><span>MIT. Built for Omarchy.</span>
<span>Every contrast figure measured from <code>colors.toml</code> at build time.</span></div>
</div></footer>"""


def page(title, description, body, active, depth=0, palette=""):
    up = "../" * depth
    style = f' style="{palette}"' if palette else ""
    return f"""<!doctype html>
<html lang="en"{style}><head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>{esc(title)}</title>
<meta name="description" content="{esc(description)}">
<meta property="og:title" content="{esc(title)}">
<meta property="og:description" content="{esc(description)}">
<meta name="color-scheme" content="dark">
<link rel="stylesheet" href="{up}assets/site.css">
</head><body>
{nav(active, depth)}
{body}
<script src="{up}assets/site.js" defer></script>
</body></html>
"""


# ------------------------------------------------------------ page bodies

def card(theme, depth=0):
    up = "../" * depth
    strip = "".join(
        f'<i style="background:{esc(c)}"></i>'
        for c in [theme["colours"].get(k) for k in
                  ("red", "orange", "yellow", "green", "cyan", "blue", "magenta", "accent")]
        if c)
    thumb = theme["assets"].get("thumb") or theme["assets"].get("preview")
    img = (f'<img class="shot" loading="lazy" src="{up}assets/{esc(thumb)}" '
           f'alt="{esc(theme["name"])} desktop">' if thumb else "")
    worst = theme["slots"][0]["ratio"] if theme["slots"] else "-"
    meta = (f'<span>floor <b>{esc(theme["floor"])}:1</b></span>'
            f'<span>worst <b>{esc(worst)}:1</b></span>'
            f'<span>walls <b>{esc(theme["wallpapers"])}</b></span>'
            + ("<span><b>shader</b></span>" if theme["shader"] else ""))
    return (f'<li class="card" data-tags="{esc(" ".join(theme["tags"]))}">'
            f'<a href="{up}themes/{esc(theme["slug"])}.html">{img}'
            f'<div class="body"><h3>{esc(theme["name"])}</h3>'
            f'<div class="strip">{strip}</div>'
            f'<p class="desc">{esc(theme["tagline"])}</p>'
            f'<div class="meta">{meta}</div></div></a></li>')


FEATURES = [
    ("01", "The recipe ships, not just the picture",
     "Every wallpaper comes with the script that drew it. Run it again and you get a fresh "
     "set in the same palette, at whatever size your screen actually is."),
    ("02", "Loud, but you can still read it",
     "Every theme says how readable it promises to be, and that promise is checked before "
     "it ships. Where a colour sits below the line it says so on its own page, and says why."),
    ("03", "It is just files in a folder",
     "Installing copies a directory into Omarchy's themes folder. No symlinks, no background "
     "process, nothing running inside your shell. Delete the folder and it is gone."),
]


def render_landing(themes):
    lead = next((t for t in themes if t["slug"] == "blueprint"), themes[0])
    walls = sum(t["wallpapers"] for t in themes)
    stats = [("Themes", len(themes)), ("Wallpapers", walls),
             ("Generators", sum(1 for t in themes if t["generator"])),
             ("Ink slots each", len(themes[0]["slots"])),
             ("Shader themes", sum(1 for t in themes if t["shader"]))]
    band = "".join(f"<div><dt>{esc(k)}</dt><dd>{esc(v)}</dd></div>" for k, v in stats)
    feats = "".join(
        f'<div class="feat"><span class="ico">{n}</span><h3>{esc(t)}</h3><p>{esc(b)}</p></div>'
        for n, t, b in FEATURES)
    body = f"""
<header class="hero"><div class="wrap"><div class="hero-grid">
<p class="eyebrow">Omarchy theme collection</p>
<h1>Desktop themes that are not trying to be tasteful<i>.</i></h1>
<p class="lede">{len(themes)} themes for Omarchy, each one built to be seen from across
the room. Wallpapers that ship with the script that drew them, contrast you can
check, and an install that just copies files.</p>
<div class="actions">
<a class="btn primary" href="catalog.html">Browse {len(themes)} themes</a>
<a class="btn" href="#install">How to install</a>
<a class="btn" href="contributing.html">Create your own</a>
</div>
</div></div></header>

<div class="band"><div class="band-in">{band}</div></div>

<section class="sec"><div class="wrap">
<div class="sec-head"><p class="eyebrow">Why this exists</p>
<h2>Loud, but not careless</h2>
<p>A theme being obnoxious on purpose is not an excuse for it to be sloppy
underneath. These are the three rules the whole collection is held to.</p></div>
<div class="feats">{feats}</div>
</div></section>

<section class="sec" id="install"><div class="wrap">
<div class="sec-head"><p class="eyebrow">Getting started</p>
<h2>Clone it, wear it, then make your own</h2>
<p>Omarchy's own <code>omarchy theme install</code> expects one repository per
theme, so this collection ships its own small CLI instead.</p></div>
<ol class="steps">
<li><h3>Clone it</h3><p>The repository is the source of truth. Nothing is fetched
at runtime and nothing phones home.</p></li>
<li><h3>Pick a theme</h3><p><code>./ritzpah list</code> prints the roster with
its measured contrast. <code>./ritzpah install &lt;name&gt;</code> copies one in.</p></li>
<li><h3>Switch to it</h3><p><code>omarchy theme set &lt;name&gt;</code>. Installing
never switches on its own, so stocking the shelf cannot change your desktop.</p></li>
<li><h3>Make one</h3><p>Write a <code>colors.toml</code>, declare it in
<code>theme.json</code>, earn your contrast floor, and let a script draw the
wallpapers. <a href="contributing.html">The guide</a> is six steps long.</p></li>
<li><h3>Roulette it</h3><p><em>Not built yet.</em> Deal a palette, a
<code>hyprland.lua</code>, a wallpaper and shell sections from different themes
at random, and install the chimera as a real theme called Roulette.
<code>--seed</code> reproduces a disaster worth keeping.</p></li>
</ol>
<div class="cmd" style="margin-top:24px">
<pre id="quick">git clone {REPO}.git
cd ritzpah &amp;&amp; ./ritzpah list
./ritzpah install blueprint --set</pre>
<button class="btn" data-copy="quick">Copy</button>
</div>
</div></section>

<section class="sec"><div class="wrap">
<div class="sec-head"><p class="eyebrow">Contributing</p>
<h2>Add your own</h2>
<p>Nothing here is ever updated after it is merged, which makes the merge the
only moment a theme can be made right. The gate is strict; everything else is
not.</p></div>
<div class="actions" style="display:flex;gap:11px;flex-wrap:wrap">
<a class="btn primary" href="contributing.html">Read the guide</a>
<a class="btn" href="contributing.html#trust">Audit this repo first</a>
</div>
</div></section>
"""
    return page("Ritzpah — Omarchy themes. Loud ones.",
                f"{len(themes)} Omarchy desktop themes with generated wallpapers and "
                f"measured contrast. Install with one command.",
                body + footer(themes), "home")


def render_catalog(themes):
    tags = sorted({tag for t in themes for tag in t["tags"]})
    filters = ('<span class="lbl">Filter</span>'
               '<button class="pill on" data-filter="*">All</button>'
               + "".join(f'<button class="pill" data-filter="{esc(x)}">{esc(x)}</button>'
                         for x in tags))
    body = f"""
<section class="sec"><div class="wrap">
<div class="sec-head"><p class="eyebrow">The roster</p>
<h2>{len(themes)} themes, none of them subtle</h2>
<p>Every figure on these cards was measured from that theme's
<code>colors.toml</code> when this page was built. Open one for its full palette,
its wallpapers and what it costs you.</p></div>
<div class="filters">{filters}</div>
<ul class="cards">{"".join(card(t) for t in themes)}</ul>
</div></section>
"""
    return page("Themes — Ritzpah", f"All {len(themes)} Ritzpah themes for Omarchy.",
                body + footer(themes), "catalog")


STEPS = [
    ("Start with the palette",
     "<code>themes/&lt;lowercase-hyphen-name&gt;/colors.toml</code> is a complete working "
     "theme on its own — Omarchy generates the terminal, btop, neovim, Chromium and shell "
     "configs from it. Look at it before reaching for anything else."),
    ("Declare what it is",
     "<code>theme.json</code> carries the name, tagline, tags and the contrast floor you "
     "hold yourself to. Every field is optional and unknown keys are kept rather than "
     "rejected — a schema that refuses weird stops you building the good one."),
    ("Earn the floor",
     "<code>./ritzpah contrast &lt;name&gt;</code> measures every ink slot against the "
     "background. Fix the palette, or exempt the slot <em>with a reason</em>. Do not lower "
     "the floor to make the error go away."),
    ("Generate the wallpapers",
     "A <code>tools/make-backgrounds-&lt;name&gt;</code> script that draws its images from "
     "primitives, made executable in the same commit. The recipe is the deliverable; the "
     "exact image never was. Then open them and actually look."),
    ("Record the prompt",
     "<code>PROMPT.md</code>, verbatim, typos and all, with the date. No cleaning it up "
     "afterwards to sound smarter than you were. A theme without its prompt is an orphan."),
    ("Pass the gate",
     "<code>./ritzpah validate &lt;name&gt;</code> until it reports <code>[ok]</code>, or "
     "every remaining warning is one you can defend out loud. CI runs the same command on "
     "your pull request."),
]


def render_surface(executables, commit):
    """The security section's table, built from what is actually in the repo."""
    rows = []
    total_hits = 0
    for entry in executables:
        hits = entry["hits"]
        total_hits += len(hits)
        why = "executable bit" if entry["exec_bit"] else "shebang only"
        if hits:
            detail = "".join(
                f'<li><code>line {n}</code> {esc(text)}</li>' for n, text in hits)
            net = (f'<details><summary>{len(hits)} match'
                   f'{"es" if len(hits) != 1 else ""}</summary><ul>{detail}</ul></details>')
        else:
            net = '<span class="ok">none</span>'
        rows.append(f'<tr><td><code>{esc(entry["path"])}</code></td>'
                    f'<td class="dimcell">{why}</td><td>{net}</td></tr>')

    stamp = f' at <code>{esc(commit)}</code>' if commit else ""
    summary = (f"{len(executables)} file{'s' if len(executables) != 1 else ''} in this "
               f"repository can execute{stamp}. Everything else is data.")
    if total_hits:
        note = (f"The scan found {total_hits} line{'s' if total_hits != 1 else ''} "
                f"mentioning something that could reach the network. Every one is shown "
                f"in full, false positives included \u2014 a URL in a comment counts, and so "
                f"does the word <code>curl</code> inside the prompt above. Read them and "
                f"decide for yourself.")
    else:
        note = ("Nothing matched the network scan. That is evidence, not proof, which is "
                "why the prompt above exists.")

    return f"""<div style="margin-top:30px">
<p class="lede" style="max-width:76ch">{summary} {note}</p>
<div class="tablewrap"><table class="surface">
<thead><tr><th>File</th><th>Why it counts</th><th>Network scan</th></tr></thead>
<tbody>{"".join(rows)}</tbody></table></div>
<p class="scanline">Scan pattern: <code>{esc(NETWORK_PATTERN.pattern)}</code></p>
</div>"""


def render_contributing(themes, executables=(), commit=""):
    steps = "".join(f"<li><h3>{t}</h3><p>{b}</p></li>" for t, b in STEPS)
    surface = render_surface(executables, commit)
    body = f"""
<section class="sec"><div class="wrap">
<div class="sec-head"><p class="eyebrow">Contributing</p>
<h2>Add a theme</h2>
<p>Nothing here is ever updated after it is merged. This is a roster of
one-shots, which makes the merge the only moment a theme can be made right — so
perfect it before you contribute it, and expect the gate to be the strict part
of an otherwise permissive repository.</p></div>
<ol class="steps">{steps}</ol>
<div class="note-box" style="margin-top:38px">
<p><strong>House rule: Ritzpah is allowed to be too much.</strong> If a theme is
tasteful, restrained, or honestly pretty usable for daily driving, it is in the
wrong repository. Turn something up.</p>
<p>Blueprint is the exception that proves it, and it is not a loophole. It holds
AAA where the rest of the collection sits on AA — but the excess did not go
missing, it went into the rigour instead of the look. If you are going to be
restrained here, be insufferable about it.</p>
</div>
<div class="actions" style="margin-top:32px;display:flex;gap:11px;flex-wrap:wrap">
<a class="btn primary" href="{REPO}/blob/main/THEME_JSON.md">theme.json schema</a>
<a class="btn" href="{REPO}/blob/main/RITZPAH_SKILL.md">Full build guide</a>
<a class="btn" href="{REPO}/issues/new">Open an issue</a>
</div>
</div></section>

<section class="sec" id="trust"><div class="wrap">
<div class="sec-head"><p class="eyebrow">Before you install anything</p>
<h2>Don't trust me</h2>
<p>This repository ships shell scripts that run on your machine and write into
<code>~/.config/omarchy/</code>. You have no reason to trust a stranger's theme
repo, so don't — ask your own agent first.</p></div>
<div class="cmd"><pre id="audit">{esc(AUDIT_PROMPT)}</pre>
<button class="btn" data-copy="audit">Copy prompt</button></div>
<div class="note-box" style="margin-top:30px">
<p>To make that cheap, here is the entire audit surface, <strong>found by
reading the repository when this page was built</strong> rather than written
down once and left to rot. Themes are allowed to ship their own scripts, so this
list will grow — and it grows here automatically when it does.</p>
<p>An audit covers the commit you audited. Run it again after a
<code>git pull</code>.</p>
</div>
{surface}
</div></section>
"""
    return page("Contribute — Ritzpah",
                "How to add a theme to Ritzpah, and how to audit it before installing.",
                body + footer(themes), "contributing")


def render_theme_page(theme, prev_theme, next_theme, themes):
    worst = theme["slots"][0]["ratio"] if theme["slots"] else "-"
    facts = "".join(
        f"<div><dt>{esc(k)}</dt><dd>{esc(v)}</dd></div>" for k, v in [
            ("Contrast floor", f'{theme["floor"]}:1'),
            ("Worst slot", f"{worst}:1"),
            ("Ink slots", len(theme["slots"])),
            ("Wallpapers", theme["wallpapers"]),
            ("Shader", "Yes" if theme["shader"] else "No"),
            ("Battery", (theme["battery"] or "normal").title()),
        ])

    swatches = []
    for entry in theme["slots"]:
        slot, ratio = entry["slot"], entry["ratio"]
        if slot in theme["exempt"]:
            cls, note = "xmpt", "exempt"
        elif ratio < theme["floor"]:
            cls, note = "under", "under floor"
        else:
            cls, note = "", "ok"
        title = theme["exempt"].get(slot) or ""
        swatches.append(
            f'<div class="sw"{f" title={json.dumps(title)}" if title else ""}>'
            f'<div class="chip" style="background:{esc(entry["colour"])}"></div>'
            f'<div class="m"><div class="n">{esc(slot)}</div>'
            f'<div class="r {cls}">{ratio}:1 &middot; {note}</div></div></div>')

    shot = theme["assets"].get("preview")
    hero_shot = (f'<figure class="t-shot"><img src="../assets/{esc(shot)}" '
                 f'alt="{esc(theme["name"])} desktop preview">'
                 f'<figcaption>Rendered with ImageMagick, not screenshotted.</figcaption>'
                 f'</figure>' if shot else "")
    sheet = theme["assets"].get("sheet")
    sheet_block = (f"""<section class="sec"><div class="wrap">
<div class="sec-head"><h2>The wallpapers</h2>
<p>All {theme["wallpapers"]} of them, drawn by
<code>{esc(theme["generator"] or "its generator script")}</code>. Re-run it and
you get a different set in the same palette, because the recipe is what ships.</p></div>
<figure class="t-shot" style="margin-top:0"><img loading="lazy" src="../assets/{esc(sheet)}"
alt="{esc(theme["name"])} wallpapers"></figure>
</div></section>""" if sheet else "")

    notes = (f'<div class="note-box" style="margin-top:30px"><p>{esc(theme["notes"])}</p></div>'
             if theme["notes"] else "")
    tags = "".join(f"<span>{esc(x)}</span>" for x in theme["tags"])

    def pager_link(other, label):
        if not other:
            return "<span></span>"
        return (f'<a href="{esc(other["slug"])}.html">{label}<b>{esc(other["name"])}</b></a>')

    body = f"""
<header class="t-hero"><div class="wrap">
<a class="crumb" href="../catalog.html">&larr; All themes</a>
<h1>{esc(theme["name"])}</h1>
<p class="lede">{esc(theme["tagline"])}</p>
<div class="tags">{tags}</div>
{hero_shot}
</div></header>

<section class="sec"><div class="wrap">
<div class="sec-head"><h2>Install it</h2></div>
<div class="cmd"><pre id="cmd">./ritzpah install {esc(theme["slug"])}
omarchy theme set {esc(theme["slug"])}</pre>
<button class="btn" data-copy="cmd">Copy</button></div>
<dl class="facts" style="margin-top:26px">{facts}</dl>
{notes}
</div></section>

<section class="sec"><div class="wrap">
<div class="sec-head"><h2>The palette</h2>
<p>Every ink slot measured against <code>{esc(theme["background"])}</code>, worst
first. A slot marked <em>exempt</em> sits below the floor deliberately and says
why on hover.</p></div>
<div class="swatches">{"".join(swatches)}</div>
</div></section>

{sheet_block}

<section class="sec"><div class="wrap">
<div class="pager">{pager_link(prev_theme, "Previous")}{pager_link(next_theme, "Next")}</div>
</div></section>
"""
    return page(f'{theme["name"]} — Ritzpah',
                theme["tagline"] or f'The {theme["name"]} theme for Omarchy.',
                body + footer(themes, depth=1), "catalog", depth=1,
                palette=palette_vars(theme))


def build(repo, out):
    assets = os.path.join(out, "assets")
    if os.path.isdir(out):
        shutil.rmtree(out)
    os.makedirs(assets)
    os.makedirs(os.path.join(out, "themes"))

    themes = collect(repo, assets)
    surface = audit_surface(repo)
    commit = repo_commit(repo)

    with open(os.path.join(assets, "site.css"), "w", encoding="utf-8") as fh:
        fh.write(CSS)
    with open(os.path.join(assets, "site.js"), "w", encoding="utf-8") as fh:
        fh.write(JS)

    pages = {
        "index.html": render_landing(themes),
        "catalog.html": render_catalog(themes),
        "contributing.html": render_contributing(themes, surface, commit),
    }
    for index, theme in enumerate(themes):
        pages[os.path.join("themes", f'{theme["slug"]}.html')] = render_theme_page(
            theme,
            themes[index - 1] if index else None,
            themes[index + 1] if index + 1 < len(themes) else None,
            themes,
        )
    pages["404.html"] = pages["index.html"]

    for name, markup in pages.items():
        with open(os.path.join(out, name), "w", encoding="utf-8") as fh:
            fh.write(markup)

    total = sum(os.path.getsize(os.path.join(root, name))
                for root, _, names in os.walk(out) for name in names)
    print(f"built {out} - {len(pages)} pages, {len(themes)} themes, {total / 1024 / 1024:.1f} MB")
    print("open it with: xdg-open " + os.path.join(out, "index.html"))
    return 0


if __name__ == "__main__":
    if len(sys.argv) < 3:
        print("usage: ritzpah-site.py <repo> <out-dir>", file=sys.stderr)
        raise SystemExit(2)
    raise SystemExit(build(sys.argv[1], sys.argv[2]))
