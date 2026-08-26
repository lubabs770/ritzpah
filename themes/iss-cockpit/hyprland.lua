-- ISS Cockpit. This file is the reason the theme is called `live`.
--
-- At every Hyprland config load it works out where the International Space
-- Station is and whether it is in sunlight, dresses the compositor in the
-- answer, and writes cockpit.frag by substituting the current orbital
-- arguments into cockpit.frag.in. The shader then carries the orbit forward
-- from `time` on the GPU, so nothing here has to run on a timer.
--
-- The LIVE telemetry -- cabin pressure, crewlock, array voltage, attitude --
-- does not come through this file at all. It arrives as pixels, from the
-- optional `ritzpahd` daemon, and the shader reads it out of the composited
-- frame. See TELEMETRY.md. Everything in this file is the FALLBACK: what the
-- cockpit flies on when that daemon is not running, which is the state it
-- ships in.
--
-- WHAT THIS FILE DOES TO YOUR MACHINE, since it is doing more than a theme
-- normally should and you should not have to grep for it:
--   reads  <this theme dir>/colors.toml
--   reads  <this theme dir>/cockpit.frag.in
--   writes <this theme dir>/cockpit.frag
-- That is the whole list. No network, no subprocess, no timer, no shell hook.
-- The theme dir is Omarchy's own generated copy under
-- ~/.local/state/omarchy/current/theme, which is rebuilt from scratch every
-- time you switch themes; nothing here writes to ~/.config/omarchy/themes and
-- nothing here writes outside that one directory.

local sin, cos, asin, atan = math.sin, math.cos, math.asin, math.atan
local floor, sqrt, pi = math.floor, math.sqrt, math.pi
local D2R, R2D = pi / 180.0, 180.0 / pi

local function wrap360(x) return x - 360.0 * floor(x / 360.0) end
local function sd(x) return sin(x * D2R) end
local function cd(x) return cos(x * D2R) end
local function clamp(x, lo, hi) return x < lo and lo or (x > hi and hi or x) end

local theme_dir = (os.getenv("HOME") or "") .. "/.local/state/omarchy/current/theme"

local function read_file(path)
  local handle = io.open(path, "r")
  if not handle then return nil end
  local text = handle:read("*a")
  handle:close()
  return text
end

-- ------------------------------------------------------------- palette
-- The telemetry drives the motion; the theme drives the colour. Read the
-- palette rather than restating it, so editing colors.toml actually changes
-- the cockpit instead of only changing the terminal.
local palette = {}
do
  local text = read_file(theme_dir .. "/colors.toml") or ""
  for key, hex in text:gmatch("([%w_]+)%s*=%s*\"#(%x%x%x%x%x%x)\"") do
    palette[key] = hex
  end
end

local function vec3(key, fallback)
  local hex = palette[key] or fallback
  local r = tonumber(hex:sub(1, 2), 16) / 255.0
  local g = tonumber(hex:sub(3, 4), 16) / 255.0
  local b = tonumber(hex:sub(5, 6), 16) / 255.0
  return string.format("vec3(%.5f, %.5f, %.5f)", r, g, b)
end

-- ------------------------------------------------------- the orbit
-- Mean elements for ISS (ZARYA), NORAD 25544, from the public two-line element
-- set at epoch 2026-08-25T15:51:11Z. Committed deliberately: this is the
-- fallback, and a fallback that needs the network is not a fallback.
--
-- A TLE is a snapshot. Drag lowers the station and the crew reboosts it, so
-- this drifts -- roughly a kilometre a day of along-track error, which is
-- invisible on a ground-track dot and would matter enormously if this were
-- used to point an antenna. It is not. When `ritzpahd` is running, the real
-- state vector off the live feed overwrites every number below.
--
-- Refresh with `./ritzpah iss-tle`, which is a thing you run on purpose.
local EPOCH_JD   = 2461278.160555380
local ISS_A      = 6795.9580          -- km, semi-major axis
local ISS_INC    = 51.6329            -- degrees
local ISS_RAAN0  = 316.2335           -- degrees at epoch
local ISS_RAAN_R = -4.952990364       -- deg/day, J2 nodal regression
local ISS_U0     = 0.186100           -- degrees at epoch, argument of latitude
local ISS_U_R    = 5582.347392575     -- deg/day

