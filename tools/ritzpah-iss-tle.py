#!/usr/bin/env python3
"""Refresh the ISS orbital elements baked into the ISS Cockpit theme.

THIS IS THE ONE THING IN THIS REPO THAT REACHES THE NETWORK ON PURPOSE, and it
only does so when a human types `ritzpah iss-tle`. Nothing calls it on a timer,
nothing calls it at install, and no theme calls it at all.

Why it exists: `themes/iss-cockpit/hyprland.lua` carries a two-line element set
for ISS (ZARYA), NORAD 25544, as the committed fallback the cockpit flies on
when the `ritzpahd` daemon is not running. A TLE is a snapshot -- drag lowers
the station and the crew reboosts it -- so it drifts by roughly a kilometre of
along-track error per day. That is invisible on a ground-track dot and would
matter enormously if you were pointing an antenna. You are not.

Run this when the fallback has gone stale enough to bother you, look at the
diff, and commit it like any other change.
"""

import datetime
import math
import re
import sys
import urllib.request

# Celestrak publishes the public element sets. No account, no key, no terms
# that require attribution in a config file.
SOURCE = "https://celestrak.org/NORAD/elements/gp.php?CATNR=25544&FORMAT=TLE"

MU = 398600.4418   # km^3/s^2, Earth gravitational parameter
RE = 6378.137      # km, equatorial radius
J2 = 1.08263e-3


def fetch(url):
    request = urllib.request.Request(url, headers={"User-Agent": "ritzpah/iss-tle"})
    with urllib.request.urlopen(request, timeout=30) as response:
        return response.read().decode("utf-8", "replace")


def parse(text):
    lines = [line.rstrip() for line in text.splitlines() if line.strip()]
    one = next((l for l in lines if l.startswith("1 25544")), None)
    two = next((l for l in lines if l.startswith("2 25544")), None)
    if not one or not two:
        raise SystemExit("ritzpah: that did not look like an ISS TLE:\n" + text[:400])

    epoch_field = one[18:32]
    year = 2000 + int(epoch_field[:2])
    doy = float(epoch_field[2:])

    inc = float(two[8:16])
    raan = float(two[17:25])
    ecc = float("0." + two[26:33].strip())
    argp = float(two[34:42])
    ma = float(two[43:51])
    n_rev = float(two[52:63])
    return year, doy, inc, raan, ecc, argp, ma, n_rev


def derive(year, doy, inc, raan, ecc, argp, ma, n_rev):
    n_rad = n_rev * 2.0 * math.pi / 86400.0
    a = (MU / n_rad ** 2) ** (1.0 / 3.0)
    n_deg = n_rev * 360.0
    i = math.radians(inc)
    p = a * (1.0 - ecc ** 2)

    # Secular J2 rates. The nodal regression is the one that matters over days:
    # about -5 deg/day for this orbit, which is why the ground track walks west.
    raan_rate = -1.5 * n_deg * J2 * (RE / p) ** 2 * math.cos(i)
    argp_rate = 0.75 * n_deg * J2 * (RE / p) ** 2 * (5.0 * math.cos(i) ** 2 - 1.0)

    # Near-circular, so argument of latitude is what the shader wants, not a
    # separate perigee and anomaly.
    u0 = (argp + ma) % 360.0
    u_rate = n_deg + argp_rate

    epoch = (datetime.datetime(year, 1, 1, tzinfo=datetime.timezone.utc)
             + datetime.timedelta(days=doy - 1.0))
    epoch_jd = epoch.timestamp() / 86400.0 + 2440587.5

    return {
        "EPOCH_JD": epoch_jd, "ISS_A": a, "ISS_INC": inc,
        "ISS_RAAN0": raan, "ISS_RAAN_R": raan_rate,
        "ISS_U0": u0, "ISS_U_R": u_rate,
        "epoch_iso": epoch.strftime("%Y-%m-%dT%H:%M:%SZ"),
        "period_min": 1440.0 / n_rev,
        "alt_km": a - 6371.0,
    }


FORMATS = {
    "EPOCH_JD": "%.9f", "ISS_A": "%.4f", "ISS_INC": "%.4f",
    "ISS_RAAN0": "%.4f", "ISS_RAAN_R": "%.9f",
    "ISS_U0": "%.6f", "ISS_U_R": "%.9f",
}


def main():
    repo = sys.argv[1] if len(sys.argv) > 1 else "."
    lua = f"{repo}/themes/iss-cockpit/hyprland.lua"

    print(f"fetching {SOURCE}")
    values = derive(*parse(fetch(SOURCE)))

    print(f"  epoch     {values['epoch_iso']}")
    print(f"  altitude  {values['alt_km']:.1f} km")
    print(f"  period    {values['period_min']:.3f} min")
    print(f"  node rate {values['ISS_RAAN_R']:.4f} deg/day")

    # Sanity floor. A garbled fetch that parses into nonsense would otherwise be
    # written straight into the theme and the cockpit would fly a fictional
    # orbit with total confidence.
    if not (300.0 < values["alt_km"] < 600.0 and 88.0 < values["period_min"] < 96.0):
        raise SystemExit("ritzpah: those elements are not a low Earth orbit; refusing to write")

    with open(lua, "r", encoding="utf-8") as handle:
        text = handle.read()

    original = text
    for key, fmt in FORMATS.items():
        literal = fmt % values[key]
        text, count = re.subn(
            rf"^(local {key}\s*=\s*)(-?[\d.]+)",
            lambda m, v=literal: m.group(1) + v,
            text, count=1, flags=re.M)
        if count != 1:
            raise SystemExit(f"ritzpah: could not find `local {key}` in {lua}")

    text = re.sub(r"(set at epoch )[0-9TZ:-]+", rf"\g<1>{values['epoch_iso']}", text, count=1)

    if text == original:
        print("already current; nothing changed")
        return

    with open(lua, "w", encoding="utf-8") as handle:
        handle.write(text)
    print(f"updated {lua}")
    print("look at the diff, then commit it.")


if __name__ == "__main__":
    main()
