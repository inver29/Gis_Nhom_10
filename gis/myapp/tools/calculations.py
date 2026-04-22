import math
from datetime import datetime


# ============================================================
# Cấu hình
# ============================================================

AVERAGE_SPEED_KMH = {
    'motorbike': 35,
    'car': 30,
    'walking': 4.5,
}

ROAD_DISTANCE_FACTOR = {
    'motorbike': 1.2,
    'car': 1.3,
    'walking': 1.05,
}

PEAK_WINDOWS = {
    'morning': {
        'label': 'Giờ cao điểm sáng',
        'start': '06:30',
        'end': '09:45',
        'speed_factor': {
            'motorbike': 0.78,
            'car': 0.72,
            'walking': 0.96,
        },
        'shipping_fee_multiplier': 1.15,
    },
    'evening': {
        'label': 'Giờ cao điểm chiều',
        'start': '16:00',
        'end': '19:30',
        'speed_factor': {
            'motorbike': 0.72,
            'car': 0.68,
            'walking': 0.94,
        },
        'shipping_fee_multiplier': 1.20,
    },
}

BASE_SHIPPING_FEE = 15000
BASE_SHIPPING_DISTANCE_KM = 3
EXTRA_SHIPPING_FEE_PER_KM = 5000


# ============================================================
# Khoảng cách
# ============================================================

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
    road_factor = ROAD_DISTANCE_FACTOR.get(delivery_mode, 1.2)
    return air_distance_km * road_factor


# ============================================================
# Thời gian và giờ cao điểm
# ============================================================

def _parse_time_string_to_minutes(raw_value):
    text = (raw_value or '').strip()
    if not text:
        return None

    try:
        parsed_time = datetime.strptime(text, '%H:%M')
    except ValueError:
        return None

    return parsed_time.hour * 60 + parsed_time.minute


def normalize_departure_time_str(raw_value=None):
    minutes_value = _parse_time_string_to_minutes(raw_value)
    if minutes_value is None:
        return datetime.now().strftime('%H:%M')
    return f"{minutes_value // 60:02d}:{minutes_value % 60:02d}"


def get_departure_traffic_profile(departure_time_str=None, delivery_mode='motorbike'):
    normalized_time = normalize_departure_time_str(departure_time_str)
    departure_minutes = _parse_time_string_to_minutes(normalized_time)

    active_period_key = None
    active_period = None

    for period_key, period in PEAK_WINDOWS.items():
        start_minutes = _parse_time_string_to_minutes(period.get('start'))
        end_minutes = _parse_time_string_to_minutes(period.get('end'))
        if start_minutes is None or end_minutes is None or departure_minutes is None:
            continue
        if start_minutes <= departure_minutes <= end_minutes:
            active_period_key = period_key
            active_period = period
            break

    if not active_period:
        return {
            'is_peak_hour': False,
            'period_key': '',
            'period_label': 'Khung giờ thông thường',
            'departure_time': normalized_time,
            'speed_factor': 1.0,
            'duration_multiplier': 1.0,
            'shipping_fee_multiplier': 1.0,
            'fee_increase_percent': 0,
            'notice': '',
        }

    speed_factor = float(active_period.get('speed_factor', {}).get(delivery_mode, 1.0) or 1.0)
    if speed_factor <= 0:
        speed_factor = 1.0

    duration_multiplier = round(1 / speed_factor, 2)
    shipping_fee_multiplier = (
        1.0
        if delivery_mode != 'motorbike'
        else float(active_period.get('shipping_fee_multiplier', 1.0) or 1.0)
    )
    fee_increase_percent = max(int(round((shipping_fee_multiplier - 1.0) * 100)), 0)

    notice = (
        f"Đang trong {active_period.get('label', 'giờ cao điểm').lower()}. "
        f"Thời gian di chuyển đang tăng khoảng {int(round((duration_multiplier - 1) * 100))}%"
    )
    if delivery_mode == 'motorbike' and fee_increase_percent > 0:
        notice += f", phí ship khi thanh toán tăng {fee_increase_percent}%"
    notice += '.'

    return {
        'is_peak_hour': True,
        'period_key': active_period_key or '',
        'period_label': active_period.get('label', 'Giờ cao điểm'),
        'departure_time': normalized_time,
        'speed_factor': speed_factor,
        'duration_multiplier': duration_multiplier,
        'shipping_fee_multiplier': shipping_fee_multiplier,
        'fee_increase_percent': fee_increase_percent,
        'notice': notice,
    }