-- ------------------------------------------------------------- right now
local now = os.time()
local jd = now / 86400.0 + 2440587.5
local T = (jd - 2451545.0) / 36525.0
local d = jd - 2451545.0

-- Obliquity and the Sun's ecliptic longitude, Meeus 22 and 25, truncated to
-- the terms that matter at this scale. The Sun moves about a degree a day and
-- the shadow it casts is 12,700 km across; a few arcseconds are irrelevant.
local eps = 23.439291 - 0.0130042 * T
local L0 = 280.46646 + 36000.76983 * T
local Ms = 357.52911 + 35999.05029 * T
local sun_lon = wrap360(L0 + 1.914602 * sd(Ms) + 0.019993 * sd(2 * Ms))
local SUNLON_R = 36000.76983 / 36525.0 + 0.9856  -- deg/day, mean plus anomaly

-- Greenwich mean sidereal time, Meeus 12.4.
local gmst = wrap360(280.46061837 + 360.98564736629 * d + 0.000387933 * T * T)

-- Propagate the station from the TLE epoch to now.
local days_since_epoch = jd - EPOCH_JD
local raan = wrap360(ISS_RAAN0 + ISS_RAAN_R * days_since_epoch)
local u = wrap360(ISS_U0 + ISS_U_R * days_since_epoch)

local function position(u_deg, raan_deg)
  local cu, su = cd(u_deg), sd(u_deg)
  local cr, sr = cd(raan_deg), sd(raan_deg)
  local ci, si = cd(ISS_INC), sd(ISS_INC)
  return {
    ISS_A * (cr * cu - sr * su * ci),
    ISS_A * (sr * cu + cr * su * ci),
    ISS_A * (su * si),
  }
end

local pos = position(u, raan)

-- The Sun's direction in the same frame.
local sun = {
  cd(sun_lon),
  sd(sun_lon) * cd(eps),
  sd(sun_lon) * sd(eps),
}

-- In sunlight, or in the shadow? A cylinder is close enough: the penumbra is
-- about ten seconds wide at this altitude.
local EARTH_R = 6371.0
local along = pos[1] * sun[1] + pos[2] * sun[2] + pos[3] * sun[3]
local lit
if along > 0.0 then
  lit = 1.0
else
  local px = pos[1] - along * sun[1]
  local py = pos[2] - along * sun[2]
  local pz = pos[3] - along * sun[3]
  local perp = sqrt(px * px + py * py + pz * pz)
  lit = clamp((perp - (EARTH_R - 40.0)) / 80.0, 0.0, 1.0)
end

-- Subpoint, for the log line at the top of the generated shader.
local radius = sqrt(pos[1] ^ 2 + pos[2] ^ 2 + pos[3] ^ 2)
local sublat = asin(clamp(pos[3] / radius, -1, 1)) * R2D
local sublon = wrap360(atan(pos[2], pos[1]) * R2D - gmst)
if sublon > 180.0 then sublon = sublon - 360.0 end

