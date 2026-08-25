---
name: ritzpah
description: Build, install, validate, and debug themes in the Ritzpah Omarchy theme collection. Use when working in the ritzpah repo, adding a theme under themes/, running ./ritzpah or ./install, writing a theme.json, checking contrast floors, regenerating wallpapers with tools/make-backgrounds*, or explaining why the desktop is melting.
---

# RITZPAH: THE SKILL

**READ THIS BEFORE YOU TOUCH ANYTHING, YOU MAGNIFICENT LITTLE GOBLIN.**

Ritzpah is not a theme. Ritzpah is a **COLLECTION**. A menagerie. A zoo with the
locks filed off. `lubabs770/ritzpah`, cloned at `~/code/ritzpah`, and every
theme inside it is engineered to be seen from orbit.

Six inhabitants, and the roster is authoritative in `./ritzpah list`, not here —
if this section and the CLI disagree, the CLI is right and this file is stale:

| Theme | Floor | Shader | What it is |
|---|---|---|---|
| **acid-vortex** | 4.5 | no | neon filaments on a violet void, borders that spin until the heat death of the universe |
| **ego-death** | 4.5 | YES | a GLSL shader over the **entire compositor output**. The desktop melts. Windows melt. The cursor melts. |
| **untitled** | 4.5 | no | grayscale, but *derived* — the eight ANSI hues ranked by Rec.709 luma and dealt onto even neutral bands. Hue gone, only the order it implied survives. |
| **cathode** | 4.5 | YES | amber phosphor, barrel distortion, 720 scanlines, aperture grille. Not themed like a CRT — *displayed on one*. |
| **blueprint** | **7.0** | no | cyan-white ink on deep navy, drawn to a standard. The one you can work in all day. |
| **casino-carpet** | 4.5 | no | the Las Vegas floor-covering recipe, applied without mercy. Generated carpets, six-stop spinning border. |

---

## PART ZERO: THE CLI IS THE FRONT DOOR

`./ritzpah` is the collection's own CLI and it is where every verb lives now.

```bash
./ritzpah list                        # the roster, measured off the files
./ritzpah install <name> [--set]      # copy in; --set also switches
./ritzpah install --all               # every theme, switch to none
./ritzpah validate [name...]          # THE GATE. no args = all of them
./ritzpah contrast <name> [--floor N] # WCAG ratio per ink slot, worst first
./ritzpah show <name>                 # everything known about one theme, as JSON
```

Two files implement it: `ritzpah` (bash — argument parsing and the one verb that
writes outside the repo) and `tools/ritzpah-lib.py` (Python — TOML, JSON, and
the contrast maths). `./install` still exists as a thin wrapper so older
instructions keep working; it forwards to `ritzpah install --set`.

**Omarchy's built-in `omarchy theme install <git-url>` is USELESS HERE.** It
believes — sweetly, naively — that one repo equals one theme. Ritzpah has six.
Do not reach for it. Do not suggest it. It will clone the whole collection as one
broken theme and you will have to explain yourself.

### Things that changed and will trip you if you remember the old shape

- **`--link` IS GONE.** Themes are copied, never symlinked. Every theme here is
  a one-shot — perfected before merge, never updated after — so a live link back
  to the working tree only means the installed theme mutates while you edit it.
  The clone is not load-bearing; move it or delete it and nothing breaks.
  See `THEME_JSON.md`.
- **Installing no longer switches by default.** `ritzpah install <name>` copies
  and stops. `--set` switches. `./install <name>` still switches, for continuity.
- **The unprompted `rm -rf` is fenced.** It still removes the destination before
  copying, but only if that destination contains a `colors.toml`. Anything else
  at that path is somebody's actual work and the install aborts instead of
  eating it.
- **Every theme now carries `theme.json`.** Read `THEME_JSON.md` before writing
  one. The schema is deliberately forgiving; the contrast floor is the only part
  with teeth.

### What the installer still does NOT do

