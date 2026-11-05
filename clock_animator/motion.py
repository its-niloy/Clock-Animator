"""Deterministic time and motion calculations, independent of Blender."""
from math import floor, isfinite


def clock_text(seconds):
    if not isfinite(seconds):
        return '--:--:--'
    value = floor(seconds) % 86400
    return f'{value // 3600:02d}:{value // 60 % 60:02d}:{value % 60:02d}'


def ramp_seconds(frame, start, end, first, last, fps, smooth=False):
    """Integral of a linear or smoothstep speed ramp, followed by terminal speed."""
    if end <= start or fps <= 0 or not all(isfinite(x) for x in (first, last, fps)):
        raise ValueError('Choose a positive frame range and finite speeds')
    u = min(1.0, max(0.0, (frame - start) / (end - start)))
    integral = u ** 3 - u ** 4 / 2 if smooth else u * u / 2
    return (end - start) / fps * (first * u + (last - first) * integral) + max(0, frame - end) * last / fps


def date_position(seconds, first=1, transition=0):
    if not 1 <= first <= 31 or not 0 <= transition <= 86400:
        raise ValueError('Date must be 1 to 31; transition must be 0 to 86400 seconds')
    days = floor(seconds / 86400)
    fraction = max(0, (seconds % 86400 - (86400 - transition)) / transition) if transition else 0
    return (first - 1 + days + fraction) % 31


def movement_expression(base, rate, second=False):
    q = '(t-tick*(t-floor(t*hz)/hz))'
    expression = f'({base:.15f})+({rate:.15f})*{q}'
    if second:
        expression += '+tick*amp*exp(-damp*(t*hz-floor(t*hz)))*sin(6.283185307179586*(t*hz-floor(t*hz)))'
    return expression
