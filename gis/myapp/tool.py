import requests
import polyline
import math


def haversine_km(lat1, lng1, lat2, lng2):
    """
    Tính khoảng cách đường chim bay (km) theo công thức Haversine.
    """
    R = 6371.0
    lat1 = float(lat1)
    lng1 = float(lng1)
    lat2 = float(lat2)
    lng2 = float(lng2)

    dlat = math.radians(lat2 - lat1)
    dlng = math.radians(lng2 - lng1)

    a = math.sin(dlat / 2) ** 2 + math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) * math.sin(dlng / 2) ** 2
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
    return R * c


def calc_shipping_fee(distance_km):
    """
    Tính phí ship theo quy tắc hiện tại của nhóm:
    fee = max(15000, distance_km * 5000)
    Trả về: (fee_value_int, fee_text)
    """
    try:
        dist = float(distance_km or 0)
    except Exception:
        dist = 0.0

    fee = max(15000, dist * 5000)
    fee_value = int(round(fee, -3))
    fee_text = f"{fee_value:,} đ".replace(',', '.')
    return fee_value, fee_text


def filter_pharmacies_in_radius(pharmacies, user_lat, user_lng, radius_km):
    """
    Lọc danh sách nhà thuốc trong bán kính (km) dựa trên Haversine.
    pharmacies: iterable các object có lat/lng/id
    Trả về list dict: {id, distance_km}
    """
    try:
        r = float(radius_km or 0)
    except Exception:
        r = 0.0

    results = []
    for p in pharmacies:
        if p.lat is None or p.lng is None:
            continue
        dist = haversine_km(user_lat, user_lng, p.lat, p.lng)
        if r <= 0 or dist <= r:
            results.append({
                "id": p.id,
                "distance_km": round(dist, 2),
            })

    results.sort(key=lambda x: x["distance_km"])
    return results


class RoutingTool:
    OSRM_URL = "http://router.project-osrm.org/route/v1"

    def __init__(self):
        pass

    def get_route(self, start_lat, start_lng, end_lat, end_lng, mode='driving'):
        """
        Tính toán lộ trình (Hỗ trợ nhiều tuyến đường - Alternatives)
        """
        try:
            s_lat, s_lng = float(start_lat), float(start_lng)
            e_lat, e_lng = float(end_lat), float(end_lng)
        except ValueError:
            return {'error': 'Tọa độ lỗi.'}

        osrm_mode_map = {
            'driving': 'driving',
            'cycling': 'bike',
            'walking': 'foot'
        }
        osrm_profile = osrm_mode_map.get(mode, 'driving')

        coords = f"{s_lng},{s_lat};{e_lng},{e_lat}"
        url = f"{self.OSRM_URL}/{osrm_profile}/{coords}"

        params = {
            'overview': 'full',
            'geometries': 'polyline',
            'steps': 'true',
            'alternatives': 'true'
        }

        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        }

        try:
            response = requests.get(url, params=params, headers=headers, timeout=10)
            data = response.json()

            if response.status_code == 200 and data.get('code') == 'Ok':
                routes_result = []

                speeds = {
                    'driving': 35
                }
                speed_kmh = speeds.get(mode, 35)

                for index, route in enumerate(data['routes']):
                    distance_km = route['distance'] / 1000

                    duration_min = round((distance_km / speed_kmh) * 60)
                    if duration_min < 1:
                        duration_min = 1

                    summary_name = ""
                    if route.get('legs') and len(route['legs']) > 0:
                        summary_name = route['legs'][0].get('summary', '')

                    if not summary_name:
                        summary_name = f"Tuyến đường {index + 1}"

                    routes_result.append({
                        'id': index,
                        'summary': summary_name,
                        'distance_km': round(distance_km, 2),
                        'duration_min': duration_min,
                        'route_points': polyline.decode(route['geometry'])
                    })

                return {
                    'routes': routes_result,
                    'mode': mode
                }
            else:
                return {'error': 'Không tìm thấy đường đi nào.'}

        except Exception as e:
            return {'error': f'Lỗi hệ thống: {str(e)}'}
