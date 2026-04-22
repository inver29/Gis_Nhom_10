import re

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


def search_address_candidates(query, limit=5, country_codes='vn'):
    """
    Tìm các địa điểm gần đúng theo từ khóa địa chỉ.
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
