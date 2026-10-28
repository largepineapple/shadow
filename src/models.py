from zoneinfo import ZoneInfo
from datetime import datetime
from .time_utils import parse_time


def validate_request(r):
    if not isinstance(r, dict):
        raise ValueError('Request must be an object')
    required = {'request_id', 'material_ids', 'platform', 'requested_time', 'time_requirement', 'timezone', 'allow_alternative_suggestion', 'confirmed_alternative_time'}
    if set(r) != required:
        raise ValueError('Unexpected or missing request fields')
    for key in ('request_id', 'platform', 'timezone'):
        if not isinstance(r[key], str) or not r[key].strip():
            raise ValueError('Invalid ' + key)
    ids = r['material_ids']
    if not isinstance(ids, list) or not ids or any(not isinstance(x, str) or not x for x in ids) or len(set(ids)) != len(ids):
        raise ValueError('material_ids must be distinct nonempty strings')
    if r['time_requirement'] not in ('hard', 'soft') or type(r['allow_alternative_suggestion']) is not bool:
        raise ValueError('Invalid scheduling policy')
    zone = ZoneInfo(r['timezone'])
    for key in ('requested_time', 'confirmed_alternative_time'):
        if r[key] is not None:
            dt = parse_time(r[key])
            if dt.astimezone(zone).utcoffset() != datetime.fromisoformat(r[key]).utcoffset():
                raise ValueError('Timestamp offset does not match timezone')
    parse_time(r['requested_time'])
    return r
