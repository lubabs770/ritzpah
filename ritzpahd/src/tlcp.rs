//! A hand-rolled TLCP client, WS transport only.
//!
//! TLCP is Lightstreamer's own text protocol. This implements the small
//! subset needed to hold one MERGE subscription open against the public
//! ISSLIVE adapter set: create a session, add two subscriptions, read update
//! lines, and notice when the server ends the session so we can start again.
//!
//! Grammar checked against the TLCP 2.1.0 specification, sections on WS
//! Transport, Session Creation, Subscription Control, and Real-Time Update.
//! The parts that matter and are easy to get wrong are all in `apply_update`.

use std::io::{Error, ErrorKind, Result};
use std::sync::mpsc::Sender;

use tungstenite::client::IntoClientRequest;
use tungstenite::http::HeaderValue;
use tungstenite::Message;

/// The subprotocol is version-pinned by name, so this constant and the grammar
/// implemented below have to move together. 2.1.0 is used rather than the
/// newest because it is the version this parser was written against and the
/// server accepts it; there is nothing in a later revision that this client
/// needs.
const SUBPROTOCOL: &str = "TLCP-2.1.0.lightstreamer.com";
const ENDPOINT: &str = "wss://push.lightstreamer.com/lightstreamer";
const ADAPTER_SET: &str = "ISSLIVE";

/// The client identifier the specification assigns to generic (non-SDK)
/// clients. It is not a secret, not an account, and not rate-limiting us --
/// it is how the server records that this is a hand-rolled client. Sent
/// percent-encoded, exactly as the spec prints it.
const CID: &str = "mgQkwtwdysogQz2BJ4Ji%20kOj2Bg";

/// Every item we subscribe to, in order. The U lines refer to items by their
/// 1-based index into this list, so the ORDER IS THE WIRE FORMAT: append only,
/// never reorder, or every gauge silently reads some other instrument.
///
/// Meanings verified against ISS-Mimic's own ID-to-label table. Several
/// differ from what the original tech spec assumed; see TELEMETRY.md.
pub const ITEMS: &[(&str, Field)] = &[
    ("USLAB000058", Field::CabinP),     // LAB_PCA_Cabin_Pressure, psia
    ("USLAB000059", Field::CabinT),     // LAB1P6_CCAA_In_T1, deg C
    ("AIRLOCK000049", Field::CrewlockP), // crewlock_pres, psia
    ("S4000001", Field::ArrayV),        // voltage_1a
    ("USLAB000040", Field::Beta),       // USGNC_PS_Solar_Beta_Angle
    ("USLAB000032", Field::PosX),       // J2000 propagated state vector, km
    ("USLAB000033", Field::PosY),
    ("USLAB000034", Field::PosZ),
    ("USLAB000035", Field::VelX),       // km/s
    ("USLAB000036", Field::VelY),
    ("USLAB000037", Field::VelZ),
    ("USLAB000018", Field::Quat0),      // LVLH pointing attitude quaternion
    ("USLAB000019", Field::Quat1),
    ("USLAB000020", Field::Quat2),
    ("USLAB000021", Field::Quat3),
    ("USLAB000053", Field::PpO2),       // LAB_MCA_ppO2, mmHg
    ("USLAB000054", Field::PpN2),
    ("USLAB000055", Field::PpCO2),
    ("USLAB000039", Field::Mass),       // iss_mass, kg
];

/// TIME_000001 is subscribed separately because it is the one item that
/// carries the feed's own acquisition-of-signal state, and that needs two
/// extra fields in the schema.
const TIME_ITEM: &str = "TIME_000001";

const SUB_MAIN: u32 = 1;
const SUB_TIME: u32 = 2;

#[derive(Clone, Copy, Debug)]
pub enum Field {
    CabinP, CabinT, CrewlockP, ArrayV, Beta,
    PosX, PosY, PosZ, VelX, VelY, VelZ,
    Quat0, Quat1, Quat2, Quat3,
    PpO2, PpN2, PpCO2, Mass,
    Gmt, Signal,
}

/// What the socket thread hands back to the main thread.
pub enum Event {
    Connected,
    Value(Field, f64),
}

fn err(msg: impl Into<String>) -> Error {
    Error::new(ErrorKind::Other, msg.into())
}

/// Decode a TLCP field value. Percent-encoding only; the escape set is
/// documented as "meta characters such as the pipe and CR-LF", but the
/// decoder is general because the spec permits any further percent-encoding
/// so long as it is UTF-8 based.
fn percent_decode(s: &str) -> String {
    let b = s.as_bytes();
    let mut out = Vec::with_capacity(b.len());
    let mut i = 0;
    while i < b.len() {
        if b[i] == b'%' && i + 2 < b.len() {
            let hex = |c: u8| -> Option<u8> {
                match c {
                    b'0'..=b'9' => Some(c - b'0'),
                    b'a'..=b'f' => Some(c - b'a' + 10),
                    b'A'..=b'F' => Some(c - b'A' + 10),
                    _ => None,
                }
            };
            if let (Some(h), Some(l)) = (hex(b[i + 1]), hex(b[i + 2])) {
                out.push((h << 4) | l);
                i += 3;
                continue;
            }
        }
        out.push(b[i]);
        i += 1;
    }
    String::from_utf8_lossy(&out).into_owned()
}

