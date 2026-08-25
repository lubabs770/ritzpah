-- Blueprint. The one theme in this repo with nothing running on top of the
-- compositor: no screen shader, no full-damage redraws, no border that spins.
-- Everything below is either a line weight or a stopwatch reading.

-- ISO 128 gives line weights as a ratio, not a value: thin is half of thick,
-- and every line on a sheet is one or the other. Thick is the visible edge of
-- a solid object -- which is exactly what a window border is -- so the border
-- is the thick line and 2px is the whole scale.
local LINE_THICK = 2

-- One stop, no angle. A gradient along a line means the line changes weight
-- along its length, and a line that changes weight along its length means
-- something else on a drawing.
local active_border_color = "rgba(4dd2ffff)"
local inactive_border_color = "rgba(1d3b55ff)"

hl.config({
  general = {
    border_size = LINE_THICK,

    col = {
      active_border = active_border_color,
      inactive_border = inactive_border_color,
    },

    -- A drafting board has a grid and everything on it lands on the grid.
    -- Floating windows snap to each other and to the edge of the sheet from
    -- 10px out, and overlap their borders when they meet so two adjacent
    -- windows share one line instead of drawing two.
    snap = {
      enabled = true,
      window_gap = 10,
      monitor_gap = 10,
      border_overlap = true,
    },

    -- Grab the border to resize. On a 2px border that is a small target, and
    -- it is still the right call: the border is the edge of the object, so the
    -- edge of the object is what you pull.
    resize_on_border = true,
  },

  group = {
    col = {
      border_active = active_border_color,
      border_inactive = inactive_border_color,
    },
  },

  decoration = {
    -- Drawings have corners. Corners are where two edges meet, and two edges
    -- that meet at a radius have a radius called out next to them.
    rounding = 0,

    -- No shadow: a shadow is a claim that one window is physically above
    -- another, and on a flat sheet nothing is above anything.
    shadow = { enabled = false },

    -- No blur: the entire argument of this theme is that you can read what is
    -- on the screen, and blur is a machine for making that less true.
    blur = { enabled = false },

    -- The one exception to "no effects". Dim is not decoration here, it is the
    -- sheet under the one you are working on -- still visible, still legible,
    -- clearly not the one you are drawing on. Body text in a dimmed window
    -- measures 10.63:1, comfortably over the theme's 7:1 floor.
    --
    -- Comments are the exception, and it is worth knowing: dark_foreground was
    -- placed at exactly 7.07:1, so 15% off both it and the background drops it
    -- to 5.36:1 -- still AA, no longer AAA. If you read code in unfocused
    -- windows all day, set dim_inactive = false in your own looknfeel.lua and
    -- the floor holds everywhere.
    dim_inactive = true,
    dim_strength = 0.15,
  },

  animations = { enabled = true },
})

-- Motion, timed rather than styled.
--
-- Omarchy's defaults run windows at 379ms and layers at 381ms on an
-- ease-out-quint, which is a lovely curve and is also long enough that you
-- watch it. Nothing in this theme runs longer than 120ms, which is under the
-- ~150ms at which a change stops reading as motion and starts reading as
-- having already happened. Over an eight-hour day that is the difference
-- between a desk and a screensaver.
--
-- The curves are the two motions a drafting machine actually has.
--   ruleSlide: dead linear. A parallel rule pushed along its track moves at
--              whatever speed your hand moves it and does not accelerate.
--   ruleStop:  quick off the mark, decelerating into position, no overshoot.
--              A set square brought up against a stop does not bounce.
hl.curve("ruleSlide", { type = "bezier", points = { { 0.0, 0.0 }, { 1.0, 1.0 } } })
hl.curve("ruleStop", { type = "bezier", points = { { 0.16, 0.0 }, { 0.24, 1.0 } } })

hl.animation({ leaf = "global", enabled = true, speed = 1.2, bezier = "ruleStop" })

-- A flat border has no angle to rotate, so this leaf has nothing to do.
hl.animation({ leaf = "borderangle", enabled = false })
hl.animation({ leaf = "border", enabled = true, speed = 1.0, bezier = "ruleStop" })

-- Windows slide. They do not grow: a window that scales up from 87% is a
-- drawing being enlarged, and enlarging a drawing changes its scale, which is
-- the one thing a scale bar exists to stop you doing.
hl.animation({ leaf = "windows", enabled = true, speed = 1.2, bezier = "ruleStop" })
hl.animation({ leaf = "windowsIn", enabled = true, speed = 1.2, bezier = "ruleStop", style = "slide" })
hl.animation({ leaf = "windowsOut", enabled = true, speed = 1.0, bezier = "ruleSlide", style = "slide" })

-- Workspaces are sheets on the same table, so switching one is a slide at
-- constant speed. Omarchy leaves this leaf off entirely; Blueprint turns it on
-- precisely because the direction of the slide tells you which way you went.
hl.animation({ leaf = "workspaces", enabled = true, speed = 1.2, bezier = "ruleSlide", style = "slide" })
hl.animation({ leaf = "specialWorkspace", enabled = true, speed = 1.2, bezier = "ruleSlide", style = "slidevert" })

-- Menus, the launcher and notifications fade. They are overlays laid on the
-- sheet, not objects on it, and an overlay arriving by sliding would imply it
-- came from somewhere.
hl.animation({ leaf = "layers", enabled = true, speed = 1.0, bezier = "ruleStop", style = "fade" })
hl.animation({ leaf = "fade", enabled = true, speed = 1.0, bezier = "ruleStop" })

-- Group tabs are the tab index down the edge of a drawing set: readable at a
-- glance, one line of indicator, no gradient.
hl.config({
  group = {
    groupbar = {
      font_family = "monospace",
      font_size = 12,
      font_weight_active = "bold",
      font_weight_inactive = "normal",
      height = 20,
      indicator_height = 2,
      indicator_gap = 4,
      gradients = false,
      text_color = "rgb(0b1a2b)",
      text_color_inactive = "rgb(8fb4c9)",
      col = {
        active = "rgba(4dd2ffff)",
        inactive = "rgba(12293fff)",
      },
    },
  },
})

-- Gaps and per-window opacity are deliberately not set here. They belong to
-- the human, and this file is loaded before ~/.config/hypr/looknfeel.lua, so
-- everything above is an opening offer rather than a decision.
