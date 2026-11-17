"""Validate normalized Patna inventory without changing files or contacting services."""
import argparse
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from broker.csv_schema import validate_row
from city_config import INVENTORY_PATH, CITY, STATE


def validate_documents(documents):
    if not isinstance(documents, list):
        return ['Inventory must be a JSON array.']
    errors = []
    ids = set()
    for number, document in enumerate(documents, 1):
        if not isinstance(document, dict):
            errors.append(f'Record {number}: must be an object.')
            continue
        sections = ['location', 'property_profile', 'pricing', 'metadata']
        if any(not isinstance(document.get(name), dict) for name in sections):
            errors.append(f'Record {number}: location, property_profile, pricing and metadata are required objects.')
            continue
        location, profile, pricing, metadata = (document[name] for name in sections)
        if location.get('city') != CITY or location.get('state') != STATE:
            errors.append(f'Record {number}: location must explicitly be {CITY}, {STATE}.')
        doc_id = document.get('doc_id')
        if not isinstance(doc_id, str) or not doc_id or doc_id in ids:
            errors.append(f'Record {number}: doc_id must be a unique nonempty string.')
        else:
            ids.add(doc_id)
        errors.extend(validate_row({'property_type': profile.get('property_type') or '',
            'price_inr': pricing.get('total_price_inr'), 'bhk': profile.get('bhk'),
            'address': metadata.get('raw_full_address') or location.get('area_name') or '',
            'city': CITY, 'state': STATE}, number))
    return errors


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('inventory', nargs='?', type=Path, default=INVENTORY_PATH)
    args = parser.parse_args()
    try:
        documents = json.loads(args.inventory.read_text(encoding='utf-8'))
    except (OSError, ValueError) as exc:
        print(f'Could not read inventory: {type(exc).__name__}')
        return 1
    errors = validate_documents(documents)
    if errors:
        print('\n'.join(errors))
        return 1
    print(f'Patna inventory structure valid: {len(documents)} record(s). No availability or legal verification implied.')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
