-- Lunation. This file is the only reason the theme is called `live`.
--
-- Every other theme in this collection is a fixed set of colours. This one
-- computes, at each Hyprland config load, where the Moon actually is over the
-- machine it is running on -- altitude, azimuth, phase, distance, libration --
-- and then dresses the compositor in the answer: the window borders take the
-- colour of moonlight after however much atmosphere it is behind, their
-- gradient runs toward it, and window shadows fall away from it.
--
-- It also writes sky.frag, the screen shader, by substituting the current
-- orbital arguments into sky.frag.in. See the header of that file for why the
-- work is split the way it is: the linear part is baked here, the non-linear
-- part is evaluated on the GPU from `time`, and nothing has to run on a timer.
--
-- WHAT THIS FILE DOES TO YOUR MACHINE, since it is doing more than a theme
-- normally should and you should not have to grep for it:
--   reads  /etc/localtime (as a symlink target only, never its contents)
--   reads  /usr/share/zoneinfo/zone1970.tab
--   reads  ~/.config/omarchy/lunation.conf, if you made one
--   reads  <this theme dir>/sky.frag.in
--   writes <this theme dir>/sky.frag
-- That is the whole list. No network, no subprocess, no timer, no shell hook.
-- The theme dir is Omarchy's own generated copy under
-- ~/.local/state/omarchy/current/theme, which is rebuilt from scratch every
-- time you switch themes; nothing here writes to ~/.config/omarchy/themes and
-- nothing here writes outside that one directory.

local sin, cos, tan, asin, acos, atan = math.sin, math.cos, math.tan, math.asin, math.acos, math.atan
local floor, sqrt, pi = math.floor, math.sqrt, math.pi
local D2R, R2D = pi / 180.0, 180.0 / pi

local function wrap360(x) return x - 360.0 * floor(x / 360.0) end
local function wrap180(x) return wrap360(x + 180.0) - 180.0 end
local function sd(x) return sin(x * D2R) end
local function cd(x) return cos(x * D2R) end
local function clamp(x, lo, hi) return x < lo and lo or (x > hi and hi or x) end

-- ------------------------------------------------------------------ where
-- Nobody wants to configure their latitude to get a theme. So: an override if
-- you want one, otherwise the coordinates tzdata already keeps for your
-- timezone -- which is the centre of the zone's largest city, and therefore
-- wrong by up to a couple of hundred kilometres. For the Moon that is worth
-- well under a degree of altitude, which is less than the refraction at the
-- horizon, so it does not matter and it costs you nothing to set up.
--
-- If even that fails you are placed at the Royal Observatory, Greenwich, which
-- is the correct place to be when nobody knows where you are.
local function read_line(path)
  local handle = io.open(path, "r")
  if not handle then return nil end
  local text = handle:read("*a")
  handle:close()
  return text
end

local function sexagesimal(text, degree_digits)
  -- ISO 6709, as tzdata writes it: +DDMMSS or +DDMM, no separators.
  local sign = text:sub(1, 1) == "-" and -1 or 1
  local body = text:sub(2)
  local deg = tonumber(body:sub(1, degree_digits)) or 0
  local minute = tonumber(body:sub(degree_digits + 1, degree_digits + 2)) or 0
  local second = tonumber(body:sub(degree_digits + 3, degree_digits + 4)) or 0
  return sign * (deg + minute / 60.0 + second / 3600.0)
end

