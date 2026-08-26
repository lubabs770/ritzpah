//! The shared state, and the encoder that turns it into pixels.
//!
//! This module is the Rust half of `themes/iss-cockpit/TELEMETRY.md`. If you
//! change a texel index or a range here, change it there too -- the shader
//! reads that document, not this file.

use std::sync::{Arc, Mutex};
use std::time::{Instant, SystemTime, UNIX_EPOCH};

pub const STRIP_W: usize = 64;
pub const STRIP_H: usize = 2;

/// Bumped only when the meaning of an existing texel changes. Carried in the
/// low nibble of MAGIC_B so a shader built against an older map can refuse to
/// decode rather than draw a confident lie.
pub const SCHEMA: u32 = 1;

pub const CODE_MAX: u32 = 0x0F_FFFF; // 20 bits

// ---------------------------------------------------------------- texel map
pub const T_MAGIC_A: usize = 0;
pub const T_MAGIC_B: usize = 1;
pub const T_SEQ: usize = 2;
pub const T_AGE: usize = 3;
pub const T_FLAGS: usize = 4;
pub const T_GMT: usize = 5;
pub const T_CABIN_P: usize = 6;
pub const T_CABIN_T: usize = 7;
pub const T_CREWLOCK_P: usize = 8;
pub const T_ARRAY_V: usize = 9;
pub const T_BETA: usize = 10;
pub const T_POS: usize = 11; // ..13
pub const T_VEL: usize = 14; // ..16
pub const T_QUAT: usize = 17; // ..20
pub const T_PPO2: usize = 21;
pub const T_PPN2: usize = 22;
pub const T_PPCO2: usize = 23;
pub const T_MASS: usize = 24;
pub const T_SIGNAL: usize = 25;
pub const T_CHECK: usize = 63;

// ------------------------------------------------------------------- flags
pub const F_CONNECTED: u32 = 1 << 0;
pub const F_FRESH: u32 = 1 << 1;
pub const F_EVA: u32 = 1 << 2;
pub const F_POS_REST: u32 = 1 << 3;
pub const F_POS_DEAD_RECKONED: u32 = 1 << 4;
pub const F_SHUTTING_DOWN: u32 = 1 << 5;

/// A single telemetry value plus when we last actually heard it. `None` means
/// we have never received it -- which is different from "it is zero", and the
/// shader is told the difference via the freshness flags.
#[derive(Clone, Copy, Default)]
pub struct Reading {
    pub value: f64,
    pub seen: Option<f64>, // unix seconds
}

impl Reading {
    pub fn set(&mut self, v: f64, now: f64) {
        self.value = v;
        self.seen = Some(now);
    }
}

#[derive(Default)]
pub struct Gauges {
    pub gmt: Reading,
    pub cabin_p: Reading,
    pub cabin_t: Reading,
    pub crewlock_p: Reading,
    pub array_v: Reading,
    pub beta: Reading,
    pub pos: [Reading; 3],
    pub vel: [Reading; 3],
    pub quat: [Reading; 4],
    pub ppo2: Reading,
    pub ppn2: Reading,
    pub ppco2: Reading,
    pub mass: Reading,
    /// AOS/LOS class straight off the feed's own `Status.Class` field.
    pub signal: f64,

    pub connected: bool,
    pub shutting_down: bool,
    pub pos_from_rest: bool,
    /// Wraps at 20 bits, which is the point -- the shader only ever compares
    /// it to the previous frame's value to notice the daemon has gone quiet.
    pub seq: u32,
    pub last_update: Option<f64>,
}

pub type Shared = Arc<Mutex<Gauges>>;

pub fn now_unix() -> f64 {
    SystemTime::now()
        .duration_since(UNIX_EPOCH)
        .map(|d| d.as_secs_f64())
        .unwrap_or(0.0)
}

/// Normalize into the declared range and quantize to 20 bits.
fn code(value: f64, lo: f64, hi: f64) -> u32 {
    if !value.is_finite() {
        return 0;
    }
    let t = ((value - lo) / (hi - lo)).clamp(0.0, 1.0);
    (t * CODE_MAX as f64).round() as u32
}

/// 20 bits across R, G and B at 8/8/4. The low nibble is left-aligned into B's
/// high nibble so that an unexpected requantization down to RGB565 costs
/// precision from the bottom instead of scrambling the value.
fn pack(code: u32) -> [u8; 3] {
    let c = code & CODE_MAX;
    [
        ((c >> 12) & 0xFF) as u8,
        ((c >> 4) & 0xFF) as u8,
        (((c & 0xF) << 4) & 0xFF) as u8,
    ]
}