-- --------------------------------------------------------- the shader
-- Substituted, not generated: the shader is a file you can read in the repo,
-- and this only fills in the numbers at the top of it.
local function bake()
  local template = read_file(theme_dir .. "/cockpit.frag.in")
  if not template then return false end

  -- Hyprland's shader clock is seconds since the compositor started, and the
  -- instance signature carries the unix time it started at. So the shader can
  -- be told exactly what its own clock will read at this instant.
  local t_load = 0.0
  local his = os.getenv("HYPRLAND_INSTANCE_SIGNATURE") or ""
  local started = tonumber(his:match("^%x+_(%d+)"))
  if started then t_load = now - started end
  if t_load < 0 then t_load = 0.0 end

  local function g(x) return string.format("%.9f", x) end
  local values = {
    T_LOAD = g(t_load),
    GMST0 = g(gmst), GMST_R = g(360.98564736629),
    SUNLON0 = g(sun_lon), SUNLON_R = g(SUNLON_R),
    EPS = g(eps),
    ISS_A = g(ISS_A), ISS_INC = g(ISS_INC),
    ISS_RAAN0 = g(raan), ISS_RAAN_R = g(ISS_RAAN_R),
    ISS_U0 = g(u), ISS_U_R = g(ISS_U_R),
    C_ACCENT = vec3("accent", "4fd6c8"),
    C_FG     = vec3("foreground", "cfdae6"),
    C_MUTED  = vec3("muted", "8d9cad"),
    C_RED    = vec3("red", "ff6b5e"),
    C_ORANGE = vec3("orange", "ffa657"),
    C_GREEN  = vec3("green", "5ee08a"),
    C_CYAN   = vec3("cyan", "5fd8e0"),
    C_BLUE   = vec3("blue", "7fb0ff"),
  }

  local out = template:gsub("@@([%w_]+)@@", function(key)
    return values[key] or ("/* unbaked " .. key .. " */ 0.0")
  end)

  -- Refuse to install a shader that is not whole. An unsubstituted @@KEY@@ is
  -- not valid GLSL, and a template that does not open with #version cannot be
  -- one either -- in the ES profile nothing at all is allowed in front of that
  -- line, not even a comment, which is why the header goes after it.
  local version, body = out:match("^(#version[^\n]*\n)(.*)$")
  if not version or out:find("@@") then return false end

  -- Write somewhere else and rename into place. Hyprland reads this file while
  -- applying the very config that is writing it, so opening the real path with
  -- "w" truncates a file the compositor may be about to read, and it would get
  -- half a shader. A rename on the same filesystem is atomic: the compositor
  -- sees the old shader or the new one and never a torn one.
  --
  -- This theme sets damage_tracking = 0, so a shader that fails to compile is
  -- logged sixty times a second into a log in a tmpfs -- which is how a
  -- cosmetic bug becomes a full disk. Same reasoning as Lunation; same fix.
  local tmp = theme_dir .. "/cockpit.frag.new"
  local handle = io.open(tmp, "w")
  if not handle then return false end

  local ok = handle:write(version) and handle:write(string.format(
    "// Baked %s UTC.\n" ..
    "// ISS by propagated TLE: %.2f, %.2f, altitude %.0f km, %s.\n" ..
    "// This is the FALLBACK orbit. Run ritzpahd and the real station\n" ..
    "// overwrites all of it -- see TELEMETRY.md.\n",
    os.date("!%Y-%m-%d %H:%M:%S", now),
    sublat, sublon, radius - EARTH_R,
    lit > 0.5 and "in sunlight" or "in eclipse"))
    and handle:write(body)
  handle:close()

  if not ok then
    os.remove(tmp)
    return false
  end
  if not os.rename(tmp, theme_dir .. "/cockpit.frag") then
    os.remove(tmp)
    return false
  end
  return true
end

local ok_bake, baked = pcall(bake)
local have_shader = ok_bake and baked

-- ------------------------------------------------------------ the look
local function rgba(r, g, b, a)
  return string.format("rgba(%02x%02x%02x%02x)",
    clamp(floor(r * 255 + 0.5), 0, 255),
    clamp(floor(g * 255 + 0.5), 0, 255),
    clamp(floor(b * 255 + 0.5), 0, 255),
    clamp(floor(a * 255 + 0.5), 0, 255))
end

local function hex_rgb(key, fallback)
  local hex = palette[key] or fallback
  return tonumber(hex:sub(1, 2), 16) / 255.0,
         tonumber(hex:sub(3, 4), 16) / 255.0,
         tonumber(hex:sub(5, 6), 16) / 255.0
end

-- The focused window is lit the way the station is lit. In sunlight the
-- borders take the panel's own backlight colour; in eclipse they fall back to
-- the deep blue of the night side, which is the colour of every photograph
-- taken out of the Cupola with the lights off.
local ar, ag, ab = hex_rgb("accent", "4fd6c8")
local br, bg, bb = hex_rgb("blue", "7fb0ff")
local function mix(a, b, t) return a + (b - a) * t end

local hi = rgba(mix(br * 0.55, ar, lit), mix(bg * 0.55, ag, lit), mix(bb * 0.7, ab, lit), 1.0)
local mid = rgba(mix(br * 0.30, ar * 0.62, lit), mix(bg * 0.32, ag * 0.66, lit),
                 mix(bb * 0.45, ab * 0.86, lit), 1.0)
local lo = rgba(0.05 + 0.06 * lit, 0.08 + 0.07 * lit, 0.14 + 0.08 * lit, 1.0)