local function observer()
  local home = os.getenv("HOME") or ""
  local override = read_line(home .. "/.config/omarchy/lunation.conf")
  if override then
    local lat = tonumber(override:match("lat%s*=%s*(-?[%d%.]+)"))
    local lon = tonumber(override:match("lon%s*=%s*(-?[%d%.]+)"))
    if lat and lon then return lat, lon, "lunation.conf" end
  end

  local table_text = read_line("/usr/share/zoneinfo/zone1970.tab")
  if not table_text then return 51.4779, -0.0015, "Greenwich (no zone table)" end

  local function parse(coords)
    local lat_text, lon_text = coords:match("^([%+%-]%d+)([%+%-]%d+)$")
    if not lat_text then return nil end
    return sexagesimal(lat_text, 2), sexagesimal(lon_text, 3)
  end

  local function coords_for(zone)
    for line in table_text:gmatch("[^\n]+") do
      if line:sub(1, 1) ~= "#" then
        local coords, names = line:match("^%S+\t(%S+)\t(%S+)")
        if coords and names then
          for name in (names .. ","):gmatch("([^,]+),?") do
            if name == zone then return parse(coords) end
          end
        end
      end
    end
  end

  -- The cheap, exact routes first.
  local zone = os.getenv("TZ")
  if not zone or zone == "" then
    local tz = read_line("/etc/timezone")
    if tz then zone = tz:match("^%s*(.-)%s*$") end
  end
  if zone and zone ~= "" then
    local lat, lon = coords_for((zone:gsub("^:", "")))
    if lat then return lat, lon, "TZ: " .. zone end
  end

  -- Otherwise: /etc/localtime is a symlink, and Lua cannot read a symlink. It
  -- can read bytes, though, and the file is byte-identical to the zoneinfo
  -- file it points at. So identify the zone by matching its contents against
  -- the tree. About three hundred small reads, once, when Hyprland loads its
  -- config -- not on a timer, and not on a keystroke.
  local mine = read_line("/etc/localtime")
  if mine then
    for line in table_text:gmatch("[^\n]+") do
      if line:sub(1, 1) ~= "#" then
        local coords, names = line:match("^%S+\t(%S+)\t(%S+)")
        if coords and names then
          local zone_name = names:match("^([^,]+)")
          if read_line("/usr/share/zoneinfo/" .. zone_name) == mine then
            local lat, lon = parse(coords)
            if lat then return lat, lon, "zoneinfo bytes: " .. zone_name end
          end
        end
      end
    end
  end

  -- Nobody knows where you are, so you are at the Royal Observatory, which is
  -- the correct place to be when nobody knows where you are.
  return 51.4779, -0.0015, "Royal Observatory, Greenwich (nothing else was knowable)"
end

-- ------------------------------------------------------- the ephemeris
-- Meeus, Astronomical Algorithms, chapters 22, 25, 47 and 53, truncated. The
-- longitude series keeps twenty terms of sixty, latitude eleven of sixty,
-- distance fourteen. Checked against Meeus's own worked example 47.a (1992
-- April 12.0 TD): this gets lambda 133.1653 against his 133.162655, beta
-- -3.2309 against -3.229126, and Delta 368413 km against 368409.7. Eleven
-- arcseconds and four kilometres. The Moon is 1900 arcseconds across.

local function arguments(T)
  return {
    Lp = 218.3164477 + 481267.88123421 * T - 0.0015786 * T * T,
    D  = 297.8501921 + 445267.1114034 * T - 0.0018819 * T * T,
    Ms = 357.5291092 + 35999.0502909 * T - 0.0001536 * T * T,
    Mp = 134.9633964 + 477198.8675055 * T + 0.0087414 * T * T,
    F  =  93.2720950 + 483202.0175233 * T - 0.0036539 * T * T,
    Om = 125.0445479 - 1934.1362891 * T,
    L0 = 280.46646 + 36000.76983 * T + 0.0003032 * T * T,
  }
end

local function moon(a)
  local D, Ms, Mp, F = a.D, a.Ms, a.Mp, a.F
  local lon = a.Lp
    + 6.288774 * sd(Mp) + 1.274027 * sd(2*D - Mp) + 0.658314 * sd(2*D)
    + 0.213618 * sd(2*Mp) - 0.185116 * sd(Ms) - 0.114332 * sd(2*F)
    + 0.058793 * sd(2*D - 2*Mp) + 0.057066 * sd(2*D - Ms - Mp)
    + 0.053322 * sd(2*D + Mp) + 0.045758 * sd(2*D - Ms)
    - 0.040923 * sd(Ms - Mp) - 0.034720 * sd(D) - 0.030383 * sd(Ms + Mp)
    + 0.015327 * sd(2*D - 2*F) - 0.012528 * sd(Mp + 2*F) + 0.010980 * sd(Mp - 2*F)
    + 0.010675 * sd(4*D - Mp) + 0.010034 * sd(3*Mp) + 0.008548 * sd(4*D - 2*Mp)
  local lat = 5.128122 * sd(F) + 0.280602 * sd(Mp + F) + 0.277693 * sd(Mp - F)
    + 0.173237 * sd(2*D - F) + 0.055413 * sd(2*D - Mp + F) + 0.046271 * sd(2*D - Mp - F)
    + 0.032573 * sd(2*D + F) + 0.017198 * sd(2*Mp + F) + 0.009266 * sd(2*D + Mp - F)
    + 0.008822 * sd(2*Mp - F) + 0.008216 * sd(2*D - Ms - F)
  local dist = 385000.56
    - 20905.355 * cd(Mp) - 3699.111 * cd(2*D - Mp) - 2955.968 * cd(2*D)
    - 569.925 * cd(2*Mp) + 48.888 * cd(Ms) - 3.149 * cd(2*F)
    + 246.158 * cd(2*D - 2*Mp) - 152.138 * cd(2*D - Ms - Mp) - 170.733 * cd(2*D + Mp)
    - 204.586 * cd(2*D - Ms) - 129.620 * cd(Ms - Mp) + 108.743 * cd(D)
    + 104.755 * cd(Ms + Mp) + 79.661 * cd(Mp - 2*F)
  return wrap360(lon), lat, dist