/// Walk one `U` line's field list and emit the values that changed.
///
/// The field pointer semantics are the whole reason this function exists, and
/// all four cases are load-bearing:
///   - an EMPTY value means unchanged; do not emit, advance one
///   - `#` means null; do not emit, advance one
///   - `$` means the empty string; not a number, so do not emit, advance one
///   - `^N` means N fields including this one are unchanged; advance N
/// Anything else is content: percent-decode it and parse.
///
/// Getting `^N` wrong is the subtle failure, because it does not error -- it
/// shifts every later field by some amount and the panel reads plausible
/// values off the wrong instruments.
fn walk_fields<F: FnMut(usize, &str)>(body: &str, mut emit: F) {
    let mut idx = 0usize; // 0-based field index
    for raw in body.split('|') {
        if raw.is_empty() {
            idx += 1;
        } else if raw == "#" || raw == "$" {
            idx += 1;
        } else if let Some(n) = raw.strip_prefix('^') {
            idx += n.parse::<usize>().unwrap_or(1);
        } else {
            emit(idx, raw);
            idx += 1;
        }
    }
}

pub struct Client;

impl Client {
    /// Connect, subscribe, and pump updates into `tx` until the stream ends.
    ///
    /// Returns `Ok(())` on a clean server-side session end (which is routine
    /// and expected -- Lightstreamer rotates sessions) and `Err` on anything
    /// else. Either way the caller reconnects; the distinction exists only so
    /// the log can stay quiet about the normal case.
    pub fn run(tx: &Sender<Event>) -> Result<()> {
        let mut req = ENDPOINT
            .into_client_request()
            .map_err(|e| err(format!("bad endpoint: {e}")))?;
        req.headers_mut().insert(
            "Sec-WebSocket-Protocol",
            HeaderValue::from_static(SUBPROTOCOL),
        );

        let (mut sock, _) =
            tungstenite::connect(req).map_err(|e| err(format!("connect: {e}")))?;

        // Over WS a request is the request name, CRLF, then the query string.
        // No `.txt`, no LS_protocol parameter -- the subprotocol carries the
        // version, and the socket itself carries the session.
        sock.send(Message::Text(
            format!("create_session\r\nLS_adapter_set={ADAPTER_SET}&LS_cid={CID}").into(),
        ))
        .map_err(|e| err(format!("create_session: {e}")))?;

        let mut subscribed = false;

        loop {
            let msg = sock.read().map_err(|e| err(format!("read: {e}")))?;
            let text = match msg {
                Message::Text(t) => t.to_string(),
                Message::Binary(_) => continue,
                Message::Ping(p) => {
                    let _ = sock.send(Message::Pong(p));
                    continue;
                }
                Message::Close(_) => return Ok(()),
                _ => continue,
            };

            for line in text.split("\r\n").flat_map(|l| l.split('\n')) {
                let line = line.trim_end_matches('\r');
                if line.is_empty() {
                    continue;
                }

                // PROBE and NOOP are keepalives and mean nothing. SYNC, CONS,
                // SERVNAME, CLIENTIP and PROG are session bookkeeping we do
                // not act on. All are explicitly no-ops rather than falling
                // into a catch-all, so an unrecognised line stays visible.
                if line == "PROBE" || line.starts_with("NOOP") {
                    continue;
                }
                if line.starts_with("SYNC")
                    || line.starts_with("CONS")
                    || line.starts_with("SERVNAME")
                    || line.starts_with("CLIENTIP")
                    || line.starts_with("PROG")
                    || line.starts_with("REQOK")
                    || line.starts_with("CONF")
                    || line.starts_with("EOS")
                    || line.starts_with("CS")
                    || line.starts_with("OV")
                {
                    continue;
                }

                if let Some(rest) = line.strip_prefix("CONOK,") {
                    // CONOK,<session-ID>,<request-limit>,<keep-alive>,<control-link>
                    let _session = rest.split(',').next().unwrap_or_default();
                    if !subscribed {
                        Self::subscribe(&mut sock)?;
                        subscribed = true;
                    }
                    let _ = tx.send(Event::Connected);
                    continue;
                }

                if let Some(rest) = line.strip_prefix("CONERR,") {
                    return Err(err(format!("CONERR {rest}")));
                }
                if let Some(rest) = line.strip_prefix("REQERR,") {
                    return Err(err(format!("REQERR {rest}")));
                }
                if let Some(rest) = line.strip_prefix("ERROR,") {
                    return Err(err(format!("ERROR {rest}")));
                }
                if line.starts_with("END") {
                    // Routine. The server rotates sessions and expects the
                    // client to come straight back.
                    return Ok(());
                }
                if line.starts_with("LOOP") {
                    // "Rebind the session." With one socket and no session
                    // resumption to preserve, reconnecting from scratch is
                    // both simpler and indistinguishable from the outside.
                    return Ok(());
                }
                if line.starts_with("SUBOK") || line.starts_with("SUBCMD") {
                    continue;
                }

                if let Some(rest) = line.strip_prefix("U,") {
                    Self::apply_update(rest, tx);
                    continue;
                }
            }
        }
    }