-- The gradient runs along the orbit: the bright end leads, the way the
-- station is always about to arrive somewhere.
local border_angle = floor(wrap360(u)) % 360

local active_border = { colors = { hi, mid, lo }, angle = border_angle }
local inactive_border = {
  colors = { rgba(0.05, 0.07, 0.12, 0.85), rgba(0.02, 0.03, 0.06, 0.85) },
  angle = border_angle,
}

hl.config({
  general = {
    border_size = 2,
    col = { active_border = active_border, inactive_border = inactive_border },
  },

  group = {
    col = { border_active = active_border, border_inactive = inactive_border },
  },

  decoration = {
    -- Only if it is actually there. A screen_shader pointing at a file that
    -- does not exist is a config error, and a theme that cannot compute an
    -- orbit should still be a theme.
    screen_shader = have_shader and (theme_dir .. "/cockpit.frag") or nil,

    rounding = 6,
    rounding_power = 2,

    -- Unfocused windows sit further from the window. Slightly more so at
    -- night, because at night the only light in here is the panel.
    dim_inactive = true,
    dim_strength = 0.14 + 0.10 * (1.0 - lit),

    shadow = {
      enabled = true,
      range = 18,
      render_power = 2,
      offset = "0 4",
      color = rgba(0.0, 0.0, 0.0, 0.66),
      color_inactive = rgba(0.0, 0.0, 0.0, 0.80),
    },

    blur = {
      enabled = true,
      size = 5,
      passes = 3,
      new_optimizations = true,
      noise = 0.012,
      contrast = 1.02,
      brightness = 0.92,
      vibrancy = 0.10,
      vibrancy_darkness = 0.30,
      popups = true,
    },
  },

  -- A screen shader only advances when Hyprland draws a frame, and by default
  -- it only redraws what changed -- so on a still screen the orbit would
  -- freeze wherever nothing is happening, and worse, the telemetry strip
  -- would stop being re-read. Full damage forces the whole output every
  -- frame. This is the battery cost, and it is the price of a live panel.
  debug = {
    damage_tracking = 0,
  },
})

-- THE LOAD-BEARING LAYER RULE. The telemetry strip is 64x2 real pixels that
-- the shader reads out of the composited frame, so anything that blurs, dims,
-- rounds or fades it corrupts the channel and the panel goes STALE for
-- reasons that look like a bug in the daemon. Rounding is the sneaky one: a
-- corner radius alpha-blends the first texel, which is the magic number.
hl.layer_rule({
  match = { namespace = "^ritzpah-iss-telemetry$" },
  blur = false,
  ignore_alpha = 0.0,
  no_anim = true,
  dim_around = 0.0,
  xray = false,
})

-- Everything moves the way something in orbit moves: no snap, no bounce, a
-- long ease out of a fast start.
hl.curve("orbit", { type = "bezier", points = { { 0.16, 0.84 }, { 0.24, 1.0 } } })
hl.curve("thrust", { type = "bezier", points = { { 0.4, 0.0 }, { 0.2, 1.0 } } })

hl.animation({ leaf = "borderangle", enabled = false })
hl.animation({ leaf = "border", enabled = true, speed = 10, bezier = "orbit" })
hl.animation({ leaf = "windows", enabled = true, speed = 5, bezier = "orbit" })
hl.animation({ leaf = "windowsIn", enabled = true, speed = 6, bezier = "thrust", style = "popin 90%" })
hl.animation({ leaf = "windowsOut", enabled = true, speed = 5, bezier = "orbit", style = "popin 92%" })
hl.animation({ leaf = "workspaces", enabled = true, speed = 6, bezier = "orbit", style = "slide" })
hl.animation({ leaf = "specialWorkspace", enabled = true, speed = 6, bezier = "orbit", style = "slidevert" })
hl.animation({ leaf = "layers", enabled = true, speed = 4, bezier = "orbit" })
hl.animation({ leaf = "fade", enabled = true, speed = 5, bezier = "orbit" })

-- Let the shell surfaces sit under the canopy rather than on top of it.
hl.layer_rule({ match = { namespace = "^(omarchy-bar|omarchy-menu|omarchy-image-selector|omarchy-emojis|omarchy-clipboard|omarchy-keyboard-panel|omarchy-notifications|omarchy-osd|omarchy-launcher)$" }, blur = true, ignore_alpha = 0.1 })
