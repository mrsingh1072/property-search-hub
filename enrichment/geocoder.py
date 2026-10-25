"""Patna geocoding with a bounded search and persistent local cache.

Missing or out-of-market results remain unknown instead of becoming
city-centre locations. Only sourced Patna coordinates are accepted.
"""
import csv
import json
import logging
import os
from pathlib import Path
import threading

import requests
from geopy.geocoders import Nominatim
from geopy.extra.rate_limiter import RateLimiter

from city_config import CITY, STATE, AREAS_PATH, SEARCH_CENTER, ROOT, is_active_city, in_market_bounds

logger = logging.getLogger(__name__)
AREA_COORDS = {}
_CACHE_PATH = ROOT / 'runtime' / 'patna_geocodes.json'
_CACHE_LOCK = threading.RLock()
_LANDMARK_CACHE = {}
_USER_AGENT = os.environ.get('GEOCODER_USER_AGENT') or 'ApnaGhar-Patna/1.0'


def _load_areas_csv():
    if not AREAS_PATH.exists():
        return
    with AREAS_PATH.open(encoding='utf-8-sig') as handle:
        for row in csv.DictReader(handle):
            try:
                lat, lng = float(row['latitude']), float(row['longitude'])
                name = row.get('area_name_original', '').strip().casefold()
                if name and is_active_city(row.get('city')) and in_market_bounds(lat, lng):
                    AREA_COORDS[name] = (lat, lng)
            except (ValueError, TypeError, KeyError):
                continue


def _load_cache():
    try:
        stored = json.loads(_CACHE_PATH.read_text(encoding='utf-8'))
        if not isinstance(stored, dict):
            return
        for key, value in stored.items():
            if len(value) == 2 and in_market_bounds(float(value[0]), float(value[1])):
                _LANDMARK_CACHE[key] = tuple(value)
    except (OSError, ValueError, TypeError):
        pass


def _remember(key, coords):
    with _CACHE_LOCK:
        _LANDMARK_CACHE[key] = coords
        try:
            _CACHE_PATH.parent.mkdir(parents=True, exist_ok=True)
            _CACHE_PATH.write_text(json.dumps(_LANDMARK_CACHE), encoding='utf-8')
        except OSError:
            logger.warning('Could not persist geocoding cache')
    return coords


_load_areas_csv()
_load_cache()
_geolocator = Nominatim(user_agent=_USER_AGENT,
                        domain=os.environ.get('NOMINATIM_DOMAIN') or 'nominatim.openstreetmap.org')
# Single process, cached, at most one request per 1.1 seconds. See docs/PATNA.md.
_geocode_limited = RateLimiter(_geolocator.geocode, min_delay_seconds=1.1,
                               max_retries=0, swallow_exceptions=False)


def _match_area_coords(text):
    return AREA_COORDS.get((text or '').strip().casefold())


def _extract_locality(address):
    skip = {CITY.casefold(), STATE.casefold(), 'india'}
    for part in (address or '').split(','):
        part = part.strip()
        if part and part.casefold() not in skip and not part.isdigit():
            return part
    return None


def get_area_coords(area_name, city=CITY):
    if not area_name or not is_active_city(city):
        return None
    return _match_area_coords(area_name) or geocode_area(area_name, city)


def geocode_address(address, city=CITY, state=STATE):
    if not address or not is_active_city(city) or (state or STATE).casefold() != STATE.casefold():
        return None
    # An exact whole-locality match is a centroid, not a precise street address.
    known = _match_area_coords(address)
    if known:
        return known
    query = f'{address}, {CITY}, {STATE}, India'
    return _try_nominatim(query)


def geocode_area(area_name, city=CITY):
    if not area_name or not is_active_city(city):
        return None
    known = _match_area_coords(area_name)
    if known:
        return known
    query = f'{area_name}, {CITY}, {STATE}, India'
    return _try_photon(query) or _try_nominatim(query)


def _try_photon(query):
    key = 'photon:' + query.strip().casefold()
    if key in _LANDMARK_CACHE:
        return _LANDMARK_CACHE[key]
    lat_bias, lng_bias = SEARCH_CENTER
    try:
        response = requests.get(os.environ.get('PHOTON_URL') or 'https://photon.komoot.io/api',
            params={'q': query, 'limit': 5, 'lat': lat_bias, 'lon': lng_bias},
            headers={'User-Agent': _USER_AGENT}, timeout=10)
        response.raise_for_status()
        for feature in response.json().get('features', []):
            if (feature.get('properties') or {}).get('osm_value') in {'city', 'state', 'country'}:
                continue
            lng, lat = feature['geometry']['coordinates'][:2]
            if in_market_bounds(float(lat), float(lng)):
                return _remember(key, (float(lat), float(lng)))
    except (requests.RequestException, ValueError, TypeError, KeyError):
        logger.warning('Photon lookup unavailable; leaving coordinates unknown')
    return None


def _try_nominatim(query):
    key = 'nominatim:' + query.strip().casefold()
    if key in _LANDMARK_CACHE:
        return _LANDMARK_CACHE[key]
    try:
        location = _geocode_limited(query, timeout=10, country_codes='in', addressdetails=True)
        if location:
            if location.raw.get('addresstype') in {'city', 'state', 'country', 'county'}:
                return None
            lat, lng = float(location.latitude), float(location.longitude)
            if in_market_bounds(lat, lng):
                return _remember(key, (lat, lng))
    except Exception as exc:
        logger.warning('Nominatim lookup unavailable (%s); leaving coordinates unknown', type(exc).__name__)
    return None
