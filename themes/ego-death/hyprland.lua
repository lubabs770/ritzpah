-- Ego Death. Read the "Turning it down" section of README.md before wondering
-- why the fans are on.

local home = os.getenv("HOME") or ""

local active_border_color = {
  colors = {
    "rgba(ff0044ff)", "rgba(ff7a00ff)", "rgba(ffe800ff)", "rgba(00ff6aff)",
    "rgba(00f5ffff)", "rgba(3d5bffff)", "rgba(ff00d4ff)", "rgba(ff0044ff)",
  },
  angle = 45,
}
local inactive_border_color = { colors = { "rgba(2a0055cc)", "rgba(6a00b8cc)" }, angle = 45 }

hl.config({
  general = {
    border_size = 5,
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
    -- The whole desktop, warped and hue-cycled every frame.
    screen_shader = home .. "/.local/state/omarchy/current/theme/liquid.frag",

    rounding = 28,
    rounding_power = 8,

    dim_inactive = true,
    dim_strength = 0.45,

    shadow = {
      enabled = true,
      range = 45,
      render_power = 2,
      color = "rgba(ff00d4cc)",
      color_inactive = "rgba(00f5ff44)",
    },

    blur = {
      enabled = true,
      size = 10,
      passes = 4,
      new_optimizations = true,
      xray = true,
      noise = 0.05,
      contrast = 1.5,
      brightness = 1.2,
      vibrancy = 0.6,
      vibrancy_darkness = 0.0,
      popups = true,
    },
  },

  -- A time-driven screen shader only advances when Hyprland draws a frame, and
  -- by default it only redraws the damaged region -- so the melt would freeze
  -- wherever the screen is still. Full damage forces the whole output to
  -- re-render, which is what makes it move, and is also why this theme costs
  -- real battery. (misc.vfr is gone as of Hyprland 0.56; this is the knob.)
  debug = {
    damage_tracking = 0,
  },
})

hl.curve("egoLiner", { type = "bezier", points = { { 0, 0 }, { 1, 1 } } })
hl.curve("egoWobble", { type = "bezier", points = { { 0.16, 1.6 }, { 0.5, 1.0 } } })
hl.curve("egoOoze", { type = "bezier", points = { { 0.85, 0.05 }, { 0.15, 1.0 } } })

hl.animation({ leaf = "borderangle", enabled = true, speed = 100, bezier = "egoLiner", style = "loop" })
hl.animation({ leaf = "border", enabled = true, speed = 12, bezier = "egoLiner" })
hl.animation({ leaf = "windows", enabled = true, speed = 7, bezier = "egoWobble" })
hl.animation({ leaf = "windowsIn", enabled = true, speed = 7, bezier = "egoWobble", style = "popin 20%" })
hl.animation({ leaf = "windowsOut", enabled = true, speed = 6, bezier = "egoOoze", style = "popin 20%" })
hl.animation({ leaf = "workspaces", enabled = true, speed = 8, bezier = "egoWobble", style = "slidevert" })
hl.animation({ leaf = "specialWorkspace", enabled = true, speed = 8, bezier = "egoWobble", style = "slidevert" })
hl.animation({ leaf = "layers", enabled = true, speed = 6, bezier = "egoWobble" })
hl.animation({ leaf = "fade", enabled = true, speed = 6, bezier = "egoOoze" })

-- Frost every shell surface, so the bar and menus dissolve into the wallpaper.
hl.layer_rule({ match = { namespace = "^(omarchy-bar|omarchy-menu|omarchy-image-selector|omarchy-emojis|omarchy-clipboard|omarchy-keyboard-panel|omarchy-notifications|omarchy-osd|omarchy-launcher)$" }, blur = true, ignore_alpha = 0.05 })
