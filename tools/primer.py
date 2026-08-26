"""Primer design tokens, fetched once and resolved.

Shared by tools/make-github-themes and tools/make-backgrounds-github so that a
palette and the wallpaper drawn to match it can never disagree: both read the
same pinned package, and neither contains a hex value of its own.
"""

import io
import json
import os
import re
import tarfile
import tempfile
import urllib.request

# Pinned. An unpinned fetch means this repo builds differently on a different
# day, which is a hand-typed number wearing a better hat. Bump deliberately,
# rerun both generators, and read the diff.
VERSION = "11.10.0"
TARBALL = (f"https://registry.npmjs.org/@primer/primitives/-/"
           f"primitives-{VERSION}.tgz")

_CACHE = os.path.join(tempfile.gettempdir(), f"ritzpah-primer-{VERSION}.json")
_DECL = re.compile(r"^\s*(--[A-Za-z0-9-]+)\s*:\s*([^;]+);")
_THEME = re.compile(r"package/dist/css/functional/themes/(dark[a-z-]*)\.css")


def load(verbose=True):
    """Return {variant: {token: value}} for every dark theme Primer ships."""
    if os.path.exists(_CACHE):
        with open(_CACHE) as handle:
            return json.load(handle)

    if verbose:
        print(f"fetching @primer/primitives@{VERSION}")
    with urllib.request.urlopen(TARBALL, timeout=60) as response:
        blob = response.read()

    themes = {}
    with tarfile.open(fileobj=io.BytesIO(blob), mode="r:gz") as tar:
        for member in tar.getmembers():
            match = _THEME.fullmatch(member.name)
            if not match:
                continue
            tokens = {}
            body = tar.extractfile(member).read().decode("utf-8")
            for line in body.splitlines():
                hit = _DECL.match(line)
                if not hit:
                    continue
                key, value = hit.group(1), hit.group(2).strip()
                # Each file declares every token twice, under :root and under an
                # attribute selector, with identical values. Verified rather
                # than assumed: disagreement means the file shape changed.
                if key in tokens and tokens[key] != value:
                    raise SystemExit(
                        f"{member.name}: {key} declared twice and differs "
                        f"({tokens[key]!r} vs {value!r})")
                tokens[key] = value
            themes[match.group(1)] = tokens

    with open(_CACHE, "w") as handle:
        json.dump(themes, handle)
    return themes


def resolve(tokens, name, seen=()):
    """Follow var() indirection down to a literal value."""
    if name in seen:
        raise SystemExit(f"token cycle at {name}")
    if name not in tokens:
        raise SystemExit(f"missing token {name}")
    value = tokens[name]
    indirect = re.fullmatch(r"var\((--[A-Za-z0-9-]+)\)", value)
    if indirect:
        return resolve(tokens, indirect.group(1), seen + (name,))
    return value


def parse_hex(value):
    value = value.strip().lstrip("#")
    if len(value) == 3:
        value = "".join(c * 2 for c in value)
    if len(value) == 6:
        return tuple(int(value[i:i + 2], 16) for i in (0, 2, 4)) + (255,)
    if len(value) == 8:
        return tuple(int(value[i:i + 2], 16) for i in (0, 2, 4, 6))
    raise SystemExit(f"cannot parse colour {value!r}")


def flatten(colour, backdrop):
    """Composite a colour that has alpha onto an opaque backdrop."""
    r, g, b, a = colour
    br, bg, bb, _ = backdrop
    alpha = a / 255.0
    return (round(r * alpha + br * (1 - alpha)),
            round(g * alpha + bg * (1 - alpha)),
            round(b * alpha + bb * (1 - alpha)), 255)


def to_hex(rgba):
    return "#%02x%02x%02x" % rgba[:3]


def solid(tokens, name, over=None):
    """Resolve a token to an opaque #rrggbb, flattening alpha if it has any."""
    raw = parse_hex(resolve(tokens, name))
    if raw[3] == 255:
        return to_hex(raw)
    backdrop = over or parse_hex(resolve(tokens, "--bgColor-default"))
    if isinstance(backdrop, str):
        backdrop = parse_hex(backdrop)
    return to_hex(flatten(raw, backdrop))


def split_alpha(tokens, name):
    """Resolve to (#rrggbb, alpha) with the alpha kept rather than flattened."""
    raw = parse_hex(resolve(tokens, name))
    return to_hex(raw), round(raw[3] / 255.0, 3)


def relative_luminance(rgba):
    def channel(v):
        v /= 255.0
        return v / 12.92 if v <= 0.03928 else ((v + 0.055) / 1.055) ** 2.4
    r, g, b = (channel(c) for c in rgba[:3])
    return 0.2126 * r + 0.7152 * g + 0.0722 * b


def contrast(a, b):
    la, lb = relative_luminance(a), relative_luminance(b)
    high, low = max(la, lb), min(la, lb)
    return (high + 0.05) / (low + 0.05)