def calculate_travel_time_minutes(distance_km, delivery_mode, departure_time_str=None):
    """
    Tính thời gian di chuyển dự kiến theo quãng đường, vận tốc trung bình và khung giờ giao hàng.
    """
    average_speed = AVERAGE_SPEED_KMH.get(delivery_mode, 30)
    traffic_profile = get_departure_traffic_profile(departure_time_str, delivery_mode)
    adjusted_speed = average_speed * traffic_profile['speed_factor']

    if adjusted_speed <= 0:
        return 1

    estimated_minutes = int(round((distance_km / adjusted_speed) * 60))
    return max(estimated_minutes, 1)


def calculate_estimated_delivery_info(departure_time_str=None, duration_minutes=0):
    normalized_time = normalize_departure_time_str(departure_time_str)
    departure_minutes = _parse_time_string_to_minutes(normalized_time)

    try:
        duration_value = int(round(float(duration_minutes or 0)))
    except (TypeError, ValueError):
        duration_value = 0

    duration_value = max(duration_value, 0)
    arrival_total_minutes = departure_minutes + duration_value
    day_offset = arrival_total_minutes // (24 * 60)
    arrival_minutes_of_day = arrival_total_minutes % (24 * 60)
    arrival_time_text = f"{arrival_minutes_of_day // 60:02d}:{arrival_minutes_of_day % 60:02d}"
    arrival_display_text = arrival_time_text
    if day_offset == 1:
        arrival_display_text += ' (ngày hôm sau)'
    elif day_offset > 1:
        arrival_display_text += f' (+{day_offset} ngày)'

    return {
        'departure_time': normalized_time,
        'duration_minutes': duration_value,
        'arrival_time': arrival_time_text,
        'arrival_day_offset': day_offset,
        'arrival_display_text': arrival_display_text,
    }


# ============================================================
# Phí giao hàng
# ============================================================

def calculate_shipping_fee(estimated_distance_km, delivery_mode='motorbike', departure_time_str=None):
    """
    Tính phí giao hàng dựa trên quãng đường và khung giờ xuất phát.
    """
    try:
        distance_value = float(estimated_distance_km)
    except (TypeError, ValueError):
        distance_value = 0.0

    if distance_value <= BASE_SHIPPING_DISTANCE_KM:
        base_shipping_fee = BASE_SHIPPING_FEE
    else:
        base_shipping_fee = BASE_SHIPPING_FEE + int(
            (distance_value - BASE_SHIPPING_DISTANCE_KM) * EXTRA_SHIPPING_FEE_PER_KM
        )

    base_shipping_fee = int(round(base_shipping_fee, -3))

    traffic_profile = get_departure_traffic_profile(departure_time_str, delivery_mode)
    shipping_fee_value = base_shipping_fee
    if delivery_mode == 'motorbike' and traffic_profile['shipping_fee_multiplier'] > 1:
        shipping_fee_value = int(round(base_shipping_fee * traffic_profile['shipping_fee_multiplier'], -3))

    shipping_fee_text = f"{shipping_fee_value:,} đ".replace(',', '.')

    return {
        'base_shipping_fee_value': base_shipping_fee,
        'base_shipping_fee_text': f"{base_shipping_fee:,} đ".replace(',', '.'),
        'shipping_fee_value': shipping_fee_value,
        'shipping_fee_text': shipping_fee_text,
        'fee_multiplier': traffic_profile['shipping_fee_multiplier'],
        'fee_increase_percent': traffic_profile['fee_increase_percent'],
        'traffic_profile': traffic_profile,
    }