end

local function sun(a)
  local Ms = a.Ms
  local C = 1.914602 * sd(Ms) + 0.019993 * sd(2*Ms) + 0.000289 * sd(3*Ms)
  local e = 0.016708634
  local r = 1.000001018 * (1 - e * e) / (1 + e * cd(Ms + C))
  return wrap360(a.L0 + C), r * 149597870.7
end

local function equatorial(lon, lat, eps)
  local sl, cl, sb, cb = sd(lon), cd(lon), sd(lat), cd(lat)
  local se, ce = sd(eps), cd(eps)
  local ra = wrap360(atan(sl * ce - (sb / cb) * se, cl) * R2D)
  local dec = asin(sb * ce + cb * se * sl) * R2D
  return ra, dec
end

local function horizontal(ra, dec, lst, phi)
  local H = lst - ra
  local sH, cH, sD, cD = sd(H), cd(H), sd(dec), cd(dec)
  local sP, cP = sd(phi), cd(phi)
  local alt = asin(sD * sP + cD * cP * cH) * R2D
  local azS = atan(sH * cD, cH * sP * cD - sD * cP) * R2D
  return alt, wrap360(azS + 180.0), H
end

-- ------------------------------------------------------------- right now
local now = os.time()
local jd = now / 86400.0 + 2440587.5
local T = (jd - 2451545.0) / 36525.0
local args = arguments(T)
local eps = 23.439291 - 0.0130042 * T

local mlon, mlat, mdist = moon(args)
local slon, sdist = sun(args)
local mra, mdec = equatorial(mlon, mlat, eps)
local sra, sdec = equatorial(slon, 0.0, eps)

-- Greenwich mean sidereal time, Meeus 12.4.
local d = jd - 2451545.0
local gmst = wrap360(280.46061837 + 360.98564736629 * d + 0.000387933 * T * T)

local lat, lon, source = observer()
local lst = gmst + lon
local alt, az = horizontal(mra, mdec, lst, lat)
local salt, saz = horizontal(sra, sdec, lst, lat)

local elong = acos(clamp(cd(mlat) * cd(mlon - slon), -1, 1)) * R2D
local phase_angle = atan(sdist * sd(elong), mdist - sdist * cd(elong)) * R2D
local illum = 0.5 * (1.0 + cd(phase_angle))
-- Waxing or waning: the Moon is waxing while it is running ahead of the Sun by
-- less than half a turn.
local waxing = wrap360(mlon - slon) < 180.0

-- Extinction, so the borders are the colour the Moon actually is right now
-- rather than the colour it would be if it were overhead.
local function airmass(a)
  local s = sd(a < -3.0 and -3.0 or a)
  return 1.0 / (s + 0.025 * math.exp(-11.0 * s))
end
local X = airmass(alt) - 1.0
local function transmit(k) return 10.0 ^ (-0.4 * k * X) end

-- Visible at all? Refraction lifts it about half a degree and then it is gone.
local up = clamp((alt + 2.5) / 3.3, 0.0, 1.0)

-- --------------------------------------------------------- the shader
-- Substituted, not generated: the shader is a file you can read in the repo,
-- and this only fills in the numbers at the top of it.
local theme_dir = (os.getenv("HOME") or "") .. "/.local/state/omarchy/current/theme"

