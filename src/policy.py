from .time_utils import parse_time


def authorized(request, proposed):
    if parse_time(proposed) == parse_time(request['requested_time']):
        return True
    confirmed = request['confirmed_alternative_time']
    return (confirmed is not None and parse_time(proposed) == parse_time(confirmed)) or (request['time_requirement'] == 'soft' and request['allow_alternative_suggestion'])
