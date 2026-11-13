import sys
import csv
import math

EARTH_RADIUS_M = 6371000.0      # average radius of the Earth in metres
ARRIVAL_RADIUS_M = 3.0          # "close enough" distance to a target
STOPPED_SPEED_MS = 0.5          # slower than this counts as stopped
GREEN_SECONDS = 5               # how long green stays on


def haversine_m(lat1, lon1, lat2, lon2):
    """Straight-line distance over the Earth's surface, in metres."""
    p1 = math.radians(lat1)
    p2 = math.radians(lat2)
    dphi = p2 - p1
    dlmb = math.radians(lon2 - lon1)
    a = math.sin(dphi / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dlmb / 2) ** 2
    a = min(1.0, max(0.0, a))   # protects asin/sqrt from tiny rounding errors
    return 2 * EARTH_RADIUS_M * math.asin(math.sqrt(a))


def to_float(text):
    """Turn text into a usable number, or None if it is junk (blank, 'nan', 'abc')."""
    try:
        value = float(str(text).strip())
    except (ValueError, TypeError):
        return None
    if not math.isfinite(value):          # rejects nan and inf
        return None
    return value


def valid_position(lat, lon):
    """A GPS point must exist and be a real place on Earth."""
    return (lat is not None and lon is not None
            and -90.0 <= lat <= 90.0 and -180.0 <= lon <= 180.0)


def read_targets(path):
    targets = []
    with open(path, newline="", encoding="utf-8-sig") as f:
        for row in csv.reader(f):
            numbers = [to_float(cell) for cell in row]
            numbers = [n for n in numbers if n is not None]
            if len(numbers) < 2:
                continue                      # header, blank line, broken line
            lat, lon = numbers[-2], numbers[-1]   # last two numbers = lat, lon
            if valid_position(lat, lon):
                targets.append((lat, lon))
    return targets


def read_log(path):
    """Returns a list of (time_value, time_text, mode, lat, lon), one per second."""
    rows = []
    seen_times = set()
    with open(path, newline="", encoding="utf-8-sig") as f:
        for row in csv.reader(f):
            if not row:
                continue
            row = [c.strip() for c in row] + [""] * 4     # pad short rows
            t = to_float(row[0])
            if t is None:
                continue                      # header or garbage time
            if t in seen_times:
                continue                      # duplicate second: keep the first
            seen_times.add(t)
            mode = row[1].upper()
            lat = to_float(row[2])
            lon = to_float(row[3])
            if not valid_position(lat, lon):
                lat, lon = None, None
            rows.append((t, row[0], mode, lat, lon))
    rows.sort(key=lambda r: r[0])             # make sure time goes forward
    return rows


def main():
    if len(sys.argv) < 3:
        print("usage: python light.py <mission_log.csv> <targets.csv>", file=sys.stderr)
        return 1
    try:
        targets = read_targets(sys.argv[2])
        rows = read_log(sys.argv[1])
    except OSError as err:
        print("cannot read file: " + str(err), file=sys.stderr)
        return 1

    target_index = 0          # which target we are heading to now
    green_until = None        # green is on while time < green_until
    last_mode = "MANUAL"      # remembered mode, used if a row has a bad mode
    prev_time = None          # last row that had good GPS
    prev_lat = None
    prev_lon = None

    for t, t_text, mode, lat, lon in rows:
        if mode in ("AUTO", "MANUAL"):
            last_mode = mode
        else:
            mode = last_mode

        # speed in m/s from the last good GPS point
        speed = None
        if lat is not None and prev_time is not None and t > prev_time:
            speed = haversine_m(prev_lat, prev_lon, lat, lon) / (t - prev_time)

        green_is_on = green_until is not None and t < green_until

        # arrival check (only while a target is left and green is not already on)
        if (not green_is_on and target_index < len(targets)
                and mode == "AUTO" and lat is not None and speed is not None):
            tlat, tlon = targets[target_index]
            near = haversine_m(lat, lon, tlat, tlon) <= ARRIVAL_RADIUS_M
            stopped = speed < STOPPED_SPEED_MS
            if near and stopped:
                green_until = t + GREEN_SECONDS
                green_is_on = True
                target_index += 1             # next target from now on

        if green_is_on:
            light = "green"
        elif mode == "AUTO":
            light = "red"
        else:
            light = "blue"
        print(t_text + "," + light)

        if lat is not None:
            prev_time, prev_lat, prev_lon = t, lat, lon
    return 0


if __name__ == "__main__":
    sys.exit(main())