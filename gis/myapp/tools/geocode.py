import math
import re
import unicodedata

try:
    import requests
except ImportError:
    requests = None


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
    return [
        {
            key: value
            for key, value in dict(item).items()
            if not str(key).startswith('_')
        }
        for item in (results or [])
    ]


def _append_search_result(
    search_results,
    seen_keys,
    *,
    lat,
    lng,
    display_name,
    type_label,
    raw_type=None,
    raw_class=None,
    source_label='',
):
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
            '_raw_type': (raw_type or type_label or ''),
            '_raw_class': (raw_class or ''),
            '_source': source_label,
            '_order': len(search_results),
        }
    )
    return False


def _normalize_country_codes(country_codes):
    return {item.strip().casefold() for item in str(country_codes or '').split(',') if item.strip()}


SEARCH_STOPWORDS = {
    'duong', 'd', 'so', 'hem', 'ngo', 'ngach', 'pho', 'phuong', 'p',
    'quan', 'q', 'huyen', 'tp', 'thanh', 'pho', 'tinh', 'viet', 'nam',
}

RESULT_TYPE_SCORES = {
    'house': 95,
    'building': 90,
    'pharmacy': 88,
    'hospital': 82,
    'clinic': 80,
    'street': 64,
    'road': 74,
    'residential': 72,
    'service': 70,
    'primary': 68,
    'secondary': 66,
    'tertiary': 64,
    'unclassified': 60,
    'living_street': 60,
    'amenity': 50,
    'shop': 48,
    'commercial': 42,
    'administrative': -35,
    'suburb': -20,
    'village': -25,
    'hamlet': -25,
    'city': -30,
    'county': -35,
    'state': -45,
}


def _normalize_search_text(value):
    normalized = unicodedata.normalize('NFD', str(value or '').casefold())
    normalized = ''.join(
        char
        for char in normalized
        if unicodedata.category(char) != 'Mn'
    )
    normalized = normalized.replace('đ', 'd')
    return re.sub(r'[^a-z0-9]+', ' ', normalized).strip()


def _extract_search_tokens(value):
    tokens = []
    for token in _normalize_search_text(value).split():
        if len(token) <= 1 or token in SEARCH_STOPWORDS:
            continue
        tokens.append(token)
    return tokens


def _extract_number_tokens(value):
    return re.findall(r'\d+(?:/\d+)*[a-zA-Z]?', str(value or ''))


def _distance_km(lat1, lng1, lat2, lng2):
    if lat1 is None or lng1 is None:
        return None
    radius_km = 6371.0
    lat1_rad = math.radians(float(lat1))
    lat2_rad = math.radians(float(lat2))
    delta_lat = math.radians(float(lat2) - float(lat1))
    delta_lng = math.radians(float(lng2) - float(lng1))
    a = (
        math.sin(delta_lat / 2) ** 2
        + math.cos(lat1_rad) * math.cos(lat2_rad) * math.sin(delta_lng / 2) ** 2
    )
    return radius_km * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))


def _score_search_result(item, query_text, bias_lat=None, bias_lng=None):
    display_name = item.get('display_name', '')
    display_normalized = _normalize_search_text(display_name)
    display_tokens = set(display_normalized.split())
    query_tokens = _extract_search_tokens(query_text)
    number_tokens = _extract_number_tokens(query_text)

    raw_type = _normalize_search_text(item.get('_raw_type') or item.get('type_label')).split()
    raw_class = _normalize_search_text(item.get('_raw_class')).split()
    type_key = raw_type[0] if raw_type else ''
    class_key = raw_class[0] if raw_class else ''

    score = RESULT_TYPE_SCORES.get(type_key, 25)
    if class_key in {'highway', 'building', 'amenity', 'shop'}:
        score += 14
    elif class_key in {'boundary', 'place'}:
        score -= 18

    if query_tokens:
        matched_tokens = sum(
            1
            for token in query_tokens
            if token in display_tokens or token in display_normalized
        )
        score += 80 * (matched_tokens / len(query_tokens))

    if number_tokens:
        display_number_tokens = _extract_number_tokens(display_name)
        has_matching_number = any(
            number.casefold() in display_tokens or number.casefold() in display_normalized
            for number in number_tokens
        )
        if has_matching_number:
            score += 34
        else:
            score -= 18
            if display_number_tokens:
                score -= 24
            if type_key in {'house', 'building'} or class_key in {'building', 'amenity', 'shop'}:
                score -= 70

    if 'ho chi minh' in display_normalized or 'hcm' in display_normalized:
        score += 12
    elif 'viet nam' in display_normalized:
        score += 4

    distance = _distance_km(bias_lat, bias_lng, item.get('lat'), item.get('lng'))
    if distance is not None:
        item['_distance_km'] = distance
        if distance <= 2:
            score += 35
        elif distance <= 5:
            score += 26
        elif distance <= 15:
            score += 16
        elif distance <= 30:
            score += 6
        elif distance <= 60:
            score -= 35
        elif distance <= 120:
            score -= 95
        else:
            score -= 180
        score -= min(distance, 160) * 0.35

    if item.get('_source') == 'photon':
        score += 4

    item['_score'] = score
    return score


