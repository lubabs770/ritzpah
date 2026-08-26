# Ritzpah

Omarchy themes. Loud ones.

**Browse them at [lubabs770.github.io/ritzpah](https://lubabs770.github.io/ritzpah/)**
— previews, full palettes with measured contrast, and the wallpapers. This file
is the technical reference; the site is where you look at things.

## Install

Omarchy's `omarchy theme install <url>` expects one repo per theme, so this
collection ships its own CLI.

```bash
git clone https://github.com/lubabs770/ritzpah.git
cd ritzpah
./ritzpah install blueprint --set
```

| Command | Does |
|---------|------|
| `ritzpah list` | roster with contrast and wallpaper counts, measured off the files |
| `ritzpah install <name> [--set]` | copy into `~/.config/omarchy/themes`; `--set` also switches |
| `ritzpah install --all` | every theme, switching to none |
| `ritzpah validate [name...]` | the gate; exit 1 on errors, 0 on warnings |
| `ritzpah contrast [name...] [--floor N]` | WCAG ratio per ink slot, worst first |
| `ritzpah show <name>` | everything known about one theme, as JSON |
| `ritzpah site [dir]` | build the static site into `site/` |
| `ritzpah iss-tle` | refresh ISS Cockpit's fallback orbit — **the only networked verb** |

`./install` is a thin wrapper kept for older instructions.

Themes are **copied, never symlinked**. Each one is a one-shot, perfected before
merge rather than updated after, so a live link back to a working tree would
only mean the installed theme changes under you. The clone is not load-bearing.

## Repo layout

```
ritzpah                               CLI: list, install, validate, contrast, show, site, iss-tle
install                               thin wrapper kept for older instructions
THEME_JSON.md                         the theme.json schema, and why it is forgiving
RITZPAH_SKILL.md                      full build guide, gotchas, house rules
themes/<name>/                        one theme, in Omarchy's own layout
themes/<name>/theme.json              name, tagline, tags, contrast floor
tools/ritzpah-lib.py                  data half of the CLI (TOML, JSON, contrast maths)
tools/ritzpah-site.py                 builds the static site published to Pages
tools/primer.py                       fetches and resolves @primer/primitives design tokens
tools/make-github-themes              derives the five GitHub themes from those tokens
tools/make-backgrounds*               one wallpaper generator per theme
tools/make-preview-github             renders the GitHub themes' preview cards
tools/make-docs-github                palette strips and contact sheets for the GitHub themes
tools/make-preview-iss-cockpit        renders that preview from live telemetry
tools/ritzpah-iss-tle.py              the one networked verb; refreshes a fallback orbit
ritzpahd/                             optional Rust daemon: live ISS telemetry for ISS Cockpit
docs/                                 palette strips and wallpaper contact sheets
.github/workflows/pages.yml           validates every theme, then publishes the site
```

## Anatomy of a theme

Drop a directory under `themes/`. `colors.toml` alone is a complete working
theme — Omarchy generates the terminal, btop, neovim, Chromium and shell configs
from it via the templates in `/usr/share/omarchy/default/themed/`. Everything
else is opt-in.

| File | Does |
|------|------|
| `colors.toml` | the palette; drives every generated config. Required. |
| `theme.json` | name, tagline, tags, contrast floor — see [THEME_JSON.md](THEME_JSON.md) |
| `hyprland.lua` | borders, rounding, shadow, blur, animations, screen shaders |
| `shell.<section>.toml` | overrides one section of the generated `shell.toml` |
| `icons.theme` | one line, a Yaru variant |
| `backgrounds/` | wallpapers, cycled by `omarchy theme bg next`. Keep each under 2 MB. |
| `ghostty.conf` | replaces the generated one (restate the whole palette if you ship it) |
| `preview.png` | rendered, not screenshotted |
| `PROMPT.md` | the original prompt, verbatim |

Ship `shell.<section>.toml` rather than a whole `shell.toml`: Omarchy merges each
section file into the generated config and leaves the rest at their defaults, so
you do not freeze sections you did not mean to own.

`hyprland.lua` loads *before* `~/.config/hypr/looknfeel.lua`, so a user's
personal config always wins. A theme owns borders, rounding, blur, shadow and
animations; gaps and per-window opacity belong to the human.

### Live themes

Most themes here are `kind: "static"` — a fixed set of colours that will look
the same next year. A theme can also declare `kind: "live"`, meaning it derives
itself from something outside the repo.

[Lunation](themes/lunation) is the first, and it sets the shape. Two rules:

- **A live theme does not get a timer.** Nothing here is allowed to install a
  systemd unit, a cron entry or a shell hook — that would make the audit
  surface below considerably less reassuring, and it is not necessary. Hyprland
  already re-executes `hyprland.lua` on every config load, and already hands a
  screen shader the wall clock on every frame. Both were already running.
- **A live theme writes into the generated theme directory**
  (`~/.local/state/omarchy/current/theme`), never into `~/.config/omarchy/themes`
  and never into this repo. That directory is Omarchy's own working copy and is
  rebuilt from scratch on every theme switch, so the committed version of the
  file stays the proven fallback.

[ISS Cockpit](themes/iss-cockpit) is the second, and it is the first theme here
that talks to anything. It keeps both rules — the theme itself has no timer and
writes only `cockpit.frag` into the generated directory — but it comes with
something no other theme has: **`ritzpahd`, an optional daemon** that holds a
WebSocket to the public ISSLIVE feed and drives the panel with real cabin
telemetry.

That is a genuine widening of what this repo ships, so it is worth being exact
about the seam:

- The **theme** is unchanged in kind. Install it, run nothing, and it is a
  self-contained live theme that computes an orbit locally and never opens a
  socket.
- The **daemon** is a separate binary you build and start yourself. No unit, no
  hook, no autostart, and nothing in the install path builds or runs it.
- It hands its data to the shader by painting 64×2 pixels of real screen that
  the shader reads out of the composited frame, because Hyprland's screen-shader
  uniforms are a fixed compiled-in enum with no second sampler. See
  [TELEMETRY.md](themes/iss-cockpit/TELEMETRY.md).

Its Rust sources are in the audit surface below, found by the same scan as
everything else.

`ritzpah list` prints the kind, read from `theme.json`.

## The gate

Nothing here is ever updated after it is merged, which makes the merge the only
moment a theme can be made right. `ritzpah validate` is therefore the whole
quality policy, and CI runs it on every pull request.

**Errors** — no `colors.toml`, TOML that does not parse, Lua that does not
compile, a `shell.<section>.toml` aiming at a section Omarchy does not have, an
ink slot under the theme's own contrast floor, or a named generator that is not
executable.

**Warnings** — no `theme.json`, no tagline, no `PROMPT.md`, no `preview.png`, an
empty `backgrounds/`, a wallpaper over 2 MB, a shell key absent from the
installed template, or a stale contrast exemption.

Shell keys are checked against the live
`/usr/share/omarchy/default/themed/shell.toml.tpl`, not a list baked into the
validator, so an upstream rename surfaces as a failure rather than themes
rotting silently. That check is skipped when Omarchy is not installed, which
includes CI.

No measured value is ever written by hand. Slot counts, ratios, wallpaper counts
and shader yes/no are derived from the files every time they are needed.

## Don't trust me

This repo ships shell scripts that run on your machine and write into
`~/.config/omarchy/`. You have no reason to trust a stranger's theme repo. So
don't — ask your own agent, before you install anything:

```
Audit this repo before I install it: https://github.com/lubabs770/ritzpah
Clone it somewhere temporary and actually read it. Tell me:
- what executes, and when - install time, every shell start, on a timer?
- does anything touch the network, and where does it connect?
- does it write anywhere outside ~/.config/omarchy/themes?
- does it read anything it has no business reading - keys, tokens, shell history?
- anything obfuscated: base64, eval, curl piped into a shell?
Quote the exact lines for anything you flag. If it's clean, say so plainly.
```

To make that cheap, the site publishes the **whole audit surface**, computed
from the files at build time rather than written down once and left to rot:
[every file in this repo that can execute](https://lubabs770.github.io/ritzpah/contributing.html#trust),
why it counts as executable, and every line in it that mentions anything capable
of reaching the network or of writing to your disk — false positives included,
with both scan patterns shown so you can judge them rather than trust them.

"Can execute" is not the same as "has an executable bit". Every theme's
`hyprland.lua` is handed to a Lua interpreter by Hyprland on every config load,
and every `.frag` is handed to your GPU on every frame. Both are listed, for
every theme, whether or not they do anything interesting.

That list is generated because it will keep changing. Themes are allowed to ship
their own scripts, and a security claim frozen into a README is exactly the kind
that quietly stops being true.

Reproduce it yourself:

```bash
./ritzpah site && $BROWSER site/contributing.html
```

An audit covers the commit you audited. Run it again after `git pull`.

## Contributing

See [THEME_JSON.md](THEME_JSON.md) for the schema and
[RITZPAH_SKILL.md](RITZPAH_SKILL.md) for the full build guide. The short version:
`colors.toml` first, declare it in `theme.json`, earn the contrast floor or
exempt a slot with a reason, generate the wallpapers with a script that ships,
record `PROMPT.md` verbatim, then `./ritzpah validate` until it is clean.

## Ideas queue

```
calvin & hobbes
the far side
annoying (randomly timed subtle looknfeel changes to unnerve you, no loudness just erk)
ritzpah-roulette: deal colors.toml, hyprland.lua, a wallpaper, icons.theme and
  shell sections from different themes at random; install the chimera as a real
  theme called Roulette. --seed N reproduces a disaster you liked, --dry-run
  shows what it was about to do to you.
your computer is a website!!! famous website based themes
  -- started: the five GitHub dark themes, derived from @primer/primitives
themes dynamically built in real time from ridiculous variables — sports scores,
  the weather. The variable drives hue and chroma, never the luminance the
  contrast floor depends on.
  (ISS Cockpit is the first of these, and the variable is a space station.)
```

## License

MIT. See [LICENSE](LICENSE).
