import math
import re
from datetime import datetime

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
    'peak_windows': {
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
    },
}

NOMINATIM_SEARCH_URL = "https://nominatim.openstreetmap.org/search"
NOMINATIM_REVERSE_URL = "https://nominatim.openstreetmap.org/reverse"
PHOTON_SEARCH_URL = "https://photon.komoot.io/api/"
BIGDATACLOUD_REVERSE_URL = "https://api.bigdatacloud.net/data/reverse-geocode-client"

GEOCODE_SEARCH_CACHE = {}
GEOCODE_REVERSE_CACHE = {}


def _build_geocode_headers(context_label):
    return {
        'User-Agent': f'GIS-Pharma/1.0 ({context_label})',
        'Accept-Language': 'vi,en',
    }


def _copy_search_results(results):
    return [dict(item) for item in (results or [])]


def _append_search_result(search_results, seen_keys, *, lat, lng, display_name, type_label, limit_value):
    try:
        lat_value = float(lat)
        lng_value = float(lng)
    except (TypeError, ValueError):
        return False

    normalized_name = (display_name or '').strip() or 'Địa điểm'
    dedupe_key = (round(lat_value, 6), round(lng_value, 6), normalized_name.casefold())
    if dedupe_key in seen_keys:
        return False

    seen_keys.add(dedupe_key)
    search_results.append(
        {
            'display_name': normalized_name,
            'lat': lat_value,
            'lng': lng_value,
            'type_label': (type_label or 'location'),
        }
    )
    return len(search_results) >= limit_value


def _normalize_country_codes(country_codes):
    return {item.strip().casefold() for item in str(country_codes or '').split(',') if item.strip()}


def _format_photon_display_name(properties, fallback_text):
    ordered_parts = [
        properties.get('name'),
        properties.get('house_number'),
        properties.get('street'),
        properties.get('district'),
        properties.get('city'),
        properties.get('state'),
        properties.get('country'),
    ]
    seen = set()
    parts = []
    for part in ordered_parts:
        text = str(part or '').strip()
        if not text:
            continue
        normalized = text.casefold()
        if normalized in seen:
            continue
        seen.add(normalized)
        parts.append(text)
    return ', '.join(parts) or fallback_text


def _format_bigdatacloud_display_name(data, fallback_text):
    ordered_parts = [
        data.get('locality'),
        data.get('city'),
        data.get('principalSubdivision'),
        data.get('countryName'),
    ]
    seen = set()
    parts = []
    for part in ordered_parts:
        text = str(part or '').strip()
        if not text:
            continue
        normalized = text.casefold()
        if normalized in seen:
            continue
        seen.add(normalized)
        parts.append(text)
    return ', '.join(parts) or fallback_text


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

    for period_key, period in TRAFFIC_CONFIG['peak_windows'].items():
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
    shipping_fee_multiplier = 1.0 if delivery_mode != 'motorbike' else float(active_period.get('shipping_fee_multiplier', 1.0) or 1.0)
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


def calculate_estimated_delivery_info(departure_time_str=None, duration_minutes=0):
    normalized_time = normalize_departure_time_str(departure_time_str)
    departure_minutes = _parse_time_string_to_minutes(normalized_time)
    if departure_minutes is None:
        departure_minutes = _parse_time_string_to_minutes(datetime.now().strftime('%H:%M')) or 0

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