def _rank_search_results(search_results, query_text, limit_value, bias_lat=None, bias_lng=None):
    ranked = list(search_results or [])
    for item in ranked:
        _score_search_result(item, query_text, bias_lat=bias_lat, bias_lng=bias_lng)

    ranked.sort(
        key=lambda item: (
            -item.get('_score', 0),
            item.get('_distance_km', 999999),
            item.get('_order', 999999),
        )
    )
    return _copy_search_results(ranked[:limit_value])


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


REVERSE_ADMIN_PARENT_OVERRIDES = {
    'thanh pho thu duc': {
        'parent': 'Thành phố Hồ Chí Minh',
        'bounds': {
            'lat_min': 10.35,
            'lat_max': 11.20,
            'lng_min': 106.35,
            'lng_max': 107.05,
        },
    },
}


def _clean_reverse_component(value):
    text = re.sub(r'\s+', ' ', str(value or '')).strip(' ,')
    return text or None


def _append_reverse_component(parts, value):
    text = _clean_reverse_component(value)
    if not text:
        return
    normalized = _normalize_search_text(text)
    if not normalized:
        return
    if any(_normalize_search_text(part) == normalized for part in parts):
        return
    parts.append(text)


def _is_within_bounds(lat, lng, bounds):
    try:
        lat_value = float(lat)
        lng_value = float(lng)
    except (TypeError, ValueError):
        return False
    return (
        bounds['lat_min'] <= lat_value <= bounds['lat_max']
        and bounds['lng_min'] <= lng_value <= bounds['lng_max']
    )


def _reverse_parent_for_component(component, lat=None, lng=None):
    override = REVERSE_ADMIN_PARENT_OVERRIDES.get(_normalize_search_text(component))
    if not override:
        return None
    if not _is_within_bounds(lat, lng, override['bounds']):
        return None
    return override['parent']


def _is_reverse_admin_noise(component, lat=None, lng=None):
    normalized = _normalize_search_text(component)
    if not normalized:
        return True
    return _reverse_parent_for_component(component, lat=lat, lng=lng) is not None


def _is_reverse_tail_component(component):
    normalized = _normalize_search_text(component)
    if normalized in {'viet nam', 'vietnam'}:
        return True
    return bool(re.fullmatch(r'\d{4,6}', str(component or '').strip()))


def _clean_reverse_display_name(display_name, fallback_text, lat=None, lng=None):
    parts = []
    parents = []
    tail_parts = []
    for component in str(display_name or '').split(','):
        text = _clean_reverse_component(component)
        if not text:
            continue
        if _is_reverse_admin_noise(text, lat=lat, lng=lng):
            parent = _reverse_parent_for_component(text, lat=lat, lng=lng)
            if parent:
                parents.append(parent)
            continue
        if _is_reverse_tail_component(text):
            _append_reverse_component(tail_parts, text)
        else:
            _append_reverse_component(parts, text)
    for parent in parents:
        _append_reverse_component(parts, parent)
    for text in tail_parts:
        _append_reverse_component(parts, text)
    return ', '.join(parts) or fallback_text


