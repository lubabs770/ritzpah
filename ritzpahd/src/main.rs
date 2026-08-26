//! ritzpahd -- the daemon behind the ritzpah "ISS Cockpit" theme.
//!
//! It holds one WebSocket to Lightstreamer's public ISSLIVE feed, decodes the
//! telemetry, and paints it into a 64x2 layer-shell surface that the theme's
//! screen shader reads back out of the composited frame. See
//! `themes/iss-cockpit/TELEMETRY.md` for the texel map and the reasoning.
//!
//! WHAT THIS DOES TO YOUR MACHINE, stated plainly because it does more than a
//! theme normally should and you should not have to read the source to find
//! out:
//!   opens   one TLS WebSocket to push.lightstreamer.com (public ISSLIVE
//!           adapter set; no account, no key, no credentials of any kind)
//!   sends   nothing but the TLCP subscription itself
//!   creates one 64x2 pixel layer-shell surface per output
//!   writes  nothing to disk, ever
//!   reads   no files and no environment beyond WAYLAND_DISPLAY
//! That is the whole list. It is a separate binary you start yourself; the
//! theme works without it and says so on the panel when it is not running.

mod gauges;
mod strip;
mod tlcp;

use std::sync::mpsc;
use std::sync::{Arc, Mutex};
use std::thread;

use gauges::{now_unix, Backoff, Gauges, Shared};
use tlcp::{Event, Field};

fn usage() -> ! {
    eprintln!(
        "\
ritzpahd -- live ISS telemetry for the ritzpah ISS Cockpit theme

USAGE:
    ritzpahd              stream, and paint the strip on every output
    ritzpahd --print      stream and print gauges to stdout; no Wayland surface
    ritzpahd --dump       print the encoded strip as hex and exit
    ritzpahd --help

The strip is a 64x2 layer-shell surface at the top-left of each output, in the
namespace `{}`. It is painted over by the theme's screen shader and does not
appear in screenshots. Nothing is written to disk.",
        strip::NAMESPACE
    );
    std::process::exit(2)
}

fn apply(g: &mut Gauges, field: Field, v: f64, now: f64) {
    match field {
        Field::CabinP => g.cabin_p.set(v, now),
        Field::CabinT => g.cabin_t.set(v, now),
        Field::CrewlockP => g.crewlock_p.set(v, now),
        Field::ArrayV => g.array_v.set(v, now),
        Field::Beta => g.beta.set(v, now),
        Field::PosX => g.pos[0].set(v, now),
        Field::PosY => g.pos[1].set(v, now),
        Field::PosZ => g.pos[2].set(v, now),
        Field::VelX => g.vel[0].set(v, now),
        Field::VelY => g.vel[1].set(v, now),
        Field::VelZ => g.vel[2].set(v, now),
        Field::Quat0 => g.quat[0].set(v, now),
        Field::Quat1 => g.quat[1].set(v, now),
        Field::Quat2 => g.quat[2].set(v, now),
        Field::Quat3 => g.quat[3].set(v, now),
        Field::PpO2 => g.ppo2.set(v, now),
        Field::PpN2 => g.ppn2.set(v, now),
        Field::PpCO2 => g.ppco2.set(v, now),
        Field::Mass => g.mass.set(v, now),
        Field::Gmt => g.gmt.set(v, now),
        Field::Signal => g.signal = v,
    }
    g.last_update = Some(now);
    g.seq = g.seq.wrapping_add(1);
}

/// Owns the socket. Reconnects forever, because Lightstreamer ends sessions as
/// a matter of routine and a cockpit that gives up after one rotation is not a
/// cockpit.
fn stream(shared: Shared) {
    let (tx, rx) = mpsc::channel::<Event>();

    {
        let shared = Arc::clone(&shared);
        thread::spawn(move || {
            for ev in rx {
                let now = now_unix();
                let mut g = shared.lock().unwrap_or_else(|e| e.into_inner());
                match ev {
                    Event::Connected => g.connected = true,
                    Event::Value(f, v) => apply(&mut g, f, v, now),
                }
            }
        });
    }

    let mut backoff = Backoff::new();
    loop {
        match tlcp::Client::run(&tx) {
            Ok(()) => {
                // A clean session end. Expected, frequent, not worth a line of
                // log -- but reset the backoff so we come straight back.
                backoff.reset();
            }
            Err(e) => {
                eprintln!("ritzpahd: stream: {e}");
            }
        }
        {
            let mut g = shared.lock().unwrap_or_else(|e| e.into_inner());
            g.connected = false;
        }
        thread::sleep(backoff.next_delay());
    }
}

fn print_loop(shared: Shared) -> ! {
    // A dash rather than a number means the gauge has never been received at
    // all, which is a different thing from reading zero and is the first
    // question to ask when an instrument looks dead.
    fn f(r: &gauges::Reading, prec: usize) -> String {
        match r.seen {
            Some(_) => format!("{:.*}", prec, r.value),
            None => "--".to_string(),
        }
    }
    loop {
        thread::sleep(std::time::Duration::from_secs(2));
        let g = shared.lock().unwrap_or_else(|e| e.into_inner());
        let age = g.last_update.map(|t| now_unix() - t).unwrap_or(f64::INFINITY);
        println!(
            "conn={} age={:>5.1}s seq={:<6} cabin={} psia  ccaa={}C  crewlock={} \
             array={}V  beta={}  ppO2={} ppCO2={}  mass={}kg  pos=[{} {} {}]km  |v|={:.2}km/s",
            g.connected, age, g.seq,
            f(&g.cabin_p, 2), f(&g.cabin_t, 1), f(&g.crewlock_p, 2),
            f(&g.array_v, 1), f(&g.beta, 1), f(&g.ppo2, 1), f(&g.ppco2, 2),
            f(&g.mass, 0),
            f(&g.pos[0], 0), f(&g.pos[1], 0), f(&g.pos[2], 0),
            (g.vel[0].value.powi(2) + g.vel[1].value.powi(2) + g.vel[2].value.powi(2)).sqrt(),
        );
    }
}

fn main() {
    // rustls will not pick a crypto provider on its own, and the failure mode
    // is a panic on the first connect rather than an error, so this is done
    // once up front where it is visible.
    let _ = rustls::crypto::ring::default_provider().install_default();

    let args: Vec<String> = std::env::args().skip(1).collect();
    let mode = args.first().map(String::as_str).unwrap_or("");
    if mode == "--help" || mode == "-h" {
        usage();
    }
    if !mode.is_empty() && mode != "--print" && mode != "--dump" {
        eprintln!("ritzpahd: unknown argument `{mode}`");
        usage();
    }

    let shared: Shared = Arc::new(Mutex::new(Gauges::default()));

    if mode == "--dump" {
        // Encode whatever we have (nothing, on a cold start) and print it, so
        // the texel map can be checked against the shader without a
        // compositor, a network, or a station.
        let mut px = [0u32; gauges::STRIP_W * gauges::STRIP_H];
        let g = shared.lock().unwrap();
        gauges::render(&g, &mut px);
        for (x, p) in px[gauges::STRIP_W..].iter().enumerate() {
            println!("{x:>2}  #{:06x}", p & 0x00FF_FFFF);
        }
        return;
    }

    {
        let shared = Arc::clone(&shared);
        thread::spawn(move || stream(shared));
    }

    if mode == "--print" {
        print_loop(shared);
    }

    if let Err(e) = strip::run(shared) {
        eprintln!("ritzpahd: wayland: {e}");
        eprintln!("ritzpahd: (no compositor, or no wlr-layer-shell. --print streams without one.)");
        std::process::exit(1);
    }
}
