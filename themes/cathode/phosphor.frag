#version 300 es
// Cathode screen shader. Hyprland runs this over the entire compositor output,
// so the barrel, the scanlines and the glow apply to windows, the bar, menus,
// video and the cursor alike -- it has no idea what a window is, it only ever
// sees the finished frame.
//
// Hyprland supplies: tex (the composited screen), v_texcoord, time (seconds).
// Budget: five texture samples and some trig. A CRT was a dumb device and this
// should stay a cheap shader.
precision highp float;

in vec2 v_texcoord;
uniform sampler2D tex;
uniform float time;
out vec4 fragColor;

// Every knob worth turning is here. The README explains what each one costs.
const float CURVE      = 0.13;   // barrel distortion, 0.0 = flat panel
const float SCAN_LINES = 720.0;  // a tube has its own line count, not yours
const float SCAN_DEPTH = 0.28;   // how dark the gaps between lines go
const float MASK_DEPTH = 0.13;   // aperture grille, on physical pixel triads
const float BLOOM      = 0.55;   // phosphor spill into neighbouring pixels
const float TINT       = 0.72;   // how much of the frame is dragged to amber
const float IDLE       = 0.014;  // the tube is never off, so black is never 0

const vec3 PHOSPHOR = vec3(1.0, 0.690, 0.0);   // P3 amber

// Cheap per-pixel hash for the snow. Nothing about it is uniform, which is the
// point -- a real tube's noise floor is not smooth either.
float hash(vec2 p, float t) {
  return fract(sin(dot(p, vec2(127.1, 311.7)) + t) * 43758.5453);
}

void main() {
  // Push the sample coordinates outward from centre, harder the further out
  // they start. The image bows toward the viewer and the corners pull away.
  //
  // The divide is not decoration. Without it, the top of the screen is dragged
  // about five percent off the glass, which is more than the height of the bar
  // -- the bar would simply not be there. Normalising by (1 + CURVE) pins the
  // middle of each edge exactly where it was, so only the four corners fall
  // off, which is what a real tube does anyway.
  vec2 c = v_texcoord * 2.0 - 1.0;
  float r2 = dot(c, c);
  c *= (1.0 + CURVE * r2) / (1.0 + CURVE);
  vec2 uv = c * 0.5 + 0.5;

  // Past the glass there is no picture, only the inside of the bezel. Feather
  // the edge slightly so the tube has a curve instead of a cut.
  vec2 edge = smoothstep(vec2(0.0), vec2(0.004), uv) *
              smoothstep(vec2(0.0), vec2(0.004), 1.0 - uv);
  float inside = edge.x * edge.y;

  // Centre tap plus four diagonals: the phosphor glows into its neighbours,
  // which is the only persistence available here (see the README -- a screen
  // shader gets no previous frame to decay).
  float sp = 0.0018;
  vec3 col = texture(tex, uv).rgb;
  vec3 glow = texture(tex, uv + vec2( sp,  sp)).rgb;
  glow = max(glow, texture(tex, uv + vec2(-sp,  sp)).rgb);
  glow = max(glow, texture(tex, uv + vec2( sp, -sp)).rgb);
  glow = max(glow, texture(tex, uv + vec2(-sp, -sp)).rgb);
  col = 1.0 - (1.0 - col) * (1.0 - glow * BLOOM);

  // One phosphor. Take the luminance the frame would have had and re-emit it
  // in amber, then blend back toward the original so the desktop keeps a
  // little of its own opinion.
  float lum = dot(col, vec3(0.2126, 0.7152, 0.0722));
  col = mix(col, PHOSPHOR * lum * 1.08, TINT);

  // Scanlines are fixed to the tube, not to your panel, so they stay the same
  // thickness whether this is a 1080p laptop or a 4K monitor.
  float scan = 0.5 + 0.5 * cos(uv.y * SCAN_LINES * 6.2831853);
  col *= 1.0 - SCAN_DEPTH * scan;

  // Aperture grille, on real pixel triads. Subtle by design: crank MASK_DEPTH
  // and the screen turns into corduroy.
  float triad = mod(gl_FragCoord.x, 3.0);
  col *= 1.0 - MASK_DEPTH * step(1.0, triad) * step(triad, 2.0);

  // The refresh never quite locked. A faint bright band crawls up the screen
  // every eight seconds or so, the way a badly synced tube beats against
  // whatever is filming it.
  float bar = fract(uv.y - time * 0.125);
  col *= 1.0 + 0.07 * smoothstep(0.86, 0.97, bar) * (1.0 - smoothstep(0.97, 1.0, bar));

  // Mains hum on the high-voltage supply: a slow, shallow brightness breath.
  col *= 1.0 + 0.022 * sin(time * 5.9) + 0.008 * sin(time * 1.3);

  // Snow. Almost nothing, but it keeps the black from ever being clean.
  col += (hash(gl_FragCoord.xy, fract(time) * 91.7) - 0.5) * 0.022;

  // Vignette, then the idle glow of a powered tube with nothing to draw.
  col *= 1.0 - 0.34 * r2 * r2;
  col += PHOSPHOR * IDLE;

  fragColor = vec4(col * inside, 1.0);
}
