-- Cathode. The screen shader is the theme; everything below is the cabinet it
-- sits in. Read the "Turning it down" section of README.md before wondering
-- where the battery went.

local home = os.getenv("HOME") or ""

-- The focused window glows like the middle of a tube: hottest in the centre of
-- the gradient, falling off toward the ends. Unfocused windows are bezel.
local active_border_color = {
  colors = { "rgba(ffb000ff)", "rgba(ff7a00ff)", "rgba(ffd166ff)", "rgba(ffb000ff)" },
  angle = 90,
}
local inactive_border_color = { colors = { "rgba(3a2800cc)", "rgba(1c1408cc)" }, angle = 90 }

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
    -- Barrel distortion, scanlines, aperture grille and phosphor bloom, over
    -- the entire compositor output.
    screen_shader = home .. "/.local/state/omarchy/current/theme/phosphor.frag",

    -- A tube corner is not a circle. rounding_power 3 gives the flattened,
    -- squarish curve that glass actually has, instead of a lozenge.
    rounding = 16,
    rounding_power = 3,

    -- The unfocused window is the part of the screen the gun is not driving
    -- as hard.
    dim_inactive = true,
    dim_strength = 0.3,

    shadow = {
      enabled = true,
      range = 30,
      render_power = 3,
      color = "rgba(ffb00066)",
      color_inactive = "rgba(00000099)",
    },

    -- Light blur only. The shader is already doing the smearing; stacking a
    -- heavy blur under it turns text into a warm fog.
    blur = {
      enabled = true,
      size = 5,
      passes = 2,
      new_optimizations = true,
      noise = 0.03,
      contrast = 1.1,
      brightness = 1.05,
      vibrancy = 0.2,
      vibrancy_darkness = 0.0,
      popups = true,
    },
  },

  -- A time-driven screen shader only advances when Hyprland draws a frame, and
  -- by default it only redraws the damaged region -- so the roll bar, the hum
  -- and the snow would all freeze wherever the screen is still. Full damage
  -- forces the whole output to re-render every frame, which is what keeps the
  -- tube alive, and is also why this theme costs real battery.
  -- (misc.vfr was the other half of this trick; it went away in Hyprland 0.56.)
  debug = {
    damage_tracking = 0,
  },
})

-- Deflection is fast and then it rings. Windows snap most of the way and
-- overshoot slightly, the way a beam settles after a big jump.
hl.curve("crtSnap", { type = "bezier", points = { { 0.05, 0.9 }, { 0.1, 1.05 } } })
hl.curve("crtRing", { type = "bezier", points = { { 0.2, 1.35 }, { 0.6, 1.0 } } })
hl.curve("crtDrain", { type = "bezier", points = { { 0.7, 0.0 }, { 1.0, 0.4 } } })

hl.animation({ leaf = "borderangle", enabled = true, speed = 40, bezier = "crtSnap", style = "loop" })
hl.animation({ leaf = "border", enabled = true, speed = 6, bezier = "crtSnap" })
hl.animation({ leaf = "windows", enabled = true, speed = 4, bezier = "crtRing" })
-- A window opening is the tube warming up: a bright line that expands.
hl.animation({ leaf = "windowsIn", enabled = true, speed = 4, bezier = "crtRing", style = "popin 40%" })
-- Closing is the opposite, and faster, like the picture collapsing at power-off.
hl.animation({ leaf = "windowsOut", enabled = true, speed = 3, bezier = "crtDrain", style = "popin 60%" })
hl.animation({ leaf = "workspaces", enabled = true, speed = 4, bezier = "crtSnap", style = "slide" })
hl.animation({ leaf = "specialWorkspace", enabled = true, speed = 4, bezier = "crtSnap", style = "slidevert" })
hl.animation({ leaf = "layers", enabled = true, speed = 3, bezier = "crtSnap" })
hl.animation({ leaf = "fade", enabled = true, speed = 3, bezier = "crtDrain" })

-- Let the shell surfaces sit on the glass rather than above it.
hl.layer_rule({ match = { namespace = "^(omarchy-bar|omarchy-menu|omarchy-image-selector|omarchy-emojis|omarchy-clipboard|omarchy-keyboard-panel|omarchy-notifications|omarchy-osd|omarchy-launcher)$" }, blur = true, ignore_alpha = 0.1 })