def calculate_shipping_fee(estimated_distance_km, delivery_mode='motorbike', departure_time_str=None, return_details=False):
    """
    Tính phí giao hàng dựa trên quãng đường và khung giờ xuất phát.
    """
    try:
        distance_value = float(estimated_distance_km)
    except (TypeError, ValueError):
        distance_value = 0.0

    if distance_value <= 3:
        base_shipping_fee = 15000
    else:
        base_shipping_fee = 15000 + int((distance_value - 3) * 5000)

    base_shipping_fee = int(round(base_shipping_fee, -3))

    traffic_profile = get_departure_traffic_profile(departure_time_str, delivery_mode)
    shipping_fee_value = base_shipping_fee
    if delivery_mode == 'motorbike' and traffic_profile['shipping_fee_multiplier'] > 1:
        shipping_fee_value = int(round(base_shipping_fee * traffic_profile['shipping_fee_multiplier'], -3))

    shipping_fee_text = f"{shipping_fee_value:,} đ".replace(',', '.')

    if not return_details:
        return shipping_fee_value, shipping_fee_text

    return {
        'base_shipping_fee_value': base_shipping_fee,
        'base_shipping_fee_text': f"{base_shipping_fee:,} đ".replace(',', '.'),
        'shipping_fee_value': shipping_fee_value,
        'shipping_fee_text': shipping_fee_text,
        'fee_multiplier': traffic_profile['shipping_fee_multiplier'],
        'fee_increase_percent': traffic_profile['fee_increase_percent'],
        'traffic_profile': traffic_profile,
    }


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
    cache_key = (query_text.casefold(), limit_value, str(country_codes or '').casefold())
    cached_results = GEOCODE_SEARCH_CACHE.get(cache_key)
    if cached_results is not None:
        return _copy_search_results(cached_results)

    normalized_query = re.sub(r"\s+", " ", query_text).strip()
    variants = [normalized_query]

    if "/" in normalized_query:
        compact_variant = re.sub(r"\s*/\s*", "/", normalized_query)
        spaced_variant = compact_variant.replace("/", " / ")
        slash_as_space_variant = compact_variant.replace("/", " ")
        hem_variant = compact_variant
        if not compact_variant.casefold().startswith("hem "):
            hem_variant = f"Hẻm {compact_variant}"
        for candidate in (compact_variant, spaced_variant, slash_as_space_variant, hem_variant):
            cleaned_candidate = re.sub(r"\s+", " ", candidate).strip()
            if cleaned_candidate and cleaned_candidate not in variants:
                variants.append(cleaned_candidate)

    if not any(keyword in normalized_query.casefold() for keyword in ("việt nam", "ho chi minh", "hồ chí minh", "tphcm", "tp hcm")):
        variants.extend(
            [
                f"{normalized_query}, Hồ Chí Minh, Việt Nam",
                f"{normalized_query}, Việt Nam",
            ]
        )

    search_results = []
    seen_keys = set()
    request_headers = _build_geocode_headers('Django address search')
    allowed_country_codes = _normalize_country_codes(country_codes)
    nominatim_available = True

    for variant in variants:
        if not nominatim_available:
            break

        try:
            response = requests.get(
                NOMINATIM_SEARCH_URL,
                params={
                    'q': variant,
                    'format': 'json',
                    'limit': limit_value,
                    'countrycodes': country_codes,
                    'addressdetails': 1,
                },
                headers=request_headers,
                timeout=10,
            )
        except requests.RequestException:
            nominatim_available = False
            break

        if response.status_code in {403, 429}:
            nominatim_available = False
            break

        try:
            response.raise_for_status()
            payload = response.json()
        except (requests.RequestException, ValueError):
            continue

        for item in payload:
            if _append_search_result(
                search_results,
                seen_keys,
                lat=item.get('lat'),
                lng=item.get('lon'),
                display_name=item.get('display_name', query_text),
                type_label=item.get('type') or item.get('class') or 'location',
                limit_value=limit_value,
            ):
                GEOCODE_SEARCH_CACHE[cache_key] = _copy_search_results(search_results)
                return _copy_search_results(search_results)

    if search_results:
        GEOCODE_SEARCH_CACHE[cache_key] = _copy_search_results(search_results)
        return _copy_search_results(search_results)

    photon_headers = _build_geocode_headers('Photon address search fallback')
    for variant in variants:
        try:
            response = requests.get(
                PHOTON_SEARCH_URL,
                params={
                    'q': variant,
                    'limit': limit_value,
                },
                headers=photon_headers,
                timeout=10,
            )
            response.raise_for_status()
            payload = response.json()
        except (requests.RequestException, ValueError):
            continue

        for feature in payload.get('features', []):
            geometry = feature.get('geometry') or {}
            coordinates = geometry.get('coordinates') or []
            if len(coordinates) < 2:
                continue
            properties = feature.get('properties') or {}
            country_code = str(properties.get('countrycode') or '').casefold()
            if allowed_country_codes and country_code and country_code not in allowed_country_codes:
                continue
            if _append_search_result(
                search_results,
                seen_keys,
                lat=coordinates[1],
                lng=coordinates[0],
                display_name=_format_photon_display_name(properties, query_text),
                type_label=properties.get('type') or properties.get('osm_value') or 'location',
                limit_value=limit_value,
            ):
                GEOCODE_SEARCH_CACHE[cache_key] = _copy_search_results(search_results)
                return _copy_search_results(search_results)

    GEOCODE_SEARCH_CACHE[cache_key] = _copy_search_results(search_results)
    return _copy_search_results(search_results)


