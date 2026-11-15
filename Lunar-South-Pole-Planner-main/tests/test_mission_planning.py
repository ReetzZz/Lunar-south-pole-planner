# Last updated: 2026-11-14
import pytest

from src.mission_planning import OperationalWindow, find_operational_windows


def test_single_operational_window():
    result = find_operational_windows(
        [-2, 6, 10, 3],
        [8, 7, 9, 10],
    )
    assert result == [OperationalWindow(1, 2, 2)]


def test_multiple_operational_windows():
    result = find_operational_windows(
        [6, 8, 1, 7, 9, 2],
        [7, 9, 8, 6, 10, 10],
    )
    assert result == [
        OperationalWindow(0, 1, 2),
        OperationalWindow(3, 4, 2),
    ]


def test_both_thresholds_must_be_met():
    result = find_operational_windows(
        [5, 10, 10],
        [5, 4.9, 10],
    )
    assert result == [
        OperationalWindow(0, 0, 1),
        OperationalWindow(2, 2, 1),
    ]


def test_thresholds_are_inclusive():
    result = find_operational_windows(
        [5, 4.99],
        [5, 10],
        min_sun_elevation_deg=5,
        min_earth_elevation_deg=5,
    )
    assert result == [OperationalWindow(0, 0, 1)]


def test_missing_and_non_finite_samples_break_windows():
    result = find_operational_windows(
        [8, None, 9, float("nan"), 10, 11],
        [8, 9, 9, 9, float("inf"), 11],
    )
    assert result == [OperationalWindow(0, 0, 1), OperationalWindow(2, 2, 1), OperationalWindow(5, 5, 1)]


def test_empty_series_returns_no_windows():
    assert find_operational_windows([], []) == []


def test_different_series_lengths_raise_value_error():
    with pytest.raises(ValueError, match="stessa lunghezza"):
        find_operational_windows([1, 2], [1])


def test_custom_thresholds():
    result = find_operational_windows(
        [9, 11, 12],
        [15, 16, 17],
        min_sun_elevation_deg=10,
        min_earth_elevation_deg=15,
    )
    assert result == [OperationalWindow(1, 2, 2)]
