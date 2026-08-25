# `theme.json`

One file per theme, at `themes/<slug>/theme.json`. It carries the things a
theme knows about itself that no file on disk can tell you — what it is called,
what it is for, and what floor it holds itself to.

**The schema is deliberately forgiving.** Themes here are meant to get weird,
and a schema that rejects weird is a schema that stops you building the good
one. So:

- **Every field is optional.** A theme with no `theme.json` at all still
  installs, still validates, and still shows up in `ritzpah list`. It just gets
  a title-cased slug for a name and no tagline.
- **Unknown keys are kept, never rejected.** Invent fields freely. `ritzpah
  show` prints everything you declared. Nothing warns about a key it does not
  recognise.
- **Open vocabularies.** `kind` and `tags` are free strings, not enums. Adding
  a new kind of theme should not require editing the validator first.
- **Nothing measurable is declared.** Slot counts, wallpaper counts, contrast
  ratios and whether a theme runs a shader are *derived from the files* every
  time they are needed, never read from this file. A theme once shipped a
  preview image asserting "16 slots" when it had 20, because that number was
  written by hand. Numbers that can drift are not stored here.

## Fields

| Field | Type | Default | Means |
|---|---|---|---|
| `schema` | number | `1` | Bump only if the meaning of an existing field changes. |
| `slug` | string | the directory name | Kept for readability; the directory always wins. |
| `name` | string | title-cased slug | Display name. |
| `tagline` | string | — | One line. Shown in `ritzpah list` and the README. |
| `kind` | string | `"static"` | `static` = fixed once and never changes. `live` = regenerated from something outside the repo. Free string; anything else is carried, not judged. |
| `tags` | array | `[]` | Free strings, for browsing. |
| `contrast_floor` | number | `4.5` | The WCAG ratio every ink slot must clear against `background`. `ritzpah validate` **fails** the theme if a non-exempt slot is under it. |
| `contrast_exempt` | array or object | `{}` | Slots deliberately below the floor. An array of names works; an object mapping name → reason is better, and the reason is printed by `ritzpah contrast`. |
| `generator` | string | — | Repo-relative path to the script that builds this theme's wallpapers. If it names a file that is not executable, that is an **error**: a non-executable generator has never run. |
| `battery` | string | — | Free string. `"costs"` for shader themes. |
| `notes` | string | — | Anything worth saying that is not a tagline. |

## The floor and its exemptions

The floor is the only part of this file with teeth, because in a roster of
one-shots the merge is the only moment a theme can be made right — nothing is
ever updated afterwards.

An exemption is not a way to lower the floor. It is a way to say *this specific
slot is deliberately below it, and here is why*, in a place a reader will find
it. `ritzpah validate` also warns about a **stale exemption** — a slot that is
exempted but now clears the floor anyway — so the list cannot quietly outlive
the problem it was written for.

```json
{
  "schema": 1,
  "name": "Untitled",
  "tagline": "The most themeless theme ever themed.",
  "contrast_floor": 4.5,
  "contrast_exempt": {
    "muted": "the darkest band the derivation produced"
  }
}
```

## Why not symlinks

An earlier plan had `ritzpah` symlink themes into `~/.config/omarchy/themes`.
Dropped. Every theme here is a one-shot — perfected before it is merged, never
updated after — so a live link back to a working tree only means the installed
theme mutates under you while you edit. Themes are copied. The clone is not
load-bearing, and moving it breaks nothing.

The exception, if it ever arrives, is a `live` theme, whose palette is by
definition regenerated after install. That one writes into its *installed*
directory, not the repo — which keeps the working tree clean and keeps the
repo's committed palette as the proven fallback.