    fn subscribe<S>(sock: &mut tungstenite::WebSocket<S>) -> Result<()>
    where
        S: std::io::Read + std::io::Write,
    {
        // LS_group is a space-separated item list; LS_schema likewise. Both
        // get percent-encoded, which for these ids means the spaces become
        // %20 and nothing else changes.
        let group: Vec<&str> = ITEMS.iter().map(|(id, _)| *id).collect();
        let group = group.join("%20");

        sock.send(Message::Text(
            format!(
                "control\r\nLS_reqId=1&LS_op=add&LS_subId={SUB_MAIN}\
                 &LS_mode=MERGE&LS_group={group}&LS_schema=TimeStamp%20Value&LS_snapshot=true"
            )
            .into(),
        ))
        .map_err(|e| err(format!("subscribe main: {e}")))?;

        sock.send(Message::Text(
            format!(
                "control\r\nLS_reqId=2&LS_op=add&LS_subId={SUB_TIME}\
                 &LS_mode=MERGE&LS_group={TIME_ITEM}\
                 &LS_schema=TimeStamp%20Value%20Status.Class%20Status.Indicator&LS_snapshot=true"
            )
            .into(),
        ))
        .map_err(|e| err(format!("subscribe time: {e}")))?;

        Ok(())
    }

    /// `U,<sub>,<item>,<fields>` -- everything after the third comma is the
    /// pipe-separated field list, and it may itself contain commas, so the
    /// split is bounded at 3.
    fn apply_update(rest: &str, tx: &Sender<Event>) {
        let mut parts = rest.splitn(3, ',');
        let sub: u32 = match parts.next().and_then(|s| s.parse().ok()) {
            Some(v) => v,
            None => return,
        };
        let item: usize = match parts.next().and_then(|s| s.parse().ok()) {
            Some(v) => v,
            None => return,
        };
        let body = parts.next().unwrap_or_default();

        walk_fields(body, |idx, raw| {
            let text = percent_decode(raw);
            let parsed = text.trim().parse::<f64>();

            if sub == SUB_MAIN {
                // schema is `TimeStamp Value`, so field 1 is the value.
                if idx != 1 {
                    return;
                }
                // Items are 1-based on the wire.
                if let Some((_, field)) = ITEMS.get(item.wrapping_sub(1)) {
                    if let Ok(v) = parsed {
                        let _ = tx.send(Event::Value(*field, v));
                    }
                }
            } else if sub == SUB_TIME {
                // schema is `TimeStamp Value Status.Class Status.Indicator`
                match idx {
                    1 => {
                        if let Ok(v) = parsed {
                            let _ = tx.send(Event::Value(Field::Gmt, v));
                        }
                    }
                    2 => {
                        // Status.Class is a short code, not a number. Map it
                        // to the 0..3 the strip carries: 24 is the feed's
                        // "signal good" class; anything else is a loss.
                        let v = match text.trim() {
                            "24" => 3.0,
                            "" => 0.0,
                            _ => 1.0,
                        };
                        let _ = tx.send(Event::Value(Field::Signal, v));
                    }
                    _ => {}
                }
            }
        });
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    fn collect(body: &str) -> Vec<(usize, String)> {
        let mut out = Vec::new();
        walk_fields(body, |i, s| out.push((i, s.to_string())));
        out
    }

    #[test]
    fn plain_fields_are_indexed_in_order() {
        assert_eq!(
            collect("20:00:33|3.04|0.0"),
            vec![(0, "20:00:33".into()), (1, "3.04".into()), (2, "0.0".into())]
        );
    }

    #[test]
    fn empty_null_and_dollar_are_skipped_but_still_advance() {
        // From the spec's own worked example.
        assert_eq!(
            collect("20:04:16|3.02|-0.65|||3.01|3.02|||$"),
            vec![
                (0, "20:04:16".into()),
                (1, "3.02".into()),
                (2, "-0.65".into()),
                (5, "3.01".into()),
                (6, "3.02".into()),
            ]
        );
    }

    #[test]
    fn caret_run_advances_by_its_count() {
        // `^4` covers the pointed field and the three after it, so the next
        // real value lands at index 4. Getting this wrong shifts every later
        // field and the panel reads the wrong instruments.
        assert_eq!(
            collect("^4|3.02|3.03|||"),
            vec![(4, "3.02".into()), (5, "3.03".into())]
        );
    }

    #[test]
    fn caret_run_at_the_end_consumes_the_rest() {
        assert_eq!(
            collect("3.05|0.32|^7"),
            vec![(0, "3.05".into()), (1, "0.32".into())]
        );
    }

    #[test]
    fn percent_decoding_handles_the_escaped_meta_characters() {
        assert_eq!(percent_decode("a%7Cb"), "a|b");
        assert_eq!(percent_decode("%23not-null"), "#not-null");
        assert_eq!(percent_decode("plain"), "plain");
        assert_eq!(percent_decode("100%"), "100%");
    }
}
