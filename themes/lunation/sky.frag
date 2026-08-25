#version 300 es
// Baked 2000-01-01 12:00:00 UTC for 51.4779, -0.0015 (lunation.conf).
// Moon: altitude +10.14 deg, azimuth 237.78 deg, 23.0% lit and waning,
// 402484 km away, phase angle 122.7 deg.
// Lunation. Hyprland runs this over the whole compositor output, so the Moon
// is behind your windows in the literal sense: this shader only ever sees the
// finished frame, and it adds light where the frame is dark.
//
// Hyprland supplies: tex (the composited screen), v_texcoord, time (seconds).
//
// WHAT IS BAKED AND WHAT IS NOT. The constants below are written by
// themes/lunation/hyprland.lua every time Hyprland loads its config. They are
// the mean orbital arguments AT THAT INSTANT, plus their rates -- the linear
// part of the model, which is the part that is boring and exact. Everything
// non-linear (the periodic terms, the equatorial rotation, the hour angle, the
// phase, the extinction) is evaluated HERE, per frame, from `time`. So the sky
// stays correct between reloads for as long as the compositor runs; nothing
// has to fire on a timer, because the shader is already being asked what time
// it is sixty times a second.
//
// It is also evaluated per PIXEL, because a fragment shader has nowhere else
// to put it. Roughly forty transcendentals per fragment that are identical
// across the entire frame. That is absurd, it is unavoidable without a uniform
// we are not given, and it is most of why this theme costs battery.
precision highp float;

in vec2 v_texcoord;
uniform sampler2D tex;
uniform float time;
out vec4 fragColor;

// ---------------------------------------------------------------- baked
// Written by hyprland.lua. Do not hand-edit the generated sky.frag; edit
// sky.frag.in, which is the template these are substituted into.
const float T_LOAD    = 0.000000000;    // what `time` held when this was baked
const float LON       = -0.001500000;       // observer, degrees, east positive
const float SINPHI    = 0.782367984;
const float COSPHI    = 0.622816456;
const float TANPHI    = 1.256177443;
const float AZ_CENTER = 180.000000000; // the azimuth the screen is centred on
const float EPS       = 23.439291000;       // obliquity of the ecliptic, degrees
const float RSUN      = 147100847.962749898;      // Earth-Sun distance, km, today

// Mean arguments at bake time (degrees, already reduced) and rates (deg/day).
const float LP0 = 218.316447700, LP_R = 13.176396475;   // Moon mean longitude
const float DD0 = 297.850192100, DD_R = 12.190749114;   // mean elongation
const float MS0 = 357.529109200, MS_R = 0.985600282;   // Sun mean anomaly
const float MP0 = 134.963396400, MP_R = 13.064992950;   // Moon mean anomaly
const float FF0 = 93.272095000, FF_R = 13.229350240;   // argument of latitude
const float OM0 = 125.044547900, OM_R = -0.052953766;   // ascending node
const float SL0 = 280.466460000, SL_R = 0.985647360;   // Sun mean longitude
const float TH0 = 280.460618370, TH_R = 360.985647366;   // Greenwich mean sidereal time

// ---------------------------------------------------------------- knobs
// The one thing here that is not to scale. The Moon is half a degree wide;
// across a screen mapped to the full 360 degrees of the horizon that is about
// three pixels. So the disc is drawn about ninety times oversize -- but its
// size still tracks the true angular diameter, so perigee really is bigger
// than apogee by the real five and a half percent.
const float MOON_R    = 0.062;   // disc radius, fraction of screen height, at 384400 km
const float HORIZON_Y = 0.86;    // where altitude 0 lands
const float ZENITH_Y  = 0.06;    // where altitude 90 lands
const float MOONLIGHT = 0.85;    // how hard full moonlight washes the desktop
const float NIGHT_AMT = 0.13;    // how much the frame cools when the Moon is down
const float DISC_GAIN = 1.00;    // disc brightness against the sky
const float EXT_V     = 0.20;    // extinction, magnitudes per airmass, green
const float EXT_B     = 0.36;    // ... blue. The difference is why a low Moon is orange.
const float EXT_R     = 0.11;    // ... red.

