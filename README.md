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

## Repo layout

```
install                            installer for the whole collection
themes/<name>/                     one theme, in Omarchy's own layout
tools/make-backgrounds             regenerates Acid Vortex's wallpapers
tools/make-backgrounds-ego-death   regenerates Ego Death's wallpapers
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

## License

MIT. See [LICENSE](LICENSE).
