import math

import pytest

from limo_worlds.trajectory import pose_at

SQUARE = [
    {'time': 0.0, 'x': 0.0, 'y': 0.0, 'yaw': 0.0},
    {'time': 10.0, 'x': 10.0, 'y': 0.0, 'yaw': 0.0},
    {'time': 20.0, 'x': 10.0, 'y': 4.0, 'yaw': 1.0},
]


def test_first_waypoint_at_start():
    assert pose_at(SQUARE, 0.0) == (0.0, 0.0, 0.0)


def test_interpolates_inside_a_segment():
    x, y, yaw = pose_at(SQUARE, 5.0)
    assert x == pytest.approx(5.0)
    assert y == pytest.approx(0.0)
    assert yaw == pytest.approx(0.0)


def test_interpolates_in_the_second_segment():
    x, y, yaw = pose_at(SQUARE, 15.0)
    assert x == pytest.approx(10.0)
    assert y == pytest.approx(2.0)
    assert yaw == pytest.approx(0.5)


def test_time_before_start_holds_first_waypoint():
    assert pose_at(SQUARE, -3.0, loop=False) == (0.0, 0.0, 0.0)


def test_time_before_start_wraps_when_looping():
    assert pose_at(SQUARE, -3.0, loop=True) == pytest.approx(pose_at(SQUARE, 17.0))


def test_without_loop_holds_last_waypoint():
    assert pose_at(SQUARE, 99.0, loop=False) == (10.0, 4.0, 1.0)


def test_with_loop_wraps_around():
    x, y, yaw = pose_at(SQUARE, 25.0, loop=True)
    assert (x, y, yaw) == pytest.approx(pose_at(SQUARE, 5.0, loop=True))


def test_yaw_takes_the_short_way_around_pi():
    waypoints = [
        {'time': 0.0, 'x': 0.0, 'y': 0.0, 'yaw': 3.0},
        {'time': 2.0, 'x': 0.0, 'y': 0.0, 'yaw': -3.0},
    ]
    _, _, yaw = pose_at(waypoints, 1.0)
    # 3.0 -> -3.0 são 0.283 rad pelo caminho curto, cruzando pi
    assert abs(math.atan2(math.sin(yaw - math.pi), math.cos(yaw - math.pi))) < 0.2


def test_single_waypoint_is_a_static_obstacle():
    waypoints = [{'time': 0.0, 'x': 1.0, 'y': 2.0, 'yaw': 0.5}]
    assert pose_at(waypoints, 42.0) == (1.0, 2.0, 0.5)


def test_empty_waypoints_is_an_error():
    with pytest.raises(ValueError):
        pose_at([], 0.0)