local function bake()
  local template = read_line(theme_dir .. "/sky.frag.in")
  if not template then return false end

  -- Hyprland's shader clock is seconds since the compositor started, and the
  -- instance signature carries the unix time it started at. So the shader can
  -- be told, exactly, what its own clock will read at this instant.
  local t_load = 0.0
  local his = os.getenv("HYPRLAND_INSTANCE_SIGNATURE") or ""
  local started = tonumber(his:match("^%x+_(%d+)"))
  if started then t_load = now - started end
  if t_load < 0 then t_load = 0.0 end

  local function g(x) return string.format("%.9f", x) end
  local values = {
    T_LOAD = g(t_load),
    LON = g(lon),
    SINPHI = g(sd(lat)), COSPHI = g(cd(lat)), TANPHI = g(tan(lat * D2R)),
    -- Face the equator: south in the northern hemisphere, north in the
    -- southern one, so the Moon crosses the middle of the screen rather than
    -- the edges. The one concession this theme makes to where you live.
    AZ_CENTER = g(lat >= 0 and 180.0 or 0.0),
    EPS = g(eps),
    RSUN = g(sdist),
    LP0 = g(wrap360(args.Lp)), LP_R = g(481267.88123421 / 36525.0),
    DD0 = g(wrap360(args.D)),  DD_R = g(445267.1114034 / 36525.0),
    MS0 = g(wrap360(args.Ms)), MS_R = g(35999.0502909 / 36525.0),
    MP0 = g(wrap360(args.Mp)), MP_R = g(477198.8675055 / 36525.0),
    FF0 = g(wrap360(args.F)),  FF_R = g(483202.0175233 / 36525.0),
    OM0 = g(wrap360(args.Om)), OM_R = g(-1934.1362891 / 36525.0),
    SL0 = g(wrap360(args.L0)), SL_R = g(36000.76983 / 36525.0),
    TH0 = g(gmst),             TH_R = g(360.98564736629),
  }

  local out = template:gsub("@@([%w_]+)@@", function(key)
    return values[key] or ("/* unbaked " .. key .. " */ 0.0")
  end)

  local handle = io.open(theme_dir .. "/sky.frag", "w")
  if not handle then return false end
  -- A header nobody needs and everybody wants: the sky this file was cut for.
  -- It goes after the #version line, because in the ES profile nothing at all
  -- is allowed in front of that -- not even a comment.
  local version, body = out:match("^([^\n]*\n)(.*)$")
  handle:write(version)
  handle:write(string.format(
    "// Baked %s UTC for %.4f, %.4f (%s).\n" ..
    "// Moon: altitude %+.2f deg, azimuth %.2f deg, %.1f%% lit and %s,\n" ..
    "// %.0f km away, phase angle %.1f deg.\n",
    os.date("!%Y-%m-%d %H:%M:%S", now), lat, lon, source,
    alt, az, illum * 100, waxing and "waxing" or "waning", mdist, phase_angle))
  handle:write(body)
  handle:close()
  return true
end

local ok_bake, baked = pcall(bake)
local have_shader = ok_bake and baked

-- ------------------------------------------------------------ the look
-- Moonlight is sunlight that has bounced off a rock, so it is very slightly
-- warm; the blue-grey everyone paints it is an artefact of the eye giving up
-- on colour at low light. This theme uses the real thing and lets the
-- extinction do the colouring instead.
local function rgba(r, g, b, a)
  return string.format("rgba(%02x%02x%02x%02x)",
    clamp(floor(r * 255 + 0.5), 0, 255),
    clamp(floor(g * 255 + 0.5), 0, 255),
    clamp(floor(b * 255 + 0.5), 0, 255),
    clamp(floor(a * 255 + 0.5), 0, 255))
end

-- How much light there is: phase times how far it has got above the horizon,
-- times how much of it survived the trip through the air.
local brightness = illum * up
local moon_r = 1.000 * transmit(0.11)
local moon_g = 0.972 * transmit(0.20)
local moon_b = 0.926 * transmit(0.36)
local peak = math.max(moon_r, math.max(moon_g, moon_b))
moon_r, moon_g, moon_b = moon_r / peak, moon_g / peak, moon_b / peak

-- The focused window is lit by the Moon. At new moon, or with the Moon down,
-- it falls back to earthshine: the ashen blue-grey of sunlight that went to
-- Earth, to the Moon, and back, which is what the dark limb is lit by.
local lit = 0.28 + 0.72 * brightness
local ash_r, ash_g, ash_b = 0.42, 0.48, 0.64

local function mix(a, b, t) return a + (b - a) * t end
local border_hi = rgba(mix(ash_r, moon_r, lit), mix(ash_g, moon_g, lit), mix(ash_b, moon_b, lit), 1.0)
local border_mid = rgba(mix(ash_r, moon_r, lit) * 0.72, mix(ash_g, moon_g, lit) * 0.76,
                        mix(ash_b, moon_b, lit) * 0.92, 1.0)
local border_lo = rgba(0.12 + 0.10 * lit, 0.14 + 0.11 * lit, 0.22 + 0.14 * lit, 1.0)

