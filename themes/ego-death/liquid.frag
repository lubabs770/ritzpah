#version 300 es
// Ego Death screen shader. Hyprland runs this over the entire compositor
// output, so it warps windows, bar, cursor -- everything -- in real time.
//
// Hyprland supplies: tex (the composited screen), v_texcoord, time (seconds).
// Keep it cheap: three texture samples and a handful of trig. Anything heavier
// stops being a desktop and starts being a space heater.
precision highp float;

in vec2 v_texcoord;
uniform sampler2D tex;
uniform float time;
out vec4 fragColor;

// Rodrigues rotation about the grey axis == hue rotation. No branching, no
// RGB->HSV round trip.
vec3 hueshift(vec3 c, float a) {
  const vec3 k = vec3(0.57735);
  float cs = cos(a);
  return c * cs + cross(k, c) * sin(a) + k * dot(k, c) * (1.0 - cs);
}

void main() {
  vec2 uv = v_texcoord;
  float t = time;

  // Two crossed sine fields at different rates: a slow liquid churn that
  // never repeats cleanly.
  vec2 warp;
  warp.x = sin(uv.y * 9.0 + t * 0.9) * 0.0090 + sin(uv.y * 3.1 - t * 0.5) * 0.0060;
  warp.y = cos(uv.x * 7.0 - t * 0.7) * 0.0090 + cos(uv.x * 2.3 + t * 0.4) * 0.0060;

  // A ripple crawling outward from the middle of the screen.
  vec2 d = uv - 0.5;
  float r = length(d);
  warp += normalize(d + 1e-5) * sin(r * 22.0 - t * 1.6) * 0.0045;

  // Sample each channel at a different offset so colour smears against itself.
  // This is what makes text ghost.
  float ab = 0.0030 + sin(t * 0.3) * 0.0015;
  vec3 col;
  col.r = texture(tex, uv + warp * 1.15 + vec2(ab, 0.0)).r;
  col.g = texture(tex, uv + warp).g;
  col.b = texture(tex, uv + warp * 0.85 - vec2(ab, 0.0)).b;

  // Everything drifts through the spectrum, and faster the further out it is,
  // so the screen is never one colour.
  col = hueshift(col, t * 0.35 + r * 1.2);

  // Saturation breathes.
  float lum = dot(col, vec3(0.299, 0.587, 0.114));
  col = mix(vec3(lum), col, 1.45 + sin(t * 0.6) * 0.25);

  fragColor = vec4(col, 1.0);
}