/// Render the current state into `STRIP_W * STRIP_H` XRGB8888 pixels.
///
/// Row 0 is deliberately left black and is never read by the shader: a 1 px
/// surface has nowhere to hide from a corner radius, and the top row is what a
/// rounding or blur rule would eat first.
pub fn render(g: &Gauges, out: &mut [u32]) {
    debug_assert_eq!(out.len(), STRIP_W * STRIP_H);

    let now = now_unix();
    let mut codes = [0u32; STRIP_W];

    // Magic. Constant, and chosen to be a value no ordinary window content
    // lands on by accident: two complementary bytes and a third that is not a
    // multiple of anything.
    codes[T_MAGIC_A] = 0xA5_5AC;
    codes[T_MAGIC_B] = 0x1_0000 | (SCHEMA & 0xF);

    codes[T_SEQ] = g.seq & CODE_MAX;

    let age = g.last_update.map(|t| (now - t).max(0.0)).unwrap_or(3600.0);
    codes[T_AGE] = code(age, 0.0, 3600.0);

    let mut flags = 0u32;
    if g.connected {
        flags |= F_CONNECTED;
    }
    if age <= 60.0 {
        flags |= F_FRESH;
    }
    // An EVA is not announced on the feed; it is inferred, the same way the
    // crew infers it, from the crewlock being pumped down. Ambient is about
    // 750 mmHg and a depress runs down toward 260 before the hatch opens, so
    // 500 sits clear of both ends and of ordinary cabin drift.
    if g.crewlock_p.seen.is_some() && g.crewlock_p.value < 500.0 {
        flags |= F_EVA;
    }
    if g.pos_from_rest {
        flags |= F_POS_REST;
    }
    if g.pos[0].seen.is_none() && !g.pos_from_rest {
        flags |= F_POS_DEAD_RECKONED;
    }
    if g.shutting_down {
        flags |= F_SHUTTING_DOWN;
    }
    codes[T_FLAGS] = flags & CODE_MAX;

    codes[T_GMT] = code(g.gmt.value, 0.0, 86400.0);
    // mmHg, not psia. The feed reports cabin and crewlock pressure in
    // millimetres of mercury -- ambient reads about 750, which is the 14.7
    // psia everybody quotes. Assuming psia here silently pins both gauges to
    // full scale.
    codes[T_CABIN_P] = code(g.cabin_p.value, 0.0, 800.0);
    codes[T_CABIN_T] = code(g.cabin_t.value, 0.0, 40.0);
    codes[T_CREWLOCK_P] = code(g.crewlock_p.value, 0.0, 800.0);
    codes[T_ARRAY_V] = code(g.array_v.value, 0.0, 200.0);
    codes[T_BETA] = code(g.beta.value, -90.0, 90.0);
    for i in 0..3 {
        codes[T_POS + i] = code(g.pos[i].value, -8000.0, 8000.0);
        // m/s, not km/s: the feed reports about 7650, and the ISS really is
        // doing 7.65 km/s.
        codes[T_VEL + i] = code(g.vel[i].value, -8000.0, 8000.0);
    }
    for i in 0..4 {
        codes[T_QUAT + i] = code(g.quat[i].value, -1.0, 1.0);
    }
    codes[T_PPO2] = code(g.ppo2.value, 0.0, 250.0);
    codes[T_PPN2] = code(g.ppn2.value, 0.0, 800.0);
    codes[T_PPCO2] = code(g.ppco2.value, 0.0, 15.0);
    codes[T_MASS] = code(g.mass.value, 0.0, 500_000.0);
    codes[T_SIGNAL] = code(g.signal, 0.0, 3.0);

    // Not a security measure -- nothing here is adversarial. It exists so the
    // shader can tell a running daemon apart from a beige window sitting in
    // the top-left corner of the screen, which is otherwise indistinguishable
    // and produces a cockpit full of confident nonsense.
    let sum: u64 = codes[..T_CHECK].iter().map(|&c| c as u64).sum();
    codes[T_CHECK] = (sum % (CODE_MAX as u64 + 1)) as u32;

    for (x, &c) in codes.iter().enumerate() {
        let [r, g_, b] = pack(c);
        let px = 0xFF00_0000 | ((r as u32) << 16) | ((g_ as u32) << 8) | b as u32;
        out[STRIP_W + x] = px; // row 1: the data
        out[x] = 0xFF00_0000; // row 0: sacrificial, always black
    }
}

/// Wall-clock helper for the reconnect backoff, kept here so the socket thread
/// does not have to care what time it is.
pub struct Backoff {
    start: Instant,
    step: u32,
}

impl Backoff {
    pub fn new() -> Self {
        Backoff { start: Instant::now(), step: 0 }
    }
    pub fn reset(&mut self) {
        self.step = 0;
        self.start = Instant::now();
    }
    /// 1, 2, 4, 8 ... capped at 60 seconds. Lightstreamer ends sessions as a
    /// matter of routine, so the first retry has to be quick or the panel
    /// blinks STALE every time the server rotates us.
    pub fn next_delay(&mut self) -> std::time::Duration {
        let secs = 1u64 << self.step.min(6);
        if self.step < 6 {
            self.step += 1;
        }
        std::time::Duration::from_secs(secs.min(60))
    }
}
