#!/usr/bin/env python3
"""Data half of the ritzpah CLI: read a theme, judge it, print it.

Nothing here writes to disk, makes a network request, or runs a subprocess
except `luac -p` to syntax-check a theme's hyprland.lua. The bash half
(`./ritzpah`) does the filesystem work.

The schema this reads is deliberately forgiving -- see THEME_JSON.md. Unknown
keys are carried, never rejected. Anything omitted is either derived from the
files on disk or simply not claimed.
"""

import json
import os
import re
import subprocess
import sys
import tomllib

# Keys in colors.toml that are surfaces rather than ink. Everything else that
# holds a #rrggbb is treated as a foreground slot and measured against
# `background`.
SURFACE_KEYS = {
    "background", "dark_background", "darker_background", "lighter_background",
    "selection",
}

HEX = re.compile(r"^#[0-9a-fA-F]{6}$")
SLUG = re.compile(r"^[a-z0-9]+(-[a-z0-9]+)*$")

# The floor a theme is held to when its theme.json does not claim one.
DEFAULT_FLOOR = 4.5

# The brief's ceiling for a single wallpaper.
MAX_IMAGE_BYTES = 2 * 1024 * 1024

SHELL_TPL = "/usr/share/omarchy/default/themed/shell.toml.tpl"


# --------------------------------------------------------------- contrast

def _channel(value):
    c = value / 255
    return c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4


def luminance(hex_colour):
    r = int(hex_colour[1:3], 16)
    g = int(hex_colour[3:5], 16)
    b = int(hex_colour[5:7], 16)
    return 0.2126 * _channel(r) + 0.7152 * _channel(g) + 0.0722 * _channel(b)


def contrast_ratio(fg, bg):
    a, b = luminance(fg), luminance(bg)
    hi, lo = max(a, b), min(a, b)
    return (hi + 0.05) / (lo + 0.05)


# --------------------------------------------------------------- reading

def read_colors(theme_dir):
    path = os.path.join(theme_dir, "colors.toml")
    with open(path, "rb") as handle:
        return tomllib.load(handle)


def contrast_report(theme_dir):
    """Every ink slot, measured against `background`, worst first."""
    colours = read_colors(theme_dir)
    background = colours.get("background")
    if not isinstance(background, str) or not HEX.match(background):
        raise ValueError("colors.toml has no usable `background`")

    slots = []
    for key, value in colours.items():
        if key in SURFACE_KEYS or not isinstance(value, str):
            continue
        if not HEX.match(value):
            continue
        slots.append({
            "slot": key,
            "colour": value,
            "ratio": round(contrast_ratio(value, background), 2),
        })
    slots.sort(key=lambda entry: entry["ratio"])
    return {"background": background, "slots": slots}


def read_theme_json(theme_dir):
    """Missing or unreadable theme.json is absence, never an error."""
    path = os.path.join(theme_dir, "theme.json")
    if not os.path.isfile(path):
        return None
    try:
        with open(path, "r", encoding="utf-8") as handle:
            data = json.load(handle)
    except (OSError, json.JSONDecodeError):
        return {"__unreadable__": True}
    return data if isinstance(data, dict) else {"__unreadable__": True}


def exemptions(declared):
    """`contrast_exempt` may be a list of slot names or an object mapping slot
    to reason. Both are accepted; a reason is encouraged but never required."""
    raw = declared.get("contrast_exempt")
    if isinstance(raw, dict):
        return {str(k): str(v) for k, v in raw.items()}
    if isinstance(raw, list):
        return {str(k): "" for k in raw}
    if isinstance(raw, str):
        return {raw: ""}
    return {}


def title_from_slug(slug):
    return " ".join(word.capitalize() for word in slug.split("-"))


