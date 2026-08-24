---
name: ritzpah
description: Build, install, and debug themes in the Ritzpah Omarchy theme collection. Use when working in the ritzpah repo, adding a theme under themes/, running ./install, regenerating wallpapers with tools/make-backgrounds*, or explaining why the desktop is melting.
---

# RITZPAH: THE SKILL

**READ THIS BEFORE YOU TOUCH ANYTHING, YOU MAGNIFICENT LITTLE GOBLIN.**

Ritzpah is not a theme. Ritzpah is a **COLLECTION**. A menagerie. A zoo with the
locks filed off. `lubabs770/ritzpah`, cloned at `~/code/ritzpah`, and every
theme inside it is engineered to be seen from orbit.

Two inhabitants so far:

- **acid-vortex** — neon filaments on a violet void, window borders that spin
  until the heat death of the universe.
- **ego-death** — loads a GLSL shader **over the entire compositor output**. The
  desktop melts. Windows melt. The cursor melts. Your ability to read 11pt text:
  gone, screaming, into the sun.

---

## PART ONE: THE INSTALLER, WHICH IS THE WHOLE POINT

Omarchy's built-in `omarchy theme install <git-url>` believes — sweetly,
naively — that one repo equals one theme. Ritzpah has many. So Ritzpah ships
`./install` and the built-in command is **USELESS HERE**. Do not reach for it.
Do not suggest it. It will clone the whole collection as one broken theme and
you will have to explain yourself.

```bash
./install                    # list what's in the repo, install nothing
./install acid-vortex        # copy it in AND switch to it
./install --all              # copy every theme in, switch to NONE
./install --link ego-death   # symlink instead of copy, for live editing
./install --help             # prints the header comment
```

### What it actually does, mechanically

1. Source is `themes/`, destination is `~/.config/omarchy/themes/`.
2. A directory counts as a theme **only if it contains `colors.toml`.** No
   `colors.toml`, no existence. That single file is the entire membership test,
   for both the listing and the "no theme named X" error.
3. **`rm -rf "$dst"` runs before every install.** Yes. Every time. It nukes
   `~/.config/omarchy/themes/<name>` with no backup and no prompt. If a theme of
   that name got there by any other route, it is *gone*. Check before installing
   over a name you did not create.
4. Copy mode = `cp -r`. Link mode = `ln -s` back into the repo.
5. It calls `omarchy theme set <name>` **only when exactly one theme was named
   and `--all` was not passed.** `--all` deliberately switches to nothing.
6. Theme names are the **directory names** — `acid-vortex`, `ego-death`.
   Lowercase, hyphenated. Omarchy prettifies them for display ("Acid Vortex"),
   and `omarchy theme set` takes either, but the installer only ever speaks
   directory.
7. `set -euo pipefail`. First failure kills the run mid-loop. A `--all` that dies
   on theme three leaves themes one and two installed. Not transactional. Never
   claimed to be.

### `--link` is the dev loop

Symlink, edit in the repo, then re-apply. Applying is what copies the theme into
`~/.local/state/omarchy/current/theme/` and regenerates every downstream config
from `/usr/share/omarchy/default/themed/*.tpl`. Editing the repo alone changes
NOTHING on screen until you do:

```bash
omarchy theme set ego-death     # or: omarchy theme refresh
```

### What the installer does NOT do

- No dependency check. No ImageMagick check (that's the wallpaper tools' job).
- No uninstall. That's `omarchy theme remove <name>`.
- No git pull. It installs whatever is in the working tree, dirty or not.
- No validation of `hyprland.lua`, the shell TOMLs, or the shader. Bad Lua fails
  loudly at the compositor, far away from here, wearing a different hat.

---

## PART TWO: ANATOMY OF A THEME

Drop a directory under `themes/`. Ship `colors.toml` and you have a complete,
working theme — Omarchy generates alacritty, ghostty, kitty, foot, btop, neovim,
helix, chromium, obsidian, vscode and the shell from it. Everything else is
**opt-in flex**.

| File | Does |
|------|------|
| `colors.toml` | THE PALETTE. Mandatory. Drives every generated config. |
| `hyprland.lua` | borders, rounding, shadow, blur, animations, screen shaders |
| `shell.<section>.toml` | overrides ONE section of the generated `shell.toml` |
| `icons.theme` | one line, a Yaru variant |
| `backgrounds/` | wallpapers, cycled by `omarchy theme bg next` |
| `ghostty.conf` | REPLACES the generated one — restate the whole palette or lose it |
| `preview.png` | what shows in the READMEs and the theme switcher |

**Ship `shell.<section>.toml`, not `shell.toml`.** Omarchy merges each section
file into the generated shell config and leaves every other section at default.
Shipping a whole `shell.toml` freezes sections you did not mean to own, and they
rot the moment Omarchy's template changes.

**`hyprland.lua` loads BEFORE `~/.config/hypr/looknfeel.lua`**, so the user's
personal config always wins. A theme owns borders, rounding, blur, shadow,
animations. Gaps and per-window opacity belong to the human.

---

## PART THREE: WALLPAPERS ARE SYNTHESIZED, NOT SCAVENGED

```bash
tools/make-backgrounds                     # acid-vortex
tools/make-backgrounds-ego-death           # ego-death
tools/make-backgrounds [dir] [W] [H]       # defaults 2560x1440
```

Not one pixel in this repo was downloaded. Every wallpaper is built from
ImageMagick plasma noise pushed through a **256x1 CLUT** — a lookup strip of
narrow neon bands separated by dead void. Map a smooth grayscale field through
it and the gradients snap into glowing filaments instead of a pastel smear.
Then: bloom, vignette, contrast, saturation.

Requires **ImageMagick 7** (`magick`, not `convert`). The plasma seeds are
random, so **every run produces a different set in the same palette** — the
recipe is the deliverable, the exact image never was. Do not hand-retouch
output; change the script.

---

## PART FOUR: THE GOTCHA VAULT

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
- **LICENSE is MIT.** Keep it.

---

## PART FIVE: ADDING A THEME — THE RITUAL

1. `themes/<lowercase-hyphen-name>/`
2. Write `colors.toml` first. Look at it. Only then reach for the Lua.
3. Add wallpapers via a `tools/make-backgrounds-<name>` script — the generator
   ships, not the provenance question.
4. `preview.png`, then `themes/<name>/README.md`.
5. `./install --link <name>` and live in it for a while.
6. Link it from the root `README.md` "Themes" section, with palette + preview.
7. Commit. Push. Loudly.

---

## HOUSE RULE

**Ritzpah is allowed to be too much.** If a theme is tasteful, restrained, or
"honestly pretty usable for daily driving," it is in the wrong repo. Turn
something up. The `README.md` of Ego Death has an entire section titled
*Turning it down* — that section exists so the theme never has to.
