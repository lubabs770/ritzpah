# The prompts that summoned ISS Cockpit

2026-08-25. Recorded verbatim, in order, typos and all. The theme grew across
four turns and the last three are the ones that decided what it is.

---

## 1

> use ritzpah skill, this is my prompt "this is gonna be a mad-rad cockpit view,
> astrounat, cool looking, classy, immersive, live and real space explorer theme,
> here's a tech_spec claude churned out - # TECH SPEC — ritzpah ISS Cockpit
> ("live" shader theme)
>
> ## Goal
> A live Omarchy/ritzpah shader theme that renders a spaceship cockpit whose gauges
> are driven by REAL International Space Station telemetry, streamed continuously.
>
> ## Architecture (3 parts, one data boundary)
>
>     Lightstreamer WSS ──> ritzpahd (Rust daemon) ──> iss.state (data texture) ──> cockpit.glsl (host samples it)
>
> The daemon owns the network; the shader only draws. They meet at ONE file: a tiny
> data texture the shader host uploads each frame. Nothing about the shader or daemon
> changes when the host changes (glslViewer now → shader-wallpaper daemon later).
>
> ## Part 1 — ritzpahd (headless Rust daemon)
>
> Rationale: lowest 24/7 idle footprint (~few MB RSS, no GC, ~0% idle CPU).
>
> Responsibilities:
> - Hold ONE persistent WSS connection to Lightstreamer and hand-roll the TLCP
>   (Text Lightstreamer Client Protocol) — do NOT pull in a Lightstreamer client crate.
> - Poll OpenNotify REST for ground position (lat/long) on an interval.
> - On every update, write all current gauge values into a small data texture file
>   the shader host can upload.
>
> ### Lightstreamer / TLCP details (public ISS feed)
> - Endpoint base: wss://push.lightstreamer.com/lightstreamer
> - Adapter set:   ISSLIVE
> - Mode:          MERGE subscriptions (each item = latest snapshot, fields Value + TimeStamp)
> - No auth / no API key for the public ISSLIVE feed.
>
> TLCP is a newline-delimited text protocol over the WS transport. Hand-roll these steps:
> 1. WS connect (TLS) to the endpoint; TLCP runs as text frames over that socket.
> 2. Send a `create_session` request specifying adapter set ISSLIVE; parse the
>    session-creation response line for the assigned session id.
> 3. Issue `control` messages to add MERGE subscriptions for the item list below,
>    requesting fields Value,TimeStamp.
> 4. Read the streaming update lines (item index + field values) and parse them into
>    the gauge state. Handle the periodic PROBE/keepalive lines as no-ops.
> 5. Handle session end / content-length exhaustion by reconnecting and re-subscribing
>    (Lightstreamer WILL end sessions periodically — reconnect is mandatory, not optional).
>
> Reference implementations to read (NOT to depend on): Lightstreamer's own
> Quickstart-client-socket (raw TLCP over HTTP, same message grammar) and the
> ISS-Mimic project's telemetry item list.
>
> ### Gauge item list (ISSLIVE) — ALL gauges
> Subscribe to the full set; map each to a cockpit instrument:
> - TIME_000001    — mission elapsed time            → MET readout
> - USLAB000032    — cabin pressure                  → pressure gauge
> - USLAB000058    — cabin temperature               → temp gauge
> - AIRLOCK000049  — airlock pressure (moves in EVA)  → airlock gauge / EVA warning lamp
> - Z1000005       — solar array voltage             → power gauge
> - (attitude/quaternion items)                       → artificial-horizon
> - OpenNotify iss-now.json (REST, not the stream)   → lat/long map dot / ground track
> Verify exact item ids against the ISS-Mimic public item list before finalizing.
>
> ## Part 2 — Data boundary: iss.state
>
> Format: a 32×1 (or NxM) RGBA texture written to /tmp/ritzpah/iss.png (or raw buffer).
> - One texel per gauge value; pack normalized value (and range/flags) into channels.
> - Daemon rewrites it on each update. Atomic write (temp file + rename) to avoid
>   torn reads.
> - This is the ONLY contract between daemon and shader. Keep a documented
>   texel-map: texel index → which gauge → what the RGBA channels mean.
>
> ## Part 3 — cockpit.glsl
>
> - Samples iss.state via texelFetch(); one texel per gauge, no per-uniform plumbing.
> - Draws the cockpit: needle gauges, MET readout, artificial horizon, EVA warning
>   lamp (driven by airlock pressure), ground-track dot.
> - Follows ritzpah shader-theme conventions (cf. Ego Death / Lunation): reads theme
>   colors from the active palette; the telemetry drives motion, the theme drives color.
>
> ## Host (where cockpit.glsl runs)
> - Develop under glslViewer: it loads a texture and reloads the shader on save — the
>   fastest iterate loop, minimal glue.
> - Ship as a shader-wallpaper theme: point the wallpaper daemon at the same
>   cockpit.glsl + iss.state. Same texture contract — no code change on migration.
>
> ## Non-negotiables / gotchas
> - Reconnect + re-subscribe on session end (Lightstreamer closes streams regularly).
> - Treat PROBE/keepalive lines as no-ops.
> - Daemon must degrade gracefully when offline: last-known values + a stale flag in
>   the texture so the shader can dim/flag gauges rather than freeze silently.
> - No secrets: public feed, no key committed.
> - Atomic texture writes to avoid the shader sampling a half-written file. go go go!!"

## 2

> why is htis not shippable, the project specificly made it freeform, as long as
> the user knows what's about to happen, why not?

## 3

> what's your opinion

## 4

> no then it's just another lunation, it's gotta have the stream

---

## What the argument changed

The spec's data boundary — a PNG the shader samples — cannot exist under
Hyprland, whose screen-shader uniforms are a fixed compiled-in enum with no
second sampler. That was the one hard constraint, and it survived.

Everything else in the objection did not. The "no timers" rule quoted back at
prompt 2 is Lunation's own boast, not a law of the collection, and this repo's
actual ethic is to *compute and publish* what executes rather than forbid it.

Prompt 3 got an opinion that was wrong: build the orbital half, skip the
stream, on the grounds that almost nothing in ISSLIVE actually moves. Prompt 4
is the correction, and it is the reason the theme exists — a propagated TLE is
a simulation, and the whole claim of this theme is that it is a *connection*.
The gauges have to twitch, and the twitch has to be real.

So the boundary moved from a file to the framebuffer: the daemon paints
telemetry into 64x2 pixels of actual screen, and the shader reads the screen to
find out where the ISS is, then paints over the evidence. See `TELEMETRY.md`.