def meta(theme_dir):
    """theme.json plus everything derivable from the files, one dict.

    Declared values win over derived ones for anything the author can have an
    opinion about. Counts and measurements are always derived, never read, so
    they cannot drift out of sync with the theme the way a hand-written slot
    count did.
    """
    slug = os.path.basename(theme_dir.rstrip("/"))
    declared = read_theme_json(theme_dir) or {}
    unreadable = declared.pop("__unreadable__", False)

    backgrounds_dir = os.path.join(theme_dir, "backgrounds")
    wallpapers = []
    if os.path.isdir(backgrounds_dir):
        wallpapers = sorted(
            name for name in os.listdir(backgrounds_dir)
            if not name.startswith(".")
        )

    shell_sections = sorted(
        name[len("shell."):-len(".toml")]
        for name in os.listdir(theme_dir)
        if name.startswith("shell.") and name.endswith(".toml")
    )

    has_lua = os.path.isfile(os.path.join(theme_dir, "hyprland.lua"))
    shader = False
    if has_lua:
        with open(os.path.join(theme_dir, "hyprland.lua"), encoding="utf-8") as handle:
            shader = "screen_shader" in handle.read()

    try:
        report = contrast_report(theme_dir)
        worst = report["slots"][0] if report["slots"] else None
    except (OSError, ValueError, tomllib.TOMLDecodeError):
        report, worst = None, None

    return {
        "slug": slug,
        "dir": theme_dir,
        "has_theme_json": bool(declared) or unreadable,
        "theme_json_unreadable": unreadable,
        "declared": declared,
        # Declared, with a sane fallback.
        "name": declared.get("name") or title_from_slug(slug),
        "tagline": declared.get("tagline", ""),
        "kind": declared.get("kind", "static"),
        "tags": declared.get("tags", []),
        "floor": declared.get("contrast_floor", DEFAULT_FLOOR),
        "exempt": exemptions(declared),
        "generator": declared.get("generator", ""),
        # Derived, always.
        "shader": shader,
        "wallpapers": wallpapers,
        "shell_sections": shell_sections,
        "slot_count": len(report["slots"]) if report else 0,
        "worst_slot": worst,
        "files": sorted(os.listdir(theme_dir)),
    }


# --------------------------------------------------------------- validate

def shell_tpl_keys():
    """Section -> set of keys, read off the live Omarchy template.

    Read from the installed template rather than a list baked in here, so an
    upstream rename shows up as a validation failure instead of themes quietly
    rotting.
    """
    if not os.path.isfile(SHELL_TPL):
        return None
    key_line = re.compile(r"^([a-z][a-z0-9]*(?:-[a-z0-9]+)*)\s*=")
    sections, current = {}, None
    with open(SHELL_TPL, encoding="utf-8") as handle:
        for raw in handle:
            line = raw.strip()
            if line.startswith("[") and line.endswith("]"):
                current = line[1:-1]
                sections[current] = set()
                continue
            if not current:
                continue
            # A key the template ships commented out -- `# border-width = 2` --
            # is a documented, optional key, not an absent one. Harvest those
            # too, or every theme that sets one gets a bogus warning.
            candidate = line[1:].strip() if line.startswith("#") else line
            match = key_line.match(candidate)
            if match:
                sections[current].add(match.group(1))
    return sections


# The template documents that a width key may be split per edge. Accept those
# without needing each one spelled out upstream.
EDGE_SUFFIXES = ("-top", "-right", "-bottom", "-left")


def known_shell_key(key, known):
    if key in known:
        return True
    for suffix in EDGE_SUFFIXES:
        if key.endswith(suffix) and key[: -len(suffix)] in known:
            return True
    return False


