-- Casino Carpet: a six-stop border that never stops turning, rounding with no
-- shame in it, and animations wound up past the point of usefulness.
--
-- The border is the theme's whole argument in one object. A real floor uses a
-- dark keyline between every pair of saturated figures, because two high-chroma
-- colours meeting directly produce a vibrating edge the eye cannot resolve.
-- This border does the opposite on purpose: magenta, teal, gold and red, in
-- that order, with no keyline anywhere, rotating. Every boundary in it is one
-- of the pairs a carpet designer would have separated, and the rotation means
-- you get all of them in turn.

local active_border_color = {
  colors = {
    "rgba(ff3ad6ff)", -- the swirls
    "rgba(22e0d0ff)", -- the teal
    "rgba(ffc61fff)", -- the gold
    "rgba(ff1f2eff)", -- the red that should not be here
    "rgba(ff3ad6ff)", -- back to magenta, so the loop closes cleanly
    "rgba(22e0d0ff)",
  },
  angle = 45,
}

-- Inactive windows drop to the aubergine the figures sit on. An unfocused
-- window on this theme is the floor, and the floor is the one place your eye
-- is allowed to rest.
local inactive_border_color = { colors = { "rgba(5a0d78ff)", "rgba(2c0a4aff)" }, angle = 45 }

hl.config({
  general = {
    -- Four pixels. Three reads as a border; four reads as trim.
    border_size = 4,
    col = {
      active_border = active_border_color,
      inactive_border = inactive_border_color,
    },
  },

  group = {
    col = {
      border_active = active_border_color,
      border_inactive = inactive_border_color,
    },
  },

  decoration = {
    -- Loud rounding, as ordered. rounding_power below 2 pushes the corner
    -- towards a squircle, which at this radius stops looking like a rounded
    -- rectangle and starts looking like a casino chip.
    rounding = 20,
    rounding_power = 2,

    -- Unfocused windows sink into the floor rather than merely dimming.
    dim_inactive = true,
    dim_strength = 0.35,

    shadow = {
      enabled = true,
      range = 34,
      render_power = 3,
      -- Magenta bloom on the focused window, teal on everything else, so the
      -- two loudest hues in the palette are always both on screen and never
      -- on the same window.
      color = "rgba(ff3ad6bb)",
      color_inactive = "rgba(22e0d033)",
    },

    blur = {
      enabled = true,
      size = 7,
      passes = 3,
      new_optimizations = true,
      xray = true,
      noise = 0.03,
      contrast = 1.3,
      brightness = 1.05,
      -- Vibrancy is the knob that decides whether a blurred wallpaper keeps
      -- its chroma or turns into grey soup. The wallpapers are the theme, so
      -- it goes up rather than down.
      vibrancy = 0.45,
      vibrancy_darkness = 0.15,
      popups = true,
    },
  },
})

-- Animations turned up. `borderangle` at speed 55 in loop style is the piece
-- that matters: the gradient rotates continuously, so the four hues trade
-- places on every edge of the focused window for as long as it is focused.
hl.curve("carpetLiner", { type = "bezier", points = { { 0, 0 }, { 1, 1 } } })
hl.curve("carpetBounce", { type = "bezier", points = { { 0.16, 1.5 }, { 0.38, 1.0 } } })

hl.animation({ leaf = "borderangle", enabled = true, speed = 55, bezier = "carpetLiner", style = "loop" })
hl.animation({ leaf = "border", enabled = true, speed = 9, bezier = "carpetLiner" })
hl.animation({ leaf = "windowsIn", enabled = true, speed = 5, bezier = "carpetBounce", style = "popin 55%" })
hl.animation({ leaf = "windowsOut", enabled = true, speed = 4, bezier = "carpetLiner", style = "popin 55%" })
hl.animation({ leaf = "workspaces", enabled = true, speed = 5, bezier = "carpetBounce", style = "slidefadevert 30%" })
hl.animation({ leaf = "fade", enabled = true, speed = 6, bezier = "carpetLiner" })

-- Frost every shell surface so the carpet reads through the bar and the menus.
-- On a theme whose wallpaper is this busy, an opaque bar would be the only
-- calm rectangle on the screen, and calm is not what was ordered.
hl.layer_rule({ match = { namespace = "^(omarchy-bar|omarchy-menu|omarchy-image-selector|omarchy-emojis|omarchy-clipboard|omarchy-keyboard-panel|omarchy-notifications|omarchy-osd|omarchy-launcher)$" }, blur = true, ignore_alpha = 0.1 })
