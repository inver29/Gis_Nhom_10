import requests
import polyline
import math
from datetime import datetime

# --- CẤU HÌNH HỆ SỐ GIAO THÔNG ---
TRAFFIC_CONFIG = {
    'rush_hour': {
        'morning': (7, 9),   # 7h-9h
        'evening': (17, 19)  # 17h-19h
    },
    'penalty': {
        # (Hệ số nhân thời gian)
        'motorbike': 1.2,  # Xe máy tắc: chậm đi 20% (luồn lách được)
        'car': 2.5,        # Ô tô tắc: chậm đi 2.5 lần (đứng im)
        'walking': 1.0     # Đi bộ: không ảnh hưởng
    },
    'speed': {
        # Tốc độ trung bình (km/h) để fallback
        'motorbike': 35,
        'car': 30,         # Ô tô đi phố chậm hơn xe máy
        'walking': 4.5
    }
}

def haversine_km(lat1, lng1, lat2, lng2):
    """Tính khoảng cách đường chim bay (km)."""
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

def calc_shipping_fee(distance_km, mode='motorbike'):
    """
    Tính phí ship:
    - Walking: 0đ
    - Motorbike: Min 15k, 5k/km
    - Car: Min 30k, 12k/km
    """
    try:
        dist = float(distance_km or 0)
    except Exception:
        dist = 0.0

    if mode == 'walking':
        return 0, ""

    if mode == 'car':
        fee = max(30000, dist * 12000)
    else: 
        fee = max(15000, dist * 5000)

    fee_value = int(round(fee, -3))
    fee_text = f"{fee_value:,} đ".replace(',', '.')
    return fee_value, fee_text

def filter_pharmacies_in_radius(pharmacies, user_lat, user_lng, radius_km):
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

    def get_traffic_status(self, check_time, vehicle):
        """
        Trả về (factor, note).
        Logic cố định, không random.
        """
        if vehicle == 'walking':
            return 1.0, ""

        hour = check_time.hour
        # Logic giờ cao điểm
        morning = TRAFFIC_CONFIG['rush_hour']['morning']
        evening = TRAFFIC_CONFIG['rush_hour']['evening']

        is_rush = (morning[0] <= hour < morning[1]) or (evening[0] <= hour < evening[1])

        if is_rush:
            factor = TRAFFIC_CONFIG['penalty'].get(vehicle, 1.0)
            note = "Giờ cao điểm (Tắc đường)"
            return factor, note
        
        return 1.0, ""

    def get_route(self, start_lat, start_lng, end_lat, end_lng, mode='motorbike', departure_time_str=None):
        try:
            s_lat, s_lng = float(start_lat), float(start_lng)
            e_lat, e_lng = float(end_lat), float(end_lng)
        except ValueError:
            return {'error': 'Tọa độ lỗi.'}

        # 1. Xác định thời gian
        check_time = datetime.now()
        if departure_time_str:
            try:
                h, m = map(int, departure_time_str.split(':'))
                check_time = check_time.replace(hour=h, minute=m)
            except:
                pass 

        # 2. Lấy hệ số giao thông (CỐ ĐỊNH, KHÔNG RANDOM)
        traffic_factor, traffic_note = self.get_traffic_status(check_time, mode)

        # 3. Cấu hình OSRM
        osrm_profile = 'foot' if mode == 'walking' else 'driving'
        
        coords = f"{s_lng},{s_lat};{e_lng},{e_lat}"
        url = f"{self.OSRM_URL}/{osrm_profile}/{coords}"
        params = {'overview': 'full', 'geometries': 'polyline', 'steps': 'true', 'alternatives': 'true'}
        headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/91.0.4472.124 Safari/537.36'}

        try:
            response = requests.get(url, params=params, headers=headers, timeout=10)
            data = response.json()

            if response.status_code == 200 and data.get('code') == 'Ok':
                routes_result = []
                for index, route in enumerate(data['routes']):
                    distance_km = route['distance'] / 1000

                    # 4. Tính toán thời gian
                    # Nếu là đi bộ -> BẮT BUỘC dùng công thức riêng để đảm bảo chậm hơn xe máy
                    if mode == 'walking':
                        speed = TRAFFIC_CONFIG['speed']['walking']
                        base_duration_min = (distance_km / speed) * 60
                    else:
                        # Xe máy/Ô tô: Lấy từ API nếu có
                        osrm_sec = route.get('duration')
                        if osrm_sec:
                            base_duration_min = osrm_sec / 60
                        else:
                            speed = TRAFFIC_CONFIG['speed'].get(mode, 30)
                            base_duration_min = (distance_km / speed) * 60

                    # Áp dụng hệ số kẹt xe
                    final_duration_min = base_duration_min * traffic_factor
                    
                    # Làm tròn
                    final_duration_min = int(round(final_duration_min))
                    if final_duration_min < 1: final_duration_min = 1

                    summary = route['legs'][0].get('summary', '') if route.get('legs') else f"Tuyến đường {index+1}"
                    if not summary: summary = f"Tuyến đường {index+1}"

                    # Note hiển thị
                    display_note = ""
                    if traffic_factor > 1.0:
                        percent = int((traffic_factor - 1) * 100)
                        display_note = f"{traffic_note} (+{percent}% thời gian)"

                    routes_result.append({
                        'id': index,
                        'summary': summary,
                        'distance_km': round(distance_km, 2),
                        'duration_min': final_duration_min,
                        'route_points': polyline.decode(route['geometry']),
                        'traffic_note': display_note,
                        'traffic_factor': traffic_factor
                    })

                return {
                    'routes': routes_result,
                    'mode': mode,
                    'check_time': check_time.strftime("%H:%M")
                }
            else:
                return {'error': 'Không tìm thấy đường.'}
        except Exception as e:
            return {'error': str(e)}