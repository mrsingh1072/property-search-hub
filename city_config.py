"""Active ApnaGhar market. Historical inventories keep their original locations."""
from pathlib import Path

ROOT = Path(__file__).resolve().parent
CITY = "Patna"
STATE = "Bihar"
COUNTRY = "India"
AREAS = (
    "Boring Road", "Kankarbagh", "Bailey Road", "Patliputra Colony", "Danapur",
    "Saguna More", "Digha", "Rajendra Nagar", "Phulwari Sharif", "Bihta",
    "Ashiana Nagar", "Kadamkuan", "Gola Road", "Rukanpura", "Anisabad",
    "Gardanibagh", "Mithapur", "Patna City", "Khagaul", "Jagdeo Path",
)
AREA_ALIASES = {
    "boring rd": "Boring Road", "boringroad": "Boring Road",
    "kankar bagh": "Kankarbagh", "kankarbag": "Kankarbagh",
    "bailey rd": "Bailey Road", "baileyroad": "Bailey Road",
    "patliputra": "Patliputra Colony", "patliputra colony": "Patliputra Colony",
    "pataliputra": "Patliputra Colony", "saguna mor": "Saguna More",
    "saguna more": "Saguna More", "sagunamore": "Saguna More",
    "phulwari sarif": "Phulwari Sharif", "phulwarisharif": "Phulwari Sharif",
    "rajendranagar": "Rajendra Nagar", "gola rd": "Gola Road",
    "ashiana": "Ashiana Nagar", "asiana nagar": "Ashiana Nagar",
}
KNOWN_AREAS = {area.lower() for area in AREAS} | set(AREA_ALIASES) | {CITY.lower()}

# Search bias and acceptance envelope, not legal municipal boundaries or listing coordinates.
SEARCH_CENTER = (25.61, 85.14)
SEARCH_BOUNDS = (25.30, 84.65, 25.90, 85.55)  # south, west, north, east
INVENTORY_PATH = ROOT / "data" / "patna" / "rag_properties.json"
AREAS_PATH = ROOT / "data" / "patna" / "areas.csv"


def is_active_city(value: str | None) -> bool:
    return bool(value) and value.strip().casefold() == CITY.casefold()


def in_market_bounds(lat: float, lng: float) -> bool:
    south, west, north, east = SEARCH_BOUNDS
    return south <= lat <= north and west <= lng <= east
