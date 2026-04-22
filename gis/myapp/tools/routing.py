try:
    import requests
except ImportError:
    requests = None

from .calculations import (
    AVERAGE_SPEED_KMH,
    calculate_air_distance_km,
    calculate_estimated_delivery_info,
    calculate_shipping_fee,
    calculate_travel_time_minutes,
    estimate_road_distance_km,
    get_departure_traffic_profile,
    normalize_departure_time_str,
)


OSRM_BASE_URL = "http://router.project-osrm.org/route/v1"


class DeliveryRoutingService:
    """
    Service trung tâm xử lý định tuyến giao hàng.
    """

    def get_osrm_route_data(self, start_lat, start_lng, end_lat, end_lng):
        """
        Gọi OSRM một lần để lấy hình học tuyến và quãng đường cơ sở dùng chung cho mọi phương tiện.
        """
        fallback_points = [
            [float(start_lat), float(start_lng)],
            [float(end_lat), float(end_lng)],
        ]

        if requests is None:
            return {
                'route_points': fallback_points,
                'distance_km': None,
            }

        route_coordinates = f"{start_lng},{start_lat};{end_lng},{end_lat}"
        request_url = f"{OSRM_BASE_URL}/driving/{route_coordinates}"
        query_params = {
            'overview': 'full',
            'geometries': 'geojson',
            'steps': 'true',
            'alternatives': 'false',
        }
        request_headers = {
            'User-Agent': 'Mozilla/5.0',
        }

        response = requests.get(
            request_url,
            params=query_params,
            headers=request_headers,
            timeout=10,
        )
        response_data = response.json()

        if response.status_code == 200 and response_data.get('code') == 'Ok':
            route_list = response_data.get('routes', [])
            if route_list:
                route_item = route_list[0]
                geometry = route_item.get('geometry') or {}
                route_coordinates = geometry.get('coordinates', [])
                route_points = [
                    [point[1], point[0]]
                    for point in route_coordinates
                    if len(point) >= 2
                ] or fallback_points
                distance_km = None
                try:
                    distance_km = round(float(route_item.get('distance', 0)) / 1000, 2)
                except (TypeError, ValueError):
                    distance_km = None
                return {
                    'route_points': route_points,
                    'distance_km': distance_km,
                }

        return {
            'route_points': fallback_points,
            'distance_km': None,
        }

    def estimate_route(self, start_lat, start_lng, end_lat, end_lng, delivery_mode='motorbike', departure_time_str=None):
        """
        Ước lượng tuyến giao hàng giữa 2 điểm.
        """
        try:
            start_lat = float(start_lat)
            start_lng = float(start_lng)
            end_lat = float(end_lat)
            end_lng = float(end_lng)
        except (TypeError, ValueError):
            return {'error': 'Tọa độ lỗi.'}

        if delivery_mode not in AVERAGE_SPEED_KMH:
            delivery_mode = 'motorbike'

        normalized_departure_time = normalize_departure_time_str(departure_time_str)
        air_distance_km = calculate_air_distance_km(start_lat, start_lng, end_lat, end_lng)
        estimated_distance_km = estimate_road_distance_km(air_distance_km, delivery_mode)

        try:
            route_data = self.get_osrm_route_data(
                start_lat,
                start_lng,
                end_lat,
                end_lng,
            )
        except Exception:
            route_data = {
                'route_points': [
                    [start_lat, start_lng],
                    [end_lat, end_lng],
                ],
                'distance_km': None,
            }

        route_points = route_data.get('route_points') or [
            [start_lat, start_lng],
            [end_lat, end_lng],
        ]
        shared_distance_km = route_data.get('distance_km')
        if shared_distance_km is None:
            shared_distance_km = round(estimated_distance_km, 2)

        traffic_profile = get_departure_traffic_profile(normalized_departure_time, delivery_mode)
        estimated_duration_min = calculate_travel_time_minutes(
            shared_distance_km,
            delivery_mode,
            normalized_departure_time,
        )
        shipping_fee_details = calculate_shipping_fee(
            shared_distance_km,
            delivery_mode=delivery_mode,
            departure_time_str=normalized_departure_time,
        )

        estimated_delivery_info = calculate_estimated_delivery_info(
            departure_time_str=normalized_departure_time,
            duration_minutes=estimated_duration_min,
        )

        route_result = {
            'id': 0,
            'distance_km': round(shared_distance_km, 2),
            'duration_min': estimated_duration_min,
            'route_points': route_points,
            'shipping_fee': shipping_fee_details['shipping_fee_text'],
            'shipping_fee_value': shipping_fee_details['shipping_fee_value'],
            'base_shipping_fee': shipping_fee_details['base_shipping_fee_text'],
            'base_shipping_fee_value': shipping_fee_details['base_shipping_fee_value'],
            'fee_increase_percent': shipping_fee_details['fee_increase_percent'],
            'fee_multiplier': shipping_fee_details['fee_multiplier'],
            'departure_time': normalized_departure_time,
            'estimated_delivery_time': estimated_delivery_info['arrival_time'],
            'estimated_delivery_day_offset': estimated_delivery_info['arrival_day_offset'],
            'estimated_delivery_label': estimated_delivery_info['arrival_display_text'],
            'is_peak_hour': traffic_profile['is_peak_hour'],
            'traffic_period_label': traffic_profile['period_label'],
            'traffic_notice': traffic_profile['notice'],
        }

        return {
            'routes': [route_result],
            'mode': delivery_mode,
            'departure_time': normalized_departure_time,
            'notice': traffic_profile['notice'],
        }
