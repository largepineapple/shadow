from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo


def parse_time(value):
    dt = datetime.fromisoformat(value)
    if dt.tzinfo is None or dt.utcoffset() is None:
        raise ValueError('Timestamp must include UTC offset')
    return dt.astimezone(timezone.utc)


def display_time(value, zone):
    return parse_time(value).astimezone(ZoneInfo(zone)).isoformat()


def overlaps(a, b, c, d):
    return a < d and c < b
