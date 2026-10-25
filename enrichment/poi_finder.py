"""Find real nearby OpenStreetMap POIs for Patna. Unknown distances stay null.

Distances are straight-line kilometres, not driving or walking route lengths.
POIs are looked up around accepted Patna coordinates only.
"""
import json
import logging
import math
import os
import time

import requests
from city_config import CITY, ROOT, in_market_bounds, is_active_city

logger = logging.getLogger(__name__)
_CATEGORIES = ('metro', 'railway', 'hospital', 'school', 'market', 'airport', 'bus_stop', 'park')
_CACHE_PATH = ROOT / 'runtime' / 'patna_pois.json'
_CACHE_TTL = 7 * 24 * 3600


def _haversine(lat1, lon1, lat2, lon2):
    dlat, dlon = math.radians(lat2 - lat1), math.radians(lon2 - lon1)
    value = math.sin(dlat / 2) ** 2 + math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) * math.sin(dlon / 2) ** 2
    return 6371.0 * 2 * math.asin(min(1.0, math.sqrt(value)))


def _find_nearest_local(lat, lng, poi_list):
    if not poi_list:
        return None
    best = min(poi_list, key=lambda p: _haversine(lat, lng, p['lat'], p['lng']))
    return _haversine(lat, lng, best['lat'], best['lng']), best['name']


def _empty_result(status):
    result = {'enrichment_source': 'openstreetmap_overpass', 'poi_status': status,
              'distance_kind': 'straight_line', 'fixed_anchors': {}}
    for category in _CATEGORIES:
        result[category + '_distance_km'] = None
        result[category + '_name'] = None
    return result


def _categories(tags):
    if any(tags.get(key) in {'yes', 'construction', 'proposed'} for key in ('disused', 'abandoned', 'construction', 'proposed')):
        return []
    found = []
    if tags.get('railway') == 'station':
        found.append('metro' if tags.get('station') == 'subway' else 'railway')
    if tags.get('amenity') in {'hospital', 'school', 'marketplace', 'bus_station'}:
        found.append({'hospital': 'hospital', 'school': 'school', 'marketplace': 'market', 'bus_station': 'bus_stop'}[tags['amenity']])
    if tags.get('aeroway') == 'aerodrome': found.append('airport')
    if tags.get('highway') == 'bus_stop': found.append('bus_stop')
    if tags.get('leisure') == 'park': found.append('park')
    return found


def _query_elements(lat, lng):
    key = f'{lat:.5f},{lng:.5f}'
    try:
        cache = json.loads(_CACHE_PATH.read_text(encoding='utf-8'))
    except (OSError, ValueError):
        cache = {}
    if not isinstance(cache, dict):
        cache = {}
    entry = cache.get(key, {})
    if not isinstance(entry, dict):
        entry = {}
    if time.time() - entry.get('timestamp', 0) < _CACHE_TTL:
        return entry['elements']
    around = f'(around:15000,{lat},{lng})'
    clauses = [f'nwr{around}["railway"="station"];',
               f'nwr{around}["amenity"~"^(hospital|school|marketplace|bus_station)$"];',
               f'nwr{around}["aeroway"="aerodrome"];',
               f'nwr{around}["highway"="bus_stop"];',
               f'nwr{around}["leisure"="park"];']
    query = '[out:json][timeout:20];(' + ''.join(clauses) + ');out center;'
    response = requests.post(os.environ.get('OVERPASS_URL') or 'https://overpass-api.de/api/interpreter',
        data={'data': query}, headers={'User-Agent': os.environ.get('GEOCODER_USER_AGENT') or 'ApnaGhar-Patna/1.0'}, timeout=30)
    response.raise_for_status()
    payload = response.json()
    if payload.get('remark'):
        raise ValueError('Overpass returned an incomplete result')
    elements = payload['elements']
    cache[key] = {'timestamp': time.time(), 'elements': elements}
    try:
        _CACHE_PATH.parent.mkdir(parents=True, exist_ok=True)
        _CACHE_PATH.write_text(json.dumps(cache), encoding='utf-8')
    except OSError:
        logger.warning('Could not persist POI cache')
    return elements


def find_nearby_pois(lat, lng, city=CITY):
    result = _empty_result('unavailable')
    if not is_active_city(city) or not in_market_bounds(lat, lng):
        return result
    try:
        elements = _query_elements(lat, lng)
    except (requests.RequestException, ValueError, TypeError, KeyError):
        logger.warning('POI lookup unavailable; distances remain unknown')
        return result
    candidates = {category: [] for category in _CATEGORIES}
    for element in elements:
        tags = element.get('tags') or {}
        coords = element if 'lat' in element else element.get('center') or {}
        if not tags.get('name') or 'lat' not in coords or 'lon' not in coords:
            continue
        poi_lat, poi_lng = float(coords['lat']), float(coords['lon'])
        if not in_market_bounds(poi_lat, poi_lng):
            continue
        for category in _categories(tags):
            candidates[category].append({'name': tags['name'], 'lat': poi_lat, 'lng': poi_lng})
    for category, pois in candidates.items():
        nearest = _find_nearest_local(lat, lng, pois)
        if nearest and nearest[0] <= 15:
            result[category + '_distance_km'] = round(nearest[0], 2)
            result[category + '_name'] = nearest[1]
    result['poi_status'] = 'looked_up'
    return result


def geocode_landmark_overpass(landmark_name, city=CITY):
    # One bounded geocoding path avoids inserting untrusted names into Overpass QL.
    from enrichment.geocoder import geocode_area
    return geocode_area(landmark_name, city)