- No dependency check, no ImageMagick check (that is the wallpaper tools' job).
- No uninstall. That is `omarchy theme remove <name>`.
- No git pull. It installs the working tree, dirty or not.
- Not transactional. `set -euo pipefail`, so an `--all` that dies on theme three
  leaves one and two installed. Never claimed otherwise.

---

## PART ONE: THE GATE

**In a roster of one-shots, merge is the only moment a theme can be made right.**
Nothing here is ever updated afterwards. That makes `ritzpah validate` the whole
quality policy rather than a nicety, and it is why the floor has teeth.

```bash
./ritzpah validate               # exit 0 on clean or warnings, 1 on errors
```

**Errors** mean it will not work: no `colors.toml`, TOML that does not parse, Lua
that does not compile, a `shell.<section>.toml` aiming at a section Omarchy does
not have, an ink slot under the theme's own contrast floor, or a named generator
that is not executable.

**Warnings** mean it is not finished to this repo's conventions: no `theme.json`,
no tagline, no `PROMPT.md`, no `preview.png`, an empty `backgrounds/`, a
wallpaper over 2 MB, a shell key not in the installed template, or a stale
contrast exemption.

### Why it exists, specifically

casino-carpet shipped as a palette with an **empty `backgrounds/`** and a
generator that had **never once run** — committed non-executable, `-rw-r--r--`
while every sibling was `-rwxr-xr-x`. Underneath that were two more bugs that
each failed silently at the top level *despite* `set -euo pipefail`. Validate
catches all of it before the commit, which is the only place it can be caught.

### Shell keys are checked against the LIVE template

`/usr/share/omarchy/default/themed/shell.toml.tpl`, read at validate time, never
a list baked into the validator. An upstream rename therefore shows up as a
failure instead of themes rotting silently while a surface just stops being
themed.

Two subtleties the parser handles, and you should not "fix": keys the template
ships **commented out** (`# border-width = 2`) are documented optional keys, not
absent ones; and `-top/-right/-bottom/-left` variants of a known width key are
accepted because the template documents that split in prose.

### Contrast floors and exemptions

`ritzpah contrast <name>` measures every ink slot against `background` — every
`#rrggbb` in `colors.toml` that is not a surface (`background`,
`dark_background`, `darker_background`, `lighter_background`, `selection`). All
six themes currently have exactly 20 such slots.

Only **blueprint** (7.04, AAA) and **casino-carpet** (4.96) clear 4.5 outright.
The other four each have a slot below it and declare it in `contrast_exempt`
**with a reason** — `muted` in three of them, plus untitled's `dark_foreground`
and `blue` sitting at 4.49 because that is where the even-band derivation
landed.

**An exemption is not a way to lower the floor.** It says *this slot is
deliberately below it, and here is why*, somewhere a reader will find it.
Validate also warns about a **stale exemption** — one that now clears the floor
anyway — so the list cannot outlive the problem it was written for.

**NEVER hand-write a measured number anywhere.** Slot counts, ratios, wallpaper
counts and shader yes/no are all derived from the files, every time. A shipped
preview image once asserted "16 slots" against a 20-slot palette because that
number was typed by a human. Print it from `ritzpah contrast` or do not print it.

---

## PART TWO: ANATOMY OF A THEME

Drop a directory under `themes/`. Ship `colors.toml` and you have a complete,
working theme — Omarchy generates alacritty, ghostty, kitty, foot, btop, neovim,
helix, chromium, obsidian, vscode and the shell from it. Everything else is
**opt-in flex**.

| File | Does |
|------|------|
| `colors.toml` | THE PALETTE. Mandatory. Drives every generated config. |
| `theme.json` | name, tagline, tags, contrast floor + exemptions. See `THEME_JSON.md`. |
| `hyprland.lua` | borders, rounding, shadow, blur, animations, screen shaders |
| `shell.<section>.toml` | overrides ONE section of the generated `shell.toml` |
| `icons.theme` | one line, a Yaru variant |
| `backgrounds/` | wallpapers, cycled by `omarchy theme bg next`. Keep each under 2 MB. |
| `ghostty.conf` | REPLACES the generated one — restate the whole palette or lose it |
| `preview.png` | what shows in the READMEs and the theme switcher |
| `PROMPT.md` | the original prompt, verbatim |

**Ship `shell.<section>.toml`, not `shell.toml`.** Omarchy merges each section
file into the generated shell config and leaves every other section at default.
Shipping a whole `shell.toml` freezes sections you did not mean to own, and they
rot the moment Omarchy's template changes.

**`hyprland.lua` loads BEFORE `~/.config/hypr/looknfeel.lua`**, so the user's
personal config always wins. A theme owns borders, rounding, blur, shadow,
animations. Gaps and per-window opacity belong to the human.

---

## PART THREE: WALLPAPERS — SYNTHESIZE, SCAVENGE, OR BOTH

```bash
tools/make-backgrounds                     # acid-vortex
tools/make-backgrounds-ego-death
tools/make-backgrounds-untitled
tools/make-backgrounds-cathode
tools/make-backgrounds-blueprint
tools/make-backgrounds-casino-carpet
tools/make-palette-untitled                # derives untitled's colors.toml
tools/make-backgrounds [dir] [W] [H]       # defaults 2560x1440
```

**Generate it, fetch it, or do both and collide them.** The old rule said
synthesize only. That rule is dead. Pick whichever route ends up more
outrageous, pompous, ludicrous and silly for the theme at hand, and if you
genuinely cannot decide, do both and composite one over the other. A fetched
image must be one you are allowed to ship: check the license, record where it
came from in the theme's `README.md`, and prefer public-domain or CC0 sources.
If a fetch would need a credit you cannot honour, generate instead.

`chmod +x` the generator **in the same commit that adds it.** Non-executable is
how casino-carpet shipped with an empty `backgrounds/`, and validate now treats
it as an error precisely because of that.

Several generators use the ImageMagick plasma-through-**256x1 CLUT** trick — a
lookup strip of narrow neon bands separated by dead void. Map a smooth grayscale
field through it and the gradients snap into glowing filaments instead of a
pastel smear. Then: bloom, vignette, contrast, saturation. Others draw
primitives directly (casino-carpet tiles scrolls, starbursts and paisleys into
wallpaper group `pmm`; blueprint draws real technical sheets).

Requires **ImageMagick 7** (`magick`, not `convert`). The plasma seeds are
random, so **every run produces a different set in the same palette** — the
recipe is the deliverable, the exact image never was. Do not hand-retouch
output; change the script.

---

## PART FOUR: THE GOTCHA VAULT

### Compositor and shaders

- **A screen shader only advances when Hyprland draws a frame.** Damage tracking
  means it draws almost nothing when the screen is still, so the melt FREEZES.
  Ego Death sets `debug = { damage_tracking = 0 }` to force continuous
  full-output redraws. **That, not the shader, is what eats the battery.**
  (`misc.vfr` was the old half of this trick — removed in Hyprland 0.56. Gone.)
- **`hyprctl keyword` is dead here.** Use `hyprctl --instance <n> eval` or just
  re-apply the theme.
- **Screencopy serialises.** One stuck `grim` makes every later screenshot look
  hung, which looks exactly like a dead compositor. It is not. `pgrep -a grim`,
  kill the leftover, carry on. No restart needed. Observed on Hyprland 0.56.2
  under heavy theme reloading; cause unconfirmed.
- **Shipping `ghostty.conf` replaces the generated file wholesale.** Ego Death
  does it purely to add `background-opacity = 0.65`, and therefore has to
  restate the entire palette. Cheapest possible mistake to make; most annoying
  to debug.
- **Escape hatch from any catastrophe:** `omarchy theme set "Acid Vortex"`. A
  theme switch reloads Hyprland's config, which resets shaders and damage
  tracking to defaults.

### ImageMagick, learned the hard way in casino-carpet

- **`stroke-linecap round` inlined before a `polyline` on the same MVG line
  breaks the parser.** Exactly that one pairing, on ImageMagick 7.1.2-29. The
  matrix was checked: `linecap`+`polygon`, `linecap`+`line`, `linecap`+`path`,
  `linejoin`+`polyline` and bare `polyline` are all fine. Emit the shape as a
  `path` and the round caps survive.
- **Arguments crossed in a drawing helper fail silently and drop the whole
  layer.** `burst()` read `col=$4` when `$4` was the ray count, so ImageMagick
  got `unrecognized color '16'`, dropped the layer, and **still exited 0**.
- **`set -euo pipefail` did not catch either of those.** Both failed inside a
  subshell/pipeline whose status never reached the top. Never trust exit 0 from
  a wallpaper generator — **look at the images**, and let `ritzpah validate`
  check the directory is not empty.

### Misc

- **`omarchy theme update` skips anything not a git checkout.** Copied themes
  are therefore never updated — which is correct here, not a defect. One-shots.
- **LICENSE is MIT.** Keep it.

---

## PART FIVE: ADDING A THEME — THE RITUAL

1. `themes/<lowercase-hyphen-name>/`
2. Write `colors.toml` first. Look at it. Only then reach for the Lua.
3. `theme.json` — name, tagline, tags, `contrast_floor`. Run
   `./ritzpah contrast <name>` and either fix the palette or exempt the slot
   **with a reason**. Do not lower the floor to make the error go away.
4. Wallpapers: a `tools/make-backgrounds-<name>` script, fetched images, or both
   — whichever is more ludicrous. **`chmod +x` it in the same commit.** If
   generated, the script ships. If fetched, source and license go in the theme's
   `README.md`. Then open the images and actually look at them.
5. `themes/<name>/PROMPT.md` — **the original prompt, verbatim.** Every theme
   records the exact words that summoned it, typos and all, plus the date. No
   cleaning it up afterwards to sound smarter than you were. If a theme grew
   across several prompts, list them in order. A theme without its prompt is an
   orphan. (acid-vortex, ego-death and untitled are currently orphans. Do not
   add a fourth.)
6. `preview.png` — **rendered with ImageMagick, not screencaptured** — then
   `themes/<name>/README.md`.
7. `./ritzpah validate <name>` until it is `[ok]`, or every remaining warning is
   one you can defend out loud.
8. `./ritzpah install <name> --set` and live in it for a while.
9. Link it from the root `README.md` "Themes" section, with palette + preview,
   and add the row to the "Repo layout" block.
10. Commit. Push. Loudly.

---

## PART SIX: THE PROMISE IN THE README

The root `README.md` has a **"Don't trust me"** section that hands the reader a
copy-pasteable prompt for auditing this repo with their own agent, and then makes
a falsifiable claim to make that audit cheap:

> the only things here that execute are `ritzpah`, `install`,
> `tools/ritzpah-lib.py`, and `tools/make-backgrounds-*` ... **Nothing in this
> repo makes a network request. Nothing runs on a schedule. Nothing runs at
> shell startup.**

**That paragraph is load-bearing and it is a promise.** The day anything here
fetches a URL, adds a systemd timer, or grows a shell hook, that claim becomes a
lie in the README of a repo whose whole pitch is "audit me". Amend it **in the
same commit** that breaks it, or do not break it.

---

## HOUSE RULE

**Ritzpah is allowed to be too much.** If a theme is tasteful, restrained, or
"honestly pretty usable for daily driving," it is in the wrong repo. Turn
something up. The `README.md` of Ego Death has an entire section titled
*Turning it down* — that section exists so the theme never has to.

**Blueprint is the exception that proves it, and it is not a loophole.** It is
readable at hour eight and holds AAA where the rest of the repo sits on AA — but
the excess did not go missing, it went into the rigour instead of the look: ISO
128 line weights, ISO 129 dimensioning, and wallpapers that are real technical
sheets with zone strips, ruler ticks, filed revision histories and drawn filing
holes. `red` had to become pink to make the floor, and the write-up says so out
loud. If you are going to be restrained here, be **insufferable** about it.
