import pytest

from mplms.services.road_days import RoadDayPolicyError
from mplms.services.road_days import allowed_road_days
from mplms.services.road_days import validate_requested_road_days


@pytest.mark.parametrize(
    ("distance_km", "expected"),
    [
        (0, 0),
        (199, 0),
        (200, 2),
        (800, 2),
        (801, 4),
    ],
)
def test_allowed_road_days(distance_km: int, expected: int) -> None:
    assert allowed_road_days(distance_km) == expected


def test_rejects_excessive_requested_road_days() -> None:
    with pytest.raises(RoadDayPolicyError):
        validate_requested_road_days(distance_km=150, requested_days=2)

