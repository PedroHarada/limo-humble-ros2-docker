"""Interpolação de waypoints para os obstáculos móveis."""

import math


def _lerp_angle(a, b, f):
    delta = math.atan2(math.sin(b - a), math.cos(b - a))
    return a + delta * f


def pose_at(waypoints, t, loop=True):
    """Pose (x, y, yaw) do obstáculo no instante t.

    Waypoints são dicts com time/x/y/yaw, em ordem crescente de time. Antes do
    primeiro e depois do último (sem loop), a pose fica congelada no waypoint
    da ponta.
    """
    if not waypoints:
        raise ValueError('a trajetória precisa de pelo menos um waypoint')

    def pose(w):
        return (w['x'], w['y'], w['yaw'])

    if len(waypoints) == 1:
        return pose(waypoints[0])

    start, end = waypoints[0]['time'], waypoints[-1]['time']
    duration = end - start
    if loop and duration > 0:
        t = start + (t - start) % duration

    if t <= start:
        return pose(waypoints[0])
    if t >= end:
        return pose(waypoints[-1])

    for a, b in zip(waypoints, waypoints[1:]):
        if a['time'] <= t <= b['time']:
            span = b['time'] - a['time']
            f = 0.0 if span == 0 else (t - a['time']) / span
            return (
                a['x'] + (b['x'] - a['x']) * f,
                a['y'] + (b['y'] - a['y']) * f,
                _lerp_angle(a['yaw'], b['yaw'], f),
            )

    return pose(waypoints[-1])
