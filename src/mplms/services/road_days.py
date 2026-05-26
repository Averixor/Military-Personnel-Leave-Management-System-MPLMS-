class RoadDayPolicyError(ValueError):
    pass


def allowed_road_days(distance_km: int) -> int:
    if distance_km < 0:
        raise RoadDayPolicyError("Distance cannot be negative")
    if distance_km < 200:
        return 0
    if distance_km <= 800:
        return 2
    return 4


def validate_requested_road_days(distance_km: int, requested_days: int) -> None:
    allowed = allowed_road_days(distance_km)
    if requested_days < 0:
        raise RoadDayPolicyError("Requested road days cannot be negative")
    if requested_days > allowed:
        raise RoadDayPolicyError(f"Requested {requested_days} road days, allowed maximum is {allowed}")

