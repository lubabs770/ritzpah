-- Untitled: one border color, no rounding, no shadow, no blur, no motion.
--
-- Omarchy's own defaults (loaded just before this file) are already restrained.
-- They are still a look: 2px, a two-stop cyan-to-green gradient at 45 degrees,
-- and fourteen animation curves. This file removes them.

local active_border_color = "rgba(5a5a5aff)"
local inactive_border_color = "rgba(262626ff)"

hl.config({
  general = {
    -- One pixel: enough to find the edge of a window, not enough to be a
    -- design element.
    border_size = 1,

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
    rounding = 0,

    -- Dimming is an opinion about which window matters. The border says it.
    dim_inactive = false,

    shadow = { enabled = false },
    blur = { enabled = false },
  },

  -- The whole point: windows arrive where they are going to be, at the moment
  -- they are asked to. No popin, no fade, no slide, no easing curve.
  animations = { enabled = false },
})
