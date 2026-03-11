import math
import polyline
import requests


TRAFFIC_CONFIG = {
    'average_speed': {
        'motorbike': 35,
        'car': 30,
        'walking': 4.5,
    },
    'road_distance_factor': {
        'motorbike': 1.2,
        'car': 1.3,
        'walking': 1.05,
    },
}


def calculate_air_distance_km(start_lat, start_lng, end_lat, end_lng):
    """
    Tính khoảng cách đường chim bay giữa 2 tọa độ bằng công thức Haversine.
    """
    earth_radius_km = 6371.0

    start_lat = float(start_lat)
    start_lng = float(start_lng)
    end_lat = float(end_lat)
    end_lng = float(end_lng)

    delta_lat = math.radians(end_lat - start_lat)
    delta_lng = math.radians(end_lng - start_lng)

    a = (
        math.sin(delta_lat / 2) ** 2
        + math.cos(math.radians(start_lat))
        * math.cos(math.radians(end_lat))
        * math.sin(delta_lng / 2) ** 2
    )
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
    return earth_radius_km * c


def estimate_road_distance_km(air_distance_km, delivery_mode='motorbike'):
    """
    Ước lượng quãng đường di chuyển thực tế từ khoảng cách đường chim bay.
    """
    road_factor = TRAFFIC_CONFIG['road_distance_factor'].get(delivery_mode, 1.2)
    return air_distance_km * road_factor


def calculate_shipping_fee(estimated_distance_km):
    """
    Tính phí giao hàng dựa trên quãng đường ước lượng.
    """
    try:
        distance_value = float(estimated_distance_km)
    except (TypeError, ValueError):
        distance_value = 0.0

    if distance_value <= 3:
        shipping_fee_value = 15000
    else:
        shipping_fee_value = 15000 + int((distance_value - 3) * 5000)

    shipping_fee_value = int(round(shipping_fee_value, -3))
    shipping_fee_text = f"{shipping_fee_value:,} đ".replace(",", ".")
    return shipping_fee_value, shipping_fee_text


class DeliveryRoutingService:
    """
    Service trung tâm xử lý định tuyến giao hàng.
    """

    OSRM_BASE_URL = "http://router.project-osrm.org/route/v1"

    def get_osrm_route_points(self, start_lat, start_lng, end_lat, end_lng, delivery_mode='motorbike'):
        """
        Gọi OSRM để lấy tuyến đường đẹp hiển thị trên bản đồ.
        """
        osrm_profile = 'foot' if delivery_mode == 'walking' else 'driving'
        route_coordinates = f"{start_lng},{start_lat};{end_lng},{end_lat}"
        request_url = f"{self.OSRM_BASE_URL}/{osrm_profile}/{route_coordinates}"

        query_params = {
            'overview': 'full',
            'geometries': 'polyline',
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
                encoded_geometry = route_list[0].get('geometry')
                if encoded_geometry:
                    return polyline.decode(encoded_geometry)

        return [
            [float(start_lat), float(start_lng)],
            [float(end_lat), float(end_lng)],
        ]

    def estimate_travel_time_minutes(self, estimated_distance_km, delivery_mode):
        """
        Tính thời gian di chuyển dự kiến theo quãng đường và vận tốc trung bình.
        """
        average_speed = TRAFFIC_CONFIG['average_speed'].get(delivery_mode, 30)

        if average_speed <= 0:
            return 1

        estimated_minutes = int(round((estimated_distance_km / average_speed) * 60))
        return max(estimated_minutes, 1)

    def estimate_route(self, start_lat, start_lng, end_lat, end_lng, delivery_mode='motorbike'):
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

        if delivery_mode not in TRAFFIC_CONFIG['average_speed']:
            delivery_mode = 'motorbike'

        air_distance_km = calculate_air_distance_km(start_lat, start_lng, end_lat, end_lng)
        estimated_distance_km = estimate_road_distance_km(air_distance_km, delivery_mode)
        estimated_duration_min = self.estimate_travel_time_minutes(estimated_distance_km, delivery_mode)
        shipping_fee_value, shipping_fee_text = calculate_shipping_fee(estimated_distance_km)

        try:
            route_points = self.get_osrm_route_points(
                start_lat,
                start_lng,
                end_lat,
                end_lng,
                delivery_mode,
            )
        except Exception:
            route_points = [
                [start_lat, start_lng],
                [end_lat, end_lng],
            ]

        route_result = {
            'id': 0,
            'distance_km': round(estimated_distance_km, 2),
            'duration_min': estimated_duration_min,
            'route_points': route_points,
            'shipping_fee': shipping_fee_text,
            'shipping_fee_value': shipping_fee_value,
        }

        return {
            'routes': [route_result],
            'mode': delivery_mode,
        }

    def choose_best_pharmacy(self, pharmacies, delivery_lat, delivery_lng, delivery_mode='motorbike'):
        """
        Chọn chi nhánh phù hợp nhất cho vị trí giao hàng.
        """
        if not pharmacies:
            return {'error': 'Không có nhà thuốc khả dụng.'}

        best_result = None
        shortest_distance_km = None

        for pharmacy in pharmacies:
            if pharmacy.lat is None or pharmacy.lng is None:
                continue

            route_result = self.estimate_route(
                start_lat=pharmacy.lat,
                start_lng=pharmacy.lng,
                end_lat=delivery_lat,
                end_lng=delivery_lng,
                delivery_mode=delivery_mode,
            )

            if 'routes' not in route_result or not route_result['routes']:
                continue

            selected_route = route_result['routes'][0]
            current_distance_km = selected_route['distance_km']

            if shortest_distance_km is None or current_distance_km < shortest_distance_km:
                shortest_distance_km = current_distance_km
                best_result = {
                    'pharmacy': pharmacy,
                    'route': selected_route,
                    'mode': route_result.get('mode', delivery_mode),
                }

        if best_result is None:
            return {'error': 'Không tìm được chi nhánh phù hợp.'}

        return best_result