const vec3 MOON_TINT  = vec3(1.000, 0.972, 0.926);  // sunlight off regolith
const vec3 ASHEN      = vec3(0.62, 0.70, 0.92);     // earthshine, Earth is blue
const vec3 NIGHT_TINT = vec3(0.72, 0.78, 1.00);

// ---------------------------------------------------------------- maths
const float PI = 3.14159265;
float wrap(float x)  { return x - 360.0 * floor(x / 360.0); }
float sd(float d)    { return sin(radians(d)); }
float cd(float d)    { return cos(radians(d)); }
float luma(vec3 c)   { return dot(c, vec3(0.2126, 0.7152, 0.0722)); }

// Alt/az for one equatorial position. Meeus 13.5/13.6, with the azimuth
// carried as a vector so nothing blows up on the meridian.
vec2 horizontal(float ra, float dec, float lst) {
  float H = lst - ra;
  float sH = sd(H), cH = cd(H), sD = sd(dec), cD = cd(dec);
  float alt = degrees(asin(sD * SINPHI + cD * COSPHI * cH));
  // Measured from south, westward, then turned into a compass bearing.
  float azS = degrees(atan(sH * cD, cH * SINPHI * cD - sD * COSPHI));
  return vec2(alt, wrap(azS + 180.0));
}

// The sky, projected onto the screen: the full circle of the horizon across
// the width, altitude up the height. The Moon is therefore always somewhere
// on this plane -- it just spends half its time below the bottom edge.
vec2 project(vec2 altaz) {
  float dx = wrap(altaz.y - AZ_CENTER + 180.0) - 180.0;
  return vec2(0.5 + dx / 360.0, ZENITH_Y + (HORIZON_Y - ZENITH_Y) * (1.0 - altaz.x / 90.0));
}

// Rozenberg's airmass, which stays finite through the horizon instead of
// diverging the way the secant approximation does.
float airmass(float alt) {
  float s = sd(max(alt, -3.0));
  return 1.0 / (s + 0.025 * exp(-11.0 * s));
}

// The near side, as unit vectors in the selenographic frame with the cosine
// of an angular radius in w. Stored that way so the test for "is this pixel
// inside Mare Imbrium" is one dot product and one smoothstep -- no inverse
// trigonometry, twenty-two times, for every fragment on the screen.
//
// Not a texture. A texture would have to be fetched from somewhere, and
// nothing in this repo fetches anything from anywhere.
const int NMARE = 24;
// The maria: basalt floods, albedo about 0.07 against 0.11 for the
// highlands they sit in.
const vec4 MARE[NMARE] = vec4[NMARE](
  vec4(-0.603651,  0.642788,  0.471624,  0.974370),  // Oceanus Procellarum, north
  vec4(-0.799383,  0.315649,  0.511227,  0.963630),  // Oceanus Procellarum, middle
  vec4(-0.819027, -0.017452,  0.573489,  0.970296),  // Oceanus Procellarum, south
  vec4(-0.694829, -0.258819,  0.670988,  0.984808),  // Oceanus Procellarum, Aestuum arm
  vec4(-0.226045,  0.541708,  0.809602,  0.946085),  // Mare Imbrium
  vec4( 0.265507,  0.469472,  0.842082,  0.979223),  // Mare Serenitatis
  vec4( 0.515287,  0.147809,  0.844175,  0.968583),  // Mare Tranquillitatis
  vec4( 0.820572,  0.292372,  0.491102,  0.987136),  // Mare Crisium
  vec4( 0.773210, -0.135716,  0.619458,  0.965926),  // Mare Fecunditatis
  vec4( 0.547979, -0.262189,  0.794340,  0.995396),  // Mare Nectaris
  vec4(-0.266173, -0.363251,  0.892861,  0.978867),  // Mare Nubium
  vec4(-0.568157, -0.413104,  0.711718,  0.993768),  // Mare Humorum
  vec4(-0.386377, -0.173648,  0.905847,  0.994881),  // Mare Cognitum
  vec4(-0.509148,  0.130526,  0.850724,  0.989272),  // Mare Insularum
  vec4( 0.061106,  0.230050,  0.971259,  0.997564),  // Mare Vaporum
  vec4(-0.350087,  0.838671,  0.417218,  0.996917),  // Mare Frigoris, west
  vec4(-0.146066,  0.848048,  0.509391,  0.996917),  // Mare Frigoris, centre
  vec4( 0.097103,  0.829038,  0.550698,  0.996917),  // Mare Frigoris, east
  vec4( 0.998372,  0.022687,  0.052322,  0.994151),  // Mare Smythii, on the eastern limb
  vec4( 0.777177, -0.627963, -0.040730,  0.984808),  // Mare Australe, over the southeastern limb
  vec4(-0.150226,  0.189095,  0.970399,  0.998135),  // Sinus Aestuum
  vec4( 0.000000,  0.000000,  1.000000,  0.999194),  // Sinus Medii
  vec4( 0.006248,  0.446198,  0.894913,  0.998630),  // Palus Putredinis
  vec4( 0.970925,  0.230050,  0.066191,  0.996195)  // Mare Marginis, on the limb
);

