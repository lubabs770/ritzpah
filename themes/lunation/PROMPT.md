# The prompt

2026-08-25, verbatim, typo and all:

> use ritzpah skill, this is my prompt "make a dynamic theme based off the
> posistion of the moon"

That is the whole brief. Everything else in this directory is an argument about
what "dynamic" and "position" were allowed to mean.

**Dynamic** could have been a timer -- a systemd unit that regenerates the
palette every hour. It is not, because this repo's own README hands you a
prompt for auditing it and a claim about what executes and when, and "a theme
that installs a scheduled job" is the kind of thing that claim exists to make
visible. So the dynamism had to come from somewhere that was already running:
Hyprland re-executes `hyprland.lua` on every config load, and a screen shader
is handed the wall clock sixty times a second. Both were already there. Neither
had to be scheduled.

**Position** could have been phase alone -- a waxing gibbous is what most
people mean by "where the Moon is". It is not, because the Moon has an actual
altitude and an actual azimuth over the actual machine, and once you are
computing the phase you are four lines from computing those too. So the theme
tracks both: the disc rises, crosses and sets across the desktop over the
night, and the phase follows the month.
