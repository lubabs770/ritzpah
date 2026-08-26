# The strip: how live ISS telemetry gets into a Hyprland screen shader

This is the load-bearing document of the theme. The daemon writes to this
contract, the shader reads from it, and neither one knows anything else about
the other. If you change a texel meaning, change it here first.

## Why there is a strip at all

Hyprland binds a **fixed, compiled-in set** of uniforms to a screen shader.
In 0.56.2 the enum (`eShaderUniform`, filled by `CShader::getUniformLocations()`)
is exactly:

    tex   time   wl_output   screen_size   v_texcoord

There is no extension point. You cannot bind a second sampler, you cannot add
a float, and there is no arbitrary-uniform path. So a data *texture* — the
obvious way to hand a shader a table of numbers — is not available to any
theme that ships as a Hyprland `screen_shader`. That is not a policy of this
repo, it is the compositor.

But `tex` is the **composited output**. Whatever is on the screen is in it. So
the daemon paints the telemetry into the screen as actual pixels, and the
shader reads the screen to find out where the ISS is:

    ritzpahd ──layer-shell surface──> 64x2 px of real screen ──> tex ──> shader
                                              ↑                            │
                                              └──── painted over ──────────┘

The shader covers the strip in the same pass that reads it. Hyprland's
screencopy captures the output *after* the screen shader runs, so the strip is
invisible on screen and invisible to `grim` — it exists only in the one frame
buffer the shader is looking at.

## Where the strip is

Top-left corner, **origin (0,0)**, 64 px wide and 2 px tall, one strip per
output. Layer-shell, `overlay` layer, no keyboard focus, no pointer input,
fully opaque.

The theme's `hyprland.lua` ships the layer rule that keeps it pristine:

    namespace `ritzpah-iss-telemetry` — blur off, no dim, no shadow, no rounding

Anything that blurs, dims, rounds or fades that surface corrupts the channel.
Rounding is the sneaky one: a rounded corner alpha-blends texel 0, which is
the magic. That is why the strip is 2 px tall and the shader reads **row 1**,
never row 0 — a 1 px surface has nowhere to hide from a corner radius.

## Encoding

Every value is carried as a **20-bit unsigned integer** split across R, G and
B at 8/8/4 bits, with A reserved. Values are normalized to a declared range
before packing, so the shader never needs to know a gauge's units:

    raw   = clamp((value - lo) / (hi - lo), 0, 1)
    code  = round(raw * 1048575)          // 20 bits
    R     = (code >> 12) & 0xFF
    G     = (code >>  4) & 0xFF
    B     = (code & 0xF) << 4             // low nibble, left-aligned

B is left-aligned into the high nibble so that a compositor that quantizes to
RGB565 (5/6/5) degrades gracefully instead of catastrophically: you lose the
bottom bits of precision, not the top. 20 bits is far more than any gauge
needs — the headroom is there to survive one unexpected requantization, not
because cabin pressure deserves six decimal places.

**Never encode into A.** A composited surface's alpha is not guaranteed to
survive to the shader untouched, and an opaque surface may have its alpha
channel discarded entirely.

## Item IDs: what the spec said, and what the feed actually carries

The tech spec's gauge list was wrong on every item but one. Verified against
`Pi/database_initialize.py` in the ISS-Mimic repo, which is the ID-to-label
table their own client is built from.

| Spec claimed | Real meaning of that ID | What we actually use |
|---|---|---|
| `TIME_000001` = mission elapsed time | Greenwich Mean Time | `TIME_000001`, as GMT |
| `USLAB000032` = cabin pressure | J2000 propagated state vector **X**, km | `USLAB000058` for cabin pressure |
| `USLAB000058` = cabin temperature | LAB PCA **cabin pressure**, psia | `USLAB000059` for cabin temp |
| `Z1000005` = solar array voltage | CMG-1 **spin motor current** | `S4000001` for array 1A voltage |
| `AIRLOCK000049` = airlock pressure | Crewlock pressure -- correct | `AIRLOCK000049` |
| "(attitude/quaternion items)" | unspecified | `USLAB000018..21`, LVLH pointing quaternion |
| OpenNotify REST for lat/long | — | `USLAB000032..37`, the real state vector |

That last row is the important one. The spec planned to poll a REST endpoint
for a ground position because it assumed the stream did not carry one. It
does: `USLAB000032..34` is the J2000 propagated position in km and
`USLAB000035..37` is the velocity. So the cockpit gets a real state vector
rather than a scraped lat/long, the shader can propagate it between updates,
and OpenNotify is demoted to a fallback that is only consulted when the stream
has never once delivered a position.

Units were read off the live feed, not assumed. Cabin and crewlock pressure
come through in **mmHg** (ambient reads ~750, which is the 14.7 psia everyone
quotes) and velocity in **m/s** (~7650). Both were psia and km/s in the first
draft of this map, which pinned two gauges to full scale and left the velocity
needle at zero -- caught only by looking at the numbers the station actually
sent. Position is in km, magnitude ~6800, which is Earth radius plus 420.