const int NRAYED = 4;
// The young rayed craters, which are bright because their ejecta has not
// been in the solar wind long enough to darken.
const vec4 RAYED[NRAYED] = vec4[NRAYED](
  vec4(-0.143850, -0.685818,  0.713415,  0.998806),  // Tycho, and the rays it throws a quarter of the way round
  vec4(-0.338847,  0.166769,  0.925943,  0.998971),  // Copernicus
  vec4(-0.609519,  0.140901,  0.780149,  0.999816),  // Kepler
  vec4(-0.674017,  0.401948,  0.619790,  0.999743)  // Aristarchus
);

void main() {
  vec2 uv = v_texcoord;
  vec3 base = texture(tex, uv).rgb;

  // Hyprland's clock is seconds since the compositor started, so `time` is
  // already past T_LOAD by the time this file exists. If some other Hyprland
  // ever hands a shader a clock that starts at zero instead, the second branch
  // is still correct -- it is then seconds since this shader loaded.
  float dt = (time >= T_LOAD ? time - T_LOAD : time) / 86400.0;

  float Lp = LP0 + LP_R * dt;
  float D  = DD0 + DD_R * dt;
  float Ms = MS0 + MS_R * dt;
  float Mp = MP0 + MP_R * dt;
  float F  = FF0 + FF_R * dt;
  float SL = SL0 + SL_R * dt;
  float TH = TH0 + TH_R * dt;

  // Moon, ecliptic. Six longitude terms, four latitude, four distance -- the
  // head of Meeus 47, cut where the next term stops being worth a sine.
  float lam = Lp + 6.288774 * sd(Mp) + 1.274027 * sd(2.0 * D - Mp)
                 + 0.658314 * sd(2.0 * D) + 0.213618 * sd(2.0 * Mp)
                 - 0.185116 * sd(Ms) - 0.114332 * sd(2.0 * F);
  float bet = 5.128122 * sd(F) + 0.280602 * sd(Mp + F) + 0.277693 * sd(Mp - F)
                 + 0.173237 * sd(2.0 * D - F);
  float dist = 385000.56 - 20905.355 * cd(Mp) - 3699.111 * cd(2.0 * D - Mp)
                 - 2955.968 * cd(2.0 * D) - 569.925 * cd(2.0 * Mp);

  // Sun, ecliptic. Mean longitude plus the equation of the centre.
  float slam = SL + 1.914602 * sd(Ms) + 0.019993 * sd(2.0 * Ms) + 0.000289 * sd(3.0 * Ms);

  float se = sd(EPS), ce = cd(EPS);
  float sl = sd(lam), cl = cd(lam), sb = sd(bet), cb = cd(bet);
  float ra   = degrees(atan(sl * ce - (sb / cb) * se, cl));
  float dec  = degrees(asin(sb * ce + cb * se * sl));
  float sra  = degrees(atan(sd(slam) * ce, cd(slam)));
  float sdec = degrees(asin(se * sd(slam)));

  float lst = TH + LON;
  vec2 maltaz = horizontal(ra, dec, lst);
  vec2 saltaz = horizontal(sra, sdec, lst);

  // Illuminated fraction, from the real elongation and the real distances.
  float elong = degrees(acos(clamp(cb * cd(lam - slam), -1.0, 1.0)));
  float phase = degrees(atan(RSUN * sd(elong), dist - RSUN * cd(elong)));
  float k = 0.5 * (1.0 + cd(phase));

  ivec2 size = textureSize(tex, 0);
  float aspect = float(size.x) / max(float(size.y), 1.0);

  vec2 mpos = project(maltaz);
  vec2 spos = project(saltaz);

  // Extinction. The Moon is dimmed and reddened by however much atmosphere it
  // is behind, normalised so that a Moon at the zenith is unattenuated.
  float X = airmass(maltaz.x) - 1.0;
  vec3 trans = vec3(pow(10.0, -0.4 * EXT_R * X),
                    pow(10.0, -0.4 * EXT_V * X),
                    pow(10.0, -0.4 * EXT_B * X));
  // Refraction lifts it about half a degree, and then it is gone.
  float vis = smoothstep(-2.5, 0.8, maltaz.x);

  // Screen-space geometry of the disc. y is flipped so that up is up.
  float R = MOON_R * (384400.0 / dist);
  vec2 rel = vec2((uv.x - mpos.x) * aspect, -(uv.y - mpos.y));
  float r = length(rel) / R;

  // The bright limb points at the Sun, because it always does. Taking the
  // direction from the Sun's own projected position rather than from a
  // position angle means the terminator cannot end up mirrored: both bodies
  // went through the same projection.
  vec2 toSun = vec2((spos.x - mpos.x) * aspect, -(spos.y - mpos.y));
  vec2 sdir = length(toSun) > 1e-5 ? normalize(toSun) : vec2(1.0, 0.0);

  float darkness = 1.0 - luma(base);
  float gate = darkness * darkness;

  vec3 col = base;

  // 1. The night itself. Cool the dark parts of the frame, hardest when there
  //    is no Moon up to warm them.
  float nightness = 1.0 - vis * k;
  col = mix(col, col * NIGHT_TINT, NIGHT_AMT * nightness * gate);

  // 2. Moonlight. A broad wash centred on where the Moon actually is, so the
  //    desktop is lit from the correct side of the room.
  float lit = k * vis;
  float d = length(vec2((uv.x - mpos.x) * aspect, uv.y - mpos.y));
  float wash = exp(-d * d * 1.6) * 0.75 + 0.25;
  col += MOON_TINT * trans * (MOONLIGHT * lit * wash * 0.10 * gate);

  // 3. The halo. Scattered light in the air immediately around the disc.
  // Scattered light in the air immediately around the disc. It belongs
  // around the Moon, not on it, so it is faded out where the disc starts.
  float halo = exp(-r * 0.55) * 0.35 / (1.0 + r * r * 0.08) * smoothstep(0.55, 1.25, r);
  col += MOON_TINT * trans * (halo * lit * 0.60 * gate);

  // 4. The disc.
  if (r < 1.02) {
    float w = sqrt(max(1.0 - min(r * r, 1.0), 0.0));   // z of the surface normal
    vec2 n2 = rel / R;
    // Surface normal in a frame whose x axis points at the Sun.
    float a = dot(n2, sdir);
    float b = dot(n2, vec2(-sdir.y, sdir.x));
    float ci = cd(phase), si = sd(phase);
    float mu0 = a * si + w * ci;                       // cos of the incidence angle
    float mu  = w;                                     // cos of the emission angle

    // Where on the Moon this pixel is. The physical libration is folded in, so
    // the face you are looking at is the face that is turned toward you
    // tonight -- over a month the Moon nods about eight degrees each way and
    // shows you nearly sixty percent of itself, and it does that here too.
    float Om = OM0 + OM_R * dt;
    float W = radians(lam - Om);
    float I = radians(1.54242);
    float bR = radians(bet);
    float A = atan(sin(W) * cos(bR) * cos(I) - sin(bR) * sin(I), cos(W) * cos(bR));
    float libLon = radians(wrap(degrees(A) - F + 180.0) - 180.0);
    float libLat = asin(clamp(-sin(W) * cos(bR) * sin(I) - sin(bR) * cos(I), -1.0, 1.0));

    // Rotate the disc frame by the parallactic angle, so the Moon lies over on
    // its side through the night by exactly as much as it really does. This is
    // the detail nobody notices and everybody would notice the absence of.
    float H = lst - ra;
    float q = atan(sd(H), TANPHI * cd(dec) - sd(dec) * cd(H));
    float cq = cos(q), sq = sin(q);
    vec3 nrm = vec3(n2.x * cq + n2.y * sq, -n2.x * sq + n2.y * cq, w);

    float clb = cos(libLat), slb = sin(libLat);
    float cll = cos(libLon), sll = sin(libLon);
    vec3 t = vec3(nrm.x, nrm.y * clb + nrm.z * slb, -nrm.y * slb + nrm.z * clb);
    vec3 g = vec3(t.x * cll + t.z * sll, t.y, -t.x * sll + t.z * cll);

    // Mare edges are not circles. A little low-frequency wobble on the
    // threshold is cheaper than storing an outline and reads better than a
    // perfect disc.
    float wobble = 0.006 * sin(9.0 * g.x + 3.0 * g.y) * cos(7.0 * g.z - 2.0 * g.x)
               + 0.003 * sin(17.0 * g.y - 5.0 * g.z);

    float basalt = 0.0;
    for (int i = 0; i < NMARE; i++) {
      float c = dot(g, MARE[i].xyz) + wobble;
      // The soft edge is a fraction of each mare's own radius rather than a
      // fixed number of degrees, so a small sea does not get a coastline as
      // wide as itself.
      basalt = max(basalt, smoothstep(MARE[i].w, mix(MARE[i].w, 1.0, 0.40), c));
    }
    float albedo = mix(1.0, 0.50, basalt);

    for (int i = 0; i < NRAYED; i++) {
      float c = dot(g, RAYED[i].xyz);
      albedo += 0.24 * smoothstep(RAYED[i].w, mix(RAYED[i].w, 1.0, 0.55), c);
    }

    // Tycho throws rays a quarter of the way round the Moon, and they cross
    // everything, mare and highland alike, because they are younger than all
    // of it.
    vec3 ty = RAYED[0].xyz;
    float ct = dot(g, ty);
    vec3 east = normalize(cross(vec3(0.0, 1.0, 0.0), ty));
    vec3 north = cross(ty, east);
    float theta = atan(dot(g, north), dot(g, east));
    float reach = smoothstep(0.62, 0.995, ct);
    albedo += 0.11 * reach * (0.5 + 0.5 * cos(theta * 11.0));
    albedo = clamp(albedo, 0.30, 1.60);

    // Lommel-Seeliger, not Lambert. Regolith backscatters, which is why the
    // full Moon looks like a flat disc and not like a lit ball.
    float shade = mu0 > 0.0 ? mu0 / max(mu0 + mu, 1e-3) : 0.0;
    // The opposition surge: shadow-hiding at small phase angles, which is real
    // and is why a full Moon is brighter than twice a half Moon.
    shade *= 1.0 + 0.40 * exp(-phase / 7.0);

    vec3 lunar = MOON_TINT * (albedo * shade * DISC_GAIN);
    // Earthshine on the unlit side. Second-hand light: sunlight off the Earth,
    // off the Moon, back to you, and brightest when the Earth is full as seen
    // from up there -- which is exactly when the Moon is new down here.
    lunar += ASHEN * (albedo * (1.0 - k) * 0.075 * pow(max(w, 0.0), 0.35));

    float edge = 1.0 - smoothstep(0.985, 1.0, r);
    col += lunar * trans * (edge * vis * gate);
  }

  fragColor = vec4(col, 1.0);
}