def validate(theme_dir):
    """Return (errors, warnings). Errors mean it will not work; warnings mean
    it is not finished to this repo's own conventions."""
    errors, warnings = [], []
    slug = os.path.basename(theme_dir.rstrip("/"))

    if not SLUG.match(slug):
        errors.append(f"directory name {slug!r} is not a lowercase-hyphen slug")

    info = meta(theme_dir)

    if info["theme_json_unreadable"]:
        errors.append("theme.json is present but is not readable JSON")
    elif not info["has_theme_json"]:
        warnings.append("no theme.json (name and tagline fall back to the slug)")
    elif not info["tagline"]:
        warnings.append("theme.json has no tagline")

    # colors.toml is the one genuinely required file.
    colours_path = os.path.join(theme_dir, "colors.toml")
    if not os.path.isfile(colours_path):
        errors.append("colors.toml is missing (Omarchy cannot generate anything)")
        return errors, warnings
    try:
        read_colors(theme_dir)
    except tomllib.TOMLDecodeError as exc:
        errors.append(f"colors.toml does not parse: {exc}")
        return errors, warnings

    # Contrast against the floor this theme claims for itself.
    try:
        report = contrast_report(theme_dir)
    except ValueError as exc:
        errors.append(str(exc))
        report = None
    if report:
        floor = info["floor"]
        exempt = info["exempt"]
        seen = set()
        for entry in report["slots"]:
            slot = entry["slot"]
            if entry["ratio"] >= floor:
                if slot in exempt:
                    warnings.append(
                        f"{slot} is exempted from the {floor}:1 floor but "
                        f"clears it at {entry['ratio']}:1 -- stale exemption"
                    )
                continue
            seen.add(slot)
            if slot in exempt:
                continue
            errors.append(
                f"{slot} is {entry['ratio']}:1 against the background, under "
                f"this theme's floor of {floor}:1 (exempt it in theme.json, "
                f"with a reason, if that is deliberate)"
            )
        for slot in exempt:
            if slot not in {e["slot"] for e in report["slots"]}:
                warnings.append(f"contrast_exempt names {slot!r}, which is not a slot")

    # Every TOML in the theme has to parse, not just colors.toml.
    for name in info["files"]:
        if not name.endswith(".toml") or name == "colors.toml":
            continue
        try:
            with open(os.path.join(theme_dir, name), "rb") as handle:
                tomllib.load(handle)
        except tomllib.TOMLDecodeError as exc:
            errors.append(f"{name} does not parse: {exc}")

    # Shell sections, checked against the installed template.
    tpl = shell_tpl_keys()
    if tpl is None:
        warnings.append(f"cannot check shell keys: {SHELL_TPL} not found")
    else:
        for section in info["shell_sections"]:
            if section not in tpl:
                errors.append(
                    f"shell.{section}.toml targets a section Omarchy does not "
                    f"have (known: {', '.join(sorted(tpl))})"
                )
                continue
            try:
                with open(os.path.join(theme_dir, f"shell.{section}.toml"), "rb") as handle:
                    data = tomllib.load(handle)
            except tomllib.TOMLDecodeError:
                continue
            body = data.get(section, data)
            if isinstance(body, dict):
                for key in body:
                    if not known_shell_key(key, tpl[section]):
                        warnings.append(
                            f"shell.{section}.toml sets {key!r}, which is not "
                            f"in the installed template"
                        )

    # Lua has to at least compile.
    lua_path = os.path.join(theme_dir, "hyprland.lua")
    if os.path.isfile(lua_path):
        try:
            result = subprocess.run(
                ["luac", "-p", lua_path],
                capture_output=True, text=True, timeout=10,
            )
            if result.returncode != 0:
                errors.append(f"hyprland.lua does not compile: {result.stderr.strip()}")
        except FileNotFoundError:
            warnings.append("cannot check hyprland.lua: luac not installed")
        except subprocess.TimeoutExpired:
            warnings.append("cannot check hyprland.lua: luac timed out")

    # Wallpapers. An empty backgrounds/ is how casino-carpet shipped broken.
    if not info["wallpapers"]:
        warnings.append("backgrounds/ is empty or missing")
    for name in info["wallpapers"]:
        size = os.path.getsize(os.path.join(theme_dir, "backgrounds", name))
        if size > MAX_IMAGE_BYTES:
            warnings.append(
                f"backgrounds/{name} is {size / 1024 / 1024:.1f} MB, over the 2 MB brief"
            )

    for name, why in (
        ("preview.png", "the README has nothing to show"),
        ("README.md", "no write-up"),
        ("PROMPT.md", "the brief that produced it is not recorded"),
    ):
        if not os.path.isfile(os.path.join(theme_dir, name)):
            warnings.append(f"no {name} ({why})")

    # A generator that is not executable has never been run.
    generator = info["generator"]
    if generator:
        repo = os.path.dirname(os.path.dirname(theme_dir.rstrip("/")))
        path = os.path.join(repo, generator)
        if not os.path.isfile(path):
            warnings.append(f"theme.json names generator {generator!r}, which does not exist")
        elif not os.access(path, os.X_OK):
            errors.append(f"generator {generator} is not executable, so it has never run")

    return errors, warnings