`USLAB000059` is `LAB1P6_CCAA_In_T1` -- the Common Cabin Air Assembly inlet
temperature, which is cabin air on its way into the air conditioner. It is the
closest thing the public feed has to "cabin temperature" and the panel labels
it CCAA IN, not CABIN, because that is what it is.

## Texel map

Row 1, x = 0..63. Every texel is `texelFetch(tex, ivec2(x, 1), 0)`.

| x | Name | Range (lo..hi) | Units | ISSLIVE item |
|---|---|---|---|---|
| 0 | `MAGIC_A` | — | — | constant `0xA5,0x5A,0xC0` |
| 1 | `MAGIC_B` | — | — | constant, low nibble = schema |
| 2 | `SEQ` | 0..1048575 | counter | increments every write, wraps |
| 3 | `AGE` | 0..3600 | seconds | since last good stream update |
| 4 | `FLAGS` | bitfield | — | see below |
| 5 | `GMT` | 0..86400 | seconds of day | `TIME_000001` |
| 6 | `CABIN_P` | 0..800 | mmHg | `USLAB000058` |
| 7 | `CABIN_T` | 0..40 | degC | `USLAB000059` |
| 8 | `CREWLOCK_P` | 0..800 | mmHg | `AIRLOCK000049` |
| 9 | `ARRAY_V` | 0..200 | volts | `S4000001` |
| 10 | `BETA` | -90..90 | degrees | `USLAB000040` |
| 11..13 | `POS_XYZ` | -8000..8000 | km, J2000 | `USLAB000032..34` |
| 14..16 | `VEL_XYZ` | -8000..8000 | m/s, J2000 | `USLAB000035..37` |
| 17..20 | `QUAT_0123` | -1..1 | — | `USLAB000018..21` |
| 21 | `PPO2` | 0..250 | mmHg | `USLAB000053` |
| 22 | `PPN2` | 0..800 | mmHg | `USLAB000054` |
| 23 | `PPCO2` | 0..15 | mmHg | `USLAB000055` |
| 24 | `ISS_MASS` | 0..500000 | kg | `USLAB000039` |
| 25 | `SIGNAL` | 0..3 | class | `TIME_000001` Status.Class (AOS/LOS) |
| 26..62 | reserved | — | — | must be written as zero |
| 63 | `CHECK` | — | — | see below |

`SIGNAL` is the one field that is not a measurement. The ISSLIVE feed carries
its own acquisition-of-signal state on `TIME_000001`, because the station
loses the ground for real when it crosses the gap over the Indian Ocean and
during TDRS handovers. So the panel can distinguish "the daemon is broken"
from "the station is out of contact", and those light different lamps.

### FLAGS (texel 4)

Packed as a 20-bit integer, bit 0 = least significant:

| Bit | Meaning |
|---|---|
| 0 | stream connected |
| 1 | stream had a value in the last 60 s |
| 2 | EVA in progress (airlock depressurized) |
| 3 | position is from the REST fallback, not the stream |
| 4 | position is dead-reckoned (no network at all) |
| 5 | daemon is shutting down |

### CHECK (texel 63)

The sum of the 20-bit codes of texels 0..62, modulo 1048576, packed the same
way. The shader recomputes it. **This is not a security measure** — nothing
here is adversarial. It exists so the shader can tell "the daemon is running
and the pixels arrived intact" apart from "there is a beige window in the top
left corner of the screen", which is otherwise indistinguishable and produces
a cockpit reading 14.7 psi of nonsense.

## What the shader does when the strip is wrong

Falls back, in this order:

1. **Magic and check both good** — decode everything, gauges live.
2. **Magic good, check bad** — one torn frame. Hold the previous frame's
   values, do not flag. Tearing is expected; the daemon writes while the
   compositor reads and there is no synchronization between them.
3. **Magic absent for more than 2 seconds** — daemon is not running. Fall
   back to the values baked into `cockpit.frag` by `hyprland.lua`, propagate
   the orbit on the GPU from `time`, and light the **STALE** annunciator.

Case 3 is the committed fallback, and it is a working cockpit — the orbital
mechanics (ground track, terminator, orbital sunrise, MET) are computed on the
GPU from baked elements and need no network and no daemon at all. What is lost
is the live cabin telemetry and the EVA lamp. The panel says so rather than
silently freezing, which is the whole point of the annunciator.

## What is streamed and what is computed

Deliberately split, because streaming a thing that can be computed exactly is
worse than computing it:

- **Computed on the GPU**, from elements baked at Hyprland config load:
  ground track, subpoint, terminator, orbital sunrise/sunset, MET between
  updates. These need no network and stay correct for as long as the
  compositor runs.
- **Streamed**, because nothing can derive them: cabin pressure, cabin
  temperature, airlock pressure, array voltage, attitude, beta angle.

The stream also *corrects* the computed values — texels 11..16 overwrite the
propagated position whenever the stream is live, so the panel is never wrong
by more than the propagation error while the daemon is up.