def _format_nominatim_reverse_display_name(data, fallback_text):
    """
    Nominatim reverse sometimes returns a raw `display_name` with an
    unreliable intermediate administrative layer. Build the address from
    structured fields so the UI shows a cleaner, less misleading label.
    """
    address = data.get('address') or {}
    result_lat = data.get('lat')
    result_lng = data.get('lon')
    if not isinstance(address, dict) or not address:
        return _clean_reverse_display_name(data.get('display_name'), fallback_text, lat=result_lat, lng=result_lng)

    parts = []
    road_name = (
        address.get('road')
        or address.get('pedestrian')
        or address.get('residential')
        or address.get('footway')
        or address.get('path')
    )
    house_number = _clean_reverse_component(address.get('house_number'))
    road_text = _clean_reverse_component(road_name)
    if house_number and road_text and house_number not in road_text:
        _append_reverse_component(parts, f'{house_number} {road_text}')
    else:
        _append_reverse_component(parts, road_text)

    for key in ('neighbourhood', 'quarter', 'suburb', 'village'):
        _append_reverse_component(parts, address.get(key))

    parent_components = []
    for key in ('city_district', 'district', 'county', 'city', 'town', 'state', 'province'):
        component = _clean_reverse_component(address.get(key))
        if not component:
            continue
        if key in {'city_district', 'district', 'county', 'city', 'town'} and _is_reverse_admin_noise(component, lat=result_lat, lng=result_lng):
            parent = _reverse_parent_for_component(component, lat=result_lat, lng=result_lng)
            if parent:
                parent_components.append(parent)
            continue
        _append_reverse_component(parts, component)

    for parent in parent_components:
        _append_reverse_component(parts, parent)

    _append_reverse_component(parts, address.get('postcode'))
    _append_reverse_component(parts, address.get('country'))

    return ', '.join(parts) or _clean_reverse_display_name(data.get('display_name'), fallback_text, lat=result_lat, lng=result_lng)


CITY_HINT_KEYWORDS = (
    "việt nam", "viet nam",
    "hồ chí minh", "ho chi minh", "tphcm", "tp hcm", "tp.hcm", "tp. hcm", "sài gòn", "sai gon",
    "hà nội", "ha noi",
    "đà nẵng", "da nang",
    "hải phòng", "hai phong",
    "cần thơ", "can tho",
    "biên hòa", "bien hoa",
    "nha trang", "huế", "hue", "vũng tàu", "vung tau",
    "bình dương", "binh duong", "đồng nai", "dong nai",
)


def _coerce_float(value):
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _build_search_variants(normalized_query):
    """
    Sinh các biến thể truy vấn theo thứ tự ưu tiên:
    biến thể có hậu tố thành phố/quốc gia chạy TRƯỚC, biến thể trần
    chỉ chạy như fallback. Nhờ đó kết quả đầu tiên thường rơi vào
    đúng địa phương người dùng kỳ vọng (ví dụ: "Lê Lợi" → đường Lê
    Lợi tại HCM thay vì một đường trùng tên ở tỉnh khác).
    """
    core_variants = [normalized_query]

    if "/" in normalized_query:
        compact_variant = re.sub(r"\s*/\s*", "/", normalized_query)
        spaced_variant = compact_variant.replace("/", " / ")
        slash_as_space_variant = compact_variant.replace("/", " ")
        hem_variant = compact_variant
        if not compact_variant.casefold().startswith("hem "):
            hem_variant = f"Hẻm {compact_variant}"
        for candidate in (compact_variant, spaced_variant, slash_as_space_variant, hem_variant):
            cleaned_candidate = re.sub(r"\s+", " ", candidate).strip()
            if cleaned_candidate and cleaned_candidate not in core_variants:
                core_variants.append(cleaned_candidate)

    has_city_hint = any(
        keyword in normalized_query.casefold()
        for keyword in CITY_HINT_KEYWORDS
    )

    ordered = []
    if not has_city_hint:
        for core in core_variants:
            ordered.append(f"{core}, Hồ Chí Minh, Việt Nam")
        for core in core_variants:
            ordered.append(f"{core}, Việt Nam")
    ordered.extend(core_variants)

    seen = set()
    deduped = []
    for variant in ordered:
        key = variant.casefold()
        if key in seen:
            continue
        seen.add(key)
        deduped.append(variant)
    return deduped