def reverse_geocode_coordinates(lat, lng):
    """
    Tra ve dia chi gan nhat tu cap toa do.
    """
    fallback_payload = {
        'display_name': f'Tọa độ: {float(lat):.5f}, {float(lng):.5f}',
        'lat': float(lat),
        'lng': float(lng),
    }
    if requests is None:
        return fallback_payload

    try:
        cache_key = (round(float(lat), 6), round(float(lng), 6))
    except (TypeError, ValueError):
        return fallback_payload

    cached_payload = GEOCODE_REVERSE_CACHE.get(cache_key)
    if cached_payload is not None:
        return dict(cached_payload)

    try:
        response = requests.get(
            NOMINATIM_REVERSE_URL,
            params={
                'lat': lat,
                'lon': lng,
                'format': 'jsonv2',
                'zoom': 18,
                'addressdetails': 1,
            },
            headers=_build_geocode_headers('Django reverse geocode'),
            timeout=10,
        )
        if response.status_code not in {403, 429}:
            response.raise_for_status()
            data = response.json()
            payload = {
                'display_name': data.get('display_name', '') or fallback_payload['display_name'],
                'lat': float(data.get('lat', lat)),
                'lng': float(data.get('lon', lng)),
            }
            GEOCODE_REVERSE_CACHE[cache_key] = dict(payload)
            return payload
    except (requests.RequestException, ValueError, TypeError):
        pass

    try:
        response = requests.get(
            BIGDATACLOUD_REVERSE_URL,
            params={
                'latitude': lat,
                'longitude': lng,
                'localityLanguage': 'vi',
            },
            headers=_build_geocode_headers('BigDataCloud reverse fallback'),
            timeout=10,
        )
        response.raise_for_status()
        data = response.json()
        payload = {
            'display_name': _format_bigdatacloud_display_name(data, fallback_payload['display_name']),
            'lat': float(data.get('latitude', lat)),
            'lng': float(data.get('longitude', lng)),
        }
        GEOCODE_REVERSE_CACHE[cache_key] = dict(payload)
        return payload
    except (requests.RequestException, ValueError, TypeError):
        GEOCODE_REVERSE_CACHE[cache_key] = dict(fallback_payload)
        return fallback_payload


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

    def estimate_travel_time_minutes(self, estimated_distance_km, delivery_mode, departure_time_str=None):
        """
        Tính thời gian di chuyển dự kiến theo quãng đường, vận tốc trung bình và khung giờ giao hàng.
        """
        average_speed = TRAFFIC_CONFIG['average_speed'].get(delivery_mode, 30)
        traffic_profile = get_departure_traffic_profile(departure_time_str, delivery_mode)
        adjusted_speed = average_speed * traffic_profile['speed_factor']

        if adjusted_speed <= 0:
            return 1

        estimated_minutes = int(round((estimated_distance_km / adjusted_speed) * 60))
        return max(estimated_minutes, 1)

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

        if delivery_mode not in TRAFFIC_CONFIG['average_speed']:
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
        estimated_duration_min = self.estimate_travel_time_minutes(shared_distance_km, delivery_mode, normalized_departure_time)
        shipping_fee_details = calculate_shipping_fee(
            shared_distance_km,
            delivery_mode=delivery_mode,
            departure_time_str=normalized_departure_time,
            return_details=True,
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

    def choose_best_pharmacy(self, pharmacies, delivery_lat, delivery_lng, delivery_mode='motorbike', departure_time_str=None):
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
                departure_time_str=departure_time_str,
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


def choose_best_pharmacy_fast(service, pharmacies, delivery_lat, delivery_lng, delivery_mode='motorbike', departure_time_str=None):
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
        departure_time_str=departure_time_str,
    )
    if 'routes' not in route_result or not route_result['routes']:
        return {'error': 'Khong the tinh duoc chi nhanh giao hang phu hop.'}

    return {
        'pharmacy': best_pharmacy,
        'route': route_result['routes'][0],
        'mode': route_result.get('mode', delivery_mode),
    }
