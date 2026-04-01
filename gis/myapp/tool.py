import math

try:
    import requests
except ImportError:
    requests = None


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

NOMINATIM_SEARCH_URL = "https://nominatim.openstreetmap.org/search"
NOMINATIM_REVERSE_URL = "https://nominatim.openstreetmap.org/reverse"


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
    Giữ cùng một quãng đường cơ sở cho mọi phương tiện; chỉ khác thời gian di chuyển.
    """
    road_factor = TRAFFIC_CONFIG['road_distance_factor'].get('motorbike', 1.2)
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


def search_address_candidates(query, limit=5, country_codes='vn'):
    """
    Tim cac dia diem gan dung theo tu khoa dia chi.
    """
    query_text = (query or '').strip()
    if not query_text:
        return []
    if requests is None:
        return []

    try:
        limit_value = int(limit)
    except (TypeError, ValueError):
        limit_value = 5

    limit_value = max(1, min(limit_value, 8))

    response = requests.get(
        NOMINATIM_SEARCH_URL,
        params={
            'q': query_text,
            'format': 'json',
            'limit': limit_value,
            'countrycodes': country_codes,
            'addressdetails': 1,
        },
        headers={
            'User-Agent': 'GIS-Pharma/1.0 (Django address search)',
            'Accept-Language': 'vi,en',
        },
        timeout=10,
    )
    response.raise_for_status()

    search_results = []

    for item in response.json():
        lat = item.get('lat')
        lng = item.get('lon')
        if lat is None or lng is None:
            continue

        try:
            lat_value = float(lat)
            lng_value = float(lng)
        except (TypeError, ValueError):
            continue

        search_results.append(
            {
                'display_name': item.get('display_name', query_text),
                'lat': lat_value,
                'lng': lng_value,
                'type_label': item.get('type') or item.get('class') or 'location',
            }
        )

    return search_results


def reverse_geocode_coordinates(lat, lng):
    """
    Tra ve dia chi gan nhat tu cap toa do.
    """
    if requests is None:
        return {
            'display_name': '',
            'lat': float(lat),
            'lng': float(lng),
        }

    response = requests.get(
        NOMINATIM_REVERSE_URL,
        params={
            'lat': lat,
            'lon': lng,
            'format': 'jsonv2',
            'zoom': 18,
            'addressdetails': 1,
        },
        headers={
            'User-Agent': 'GIS-Pharma/1.0 (Django reverse geocode)',
            'Accept-Language': 'vi',
        },
        timeout=10,
    )
    response.raise_for_status()

    data = response.json()
    return {
        'display_name': data.get('display_name', ''),
        'lat': float(data.get('lat', lat)),
        'lng': float(data.get('lon', lng)),
    }


class DeliveryRoutingService:
    """
    Service trung tâm xử lý định tuyến giao hàng.
    """

    OSRM_BASE_URL = "http://router.project-osrm.org/route/v1"

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
        request_url = f"{self.OSRM_BASE_URL}/driving/{route_coordinates}"
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

        estimated_duration_min = self.estimate_travel_time_minutes(shared_distance_km, delivery_mode)
        shipping_fee_value, shipping_fee_text = calculate_shipping_fee(shared_distance_km)

        route_result = {
            'id': 0,
            'distance_km': round(shared_distance_km, 2),
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


def choose_best_pharmacy_fast(service, pharmacies, delivery_lat, delivery_lng, delivery_mode='motorbike'):
    if not pharmacies:
        return {'error': 'Khong co nha thuoc kha dung.'}

    best_pharmacy = None
    shortest_distance_km = None

    for pharmacy in pharmacies:
        if pharmacy.lat is None or pharmacy.lng is None:
            continue

        air_distance_km = calculate_air_distance_km(
            pharmacy.lat,
            pharmacy.lng,
            delivery_lat,
            delivery_lng,
        )
        current_distance_km = estimate_road_distance_km(air_distance_km, delivery_mode)

        if shortest_distance_km is None or current_distance_km < shortest_distance_km:
            shortest_distance_km = current_distance_km
            best_pharmacy = pharmacy

    if best_pharmacy is None:
        return {'error': 'Khong tim duoc chi nhanh phu hop.'}

    route_result = service.estimate_route(
        start_lat=best_pharmacy.lat,
        start_lng=best_pharmacy.lng,
        end_lat=delivery_lat,
        end_lng=delivery_lng,
        delivery_mode=delivery_mode,
    )
    if 'routes' not in route_result or not route_result['routes']:
        return {'error': 'Khong the tinh duoc chi nhanh giao hang phu hop.'}

    return {
        'pharmacy': best_pharmacy,
        'route': route_result['routes'][0],
        'mode': route_result.get('mode', delivery_mode),
    }
