from decimal import Decimal
from math import asin, cos, radians, sin, sqrt

EARTH_RADIUS_KM = 6371.0088


def haversine_distance_km(
    *,
    first_latitude: Decimal,
    first_longitude: Decimal,
    second_latitude: Decimal,
    second_longitude: Decimal,
) -> Decimal:
    first_lat = radians(float(first_latitude))
    second_lat = radians(float(second_latitude))
    lat_delta = radians(float(second_latitude - first_latitude))
    lon_delta = radians(float(second_longitude - first_longitude))

    haversine = (
        sin(lat_delta / 2) ** 2
        + cos(first_lat) * cos(second_lat) * sin(lon_delta / 2) ** 2
    )
    distance = 2 * EARTH_RADIUS_KM * asin(sqrt(haversine))
    return Decimal(str(round(distance, 3)))