# --------------------------------------------------------------- output

def theme_dirs(repo):
    root = os.path.join(repo, "themes")
    return [
        os.path.join(root, name)
        for name in sorted(os.listdir(root))
        if os.path.isdir(os.path.join(root, name))
    ]


def resolve(repo, names):
    if not names:
        return theme_dirs(repo)
    resolved = []
    for name in names:
        path = os.path.join(repo, "themes", name)
        if not os.path.isdir(path):
            print(f"ritzpah: no theme called {name!r}", file=sys.stderr)
            raise SystemExit(2)
        resolved.append(path)
    return resolved


def cmd_list(repo, args):
    rows = [meta(path) for path in theme_dirs(repo)]
    width = max((len(row["name"]) for row in rows), default=4)
    print(f"{'THEME'.ljust(width)}  KIND    SHADER  WALLS  SLOTS  WORST   TAGLINE")
    for row in rows:
        worst = f"{row['worst_slot']['ratio']:.2f}" if row["worst_slot"] else "-"
        tagline = row["tagline"] or "(no tagline)"
        if len(tagline) > 46:
            tagline = tagline[:45] + "…"
        print(
            f"{row['name'].ljust(width)}  "
            f"{row['kind'].ljust(6)}  "
            f"{('yes' if row['shader'] else 'no').ljust(6)}  "
            f"{str(len(row['wallpapers'])).rjust(5)}  "
            f"{str(row['slot_count']).rjust(5)}  "
            f"{worst.rjust(5)}   {tagline}"
        )
    return 0


def cmd_contrast(repo, args):
    floor = None
    names = []
    index = 0
    while index < len(args):
        if args[index] == "--floor" and index + 1 < len(args):
            floor = float(args[index + 1])
            index += 2
        else:
            names.append(args[index])
            index += 1

    failed = 0
    for path in resolve(repo, names):
        info = meta(path)
        limit = floor if floor is not None else info["floor"]
        report = contrast_report(path)
        print(f"{info['name']}  on {report['background']}  floor {limit}:1")
        exempt = info["exempt"]
        for entry in report["slots"]:
            slot = entry["slot"]
            if entry["ratio"] >= limit:
                mark = "ok  "
            elif slot in exempt:
                mark = "xmpt"
            else:
                mark = "UNDER"
                failed += 1
            line = f"  {mark} {slot.ljust(20)} {entry['colour']}  {entry['ratio']:6.2f}:1"
            if mark == "xmpt" and exempt.get(slot):
                line += f"   ({exempt[slot]})"
            print(line)
        print()
    return 1 if failed else 0


def cmd_validate(repo, args):
    worst = 0
    for path in resolve(repo, args):
        info = meta(path)
        errors, warnings = validate(path)
        if errors:
            status, worst = "FAIL", 1
        elif warnings:
            status = "warn"
            worst = max(worst, 0)
        else:
            status = "ok"
        print(f"[{status}] {info['name']}")
        for message in errors:
            print(f"       error: {message}")
        for message in warnings:
            print(f"       warn:  {message}")
    return worst


def cmd_show(repo, args):
    for path in resolve(repo, args):
        print(json.dumps(meta(path), indent=2, sort_keys=True))
    return 0


COMMANDS = {
    "list": cmd_list,
    "contrast": cmd_contrast,
    "validate": cmd_validate,
    "show": cmd_show,
}


def main(argv):
    if len(argv) < 3 or argv[2] not in COMMANDS:
        print("usage: ritzpah-lib.py <repo> <list|validate|contrast|show> [args]",
              file=sys.stderr)
        return 2
    return COMMANDS[argv[2]](argv[1], argv[3:])


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
