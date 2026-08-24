-- Acid Vortex: spinning neon border, glow, and blur.

local active_border_color = {
  colors = {
    "rgba(ff2fd0ff)",
    "rgba(22f0ffff)",
    "rgba(3dff9eff)",
    "rgba(ffe600ff)",
    "rgba(ff2fd0ff)",
  },
  angle = 45,
}
local inactive_border_color = { colors = { "rgba(3d0f7a99)", "rgba(1a0540aa)" }, angle = 45 }

hl.config({
  general = {
    border_size = 3,
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
    rounding = 14,
    rounding_power = 4,

    dim_inactive = true,
    dim_strength = 0.25,

    shadow = {
      enabled = true,
      range = 30,
      render_power = 3,
      color = "rgba(ff2fd0aa)",
      color_inactive = "rgba(22f0ff33)",
    },

    blur = {
      enabled = true,
      size = 6,
      passes = 3,
      new_optimizations = true,
      xray = true,
      noise = 0.02,
      contrast = 1.25,
      brightness = 1.1,
      vibrancy = 0.35,
      vibrancy_darkness = 0.2,
      popups = true,
    },
  },
})

-- The whole point: the gradient angle never stops turning.
hl.curve("acidLiner", { type = "bezier", points = { { 0, 0 }, { 1, 1 } } })
hl.curve("acidBounce", { type = "bezier", points = { { 0.2, 1.35 }, { 0.4, 1.0 } } })

hl.animation({ leaf = "borderangle", enabled = true, speed = 40, bezier = "acidLiner", style = "loop" })
hl.animation({ leaf = "border", enabled = true, speed = 8, bezier = "acidLiner" })
hl.animation({ leaf = "windowsIn", enabled = true, speed = 5, bezier = "acidBounce", style = "popin 60%" })
hl.animation({ leaf = "windowsOut", enabled = true, speed = 4, bezier = "acidLiner", style = "popin 60%" })
hl.animation({ leaf = "workspaces", enabled = true, speed = 5, bezier = "acidBounce", style = "slidefadevert 25%" })

-- Frost the bar and every menu surface so the wallpaper bleeds through them.
hl.layer_rule({ match = { namespace = "^(omarchy-bar|omarchy-menu|omarchy-image-selector|omarchy-emojis|omarchy-clipboard|omarchy-keyboard-panel|omarchy-notifications|omarchy-osd|omarchy-launcher)$" }, blur = true, ignore_alpha = 0.1 })
