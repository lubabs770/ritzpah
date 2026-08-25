# Ritzpah

Omarchy themes. Loud ones.

Omarchy's own `omarchy theme install <url>` expects one repo per theme, so this
collection ships its own installer.

```bash
git clone https://github.com/lubabs770/ritzpah.git
cd ritzpah
./install acid-vortex
```

That copies the theme into `~/.config/omarchy/themes/` and switches to it.
`./install --all` installs every theme without switching. `./install --link
<name>` symlinks instead of copying, so edits in the repo take effect on the
next `omarchy theme set`.

## Themes

### Acid Vortex

Neon filaments on a violet void, with a window border that never stops
spinning. [Full write-up](themes/acid-vortex/README.md).

![Acid Vortex](themes/acid-vortex/preview.png)

![Palette](docs/palette.png)

### Ego Death

Loads a GLSL shader over the whole compositor output, so the desktop itself
melts and hue-cycles in real time — windows, bar, cursor and all. Costs battery
and most of your ability to read small text. [Full
write-up](themes/ego-death/README.md).

![Ego Death](themes/ego-death/preview.png)

![Palette](docs/ego-death-palette.png)

### Untitled

The most themeless theme ever themed. Grayscale, but derived rather than
chosen: the eight ANSI hues are ranked by Rec.709 luma and dealt onto an even
band of neutral gray, so hue is gone and only the order it implied survives. No
gradient, no rounding, no shadow, no blur, no transparency, and animations off
at the switch. [Full write-up](themes/untitled/README.md).

![Untitled](themes/untitled/preview.png)

![Palette](docs/untitled-palette.png)

## Repo layout

```
install                            installer for the whole collection
themes/<name>/                     one theme, in Omarchy's own layout
tools/make-backgrounds             regenerates Acid Vortex's wallpapers
tools/make-backgrounds-ego-death   regenerates Ego Death's wallpapers
tools/make-backgrounds-untitled    regenerates Untitled's wallpapers
tools/make-palette-untitled        derives Untitled's colors.toml from scratch
docs/                              preview images used by the READMEs
```

No wallpaper here was downloaded. Both generators build every image from plasma
noise and gradients with ImageMagick, so the recipes ship instead of the
provenance questions.

## Adding a theme

Drop a directory under `themes/`. The only required file is `colors.toml` —
that alone is enough for Omarchy to generate terminal, btop, neovim, Chromium,
and shell configs from the templates in `/usr/share/omarchy/default/themed/`.
Everything else is opt-in:

| File | Does |
|------|------|
| `colors.toml` | the palette; drives every generated config |
| `hyprland.lua` | borders, rounding, shadow, blur, animations |
| `shell.<section>.toml` | overrides one section of the generated `shell.toml` |
| `icons.theme` | one line, a Yaru variant |
| `backgrounds/` | wallpapers, cycled by `omarchy theme bg next` |
| `ghostty.conf` | replaces the generated one (restate the whole palette if you ship this) |
| `preview.png` | what shows up in this README |

A theme's `hyprland.lua` is loaded *before* `~/.config/hypr/looknfeel.lua`, so
anything you set there wins over the theme. Gaps and per-window opacity
generally live in your personal config; borders, rounding, blur, shadow and
animations are the theme's to own.

Shipping `shell.<section>.toml` files is safer than shipping a whole
`shell.toml` — Omarchy merges each one into the generated file and leaves the
other sections at their defaults.



## so I don't forget when I have more tokens!!!
```
calvin & hobbes
the far side
annoying (randomly timed subtle looknfeel changes to unnerve you, no loudness just erk)
not a theme but - ritzpah-roulette!! a shell script that mish-moshes every theme in the
  repo together in a completely and profoundly perplexed way: colors.toml from one theme,
  hyprland.lua from another, a wallpaper from a third, icons.theme from a fourth, shell
  sections dealt out at random. installs the chimera as a real theme called Roulette so
  omarchy cannot tell it was assembled by a coin. --seed N to reproduce a disaster you
  liked, --dry-run to see what it was about to do to you. only escape is
  `omarchy theme set "Acid Vortex"`
your computer is a website!!! famous website based themes

material you for omarchy - the serious one. derive colors.toml FROM the current
  wallpaper instead of the other way round: extract the dominant hues, run them
  through material color utilities (tonal palettes, not raw pixel colors) and emit a
  real theme directory, so `omarchy theme bg next` restyles the entire desktop.
  matugen already does the extraction; the actual work is the omarchy layout, holding
  a 4.5:1 contrast floor on text the way untitled does, and picking light vs dark from
  the image's own luma. ships as a tool, not a theme:
  tools/make-theme-from-wallpaper <image>
```


## License

MIT. See [LICENSE](LICENSE).
