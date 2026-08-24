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

## Repo layout

```
install                  installer for the whole collection
themes/<name>/           one theme, in Omarchy's own layout
tools/make-backgrounds   regenerates Acid Vortex's wallpapers from scratch
docs/                    preview images used by the READMEs
```

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
| `preview.png` | what shows up in this README |

Shipping `shell.<section>.toml` files is safer than shipping a whole
`shell.toml` — Omarchy merges each one into the generated file and leaves the
other sections at their defaults.

## License

MIT. See [LICENSE](LICENSE).