-- Where the Moon is on screen, in the same projection the shader uses, so the
-- gradient and the shadows agree with the disc.
local mx = 0.5 + wrap180(az - (lat >= 0 and 180.0 or 0.0)) / 360.0
local my = 0.06 + 0.80 * (1.0 - alt / 90.0)
local dx, dy = mx - 0.5, my - 0.5
local dlen = sqrt(dx * dx + dy * dy)
if dlen < 1e-4 then dx, dy, dlen = 0.0, -1.0, 1.0 end
dx, dy = dx / dlen, dy / dlen

-- Hyprland measures a gradient angle clockwise from straight up. Point it at
-- the Moon: the bright end of every focused border is the end nearest the
-- real thing.
local border_angle = floor(wrap360(atan(dx, -dy) * R2D) + 0.5)

-- The waxing Moon is climbing and the waning Moon is falling, and the border
-- gradient is ordered to match: bright end leading on the way up.
local active_border_color = waxing
  and { colors = { border_hi, border_mid, border_lo }, angle = border_angle }
  or { colors = { border_lo, border_mid, border_hi }, angle = border_angle }
local inactive_border_color = { colors = { rgba(0.09, 0.11, 0.18, 0.85), rgba(0.05, 0.06, 0.11, 0.85) }, angle = border_angle }

hl.config({
  general = {
    border_size = 2,
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
    -- Only if it is actually there. A screen_shader pointing at a file that
    -- does not exist is a config error, and a theme that cannot compute the
    -- sky should still be a theme.
    screen_shader = have_shader and (theme_dir .. "/sky.frag") or nil,

    rounding = 12,
    rounding_power = 2,

    -- The unfocused window is further out of the moonlight. How much further
    -- depends on how much moonlight there is: at new moon everything not in
    -- front of you is nearly gone.
    dim_inactive = true,
    dim_strength = 0.16 + 0.16 * (1.0 - brightness),

    shadow = {
      enabled = true,
      range = 26,
      render_power = 2,
      -- Shadows fall away from the light, and the light is a specific object
      -- in a specific place. When the Moon sets, they go straight down.
      offset = string.format("%.1f %.1f", -dx * 10.0, -dy * 10.0),
      color = rgba(0.0, 0.0, 0.0, 0.62),
      color_inactive = rgba(0.0, 0.0, 0.0, 0.78),
    },

    blur = {
      enabled = true,
      size = 6,
      passes = 3,
      new_optimizations = true,
      noise = 0.015,
      contrast = 0.95,
      brightness = 0.88,
      vibrancy = 0.12,
      vibrancy_darkness = 0.35,
      popups = true,
    },
  },

  -- A screen shader only advances when Hyprland draws a frame, and by default
  -- it only redraws what changed -- so on a still screen the sky would freeze
  -- in whatever region nothing is happening, and the Moon would be cut into
  -- rectangles that each believe a different time. Full damage forces the
  -- whole output every frame. This is the battery cost, and it is the shader's
  -- fault rather than the astronomy's.
  debug = {
    damage_tracking = 0,
  },
})

-- Everything moves the way something in orbit moves: no snap, no bounce, a
-- long ease out of a fast start.
hl.curve("orbit", { type = "bezier", points = { { 0.16, 0.84 }, { 0.24, 1.0 } } })
hl.curve("fall", { type = "bezier", points = { { 0.42, 0.0 }, { 0.58, 1.0 } } })
hl.curve("rise", { type = "bezier", points = { { 0.12, 0.9 }, { 0.3, 1.0 } } })

hl.animation({ leaf = "borderangle", enabled = false })
hl.animation({ leaf = "border", enabled = true, speed = 12, bezier = "fall" })
hl.animation({ leaf = "windows", enabled = true, speed = 5, bezier = "orbit" })
hl.animation({ leaf = "windowsIn", enabled = true, speed = 6, bezier = "rise", style = "popin 88%" })
hl.animation({ leaf = "windowsOut", enabled = true, speed = 5, bezier = "fall", style = "popin 92%" })
hl.animation({ leaf = "workspaces", enabled = true, speed = 6, bezier = "orbit", style = "slide" })
hl.animation({ leaf = "specialWorkspace", enabled = true, speed = 6, bezier = "orbit", style = "slidevert" })
hl.animation({ leaf = "layers", enabled = true, speed = 4, bezier = "orbit" })
hl.animation({ leaf = "fade", enabled = true, speed = 5, bezier = "fall" })

-- Let the shell surfaces sit under the sky rather than on top of it.
hl.layer_rule({ match = { namespace = "^(omarchy-bar|omarchy-menu|omarchy-image-selector|omarchy-emojis|omarchy-clipboard|omarchy-keyboard-panel|omarchy-notifications|omarchy-osd|omarchy-launcher)$" }, blur = true, ignore_alpha = 0.1 })