def _build_viewbox(bias_lat, bias_lng, half_span_deg=0.45):
    """
    Tạo `viewbox` dạng `lon_left,lat_top,lon_right,lat_bottom` quanh toạ
    độ gợi ý. half_span_deg ~0.45° ≈ 50km — đủ rộng để bao toàn bộ một
    đô thị lớn (HCM, HN, ĐN) nhưng vẫn đủ hẹp để loại các tỉnh xa.
    """
    if bias_lat is None or bias_lng is None:
        return None
    lat_top = bias_lat + half_span_deg
    lat_bottom = bias_lat - half_span_deg
    lon_left = bias_lng - half_span_deg
    lon_right = bias_lng + half_span_deg
    return f"{lon_left:.4f},{lat_top:.4f},{lon_right:.4f},{lat_bottom:.4f}"


def search_address_candidates(query, limit=5, country_codes='vn', bias_lat=None, bias_lng=None):
    """
    Tìm các địa điểm gần đúng theo từ khóa địa chỉ.

    Tham số `bias_lat`, `bias_lng` (tuỳ chọn) — toạ độ trung tâm bản đồ
    của trang đang gọi, dùng để ưu tiên kết quả gần khu vực user đang
    xem (giải thuật `viewbox` của Nominatim, `lat/lon` của Photon).
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
    bias_lat_value = _coerce_float(bias_lat)
    bias_lng_value = _coerce_float(bias_lng)
    cache_key = (
        query_text.casefold(),
        limit_value,
        str(country_codes or '').casefold(),
        round(bias_lat_value, 2) if bias_lat_value is not None else None,
        round(bias_lng_value, 2) if bias_lng_value is not None else None,
    )
    cached_results = GEOCODE_SEARCH_CACHE.get(cache_key)
    if cached_results is not None:
        return _copy_search_results(cached_results)

    normalized_query = re.sub(r"\s+", " ", query_text).strip()
    variants = _build_search_variants(normalized_query)
    viewbox = _build_viewbox(bias_lat_value, bias_lng_value)

    search_results = []
    seen_keys = set()
    request_headers = _build_geocode_headers('Django address search')
    allowed_country_codes = _normalize_country_codes(country_codes)
    nominatim_available = True

    for variant in variants:
        if not nominatim_available:
            break

        nominatim_params = {
            'q': variant,
            'format': 'json',
            'limit': limit_value,
            'countrycodes': country_codes,
            'addressdetails': 1,
        }
        if viewbox:
            nominatim_params['viewbox'] = viewbox
            nominatim_params['bounded'] = 0  # ưu tiên mềm, không loại tuyệt đối

        try:
            response = requests.get(
                NOMINATIM_SEARCH_URL,
                params=nominatim_params,
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
                raw_type=item.get('type'),
                raw_class=item.get('class'),
                source_label='nominatim',
            ):
                break

    if search_results:
        ranked_results = _rank_search_results(
            search_results,
            normalized_query,
            limit_value,
            bias_lat=bias_lat_value,
            bias_lng=bias_lng_value,
        )
        if not _extract_number_tokens(normalized_query):
            GEOCODE_SEARCH_CACHE[cache_key] = _copy_search_results(ranked_results)
            return _copy_search_results(ranked_results)

    photon_headers = _build_geocode_headers('Photon address search fallback')
    for variant in variants:
        photon_params = {
            'q': variant,
            'limit': limit_value,
        }
        if bias_lat_value is not None and bias_lng_value is not None:
            photon_params['lat'] = bias_lat_value
            photon_params['lon'] = bias_lng_value
            photon_params['zoom'] = 12
        try:
            response = requests.get(
                PHOTON_SEARCH_URL,
                params=photon_params,
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
                raw_type=properties.get('type') or properties.get('osm_value'),
                raw_class=properties.get('osm_key'),
                source_label='photon',
            ):
                break

    ranked_results = _rank_search_results(
        search_results,
        normalized_query,
        limit_value,
        bias_lat=bias_lat_value,
        bias_lng=bias_lng_value,
    )
    GEOCODE_SEARCH_CACHE[cache_key] = _copy_search_results(ranked_results)
    return _copy_search_results(ranked_results)


def reverse_geocode_coordinates(lat, lng):
    """
    Trả về địa chỉ gần nhất từ cặp tọa độ.
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
                'display_name': _format_nominatim_reverse_display_name(data, fallback_payload['display_name']),
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
